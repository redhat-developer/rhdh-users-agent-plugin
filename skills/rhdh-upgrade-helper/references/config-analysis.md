# Config Analysis: Customer Configuration Parsing

This reference defines how to parse customer configuration files and produce actionable migration findings. Config files can come from `.rhdh-upgrade-helper.yaml`, `--config` flags, `--config-path` directory scan, or the interactive workflow. See `references/rhdh-upgrade-helper-config.md` for input resolution order.

## File Discovery

### RHDH Local auto-detection

When scanning a directory, first check if it is an **rhdh-local** project structure:

```bash
# Check for rhdh-local indicators
ls {config_path}/compose.yaml 2>/dev/null
ls {config_path}/configs/app-config/ 2>/dev/null
ls {config_path}/configs/dynamic-plugins/ 2>/dev/null
ls {config_path}/default.env 2>/dev/null
```

If `compose.yaml` and `configs/` subdirectory both exist, treat this as an **rhdh-local project**:

1. **Detect RHDH version** from `compose.yaml` and `default.env`:
   - Read `RHDH_IMAGE` default from compose.yaml (e.g., `quay.io/rhdh-community/rhdh:1.10` → version `1.10`)
   - Read `CATALOG_INDEX_IMAGE` from `default.env` (e.g., `quay.io/rhdh/plugin-catalog-index:1.10`)
   - Use for `--to` if not provided via CLI. If `.env` overrides the image tag, use that instead.
2. **Auto-discover all config files** by scanning the `configs/` subtree recursively:
   - `configs/app-config/*.yaml` → all app-config files
   - `configs/dynamic-plugins/*.yaml` → all dynamic-plugins files
   - `configs/extra-files/` → any additional config
3. **Read env files**: `default.env` first, then `.env` (overrides)
4. Set `environment.deployment_method` to `local`

This means an rhdh-local user can simply run:

```
/rhdh-upgrade-helper --config-path ./rhdh-local/
```

and the skill discovers everything automatically — version, configs, env vars.

### Standard directory scan

When the directory is NOT an rhdh-local project, scan for these file patterns:

| Pattern | Examples |
|---------|----------|
| `values*.yaml` | `values.yaml`, `values-prod.yaml` |
| `dynamic-plugins*.yaml` | `dynamic-plugins.yaml`, `dynamic-plugins-override.yaml` |
| `app-config*.yaml` | `app-config.yaml`, `app-config-auth.yaml` |
| `compose.yaml`, `docker-compose.yaml` | Compose files (extract RHDH image version) |
| `*.env`, `.env*` | `.env`, `.env.local`, `env.sh` |
| `backstage*.yaml` (with `kind: Backstage`) | `backstage-cr.yaml` |

### When files are provided individually (`--config` or `.rhdh-upgrade-helper.yaml`)

Do NOT rely on filename — auto-detect the type from content.

## File Type Auto-Detection

For every config file (whether discovered by directory scan or provided individually), classify by content:

| Content marker | Detected type | How to parse |
|---|---|---|
| Contains `global.dynamic.plugins` or `upstream.backstage` | **Helm values (1.x)** | Extract nested config — see "Parsing Helm Values" below. If the target release is 2.x, route to `workflows/chart-migration.md` for values restructuring. |
| Contains top-level `dynamicPlugins.plugins` or `dynamicPlugins.includes` (without `global.dynamic` or `upstream`) | **Helm values (2.x)** | Already in 2.x structure. Parse `dynamicPlugins.plugins` directly for plugin analysis. |
| Top-level `plugins:` array with `package:` entries | **Dynamic plugins config** | Parse `plugins:` array directly |
| Top-level `auth:`, `catalog:`, `backend:`, or `proxy:` keys | **App-config** | Parse as root-level Backstage configuration |
| `kind: Backstage` or `apiVersion: rhdh.redhat.com` | **Backstage CR (Operator)** | Extract environment facts — see "Parsing Backstage CR" below |
| Top-level `services:` with an `image:` containing `rhdh` | **Compose file** | Extract RHDH image version — see "Parsing Compose Files" below |
| `KEY=VALUE` pairs (no YAML structure) | **Environment file** | Parse as env vars — see `references/env-vars.md` |

