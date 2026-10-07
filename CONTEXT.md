# RHDH Users Agent Plugin

User-facing portable Agent Plugin of Skills for adopting and operating Red Hat Developer Hub (RHDH).

## Language

**RHDH Users Agent Plugin**:
The human product name for this Plugin.
_Avoid_: RHDH Users Skill Pack, skill pack, RHDH Users Plugin (without Agent)

**Plugin name**:
The machine identifier used consistently for `plugin.json` `name`, pyproject project name, and the GitHub repository slug: `rhdh-users-agent-plugin`.
_Avoid_: rhdh-users-skill-pack, rhdh-users-plugin, rhdh-users

**Repository name**:
Same as the Plugin name: `redhat-developer/rhdh-users-agent-plugin` after rename.
_Avoid_: rhdh-users-skill-pack (post-rename)

**Plugin**:
The Agent Plugins package unit: a directory with a root `plugin.json` and optional components under fixed locations.
_Avoid_: Skill pack, pack (as the product unit)

**Plugin root**:
The filesystem root of the Plugin. In this repository, the git repository root is the Plugin root.
_Avoid_: Package root (when referring to Agent Plugins discovery), nested plugin directory

**Skill**:
An Agent Skill discovered as an immediate child of `skills/` that contains a `SKILL.md`.
_Avoid_: Plugin (for an individual skill), command, workflow (as the package unit)

**Component**:
A skill or MCP server entry supplied through an Agent Plugins component type.
_Avoid_: Feature, module (when referring to plugin-discoverable units)

**Client**:
A tool that discovers, installs, loads, and executes Plugin components (for example Cursor).
_Avoid_: Agent (when referring to the installer/loader), IDE (when the distinction matters)

**Skills installer**:
The `npx skills` distribution path that copies Skills into agent-specific skill directories. Kept as an additive install path alongside Agent Plugins–aware Clients.
_Avoid_: Agent Plugins installer (for `npx skills`), plugin install (when meaning `npx skills`)

**Repository rename**:
This effort renames the GitHub repository and project identifiers away from `rhdh-users-skill-pack` to match the Plugin name, after the conformance PR merges.
_Avoid_: Leaving skill-pack only in docs while renaming the plugin (partial rename)

**Plugin description**:
Portable Agent Plugin with skills for adopting and operating Red Hat Developer Hub.
_Avoid_: Agent Skills pack for Red Hat Developer Hub users (as the plugin description)

**Plugin homepage**:
The GitHub repository URL for this Plugin (post-rename README).
_Avoid_: RHDH product docs URL (that belongs on author.url)
