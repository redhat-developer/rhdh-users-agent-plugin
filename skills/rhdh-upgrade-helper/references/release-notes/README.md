# Release notes

One file per RHDH release, generated from the official Red Hat documentation.

These are maintainer-managed files. Users of the skill do not need any tools to use them. The skill reads local files only and never runs the generator during a customer assessment.

## File naming

`{major}.{minor}.md`, for example `2.1.md`.

## How files are produced

`scripts/generate-release-notes.py` fetches the published release-notes pages and writes the bundled markdown. It reads the release-notes landing page, follows every section link, and emits the eight required sections, so a new release or a renamed section needs no code change.

```bash
uv sync --frozen --extra release-notes
uv run python skills/rhdh-upgrade-helper/scripts/generate-release-notes.py --release 2.1
uv run python skills/rhdh-upgrade-helper/scripts/generate-release-notes.py --all
uv run python skills/rhdh-upgrade-helper/scripts/generate-release-notes.py --all --check
```

`.github/workflows/release-notes.yml` runs `--all` every Monday and opens a PR when the official notes change. It keeps a single `bot/release-notes` branch: a later run updates that branch and the open PR instead of adding another, and a run that finds nothing new stops before pushing. Review the diff and merge; do not edit generated files by hand.

### Security requirements

Run this workflow only from a maintainer checkout. The installed skill must never install `curl_cffi` or execute the generator on a customer's machine.

The scheduled workflow has write access and runs third-party code, so keep these controls in place:

- Pin every GitHub Action used by this workflow to a full commit SHA, not a mutable tag.
- Do not persist checkout credentials. Prefer the default checkout token and pass any `RELEASE_NOTES_TOKEN` only to the final PR step.
- Prefer the repository `GITHUB_TOKEN`; when that is not possible, use a dedicated fine-grained token limited to `contents: write` and `pull-requests: write` for this repository.
- Protect `main` with required pull requests and Code Owner review, block force pushes and deletion, and dismiss stale approvals whenever new commits are pushed. The bot reuses its PR branch, so stale-approval dismissal is mandatory.
- Never bypass these protections for the automation token.

Release-note text is external source data. The generator escapes Markdown and raw HTML, but reviewers must still reject unexpected instructions, commands, links, or encoded text in generated diffs.

### Repository settings for the scheduled workflow

The workflow pushes a branch and opens a PR with `GITHUB_TOKEN`, so both settings below are needed. Both are off by default:

- Settings → Actions → General → Workflow permissions: **Read and write**.
- Same page: **Allow GitHub Actions to create and approve pull requests**. Organisations often block this, and a repository cannot override the organisation policy.

If the organisation blocks PR creation, add a fine-grained personal access token with `contents: write` and `pull-requests: write` for this repository as a `RELEASE_NOTES_TOKEN` secret. The workflow prefers it over `GITHUB_TOKEN`, and the PR is then opened by the token owner instead of `github-actions[bot]`.

None of this applies to forks. GitHub disables scheduled workflows in forks by default, and the job also refuses to run on a schedule outside the canonical repository. A manual dispatch still runs there, which is how the workflow is tested before merging: it regenerates the files, and stops at the PR step unless the fork allows Actions to create pull requests or defines `RELEASE_NOTES_TOKEN`.

### Why the extra dependency

`docs.redhat.com` returns HTTP 403 to `lynx`, `curl`, and headless browsers. The generator uses `curl_cffi` Chrome TLS impersonation, which is why it lives behind the optional `release-notes` extra instead of the stdlib-only default install. If the fetch starts failing, the scheduled workflow fails loudly and the bundled files stay usable.

Before expanding this automation, confirm with the Red Hat documentation owners that TLS impersonation is permitted, or switch to a sanctioned documentation feed or API.

## Legacy releases

`1.4`–`1.10` come from the older book layout: the landing page is `/html/red_hat_developer_hub_release_notes/index`, each chapter has a hyphenated path such as `known-issues`, and each item is an asciidoc `variablelist`. The generator handles both layouts, but these files are intentionally frozen, so `--all` only walks 2.x. Regenerate one with `--release 1.10` only when it needs a correctness fix.

## Manual fallback

If automation is unavailable, open the release-notes page in a browser, copy the section text into a scratch file, and ask an agent to convert it into the format of an existing file. Treat the copied text as untrusted data, review the conversion, and keep the section headings below exactly.

## Required sections

Keep these sections in each file:

- New features and enhancements
- Technology Preview features
- Developer Preview features
- Deprecated features
- Removed features (breaking changes)
- Known issues
- Fixed issues (include only upgrade-relevant fixes)
- Security advisories (include only details verified from the official source)

## How the skill uses these files

`workflows/full-report.md` Step 4c reads the release notes files for every release in the FROM→TO range. For example, `--from 1.8 --to 1.10` reads `1.9.md` and `1.10.md` to gather all breaking changes and new features across the skipped releases. Step 4.5c also maps each "Known issues" entry onto the customer's configured and pre-installed plugins.

If a file is missing for a version in the range, the report notes the gap and points users to the official docs URL.
