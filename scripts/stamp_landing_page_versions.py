#!/usr/bin/env python3
"""Stamps the landing page's version badges and Windows download link.

    python scripts/stamp_landing_page_versions.py _site/index.html

Online reflects this checkout's pyproject.toml (the bundle is built from the same checkout).
Windows is the newest GitHub Release that has a win64 zip attached; the asset name carries the
version (FullThrustFleetManager-0.1.1-win64.zip), so the link is read from the API rather than
guessed. If the API is unreachable the download button keeps its fallback, the releases page.
Substitution is by stable markers, so running it twice is harmless.
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


def latest_windows_asset(releases: list[dict]) -> tuple[str, str] | None:
    """(version, download url) of the newest non-draft release with a win64 zip."""
    for rel in releases:
        if rel.get("draft"):
            continue
        for asset in rel.get("assets", []):
            if str(asset.get("name", "")).endswith("-win64.zip"):
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


def main() -> None:
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "web" / "landing.html"
    html = target.read_text(encoding="utf-8")
    html = stamp_badge(html, "online", online_version())
    summary = [f"online=v{online_version()}"]
    try:
        windows = latest_windows_asset(_fetch_releases())
    except OSError as err:
        print(f"warning: couldn't fetch releases ({err}); leaving the Windows badge and link as-is",
              file=sys.stderr)
        windows = None
    if windows:
        version, url = windows
        html = stamp_badge(html, "windows", version)
        html = stamp_download(html, "windows", url)
        summary.append(f"windows=v{version}")
    target.write_text(html, encoding="utf-8")
    print(f"Stamped {target}: " + ", ".join(summary))


if __name__ == "__main__":
    main()
