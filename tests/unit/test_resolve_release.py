"""Tests for bundled release resolution and manifest consistency."""

import json
import re
import runpy
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[2]
SKILL = ROOT / "skills" / "rhdh-upgrade-helper"
SCRIPT = SKILL / "scripts" / "resolve-release.py"
MANIFEST = SKILL / "references" / "releases.json"
NOTES_DIR = SKILL / "references" / "release-notes"


def run_resolver(*args: str) -> subprocess.CompletedProcess:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.stdout or result.stderr
    return result


def run_json(*args: str) -> tuple[int, dict]:
    result = run_resolver(*args, "--json")
    return result.returncode, json.loads(result.stdout)


def manifest_versions() -> list[str]:
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    return [release["version"] for release in data["releases"]]


def version_key(value: str) -> tuple[int, int]:
    major, minor = value.split(".")
    return int(major), int(minor)


def test_known_target_computes_jumps_and_default_source():
    code, data = run_json("--to", "2.1")

    assert code == 0
    assert data["to"]["version"] == "2.1"
    assert data["to"]["backstage"] == "1.54.9"
    assert data["to"]["node_major"] == 24
    assert data["to"]["chart_migration"] is True
    assert data["to"]["migration_reference"] == "references/migration-2.1.md"
    assert data["from"]["version"] == "1.10"
    assert data["default_from"] is True
    assert data["backstage_minor_jump"] == 5
    assert data["node_major_jump"] == 0
    assert data["is_major_upgrade"] is True
    assert data["release_range"] == ["2.1"]
    assert data["gaps"] == []


def test_patch_versions_are_normalized_but_preserved_for_display():
    code, data = run_json("--to", "1.10.4", "--from", "1.8.2")

    assert code == 0
    assert data["to"]["version"] == "1.10"
    assert data["to"]["requested"] == "1.10.4"
    assert data["from"]["version"] == "1.8"
    assert data["from"]["requested"] == "1.8.2"
    assert data["backstage_minor_jump"] == 7
    assert data["node_major_jump"] == 2
    assert data["is_major_upgrade"] is False
    assert data["release_range"] == ["1.9", "1.10"]


def test_unknown_future_target_halts_with_update_guidance():
    code, data = run_json("--to", "2.2")

    assert code == 2
    assert data["error"] == "unknown_target"
    assert data["reason"] == "newer_than_known"
    assert data["latest"] == "2.1"
    assert "update the skill" in data["message"]
    assert "npx skills add redhat-developer/rhdh-users-agent-plugin" in data["message"]
    assert "Halted before reading any configuration." in data["message"]


def test_unknown_older_target_explains_coverage_start():
    code, data = run_json("--to", "1.3")

    assert code == 2
    assert data["reason"] == "older_than_known"
    assert "predates this skill's bundled release data" in data["message"]


def test_unknown_gap_target_is_not_treated_as_a_release():
    code, data = run_json("--to", "2.0")

    assert code == 2
    assert data["reason"] == "not_a_known_release"
    assert "not a release covered by this skill" in data["message"]


def test_malformed_target_is_rejected():
    result = run_resolver("--to", "latest")

    assert result.returncode == 1
    assert "expected X.Y or X.Y.Z" in result.stderr


def test_unknown_source_continues_with_explicit_gaps():
    code, data = run_json("--to", "1.10", "--from", "1.3")

    assert code == 0
    assert data["from"]["known"] is False
    assert data["from"]["backstage"] is None
    assert data["backstage_minor_jump"] is None
    assert data["node_major_jump"] is None
    assert data["from_dependent_checks_available"] is False
    assert data["gaps"] == ["from_version_unknown"]
    assert data["release_range"] == ["1.4", "1.5", "1.6", "1.7", "1.8", "1.9", "1.10"]


