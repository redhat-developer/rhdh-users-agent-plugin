"""Coverage checks for bundled RHDH upgrade-helper references."""

import runpy
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
UPGRADE_HELPER = PROJECT_ROOT / "skills" / "rhdh-upgrade-helper"
REQUIRED_RELEASE_NOTE_SECTIONS = (
    "## New features and enhancements",
    "## Technology Preview features",
    "## Developer Preview features",
    "## Deprecated features",
    "## Removed features",
    "## Known issues",
    "## Fixed issues (upgrade-relevant)",
    "## Security advisories",
)


def test_chart_migration_versions_have_complete_release_notes():
    """Every script-supported target has bundled notes with the expected sections."""
    script = UPGRADE_HELPER / "scripts" / "migrate-chart-values.py"
    supported_versions = runpy.run_path(str(script))["SUPPORTED_VERSIONS"]

    for version in supported_versions:
        notes = UPGRADE_HELPER / "references" / "release-notes" / f"{version}.md"
        assert notes.is_file(), f"Missing bundled release notes for {version}"
        content = notes.read_text(encoding="utf-8")
        for section in REQUIRED_RELEASE_NOTE_SECTIONS:
            assert section in content, f"{version}.md missing section: {section}"


def test_rhdh_2_1_migration_reference_exists():
    """RHDH 2.1 product migration guidance is bundled for all deployment methods."""
    assert (UPGRADE_HELPER / "references" / "migration-2.1.md").is_file()


def test_known_issue_step_covers_preinstalled_plugins():
    """Bug checks must include plugins the target release enables by default."""
    workflow = (UPGRADE_HELPER / "workflows" / "full-report.md").read_text(encoding="utf-8")

    assert "$DEFAULT_ENABLED_PLUGINS" in workflow
    assert "$EFFECTIVE_PLUGINS" in workflow
    assert "release-notes known issues" in workflow.lower()
