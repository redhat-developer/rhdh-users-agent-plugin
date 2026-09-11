"""Tests for shipped catalog-index extraction and parsing."""

import base64
import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).parents[2]
EXTRACTOR = ROOT / "skills/rhdh-upgrade-helper/scripts/extract-catalog-index.sh"
PARSER = ROOT / "skills/rhdh-upgrade-helper/scripts/parse-catalog-index.py"


def run_parser(data_root: Path, command: str, release: str = "1.10") -> dict | list:
    result = subprocess.run(
        ["python3", str(PARSER), "--data-root", str(data_root), command, release, "--json"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_parser_preserves_catalog_metadata_and_reports_authoritative_source(tmp_path):
    catalog = tmp_path / "rhdh-catalog-index-1.10"
    catalog.mkdir()
    (catalog / "index.json").write_text(
        json.dumps(
            {
                "plugin-a": {
                    "workspacePath": "orchestrator/plugin-a",
                    "support": "GA",
                    "packageName": "@example/plugin-a",
                    "dynamicArtifact": "oci://quay.io/example/plugin-a:1.0",
                    "registryReference": "registry.access.redhat.com/rhdh/plugin-a@sha256:abc",
                    "productDocumentation": {"url": "https://example.invalid/plugin-a"},
                }
            }
        )
    )
    (catalog / "dynamic-plugins.default.yaml").write_text(
        "# - package: oci://quay.io/example/plugin-a@sha256:def\n"
        "# disabled: true\n"
        "- package: ./dynamic-plugins/dist/plugin-a\n  disabled: true\n"
        "- package: oci://quay.io/example/plugin-direct@sha256:ghi\n"
        "  disabled: false\n"
        "- package: ./dynamic-plugins/dist/plugin-b\n  disabled: false\n"
    )
    package_dir = catalog / "catalog-entities/extensions/packages"
    package_dir.mkdir(parents=True)
    (package_dir / "plugin-a.yaml").write_text(
        "apiVersion: extensions.backstage.io/v1alpha1\n"
        "kind: Package\n"
        "metadata:\n"
        "  name: plugin-a\n"
        "spec:\n"
        "  packageName: '@example/plugin-a'\n"
        "  dynamicArtifact: ./dynamic-plugins/dist/plugin-a\n"
        "  version: 1.0.0\n"
        "  backstage:\n"
        "    supportedVersions: 1.49.4\n"
        "  support: generally-available\n"
    )
    (package_dir / "plugin-b.yaml").write_text(
        "metadata:\n  name: plugin-b\nspec:\n  packageName: '@example/plugin-b'\n"
        "  dynamicArtifact: ./dynamic-plugins/dist/plugin-b\n"
        "  version: 2.0.0\n  support: community\n"
    )
    labels_dir = catalog / "root/buildinfo"
    labels_dir.mkdir(parents=True)
    (labels_dir / "labels.json").write_text(
        '{"rhdh.version": "1.10.2", "backstage.version": "1.49.4"}'
    )
    (catalog / ".extraction").write_text(
        "complete=true\nsource=oc\nimage=quay.io/rhdh/plugin-catalog-index:1.10-84\n"
        "platform=linux/amd64\n"
    )

    source = run_parser(tmp_path, "source")
    plugins = run_parser(tmp_path, "plugins")
    defaults = run_parser(tmp_path, "defaults")
    versions = run_parser(tmp_path, "versions")

    assert source["source"] == "catalog-index"
    assert source["fidelity"] == "authoritative"
    assert source["extractor"] == "oc"
    assert plugins[0]["metadata"]["productDocumentation"]["url"]
    assert plugins[0]["packageName"] == "@example/plugin-a"
    assert plugins[0]["dynamicArtifact"] == "./dynamic-plugins/dist/plugin-a"
    assert plugins[0]["artifactType"] == "local"
    assert plugins[0]["artifactSource"] == "package-entity"
    assert (
        plugins[0]["indexRegistryReference"]
        == "registry.access.redhat.com/rhdh/plugin-a@sha256:abc"
    )
    assert plugins[0]["backstage"]["supportedVersions"] == "1.49.4"
    assert plugins[0]["defaultDisabled"] is True
    assert plugins[0]["defaultOciArtifact"] == "oci://quay.io/example/plugin-a@sha256:def"
    plugin_b = next(plugin for plugin in plugins if plugin["name"] == "plugin-b")
    assert plugin_b["defaultDisabled"] is False
    assert defaults["bundled_local"] == 2
    assert versions == {"backstage": "1.49.4", "rhdh": "1.10.2"}


def test_parser_uses_overlay_csv_as_reduced_fidelity_fallback(tmp_path):
    overlay = tmp_path / "rhdh-overlays-1.10"
    (overlay / "workspaces").mkdir(parents=True)
    (overlay / "versions.json").write_text('{"backstage": "1.49.4"}')
    (overlay / "rhdh-supported-plugins.csv").write_text(
        'Plugin,Support Level,Version,Role\n"plugin-a",GA,1.0,frontend\n'
    )
    (overlay / ".extraction").write_text("source=overlay-git\n")

    source = run_parser(tmp_path, "source")
    plugins = run_parser(tmp_path, "plugins")

    assert source["source"] == "overlay"
    assert source["fidelity"] == "fallback"
    assert plugins[0]["source"] == "overlay"
    assert plugins[0]["support"] == "GA"


def test_parser_associates_image_alias_with_package_entity(tmp_path):
    catalog = tmp_path / "rhdh-catalog-index-1.10"
    catalog.mkdir()
    encoded_packages = base64.b64encode(
        json.dumps(
            [
                {
                    "image-plugin": {
                        "name": "@example/frontend-dynamic",
                        "version": "1.2.3",
                        "backstage": {"pluginPackages": ["@example/backend"]},
                    }
                }
            ]
        ).encode()
    ).decode()
    (catalog / "index.json").write_text(
        json.dumps(
            {
                "image-plugin": {
                    "registryReference": "registry.access.redhat.com/rhdh/frontend@sha256:abc",
                    "io.backstage.dynamic-packages": encoded_packages,
                }
            }
        )
    )
    package_dir = catalog / "catalog-entities/extensions/packages"
    package_dir.mkdir(parents=True)
    (package_dir / "canonical-frontend.yaml").write_text(
        "metadata:\n  name: canonical-plugin\nspec:\n"
        "  packageName: '@example/frontend'\n"
        "  dynamicArtifact: oci://ghcr.io/example/frontend:1.2.3!frontend\n"
        "  version: 1.2.3\n  support: community\n"
    )
    (package_dir / "canonical-backend.yaml").write_text(
        "metadata:\n  name: canonical-backend\nspec:\n"
        "  packageName: '@example/backend'\n"
        "  dynamicArtifact: oci://registry.example/backend@sha256:def\n"
        "  version: 1.2.3\n  support: generally-available\n"
    )

    plugins = run_parser(tmp_path, "plugins")

    matched = next(plugin for plugin in plugins if plugin["name"] == "canonical-plugin")
    assert len(plugins) == 2
    assert matched["aliases"] == ["canonical-plugin", "frontend", "image-plugin"]
    assert matched["packageName"] == "@example/frontend"
    assert matched["dynamicArtifact"] == "oci://ghcr.io/example/frontend:1.2.3!frontend"
    assert matched["artifactType"] == "oci"
    assert (
        matched["indexRegistryReference"] == "registry.access.redhat.com/rhdh/frontend@sha256:abc"
    )
    assert matched["artifactSource"] == "package-entity"
    assert any(plugin["name"] == "canonical-backend" for plugin in plugins)


def test_parser_derives_inherit_artifact_only_for_ga_registry_defaults(tmp_path):
    catalog = tmp_path / "rhdh-catalog-index-1.10"
    catalog.mkdir()
    (catalog / "index.json").write_text(
        json.dumps(
            {
                "ga-plugin": {"workspacePath": "ga/plugin"},
                "community-plugin": {"workspacePath": "community/plugin"},
            }
        )
    )
    (catalog / "dynamic-plugins.default.yaml").write_text(
        "plugins:\n"
        "  - package: oci://registry.access.redhat.com/rhdh/ga-plugin:1.10--1.0.0\n"
        "    disabled: false\n"
        "  - package: oci://ghcr.io/example/community-plugin:1.0.0\n"
        "    disabled: false\n"
    )
    reference_dir = catalog / "extend_dynamic-plugins-reference"
    reference_dir.mkdir()
    (reference_dir / "ref-ga-plugins.adoc").write_text(
        "|GA Plugin |`https://npmjs.com/package/@example/ga-plugin/v/1.0.0[@example/ga-plugin]`\n"
    )
    (reference_dir / "ref-technology-preview-plugins.adoc").write_text(
        "|Community Plugin |`https://npmjs.com/package/@example/community-plugin/v/1.0.0[@example/community-plugin]`\n"
    )
    (reference_dir / "ref-deprecated-plugins.adoc").write_text(
        "There are no deprecated plugins in this release.\n"
    )
    (reference_dir / "rhdh-supported-plugins.csv").write_text(
        'Plugin,Support Level\n"@example/ga-plugin",Production\n'
        '"@example/community-plugin",Red Hat Tech Preview\n'
    )
    package_dir = catalog / "catalog-entities/extensions/packages"
    package_dir.mkdir(parents=True)
    (package_dir / "ga.yaml").write_text(
        "metadata:\n  name: ga-plugin\nspec:\n"
        "  packageName: '@example/ga-plugin'\n"
        "  dynamicArtifact: oci://registry.access.redhat.com/rhdh/ga-plugin@sha256:abc\n"
        "  support: generally-available\n"
    )
    (package_dir / "community.yaml").write_text(
        "metadata:\n  name: community-plugin\nspec:\n"
        "  packageName: '@example/community-plugin'\n"
        "  dynamicArtifact: oci://ghcr.io/example/community-plugin:1.0.0\n"
        "  support: community\n"
    )

    plugins = run_parser(tmp_path, "plugins")
    ga = next(plugin for plugin in plugins if plugin["name"] == "ga-plugin")
    community = next(plugin for plugin in plugins if plugin["name"] == "community-plugin")

    assert ga["dynamicArtifact"] == ("oci://registry.access.redhat.com/rhdh/ga-plugin@sha256:abc")
    assert ga["defaultPackageArtifact"].endswith("ga-plugin:1.10--1.0.0")
    assert ga["inheritArtifact"] == ("oci://registry.access.redhat.com/rhdh/ga-plugin:{{inherit}}")
    assert ga["referenceStatus"]["generally-available"] is True
    assert ga["referenceStatus"]["supported"] is True
    assert community["inheritArtifact"] == ""
    assert community["dynamicArtifact"] == "oci://ghcr.io/example/community-plugin:1.0.0"
    assert community["referenceStatus"]["technology-preview"] is True


def test_extractor_prefers_oc_and_rechecks_explicit_tag_cache(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    calls = tmp_path / "oc-calls"
    oc = bin_dir / "oc"
    oc.write_text(
        "#!/bin/sh\n"
        'echo called >> "$TEST_OC_CALLS"\n'
        'for arg in "$@"; do\n'
        '  case "$arg" in /:*) target="${arg#/:}" ;; esac\n'
        "done\n"
        'mkdir -p "$target"\n'
        "printf '{}' > \"$target/index.json\"\n"
    )
    oc.chmod(0o755)
    env = {
        **os.environ,
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
        "TEST_OC_CALLS": str(calls),
        "TMPDIR": str(tmp_path),
    }

    first = subprocess.run(
        ["bash", str(EXTRACTOR), "1.10", "--tag", "1.10-84"],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    second = subprocess.run(
        ["bash", str(EXTRACTOR), "1.10", "--tag", "1.10-85"],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    assert len(calls.read_text().splitlines()) == 2
    assert "rhdh-catalog-index-1.10" in second.stdout


def test_extractor_rejects_path_like_release():
    result = subprocess.run(
        ["bash", str(EXTRACTOR), "../../escape"], capture_output=True, text=True, check=False
    )

    assert result.returncode != 0
    assert "Invalid release" in result.stderr
