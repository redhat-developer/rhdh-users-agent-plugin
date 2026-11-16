# Interactive Environment Questionnaire

When no config files are provided, ask these questions to build an `$ENVIRONMENT_PROFILE`. The flow prioritizes getting config files (which give the most precise analysis) and only falls back to manual feature questions when files aren't available.

## Questions

Ask in this order. Config files are asked EARLY because they provide auth, SCM, plugins, and features automatically — making most manual questions unnecessary.

### Q1: Current Version (required)

> What version of RHDH are you currently running?

Map to: `environment.current_version`. If they say "1.8" and `--to` is `1.10`, this means a skip-release upgrade — flag it.

If `--from` was already provided in arguments, skip this question and use that value. If the answer differs from the resolved source, rerun the resolver from `workflows/interactive.md` Step 1 with `--from {answer}`. It accepts `X.Y` and `X.Y.Z`.

If the answer names a release outside the bundled range, continue with `from.known: false`. The full report marks version-jump and FROM-dependent checks "Not assessed"; it does not halt.

### Q2: Deployment Method (required)

> How is RHDH deployed in your environment?
>
> 1. Helm Chart
> 2. Operator (Backstage CR)
> 3. Not sure

Map to: `environment.deployment_method` (`helm` | `operator` | `unknown`). Determines which config files to ask for next.

### Q3: Config Files (ask based on deployment method)

**If Helm (Q2 = Helm Chart):**

> Do you have access to your RHDH configuration files? Providing them gives the most precise migration guidance with line-level instructions.
>
> Typical Helm files:
>
> - `values.yaml` (your Helm values — most important)
> - `app-config.yaml` (if you have a separate app-config ConfigMap)
> - `dynamic-plugins.yaml` (if you have a separate dynamic plugins ConfigMap)
>
> Provide a file path, or "skip" to continue without files:

**If Operator (Q2 = Operator):**

> Do you have access to your RHDH configuration files? Providing them gives the most precise migration guidance with line-level instructions.
>
> Typical Operator files:
>
> - Backstage CR YAML (your Custom Resource definition)
> - `app-config.yaml` (from your app-config ConfigMap)
> - `dynamic-plugins.yaml` (from your dynamic-plugins ConfigMap)
>
> Provide a file path, or "skip" to continue without files:

Accept files one at a time until the user says "done", "skip", or "that's all". For each file:

- Read it and apply secrets detection (`references/secrets-detection.md`)
- Auto-detect the file type from content (`references/config-analysis.md`)

Map to: `environment.config_files` (array of file paths).

**If files were provided → skip Q4–Q7.** The config files contain auth providers, SCM integrations, plugins, and features. Run config-driven analysis instead of asking manually.

**If no files ("skip") → continue to Q4–Q7** for manual environment profiling.

### Q4: Auth Providers (only if no config files)

> What authentication provider(s) do you use? (select all that apply)
>
> 1. GitHub / GitHub Enterprise OAuth
> 2. GitLab
> 3. Microsoft Entra ID (Azure AD)
> 4. Keycloak / Red Hat SSO
> 5. Generic OIDC
> 6. SAML
> 7. Other
> 8. Not sure

Map to: `environment.auth_providers` (array of strings).

### Q5: SCM Integration (only if no config files)

> What source code management system does RHDH integrate with?
>
> 1. GitHub / GitHub Enterprise
> 2. GitLab
> 3. Bitbucket
> 4. Azure DevOps
> 5. Multiple (list them)

Map to: `environment.scm_integrations` (array of strings).

### Q6: Features in Use (only if no config files)

> Which of these RHDH features do you use? (select all that apply)
>
> 1. Orchestrator (serverless workflows)
> 2. Intelligent Assistant (formerly Developer Lightspeed)
> 3. RBAC (role-based access control)
> 4. TechDocs
> 5. Bulk Import
> 6. Kubernetes / Topology
> 7. Notifications
> 8. Software Templates (Scaffolder)
> 9. Other (please list)

Map to: `environment.features` (array of strings). Each feature maps to specific workspaces in the overlay repo for scoped product context analysis.

### Q7: Scale / HA (only if no config files)

> Is your RHDH deployment single-pod or multi-pod (high availability)?
>
> 1. Single pod
> 2. Multi-pod / HA
> 3. Not sure

Map to: `environment.ha_mode` (`single` | `multi` | `unknown`).

## Feature-to-Workspace Mapping

Use this to scope the product context query to relevant workspaces:

| Feature (from Q6) | Overlay Workspace(s) |
|-------------------|---------------------|
| Orchestrator | `orchestrator` |
| Intelligent Assistant / Developer Lightspeed | `lightspeed` (verify target-release metadata for the configured plugins) |
| RBAC | `rbac` |
| TechDocs | `backstage` (techdocs plugins) |
| Bulk Import | `bulk-import` |
| Kubernetes / Topology | `topology`, `backstage` (kubernetes plugins) |
| Notifications | `backstage` (notifications plugins) |
| Software Templates | `backstage` (scaffolder plugins) |

## Output Structure

Compile answers into `$ENVIRONMENT_PROFILE`:

```json
{
  "source": "intake",
  "current_version": "1.8",
  "deployment_method": "helm",
  "auth_providers": ["microsoft"],
  "custom_plugin_count": 3,
  "scm_integrations": ["gitlab"],
  "features": ["orchestrator", "rbac", "techdocs"],
  "ha_mode": "single",
  "relevant_workspaces": ["orchestrator", "rbac", "backstage"],
  "config_files": ["./values.yaml", "./app-config-custom.yaml"]
}
```

This structure is compatible with `$CONFIG_ANALYSIS.environment` — the full-report workflow treats both sources identically for correlation and scoring. The difference: intake-sourced findings say "Config area:" instead of "File: path:line" in the report output.