When a file matches multiple markers (e.g., Helm values contain `auth:` under `upstream.backstage.appConfig`), use the most specific match. `global.dynamic.plugins` or `upstream.backstage` → Helm values (1.x) takes precedence.

**1.x vs 2.x Helm values detection:** If a values file contains `upstream.backstage` or `global.dynamic.plugins`, it is 1.x format. If it contains top-level `dynamicPlugins` without the `global.dynamic` or `upstream` wrapper, it is 2.x format. When a 1.x values file is detected and the target release is 2.x, the skill should route through `workflows/chart-migration.md` to migrate the values structure before proceeding with plugin and config analysis.

## Merging Multiple App-Config Files

Backstage merges multiple app-config files in order — later files override earlier ones (deep merge per key). The skill must do the same before analysis:

1. Sort discovered app-config files alphabetically (e.g., `app-config.yaml` before `app-config.local.yaml`)
2. Deep-merge them in order — later files override keys from earlier files
3. Analyze the **merged result** as one config

This prevents:

- False positives from flagging something in `app-config.yaml` that is overridden in `app-config.local.yaml`
- Missed findings from keys that only exist in `app-config.local.yaml`
- Duplicate findings from both files

Report findings against the **source file** where the final value comes from (not the merged result), so the customer knows which file to edit.

## Parsing Compose Files

When a compose file is detected (rhdh-local or standalone), extract:

- `RHDH_IMAGE` default value → parse the tag to determine the RHDH version (e.g., `quay.io/rhdh-community/rhdh:1.10` → `1.10`)
- Use as `rhdh_to` if not provided via CLI args or `.rhdh-upgrade-helper.yaml`
- Set `environment.deployment_method` to `local`

Also check for `CATALOG_INDEX_IMAGE` in compose env or `default.env` for the catalog index version.

## Parsing Backstage CR (Operator deployments)

When a file is detected as a Backstage CR, extract these environment facts:

- Set `environment.deployment_method` to `operator`
- Capture `metadata.name` as the instance name
- Note referenced ConfigMap and Secret names from `spec.application.appConfig.configMaps` and `spec.application.dynamicPluginsConfigMapName`

The actual config content (app-config, dynamic-plugins) must be provided as separate files. The CR tells us it's an Operator deployment and which ConfigMaps are involved, but doesn't contain the plugin/auth configuration itself.

## Parsing Helm Values

Helm values embed RHDH config in nested paths. Extract these sections:

### Dynamic plugins from Helm values

```bash
# The plugins list may be at one of these paths:
# 1. global.dynamic.plugins (array of plugin entries)
# 2. global.dynamic.includes[].dynamic-plugins.yaml (references a separate file)
python3 -c "
import yaml, sys
with open('$CONFIG_PATH/values.yaml') as f:
    v = yaml.safe_load(f)
plugins = v.get('global',{}).get('dynamic',{}).get('plugins',[])
for i, p in enumerate(plugins):
    pkg = p.get('package','')
    disabled = p.get('disabled', False)
    print(f'{i}: package={pkg} disabled={disabled}')
"
```

### App-config from Helm values

```bash
# App config is typically at upstream.backstage.appConfig
python3 -c "
import yaml, sys, json
with open('$CONFIG_PATH/values.yaml') as f:
    v = yaml.safe_load(f)
app_config = v.get('upstream',{}).get('backstage',{}).get('appConfig',{})
print(json.dumps(app_config, indent=2))
"
```

## Parsing Dynamic Plugins Config

For each plugin entry in the `plugins:` array, check:

### 1. Resolve the Target Plugin Artifact

Resolve the customer reference against the target Package entity index. The Package entity's `spec.dynamicArtifact` is the authoritative artifact reference. Do not replace it with an image reference copied from `index.json`.

Use the target support level as an artifact-policy signal, but always use the exact `spec.dynamicArtifact` value:

- **Generally available + local `spec.dynamicArtifact`** → the plugin is intentionally bundled in the target image. Keep and use that local path. Do not substitute `index.json`'s `registryReference`.
- **Generally available + `registry.access.redhat.com` OCI `spec.dynamicArtifact` with a matching active default OCI entry** → the Package entity remains authoritative, but RHDH 1.10 permits the deployment reference to replace its tag or digest with `:{{inherit}}`. Use the parser's `inheritArtifact` value so the tag is picked up from `dynamic-plugins.default.yaml`.
- **Community + OCI `spec.dynamicArtifact`** → use the exact OCI reference from the Package entity, including its registry, tag, and optional plugin path. Do not substitute a `registry.access.redhat.com` image from `index.json`.
- **Any support level with OCI `spec.dynamicArtifact`** → the plugin is OCI-backed for this release; use that exact OCI reference.
- **Any support level with local `spec.dynamicArtifact`** → the target metadata declares the bundled local path. Compare it with the customer's path and preserve the customer's enablement or disablement intent.
- **No matching Package entity** → the artifact is unresolved and requires Critical manual review; do not construct a replacement from `index.json`.

```bash
# Find local-path plugin references with line numbers
grep -n './dynamic-plugins/dist/' "$CONFIG_PATH/dynamic-plugins.yaml" 2>/dev/null
grep -n './dynamic-plugins/dist/' "$CONFIG_PATH/values.yaml" 2>/dev/null
```

**Recommended fix for each configured plugin reference:**

Do not remove or convert an entry based only on the presence of an image record. First compare the customer's reference with the target Package entity's `spec.dynamicArtifact`, then compare its `disabled` value with the target default.

1. **Target `spec.dynamicArtifact` matches the customer reference** → no artifact migration. If the target default preserves the intended state and no custom `pluginConfig` is required, the explicit entry may be removed; otherwise retain it.
2. **Customer local path, target `spec.dynamicArtifact` is OCI** → Critical bundle-to-OCI migration; replace it with the exact target `spec.dynamicArtifact`.
3. **Customer OCI/NPM reference, target `spec.dynamicArtifact` is local** → use the target local path when an artifact change is required; do not use `index.json`'s registry image.
4. **Target default state differs from the customer's `disabled` intent** → preserve the explicit entry or migrate its artifact while retaining the customer's `disabled` value.
5. **Target artifact is unresolved** → keep the finding Critical and require manual validation.

When `inheritArtifact` is present, it is the preferred customer-facing replacement for a GA registry-access OCI artifact. It is an artifact-reference convenience, not a replacement for the Package entity: retain the exact `dynamicArtifact` as the evidence and fallback value. Do not emit `{{inherit}}` for Community/GHCR artifacts, local bundled artifacts, or registry-access artifacts without a matching default OCI package entry.

Only an actual artifact transition or unresolved reference is Critical. A local path that exactly matches a target local `spec.dynamicArtifact` is not a bundle-to-OCI finding.

#### Building the plugin metadata index

Before resolving individual plugins, build a **metadata index** from the complete `catalog-entities/extensions/packages/*.yaml` Package entity list when the shipped image was extracted, then enrich those records with productized image data from `index.json`. If the extractor used the overlay Git fallback, build the same index from the overlay metadata files. This index maps every plugin by multiple keys so any customer reference — local path, OCI reference, NPM package name, or image name — resolves in a single lookup.

**Step 0 — Build the index (run once per session, after resolving product data in `workflows/full-report.md` Step 2):**

Use `$PLUGIN_METADATA` from the catalog parser, or read every metadata file under `$PRODUCT_DATA_DIR/workspaces/*/metadata/*.yaml` when `$PRODUCT_DATA_SOURCE` is `overlay`, and build an in-memory index keyed by:

1. **`spec.dynamicArtifact`** (exact value) — matches customer's `./dynamic-plugins/dist/...` or `oci://...` reference directly
2. **`spec.packageName`** (NPM name, e.g., `@roadiehq/scaffolder-backend-module-http-request`) — matches exact NPM registry references and package entries
3. **decoded dynamic-package names from `index.json`** — matches productized package names when the published NPM scope changed between releases; compare the package basename only after the image/package association is established
4. **metadata filename** (without `.yaml` extension, e.g., `roadiehq-scaffolder-backend-module-http-request`) — matches image names derived from local paths
5. **derived image name from `dynamicArtifact`** — for `oci://` artifacts, the image name between the last `/` and the `:` or `@`

