# Workflow: Config-Driven Upgrade Assessment

<required_reading>
Read these references before proceeding:

- `references/secrets-detection.md` — secret scanning patterns (read FIRST)
- `references/rhdh-upgrade-helper-config.md` — .rhdh-upgrade-helper.yaml format and resolution order
- `references/config-scoring.md` — readiness scoring model
- `references/output-format.md` — customer-facing report template
- `references/rhdh-local.md` — RHDH Local detection and recommendation
- `references/env-vars.md` — known RHDH environment variables
- `references/config-analysis.md` — how to parse config files
- `references/rhdh-architecture.md` — what actually breaks vs. false positives
</required_reading>

## Step 0: Secrets Scan (MUST run before any analysis)

Before processing any config files, scan ALL resolved config files for embedded secrets following `references/secrets-detection.md`.

1. Read each resolved config file
2. Apply the detection patterns from `references/secrets-detection.md`
3. If secrets are detected:
   - Print a warning listing each file and line number
   - Ask the user: continue (secrets will be `[REDACTED]` in output) or stop to redact first
   - If they choose to stop, halt the workflow
4. If no secrets detected, proceed silently

Template variable references (`${VAR}`, `{{ .Values.x }}`) are NOT secrets — skip them.

## Step 1: Resolve Config Files and Parse Input

Resolve config files following the order defined in `references/rhdh-upgrade-helper-config.md`. Each source **extends** the file list (not replaces):

### 1a: Check for `.rhdh-upgrade-helper.yaml`

Look for `.rhdh-upgrade-helper.yaml` in the current working directory first, then in the `--config-path` directory if provided:

```bash
# Check cwd
Read .rhdh-upgrade-helper.yaml  # if exists

# Check --config-path directory
Read {config_path}/.rhdh-upgrade-helper.yaml  # if exists and cwd check failed
```

If found, extract:

- `configs` list → add each path to the resolved file list (resolve relative paths from the `.rhdh-upgrade-helper.yaml` location)
- `from` → use as `rhdh_from_release` if `--from` not in CLI args
- `release` → use as `rhdh_to` if `--to` not in CLI args

### 1b: Process CLI arguments

Extract from $ARGUMENTS:

- `rhdh_to`: from `--to X.Y` (overrides `.rhdh-upgrade-helper.yaml`)
- `rhdh_from_release`: from `--from X.Y` (overrides `.rhdh-upgrade-helper.yaml`), defaults to release immediately before `--to`
- `--config /path/to/file`: add each file to the resolved file list (may appear multiple times)
- `--config-path /dir`: if provided and no `.rhdh-upgrade-helper.yaml` found, scan directory for config files per `references/config-analysis.md` File Discovery

### 1c: Confirm resolved files

Before proceeding, show the user what was found and confirm:

1. List all resolved config files with their auto-detected type (Helm values, app-config, dynamic-plugins, Backstage CR)
2. Ask: **"Are there additional config files in other locations? (e.g., a separate app-config or dynamic-plugins ConfigMap)"**
3. If yes, collect more paths until the user says "done"
4. If using `.rhdh-upgrade-helper.yaml`, suggest updating it with the additional paths for future runs

Skip this confirmation only when the files came from a `.rhdh-upgrade-helper.yaml` (the user already curated the list).

### 1d: Validate

- `--to` is required (from CLI or `.rhdh-upgrade-helper.yaml`). If missing, prompt: "What RHDH version are you upgrading to? (e.g., --to 1.10)"
- If config files were resolved from any source, proceed with config-driven analysis
- If `$ENVIRONMENT_PROFILE` was passed from `workflows/interactive.md`, use that instead of config files
- If no config files and no environment profile, route to `workflows/interactive.md`

## Step 2: Resolve Shipped Product Data

Use the skill-local extractor to obtain the target release's shipped product data. It tries extraction in this order:

1. `oc image extract` (works without a local container runtime)
2. `podman`
3. `docker`
4. a shallow Git clone of the target `rhdh-plugin-export-overlays` branch

