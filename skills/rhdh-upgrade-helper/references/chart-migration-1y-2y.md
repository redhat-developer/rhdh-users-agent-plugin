# Chart migration: RHDH 1.y to 2.y — skill-specific metadata

This file contains the **skill-specific** metadata that the migration script and
AI workflow need on top of the upstream migration guide. For the complete mapping
tables (Old path → New path), behavioral changes, removed values, and new
features, read the **upstream migration guide**:

> [upstream migration guide](https://github.com/redhat-developer/rhdh-chart/blob/release-2.1/charts/rhdh/docs/migration-from-backstage-chart.md)
> (RHIDP-16514) — authoritative source for all deterministic key mappings,
> before/after YAML examples, chart-managed defaults inventory, and behavioral
> change warnings.

The migration script produces a **separate output file** — the original values
file is never modified, so customers can inspect and validate the draft before
using it.

---

## Ambiguous areas (require AI-assisted resolution)

These areas cannot be translated by simple key renaming. They require understanding the
customer's intent and producing a structurally different output.

### 1. Ingress (structural reshape)

**What changed:** The single `host`/`path` model becomes an array of host objects.

**Old structure:**
```yaml
upstream:
  ingress:
    enabled: true
    className: nginx
    annotations: {}
    host: my-rhdh.example.com
    path: /
    extraHosts:
      - name: alt.example.com
        path: /rhdh
    tls:
      enabled: true
      secretName: rhdh-tls
    extraTls:
      - hosts: [alt.example.com]
        secretName: alt-tls
```

**New structure:**
```yaml
ingress:
  enabled: true
  className: nginx
  annotations: {}
  hosts:
    - host: my-rhdh.example.com
      paths:
        - path: /
    - host: alt.example.com
      paths:
        - path: /rhdh
  tls:
    - hosts: [my-rhdh.example.com]
      secretName: rhdh-tls
    - hosts: [alt.example.com]
      secretName: alt-tls
```

**Transformation rules:**
1. Move `host` + `path` into `hosts[0].host` + `hosts[0].paths[0].path`
2. Merge `extraHosts` into the `hosts[]` array; rename `name` → `host`, wrap `path` in `paths[]`
3. Convert `tls.enabled` + `tls.secretName` into `tls[0]` with `hosts: [<primary host>]`
4. Merge `extraTls` into the `tls[]` array

**Why ambiguous:** The TLS-to-host association is not explicit in the old format. When
`tls.enabled: true` with a `secretName`, the script must decide which host(s) to associate
with that TLS entry. Default: associate with the primary `host` only.

### 2. Intelligent Assistant / Lightspeed (significant restructuring)

**What changed:** Rebranded from Lightspeed to Intelligent Assistant. Multiple structural
changes beyond simple renaming.

**Sub-areas:**

**a) Sidecar image (string → structured):**
```yaml
# Old:
global:
  lightspeed:
    sidecar:
      image: "quay.io/ai/lightspeed-service:1.2.3"

# New:
intelligentAssistant:
  core:
    image:
      registry: quay.io
      repository: ai/lightspeed-service
      tag: "1.2.3"
```
Split the image string at `/` boundaries: everything before the first `/` is the registry,
everything between first `/` and `:` is the repository, after `:` is the tag. If no tag,
omit it. If no registry prefix (e.g., `lightspeed-service:1.0`), omit registry.

**b) ConfigMaps (array → structured):**
```yaml
# Old: array of 3 configMaps
global:
  lightspeed:
    configMaps:
      - name: lightspeed-config
      - name: lightspeed-stack
      - name: lightspeed-profile

# New: 2 structured entries
intelligentAssistant:
  config:
    stack:
      existingConfigMap: lightspeed-stack
    profile:
      existingConfigMap: lightspeed-profile
```
The separate `config.yaml` ConfigMap is no longer needed because the llama-stack configuration
is now inlined in `lightspeed-stack.yaml`.

