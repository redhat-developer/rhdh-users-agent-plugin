"""Offline tests for the release-notes generator."""

import runpy
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]
GENERATOR = ROOT / "skills/rhdh-upgrade-helper/scripts/generate-release-notes.py"
FIXTURES = ROOT / "tests/fixtures/release-notes"
SKILL = ROOT / "skills/rhdh-upgrade-helper"


@pytest.fixture(scope="module")
def generator():
    return runpy.run_path(str(GENERATOR))


def read(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_parse_article_ignores_navigation(generator):
    title, intro, items, overflow = generator["parse_article"](read("section-known-issues.html"))

    assert title == "Known issues"
    assert intro == ["This section lists known issues in Red Hat Developer Hub 2.1."]
    assert [item["title"] for item in items] == [
        "Bulk import reports success when a pull request cannot be created",
        "Styles on other pages render incorrectly",
    ]
    assert overflow == []
    assert "Navigation item" not in str(items)
    assert all("Additional resources" not in p for item in items for p in item["paragraphs"])


def test_known_issue_keeps_workaround_and_ticket(generator):
    _, _, items, _ = generator["parse_article"](read("section-known-issues.html"))

    bullet = generator["render_item"](items[0], "known_issues")

    assert bullet.startswith(
        "- **Bulk import reports success when a pull request cannot be created** (RHDHBUGS-4016): "
    )
    assert "Check each imported repository for its pull request" in bullet


def test_section_body_limit_truncates_on_word_boundary(generator):
    item = {"title": "Long", "paragraphs": ["word " * 200], "bullets": []}

    body = generator["render_item"](item, "new_features_and_enhancements")

    assert body.endswith("…")
    assert len(body) <= generator["DEFAULT_BODY_LIMIT"] + 40


def test_build_release_emits_every_required_section(generator):
    content = generator["build_release"](
        "2.1",
        "https://example.invalid/2.1",
        read("landing-2.1.html"),
        {"known_issues": "- **Only issue**: text\n"},
    )

    assert content.startswith("# RHDH 2.1 Release Notes")
    assert "Backstage 1.54.9" in content
    for _, heading in generator["SECTIONS"]:
        assert f"## {heading}" in content
    assert content.count("Not published for this release.") == len(generator["SECTIONS"]) - 1


def test_build_release_is_deterministic(generator):
    args = ("2.1", "https://example.invalid/2.1", read("landing-2.1.html"), {})

    assert generator["build_release"](*args) == generator["build_release"](*args)


def test_discover_sections_maps_known_slugs_only(generator):
    sections = generator["discover_sections"](read("landing-2.1.html"), "2.1")

    assert sections == {
        "new_features_and_enhancements": generator["DOCS_URL"]
        + "/2.1/whats_new-new_features_and_enhancements",
        "known_issues": generator["DOCS_URL"] + "/2.1/whats_new-known_issues",
        "removed_features": generator["DOCS_URL"] + "/2.1/whats_new-removed_features",
    }


def test_discover_versions_filters_and_sorts_numerically(generator):
    assert generator["discover_versions"](read("product-page.html")) == ["2.1", "2.2", "2.10"]


def test_generated_output_satisfies_release_note_section_contract(generator):
    required = (
        "## New features and enhancements",
        "## Technology Preview features",
        "## Developer Preview features",
        "## Deprecated features",
        "## Removed features",
        "## Known issues",
        "## Fixed issues (upgrade-relevant)",
        "## Security advisories",
    )

    content = generator["build_release"]("2.1", "https://example.invalid/2.1", "", {})

    for section in required:
        assert section in content


def test_bundled_notes_are_generator_shaped():
    notes = (SKILL / "references/release-notes/2.1.md").read_text(encoding="utf-8")

    assert "Do not edit by hand." in notes
