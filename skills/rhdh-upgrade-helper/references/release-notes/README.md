# Release notes

One text file per RHDH release, extracted from the official Red Hat documentation.

These are maintainer-managed files. Users of the skill do not need any tools to use them. The skill reads local files only.

## File naming

`{major}.{minor}.md`, for example `1.9.md` or `1.10.md`.

## How to add a new release

Add the release to `../releases.json` first, in ascending order, with its upstream Backstage version and Node.js major version. Then add `{major}.{minor}.md` here. The resolver (`scripts/resolve-release.py`) and its tests read the manifest: a release note without a manifest entry is invisible to the skill, and a manifest entry without a note fails the test suite.

Pick whichever method works for you. For RHDH 2.1, use the `whats_new` release-notes page linked in `2.1.md`; the older `html-single` URL pattern is not used for 2.1.

### Option A: lynx and Claude (recommended)

```bash
# Install lynx (one-time): brew install lynx / dnf install lynx / apt install lynx
lynx -dump -nolist \
  "https://docs.redhat.com/en/documentation/red_hat_developer_hub/{X.Y}/html-single/red_hat_developer_hub_release_notes/index" \
  > raw.txt
```

Then ask Claude to convert it:

```
Convert raw.txt to a release notes markdown file matching the format in
skills/rhdh-upgrade-helper/references/release-notes/1.10.md
```

Claude strips the navigation boilerplate and structures it into the required sections.

### Option B: paste from browser and Claude

Open the single-page release notes URL in your browser, select all, copy, and paste into `raw.txt`. Then ask Claude to convert it as above.

### Option C: PDF and Claude

Download the PDF from docs.redhat.com and convert with `pdftotext -layout file.pdf raw.txt`. Then ask Claude to convert it as above.

### Required sections

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

`workflows/full-report.md` Step 4c reads the release notes files listed in `$RELEASE_CONTEXT.release_range`, which comes from `../releases.json`. For example, `--from 1.8 --to 1.10` reads `1.9.md` and `1.10.md` to gather all breaking changes and new features across the skipped releases. The existing skip-version behavior is unchanged for a 2.1 target; review the skip-path assumption in `../migration-2.1.md` with the team.

A target version outside the manifest halts before intake (see `workflows/full-report.md` Step 0). If a file is missing for a manifest version, the report treats it as an incomplete skill install, attempts a `lynx` fetch, and otherwise points users to reinstall the skill.
