"""Tests for Agent Plugins root manifest conformance."""

import json
import re
from pathlib import Path

import jsonschema
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PLUGIN_MANIFEST = PROJECT_ROOT / "plugin.json"
PLUGIN_SCHEMA = PROJECT_ROOT / "tests" / "fixtures" / "plugin.schema.json"
PYPROJECT = PROJECT_ROOT / "pyproject.toml"


@pytest.fixture
def plugin_manifest() -> dict:
    """Load the root plugin.json document."""
    return json.loads(PLUGIN_MANIFEST.read_text(encoding="utf-8"))


@pytest.fixture
def plugin_schema() -> dict:
    """Load the vendored Agent Plugins 1.0.0 manifest schema."""
    return json.loads(PLUGIN_SCHEMA.read_text(encoding="utf-8"))


class TestPluginManifestConformance:
    """Validate plugin.json against the official schema and settled identity."""

    def test_manifest_exists(self):
        """Plugin root must include plugin.json."""
        assert PLUGIN_MANIFEST.is_file()

    def test_schema_fixture_exists(self):
        """Official schema must be vendored for offline validation."""
        assert PLUGIN_SCHEMA.is_file()

    def test_manifest_matches_schema(self, plugin_manifest, plugin_schema):
        """plugin.json must conform to Agent Plugins 1.0.0."""
        jsonschema.validate(instance=plugin_manifest, schema=plugin_schema)

    def test_required_identity_fields(self, plugin_manifest):
        """Settled Plugin identity and metadata must be present."""
        assert plugin_manifest["$schema"] == (
            "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
        )
        assert plugin_manifest["name"] == "rhdh-users-agent-plugin"
        assert plugin_manifest["version"] == "0.1.0"
        assert plugin_manifest["description"] == (
            "Portable Agent Plugin with skills for adopting and operating Red Hat Developer Hub."
        )
        assert plugin_manifest["license"] == "Apache-2.0"
        assert plugin_manifest["homepage"] == (
            "https://github.com/redhat-developer/rhdh-users-agent-plugin"
        )
        assert plugin_manifest["repository"] == (
            "https://github.com/redhat-developer/rhdh-users-agent-plugin"
        )
        assert plugin_manifest["author"] == {
            "name": "Red Hat Developer Hub",
            "url": "https://developers.redhat.com/products/rhdh/overview",
        }
        assert plugin_manifest["keywords"] == [
            "rhdh",
            "red-hat-developer-hub",
            "backstage",
            "agent-skills",
            "software-templates",
        ]

    def test_version_matches_pyproject(self, plugin_manifest):
        """Plugin version must stay aligned with the Python project version."""
        text = PYPROJECT.read_text(encoding="utf-8")
        name = re.search(r'(?m)^name = "([^"]+)"', text)
        version = re.search(r'(?m)^version = "([^"]+)"', text)
        assert name is not None and version is not None
        assert name.group(1) == "rhdh-users-agent-plugin"
        assert plugin_manifest["version"] == version.group(1)

    def test_no_mcp_config(self):
        """This Plugin ships Skills only; mcp.json must be absent."""
        assert not (PROJECT_ROOT / "mcp.json").exists()

    def test_no_extensions_field(self, plugin_manifest):
        """Portable core only; no client extension manifest data."""
        assert "extensions" not in plugin_manifest
