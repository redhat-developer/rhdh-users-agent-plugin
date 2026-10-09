# Chart migration: RHDH 1.y to 2.y values structure

The downstream RHDH Helm chart (`redhat-developer-hub` at `charts.openshift.io`) keeps the
same name across major versions. What changes is the **values structure**: the 1.y chart
nested values under `upstream.backstage.*`, `global.*`, and `route.*` because it wrapped the
upstream Backstage subchart. The 2.y chart owns all templates directly and flattens
configuration to root-level keys.

Customers cannot pass their old values file to the new chart version directly. They must
migrate values first, then `helm upgrade` the release in place. The migration script
produces a **separate output file** — the original values file is never modified, so
customers can inspect and validate the draft before using it.

Source: [upstream migration guide](https://github.com/redhat-developer/rhdh-chart/blob/release-2.1/charts/rhdh/docs/migration-from-backstage-chart.md) (RHIDP-16514).

## Prerequisites

- Kubernetes 1.31+ / OpenShift 4.18+
- Export existing values if not in version control: `helm get values <release> -n <ns> -o yaml > old-values.yaml`

## Passthrough rule

Fields not listed in any table below keep the same path. If a customer key is not mentioned,
carry it over as-is.

---

## Deterministic mappings

These are mechanical key renames. The migration script applies them automatically.

### Container image

| Old path | New path | Notes |
|----------|----------|-------|
| `upstream.backstage.image.registry` | `image.registry` | |
| `upstream.backstage.image.repository` | `image.repository` | |
| `upstream.backstage.image.tag` | `image.tag` | See digest/tag precedence below |
| `upstream.backstage.image.digest` | `image.digest` | See digest/tag precedence below |
| `upstream.backstage.image.pullPolicy` | `image.pullPolicy` | |
| `upstream.backstage.image.pullSecrets` | `imagePullSecrets` | Promoted to root level |

**Digest/tag interaction:** The downstream chart ships all container images with explicit
digests by default (not tags). When both `digest` and `tag` are set, the chart renders the
image reference as `tag@digest` (e.g., `registry.redhat.io/rhdh/rhdh-hub-rhel9:1.10@sha256:abc...`).
This can fail to resolve at pull time — for example, if you set a custom `tag` pointing to a
different image build while the default `digest` still refers to the original image (the
default digest from the chart is merged by Helm). When overriding with a custom tag, either
set `digest: ""` to clear the default, or set `digest` to the correct digest for your tag.
This applies to every `image.*` block in the chart: `image`, `catalogIndex.image`,
`intelligentAssistant.core.image`, `postgresql.image`, etc.

### Chart-level overrides

| Old path | New path | Notes |
|----------|----------|-------|
| `upstream.nameOverride` | `nameOverride` | Defaults to `developer-hub` |
| `upstream.fullnameOverride` | `fullnameOverride` | |
| `upstream.commonLabels` | `commonLabels` | |
| `upstream.commonAnnotations` | `commonAnnotations` | |
| `upstream.extraDeploy` | `extraDeploy` | Can deploy additional Kubernetes resources alongside the chart (e.g., custom NetworkPolicy rules, ConfigMaps, Secrets) |

### Global parameters

| Old path | New path | Notes |
|----------|----------|-------|
| `global.clusterRouterBase` | `openshift.clusterRouterBase` | |
| `global.host` | `host` | Promoted to root |
| `global.imagePullSecrets` | `global.imagePullSecrets` | Unchanged; see air-gapped note below |
| `global.imageRegistry` | `global.imageRegistry` | Unchanged; now documented and applied consistently; see air-gapped note below |

**Air-gapped / disconnected environments:** `global.imageRegistry` and
`global.imagePullSecrets` apply to all container images managed by the chart (RHDH,
PostgreSQL, catalog index, Intelligent Assistant, etc.) — useful for mirroring to an
internal registry. However, they do **not** apply to dynamic plugin references
(`oci://` or `ref://` in `dynamicPlugins.plugins[].package`). Plugin OCI images must
be mirrored separately and their references updated individually in the dynamic plugins
configuration.

### App config

| Old path | New path | Notes |
|----------|----------|-------|
| `upstream.backstage.appConfig` | `appConfig` | Entire tree flattened |
| `upstream.backstage.extraAppConfig` | `extraAppConfig` | Same format |

Database env var names changed:
- `POSTGRESQL_ADMIN_PASSWORD` &rarr; `POSTGRES_PASSWORD`
- Hardcoded `postgres` user &rarr; `POSTGRES_USER` env var

### Authentication

| Old path | New path | Notes |
|----------|----------|-------|
| `global.auth.backend.enabled` | `auth.backend.enabled` | |
| `global.auth.backend.existingSecret` | `auth.backend.existingSecretRef.name` | Restructured to object |
| _(none)_ | `auth.backend.existingSecretRef.key` | New field, defaults to `backend-secret` |
| `global.auth.backend.value` | `auth.backend.value` | |

### Dynamic plugins

| Old path | New path | Notes |
|----------|----------|-------|
| `global.dynamic.includes` | `dynamicPlugins.includes` | |
| `global.dynamic.plugins` | `dynamicPlugins.plugins` | |
| `upstream.backstage.initContainers[0].resources` | `dynamicPlugins.initContainer.resources` | |
| `upstream.backstage.initContainers[0].securityContext` | `dynamicPlugins.initContainer.securityContext` | |
| `upstream.backstage.initContainers[0].env` | `dynamicPlugins.initContainer.extraEnv` | System env vars auto-injected |

### Pod scheduling, replicas, and metadata

| Old path | New path | Notes |
|----------|----------|-------|
| `upstream.backstage.replicas` | `replicaCount` | Renamed |
| `upstream.backstage.revisionHistoryLimit` | `revisionHistoryLimit` | |
| `upstream.backstage.strategy` | `strategy` | |
| `upstream.backstage.annotations` | `deploymentAnnotations` | Renamed |
| `upstream.backstage.podAnnotations` | `podAnnotations` | |
| `upstream.backstage.podLabels` | `podLabels` | |
| `upstream.backstage.nodeSelector` | `nodeSelector` | |
| `upstream.backstage.tolerations` | `tolerations` | |
| `upstream.backstage.affinity` | `affinity` | |
| `upstream.backstage.topologySpreadConstraints` | `topologySpreadConstraints` | |
| `upstream.backstage.hostAliases` | `hostAliases` | |
| `upstream.backstage.priorityClassName` | `priorityClassName` | |
| `upstream.backstage.terminationGracePeriodSeconds` | `terminationGracePeriodSeconds` | |
| `upstream.backstage.lifecycleHooks` | `lifecycleHooks` | |

### Service account

| Old path | New path | Notes |
|----------|----------|-------|
| `upstream.serviceAccount.create` | `serviceAccount.create` | Defaults to `false` |
| `upstream.serviceAccount.name` | `serviceAccount.name` | |
| `upstream.serviceAccount.annotations` | `serviceAccount.annotations` | |
| `upstream.serviceAccount.automountServiceAccountToken` | `serviceAccount.automount` | Renamed |
| `upstream.serviceAccount.labels` | `serviceAccount.labels` | |

### Container command and env

| Old path | New path | Notes |
|----------|----------|-------|
| `upstream.backstage.command` | `commandOverride` | Renamed |
| `upstream.backstage.extraEnvVars` | `extraEnv` | Renamed; system env vars auto-injected |

### Volumes and mounts

| Old path | New path | Notes |
|----------|----------|-------|
| `upstream.backstage.extraVolumes` | `extraVolumes` | System volumes now hardcoded |
| `upstream.backstage.extraVolumeMounts` | `extraVolumeMounts` | System mounts now hardcoded |

### Sidecars

| Old path | New path | Notes |
|----------|----------|-------|
| `upstream.backstage.extraContainers` | `extraContainers` | |

### Security contexts and resources

| Old path | New path |
|----------|----------|
| `upstream.backstage.podSecurityContext` | `podSecurityContext` |
| `upstream.backstage.containerSecurityContext` | `containerSecurityContext` |
| `upstream.backstage.resources` | `resources` |

### Probes

| Old path | New path |
|----------|----------|
| `upstream.backstage.startupProbe` | `startupProbe` |
| `upstream.backstage.readinessProbe` | `readinessProbe` |
| `upstream.backstage.livenessProbe` | `livenessProbe` |

### Service

| Old path | New path | Notes |
|----------|----------|-------|
| `upstream.service.type` | `service.type` | |
| `upstream.service.ports.backend` | `service.port` | Flattened |
| `upstream.service.nodePorts.backend` | `service.nodePort` | Flattened |
| `upstream.service.extraPorts` | `service.extraPorts` | |
| `upstream.service.clusterIP` | `service.clusterIP` | |
| `upstream.service.loadBalancerIP` | `service.loadBalancerIP` | |
| `upstream.service.loadBalancerSourceRanges` | `service.loadBalancerSourceRanges` | |
| `upstream.service.externalTrafficPolicy` | `service.externalTrafficPolicy` | |
| `upstream.service.sessionAffinity` | `service.sessionAffinity` | |
| `upstream.service.annotations` | `service.annotations` | |
| `upstream.service.ipFamilyPolicy` | `service.ipFamilyPolicy` | |
| `upstream.service.ipFamilies` | `service.ipFamilies` | |

### OpenShift Route

| Old path | New path |
|----------|----------|
| `route.enabled` | `openshift.route.enabled` |
| `route.annotations` | `openshift.route.annotations` |
| `route.host` | `openshift.route.host` |
| `route.path` | `openshift.route.path` |
| `route.wildcardPolicy` | `openshift.route.wildcardPolicy` |
| `route.tls.enabled` | `openshift.route.tls.enabled` |
| `route.tls.termination` | `openshift.route.tls.termination` |
| `route.tls.certificate` | `openshift.route.tls.certificate` |
| `route.tls.key` | `openshift.route.tls.key` |
| `route.tls.caCertificate` | `openshift.route.tls.caCertificate` |
| `route.tls.destinationCACertificate` | `openshift.route.tls.destinationCACertificate` |
| `route.tls.insecureEdgeTerminationPolicy` | `openshift.route.tls.insecureEdgeTerminationPolicy` |

### Autoscaling (HPA)

| Old path | New path | Notes |
|----------|----------|-------|
| `upstream.backstage.autoscaling.enabled` | `autoscaling.enabled` | |
| `upstream.backstage.autoscaling.minReplicas` | `autoscaling.minReplicas` | |
| `upstream.backstage.autoscaling.maxReplicas` | `autoscaling.maxReplicas` | Default changed: 100 &rarr; 3 |
| `upstream.backstage.autoscaling.targetCPUUtilizationPercentage` | `autoscaling.targetCPUUtilizationPercentage` | |
| `upstream.backstage.autoscaling.targetMemoryUtilizationPercentage` | `autoscaling.targetMemoryUtilizationPercentage` | |

### Pod Disruption Budget

| Old path | New path |
|----------|----------|
| `upstream.backstage.pdb.create` | `podDisruptionBudget.create` |
| `upstream.backstage.pdb.minAvailable` | `podDisruptionBudget.minAvailable` |
| `upstream.backstage.pdb.maxUnavailable` | `podDisruptionBudget.maxUnavailable` |

### Gateway API HTTPRoute

| Old path | New path |
|----------|----------|
| `upstream.httpRoute.enabled` | `httpRoute.enabled` |
| `upstream.httpRoute.labels` | `httpRoute.labels` |
| `upstream.httpRoute.annotations` | `httpRoute.annotations` |
| `upstream.httpRoute.parentRefs` | `httpRoute.parentRefs` |
| `upstream.httpRoute.hostnames` | `httpRoute.hostnames` |
| `upstream.httpRoute.rules` | `httpRoute.rules` |

### Catalog index

| Old path | New path |
|----------|----------|
| `global.catalogIndex.image.registry` | `catalogIndex.image.registry` |
| `global.catalogIndex.image.repository` | `catalogIndex.image.repository` |
| `global.catalogIndex.image.tag` | `catalogIndex.image.tag` |
| `global.catalogIndex.extraImages` | `catalogIndex.extraImages` |

### PostgreSQL (Bitnami subchart)

| Old path | New path | Notes |
|----------|----------|-------|
| `upstream.postgresql.enabled` | `postgresql.enabled` | |
| `upstream.postgresql.postgresqlDataDir` | `postgresql.postgresqlDataDir` | |
| `upstream.postgresql.serviceBindings.enabled` | `postgresql.serviceBindings.enabled` | |
| `upstream.postgresql.image.*` | `postgresql.image.*` | Default changed: PostgreSQL 15 &rarr; 18 |
| `upstream.postgresql.auth.*` | `postgresql.auth.*` | |
| `upstream.postgresql.primary.*` | `postgresql.primary.*` | |

### Metrics / monitoring

| Old path | New path |
|----------|----------|
| `upstream.metrics.serviceMonitor.enabled` | `metrics.serviceMonitor.enabled` |
| `upstream.metrics.serviceMonitor.path` | `metrics.serviceMonitor.path` |
| `upstream.metrics.serviceMonitor.port` | `metrics.serviceMonitor.port` |
| `upstream.metrics.serviceMonitor.interval` | `metrics.serviceMonitor.interval` |
| `upstream.metrics.serviceMonitor.labels` | `metrics.serviceMonitor.labels` |
| `upstream.metrics.serviceMonitor.annotations` | `metrics.serviceMonitor.annotations` |

### Test pod

| Old path | New path | Notes |
|----------|----------|-------|
| `test.image.tag` | `test.image.tag` | Default changed: `latest` &rarr; pinned version |

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
2. Merge `extraHosts` into the `hosts[]` array; rename `name` &rarr; `host`, wrap `path` in `paths[]`
3. Convert `tls.enabled` + `tls.secretName` into `tls[0]` with `hosts: [<primary host>]`
4. Merge `extraTls` into the `tls[]` array

**Why ambiguous:** The TLS-to-host association is not explicit in the old format. When
`tls.enabled: true` with a `secretName`, the script must decide which host(s) to associate
with that TLS entry. Default: associate with the primary `host` only.

### 2. Intelligent Assistant / Lightspeed (significant restructuring)

**What changed:** Rebranded from Lightspeed to Intelligent Assistant. Multiple structural
changes beyond simple renaming.

**Sub-areas:**

**a) Sidecar image (string &rarr; structured):**
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