The catalog-index image is the authoritative source because it is the productized artifact and includes the plugin metadata and product documentation shipped for the release. The Git clone is a reduced-fidelity fallback for environments without an image tool or registry access. Always record which source was used in `$PRODUCT_DATA_SOURCE` and `$PRODUCT_DATA_FIDELITY`.

```bash
# SKILL_DIR is the installed rhdh-upgrade-helper directory.
PRODUCT_DATA_DIR=$(bash "$SKILL_DIR/scripts/extract-catalog-index.sh" "{rhdh_to}")
PRODUCT_DATA_ROOT=$(dirname "$PRODUCT_DATA_DIR")
PRODUCT_DATA_INFO=$(python3 "$SKILL_DIR/scripts/parse-catalog-index.py" \
  --data-root "$PRODUCT_DATA_ROOT" source "{rhdh_to}" --json)
PRODUCT_DATA_SOURCE=$(printf '%s\n' "$PRODUCT_DATA_INFO" | python3 -c \
  'import json, sys; print(json.load(sys.stdin)["source"])')
PRODUCT_DATA_FIDELITY=$(printf '%s\n' "$PRODUCT_DATA_INFO" | python3 -c \
  'import json, sys; print(json.load(sys.stdin)["fidelity"])')
RELEASE_VERSIONS=$(python3 "$SKILL_DIR/scripts/parse-catalog-index.py" \
  --data-root "$PRODUCT_DATA_ROOT" versions "{rhdh_to}" --json)
```

If extraction fails completely, report the product-data gap and do not silently make plugin-support or OCI-migration claims. The source (FROM) release does not need product-data extraction — its Backstage/Node versions come from the bundled release notes (`references/release-notes/{from}.md`).

Read version info:

```bash
# Target release (TO) — from the extracted catalog data:
echo "$RELEASE_VERSIONS"

# Source release (FROM) — from bundled release notes:
# e.g., references/release-notes/1.8.md says "upstream Backstage 1.42.5"
```

**Major version handling (e.g., 1.x → 2.x):**

- If the major version differs between FROM and TO, flag this as a **major version upgrade** in the report header
- Major version upgrades may introduce fundamental architecture changes (e.g., frontend system migration, backend system migration) — surface these prominently
- If no branch exists for the target version yet (e.g., `2.0` before release), inform the user: "RHDH {version} has not been released yet. The overlay repo does not have a branch for this version. Try a released version."

Extract `backstage` and `node` versions from both. Compute:

- `backstage_version_jump`: minor version difference
- `node_version_jump`: major version difference
- `is_major_upgrade`: true if the RHDH major version differs

Capture as `$RELEASE_CONTEXT`.

## Step 3: Analyze Customer Environment (parallel with Step 4)

### If `--config-path` provided

Follow `references/config-analysis.md` exactly. This produces `$CONFIG_ANALYSIS` with:

- `environment`: deployment method, auth providers, database, SCM, plugin counts
- `migration_issues`: array of `{file, line, severity, category, current, replacement, reason}`
- `deprecated_config_keys`: array of `{file, line, path, issue, fix}`
- `plugin_summary`: total, local_path, oci, disabled, needs_migration

### Environment variables (if `.env` files found)

Also scan `--config-path` for `.env`, `.env.local`, or `env.sh` files. If found, parse `KEY=VALUE` pairs and cross-reference with known RHDH environment variables per `references/env-vars.md`. Flag:

- Env vars deprecated or renamed between the FROM and TO releases
- `APP_CONFIG_*` overrides that conflict with the target version's defaults
- Apply secrets detection (Step 0) to `.env` file values before processing

### If `$ENVIRONMENT_PROFILE` provided (from interactive intake)

Use the profile directly. No config parsing needed. Migration issues will be detected at feature level rather than line level.

Map `features` to workspace list using the feature-to-workspace mapping in `references/intake-questions.md`.

## Step 4: Gather Product Context (parallel with Step 3)

