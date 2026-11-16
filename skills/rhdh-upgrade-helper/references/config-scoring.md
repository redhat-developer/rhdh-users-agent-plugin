# Readiness Scoring Model

Computes a 0-100 "Readiness Score" from config findings and product context. Higher is better: 90 = ready with minor prep, 20 = major migration required.

## Base Score

Start at 100 and subtract points for each finding category. The base score cannot go below 0.

| Category | Max Deduction | How to Compute |
|----------|---------------|----------------|
| Breaking config keys | -25 | Count evidence-backed deprecated or changed configuration items found across the customer's supplied config sources (including app-config, dynamic-plugin config, Helm values, and environment files). This includes applicable 2.1 migrations such as NFS, auth, RBAC, Scorecard, and confirmed network-policy dependencies. 1-2 items = -5, 3-5 = -10, 6-10 = -15, 11+ = -25. |
| Artifact-source migrations | -25 | Count configured plugin references whose source type (local, OCI, or NPM) differs from the target Package entity's `spec.dynamicArtifact`, plus unresolved references. Do not count a local path whose target `spec.dynamicArtifact` is the same bundled local path, or an OCI tag that only needs a version update. 1-2 = -10, 3-5 = -15, 6+ = -25. |
| Backstage version jump | -15 | Use `backstage_minor_jump` from `$RELEASE_CONTEXT` (resolved in Step 0). 0-1 = 0, 2-3 = -5, 4-5 = -10, 6+ = -15. |
| Node.js version jump | -10 | Use `node_major_jump` from `$RELEASE_CONTEXT`. Same major = 0, +1 major = -5, +2 major = -10. |
| Auth provider compatibility | -15 | Auth resolver changes between releases that affect the customer's configured providers. Each affected provider = -5, capped at -15. |
| Custom plugins | -10 | Plugins in customer's config NOT in target release's `default.packages.yaml`. 1-2 = -3, 3-5 = -5, 6+ = -10. These need manual version compatibility checks. |
| Chart value key migrations | -20 | Major version upgrade only. Count of ambiguous areas in the user's config that required AI-assisted resolution. 0 = 0, 1-2 = -5, 3-4 = -10, 5+ = -20. |
| Major chart restructuring | -15 | Apply only when the customer is migrating Helm values from the 1.y chart structure to 2.y. Do not apply this chart-only penalty to Operator or RHDH Local deployments; score their observed product configuration and artifact findings under the applicable existing categories. |

Count each distinct finding once, under its most specific category: auth-provider findings use Auth provider compatibility, and plugin artifact transitions use Artifact-source migrations rather than Breaking config keys. Do not deduct for Informational deprecations.

**Formula:** `base = max(0, 100 - sum(deductions))`

## Not assessed inputs

A category is **Not assessed** when its input is unavailable. This happens for these items when the source release is outside the bundled manifest (`$RELEASE_CONTEXT.from.known` is `false`):

- Backstage version jump
- Node.js version jump
- Plugin removed from release
- Large plugin version jump
- Support level downgrade
- The Single-version upgrade mitigator (do not award it)

An unassessed item contributes 0 and must not be described as a 0 deduction or as a clean result. Show it in the breakdown as:

```
Not assessed — {category}: {reason}
```

and add this line immediately after the readiness one-liner:

```
> **Provisional:** {N} scoring categories were not assessed; the score excludes them.
```

Do not lower the maximum score or rescale the result. Keep the 0-100 scale comparable, but make the omission visible.

## Amplifiers

Amplifiers reduce the base score further. Each amplifier applies a percentage reduction to the REMAINING score above 0.

| Amplifier | Reduction | Trigger |
|-----------|-----------|---------|
| Plugin removed from release | -25% each | A plugin the customer has configured exists in `--from` release but NOT in `--to` `default.packages.yaml`. This is a hard break. |
| Deprecated auth resolver | -20% | Customer's auth config uses a resolver name deprecated between releases. Login may fail after upgrade. |
| Large plugin version jump | -15% each | A configured plugin has 3+ minor version jump between releases. Higher chance of breaking API changes. Max 2 plugins counted. |
| Support level downgrade | -10% each | A configured plugin's support level dropped (e.g., `generally-available` → `tech-preview` or `community`). |
| Removed chart values | -15% each | A Helm customer uses a chart value with no 2.y equivalent (`installDir`, `containerPorts.backend`, `diagnosticMode`). Do not apply to non-Helm deployments. |

**Formula:** `amplifier_penalty = base * (1 - 1/(1 + sum(amplifier_rates)))`

This uses diminishing returns — multiple amplifiers compound but never reduce the score to 0 from amplifiers alone.

**Score after amplifiers:** `adjusted = base - amplifier_penalty`

## Mitigators

Mitigators add points back to the adjusted score. Each mitigator adds a flat bonus, capped at `100 - adjusted`.

| Mitigator | Bonus | Trigger |
|-----------|-------|---------|
| Single-version upgrade | +10 | `--from` is the previous entry in `references/releases.json` for `--to` (no skipped releases). Do not award when the source is unknown. |
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

Every deduction must trace to a specific finding from the config analysis or product context. Informational deprecations, including the RHDH 2.1 `disabled`→`enabled` notice, do not incur deductions. No opaque scores.