**b) ConfigMaps (array &rarr; structured):**
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
- `global.lightspeed.initContainer.*` &rarr; removed (RAG init container gone)
- `global.lightspeed.ragVolume.*` &rarr; removed
- `global.lightspeed.sidecar.name` &rarr; hardcoded
- `global.lightspeed.sidecar.portName` &rarr; hardcoded
- `global.lightspeed.sidecar.containerPort` &rarr; hardcoded
- `global.lightspeed.runtimeVolume.name` &rarr; hardcoded
- `global.lightspeed.runtimeVolume.mountPath` &rarr; hardcoded
- `global.lightspeed.secret.optional` &rarr; removed

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

## Behavioral changes (informational)

### Default-deny NetworkPolicies
The new chart always deploys default-deny NetworkPolicies. Customers with additional network
connectivity needs must add corresponding rules manually.

### Schema validation
The new chart ships a JSON Schema that validates values at install/upgrade time. Leftover
`upstream.*` keys may pass silently. Run `helm template` to check for rendering errors.

### PostgreSQL default version
Default image changed from PostgreSQL 15 to 18. Customers with existing data directories must
explicitly pin `postgresql.image.tag` to their current version.

### HPA maxReplicas default
Changed from 100 to 3.

### Database env vars
`POSTGRESQL_ADMIN_PASSWORD` &rarr; `POSTGRES_PASSWORD`, hardcoded `postgres` user &rarr;
`POSTGRES_USER` env var.

