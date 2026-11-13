#!/usr/bin/env python3
"""Generate RHDH release-notes markdown from the official Red Hat documentation.

docs.redhat.com rejects lynx, curl, and headless browsers with HTTP 403, so the
fetch uses curl_cffi's Chrome TLS impersonation (install with
`uv sync --extra release-notes`). Parsing uses only the standard library.

Usage:
    generate-release-notes.py --release 2.1
    generate-release-notes.py --all
    generate-release-notes.py --all --check
"""

from __future__ import annotations

import argparse
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

DOCS_URL = "https://docs.redhat.com/en/documentation/red_hat_developer_hub"
DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / "references" / "release-notes"

SECTIONS = (
    ("new_features_and_enhancements", "New features and enhancements"),
    ("technology_preview_features", "Technology Preview features"),
    ("developer_preview", "Developer Preview features"),
    ("deprecated_features", "Deprecated features"),
    ("removed_features", "Removed features (breaking changes)"),
    ("known_issues", "Known issues"),
    ("fixed_issues", "Fixed issues (upgrade-relevant)"),
    ("fixed_security_issues", "Security advisories"),
)
SECTION_SLUGS = {slug for slug, _ in SECTIONS}
LONG_BODY_SLUGS = {"known_issues", "fixed_issues", "removed_features"}
BODY_LIMIT = {"known_issues": 900, "fixed_issues": 900, "removed_features": 700}
DEFAULT_BODY_LIMIT = 500
TICKET_RE = re.compile(r"RHDHBUGS-\d+")
TEXT_TAGS = {"h1", "h2", "h3", "p", "li"}


class FetchError(RuntimeError):
    """Raised when a documentation page cannot be retrieved."""