**Why ambiguous:** The old array was positional with no typed keys. The migration must
identify which ConfigMap is the stack config and which is the profile by name or position.
If names don't match expected patterns, flag for manual review.

**c) Secret handling:**
```yaml
# Old:
global:
  lightspeed:
    secret:
      create: true
      name: lightspeed-secret

# New:
intelligentAssistant:
  existingSecret: lightspeed-secret
```
The new chart does NOT create a placeholder secret. The customer must create it independently
before upgrading. Flag this as a **manual action** in the migration report.

**d) Removed fields:**
- `global.lightspeed.initContainer.*` → removed (RAG init container gone)
- `global.lightspeed.ragVolume.*` → removed
- `global.lightspeed.sidecar.name` → hardcoded
- `global.lightspeed.sidecar.portName` → hardcoded
- `global.lightspeed.sidecar.containerPort` → hardcoded
- `global.lightspeed.runtimeVolume.name` → hardcoded
- `global.lightspeed.runtimeVolume.mountPath` → hardcoded
- `global.lightspeed.secret.optional` → removed

**e) Plugin format:**
The new chart supports `ref://` as a convenience format to reference default catalog plugins by name (e.g., `ref://backstage-plugin-catalog-backend-module-gitlab`), but `oci://` references remain fully supported. No forced migration needed — existing `oci://` references continue to work.

### 3. Container args (semantic choice)

**What changed:** `upstream.backstage.args` maps to either `extraArgs` or `argsOverride`.

- `extraArgs`: appends after the system `--config` flags. **Preferred** for most cases.
- `argsOverride`: replaces ALL arguments including system ones. Only for full control.

**Default behavior:** Map to `extraArgs` with a review marker explaining the choice.
If the old args contain `--config` flags, suggest `argsOverride` instead since the user
was already managing config loading manually.

### 4. Env from secrets/ConfigMaps (format change)

**What changed:** `extraEnvVarsSecrets` and `extraEnvVarsCM` both map to `extraEnvFrom`
but the format changes from simple name strings to structured refs.

```yaml
# Old:
upstream:
  backstage:
    extraEnvVarsSecrets:
      - my-secret
      - another-secret
    extraEnvVarsCM:
      - my-configmap

# New:
extraEnvFrom:
  - secretRef:
      name: my-secret
  - secretRef:
      name: another-secret
  - configMapRef:
      name: my-configmap
```

**Why ambiguous:** Both old fields merge into one new field. The script must interleave
entries correctly and choose `secretRef` vs `configMapRef` based on source.

### 5. Network policies (removed, replaced with defaults)

**What changed:** `upstream.networkPolicy.*` has no equivalent. The new chart always deploys
default-deny NetworkPolicies allowing only DNS, PostgreSQL, and OpenShift ingress/monitoring.

**Migration action:** Remove all `upstream.networkPolicy.*` keys. Flag as a **manual action**:
"Review your network connectivity requirements. If your RHDH deployment connects to external
APIs, custom sidecars, or cross-namespace services, add corresponding NetworkPolicy rules.
You can use `extraDeploy` to deploy custom NetworkPolicy resources alongside the chart.
See the chart's NetworkPolicies documentation."

### 6. Init containers (structural change)

**What changed:** System init containers are no longer specified as raw arrays. The
`install-dynamic-plugins` init container is configured via `dynamicPlugins.initContainer.*`.
Custom init containers use `preInitContainers` (before system) or `extraInitContainers`
(after system).

**Migration action:** If the customer had only the dynamic-plugins init container, map its
`resources`, `securityContext`, and `env` to `dynamicPlugins.initContainer.*`. If they had
additional custom init containers in the array, move those to `preInitContainers` or
`extraInitContainers` depending on ordering intent.

### 7. Orchestrator (structural splits)

**What changed:** Multiple flat fields restructured into nested objects.

