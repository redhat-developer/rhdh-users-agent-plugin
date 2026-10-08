# Workflow: Chart Migration (1.x to 2.x)

This workflow handles RHDH Helm chart major version upgrades where the values structure
changes. It combines a deterministic migration script with AI-assisted resolution of
ambiguous areas.

<required_reading>
Read these references before proceeding:

- `references/chart-migration-1x-2x.md` — mapping tables and ambiguous area guidance
- `references/secrets-detection.md` — secret scanning patterns
- `references/output-format.md` — report template (for the final combined report)
- `references/rhdh-local.md` — RHDH Local detection and recommendation
</required_reading>

## Step 0: Validate Prerequisites

1. Confirm this is a major version upgrade: the RHDH major version in `--from` differs
   from `--to` (e.g., 1.10 → 2.1).
2. Note the prerequisite: Kubernetes 1.31+ / OpenShift 4.18+.
3. Identify the Helm values file to migrate. Sources (in priority order):
   - `--config` flag pointing to a values.yaml
   - `.rhdh-upgrade-helper.yaml` config listing a values file
   - `--config-path` directory scan finding a `values*.yaml`
   - Ask the user for the file path

If no values file can be found, inform the user:
"Chart migration requires your 1.x Helm values file. Provide it with `--config ./values.yaml`
or export from a running release: `helm get values <release> -n <ns> -o yaml > old-values.yaml`"

## Step 1: Secrets Scan

Before any processing, scan the values file for embedded secrets per
`references/secrets-detection.md`. Same rules as `workflows/full-report.md` Step 0.

## Step 2: Run Deterministic Migration

The migration script **never modifies the original values file**. It reads the
1.x file and writes a separate draft 2.x file for the customer to inspect and
validate before using it in an upgrade.

Execute the migration script on the user's values file(s). If the customer uses
multiple values files (e.g., base + environment overrides), pass them all — each
is migrated independently and the output preserves the file separation:

```bash
SKILL_DIR="$(dirname "$(dirname "$0")")"  # or the installed skill directory

# Single file
python3 "$SKILL_DIR/scripts/migrate-chart-values.py" "$VALUES_FILE" \
  -o /tmp/rhdh-2x-values-draft.yaml \
  --report /tmp/rhdh-migration-report.json

# Multiple files — -o must be a directory
python3 "$SKILL_DIR/scripts/migrate-chart-values.py" $VALUES_FILES \
  -o /tmp/rhdh-2x-values-draft/ \
  --report /tmp/rhdh-migration-report.json

MIGRATION_EXIT=$?
```

Read the outputs:
- Single file: `/tmp/rhdh-2x-values-draft.yaml` — the draft 2.x values with MIGRATION-REVIEW markers
- Multiple files: `/tmp/rhdh-2x-values-draft/<filename>.yaml` — one draft per input file
- `/tmp/rhdh-migration-report.json` — structured report of all transformations (combined across files when multiple)

Present a summary to the user:

```
## Chart Values Migration: RHDH {from} → {to}

**Deterministic mappings applied:** {N} keys migrated automatically
**Removed values:** {M} keys with no 2.x equivalent
**Areas requiring review:** {R} (listed below)
**Unknown upstream keys:** {U} carried over with warnings
```

If `MIGRATION_EXIT == 0` (no review needed), skip to Step 4.

## Step 3: AI-Assisted Resolution of Ambiguous Areas

For each review item in the migration report, walk the user through the resolution.
Read the corresponding section of `references/chart-migration-1x-2x.md` for guidance.

### Resolution protocol

For each flagged area:

1. **Show the original 1.x values** for that section (from the user's input file)
2. **Explain what changed** — one paragraph, plain language, no internal jargon
3. **Show the proposed 2.x equivalent** — the draft output from the script
4. **Flag any manual actions** — things the user must do outside the values file
   (e.g., create a secret, add NetworkPolicy rules)
5. **Ask for confirmation**: "Does this look correct? Adjust anything?"

### Area-specific guidance

**ingress** — Show the structural transformation. If the user had `extraHosts`, confirm the
merged `hosts[]` array is correct. If TLS was enabled, verify the host association. If the
user's ingress has complex rules or path types, flag for manual review.

**args** — Explain the `extraArgs` vs `argsOverride` choice. If the script chose `extraArgs`,
explain that system `--config` flags will be prepended automatically. If the user's args
contained `--config`, the script chose `argsOverride` — explain that this replaces ALL
arguments.

**extraEnvFrom** — Show the merged list. Verify the user recognizes all secret/configmap names.
Note that the format changed from name strings to structured refs.

**authSecret** — Show the `existingSecretRef` object. Ask if the user's secret key is
`backend-secret` or something else. If different, they need to update the `key` field.

**initContainers** — If custom init containers were moved to `extraInitContainers`, ask whether
they should run before (→ `preInitContainers`) or after (→ `extraInitContainers`) system init
containers. Show the dynamic-plugins init container config under `dynamicPlugins.initContainer.*`.

**networkPolicy** — Explain that the old `networkPolicy.*` config is removed. The new chart
deploys default-deny policies. Ask: "Does your RHDH connect to external APIs, custom sidecars,
or cross-namespace services? If so, you'll need to add NetworkPolicy rules after migration."

**intelligentAssistant** — Walk through each sub-area:
- Image string split: show the parsed components, ask if correct
- ConfigMap mapping: show which CMs were classified as stack/profile
- Secret: warn that they must create it independently before upgrading
- Removed fields: list what was dropped and why
- Plugin format: the new chart supports `ref://` as a convenience shorthand for referencing default catalog plugins by name. Existing `oci://` references remain fully supported — no forced migration needed. Optionally suggest simplifying to `ref://` where applicable.

**orchestrator** — Show the restructured fields:
- External DB fields nested under `externalDB.*`
- Image strings split into components
- Job config fields nested under `dbCreationJob.*`
If `initContainerImage` and `createDBJobImage` differed, ask which to use.

### After all areas resolved

Apply the user's confirmed changes to the draft file. The final 2.x values file should
have no remaining `MIGRATION-REVIEW` markers.

## Step 4: Behavioral Change Warnings

Regardless of whether ambiguous areas existed, warn about behavioral changes:

1. **PostgreSQL default version**: If the user's values don't explicitly set
   `postgresql.image.tag`, warn: "The default PostgreSQL image changed from v15 to v18.
   If you have an existing data directory, add `postgresql.image.tag: '<your-current-version>'`
   to avoid data compatibility issues."

2. **HPA maxReplicas default**: If autoscaling is enabled and `maxReplicas` is not explicitly
   set, warn: "The default maxReplicas changed from 100 to 3."

3. **Database env vars**: If the user had `POSTGRESQL_ADMIN_PASSWORD` in `extraEnvVars`,
   note it should be `POSTGRES_PASSWORD` now.

4. **Image digest/tag interaction**: If the user's values set a custom `image.tag` (or any
   `*.image.tag`), warn: "The downstream chart ships images with explicit digests by default.
   When both tag and digest are set, the chart renders `tag@digest`, which can fail to resolve
   at pull time if they don't match (the chart's default digest is merged by Helm). When
   overriding with a tag, either set `digest: ""` to clear the default, or set `digest` to
   the correct digest for your tag."

5. **Air-gapped / disconnected environments**: If `global.imageRegistry` is set, note:
   "`global.imageRegistry` and `global.imagePullSecrets` apply to all chart-managed container
   images (RHDH, PostgreSQL, catalog index, etc.), but do NOT apply to dynamic plugin
   references (`oci://` or `ref://` in `dynamicPlugins.plugins`). Plugin OCI images must be
   mirrored separately and their references updated individually in your dynamic plugins
   configuration."

6. **Schema validation**: Recommend running `helm template` before upgrading:
   ```bash
   helm template <release> redhat-developer/redhat-developer-hub -f new-values.yaml
   ```

## Step 5: Produce Combined Report

If the user provided config files beyond just the Helm values (e.g., app-config.yaml,
dynamic-plugins.yaml), run `workflows/full-report.md` with the **migrated** values file
as input alongside the other config files. This produces the standard upgrade assessment
(plugin analysis, release notes correlation, scoring) combined with the chart migration.

If only the Helm values file was provided, produce a standalone chart migration report:

```
## Chart Migration Report: RHDH {from} → {to}
### Generated: {date}

> **Migration status:** {Complete | Complete with manual actions}
> **Keys migrated:** {N} deterministic + {R} reviewed
> **Removed:** {M} (no 2.x equivalent)
> **Manual actions required:** {count}

---

### Deterministic Migrations Applied

{N} values keys automatically translated to the 2.x structure.
No action needed for these.

### Reviewed and Confirmed

{For each resolved ambiguous area, show what was decided}

### Manual Actions Required

{List any post-migration steps: create secrets, add NetworkPolicy rules, etc.}

### Behavioral Change Warnings

{PostgreSQL version, HPA defaults, env var renames, etc.}

### Pre-Upgrade Validation

Run this command to validate the migrated values before upgrading:

```bash
helm template <release> redhat-developer/redhat-developer-hub -f {output-file}
```

Then upgrade:

```bash
helm upgrade --install <release> redhat-developer/redhat-developer-hub -n <namespace> -f {output-file}
```

### Migrated Values File

The migrated 2.x values file has been written to: `{output-path}`
```

### RHDH Local recommendation

Before the upgrade checklist, check for RHDH Local per `references/rhdh-local.md`:
- If found: "RHDH Local detected — use it to validate your migrated values before deploying."
- If not found: Include the full RHDH Local recommendation.

## Report rules

- Customer-facing language — no internal jargon
- Every change traces to a specific mapping from `references/chart-migration-1x-2x.md`
- No secrets echoed in output — apply `[REDACTED]` per `references/secrets-detection.md`
- Show the exact file path of the migrated values file
- Include `helm template` validation command