Package entities are the complete package list and provide the authoritative `packageName`, `dynamicArtifact`, derived `artifactType` (`local`, `oci`, or `npm`), `version`, `support`, lifecycle, Backstage compatibility, and configuration examples. `index.json` is enrichment only: use `io.backstage.dynamic-packages` for alias/package association, `workspacePath` for workspace grouping, `imageTag` and `registryReference` for image provenance or digest audit, `support` only as a consistency check when a Package entity is absent, and build fields such as `build-date`, `vcs-ref`, `upstream`, and `midstream` for provenance. Never use `registryReference` to override or replace `spec.dynamicArtifact`.

Each index entry stores the full metadata: `dynamicArtifact`, `packageName`, `version`, `support`, `lifecycle`, `appConfigExamples`, `artifactType`, `defaultDisabled`, `defaultPackageArtifact`, `inheritArtifact` when eligible, `referenceStatus` from the GA/Technology Preview/deprecated/supported-plugin references, and either the catalog record or fallback source file path.

**Why a single-pass index works:** Every catalog-index record or overlay metadata file contains `spec.packageName` — the exact NPM package name (e.g., `@backstage-community/plugin-rbac`, `@roadiehq/scaffolder-backend-module-http-request`). This eliminates the need for filename-based guessing or content grepping across files. The index handles all naming patterns — `rhdh-bsp-*` abbreviations, full names, scoped NPM names — because it indexes by the actual field values, not by filename conventions.

#### Resolving plugins from customer config

For each plugin entry in the customer's config, resolve it against the index:

**Step 1 — Determine the lookup key from the customer's `package:` value:**

| Customer's `package:` format | Lookup key | Index field |
|---|---|---|
| `./dynamic-plugins/dist/backstage-plugin-catalog-backend-module-gitlab-dynamic` | The exact value | `spec.dynamicArtifact` |
| `oci://ghcr.io/.../immobiliarelabs-backstage-plugin-gitlab:bs_1.49.4__7.0.1` | Extract image name: `immobiliarelabs-backstage-plugin-gitlab` | derived image name |
| `https://npm.registry.redhat.com/@redhat/backstage-plugin-orchestrator-backend-dynamic/-/...1.8.9.tgz` | Extract NPM scope+name, then compare with associated decoded dynamic-package names | `spec.packageName` / `dynamicPackageNames` |
| `@backstage-community/plugin-rbac` | The exact value | `spec.packageName` |

**Step 2 — Look up in index and read the result:**

- **If match found** → read `spec.dynamicArtifact`, `spec.version`, `spec.support`, `spec.packageName`, `spec.appConfigExamples`
- **If no match** → the plugin is not available in the target release

**Step 3 — Classify the finding:**

- **If `spec.dynamicArtifact` is `oci://...`** → Use this exact value as the target artifact. If `inheritArtifact` is present for a GA registry-access image, use that `:{{inherit}}` form in the customer replacement so the shipped default supplies the tag. A Community/GHCR artifact always uses the exact Package entity reference; do not replace it with `registryReference`.
- **If `spec.dynamicArtifact` is `./dynamic-plugins/dist/...`** → The plugin is still bundled. If the customer uses the same local path, there is no artifact migration. Compare `disabled` with `defaultDisabled` before recommending removal or retaining the override.
- **If no match found in index** → The plugin is not available in the target release. Flag as **Critical** with "plugin removed from target release" message.

**Step 4 — Produce migration findings:**

For each local-path plugin, create a migration issue with:

- `file`: config file path
- `line`: line number of the `package:` entry
- `severity`: `critical` only for an actual artifact transition or unresolved target reference; no migration issue for an exact target `dynamicArtifact` match
   - `category`: `artifact-source` (use `bundle-to-oci` as a more specific label for local-to-OCI transitions if desired)
- `current`: the `./dynamic-plugins/dist/...` value
- `replacement`: the exact target `spec.dynamicArtifact` when it differs; otherwise no artifact replacement, with a conditional default/`disabled` action when relevant
- `reason`: include both the local artifact-compatibility risk and whether removing the entry would change the customer's enabled/disabled state

