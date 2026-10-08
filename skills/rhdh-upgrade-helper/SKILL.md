---
name: rhdh-upgrade-helper
description: Customer-facing upgrade assessment for RHDH. Analyzes your configuration files (or asks about your environment) against a target RHDH release to produce a concrete migration plan with readiness scoring. Use when upgrading RHDH, planning a migration, checking what breaks in a new version, assessing upgrade impact, or asking "can I upgrade to X.Y", "what changed between versions", "migration guide", "upgrade checklist", "is my config compatible". No Jira access or Red Hat subscription required.
---

<objective>
Help RHDH customers prepare for an upgrade by correlating their actual configuration (or described environment) with product changes between releases. Produces a prioritized migration checklist, readiness score, and a "Does NOT Affect You" section that shows which breaking changes are irrelevant to their setup.
</objective>

<quick_start>
Invoke with:

- Config file:      `/rhdh-upgrade-helper` (reads `.rhdh-upgrade-helper.yaml` from cwd)
- Individual files: `/rhdh-upgrade-helper --to 1.10 --config ./values.yaml --config ./app-config.yaml`
- Directory:        `/rhdh-upgrade-helper --to 1.10 --config-path ./my-configs/`
- Interactive:      `/rhdh-upgrade-helper --to 1.10`
- Skip-release:     `/rhdh-upgrade-helper --from 1.8 --to 1.10 --config ./values.yaml`
- Chart migration:  `/rhdh-upgrade-helper --from 1.10 --to 2.1 --config ./values.yaml`

Arguments: `[--to X.Y] [--from X.Y] [--config /path/to/file] [--config-path /dir]`

- **--to X.Y** (required): Target RHDH release version to upgrade TO.
- **--from X.Y** (optional): Source RHDH release version upgrading FROM. Defaults to the release immediately before `--to`. Use when skipping releases (e.g., `--from 1.8 --to 1.10`).
- **--config /path/to/file** (optional, repeatable): Path to an individual config file. Can be specified multiple times. Accepts `values.yaml`, `app-config.yaml`, `dynamic-plugins.yaml`, Backstage CR, or any YAML with RHDH configuration. File type is auto-detected from content.
- **--config-path /dir** (optional): Path to a directory to scan for config files. When provided, scans for known file patterns. Can be combined with `--config` for additional files.
- When no config source is given, the skill checks for `.rhdh-upgrade-helper.yaml` in the current directory. If not found, it asks intake questions to build your environment profile. See `references/rhdh-upgrade-helper-config.md`.
</quick_start>

<context>
This skill uses two data sources:

1. **Your environment** — either parsed from config files (`--config-path`) or built from intake questions. Determines which plugins, auth providers, and features you use.

2. **Product context** — release diffs, breaking changes, plugin version jumps, support level changes, bundle-to-OCI migrations. Gathered first from the shipped `plugin-catalog-index` image, which includes productized plugin metadata and documentation, with the public `rhdh-plugin-export-overlays` repo as a fallback, plus RHDH release notes. Determines what changed between your current and target releases.

3. **Known bug data** — For each plugin in your config, the skill searches the RHDHBUGS Jira project for open bugs affecting that plugin in the target release. Also queries GitHub Issues on `redhat-developer/rhdh` for community-reported upgrade issues. If Jira is not accessible, falls back to GitHub Issues and release notes only.

4. **Chart migration data** — For major version upgrades (1.x → 2.x), the chart values migration reference (`references/chart-migration-1x-2x.md`) provides deterministic key mappings and ambiguous area guidance. The migration script (`scripts/migrate-chart-values.py`) automates mechanical translations and flags areas needing AI-assisted resolution.

The skill correlates these to answer: "Of all the changes in the target release, which ones actually affect MY setup?"

### Config file

When a `.rhdh-upgrade-helper.yaml` file exists in the current directory (or in `--config-path`), the skill reads file paths and release versions from it. This avoids re-typing flags on repeat runs. See `references/rhdh-upgrade-helper-config.md`.

