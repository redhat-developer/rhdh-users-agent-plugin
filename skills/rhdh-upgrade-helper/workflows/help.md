# Workflow: Help

Explain the rhdh-upgrade-helper skill to the user. No data sources needed.

## Response

**rhdh-upgrade-helper** analyzes your RHDH configuration against a target release and produces a personalized migration plan — showing exactly what affects your setup and what doesn't.

### What it does

1. **Scans for secrets** — checks config files for embedded API keys, passwords, and tokens before processing
2. **Analyzes your environment** — reads your config files or asks about your setup to understand your plugins, auth providers, SCM, and features
3. **Resolves OCI references** — looks up each plugin in your config against the shipped catalog-index metadata to determine if local-path references need OCI migration, with overlay Git fallback
4. **Validates existing OCI plugins** — checks that your `oci://` references are still valid and up-to-date for the target release
5. **Checks release notes** — reads bundled release notes (1.4–1.10) for breaking changes, deprecated features, removed features, and known issues
6. **Searches for known bugs** — queries RHDHBUGS Jira per-plugin for open bugs affecting your specific plugin versions, plus GitHub Issues for community-reported upgrade issues
7. **Filters what affects YOU** — classifies every breaking change as "Affects You" or "Does NOT Affect You" based on your actual configuration
8. **Generates a migration plan** — prioritized by severity (Critical → fix before upgrade, Important → fix after, Informational → nice to know)
9. **Computes a Readiness Score** — 0-100 score with transparent breakdown showing every deduction
10. **Recommends RHDH Local** — suggests testing your updated configuration locally before deploying to your cluster

### How to invoke

**With a config file (recommended for repeat use):**
Create a `.rhdh-upgrade-helper.yaml` in your working directory:

```yaml
from: "1.8"
to: "1.10"
configs:
  - ./values.yaml
  - ./app-config-custom.yaml
  - ./dynamic-plugins-override.yaml
```

Then run:

```
/rhdh-upgrade-helper
```

The skill reads file paths and release versions from this file. No flags needed.

**With individual files:**

```
/rhdh-upgrade-helper --to 1.10 --config ./values.yaml --config ./app-config.yaml
```

`--config` can be specified multiple times. File type is auto-detected from content.

**With a config directory:**

```
/rhdh-upgrade-helper --to 1.10 --config-path ./my-configs/
```

Scans the directory for known file patterns (`values*.yaml`, `app-config*.yaml`, `dynamic-plugins*.yaml`, `.env`).

**With an rhdh-local project:**

```
/rhdh-upgrade-helper --to 1.10 --config-path ./rhdh-local/
```

Auto-detects the rhdh-local project structure, discovers all configs in `configs/app-config/` and `configs/dynamic-plugins/`, reads the current version from `compose.yaml` / `.env`, and merges multiple app-config files automatically.

**Interactive (no config files):**

```
/rhdh-upgrade-helper --to 1.10
```

Asks your current version, deployment method, then asks for config file paths. If you don't have files, falls back to manual questions about auth, SCM, and features.

**Skip-release upgrade:**

```
/rhdh-upgrade-helper --to 1.10 --from 1.8
```

Surfaces all breaking changes across skipped releases (1.9 and 1.10 in this example).

### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `--to X.Y` | Yes | Target RHDH version to upgrade TO |
| `--from X.Y` | No | Source RHDH version upgrading FROM. Defaults to the release immediately before `--to` |
| `--config /path/to/file` | No | Individual config file path. Repeatable |
| `--config-path /dir` | No | Directory to scan for config files |

All arguments can also be set in `.rhdh-upgrade-helper.yaml` — CLI args override the config file.

### What config files to provide

The skill accepts any combination of these files. File type is auto-detected from content, not filename:

| File type | Content markers | What it provides |
|-----------|----------------|------------------|
| **Helm values** | `global.dynamic.plugins`, `upstream.backstage` | Plugins, auth, SCM, catalog providers (all-in-one) |
| **App-config** | Root-level `auth:`, `catalog:`, `backend:`, `proxy:` | Auth providers, catalog providers, integrations |
| **Dynamic plugins config** | Top-level `plugins:` array with `package:` entries | Plugin list, OCI references, pluginConfig |
| **Backstage CR** | `kind: Backstage`, `apiVersion: rhdh.redhat.com` | Deployment method (Operator), referenced ConfigMaps |
| **Compose file** | `services:` with `image:` containing `rhdh` | RHDH version (auto-detected from image tag) |
| **Environment file** | `KEY=VALUE` pairs | Env var overrides, proxy settings, NFS config |

For **Helm deployments**, `values.yaml` is usually sufficient — it contains plugins, auth, and app-config embedded. If you have separate `app-config` or `dynamic-plugins` ConfigMaps, provide those too.

For **Operator deployments**, provide the Backstage CR plus the `app-config` and `dynamic-plugins` ConfigMap contents as separate files.

For **rhdh-local**, just point `--config-path` at the rhdh-local directory — everything is discovered automatically.

### What the report includes

1. **Critical findings** — must fix before upgrading (OCI-only plugins, removed plugins, hard breaks)
2. **Important findings** — address before or soon after upgrading (local-path → OCI migration, outdated OCI tags)
3. **Informational** — awareness items, new features available
4. **Does NOT Affect You** — breaking changes with no overlap to your config (reduces upgrade anxiety)
5. **Known Issues Affecting Your Plugins** — open bugs from RHDHBUGS Jira matching your specific plugin versions, with workarounds
6. **Plugin version table** — every plugin in your config with its version, artifact type, and support level from workspace metadata
7. **Environment summary** — what was detected from your config files
8. **Readiness Score breakdown** — every deduction traced to a specific finding
9. **Pre-upgrade testing with RHDH Local** — recommendation and setup instructions
10. **Upgrade checklist** — actionable pre/during/post steps

### Security

- All input files are scanned for embedded secrets before processing
- Template variable references (`${MY_SECRET}`, `{{ .Values.x }}`) are safe — only literal values are flagged
- If secrets are detected, you're warned and asked to continue or redact first
- Detected secrets are replaced with `[REDACTED]` in all report output
- The skill does not modify, store, or transmit your configuration files

### What it does NOT do

- Does not modify your files — read-only analysis
- Does not predict issues from ticket history
- Does not verify runtime behavior — test with RHDH Local for that
- Does not construct OCI references that don't exist in workspace metadata — only recommends what's verified

### Prerequisites

| Dependency | Required | Purpose | If unavailable |
|------------|----------|---------|----------------|
| `oc`, `podman`, or `docker` | Recommended | Extracts the shipped catalog-index image, including productized metadata and documentation (`oc image extract` does not require a local container runtime) | Falls back to the next available tool, then Git |
| `git` | Fallback | Shallow clone of the overlay repo for reduced-fidelity plugin metadata | Product context is limited to overlay files; report labels it as fallback evidence |
| `gh` CLI (authenticated) | Recommended | GitHub Issues search | Bug search skipped if unavailable |
| Atlassian MCP (Jira) | Optional | Per-plugin bug search against RHDHBUGS | Skipped silently — report uses release notes + GitHub Issues only |
| `lynx` | Optional | Auto-fetch missing release notes | Notes the gap with a link to official docs |

The skill degrades gracefully — the catalog-index image is preferred, but the core analysis can continue with the overlay Git fallback. If neither an image tool nor Git is available, plugin-support and OCI-migration conclusions are reported as unavailable rather than inferred.

### Bundled release notes

Includes RHDH 1.4 through 1.10. Missing versions auto-fetched via `lynx` if available.

### Support

Report issues: <https://github.com/redhat-developer/rhdh-users-agent-plugin/issues>