class _ArticleParser(HTMLParser):
    """Collect headings and prose from the <article> element only."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.events: list[tuple[str, str]] = []
        self._in_article = False
        self._skip_depth = 0
        self._capture: str | None = None
        self._buffer: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "article" and dict(attrs).get("role") == "article":
            self._in_article = True
            return
        if not self._in_article:
            return
        if tag in {"script", "style", "svg"}:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if tag in TEXT_TAGS and self._capture is None:
            self._capture = tag
            self._buffer = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "article":
            self._in_article = False
            return
        if not self._in_article:
            return
        if tag in {"script", "style", "svg"} and self._skip_depth:
            self._skip_depth -= 1
            return
        if tag == self._capture:
            text = clean_text("".join(self._buffer))
            if text:
                self.events.append((tag, text))
            self._capture = None
            self._buffer = []

    def handle_data(self, data: str) -> None:
        if self._in_article and self._capture is not None:
            self._buffer.append(data)


def clean_text(value: str) -> str:
    """Collapse whitespace and drop the copy-link widget text the docs theme adds."""
    text = re.sub(r"\[\s*\]|\(\s*\)", " ", value)
    text = re.sub(r"Copy link\s*Link copied!|Link copied!|Copy link", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def parse_article(html: str) -> tuple[str | None, list[str], list[dict], list[str]]:
    """Return the article title, intro paragraphs, h2 items, and orphan bullets."""
    parser = _ArticleParser()
    parser.feed(html)
    parser.close()

    title: str | None = None
    intro: list[str] = []
    overflow: list[str] = []
    items: list[dict] = []
    current: dict | None = None

    for kind, text in parser.events:
        if kind == "h1":
            if title is None:
                title = text
            continue
        if kind == "h2":
            current = {"title": text, "paragraphs": [], "bullets": [], "tickets": []}
            items.append(current)
            continue
        if kind == "h3":
            continue
        if current is None:
            if kind == "p" and text.lower() != "additional resources":
                intro.append(text)
            elif kind == "li":
                overflow.append(text)
            continue
        if kind == "p":
            if text.lower() != "additional resources":
                current["paragraphs"].append(text)
        elif kind == "li":
            if TICKET_RE.fullmatch(text):
                current["tickets"].append(text)
            else:
                current["bullets"].append(text)

    return title, intro, items, overflow


def limit_body(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0].rstrip(",;:")
    return f"{cut}…"


def render_item(item: dict, slug: str) -> str:
    """Render one section item as a bullet, keeping tickets and workarounds."""
    has_workaround = any(line.lower() == "workaround" for line in item["paragraphs"])
    paragraphs = [line for line in item["paragraphs"] if line.lower() != "workaround"]
    if slug in LONG_BODY_SLUGS:
        parts = paragraphs[:2] + item["bullets"][:4]
    else:
        parts = paragraphs[:1] + item["bullets"][:2]
    if has_workaround:
        parts.insert(
            len(paragraphs[:2]) if slug in LONG_BODY_SLUGS else len(paragraphs[:1]), "Workaround:"
        )
    body = limit_body(" ".join(parts), BODY_LIMIT.get(slug, DEFAULT_BODY_LIMIT))
    body = body.rstrip(":;, ")
    tickets = sorted(
        set(
            item.get("tickets", [])
            + TICKET_RE.findall(" ".join(item["paragraphs"] + item["bullets"]))
        )
    )
    suffix = f" ({', '.join(tickets)})" if tickets else ""
    if not body:
        return ""
    return f"- **{item['title']}**{suffix}: {body}"


def render_section(html: str, slug: str) -> str:
    _, intro, items, overflow = parse_article(html)
    bullets = [render_item(item, slug) for item in items]
    bullets = [bullet for bullet in bullets if bullet]
    if bullets:
        return "\n".join(bullets)
    text = " ".join(intro + overflow).strip()
    if not text:
        return "Not published for this release."
    return limit_body(text, BODY_LIMIT.get(slug, DEFAULT_BODY_LIMIT))


def build_release(
    version: str, landing_url: str, landing_html: str, sections: dict[str, str]
) -> str:
    """Assemble the release-notes markdown for one version."""
    _, intro, _, _ = parse_article(landing_html)
    summary = next((line for line in intro if len(line) > 40), "")
    header = [f"# RHDH {version} Release Notes", ""]
    if summary:
        header += [limit_body(summary, 320), ""]
    header += [
        f"Generated from the official Red Hat documentation: <{landing_url}>",
        "",
        "Regenerate with `scripts/generate-release-notes.py --release "
        f"{version}`. Do not edit by hand.",
        "",
    ]

    body: list[str] = []
    for slug, heading in SECTIONS:
        text = sections.get(slug) or "Not published for this release."
        body.append(f"## {heading}\n\n{text.strip()}\n")
    return "\n".join(header) + "\n" + "\n".join(body).rstrip() + "\n"


def discover_sections(landing_html: str, version: str) -> dict[str, str]:
    """Map section slugs to their page URLs from the landing page."""
    found = {}
    for slug in re.findall(r"whats_new-([a-z_]+)", landing_html):
        if slug in SECTION_SLUGS:
            found[slug] = f"{DOCS_URL}/{version}/whats_new-{slug}"
    return found


def discover_versions(product_html: str, min_major: int = 2) -> list[str]:
    """Return published versions with at least `min_major`, newest last."""
    versions = {
        f"{major}.{minor}"
        for major, minor in re.findall(r"red_hat_developer_hub/(\d+)\.(\d+)", product_html)
        if int(major) >= min_major
    }
    return sorted(versions, key=lambda value: tuple(int(part) for part in value.split(".")))


def fetch(url: str) -> str:
    """Fetch a documentation page through Chrome TLS impersonation."""
    try:
        from curl_cffi import requests
    except ImportError as exc:  # pragma: no cover - exercised only without the extra
        raise SystemExit(
            "curl_cffi is required to fetch release notes (docs.redhat.com rejects plain "
            "clients). Install it with: uv sync --extra release-notes"
        ) from exc

    response = requests.get(url, impersonate="chrome", timeout=60)
    if response.status_code != 200:
        raise FetchError(f"{url} returned HTTP {response.status_code}")
    if "<main" not in response.text:
        raise FetchError(f"{url} did not return a documentation page")
    return response.text


def generate(version: str, docs_url: str, output_dir: Path, check: bool) -> bool:
    """Generate one release file. Return True when the file changed."""
    landing_url = f"{docs_url}/{version}/whats_new-red_hat_developer_hub_release_notes"
    landing_html = fetch(landing_url)
    section_urls = discover_sections(landing_html, version)
    missing = [slug for slug, _ in SECTIONS if slug not in section_urls]
    for slug in missing:
        print(f"warning: {version} has no {slug} page", file=sys.stderr)

    sections = {}
    for slug, _ in SECTIONS:
        url = section_urls.get(slug)
        sections[slug] = render_section(fetch(url), slug) if url else ""

    content = build_release(version, landing_url, landing_html, sections)
    target = output_dir / f"{version}.md"
    current = target.read_text(encoding="utf-8") if target.exists() else None
    if current == content:
        print(f"{version}: up to date")
        return False
    if check:
        print(f"{version}: out of date ({target})", file=sys.stderr)
        return True

    output_dir.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".md.tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(target)
    print(f"{version}: wrote {target}")
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--release", action="append", default=[], help="version to generate, e.g. 2.1"
    )
    parser.add_argument("--all", action="store_true", help="generate every published 2.x+ release")
    parser.add_argument("--check", action="store_true", help="exit 1 when a file would change")
    parser.add_argument("--docs-url", default=DOCS_URL)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--min-major", type=int, default=2)
    args = parser.parse_args(argv)

    versions = list(args.release)
    if args.all:
        versions += discover_versions(fetch(args.docs_url), args.min_major)
    if not versions:
        parser.error("pass --release X.Y or --all")

    changed = False
    for version in dict.fromkeys(versions):
        try:
            changed |= generate(version, args.docs_url, args.output_dir, args.check)
        except FetchError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
    return 1 if args.check and changed else 0


if __name__ == "__main__":
    raise SystemExit(main())
