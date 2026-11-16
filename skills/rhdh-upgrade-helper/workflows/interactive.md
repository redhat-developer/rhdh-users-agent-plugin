# Workflow: Interactive Upgrade Assessment

This is the DEFAULT workflow when no `--config-path` is provided. It asks intake questions to build an environment profile, then delegates to `workflows/full-report.md` for the actual assessment.

## Step 1: Resolve Release Versions

Extract `rhdh_to` and `rhdh_from_release` from `--to`/`--from`. If neither flag is present, read only the `release` (or `to`) and `from` keys from `.rhdh-upgrade-helper.yaml` if it exists.

```bash
if [ -n "{rhdh_from_release}" ]; then
  RELEASE_CONTEXT=$(python3 "$SKILL_DIR/scripts/resolve-release.py" \
    --to "{rhdh_to}" --from "{rhdh_from_release}" --json)
else
  RELEASE_CONTEXT=$(python3 "$SKILL_DIR/scripts/resolve-release.py" \
    --to "{rhdh_to}" --json)
fi
```

Handle exit codes exactly as in `workflows/full-report.md` Step 0:

- `0` — resolved. Keep `$RELEASE_CONTEXT` for Step 4.
- `2` — unknown target. Show the `message` verbatim and halt before any intake question.
- `4` — `--from` is not older than `--to`. Show the message and halt.
- `1` — malformed or missing version. Show the message and ask again.
- `3` — `references/releases.json` is missing or invalid. Tell the user the skill install is incomplete and halt.

**Validation:** `--to` is required. If missing, ask: "What RHDH version are you upgrading to?", then rerun the resolver. The resolver accepts `X.Y` and `X.Y.Z` and normalizes both to `X.Y`.

If the source is unknown (`from.known: false`), continue and carry the resolver's `gaps` into the full report.

## Step 2: Ask Intake Questions

Follow `references/intake-questions.md` exactly. The flow prioritizes config files over manual questions:

1. Current RHDH version (skip if `--from` was provided)
2. Deployment method (Helm / Operator)
3. **Config files** — ask for file paths based on deployment method (Helm: values.yaml, app-config, dynamic-plugins; Operator: Backstage CR, app-config, dynamic-plugins)

**If config files provided:**

- Show the list of files found and their auto-detected types (Helm values, app-config, dynamic-plugins, Backstage CR)
- Ask: **"Are there additional config files in other locations? (e.g., a separate app-config or dynamic-plugins ConfigMap)"**
- If yes, collect more paths until the user says "done" or "that's all"
- If the user provided a directory path instead of individual files, scan it, show what was found, and still ask if there are more
- Once confirmed, switch to config-driven analysis. Skip Q4–Q7 — auth, SCM, plugins, and features are extracted from the files automatically. Proceed to Step 4.
- **Tip:** Suggest creating a `.rhdh-upgrade-helper.yaml` to save the file paths for future runs. See `references/rhdh-upgrade-helper-config.md`.

**If no config files ("skip") → continue with manual questions:**

4. Auth providers
5. SCM integration
6. Features in use
7. Scale / HA mode

Then proceed to Step 3 to build the environment profile.

## Step 3: Build Environment Profile (manual flow only)

Compile the answers into `$ENVIRONMENT_PROFILE` per `references/intake-questions.md`:

```json
{
  "source": "intake",
  "current_version": "{from Q1 or --from, normalized by the resolver}",
  "deployment_method": "{from Q2}",
  "auth_providers": ["{from Q4}"],
  "scm_integrations": ["{from Q5}"],
  "features": ["{from Q6}"],
  "ha_mode": "{from Q7}",
  "relevant_workspaces": ["{mapped from features}"]
}
```

## Step 4: Run Full Report

Execute `workflows/full-report.md` with:

- `rhdh_to` and `rhdh_from_release` from Step 1, updated by Q1 when the user names a different source
- `$RELEASE_CONTEXT` from Step 1, including `gaps`
- Config files from Q3 (config-driven path), OR `environment_profile` from Step 3 (manual path)

The full-report workflow handles product context gathering, correlation, scoring, and report compilation.
