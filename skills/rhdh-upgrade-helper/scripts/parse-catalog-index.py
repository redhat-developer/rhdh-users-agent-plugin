#!/usr/bin/env python3
"""Read extracted RHDH catalog-index data or its overlay fallback."""

from __future__ import annotations

import argparse
import base64
import csv
import json
import re
import tempfile
from pathlib import Path


def find_data_dir(release: str, data_root: str | None) -> tuple[Path, str]:
    root = Path(data_root) if data_root else Path(tempfile.gettempdir())
    catalog = root / f"rhdh-catalog-index-{release}"
    overlay = root / f"rhdh-overlays-{release}"
    if (catalog / "index.json").exists():
        return catalog, "catalog-index"
    if (overlay / "versions.json").exists():
        return overlay, "overlay"
    raise SystemExit(f"No data found for release {release}. Run extract-catalog-index.sh first.")


def load_index(data_dir: Path) -> dict | None:
    path = data_dir / "index.json"
    return json.loads(path.read_text()) if path.exists() else None


def load_defaults(data_dir: Path) -> str | None:
    for name in ("dynamic-plugins.default.yaml", "default.packages.yaml"):
        path = data_dir / name
        if path.exists():
            return path.read_text()
    return None


def load_default_plugin_entries(data_dir: Path) -> dict[str, dict]:
    content = load_defaults(data_dir)
    if content is None:
        return {}

    entries = {}
    pending_oci = ""
    current_local = ""
    for line in content.splitlines():
        oci_match = re.match(r"^\s*#\s*- package:\s*(oci://\S+)", line)
        if oci_match:
            pending_oci = oci_match.group(1).strip("\"'")
            continue

        local_match = re.match(r"^\s*- package:\s*(\./dynamic-plugins/dist/\S+)", line)
        if not local_match and re.match(r"^\s*- package:", line):
            current_local = ""
            pending_oci = ""

        if local_match:
            current_local = local_match.group(1).strip("\"'")
            entries[current_local] = {
                "disabled": None,
                "ociAlternative": pending_oci,
            }
            pending_oci = ""
            continue

        if current_local:
            disabled_match = re.match(r"^\s+disabled:\s*(true|false)", line)
            if disabled_match:
                entries[current_local]["disabled"] = disabled_match.group(1) == "true"
    return entries


def load_default_oci_artifacts(data_dir: Path) -> list[dict]:
    """Return active OCI package entries from the shipped defaults file."""
    content = load_defaults(data_dir)
    if content is None:
        return []

    artifacts = []
    current = None
    for line in content.splitlines():
        package_match = re.match(r"^\s*-\s+package:\s*(\S+)", line)
        if package_match:
            if current is not None:
                artifacts.append(current)
            package = package_match.group(1).strip("\"'")
            current = (
                {"package": package, "disabled": None} if package.startswith("oci://") else None
            )
            continue

        if current is not None:
            disabled_match = re.match(r"^\s+disabled:\s*(true|false)", line)
            if disabled_match:
                current["disabled"] = disabled_match.group(1) == "true"

    if current is not None:
        artifacts.append(current)
    return artifacts


def load_versions(data_dir: Path) -> dict | None:
    path = data_dir / "versions.json"
    if path.exists():
        return json.loads(path.read_text())

    for labels_path in (
        data_dir / "root/buildinfo/labels.json",
        data_dir / "usr/share/buildinfo/labels.json",
    ):
        if not labels_path.exists():
            continue
        labels = json.loads(labels_path.read_text())
        versions = {}
        if labels.get("backstage.version"):
            versions["backstage"] = labels["backstage.version"]
        if labels.get("node.version"):
            versions["node"] = labels["node.version"]
        if labels.get("rhdh.version"):
            versions["rhdh"] = labels["rhdh.version"]
        if versions:
            return versions
    return None


def _yaml_scalar(value: str) -> str:
    value = value.strip()
    if value.startswith(("'", '"')) and value[-1:] == value[0]:
        return value[1:-1]
    return value


def _normalise_package_name(value: str) -> str:
    return value.removesuffix("-dynamic") if value else ""


def _index_package_names(metadata: dict) -> list[str]:
    encoded = metadata.get("io.backstage.dynamic-packages")
    if not encoded:
        return []
    try:
        entries = json.loads(base64.b64decode(encoded).decode())
    except (ValueError, UnicodeDecodeError):
        return []

    names = []
    seen = set()

    def add(name: str) -> None:
        name = _normalise_package_name(name)
        if name and name not in seen:
            seen.add(name)
            names.append(name)

    for entry in entries:
        for package in entry.values():
            if package.get("name"):
                add(package["name"])
            backstage = package.get("backstage", {})
            if backstage.get("pluginPackage"):
                add(backstage["pluginPackage"])
            for name in backstage.get("pluginPackages", []):
                add(name)
    return names