### 2. Validate Existing OCI and NPM References

For every `oci://` or NPM registry reference in the customer's config, verify it against the target Package entity:

**Step 1 — Extract the image or package name from the reference:**

```
oci://ghcr.io/redhat-developer/rhdh-plugin-export-overlays/immobiliarelabs-backstage-plugin-gitlab:bs_1.49.4__7.0.1
  → image name: immobiliarelabs-backstage-plugin-gitlab
```

Strip the registry prefix and everything after the `:` tag or `@` digest.

**Step 2 — Look up in the metadata index** (built in Section 1, Step 0) using the derived image name:

**Step 3 — Compare:**

- Check that the plugin still exists in workspace metadata for the target release. If not → flag as **Critical** ("plugin removed").
- Compare the source type of the customer's reference with the source type of target `spec.dynamicArtifact`:
  - local, OCI, or NPM → same source type: continue with version/reference comparison
  - different source type: **Critical** artifact-source migration; use the exact target `spec.dynamicArtifact`
- Compare the customer's OCI tag/digest with the `spec.dynamicArtifact` in metadata:
  - If the tag matches (same `bs_{version}__{plugin_version}`) → valid, no action needed.
  - If the tag is older (different backstage version or plugin version) → flag as **Important** with the updated reference from `spec.dynamicArtifact`.
  - If the customer's reference uses a tag but metadata uses a digest (or vice versa) → informational, both are valid.

**Step 4 — Produce validation findings:**

For OCI references that need updating:

- `file`: config file path
- `line`: line number
- `severity`: `critical` (removed) or `important` (outdated tag)
- `category`: `oci-version-mismatch` for same-source version changes, or `artifact-source` for local/OCI/NPM source changes
- `current`: the customer's OCI reference
- `replacement`: the `spec.dynamicArtifact` from metadata
- `reason`: "Plugin removed from target release" or "OCI reference targets older version; update to {version} for target release compatibility"

### 3. Removed/Renamed Plugins

Check each configured plugin package name against the target release's `default.packages.yaml`. If a package is not listed, it may have been removed or renamed.

### 4. Disabled Plugins Still Referenced

Flag a disabled plugin only when its target `spec.dynamicArtifact` differs from the customer reference or is unresolved. A disabled plugin whose local path exactly matches the target `dynamicArtifact` has no artifact migration finding; preserve its explicit disablement when the target default is enabled.

## Parsing App-Config

### Auth Provider Analysis

Extract auth provider configuration:

```bash
# Find auth provider blocks
grep -n 'auth:' "$CONFIG_PATH/app-config.yaml" 2>/dev/null
grep -n 'providers:' "$CONFIG_PATH/app-config.yaml" 2>/dev/null
grep -n 'microsoft:' "$CONFIG_PATH/app-config.yaml" 2>/dev/null
grep -n 'gitlab:' "$CONFIG_PATH/app-config.yaml" 2>/dev/null
grep -n 'github:' "$CONFIG_PATH/app-config.yaml" 2>/dev/null
grep -n 'oidc:' "$CONFIG_PATH/app-config.yaml" 2>/dev/null
```

Check for deprecated auth resolver names between Backstage versions:

- `userIdMatchingUserEntityAnnotation` — valid but check if the exact resolver name changed
- `signInResolvers` array format — changed in some Backstage versions

### Proxy Configuration

```bash
grep -n 'proxy:' "$CONFIG_PATH/app-config.yaml" 2>/dev/null
grep -n '/api/' "$CONFIG_PATH/app-config.yaml" 2>/dev/null
```

### Database Configuration

```bash
grep -n 'database:' "$CONFIG_PATH/app-config.yaml" 2>/dev/null
grep -n 'postgres' "$CONFIG_PATH/app-config.yaml" 2>/dev/null
grep -n 'connection:' "$CONFIG_PATH/app-config.yaml" 2>/dev/null
```

## Environment Extraction

From the parsed config files, extract concrete environment facts:

| Fact | How to Extract |
|------|---------------|
| Deployment method | `values.yaml` present → Helm. `backstage` CR YAML present → Operator. |
| Auth providers | Keys under `auth.providers` in app-config |
| Database type | `backend.database.client` value (`pg` = Postgres, `better-sqlite3` = local) |
| Database host | `backend.database.connection.host` — if contains `azure` or `rds`, note cloud provider |
| SCM integrations | Keys under `integrations` in app-config (`github`, `gitlab`, `bitbucket`) |
| Proxy endpoints | Count of entries under `proxy.endpoints` |
| Total plugins | Count of entries in `plugins:` array in dynamic-plugins config |
| Enabled plugins | Count where `disabled` is not `true` |
| Catalog locations | Count and types under `catalog.locations` |

## Output Structure

Capture as `$CONFIG_ANALYSIS`:

```json
{
  "config_path": "/path/to/configs",
  "files_found": ["values.yaml", "dynamic-plugins.yaml"],
  "environment": {
    "deployment_method": "helm|operator",
    "auth_providers": ["microsoft", "gitlab"],
    "database_type": "pg",
    "database_host": "my-azure-postgres.postgres.database.azure.com",
    "scm_integrations": ["gitlab"],
    "proxy_endpoint_count": 5,
    "total_plugins": 28,
    "enabled_plugins": 22,
    "catalog_location_count": 12
  },
  "migration_issues": [
    {
      "file": "values.yaml",
      "line": 36,
      "severity": "critical",
      "category": "artifact-source",
      "current": "./dynamic-plugins/dist/roadiehq-scaffolder-backend-module-http-request-dynamic",
      "replacement": "oci://registry.access.redhat.com/rhdh/roadiehq-scaffolder-backend-module-http-request@sha256:2e498...",
      "reason": "Plugin is OCI-only in target release (spec.dynamicArtifact is an oci:// reference)"
    },
    {
      "file": "values.yaml",
      "line": 25,
      "severity": "important",
      "category": "artifact-source",
      "current": "oci://registry.access.redhat.com/rhdh/backstage-community-plugin-argocd@sha256:abc",
      "replacement": "oci://ghcr.io/redhat-developer/rhdh-plugin-export-overlays/backstage-community-plugin-argocd:bs_1.49.4__2.8.0!backstage-community-plugin-argocd",
      "reason": "The target Community Package entity declares this GHCR dynamicArtifact; do not use the index image registryReference as the replacement"
    },
    {
      "file": "values.yaml",
      "line": 63,
      "severity": "important",
      "category": "oci-version-mismatch",
      "current": "oci://ghcr.io/.../immobiliarelabs-backstage-plugin-gitlab:bs_1.45.3__6.0.0",
      "replacement": "oci://ghcr.io/.../immobiliarelabs-backstage-plugin-gitlab:bs_1.49.4__7.0.1",
      "reason": "OCI reference targets older version; update to bs_1.49.4__7.0.1 for target release"
    }
  ],
  "deprecated_config_keys": [
    {
      "file": "app-config.yaml",
      "line": 15,
      "path": "auth.providers.microsoft.signInResolvers",
      "issue": "Resolver name format changed in Backstage 1.48",
      "fix": "Update resolver name to match new format"
    }
  ],
  "plugin_summary": {
    "total": 28,
    "local_path": 3,
    "oci": 22,
    "disabled": 6,
    "needs_migration": 3
  }
}
```

## Severity Rules

| Finding | Severity | Downgrade allowed? |
|---------|----------|--------------------|
| Local path whose target `spec.dynamicArtifact` is OCI or unresolved | **Critical** — plugin may disappear or use an unavailable artifact | No |
| Local path that exactly matches target `spec.dynamicArtifact` | No artifact finding; evaluate only default/`disabled` intent | N/A |
| Plugin package not found in target release's package list | **Critical** — plugin may be removed or renamed | No |
| Deprecated auth resolver name | **Critical** — login will fail after upgrade | No |
| Deprecated config key | **Important** — may cause warnings or unexpected behavior | Yes, to Informational if the key is still functional |
| Disabled plugin whose target default is enabled | **Important** — removing the override would change the customer's intent | Yes |