### Config analysis

When config files are provided (via `.rhdh-upgrade-helper.yaml`, `--config`, or `--config-path`), parsing follows `references/config-analysis.md`. File type is auto-detected from content — supports Helm values, app-config, dynamic-plugins config, Backstage CR, and `.env` files.

### Security

All config files are scanned for embedded secrets before processing. See `references/secrets-detection.md`. Template variable references (`${VAR}`) are safe — only literal secret values are flagged.
</context>

<routing>
| Condition | Workflow |
|-----------|----------|
| Major version upgrade (`--from` 1.x, `--to` 2.x) with Helm values file | `workflows/chart-migration.md` (chart values migration + upgrade assessment) |
| Config files resolved (via `.rhdh-upgrade-helper.yaml`, `--config`, or `--config-path`) | `workflows/full-report.md` (config-driven assessment) |
| No config files resolved | `workflows/interactive.md` (ask intake questions, then assess) |
| "help", "explain", "how" | `workflows/help.md` |

**`--to` is always required.** If omitted, prompt for it before routing. `.rhdh-upgrade-helper.yaml` may provide it.
**Major version detection:** If the major version differs between `--from` and `--to` (e.g., 1.10 → 2.1) and a Helm values file is provided, route to `workflows/chart-migration.md` first. This handles chart values restructuring, then optionally runs `workflows/full-report.md` for the full upgrade assessment.
**When no config files are resolved, always route to `workflows/interactive.md` — never produce a generic report without gathering environment context first.**
</routing>

<reference_index>

| Reference | Purpose |
|-----------|---------|
| `references/config-scoring.md` | Readiness scoring model — base score from config findings, amplifiers, mitigators. Positive framing (90 = ready). |
| `references/output-format.md` | Customer-facing report template — migration steps first, "Does NOT Affect You" section, upgrade checklist. |
| `references/intake-questions.md` | Interactive environment questionnaire — 7 questions that build an `$ENVIRONMENT_PROFILE`. |
| `references/secrets-detection.md` | Secret patterns to scan for before processing config files. Template refs are safe; literal secrets are flagged. |
| `references/rhdh-local.md` | RHDH Local detection and recommendation for safe pre-upgrade testing. |
| `references/env-vars.md` | Known RHDH environment variables that affect upgrade behavior. |
| `references/rhdh-upgrade-helper-config.md` | `.rhdh-upgrade-helper.yaml` format, resolution order, file type auto-detection, Helm and Operator examples. |
| `references/config-analysis.md` | How to parse customer config files — content-based auto-detection for Helm values, app-config, dynamic-plugins, and Backstage CR. |
| `references/rhdh-architecture.md` | RHDH architecture context — what actually breaks on upgrade vs. common false positives. |
| `references/chart-migration-1x-2x.md` | Chart values migration tables for 1.x→2.x: deterministic mappings, ambiguous areas, behavioral changes, removed/new values. |
| `references/release-notes/{X.Y}.md` | Per-release notes (new features, breaking changes, deprecated/removed features, known issues). One file per release. |
</reference_index>

<workflows_index>

| Workflow | Purpose | Data Sources Used |
|----------|---------|-------------------|
| `workflows/chart-migration.md` | AI-assisted chart values migration for 1.x→2.x upgrades | Migration script + chart-migration-1x-2x reference + AI resolution |
| `workflows/full-report.md` | Config-driven upgrade assessment with line-level migration steps | Config analysis + product context |
| `workflows/interactive.md` | Guided Q&A to build environment profile, then runs full assessment | Intake questions + product context |
| `workflows/help.md` | Explain the skill and its capabilities | None |
</workflows_index>

<anti_patterns>
<pitfall name="generic-advice-without-context">
Never produce migration advice without knowing the customer's environment. If no `--config-path` is given, ask intake questions first. "Update your auth config" is useless without knowing which auth provider they use.
</pitfall>