### Intelligent Assistant secret
The new chart does not create a placeholder secret. Customers must create the secret
independently before upgrading.

### Image digest/tag interaction
The downstream chart ships all container images with explicit digests by default. When both
`tag` and `digest` are set, the chart renders the reference as `tag@digest`, which can fail
to resolve at pull time if they point to different image builds. When overriding with a custom
tag, either set `digest: ""` to clear the default, or set `digest` to the correct digest for
your tag. This applies to every `image.*` block (`image`, `catalogIndex.image`,
`intelligentAssistant.core.image`, `postgresql.image`, etc.).

### Go template `.Values.*` references
String values in the 1.y file may contain Go template expressions referencing old paths
(e.g., `{{ .Values.global.host }}`). The migration script automatically rewrites known
`.Values.global.*`, `.Values.upstream.*`, and `.Values.route.*` references to their 2.y
equivalents (e.g., `{{ .Values.host }}`). References to decomposed fields (like
`global.lightspeed.sidecar.image`, now split into `intelligentAssistant.core.image.*`)
are flagged for manual update since a single replacement is not possible. Any remaining
old-style references not in the mapping tables are also flagged.

### Chart-managed defaults in extra* fields
The 2.y chart automatically manages certain volumes, mounts, env vars, and init containers
that 1.y users commonly added manually via `extraVolumes`, `extraVolumeMounts`, `extraEnv`,
and `initContainers`. The migration script **removes unconditional defaults deterministically**
and **flags conditional defaults for review**.

