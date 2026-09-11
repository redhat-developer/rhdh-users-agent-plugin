#!/usr/bin/env bash
# Extract the shipped RHDH catalog-index image, with an overlay Git fallback.
# Usage: extract-catalog-index.sh <release> [--tag TAG]
# Output: the extracted data directory on stdout.

set -euo pipefail

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  sed -n '2,5p' "$0" | sed 's/^# //'
  exit 0
fi

RELEASE="${1:?Usage: extract-catalog-index.sh <release> [--tag TAG]}"
TAG=""
PLATFORM="${RHDH_IMAGE_PLATFORM:-linux/amd64}"

if [[ ! "$RELEASE" =~ ^[0-9]+\.[0-9]+$ ]]; then
  echo "Invalid release '$RELEASE'; expected X.Y (for example, 1.10 or 2.1)." >&2
  exit 1
fi

shift
while [[ $# -gt 0 ]]; do
  case "$1" in
    --tag) TAG="${2:?--tag requires a value}"; shift 2 ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

if [[ -n "$TAG" && ! "$TAG" =~ ^[A-Za-z0-9_][A-Za-z0-9_.-]*$ ]]; then
  echo "Invalid image tag '$TAG'." >&2
  exit 1
fi

CATALOG_DIR="${TMPDIR:-/tmp}/rhdh-catalog-index-${RELEASE}"
OVERLAY_DIR="${TMPDIR:-/tmp}/rhdh-overlays-${RELEASE}"
IMAGE=""
MARKER="$CATALOG_DIR/.extraction"

if [[ -n "$TAG" ]]; then
  IMAGE="quay.io/rhdh/plugin-catalog-index:${TAG}"
fi

write_marker() {
  local extractor="$1"
  {
    printf 'complete=true\n'
    printf 'source=%s\n' "$extractor"
    printf 'image=%s\n' "$IMAGE"
    printf 'platform=%s\n' "$PLATFORM"
  } > "$MARKER"
}

cached_catalog_is_valid() {
  [[ -f "$CATALOG_DIR/index.json" && -f "$MARKER" ]] || return 1
  grep -Fqx 'complete=true' "$MARKER" || return 1
  grep -Fqx "platform=$PLATFORM" "$MARKER" || return 1
  if [[ -n "$TAG" ]]; then
    grep -Fqx "image=$IMAGE" "$MARKER"
  else
    grep -q '^image=quay.io/rhdh/plugin-catalog-index:' "$MARKER"
  fi
}

discover_tag() {
  command -v curl >/dev/null 2>&1 || return 1
  command -v python3 >/dev/null 2>&1 || return 1

  TAG=$(curl --fail --silent --show-error --location --max-time 15 \
    "https://quay.io/api/v1/repository/rhdh/plugin-catalog-index/tag/?limit=20&filter_tag_name=like:${RELEASE}" |
    python3 -c '
import json
import sys

data = json.load(sys.stdin)
tags = sorted(
    [tag["name"] for tag in data.get("tags", [])
     if "-" in tag["name"] and tag["name"].split("-")[-1].isdigit()],
    key=lambda value: int(value.split("-")[-1]),
)
print(tags[-1] if tags else "")
' 2>/dev/null)
  [[ -n "$TAG" ]]
}

extract_with_oc() {
  command -v oc >/dev/null 2>&1 || return 1
  rm -rf "$CATALOG_DIR"
  mkdir -p "$CATALOG_DIR"
  if oc image extract "$IMAGE" --path "/:$CATALOG_DIR" \
    --filter-by-os="$PLATFORM" --confirm >/dev/null 2>&1 \
    && [[ -f "$CATALOG_DIR/index.json" ]]; then
    write_marker oc
    return 0
  fi
  rm -rf "$CATALOG_DIR"
  return 1
}

extract_with_container_runtime() {
  local runtime="$1"
  local container="rhdh-extract-${RELEASE}-$$"

  command -v "$runtime" >/dev/null 2>&1 || return 1
  rm -rf "$CATALOG_DIR"
  if "$runtime" pull --platform "$PLATFORM" "$IMAGE" >/dev/null 2>&1 \
    && "$runtime" create --name "$container" --platform "$PLATFORM" "$IMAGE" >/dev/null 2>&1 \
    && mkdir -p "$CATALOG_DIR" \
    && "$runtime" cp "${container}:/" "$CATALOG_DIR/" >/dev/null 2>&1 \
    && [[ -f "$CATALOG_DIR/index.json" ]]; then
    "$runtime" rm "$container" >/dev/null 2>&1 || true
    write_marker "$runtime"
    return 0
  fi
  "$runtime" rm "$container" >/dev/null 2>&1 || true
  rm -rf "$CATALOG_DIR"
  return 1
}

if cached_catalog_is_valid; then
  echo "$CATALOG_DIR"
  exit 0
fi

if [[ -z "$TAG" ]] && ! discover_tag; then
  echo "Could not discover a catalog image tag for release ${RELEASE}." >&2
  TAG=""
fi

if [[ -n "$TAG" ]]; then
  IMAGE="quay.io/rhdh/plugin-catalog-index:${TAG}"
  echo "Extracting ${IMAGE} with available image tools..." >&2
  if extract_with_oc || extract_with_container_runtime podman || extract_with_container_runtime docker; then
    echo "$CATALOG_DIR"
    exit 0
  fi
  echo "Catalog image extraction failed. Falling back to overlay repo." >&2
fi

if [[ -d "$OVERLAY_DIR" && -f "$OVERLAY_DIR/versions.json" ]]; then
  printf 'source=overlay-git\n' > "$OVERLAY_DIR/.extraction"
  echo "$OVERLAY_DIR"
  exit 0
fi

if [[ -e "$OVERLAY_DIR" ]]; then
  echo "Existing overlay directory is incomplete: ${OVERLAY_DIR}." >&2
  exit 1
fi

echo "Cloning overlay repo (release-${RELEASE}) to ${OVERLAY_DIR}..." >&2
CLONE_DIR="${OVERLAY_DIR}.tmp.$$"
if ! git clone --depth 1 --branch "release-${RELEASE}" \
  https://github.com/redhat-developer/rhdh-plugin-export-overlays.git \
  "$CLONE_DIR" 2>/dev/null; then
  rm -rf "$CLONE_DIR"
  echo "Failed to clone overlay repo for release ${RELEASE}." >&2
  exit 1
fi

if [[ ! -f "$CLONE_DIR/versions.json" || ! -d "$CLONE_DIR/workspaces" ]]; then
  rm -rf "$CLONE_DIR"
  echo "Overlay clone is missing versions.json or workspaces/." >&2
  exit 1
fi

mv "$CLONE_DIR" "$OVERLAY_DIR"
printf 'source=overlay-git\n' > "$OVERLAY_DIR/.extraction"
echo "$OVERLAY_DIR"
