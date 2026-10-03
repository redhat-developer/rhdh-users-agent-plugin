"""Shared pytest fixtures for rhdh-users-agent-plugin tests."""

from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
RHDH_TEMPLATES_SKILL_DIR = PROJECT_ROOT / "skills" / "rhdh-templates"


@pytest.fixture
def skill_root():
    """Return the project root path."""
    return PROJECT_ROOT


@pytest.fixture
def rhdh_templates_skill_dir():
    """Return the rhdh-templates skill directory path."""
    return RHDH_TEMPLATES_SKILL_DIR