Gather release metadata and breaking changes from `$PRODUCT_DATA_DIR`. Source release context comes from bundled release notes.

### 4a: Default packages for target release

Read the defaults summary through the parser. When the catalog image is available, its `dynamic-plugins.default.yaml` is the shipped product default; the overlay fallback uses `default.packages.yaml` when present.

```bash
DEFAULT_PACKAGES=$(python3 "$SKILL_DIR/scripts/parse-catalog-index.py" \
  --data-root "$PRODUCT_DATA_ROOT" defaults "{rhdh_to}" --json)
```

Use this to check which plugins in the customer's config exist in the target release and at what support level. If the source is the overlay fallback, label conclusions based on this data as fallback evidence.

### 4b: Per-plugin metadata diff

Build the plugin metadata input once through the parser:

```bash
PLUGIN_METADATA=$(python3 "$SKILL_DIR/scripts/parse-catalog-index.py" \
  --data-root "$PRODUCT_DATA_ROOT" plugins "{rhdh_to}" --json)
```

For catalog-index data, the Package entity is authoritative for `spec.packageName`, `spec.dynamicArtifact`, derived artifact type (`local`, `oci`, or `npm`), `spec.version`, `spec.support`, `spec.backstage.supportedVersions`, lifecycle, and configuration examples. `index.json` is enrichment only: use its dynamic-package annotation for association, workspace path for grouping, image tag and registry reference for provenance/digest audit, its support value only as a consistency check when a Package entity is absent, and build fields for provenance. Never use `index.json`'s `registryReference` as the plugin replacement when the Package entity has a `dynamicArtifact`. For GA registry-access OCI packages, use the parser's `inheritArtifact` when a matching active default OCI entry exists; for Community packages, retain the exact Package entity OCI reference. The `referenceStatus` field records evidence from the GA, Technology Preview, deprecated, and supported-plugin reference files.

### 4c: Release notes

For every release in the FROM→TO range (excluding FROM — the customer is already on it), load the release notes:

```
For --from 1.8 --to 1.10, load 1.9.md and 1.10.md
```

**For each version in the range:**

1. **Check if the file exists:** `references/release-notes/{version}.md`
2. **If it exists:** Read it and continue.
3. **If it does NOT exist:** Auto-fetch and convert:

```bash
# Fetch raw release notes using lynx
lynx -dump -nolist \
  "https://docs.redhat.com/en/documentation/red_hat_developer_hub/{version}/html-single/red_hat_developer_hub_release_notes/index" \
  > /tmp/rhdh-{version}-raw.txt
```

Then convert the raw text to a structured markdown file matching the format of existing files (e.g., `references/release-notes/1.10.md`). Strip navigation boilerplate (header links, sidebar, legal notice) and organize into these sections:

- New features and enhancements
- Technology Preview features
- Deprecated features
- Removed features (breaking changes)
- Known issues
- Fixed issues (upgrade-relevant only)

Save the result to `references/release-notes/{version}.md` so future runs skip the fetch.

4. **If lynx is not available or the fetch fails:** Note the gap in the report: "Release notes for RHDH {version} could not be fetched automatically. Install lynx (`brew install lynx` / `dnf install lynx` / `apt install lynx`) or manually add the file per `references/release-notes/README.md`. Check <https://docs.redhat.com/en/documentation/red_hat_developer_hub/{version}> for the official release notes."

### 4d: Build plugin metadata index and resolve all plugin references

Follow `references/config-analysis.md` Sections 1 and 2. This step covers ALL plugins in the customer's config — local-path, OCI, and NPM references.

**Step 4d-i: Build the metadata index** (run once, using `$PLUGIN_METADATA` from Step 4b):

Use the complete Package entity records under `catalog-entities/extensions/packages/` as the authoritative package list and artifact map, enriched with matching `index.json` image records and `extend_dynamic-plugins-reference` status records. Key records by exact `spec.dynamicArtifact`, `spec.packageName`, decoded dynamic-package names, metadata filename, and derived OCI image name. When `$PRODUCT_DATA_SOURCE` is `overlay`, build the same index by reading the fallback workspace metadata files. See `references/config-analysis.md` Section 1, Step 0 for the full index schema.