#### Unconditional (removed automatically)

**Volumes**: `dynamic-plugins-root`, `dynamic-plugins`, `dynamic-plugins-npmrc`,
`dynamic-plugins-registry-auth`, `npmcacache`, `extensions-catalog`, `temp`

**Mount paths**: `/opt/app-root/src/dynamic-plugins-root`, `/dynamic-plugins-root`,
`/opt/app-root/src/dynamic-plugins.yaml`, `/opt/app-root/src/.npmrc.dynamic-plugins`,
`/opt/app-root/src/.npmrc.d`, `/opt/app-root/src/.config/containers`,
`/opt/app-root/src/.npm/_cacache`, `/extensions`, `/tmp`

**Env vars**: `APP_CONFIG_backend_listen_port`, `NPM_CONFIG_USERCONFIG`

**Init containers**: `install-dynamic-plugins`

#### Conditional (flagged for review)

**Volumes**: `backstage-app-config` (when `appConfig` is set), `lightspeed-data`,
`lightspeed-config-stack`, `lightspeed-config-profile` (when IA is enabled)

**Mount paths**: `/opt/app-root/src/app-config-from-configmap.yaml`

**Env vars**: `BACKEND_SECRET` (when `auth.backend.enabled`), `POSTGRES_HOST`,
`POSTGRES_PORT`, `POSTGRES_USER`, `POSTGRES_PASSWORD` (when DB is configured),
`APP_CONFIG_app_baseUrl`, `APP_CONFIG_backend_baseUrl`, `APP_CONFIG_backend_cors_origin`
(redundant with chart's default `appConfig`)

**Init containers**: `wait-for-db` (when DB is configured)

The output header recommends including only customized values for easier maintenance.

### Air-gapped image resolution
`global.imageRegistry` and `global.imagePullSecrets` apply to all chart-managed container
images but do **not** affect dynamic plugin references (`oci://` or `ref://` in
`dynamicPlugins.plugins`). Plugin OCI images must be mirrored and referenced individually.

---

## Removed values (no 2.y equivalent)

| Old path | Notes |
|----------|-------|
| `upstream.backstage.installDir` | Hardcoded in new chart |
| `upstream.backstage.containerPorts.backend` | Hardcoded to 7007 |
| `upstream.diagnosticMode.*` | Not supported |
| `upstream.networkPolicy.*` | Replaced with built-in default-deny policies |
| `global.lightspeed.initContainer.*` | RAG init container removed |
| `global.lightspeed.ragVolume.*` | RAG volume removed |
| `global.lightspeed.sidecar.name` | Hardcoded |
| `global.lightspeed.sidecar.portName` | Hardcoded |
| `global.lightspeed.sidecar.containerPort` | Hardcoded |
| `global.lightspeed.runtimeVolume.name` | Hardcoded |
| `global.lightspeed.runtimeVolume.mountPath` | Hardcoded |
| `global.lightspeed.secret.optional` | Removed |
| `test.injectTestNpmrcSecret` | Removed |

---

## New features (no old-chart equivalent)

| Feature | Values path | Description |
|---------|-------------|-------------|
| StatefulSet workload | `workload.kind: StatefulSet` | Stable pod identity and persistent volumes |
| External database block | `externalDatabase.*` | Dedicated config when `postgresql.enabled: false` |
| OKP | `intelligentAssistant.okp.*` | Offline Knowledge Portal |
| Pre-init containers | `preInitContainers` | Runs before system init containers |
| Extra init containers | `extraInitContainers` | Runs after system init containers |
| Dynamic plugins volume config | `dynamicPlugins.volume.*` | Replaces raw volume specs |
