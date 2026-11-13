# Release notes

One file per RHDH release, generated from the official Red Hat documentation.

These are maintainer-managed files. Users of the skill do not need any tools to use them. The skill reads local files only.

## File naming

`{major}.{minor}.md`, for example `2.1.md`.

## How files are produced

`scripts/generate-release-notes.py` fetches the published release-notes pages and writes the bundled markdown. It reads the release-notes landing page, follows every section link, and emits the eight required sections, so a new release or a renamed section needs no code change. The same run updates `../releases.json` for the releases it generates; the resolver (`scripts/resolve-release.py`) and its tests read that manifest, so a release note without a manifest entry is invisible to the skill.

```bash
uv sync --extra release-notes
uv run python skills/rhdh-upgrade-helper/scripts/generate-release-notes.py --release 2.1
uv run python skills/rhdh-upgrade-helper/scripts/generate-release-notes.py --all
uv run python skills/rhdh-upgrade-helper/scripts/generate-release-notes.py --all --check
```

`.github/workflows/release-notes.yml` runs `--all` every Monday and opens a PR when the official notes change. Review the diff and merge; do not edit generated files by hand.

### Why the extra dependency

`docs.redhat.com` returns HTTP 403 to `lynx`, `curl`, and headless browsers. The generator uses `curl_cffi` Chrome TLS impersonation, which is why it lives behind the optional `release-notes` extra instead of the stdlib-only default install. If the fetch starts failing, the scheduled workflow fails loudly and the bundled files stay usable.

## Legacy releases

`1.4`–`1.10` were hand-curated from the single-page documentation and are intentionally frozen; that layout parses differently. Keep them as-is unless a correctness fix is needed.

## Manual fallback

If automation is unavailable, open the release-notes page in a browser, copy the section text into a scratch file, and ask an agent to convert it into the format of an existing file. Keep the section headings below exactly.

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

`workflows/full-report.md` Step 4c reads the release notes files listed in `$RELEASE_CONTEXT.release_range`, which comes from `../releases.json`. For example, `--from 1.8 --to 1.10` reads `1.9.md` and `1.10.md` to gather all breaking changes and new features across the skipped releases. Step 4.5c also maps each "Known issues" entry onto the customer's configured and pre-installed plugins. The existing skip-version behavior is unchanged for a 2.1 target; review the skip-path assumption in `../migration-2.1.md` with the team.

A target version outside the manifest halts before intake (see `workflows/full-report.md` Step 0). If a file is missing for a manifest version, the report runs the generator for 2.x or attempts a `lynx` fetch for 1.x, and otherwise points users to reinstall the skill.