**Step 4d-ii: Resolve each plugin** against the index using the lookup key appropriate to the customer's `package:` format (local path, OCI reference, NPM URL, or NPM package name). See `references/config-analysis.md` Section 1, Steps 1-3 for key derivation rules.

**For each `./dynamic-plugins/dist/` reference** (Section 1):
1. Look up by exact `dynamicArtifact` value in the index
2. Read `spec.dynamicArtifact` from the matched entry:
   - `oci://...` → use this exact target artifact; **Critical** if the customer has a different artifact source
   - `./dynamic-plugins/dist/...` → keep the target local path; no bundle-to-OCI finding when it matches the customer reference
   - No match found → **Critical**: target artifact unresolved
3. **Do NOT construct OCI references.** Only use `spec.dynamicArtifact` from metadata.

**For each `oci://` reference** (Section 2):
1. Extract image name, look up in the index by derived image name
2. Compare the customer's tag/digest with `spec.dynamicArtifact` in metadata:
   - Tag matches → valid, no action
   - Target `dynamicArtifact` is a different OCI reference → provide that exact reference; do not use `registryReference` as a substitute
   - Target `dynamicArtifact` is local → use the target local path if an artifact change is required
   - No match found → **Critical**: target artifact unresolved

**For each NPM registry URL or package name:**
1. Extract the NPM scope+name (e.g., `@redhat/backstage-plugin-orchestrator-backend-dynamic`)
2. Look up by exact `spec.packageName`; if the published scope changed, use the associated `dynamicPackageNames` basename as the fallback association key
3. If found, compare the customer's pinned version with `spec.version` and the customer's source type with `artifactType`; use the exact target `dynamicArtifact` for any source transition

Capture as `$PLUGIN_METADATA` — merged into `$CONFIG_ANALYSIS.migration_issues` in Step 5.

Capture all gathered data as `$PRODUCT_CONTEXT`.

## Step 4.5: Query Known Bug Data

Search two sources for known bugs that affect the customer's specific plugins and target version.

### 4.5a: Per-plugin Jira search (RHDHBUGS)

For each plugin in the customer's config (both local-path and OCI), search the RHDHBUGS Jira project for open bugs mentioning that plugin in the target release:

```
For each plugin image name (e.g., "immobiliarelabs-backstage-plugin-gitlab"):
  searchJiraIssuesUsingJql(
    cloudId: "redhat.atlassian.net",
    jql: 'project = RHDHBUGS AND status != Done AND text ~ "{plugin-image-name}" ORDER BY priority DESC',
    maxResults: 5,
    fields: ["summary", "status", "priority", "description"]
  )
```

For each result:

- Read the summary and description to determine if it affects the customer's plugin version
- Extract: ticket key, summary, status, priority, workaround (if mentioned in description)
- Present in the report as a known issue with customer-friendly language
- **Do NOT expose the Jira ticket URL or internal references** — describe the issue in plain terms

If the Jira MCP is not configured or the search fails, skip silently and rely on GitHub Issues + release notes.

### 4.5b: GitHub Issues search (public)

Search GitHub Issues on `redhat-developer/rhdh` for known upgrade difficulties:

```bash
# Search for upgrade-related bugs mentioning the target version
gh search issues --repo redhat-developer/rhdh "{rhdh_to} upgrade" --label "kind/bug" --state all --limit 15 --json number,title,state,url 2>/dev/null

# Search for migration/breaking change issues
gh search issues --repo redhat-developer/rhdh "{rhdh_to} breaking" --state all --limit 10 --json number,title,state,url 2>/dev/null

# If upgrading across multiple versions, also search intermediate versions
gh search issues --repo redhat-developer/rhdh "{rhdh_from_release} upgrade migration" --state all --limit 10 --json number,title,state,url 2>/dev/null
```