def _artifact_alias(artifact: str) -> str:
    if artifact.startswith("./dynamic-plugins/dist/"):
        return artifact.removeprefix("./dynamic-plugins/dist/").removesuffix("-dynamic")
    if artifact.startswith("oci://"):
        image = artifact.removeprefix("oci://").split("!", 1)[0]
        return image.rsplit("/", 1)[-1].split(":", 1)[0].split("@", 1)[0]
    return ""


def _artifact_type(artifact: str) -> str:
    if artifact.startswith("./dynamic-plugins/dist/"):
        return "local"
    if artifact.startswith("oci://"):
        return "oci"
    if artifact.startswith(("http://", "https://", "@")):
        return "npm"
    return "unknown"


def load_package_entities(data_dir: Path) -> dict[str, dict]:
    """Load the complete Package entity list without a YAML runtime dependency."""
    package_dir = data_dir / "catalog-entities/extensions/packages"
    if not package_dir.is_dir():
        return {}

    packages = {}
    for path in sorted(package_dir.glob("*.yaml")):
        text = path.read_text()
        metadata_name = re.search(r"^  name:\s*(.+)$", text, re.MULTILINE)
        if not metadata_name:
            continue

        package = {"name": _yaml_scalar(metadata_name.group(1))}
        for field in ("packageName", "dynamicArtifact", "version", "support", "lifecycle"):
            match = re.search(rf"^  {field}:\s*(.+)$", text, re.MULTILINE)
            if match:
                package[field] = _yaml_scalar(match.group(1))

        supported_versions = re.search(r"^    supportedVersions:\s*(.+)$", text, re.MULTILINE)
        if supported_versions:
            package["backstage"] = {"supportedVersions": _yaml_scalar(supported_versions.group(1))}

        package["sourceFile"] = str(path)
        packages[package["name"]] = package
    return packages


def load_csv_plugins(data_dir: Path) -> list[dict] | None:
    for path in (
        data_dir / "extend_dynamic-plugins-reference" / "rhdh-supported-plugins.csv",
        data_dir / "rhdh-supported-plugins.csv",
    ):
        if path.exists():
            with path.open(newline="") as stream:
                return list(csv.DictReader(stream))
    return None


def load_reference_catalog(data_dir: Path) -> dict[str, dict]:
    """Index GA, Tech Preview, deprecated, and supported-plugin references."""
    reference_dir = data_dir / "extend_dynamic-plugins-reference"
    references = {}

    reference_files = {
        "ref-ga-plugins.adoc": "generally-available",
        "ref-technology-preview-plugins.adoc": "technology-preview",
        "ref-deprecated-plugins.adoc": "deprecated",
    }
    package_pattern = re.compile(r"https://npmjs\.com/package/(`?@[^/`]+/[^/`]+|[^/`]+)")
    for filename, status in reference_files.items():
        path = reference_dir / filename
        if not path.exists():
            continue
        for line in path.read_text().splitlines():
            for match in package_pattern.finditer(line):
                package_name = match.group(1).strip("`")
                entry = references.setdefault(package_name, {})
                entry[status] = True
                entry.setdefault("files", []).append(str(path))

    csv_plugins = load_csv_plugins(data_dir)
    for row in csv_plugins or []:
        package_name = row.get("Plugin", "").strip('"')
        if not package_name:
            continue
        entry = references.setdefault(package_name, {})
        support_level = row.get("Support Level", "").strip('"')
        entry["supported"] = True
        entry["supportLevel"] = support_level
        entry.setdefault("files", []).append(str(reference_dir / "rhdh-supported-plugins.csv"))
        if support_level == "Production":
            entry["generally-available"] = True
        elif support_level == "Red Hat Tech Preview":
            entry["technology-preview"] = True

    return references


def extraction_info(data_dir: Path, source: str) -> dict[str, str]:
    info = {
        "path": str(data_dir),
        "source": source,
        "fidelity": "authoritative" if source == "catalog-index" else "fallback",
    }
    marker = data_dir / ".extraction"
    if marker.exists():
        for line in marker.read_text().splitlines():
            key, separator, value = line.partition("=")
            if not separator:
                continue
            if key == "source":
                info["extractor"] = value
            elif key in {"image", "platform"}:
                info[key] = value
    return info


