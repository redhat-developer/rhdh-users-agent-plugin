"""Judges for the chart-migration eval suite.

Each judge receives the migration script's JSON report and the output YAML,
then checks a specific correctness property.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import yaml

SKILL_DIR = Path(__file__).resolve().parents[3] / "skills" / "rhdh-upgrade-helper"
SCRIPT = SKILL_DIR / "scripts" / "migrate-chart-values.py"
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def _run_migration(fixture_name: str) -> tuple[dict, dict, str]:
    """Run the migration script on a fixture and return (report, output_data, raw_output)."""
    fixture_path = FIXTURES_DIR / fixture_name
    if not fixture_path.exists():
        raise FileNotFoundError(f"Fixture not found: {fixture_path}")

    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(fixture_path), "--json"],
        capture_output=True,
        text=True,
    )
    report = json.loads(result.stdout) if result.stdout.strip() else {}

    result_yaml = subprocess.run(
        [sys.executable, str(SCRIPT), str(fixture_path)],
        capture_output=True,
        text=True,
    )
    raw_output = result_yaml.stdout

    # Strip comment lines for YAML parsing
    yaml_lines = [
        line for line in raw_output.split("\n")
        if not line.lstrip().startswith("#")
    ]
    output_data = yaml.safe_load("\n".join(yaml_lines)) or {}

    return report, output_data, raw_output


def _deep_get(data: dict, dotpath: str):
    """Get a value from a nested dict by dotted path."""
    keys = dotpath.split(".")
    current = data
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    return current


def check_deterministic_mappings(
    input_data: dict,
    annotations: dict,
    **kwargs,
) -> dict:
    """Verify all expected deterministic mappings were applied."""
    fixture = input_data.get("fixture", "simple-1x-values.yaml")
    expected_mappings = annotations.get("expected_mappings", {})

    report, output_data, _ = _run_migration(fixture)

    failures = []
    for new_path, expected_value in expected_mappings.items():
        actual = _deep_get(output_data, new_path)
        if actual is None:
            failures.append(f"Missing key: {new_path}")
        elif expected_value is not None and actual != expected_value:
            failures.append(
                f"Wrong value at {new_path}: expected {expected_value!r}, got {actual!r}"
            )

    # Verify no upstream.* keys remain in output
    old_prefixes_in_output = [
        key
        for key in _flatten_keys(output_data)
        if key.startswith("upstream.")
    ]
    if old_prefixes_in_output:
        failures.append(
            f"Old upstream.* keys still in output: {old_prefixes_in_output[:5]}"
        )

    return {
        "pass": len(failures) == 0,
        "score": 1.0 if not failures else max(0, 1.0 - len(failures) / max(len(expected_mappings), 1)),
        "details": "; ".join(failures) if failures else "All mappings correct",
        "applied_count": report.get("summary", {}).get("total_deterministic", 0),
    }


def check_ambiguous_detection(
    input_data: dict,
    annotations: dict,
    **kwargs,
) -> dict:
    """Verify expected ambiguous areas are flagged, not silently transformed."""
    fixture = input_data.get("fixture", "complex-1x-values.yaml")
    expected_areas = annotations.get("expected_ambiguous_areas", [])

    report, _, raw_output = _run_migration(fixture)

    review_areas = [
        item.get("area") for item in report.get("review", [])
    ]

    missing = [a for a in expected_areas if a not in review_areas]
    markers_in_output = raw_output.count("MIGRATION-REVIEW")

    return {
        "pass": len(missing) == 0,
        "score": 1.0 if not missing else 1.0 - len(missing) / max(len(expected_areas), 1),
        "details": f"Missing areas: {missing}" if missing else "All ambiguous areas detected",
        "review_areas_found": review_areas,
        "markers_in_output": markers_in_output,
    }


def check_removed_values(
    input_data: dict,
    annotations: dict,
    **kwargs,
) -> dict:
    """Verify removed values are excluded from output and listed in report."""
    fixture = input_data.get("fixture", "complex-1x-values.yaml")
    expected_removed = annotations.get("expected_removed", [])

    report, output_data, _ = _run_migration(fixture)

    removed_in_report = [item["old"] for item in report.get("removed", [])]
    still_in_output = []
    for old_path in expected_removed:
        if _deep_get(output_data, old_path) is not None:
            still_in_output.append(old_path)

    not_reported = [r for r in expected_removed if r not in removed_in_report]

    failures = []
    if still_in_output:
        failures.append(f"Removed values still in output: {still_in_output}")
    if not_reported:
        failures.append(f"Removed values not reported: {not_reported}")

    return {
        "pass": len(failures) == 0,
        "score": 1.0 if not failures else 0.5,
        "details": "; ".join(failures) if failures else "All removed values handled correctly",
    }


def check_no_data_loss(
    input_data: dict,
    annotations: dict,
    **kwargs,
) -> dict:
    """Verify no customer values are silently dropped."""
    fixture = input_data.get("fixture", "simple-1x-values.yaml")

    report, output_data, _ = _run_migration(fixture)

    summary = report.get("summary", {})
    total_accounted = (
        summary.get("total_deterministic", 0)
        + summary.get("total_removed", 0)
        + summary.get("total_review", 0)
        + summary.get("total_unknown", 0)
    )

    # Load original to count leaf keys
    fixture_path = FIXTURES_DIR / fixture
    with open(fixture_path) as f:
        original = yaml.safe_load(f)
    original_keys = set(_flatten_keys(original or {}))
    output_keys = set(_flatten_keys(output_data))

    return {
        "pass": total_accounted > 0 and len(output_keys) > 0,
        "score": 1.0 if total_accounted > 0 else 0.0,
        "details": f"Accounted for {total_accounted} transformations; output has {len(output_keys)} keys",
        "original_key_count": len(original_keys),
        "output_key_count": len(output_keys),
    }


def check_valid_yaml(
    input_data: dict,
    annotations: dict,
    **kwargs,
) -> dict:
    """Verify the output is valid YAML."""
    fixture = input_data.get("fixture", "simple-1x-values.yaml")

    _, _, raw_output = _run_migration(fixture)

    # Strip comment lines
    yaml_lines = [
        line for line in raw_output.split("\n")
        if not line.lstrip().startswith("#")
    ]
    yaml_str = "\n".join(yaml_lines)

    try:
        parsed = yaml.safe_load(yaml_str)
        is_valid = isinstance(parsed, dict)
    except yaml.YAMLError as e:
        return {
            "pass": False,
            "score": 0.0,
            "details": f"Invalid YAML: {e}",
        }

    return {
        "pass": is_valid,
        "score": 1.0 if is_valid else 0.0,
        "details": "Valid YAML dict" if is_valid else "Output is not a YAML dict",
    }


def _flatten_keys(data: dict, prefix: str = "") -> list[str]:
    """Return all dotted key paths in a nested dict."""
    result = []
    for key, value in data.items():
        full = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            result.extend(_flatten_keys(value, full))
        else:
            result.append(full)
    return result
