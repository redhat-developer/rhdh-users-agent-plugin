# RHDH 2.1 Migration Reference

Use this reference for every 1.x → 2.1 assessment, whether the deployment uses Helm, the Operator, or RHDH Local. Apply it alongside the release-by-release notes and product metadata. For Helm values, also run `workflows/chart-migration.md`.

## Sources and version context

- [RHDH 2.1 release notes](https://docs.redhat.com/en/documentation/red_hat_developer_hub/2.1/whats_new-red_hat_developer_hub_release_notes)
- [Migration from RHDH 1.x to 2.1](https://docs.redhat.com/en/documentation/red_hat_developer_hub/2.1/migrate-migrate_from_rhdh_1_x_to_2_1)
- [RHDH 2.1 upgrade and migration guidance](https://redhat-developer.github.io/red-hat-developers-documentation-rhdh/release-2.1/product_product/)
- [RHDH 2.1 pre-upgrade checklist](https://docs.redhat.com/en/documentation/red_hat_developer_hub/2.1/migrate-pre_upgrade_checklist)
- [RHDH 2.1 chart migration guide](https://github.com/redhat-developer/rhdh-chart/blob/release-2.1/charts/rhdh/docs/migration-from-backstage-chart.md)
- [RHDH 2.1 overlay metadata](https://raw.githubusercontent.com/redhat-developer/rhdh-plugin-export-overlays/release-2.1/versions.json)
- [RHDH 1.10 release-note update about multi-entry Operator ConfigMaps](https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html/red_hat_developer_hub_release_notes/fixed-issues)

RHDH 2.1 uses Backstage 1.54.9, Node.js 24.21.0, and CLI 2.1.2. The documented minimum platform is Kubernetes 1.32 / OpenShift 4.19. Use release notes for every version in the requested FROM→TO range. Resolve plugin artifacts from the target Package entity's `spec.dynamicArtifact`; do not construct or guess OCI references.

## Skip-version assumption for team review

The RHDH 2.1 upgrade guidance says direct upgrades from any earlier version to the latest release do not require installing intermediate versions, provided that release notes for skipped versions are reviewed. For 1.x→2.1, it also directs users to the detailed migration procedure written for a 1.10→2.1 migration. Keep the skill's existing skip-version behavior unchanged: it analyzes the requested FROM→TO range and reads the release notes for intermediate versions. Whether that existing assessment provides complete migration coverage for every source version to 2.1 (including 1.9) remains an assumption for the team to validate. Do not add a new hard stop, phase, or staged-upgrade plan to the existing route/phase logic.

## Pre-upgrade checklist

- Confirm Kubernetes 1.32+ or OpenShift 4.19+.
- For Operator deployments moving from 1.10 to 2.1, switch to the `fast-2.1` channel as directed by the upgrade guidance. Do not describe the generic `fast` channel as deprecated; it includes updates across versions.
- Operator upgrades no longer skip minor versions: the 2.1 `skipRange` requires the previous minor, so the supported paths are 1.10.z → 2.1 and 2.1.z → 2.2.
- For Helm deployments, migrate the 1.y values structure and validate it with `helm template`. In-place `helm upgrade` is supported; do not uninstall solely because of the major-version change.
- Review the complete release-note range and the current pre-upgrade checklist. Back up configuration, database data, and custom plugin artifacts before applying changes.
- Re-run the assessment against the resulting configuration before proceeding to production, especially if upgrading through an intermediate version.

## Configuration and artifact migrations

For each signal, confirm it is present in the customer's configuration before reporting it. Use Critical or Important only when supported by the cited release-note, migration-guide, or target metadata evidence. Keep file and line details when available.

| Area and evidence to look for | Assessment and action |
|---|---|
| Plugin entries using `./dynamic-plugins/dist/...` | Bundled wrappers are removed. Resolve the package against target `spec.dynamicArtifact`; recommend only that exact target artifact, including its `ref://` or `oci://` form where supplied. Treat an unresolved target artifact as manual review; never invent an image. |
| `APP_CONFIG_app_packageName=app-next`, `ENABLE_STANDARD_MODULE_FEDERATION=true`, or `dynamicPlugins.frontend` | The 2.1 frontend uses NFS. Remove the two old NFS-selection environment variables. Migrate frontend plugin wiring from `dynamicPlugins.frontend` to `app.extensions` and `app.routes.bindings`; identify custom plugins that need NFS-compatible implementations. |
| Configured `auth.providers.<id>` without a corresponding enabled authentication backend dynamic plugin; `disableIdentityResolution: true`; or Guest sign-in expected only from development mode | In 2.1, providers are not installed by default: install/enable the matching dynamic plugin and keep provider settings under `auth.providers.<id>`. For an auxiliary provider, replace `disableIdentityResolution: true` with `signIn.resolvers: []`; do not set an empty resolver list on the primary sign-in provider. Install/configure the Guest provider explicitly rather than relying on development mode. Do not treat `auth.providers` or the still-supported top-level `signInPage` by themselves as errors. |
| RBAC permission names beginning with `lightspeed.` or CRUD-specific Intelligent Assistant permissions | Rename to the `intelligent-assistant.*` permission family and use the consolidated `use` verb where applicable. Old permission names can fail silently, so identify the exact configured permission and replacement from the release evidence. |
| Developer Lightspeed app-config keys, routes, or Llama Stack references | Migrate naming to Intelligent Assistant (`intelligent-assistant`); update `/lightspeed` routes to `/intelligent-assistant` and replace Llama Stack integration with LCORE according to the 2.1 migration guide. |
| Image references ending in `-rhel9` | Check each image against the release documentation and mirror. Product images renamed to `-rhel10` must be updated; the RAG content image `rhdh-rag-content-rhel9:1.10` is removed. Update disconnected mirrors to avoid pulls for removed image names. Do not rename the Intelligent Assistant sidecar (`lightspeed-stack-rhel9`) or Offline Knowledge Portal image (`rhokp-rhel9`); both remain RHEL 9 images. |
| Operator deployment with an `app-config` ConfigMap containing multiple entries | This is not a new 2.1 requirement. The RHDH 1.10 Operator documentation notes that entries are sorted alphabetically and recommends separate single-entry ConfigMaps when merge order matters. Flag the configuration only when the customer relies on a particular merge order; split the ConfigMap and list the separate maps in the intended order. |
| Scorecard provider settings, metric IDs, or aggregation-card wiring | Check configured provider settings against the 2.1 `scorecard.metricProviders.<provider>` schema and the target metric reference (for example, `github.open_prs` becomes `github.openPRs`); do not mechanically rename every metric. Configure aggregation cards through `app.extensions`. Preserve `scorecard.plugins.filecheck` where used for file-check configuration. |
| TechDocs add-on wiring under `dynamicPlugins.frontend.<plugin>.techdocsAddons` | RHDH 2.1 registers TechDocs add-ons through `AddonBlueprint`; replace the old wiring with the add-on extension IDs in `app.extensions`. |
| Removed or unavailable plugins | Check for `global-floating-action-button`, `dynamic-home-page`, and `@backstage-community/plugin-catalog-backend-module-pingidentity`. The Global Floating Action Button and `dynamic-home-page` packages are removed; `homepage` is added for the new frontend system. The 2.1 dynamic-plugin comparison lists the Ping Identity catalog backend module as unavailable. Report configured unavailable packages and resolve any replacement only from target metadata; do not confuse this package with a PingFederate authentication provider. Migrate only frontend features the customer uses. |
| Helm values using chart-managed PostgreSQL or `POSTGRESQL_ADMIN_PASSWORD` | The 2.1 Helm chart defaults to PostgreSQL 18 instead of 15. For an existing PostgreSQL 15 data directory, either perform the documented database upgrade or retain PostgreSQL 15 with `postgresql.image.repository: rhel10/postgresql-15` and a matching digest (or clear the default digest). The chart changes `POSTGRESQL_ADMIN_PASSWORD` to `POSTGRES_PASSWORD`; do not apply these chart-specific changes to an external database or non-Helm deployment without separate evidence. |
| Dynamic-plugin entry with `disabled` | Report the announced `disabled`→`enabled` deprecation as **Informational** for 2.1: explain that migration is needed in a later release (removal is planned for 2.3). Do not treat it as a 2.1 break, rewrite it automatically, or deduct readiness points. |

Also review deprecated Orchestrator per-workflow permission strings when they appear in the customer's RBAC policy; migrate workflow-specific restrictions to conditional policies. Do not flag the top-level auth `signInPage` as deprecated: it remains documented in RHDH 2.1. Let target plugin metadata drive support-level findings.

## Helm-specific behavior

Read `workflows/chart-migration.md` and `references/chart-migration-1y-2y.md` for chart value mappings. The 2.1 chart-specific corrections are:

- The minimum platform is Kubernetes 1.32+ / OpenShift 4.19+.
- Both the 2.1 Helm chart and Operator deploy default-deny NetworkPolicies. For either deployment, inspect known external endpoints, custom sidecars, and cross-namespace dependencies and require matching allow rules; do not apply this Kubernetes policy finding to RHDH Local.
- Intelligent Assistant is enabled by default. Check the customer's intent when `intelligentAssistant.enabled` is omitted; do not silently disable it. The sidecar image is `lightspeed-stack-rhel9`.
- If PostgreSQL 15 must be retained for an existing data directory, set `postgresql.image.repository` to `rhel10/postgresql-15` and override the image digest for that repository. Do not use `postgresql.image.tag` for this pin.
- The `autoscaling.maxReplicas` default changes from 100 to 3.

## Evidence and scoring

Every Critical or Important finding must cite a concrete release-note item, migration-guide instruction, or target Package entity. Apply the existing readiness categories to observed findings across deployment methods: configuration changes count under breaking config keys, and verified plugin artifact transitions count under artifact-source migrations. Apply chart-value and chart-restructuring deductions only when Helm chart migration applies. Informational deprecations, including `disabled`→`enabled`, do not reduce the score.
