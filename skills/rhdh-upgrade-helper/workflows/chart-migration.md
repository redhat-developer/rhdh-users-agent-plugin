# Workflow: Chart migration (1.y to 2.y)

This workflow handles RHDH Helm chart major version upgrades where the values structure
changes. It combines a deterministic migration script with AI-assisted resolution of
ambiguous areas.

<required_reading>
Read these references before proceeding:

- `references/chart-migration-1y-2y.md` — mapping tables and ambiguous area guidance
- `references/secrets-detection.md` — secret scanning patterns
- `references/output-format.md` — report template (for the final combined report)
</required_reading>

## Step 0: Validate prerequisites

1. Confirm this is a major version upgrade: the RHDH major version in `--from` differs
   from `--to` (e.g., 1.10 → 2.1).
2. Note the prerequisite: Kubernetes 1.31+ / OpenShift 4.18+.
3. Identify the Helm values file to migrate. Sources (in priority order):
   - `--config` flag pointing to a values.yaml
   - `.rhdh-upgrade-helper.yaml` config listing a values file
   - `--config-path` directory scan finding a `values*.yaml`
   - Ask the user for the file path

If no values file can be found, inform the user:
"Chart migration requires your 1.y Helm values file. Provide it with `--config ./values.yaml`
or export from a running release: `helm get values <release> -n <ns> -o yaml > old-values.yaml`"

## Step 1: Secrets scan

Before any processing, scan the values file for embedded secrets per
`references/secrets-detection.md`. Same rules as `workflows/full-report.md` Step 0.

## Chart version resolution

All `helm` commands in this workflow — `helm template`, `helm pull`, `helm upgrade` —
need the correct **chart version** and **repo URL**. Resolve these once and reuse
throughout.

**Always check the official repo first.** Only fall back to the upstream repo if the
target version is not yet published at `charts.openshift.io` (e.g., pre-GA builds).

### Official repo (`charts.openshift.io`) — preferred

In the official repo, the RHDH product version aligns with the chart version:
- Product `2.1` → latest chart `2.1.x` (use `--version 2.1` and Helm picks the latest patch)
- Product `2.1.0` → exactly chart `2.1.0`

```bash
helm template <release> redhat-developer-hub --repo https://charts.openshift.io --version <product-version> -f values.yaml
helm pull redhat-developer-hub --repo https://charts.openshift.io --version <product-version> --untar
```

### Upstream repo (`redhat-developer.github.io/rhdh-chart`) — pre-GA fallback

In the upstream repo, product versions do **not** map directly to chart versions.
The chart has its own versioning scheme. To resolve:

- Product `2.1` (no patch) → use the `release-2.1` branch (or `main` if it doesn't exist).
  Read the chart version from `Chart.yaml`:
  ```
  https://github.com/redhat-developer/rhdh-chart/blob/release-2.1/charts/rhdh/Chart.yaml
  ```
- Product `2.1.1` (with patch) → use the `2.1.1` tag in the repo.
  Read the chart version from `Chart.yaml` at that tag:
  ```
  https://github.com/redhat-developer/rhdh-chart/blob/2.1.1/charts/rhdh/Chart.yaml
  ```

Then use the chart version from `Chart.yaml`:
```bash
helm template <release> redhat-developer-hub --repo https://redhat-developer.github.io/rhdh-chart --version <chart-version> -f values.yaml
helm pull redhat-developer-hub --repo https://redhat-developer.github.io/rhdh-chart --version <chart-version> --untar
```

### What you can inspect after pulling

After `helm pull --untar`, inspect:
- `redhat-developer-hub/templates/_helpers.tpl` — internal template names
- `redhat-developer-hub/values.yaml` — chart defaults
- `redhat-developer-hub/Chart.yaml` — version and appVersion

## Step 2: Run deterministic migration

The migration script **never modifies the original values file**. It reads the
1.y file and writes a separate draft 2.y file for the customer to inspect and
validate before using it in an upgrade.

Execute the migration script on the user's values file(s). If the customer uses
multiple values files (e.g., base + environment overrides), pass them all — each
is migrated independently and the output preserves the file separation:

```bash
SKILL_DIR="$(dirname "$(dirname "$0")")"  # or the installed skill directory

# Single file
python3 "$SKILL_DIR/scripts/migrate-chart-values.py" "$VALUES_FILE" \
  -o /tmp/rhdh-2y-values-draft.yaml \
  --report /tmp/rhdh-migration-report.json

# Multiple files — -o must be a directory
python3 "$SKILL_DIR/scripts/migrate-chart-values.py" $VALUES_FILES \
  --to "$TARGET_VERSION" \
  -o /tmp/rhdh-2y-values-draft/ \
  --report /tmp/rhdh-migration-report.json

MIGRATION_EXIT=$?
```

Read the outputs:
- Single file: `/tmp/rhdh-2y-values-draft.yaml` — the draft 2.y values with MIGRATION-REVIEW markers
- Multiple files: `/tmp/rhdh-2y-values-draft/<name>-<version>.yaml` — one draft per input file (e.g., `base-2.1.yaml`)
- `/tmp/rhdh-migration-report.json` — structured report of all transformations (combined across files when multiple)

Present a summary to the user:

```
## Chart values migration: RHDH {from} → {to}

**Deterministic mappings applied:** {N} keys migrated automatically
**Removed values:** {M} keys with no 2.y equivalent
**Areas requiring review:** {R} (listed below)
**Unknown upstream keys:** {U} carried over with warnings
```

If `MIGRATION_EXIT == 0` (no review needed), skip to Step 4.

## Step 3: AI-assisted resolution of ambiguous areas

For each review item in the migration report, walk the user through the resolution.
Read the corresponding section of `references/chart-migration-1y-2y.md` for guidance.

### Resolution protocol

For each flagged area:

1. **Show the original 1.y values** for that section (from the user's input file)
2. **Explain what changed** — one paragraph, plain language, no internal jargon
3. **Show the proposed 2.y equivalent** — the draft output from the script
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

Apply the user's confirmed changes to the draft file. The final 2.y values file should
have no remaining `MIGRATION-REVIEW` markers.

## Step 4: Behavioral change warnings

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

6. **Schema validation**: Recommend running `helm template` before upgrading.
   If multiple values files were migrated, pass them in the same order the customer
   used with the 1.y chart (Helm merges values files in order — last wins).

   Use the chart version resolved in the **Chart version resolution** section above:
   ```bash
   # Single file
   helm template <release> redhat-developer-hub --repo <repo-url> --version <chart-version> -f new-values.yaml
   # Multiple files — same order as the original 1.y install
   helm template <release> redhat-developer-hub --repo <repo-url> --version <chart-version> -f base-2.1.yaml -f prod-2.1.yaml
   ```

## Step 5: Produce combined report

If the user provided config files beyond just the Helm values (e.g., app-config.yaml,
dynamic-plugins.yaml), run `workflows/full-report.md` with the **migrated** values file
as input alongside the other config files. This produces the standard upgrade assessment
(plugin analysis, release notes correlation, scoring) combined with the chart migration.

If only the Helm values file was provided, produce a standalone chart migration report:

```
## Chart migration report: RHDH {from} → {to}
### Generated: {date}

> **Migration status:** {Complete | Complete with manual actions}
> **Keys migrated:** {N} deterministic + {R} reviewed
> **Removed:** {M} (no 2.y equivalent)
> **Manual actions required:** {count}

---

### Deterministic migrations applied

{N} values keys automatically translated to the 2.y structure.
No action needed for these.

### Reviewed and confirmed

{For each resolved ambiguous area, show what was decided}

### Manual actions required

{List any post-migration steps: create secrets, add NetworkPolicy rules, etc.}

### Behavioral change warnings

{PostgreSQL version, HPA defaults, env var renames, etc.}

### Pre-upgrade validation

Validate the migrated values before upgrading. If multiple values files were
migrated, pass them in the same order as the original 1.y install.

Use the chart version and repo URL from the **Chart version resolution** section:

```bash
helm template <release> redhat-developer-hub --repo <repo-url> --version {chart-version} -f {output-file(s)}
```

Then upgrade:

```bash
helm upgrade --install <release> redhat-developer-hub --repo <repo-url> --version {chart-version} -n <namespace> -f {output-file(s)}
```

### Migrated values file

The migrated 2.y values file has been written to: `{output-path}`
```

### RHDH Local

Do **not** recommend RHDH Local for validating Helm values files. RHDH Local uses
`podman compose` with app-config files — it cannot process Helm values or resolve
Go template expressions (e.g., `{{ include "rhdh.hostname" . }}`). The correct
validation path for chart migrations is `helm template` (shown above).

RHDH Local is still relevant when the customer also has app-config files to
validate — in that case, defer to `workflows/full-report.md` which includes the
RHDH Local recommendation for the app-config portion.

## Report rules

- Customer-facing language — no internal jargon
- Every change traces to a specific mapping from `references/chart-migration-1y-2y.md`
- No secrets echoed in output — apply `[REDACTED]` per `references/secrets-detection.md`
- Show the exact file path of the migrated values file
- Include `helm template` validation command