<pitfall name="workspace-rename-false-positive">
**Never predict breakage from upstream workspace renames.** Customers configure plugins by OCI image and NPM package name, not workspace paths. A workspace rename does not change the plugin's package name, OCI image, or config keys. See `references/rhdh-architecture.md`.
</pitfall>

<pitfall name="showing-all-breaking-changes-equally">
Not all breaking changes matter to every customer. The key value of this skill is FILTERING — showing which changes affect THIS customer's config and which do NOT. Always include both sections.
</pitfall>

<pitfall name="negative-framing">
Frame the output positively. "Readiness Score: 85/100 — Ready with minor prep" not "Risk Score: 15 — Low Risk." The customer is preparing for an upgrade, not assessing danger.
</pitfall>

<pitfall name="internal-jargon">
This skill is customer-facing. Avoid: "Customer Focal," "RHDHSUPP," "ticket history," "correlation rules," "churn hotspots." Use: "your configuration," "your plugins," "your auth setup."
</pitfall>

<pitfall name="using-index-image-as-plugin-artifact">
**Use the Package entity's `spec.dynamicArtifact` as the artifact source of truth.** A generally available plugin may intentionally remain bundled at a local path, so do not replace it with the `registryReference` from `index.json`. A community plugin may intentionally use a GHCR tag in `spec.dynamicArtifact`, so use that exact reference instead of a registry-access image from `index.json`. For a GA `registry.access.redhat.com` artifact with a matching default OCI entry, recommend the 1.10 `:{{inherit}}` form so the default dynamic-plugin tag is inherited. The index image data is enrichment and lookup evidence, not a replacement for `spec.dynamicArtifact`. See `references/config-analysis.md` Section 1.
</pitfall>

<pitfall name="processing-secrets">
Never process literal secret values. Before analyzing any config file, scan for patterns defined in `references/secrets-detection.md`. If embedded secrets are detected, warn the user with file and line numbers and ask them to redact before continuing. Template variable references (`${VAR_NAME}`, `{{ .Values.x }}`) are NOT secrets — do not flag them. If the user chooses to continue despite warnings, replace detected secret values with `[REDACTED]` in all report output.
</pitfall>

<pitfall name="skipping-rhdh-local">
Always recommend RHDH Local for safe pre-upgrade testing. If the customer's working directory does not contain an `rhdh-local` setup, include a recommendation in the report per `references/rhdh-local.md`. RHDH Local lets customers validate their updated configuration locally with `podman compose` before deploying to a cluster.
</pitfall>

<pitfall name="findings-without-evidence">
**Never flag a finding as Critical or Important without concrete evidence from the RHDH release notes (`references/release-notes/*.md`), the shipped catalog-index metadata (or explicitly labeled overlay fallback), or Backstage changelogs.** Do not infer deprecation or breakage from naming conventions alone (e.g., "legacy" does not mean deprecated). Every Critical or Important finding must trace to a specific release notes entry or metadata change. If no evidence exists, either omit the finding or note it as Informational with an explicit caveat.
</pitfall>
</anti_patterns>

<success_criteria>
The report is complete when:

- All config files scanned for secrets per `references/secrets-detection.md` before any analysis
- Target release resolved to Backstage version via the shipped catalog-index image or explicitly labeled overlay fallback
- Customer's environment determined (from config or intake questions)
- Product context gathered for the release range
- Per-plugin bug search run against RHDHBUGS Jira (if accessible) and `redhat-developer/rhdh` GitHub Issues
- Every breaking change classified as "affects you" or "does NOT affect you" based on environment overlap
- Readiness score computed with transparent breakdown per `references/config-scoring.md`
- Migration actions are specific: file path, line number (when from config), current value, replacement, reason
- "Does NOT Affect You" section included to reduce upgrade anxiety
- RHDH Local recommended for pre-upgrade testing per `references/rhdh-local.md`
- Upgrade checklist provided at end of report
- For major version upgrades: chart values migration completed via `workflows/chart-migration.md`, all ambiguous areas resolved with user confirmation, migrated values file validated with `helm template`
</success_criteria>