Filter results to issues relevant to the customer's plugins and upgrade scenario.

### 4.5c: Combine and deduplicate

Merge results from Jira and GitHub. Deduplicate by issue title/description similarity. Capture as `$KNOWN_BUGS` — array of `{source, key, summary, status, priority, workaround, affects_plugin}`.

Bug data is supplementary — if both searches return nothing, proceed without it.

## Step 5: Config-Impact Correlation

For each breaking change and deprecation from `$PRODUCT_CONTEXT`:

### 5a: Check if it affects the customer

Cross-reference with the customer's environment:

1. **Plugin-level check:** Does the breaking change mention a `@backstage/*` or `@red-hat-developer-hub/*` package? Is that package in the customer's configured plugins?
2. **Feature-level check:** Does the change affect a feature area (auth, catalog, scaffolder, etc.) that the customer uses?
3. **Config-level check:** Does the change involve a config key that exists in the customer's `app-config.yaml`?

If yes → classify as **"Affects You"** with specific impact description.
If no → classify as **"Does NOT Affect You"** with reason why.

### 5b: Merge with config analysis findings

If `$CONFIG_ANALYSIS` was produced (config-path mode), merge `migration_issues` and `deprecated_config_keys` with the product-context breaking changes. Deduplicate — a finding may appear in both sources.

### 5c: Classify severity

Each finding gets a severity:

- **Critical:** Runtime failure if not fixed before upgrade (removed plugin, broken auth, missing OCI reference)
- **Important:** Degraded experience if not fixed soon after upgrade (deprecated API, changed default, version mismatch)
- **Informational:** Awareness only (new feature available, minor deprecation with no immediate impact)

## Step 6: Compute Readiness Score

Follow `references/config-scoring.md` exactly:

1. Compute base score (100 minus deductions from config findings)
2. Apply amplifiers (plugin removals, auth breaks, version jumps)
3. Apply mitigators (single-version upgrade, all plugins exist, no artifact-source migration)
4. Clamp to 0-100
5. Map to readiness label

Every deduction must trace to a specific finding from Steps 3-5.

## Step 7: Compile Report

Follow `references/output-format.md` to produce the customer-facing report:

1. **Header:** Release range, readiness score, config change count, effort estimate
2. **Critical section:** Migration steps that MUST be done before upgrading
3. **Important section:** Items to address after upgrading
4. **Informational section:** Nice-to-know items
5. **Does NOT Affect You:** Breaking changes with no environment overlap
6. **Known Community-Reported Issues:** Relevant bugs from `$PUBLIC_BUGS` (GitHub Issues)
7. **What Changed:** Release summary (new features, plugin version table)
8. **Environment Summary:** Table of detected/reported environment facts
9. **Readiness Score Breakdown:** Full transparent scoring
10. **Pre-Upgrade Testing with RHDH Local:** Recommendation per `references/rhdh-local.md`
11. **Upgrade Checklist:** Actionable pre/during/post steps

### RHDH Local recommendation

Before the upgrade checklist, check for RHDH Local per `references/rhdh-local.md`:

```bash
# Check if rhdh-local exists in the working directory or parent
find . -maxdepth 3 -name 'rhdh-local' -type d 2>/dev/null
find . -maxdepth 3 -name 'podman-compose.yaml' -exec grep -l 'rhdh' {} \; 2>/dev/null
```

- If found: "RHDH Local detected at {path} — use it to validate your updated configuration before deploying to your cluster."
- If NOT found: Include the full RHDH Local recommendation block from `references/rhdh-local.md`.

### Report rules

- Config-sourced findings: include `file:line`, current value, replacement value
- Intake-sourced findings: include "Config area:" label, general action without line numbers
- Every critical/important finding must have a concrete action, not generic advice
- "Does NOT Affect You" section always present, even if empty
- No internal jargon (no RHDHSUPP, no ticket history, no correlation rules)
- Detected secret values replaced with `[REDACTED]` — never echo secrets in output
