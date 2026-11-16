# .rhdh-upgrade-helper.yaml Config File

A config file that pre-sets file paths and release versions so you don't re-type flags on every run.

## Format

```yaml
from: "1.8"
to: "1.10"
configs:
  - ./values.yaml
  - /path/to/app-config-custom.yaml
  - /path/to/dynamic-plugins-override.yaml
  - ./backstage-cr.yaml
```

- `from` and `release` (or `to`) are optional — CLI args (`--from`, `--to`) take precedence
- `configs` is a list of file paths, relative to the `.rhdh-upgrade-helper.yaml` file location
- File type is auto-detected from content, not filename — see "File Type Auto-Detection" below

## Discovery Order

The skill resolves config files in this order. Later sources **extend** earlier ones (not replace):

1. **`.rhdh-upgrade-helper.yaml`** — check current working directory first, then `--config-path` directory
2. **`--config` flags** — individual file paths from CLI args (extend the list from step 1)
3. **`--config-path` directory scan** — scan directory for known file patterns (existing behavior)
4. **Interactive fallback** — if no config files found, ask the user for file paths

## File Type Auto-Detection

Each config file is classified by its content, not its filename:

| Content marker | Detected type |
|---|---|
| `global.dynamic.plugins` or `upstream.backstage` | Helm values |
| Top-level `plugins:` array with `package:` entries | Dynamic plugins config |
| `auth:`, `catalog:`, `backend:`, `proxy:` at root level | App-config |
| `kind: Backstage` or `apiVersion: rhdh.redhat.com` | Backstage CR (Operator) |

This means a file named `my-custom-stuff.yaml` is correctly identified as Helm values if it contains `global.dynamic.plugins`.

### Backstage CR handling

Backstage CR files are parsed for environment facts only:

- Deployment method is set to `operator`
- `metadata.name` is captured
- Referenced ConfigMap names are noted (but the actual config content must be provided as separate files)

## Examples

### Helm deployment with separate configs

```yaml
# .rhdh-upgrade-helper.yaml
from: "1.9"
to: "1.10"
configs:
  - ./helm/values.yaml
  - ./configmaps/app-config-custom.yaml
  - ./configmaps/dynamic-plugins-override.yaml
```

### Operator deployment

```yaml
# .rhdh-upgrade-helper.yaml
from: "1.9"
to: "1.10"
configs:
  - ./backstage-cr.yaml
  - ./configmaps/app-config.yaml
  - ./configmaps/dynamic-plugins.yaml
  - ./configmaps/app-config-auth.yaml
```

### Minimal (just release versions, files via CLI)

```yaml
# .rhdh-upgrade-helper.yaml
from: "1.8"
to: "1.10"
```

Then run: `/rhdh-upgrade-helper --config ./values.yaml --config ./app-config.yaml`