def _inherit_artifact(artifact: str, support: str, default_oci: dict) -> str:
    if support.lower() not in {"generally-available", "ga"}:
        return ""
    if not artifact.startswith("oci://registry.access.redhat.com/"):
        return ""
    if not default_oci:
        return ""

    image, separator, plugin_path = artifact.partition("!")
    image = image.split("@", 1)[0]
    if ":" in image.rsplit("/", 1)[-1]:
        image = image.rsplit(":", 1)[0]
    result = f"{image}:{{{{inherit}}}}"
    return f"{result}{separator}{plugin_path}" if separator else result


def _reference_status(
    references: dict[str, dict], package_name: str, dynamic_package_names: list[str]
) -> dict:
    names = [package_name, *dynamic_package_names]
    for name in names:
        if name in references:
            return references[name]
    return {}


def plugin_records(data_dir: Path) -> list[dict]:
    index = load_index(data_dir)
    if index is not None:
        package_entities = load_package_entities(data_dir)
        default_entries = load_default_plugin_entries(data_dir)
        default_oci_artifacts = load_default_oci_artifacts(data_dir)
        default_oci_by_alias = {
            _artifact_alias(entry["package"]): entry
            for entry in default_oci_artifacts
            if _artifact_alias(entry["package"])
        }
        references = load_reference_catalog(data_dir)
        package_by_name = {
            _normalise_package_name(package.get("packageName", "")): package
            for package in package_entities.values()
            if package.get("packageName")
        }
        records = []
        matched_packages = set()
        for index_name, metadata in sorted(index.items()):
            package = package_entities.get(index_name, {})
            dynamic_package_names = _index_package_names(metadata)
            if not package:
                for package_name in dynamic_package_names:
                    package = package_by_name.get(package_name, {})
                    if package:
                        break
            if package:
                matched_packages.add(package["name"])
            name = package.get("name", index_name)
            merged = {**metadata, **package}
            default = default_entries.get(package.get("dynamicArtifact", ""), {})
            aliases = {index_name, name}
            artifact_alias = _artifact_alias(package.get("dynamicArtifact", ""))
            if artifact_alias:
                aliases.add(artifact_alias)
            artifact = package.get("dynamicArtifact", metadata.get("dynamicArtifact", ""))
            default_oci = default_oci_by_alias.get(_artifact_alias(artifact), {})
            records.append(
                {
                    "name": name,
                    "aliases": sorted(aliases),
                    "packageName": package.get("packageName", metadata.get("packageName", "")),
                    "dynamicArtifact": artifact,
                    "artifactType": _artifact_type(artifact),
                    "version": package.get("version", metadata.get("version", "")),
                    "backstage": package.get("backstage", metadata.get("backstage", {})),
                    "support": package.get("support", metadata.get("support", "unknown")),
                    "workspace": metadata.get("workspacePath", "").split("/")[0],
                    "imageTag": metadata.get("imageTag", ""),
                    "registryReference": metadata.get("registryReference", ""),
                    "indexRegistryReference": metadata.get("registryReference", ""),
                    "artifactSource": "package-entity" if package else "index",
                    "dynamicPackageNames": dynamic_package_names,
                    "defaultDisabled": default.get("disabled"),
                    "defaultOciArtifact": default.get("ociAlternative", ""),
                    "defaultPackageArtifact": default_oci.get("package", ""),
                    "inheritArtifact": _inherit_artifact(
                        artifact, package.get("support", ""), default_oci
                    ),
                    "referenceStatus": _reference_status(
                        references,
                        package.get("packageName", metadata.get("packageName", "")),
                        dynamic_package_names,
                    ),
                    "packageEntity": package,
                    "metadata": merged,
                }
            )
        for name in sorted(set(package_entities) - matched_packages):
            package = package_entities[name]
            default = default_entries.get(package.get("dynamicArtifact", ""), {})
            aliases = {name}
            artifact_alias = _artifact_alias(package.get("dynamicArtifact", ""))
            if artifact_alias:
                aliases.add(artifact_alias)
            artifact = package.get("dynamicArtifact", "")
            default_oci = default_oci_by_alias.get(_artifact_alias(artifact), {})
            records.append(
                {
                    "name": name,
                    "aliases": sorted(aliases),
                    "packageName": package.get("packageName", ""),
                    "dynamicArtifact": artifact,
                    "artifactType": _artifact_type(artifact),
                    "version": package.get("version", ""),
                    "backstage": package.get("backstage", {}),
                    "support": package.get("support", "unknown"),
                    "workspace": "",
                    "imageTag": "",
                    "registryReference": "",
                    "indexRegistryReference": "",
                    "artifactSource": "package-entity",
                    "dynamicPackageNames": [],
                    "defaultDisabled": default.get("disabled"),
                    "defaultOciArtifact": default.get("ociAlternative", ""),
                    "defaultPackageArtifact": default_oci.get("package", ""),
                    "inheritArtifact": _inherit_artifact(
                        artifact, package.get("support", ""), default_oci
                    ),
                    "referenceStatus": _reference_status(
                        references, package.get("packageName", ""), []
                    ),
                    "packageEntity": package,
                    "metadata": package,
                }
            )
        return records

    csv_plugins = load_csv_plugins(data_dir)
    if csv_plugins is None:
        return []
    return [
        {
            "name": row.get("Plugin", "").strip('"'),
            "support": row.get("Support Level", "").strip('"'),
            "version": row.get("Version", "").strip('"'),
            "role": row.get("Role", "").strip('"'),
            "source": "overlay",
        }
        for row in csv_plugins
        if row.get("Plugin", "").strip('"')
    ]


