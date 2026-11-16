#!/usr/bin/env python3
"""Resolve RHDH release versions against the bundled release manifest."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
MANIFEST = SKILL_DIR / "references" / "releases.json"
NOTES_DIR = SKILL_DIR / "references" / "release-notes"

VERSION_RE = re.compile(r"^(?:v)?(?:rhdh[\s_-]*)?(\d+)\.(\d+)(?:\.(\d+))?$", re.IGNORECASE)


class ResolveError(Exception):
    def __init__(self, code: int, payload: dict) -> None:
        super().__init__(payload.get("message", "release resolution failed"))
        self.code = code
        self.payload = payload


def parse_version(raw: str | None) -> dict | None:
    if raw is None:
        return None
    text = raw.strip()
    match = VERSION_RE.match(text)
    if not match:
        return None
    major, minor, patch = match.groups()
    return {
        "requested": text,
        "major": int(major),
        "minor": int(minor),
        "patch": int(patch) if patch is not None else None,
        "version": f"{int(major)}.{int(minor)}",
    }


def key(record: dict) -> tuple[int, int]:
    return (record["major"], record["minor"])


def load_manifest(path: Path = MANIFEST) -> list[dict]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ResolveError(
            3,
            {
                "error": "manifest_unavailable",
                "path": str(path),
                "message": f"Cannot read release manifest {path}: {exc}",
            },
        ) from exc

    releases = data.get("releases") if isinstance(data, dict) else None
    if not isinstance(releases, list) or not releases:
        raise ResolveError(
            3,
            {
                "error": "manifest_invalid",
                "path": str(path),
                "message": f"Release manifest {path} must contain a non-empty releases array.",
            },
        )

    records = []
    for item in releases:
        try:
            parsed = parse_version(str(item["version"]))
            backstage = str(item["backstage"])
            node_major = int(item["node_major"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ResolveError(
                3,
                {
                    "error": "manifest_invalid",
                    "path": str(path),
                    "message": f"Release manifest entry is invalid: {item!r}",
                },
            ) from exc
        if parsed is None or parsed["patch"] is not None:
            raise ResolveError(
                3,
                {
                    "error": "manifest_invalid",
                    "path": str(path),
                    "message": f"Release manifest version must be X.Y: {item.get('version')!r}",
                },
            )
        records.append(
            {
                "version": parsed["version"],
                "major": parsed["major"],
                "minor": parsed["minor"],
                "backstage": backstage,
                "node_major": node_major,
                "migration_reference": item.get("migration_reference"),
                "chart_migration": bool(item.get("chart_migration", False)),
            }
        )

    records.sort(key=key)
    seen = [record["version"] for record in records]
    if len(seen) != len(set(seen)):
        raise ResolveError(
            3,
            {
                "error": "manifest_invalid",
                "path": str(path),
                "message": f"Release manifest contains duplicate versions: {seen}",
            },
        )
    return records


def format_ranges(records: list[dict]) -> str:
    groups: list[list[tuple[int, int]]] = []
    for record in records:
        current = key(record)
        if groups and groups[-1][0][0] == current[0] and groups[-1][-1][1] + 1 == current[1]:
            groups[-1].append(current)
        else:
            groups.append([current])

    parts = []
    for group in groups:
        first = f"{group[0][0]}.{group[0][1]}"
        last = f"{group[-1][0]}.{group[-1][1]}"
        parts.append(first if first == last else f"{first}-{last}")
    return ", ".join(parts)


def unknown_target(parsed: dict, records: list[dict]) -> ResolveError:
    latest = records[-1]
    earliest = records[0]
    known = format_ranges(records)
    target = key(parsed)
    update = (
        "If this release is available, update the skill:\n"
        "  npx skills add redhat-developer/rhdh-users-agent-plugin --skill rhdh-upgrade-helper"
    )

    if target > key(latest):
        reason = "newer_than_known"
        message = (
            f"RHDH {parsed['version']} is newer than this skill's bundled release data "
            f"(latest known: {latest['version']}).\n"
            f"Known releases: {known}.\n"
            f"{update}\n"
            "Otherwise choose a released version with --to.\n"
            "Halted before reading any configuration."
        )
    elif target < key(earliest):
        reason = "older_than_known"
        message = (
            f"RHDH {parsed['version']} predates this skill's bundled release data "
            f"(earliest known: {earliest['version']}).\n"
            f"Known releases: {known}.\n"
            "Choose a covered version with --to."
        )
    else:
        reason = "not_a_known_release"
        message = (
            f"RHDH {parsed['version']} is not a release covered by this skill.\n"
            f"Known releases: {known}.\n"
            f"{update}"
        )

    return ResolveError(
        2,
        {
            "error": "unknown_target",
            "reason": reason,
            "requested": parsed["requested"],
            "version": parsed["version"],
            "known_versions": [record["version"] for record in records],
            "earliest": earliest["version"],
            "latest": latest["version"],
            "message": message,
        },
    )


def describe(record: dict, parsed: dict) -> dict:
    notes = NOTES_DIR / f"{record['version']}.md"
    return {
        "requested": parsed["requested"],
        "version": record["version"],
        "known": True,
        "backstage": record["backstage"],
        "node_major": record["node_major"],
        "notes": f"references/release-notes/{record['version']}.md",
        "notes_present": notes.is_file(),
        "migration_reference": record["migration_reference"],
        "chart_migration": record["chart_migration"],
    }


def unknown_source(parsed: dict) -> dict:
    return {
        "requested": parsed["requested"],
        "version": parsed["version"],
        "known": False,
        "backstage": None,
        "node_major": None,
        "notes": None,
        "notes_present": False,
        "migration_reference": None,
        "chart_migration": False,
    }


def backstage_parts(value: str) -> tuple[int, int, int] | None:
    match = re.match(r"^(\d+)\.(\d+)(?:\.(\d+))?$", value.strip())
    if not match:
        return None
    major, minor, patch = match.groups()
    return int(major), int(minor), int(patch) if patch is not None else 0


def previous_version(record: dict) -> dict:
    if record["minor"] > 0:
        minor = record["minor"] - 1
        return {
            "requested": f"{record['major']}.{minor}",
            "major": record["major"],
            "minor": minor,
            "patch": None,
            "version": f"{record['major']}.{minor}",
        }
    major = record["major"] - 1
    return {
        "requested": f"{major}.0",
        "major": major,
        "minor": 0,
        "patch": None,
        "version": f"{major}.0",
    }


def resolve(to_raw: str | None, from_raw: str | None) -> dict:
    if to_raw is None:
        raise ResolveError(
            1,
            {
                "error": "missing_target",
                "message": "--to is required (for example, --to 1.10).",
            },
        )

    to_parsed = parse_version(to_raw)
    if to_parsed is None:
        raise ResolveError(
            1,
            {
                "error": "invalid_version",
                "requested": to_raw,
                "message": (
                    f"Invalid release '{to_raw}'; expected X.Y or X.Y.Z (for example, 1.10)."
                ),
            },
        )

    from_parsed = None
    if from_raw is not None:
        from_parsed = parse_version(from_raw)
        if from_parsed is None:
            raise ResolveError(
                1,
                {
                    "error": "invalid_version",
                    "requested": from_raw,
                    "message": (
                        f"Invalid release '{from_raw}'; expected X.Y or X.Y.Z (for example, 1.9)."
                    ),
                },
            )

    records = load_manifest()
    by_version = {record["version"]: record for record in records}

    target = by_version.get(to_parsed["version"])
    if target is None:
        raise unknown_target(to_parsed, records)

    default_from = False
    if from_parsed is None:
        default_from = True
        index = records.index(target)
        if index == 0:
            from_parsed = previous_version(target)
        else:
            from_parsed = {
                "requested": records[index - 1]["version"],
                "major": records[index - 1]["major"],
                "minor": records[index - 1]["minor"],
                "patch": None,
                "version": records[index - 1]["version"],
            }

    if key(from_parsed) >= key(target):
        raise ResolveError(
            4,
            {
                "error": "invalid_range",
                "message": (
                    f"--from {from_parsed['requested']} must be older than "
                    f"--to {to_parsed['requested']}."
                ),
            },
        )

    source = by_version.get(from_parsed["version"])
    target_info = describe(target, to_parsed)
    source_info = describe(source, from_parsed) if source else unknown_source(from_parsed)

    gaps = []
    if not source_info["known"]:
        gaps.append("from_version_unknown")
    elif not source_info["notes_present"]:
        gaps.append("from_notes_missing")
    if not target_info["notes_present"]:
        gaps.append("target_notes_missing")

    backstage_jump = None
    if source_info["known"] and source_info["backstage"] and target_info["backstage"]:
        source_bs = backstage_parts(source_info["backstage"])
        target_bs = backstage_parts(target_info["backstage"])
        if source_bs and target_bs and source_bs[0] == target_bs[0]:
            backstage_jump = target_bs[1] - source_bs[1]

    node_jump = None
    if source_info["known"] and source_info["node_major"] is not None:
        node_jump = target_info["node_major"] - source_info["node_major"]

    if source_info["known"]:
        start = records.index(source) + 1
    else:
        start = 0
    release_range = [record["version"] for record in records[start:] if key(record) <= key(target)]

    result = {
        "to": target_info,
        "from": source_info,
        "default_from": default_from,
        "backstage_minor_jump": backstage_jump,
        "node_major_jump": node_jump,
        "is_major_upgrade": from_parsed["major"] != target["major"],
        "from_dependent_checks_available": source_info["known"],
        "release_range": release_range,
        "gaps": gaps,
    }
    if default_from and not source_info["known"]:
        result["default_from_unknown"] = True
    return result


def print_human(result: dict) -> None:
    target = result["to"]
    source = result["from"]
    requested = (
        f" (requested {target['requested']})" if target["requested"] != target["version"] else ""
    )
    print(f"Target: RHDH {target['version']}{requested}")
    print(
        f"  Backstage {target['backstage']} | Node.js {target['node_major']} "
        f"| notes: {target['notes']}"
    )
    if source["known"]:
        label = "default" if result["default_from"] else "requested"
        print(f"Source: RHDH {source['version']} ({label})")
        print(f"  Backstage {source['backstage']} | Node.js {source['node_major']}")
    else:
        label = "default" if result["default_from"] else "requested"
        print(f"Source: RHDH {source['requested']} ({label}, no bundled data)")
    print(
        "Jumps: "
        f"Backstage {result['backstage_minor_jump'] if result['backstage_minor_jump'] is not None else 'n/a'} minor, "
        f"Node.js {result['node_major_jump'] if result['node_major_jump'] is not None else 'n/a'} major, "
        f"major upgrade: {'yes' if result['is_major_upgrade'] else 'no'}"
    )
    print(f"Release notes to load: {', '.join(result['release_range']) or 'none'}")
    print(f"Gaps: {', '.join(result['gaps']) or 'none'}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Resolve RHDH release versions against the bundled release manifest."
    )
    parser.add_argument("--to", help="Target RHDH release (X.Y or X.Y.Z)")
    parser.add_argument("--from", dest="from_version", help="Source RHDH release")
    parser.add_argument("--json", action="store_true", help="Emit JSON")
    args = parser.parse_args()

    try:
        result = resolve(args.to, args.from_version)
    except ResolveError as exc:
        if args.json:
            print(json.dumps(exc.payload, indent=2))
        else:
            print(exc.payload.get("message", str(exc)), file=sys.stderr)
        return exc.code

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print_human(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
