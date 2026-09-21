#!/usr/bin/env python3
"""Stamps the landing page's version badges and download links.

    python scripts/stamp_landing_page_versions.py _site/index.html

Online reflects this checkout's pyproject.toml (the bundle is built from the same checkout).
Windows and Linux are each the newest GitHub Release carrying that platform's asset, read from
the API rather than guessed. Linux matters most here: those builds are occasional rather than one
per version, so the button has to point at whichever release actually has a tarball instead of at
"latest", and the card is dropped entirely until one does. If the API is unreachable, everything
is left exactly as the page already had it. Substitution is by stable markers, so running it
twice is harmless.
"""
from __future__ import annotations

import json
import os
import re
import sys
import tomllib
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO = "TheRealDeltrex/FullThrustFleetManager"

# Landing-page marker -> the suffix that platform's release asset name ends with.
PLATFORMS = {"windows": "-win64.zip", "linux": "-linux-x64.tar.gz"}


def online_version() -> str:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return str(data["project"]["version"])


def _fetch_releases() -> list[dict]:
    req = urllib.request.Request(f"https://api.github.com/repos/{REPO}/releases?per_page=30")
    req.add_header("Accept", "application/vnd.github+json")
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def latest_asset(releases: list[dict], suffix: str) -> tuple[str, str] | None:
    """(version, download url) of the newest non-draft release carrying an asset with `suffix`."""
    for rel in releases:
        if rel.get("draft"):
            continue
        for asset in rel.get("assets", []):
            if str(asset.get("name", "")).endswith(suffix):
                return str(rel.get("tag_name", "")).removeprefix("v"), asset["browser_download_url"]
    return None


def stamp_badge(html: str, key: str, value: str) -> str:
    pattern = re.compile(rf'(data-version-badge="{key}">)[^<]*(</span>)')
    new_html, n = pattern.subn(rf"\g<1>v{value}\g<2>", html)
    if n == 0:
        print(f'warning: no data-version-badge="{key}" marker found', file=sys.stderr)
    return new_html


def stamp_download(html: str, key: str, url: str) -> str:
    pattern = re.compile(rf'(data-download="{key}"\s+href=")[^"]*(")')
    new_html, n = pattern.subn(lambda m: m.group(1) + url + m.group(2), html)
    if n == 0:
        print(f'warning: no data-download="{key}" marker found', file=sys.stderr)
    return new_html


def drop_card(html: str, key: str) -> str:
    """Removes a download card the site has no build for.

    A card left standing would show a version badge reading vDEV over a button that only reaches
    the releases page, which is worse than not offering the platform at all. The card grid is
    auto-fit, so what is left closes up behind it.
    """
    marker = rf'<div class="card" data-platform-card="{key}">'
    pattern = re.compile(r"\s*" + marker + r".*?\n      </div>\n", re.S)
    new_html, n = pattern.subn("", html)
    if n == 0:
        print(f'warning: no data-platform-card="{key}" to drop', file=sys.stderr)
    return new_html


def main() -> None:
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "web" / "landing.html"
    html = target.read_text(encoding="utf-8")
    html = stamp_badge(html, "online", online_version())
    summary = [f"online=v{online_version()}"]
    try:
        releases = _fetch_releases()
    except OSError as err:
        # A momentary outage must not silently un-advertise a platform that does have a build,
        # so nothing is stamped and nothing is dropped.
        print(f"warning: couldn't fetch releases ({err}); leaving the download cards as-is",
              file=sys.stderr)
        releases = []
    for key, suffix in PLATFORMS.items():
        found = latest_asset(releases, suffix) if releases else None
        if not found:
            if releases:
                html = drop_card(html, key)
                summary.append(f"{key}=dropped, no {suffix} on any release")
            continue
        version, url = found
        html = stamp_badge(html, key, version)
        html = stamp_download(html, key, url)
        summary.append(f"{key}=v{version}")
    target.write_text(html, encoding="utf-8")
    print(f"Stamped {target}: " + ", ".join(summary))


if __name__ == "__main__":
    main()