def workspace_names(data_dir: Path) -> list[str]:
    index = load_index(data_dir)
    if index is not None:
        return sorted(
            {
                metadata.get("workspacePath", "").split("/")[0]
                for metadata in index.values()
                if metadata.get("workspacePath")
            }
        )
    workspaces = data_dir / "workspaces"
    return (
        sorted(path.name for path in workspaces.iterdir() if path.is_dir())
        if workspaces.exists()
        else []
    )


def bundled_plugins(data_dir: Path) -> list[str]:
    content = load_defaults(data_dir)
    if content is None:
        return []
    return [
        line.split("./dynamic-plugins/dist/", 1)[1].strip().strip("\"'")
        for line in content.splitlines()
        if "package: ./dynamic-plugins/dist/" in line and not line.strip().startswith("#")
    ]


def cmd_source(args: argparse.Namespace) -> None:
    data_dir, source = find_data_dir(args.release, args.data_root)
    print(json.dumps(extraction_info(data_dir, source), indent=2))


def cmd_plugins(args: argparse.Namespace) -> None:
    data_dir, _ = find_data_dir(args.release, args.data_root)
    records = plugin_records(data_dir)
    if args.json:
        print(json.dumps(records, indent=2))
        return
    print(f"Total plugins: {len(records)}")
    for record in records:
        print(f"{record['name']:<60} {record['support']:<20} {record['workspace']}")


def cmd_workspaces(args: argparse.Namespace) -> None:
    result = workspace_names(find_data_dir(args.release, args.data_root)[0])
    print(json.dumps(result, indent=2) if args.json else "\n".join(result))


def cmd_defaults(args: argparse.Namespace) -> None:
    data_dir, _ = find_data_dir(args.release, args.data_root)
    content = load_defaults(data_dir)
    if content is None:
        raise SystemExit("No defaults file found.")

    result = {
        "enabled": sum("disabled: false" in line for line in content.splitlines()),
        "disabled": sum("disabled: true" in line for line in content.splitlines()),
        "bundled_local": sum(
            "package: ./dynamic-plugins/dist/" in line and not line.strip().startswith("#")
            for line in content.splitlines()
        ),
        "oci_commented": sum(
            line.strip().startswith("# - package: oci://") for line in content.splitlines()
        ),
    }
    print(json.dumps(result, indent=2) if args.json else result)


def cmd_versions(args: argparse.Namespace) -> None:
    data_dir, _ = find_data_dir(args.release, args.data_root)
    versions = load_versions(data_dir)
    if versions is None:
        raise SystemExit("No versions.json found.")
    print(
        json.dumps(versions, indent=2)
        if args.json
        else "\n".join(f"{k}: {v}" for k, v in versions.items())
    )


def cmd_bundled(args: argparse.Namespace) -> None:
    result = bundled_plugins(find_data_dir(args.release, args.data_root)[0])
    print(json.dumps(result, indent=2) if args.json else "\n".join(result))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root")
    subparsers = parser.add_subparsers(dest="command", required=True)
    commands = {
        "source": ("Show source and extractor", cmd_source),
        "plugins": ("List plugin metadata", cmd_plugins),
        "defaults": ("Summarize default plugins", cmd_defaults),
        "versions": ("Show release versions", cmd_versions),
        "workspaces": ("List workspace names", cmd_workspaces),
        "bundled": ("List bundled local-path plugins", cmd_bundled),
    }
    for name, (help_text, _) in commands.items():
        subparser = subparsers.add_parser(name, help=help_text)
        subparser.add_argument("release")
        subparser.add_argument("--json", action="store_true")

    args = parser.parse_args()
    commands[args.command][1](args)


if __name__ == "__main__":
    main()