def test_earliest_target_defaults_to_an_unknown_source():
    code, data = run_json("--to", "1.4")

    assert code == 0
    assert data["from"]["version"] == "1.3"
    assert data["from"]["known"] is False
    assert data["default_from"] is True
    assert data["default_from_unknown"] is True
    assert data["gaps"] == ["from_version_unknown"]


def test_source_must_predate_target():
    same = run_resolver("--to", "1.10", "--from", "1.10")
    reverse = run_resolver("--to", "1.8", "--from", "1.10")

    assert same.returncode == 4
    assert reverse.returncode == 4
    assert "must be older than" in same.stderr


def test_manifest_covers_every_bundled_release_note():
    manifest = manifest_versions()
    notes = sorted(
        (path.stem for path in NOTES_DIR.glob("*.md") if path.name != "README.md"),
        key=version_key,
    )

    assert manifest == notes
    assert manifest == sorted(manifest, key=version_key)
    for version in manifest:
        assert (NOTES_DIR / f"{version}.md").is_file()


def test_manifest_backstage_versions_match_release_notes():
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))

    for release in data["releases"]:
        notes = (NOTES_DIR / f"{release['version']}.md").read_text(encoding="utf-8")
        match = re.search(r"upstream Backstage (\d+\.\d+)", notes)
        assert match, f"{release['version']}.md does not state an upstream Backstage version"
        assert match.group(1) == ".".join(release["backstage"].split(".")[:2])


def test_manifest_migration_references_exist():
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))

    for release in data["releases"]:
        reference = release.get("migration_reference")
        if reference:
            assert (SKILL / reference).is_file(), reference


def test_full_report_resolves_release_before_intake():
    workflow = (SKILL / "workflows" / "full-report.md").read_text(encoding="utf-8")

    assert "resolve-release.py" in workflow
    assert workflow.index("resolve-release.py") < workflow.index("## Step 1: Resolve Config Files")


def test_help_states_version_coverage_and_update_path():
    help_text = (SKILL / "workflows" / "help.md").read_text(encoding="utf-8")

    assert "1.4–1.10 and 2.1" in help_text
    assert (
        "npx skills add redhat-developer/rhdh-users-agent-plugin --skill rhdh-upgrade-helper"
        in help_text
    )


def test_manifest_allows_a_null_node_major(tmp_path):
    manifest = tmp_path / "releases.json"
    manifest.write_text(
        json.dumps(
            {
                "schema": 1,
                "releases": [
                    {"version": "2.1", "backstage": "1.54.9", "node_major": None},
                    {"version": "2.2", "backstage": "1.60.2", "node_major": 24},
                ],
            }
        ),
        encoding="utf-8",
    )

    resolver = runpy.run_path(str(SCRIPT))
    records = resolver["load_manifest"](manifest)

    assert records[0]["node_major"] is None
    assert records[1]["node_major"] == 24


def test_missing_node_version_is_reported_as_a_gap(tmp_path):
    skill = tmp_path / "skill"
    (skill / "scripts").mkdir(parents=True)
    (skill / "references" / "release-notes").mkdir(parents=True)
    shutil.copy(SCRIPT, skill / "scripts" / "resolve-release.py")
    (skill / "references" / "releases.json").write_text(
        json.dumps(
            {
                "schema": 1,
                "releases": [
                    {"version": "2.1", "backstage": "1.54.9", "node_major": 24},
                    {"version": "2.2", "backstage": "1.60.2", "node_major": None},
                ],
            }
        ),
        encoding="utf-8",
    )
    for version in ("2.1", "2.2"):
        (skill / "references" / "release-notes" / f"{version}.md").write_text(
            "# notes\n", encoding="utf-8"
        )

    result = subprocess.run(
        [
            sys.executable,
            str(skill / "scripts" / "resolve-release.py"),
            "--to",
            "2.2",
            "--from",
            "2.1",
            "--json",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data["node_major_jump"] is None
    assert "node_version_unknown" in data["gaps"]
