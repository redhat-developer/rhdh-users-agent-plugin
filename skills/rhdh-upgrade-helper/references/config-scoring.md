# Readiness Scoring Model

Computes a 0-100 "Readiness Score" from config findings and product context. Higher is better: 90 = ready with minor prep, 20 = major migration required.

## Base Score

Start at 100 and subtract points for each finding category. The base score cannot go below 0.

| Category | Max Deduction | How to Compute |
|----------|---------------|----------------|
| Breaking config keys | -25 | Count deprecated/removed config keys found in customer's `app-config.yaml`. 1-2 keys = -5, 3-5 = -10, 6-10 = -15, 11+ = -25. |
| Artifact-source migrations | -25 | Count configured plugin references whose source type (local, OCI, or NPM) differs from the target Package entity's `spec.dynamicArtifact`, plus unresolved references. Do not count a local path whose target `spec.dynamicArtifact` is the same bundled local path, or an OCI tag that only needs a version update. 1-2 = -10, 3-5 = -15, 6+ = -25. |
| Backstage version jump | -15 | Minor versions between `--from` and `--to` Backstage versions. 0-1 = 0, 2-3 = -5, 4-5 = -10, 6+ = -15. |
| Node.js version jump | -10 | Compare Node.js major versions. Same major = 0, +1 major = -5, +2 major = -10. |
| Auth provider compatibility | -15 | Auth resolver changes between releases that affect the customer's configured providers. Each affected provider = -5, capped at -15. |
| Custom plugins | -10 | Plugins in customer's config NOT in target release's `default.packages.yaml`. 1-2 = -3, 3-5 = -5, 6+ = -10. These need manual version compatibility checks. |
| Chart value key migrations | -20 | Major version upgrade only. Count of ambiguous areas in the user's config that required AI-assisted resolution. 0 = 0, 1-2 = -5, 3-4 = -10, 5+ = -20. |
| Major chart restructuring | -15 | Flat penalty when the RHDH major version differs (values structure changed from nested subchart layout to flat root-level keys). |

**Formula:** `base = max(0, 100 - sum(deductions))`

## Amplifiers

Amplifiers reduce the base score further. Each amplifier applies a percentage reduction to the REMAINING score above 0.

| Amplifier | Reduction | Trigger |
|-----------|-----------|---------|
| Plugin removed from release | -25% each | A plugin the customer has configured exists in `--from` release but NOT in `--to` `default.packages.yaml`. This is a hard break. |
| Deprecated auth resolver | -20% | Customer's auth config uses a resolver name deprecated between releases. Login may fail after upgrade. |
| Large plugin version jump | -15% each | A configured plugin has 3+ minor version jump between releases. Higher chance of breaking API changes. Max 2 plugins counted. |
| Support level downgrade | -10% each | A configured plugin's support level dropped (e.g., `generally-available` → `tech-preview` or `community`). |
| Removed chart values | -15% each | A chart value the customer uses has no 2.x equivalent (`installDir`, `containerPorts.backend`, `diagnosticMode`). |

**Formula:** `amplifier_penalty = base * (1 - 1/(1 + sum(amplifier_rates)))`

This uses diminishing returns — multiple amplifiers compound but never reduce the score to 0 from amplifiers alone.

**Score after amplifiers:** `adjusted = base - amplifier_penalty`

## Mitigators

Mitigators add points back to the adjusted score. Each mitigator adds a flat bonus, capped at `100 - adjusted`.

| Mitigator | Bonus | Trigger |
|-----------|-------|---------|
| Single-version upgrade | +10 | `--from` is the release immediately before `--to` (no skipped releases). |
| All plugins exist in target | +10 | Every plugin in customer's config exists in the target release's `default.packages.yaml`. |
| No artifact-source migration needed | +10 | Zero configured plugins require a local/OCI/NPM source-type transition according to target `spec.dynamicArtifact`. A valid bundled local path does not prevent this mitigator. |
| Deterministic chart migration | +15 | Major version upgrade only. The migration script exited 0 — all chart value mappings were mechanical with no ambiguous areas. |

**Formula:** `final = min(100, adjusted + sum(mitigator_bonuses))`

## Readiness Thresholds

| Score | Label | Meaning |
|-------|-------|---------|
| 90-100 | Ready | Straightforward upgrade. Minor or no config changes needed. |
| 70-89 | Ready with prep | A few config changes required. Plan 1-2 hours. |
| 50-69 | Significant prep needed | Multiple changes across config files. Plan a half-day. |
| 25-49 | Major migration | Substantial config rework. Plan a full day with testing. |
| 0-24 | Extensive migration | Many breaking changes affect your setup. Plan multi-day with staged rollout. |

## Display

Show the score as a one-liner in the report header:

```
> **Readiness:** {score}/100 — {label}
```

In the report body, include the full breakdown:

```
### Readiness Score Breakdown

**Base:** 100 - {deductions summary} = {base}
**Amplifiers:** {list each with rate} → {adjusted}
**Mitigators:** {list each with bonus} → {final}

**Score: {final}/100 — {label}**
```

Every deduction must trace to a specific finding from the config analysis or product context. No opaque scores.