```yaml
# Old:
orchestrator:
  sonataflowPlatform:
    externalDBsecretRef: my-db-secret
    externalDBName: sonataflow
    externalDBHost: postgres.example.com
    externalDBPort: "5432"
    initContainerImage: "registry.redhat.io/rhdh/init:1.0"
    createDBJobImage: "registry.redhat.io/rhdh/init:1.0"
    dataIndexImage: "registry.redhat.io/rhdh/data-index:1.0"
    jobServiceImage: "registry.redhat.io/rhdh/job-service:1.0"
    dbCreationJobBackoffLimit: 6
    dbCreationJobTTLSecondsAfterFinished: 600
    dbCreationJobActiveDeadlineSeconds: 300

# New:
orchestrator:
  sonataflowPlatform:
    externalDB:
      existingSecret: my-db-secret
      name: sonataflow
      host: postgres.example.com
      port: "5432"
    dbCreationJob:
      image:
        registry: registry.redhat.io
        repository: rhdh/init
        tag: "1.0"
      backoffLimit: 6
      ttlSecondsAfterFinished: 600
      activeDeadlineSeconds: 300
    dataIndex:
      image:
        registry: registry.redhat.io
        repository: rhdh/data-index
        tag: "1.0"
    jobService:
      image:
        registry: registry.redhat.io
        repository: rhdh/job-service
        tag: "1.0"
```

**Why ambiguous:** Image strings must be split into `registry`/`repository`/`tag` components.
The `initContainerImage` and `createDBJobImage` may differ but merge into one `dbCreationJob.image`.

### 8. Auth secret restructuring

**What changed:** `global.auth.backend.existingSecret` (a string) becomes an object with
`name` and `key` fields.

```yaml
# Old:
global:
  auth:
    backend:
      existingSecret: my-auth-secret

# New:
auth:
  backend:
    existingSecretRef:
      name: my-auth-secret
      key: backend-secret
```

The `key` defaults to `backend-secret` but may need adjustment if the customer's secret
uses a different key name.

---

## Script-specific metadata

The following sections document behavior specific to the migration script
(`scripts/migrate-chart-values.py`) and AI workflow. This metadata supplements
the upstream migration guide's `.Values.*` reference table with entries the
script needs that aren't directly derivable from the deterministic mapping tables.

### Additional `.Values.*` rewriting entries

The script's rewriting table is built from the deterministic mappings in the
upstream guide, plus these parent-path entries (needed because Go templates
may reference a parent object, not just leaf keys):

| Old reference | New reference |
|---------------|---------------|
| `global.catalogIndex` | `catalogIndex` |
| `global.auth` | `auth` |
| `global.auth.backend` | `auth.backend` |
| `global.dynamic` | `dynamicPlugins` |
| `route` | `openshift.route` |
| `route.tls` | `openshift.route.tls` |

### Decomposed fields (flagged, not rewritten)

These fields were split from a single value into structured sub-fields. The
script flags them for manual update since a single find-and-replace is not
possible. See the upstream guide's "Go template `.Values.*` references" section
for context.

| Old reference | Migration note |
|---------------|----------------|
| `global.lightspeed.sidecar.image` | Now `intelligentAssistant.core.image.{registry,repository,tag}` |
| `orchestrator.sonataflowPlatform.initContainerImage` | Now `orchestrator.sonataflowPlatform.dbCreationJob.image.{registry,repository,tag}` |
| `orchestrator.sonataflowPlatform.createDBJobImage` | Now `orchestrator.sonataflowPlatform.dbCreationJob.image.{registry,repository,tag}` |
| `orchestrator.sonataflowPlatform.dataIndexImage` | Now `orchestrator.sonataflowPlatform.dataIndex.image.{registry,repository,tag}` |
| `orchestrator.sonataflowPlatform.jobServiceImage` | Now `orchestrator.sonataflowPlatform.jobService.image.{registry,repository,tag}` |
