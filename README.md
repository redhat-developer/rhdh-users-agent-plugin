# RHDH Users Agent Plugin

Portable [Agent Plugin](https://agent-plugins.org/) with [Agent Skills](https://agentskills.io/specification) for adopting and using [Red Hat Developer Hub](https://developers.redhat.com/products/rhdh/overview) (RHDH).

Formerly published as **RHDH Users Skill Pack**.

> [!CAUTION]
>
> There is no official, commercial support for RHDH Users Agent Plugin. Use RHDH Users Agent Plugin at your own risk.

## Included skills

| Skill | Use when you want to |
| ----- | -------------------- |
| [rhdh-templates](./skills/rhdh-templates/SKILL.md) | Author and validate Software Templates with guided workflows |
| [rhdh-upgrade-helper](./skills/rhdh-upgrade-helper/SKILL.md) | Prepare for an RHDH upgrade with OCI checks, Jira bug search, and a Readiness Score |
| [skill-maker](./skills/skill-maker/SKILL.md) | Create, audit, and consolidate Agent Skills |

## rhdh-upgrade-helper

Analyzes your RHDH configuration against a target release and produces a personalized migration plan. The report shows what affects your setup and what does not. The skill works with Helm, Operator, and rhdh-local deployments.

See [rhdh-upgrade-helper](./skills/rhdh-upgrade-helper/SKILL.md) for the full skill definition. The skill:

- resolves OCI references for every plugin via `rhdh-plugin-export-overlays` workspace metadata.
- validates existing OCI plugin tags against the target release.
- searches the RHDHBUGS Jira project per plugin for known bugs affecting your versions.
- filters breaking changes into "Affects You" and "Does NOT Affect You" based on your config.
- computes a 0–100 Readiness Score with a transparent breakdown.

Bundled release notes cover RHDH 1.4–1.10.

Workflows:

- [full-report](./skills/rhdh-upgrade-helper/workflows/full-report.md): generate a complete upgrade report from config files or a `.rhdh-upgrade-helper.yaml`.
- [interactive](./skills/rhdh-upgrade-helper/workflows/interactive.md): guided assessment when no config files are available.
- [help](./skills/rhdh-upgrade-helper/workflows/help.md): show usage, arguments, and examples.

Example prompts:

- "Analyze my values.yaml for upgrading from RHDH 1.8 to 1.10"
- "What breaks if I upgrade to RHDH 1.10?"
- "Run an upgrade assessment on my rhdh-local project"

## rhdh-templates

Interactive authoring for RHDH Scaffolder templates. You can templatize an existing repo, create from scratch, fix common gotchas, and validate locally or against a running instance.

See [rhdh-templates](./skills/rhdh-templates/SKILL.md) for the full skill definition. The skill includes a curated reference catalog (official library and AI quickstarts), worked examples (`nodejs-backend`, `java-springboot`), and bundled JSON Schema validation.

Sub-commands:

- [init](./skills/rhdh-templates/references/init.md): check tooling, scaffold template repo layout, optional RHDH connectivity.
- [templatize](./skills/rhdh-templates/references/templatize.md): convert an existing codebase into a parameterized template.
- [create](./skills/rhdh-templates/references/create.md): guided from-scratch template authoring when no reference code exists.
- [add-parameter](./skills/rhdh-templates/references/add-parameter.md): add a parameter or parameter group to existing `template.yaml`.
- [add-step](./skills/rhdh-templates/references/add-step.md): add a scaffolder step to existing `template.yaml`.
- [add-skeleton](./skills/rhdh-templates/references/add-skeleton.md): add or parameterize skeleton files with Nunjucks.
- [create-location](./skills/rhdh-templates/references/create-location.md): generate or update root `location.yaml` for catalog registration.
- [fix-gotchas](./skills/rhdh-templates/references/fix-gotchas.md): auto-fix common RHDH template mistakes (raw/endraw blocks, catalog-info path, and similar).
- [validate](./skills/rhdh-templates/references/validate.md): local YAML schema, gotcha validation, and optional Nunjucks lint via `--lint-skeleton` (no RHDH required).
- [list-actions](./skills/rhdh-templates/references/list-actions.md): list available Scaffolder actions from a running RHDH instance.
- [dry-run](./skills/rhdh-templates/references/dry-run.md): test template execution via Scaffolder v2 dry-run API.
- [explain-action](./skills/rhdh-templates/references/explain-action.md): show action input schema or template parameter schema.
- [example-catalog](./skills/rhdh-templates/references/example-catalog.md): browse curated reference templates (official library, AI quickstarts, bundled).

Example prompts:

- "Help me turn this Node.js repo into an RHDH Software Template"
- "Validate my `template.yaml` and fix Scaffolder gotchas"
- "List scaffolder actions available on my RHDH instance"

## skill-maker

Create, audit, or consolidate [Agent Skills](https://agentskills.io/specification). Use this skill when you package your own RHDH workflows or contribute skills to this Plugin.

See [skill-maker](./skills/skill-maker/SKILL.md) for the full skill definition. Capabilities:

- Create: guided interview and drafting of a new skill from scratch.
- Audit: review, improve, or debug an existing SKILL.md (trigger issues, structure, description).
- [Consolidate](./skills/skill-maker/references/consolidation-guide.md): merge multiple skills into fewer using router patterns.

Example prompts:

- "Help me create a skill for our team's RHDH onboarding workflow"
- "Audit this SKILL.md. It never triggers when I expect it to."
- "Merge these two skills into one router skill"

## Installation

This repository is an [Agent Plugin](https://agent-plugins.org/) (`plugin.json` at the repository root). You can install its Skills with the Skills installer, or load the Plugin in a Plugin-aware Client.

### Skills installer

Works with [50+ coding agents](https://github.com/vercel-labs/skills#supported-agents):

```bash
npx skills add redhat-developer/rhdh-users-agent-plugin
```

Install one skill only:

```bash
npx skills add redhat-developer/rhdh-users-agent-plugin --skill rhdh-templates
npx skills add redhat-developer/rhdh-users-agent-plugin --skill skill-maker
```

List skills without installing:

```bash
npx skills add redhat-developer/rhdh-users-agent-plugin --list
```

Target a specific agent:

```bash
npx skills add redhat-developer/rhdh-users-agent-plugin -a claude-code
npx skills add redhat-developer/rhdh-users-agent-plugin -a cursor
```

Local checkout for development:

```bash
git clone https://github.com/redhat-developer/rhdh-users-agent-plugin.git
npx skills add ./rhdh-users-agent-plugin
```

### Agent Plugins clients

Plugin-aware Clients discover this package from root `plugin.json` and the `skills/` directory. Install or enable the Plugin through your Client’s Plugin UI or marketplace when listed.

For local development in Cursor, copy or place this repository under `~/.cursor/plugins/local/rhdh-users-agent-plugin`, then reload the window and confirm the Skills under Customize. Other Clients use their own local-folder or marketplace install flow; see [agent-plugins.org](https://agent-plugins.org/) and your Client’s docs.

## How to use

1. Install the Plugin or its Skills (see above).
2. Open your project in an agent-enabled editor or CLI.
3. Describe your goal in plain language. For example: "help me turn this repo into an RHDH Software Template."

You can also name the skill explicitly:

```
Use the rhdh-templates skill to validate my template.yaml
Use the skill-maker skill to audit my SKILL.md
```

## Frequently asked questions

### What is an Agent Plugin?

A directory with a root `plugin.json` and optional components in fixed locations (Skills under `skills/`, optional MCP config). See the [Agent Plugins specification](https://agent-plugins.org/).

### What is an Agent Skill?

A folder with a `SKILL.md` file (YAML front matter and instructions) that agents load when relevant. See the [Agent Skills specification](https://agentskills.io/specification).

### How is this different from `redhat-developer/rhdh-skill`?

This repository is the user-facing Agent Plugin. Its skills help users adopt and operate RHDH. The [`rhdh-skill`](https://github.com/redhat-developer/rhdh-skill) repository adds skills for the RHDH engineering team (Jira, release management, Extensions Catalog, lifecycle checks, CI tooling). Most RHDH users do not need those skills.

### Can I contribute a new skill?

Yes. See [CONTRIBUTING.md](./CONTRIBUTING.md). Proposed skills should help RHDH users adopt or operate the platform and follow the Agent Skills open standard. Use `skill-maker` to draft and review new skills before opening a PR.

### Where do I get help?

- RHDH product documentation: [Red Hat Developer Hub](https://docs.redhat.com/en/documentation/red_hat_developer_hub)
- Issues and feature requests: [JIRA (RHIDP)](https://issues.redhat.com/browse/RHIDP)

## Development

For contributors validating changes locally:

```bash
git clone https://github.com/redhat-developer/rhdh-users-agent-plugin.git
cd rhdh-users-agent-plugin
uv sync --extra dev
git config core.hooksPath .githooks
uv run pytest
```

See [CONTRIBUTING.md](./CONTRIBUTING.md) and [AGENTS.md](./AGENTS.md) for contribution guidelines.

## License

Apache-2.0. See [LICENSE](./LICENSE).
