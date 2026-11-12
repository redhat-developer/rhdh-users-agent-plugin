# Output Format: Customer-Facing Upgrade Report

## Report Structure

```
## Upgrade Assessment: RHDH {from_version} → {target_version}
### Generated: {date} | Backstage: {bs_from} → {bs_target} | Environment source: {Config files | Intake answers}

> **Readiness:** {score}/100 — {Ready | Ready with prep | Significant prep needed | Major migration | Extensive migration}
> **Config changes required:** {N} ({critical_count} critical, {high_count} important)
> **Estimated effort:** {effort_label}

---

### Critical: Fix Before Upgrading

These will cause failures if not addressed before the upgrade.

#### {N}. {title} — {severity_emoji}

**File:** `{file_path}:{line}` (when from config) or **Config area:** `{area}` (when from intake)
**Current:** `{current_value_or_pattern}`
**Replace with:** `{new_value_or_pattern}`
**Reason:** {why this breaks — one sentence}

---

### Important: Address After Upgrading

These won't block the upgrade but should be fixed soon after.

#### {N}. {title}

**File:** `{file_path}:{line}` or **Config area:** `{area}`
**Issue:** {what needs attention}
**Action:** {specific fix}
**Reason:** {why this matters}

---

### Informational: Review When Convenient

These are minor and won't cause issues, but are worth knowing about.

- {description} — {action if any}

---

### Does NOT Affect You

These breaking changes exist in RHDH {target_version} but do NOT apply to your configuration.

| Breaking Change | Why It Doesn't Apply |
|----------------|---------------------|
| {change description} | {reason — e.g., "You don't use the X plugin" or "Your auth config doesn't use resolver Y"} |
| ... | ... |

**{M} of {total} breaking changes in this release do not affect your setup.**

---

### Known Issues Affecting Your Plugins

Known bugs that affect plugins in your environment for the target release — both the plugins you configured and the plugins the target release pre-installs and enables by default. Sourced from internal bug tracking, public GitHub Issues, and the release notes.

| Plugin | Plugin source | Issue | Status | Impact | Workaround |
|--------|---------------|-------|--------|--------|------------|
| {plugin_name} | {Configured / Pre-installed} | {one-line summary} | {Open/Resolved} | {severity — Critical/Major/Minor} | {workaround or "None"} |

Every pre-installed plugin that ships enabled is part of your runtime and can fail without appearing in your values file. If a known issue names one of them, it belongs in this table.

When bugs are found from Jira (RHDHBUGS), describe the issue in customer-friendly language. Do NOT include internal Jira ticket URLs, ticket keys, or Slack thread links. Only include what the customer needs: what's broken, what's the impact, and how to work around it.

When bugs are found from GitHub Issues, include the link: `[#{number}]({url})`.

If no relevant issues were found, display: "No known bugs found for your plugin versions in this release." Only state this when every source was queried successfully; if a source was unavailable, say which one, so the customer does not read a partial search as a clean bill of health.

---

### What Changed in RHDH {target_version}

**Backstage:** {bs_from} → {bs_target} ({N} minor versions)
**Node.js:** {node_from} → {node_target}

#### New Features Available to You
- {feature} — {one-line description}

#### Plugin Changes in Your Config

| Plugin | From Version | To Version | Support Level | Notes |
|--------|-------------|------------|---------------|-------|
| {plugin_name} | {v_from} | {v_to} | {support} | {any notable change} |

---

### Your Environment Summary

| Dimension | Value | Source |
|-----------|-------|--------|
| Current RHDH version | {from_version} | {config / answer} |
| Deployment method | {Helm / Operator} | {config / answer} |
| Auth providers | {list} | {config / answer} |
| SCM integrations | {list} | {config / answer} |
| Total plugins | {N} configured ({M} enabled), {P} pre-installed by default | {config / answer} |
| Custom plugins | {N} (not in default packages) | {config / answer} |
| Features in use | {list} | {config / answer} |

---

### Readiness Score Breakdown

**Base:** 100 - {deductions} = {base}
**Amplifiers:** {list} → {adjusted}
**Mitigators:** {list} → {final}

**Score: {final}/100 — {label}**

---

### Pre-Upgrade Testing with RHDH Local

{Include RHDH Local recommendation per references/rhdh-local.md — detected or not-detected variant}

---

### Upgrade Checklist

Pre-upgrade:
- [ ] Apply all changes from "Critical" section above
- [ ] Test your updated configuration with RHDH Local before deploying to your cluster
- [ ] Back up your current configuration files
- [ ] Review "Important" items for post-upgrade follow-up

Upgrade:
- [ ] {deployment-method-specific command — e.g., "Run `helm upgrade ...`" or "Update the Backstage CR"}

Post-upgrade:
- [ ] Verify pods start successfully
- [ ] Verify authentication flow works (test login/logout)
- [ ] Verify {each major feature from environment} works
- [ ] Address items from "Important" section
- [ ] Review "Informational" items at your convenience
```

## Rules

- **No internal jargon.** Write for a platform team running RHDH, not a Red Hat support engineer.
- **Concrete over generic.** "Update line 42 of `dynamic-plugins.yaml`" not "Update your plugin configuration."
- **Always include "Does NOT Affect You."** Even if empty ("All breaking changes in this release apply to your setup"), this section reduces upgrade anxiety.
- **Group by action urgency**, not by data source. The customer doesn't care whether a finding came from config analysis or release notes — they care whether it blocks their upgrade.
- **Readiness score breakdown is mandatory.** Every deduction traces to a specific finding. No opaque scores.
- **Config-sourced findings include file:line.** Intake-sourced findings say "Config area:" instead.
- **Pre-installed plugins count as part of the environment.** Plugins the target release enables by default are reported in "Known Issues Affecting Your Plugins" and in the environment summary even when the customer never configured them; mark them `Pre-installed`.
- **Severity markers:** Critical = must fix before upgrade (runtime failure). Important = fix soon after (degraded experience). Informational = awareness only.
- **Effort labels:** Low (< 1 hour), Medium (1-4 hours), High (half day+), Extensive (multi-day).
- **Never echo secrets.** Replace detected secret values with `[REDACTED]` in all output. See `references/secrets-detection.md`.
