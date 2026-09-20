#!/usr/bin/env python3
"""Bundle the app's Python modules, templates, data and translations into web/bundle.json for the
Pyodide web build.

web/index.html loads Pyodide, installs Flask + fpdf2, writes these files into an in-memory
filesystem, sets FTFM_BROWSER=1 and FTFM_DATA_DIR=/data, then drives the real Flask app through
its test client: the web build runs the same rules engine as the desktop app. The shell
snapshots /data to localStorage after each mutating request and restores it at boot.

Only text travels through bundle.json. static/ (CSS, JS) is also bundled because the shell
inlines it into each rendered page; binary assets and the rulebook PDFs are deployed next to
index.html as plain files by .github/workflows/deploy-pages.yml.

Build from devversion in CI, never by hand onto another branch: Frostgrave once kept a second,
hand-copied shell on main that silently lost its localStorage code.

    python scripts/build_browser_bundle.py
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "web" / "bundle.json"
SHELL = ROOT / "web" / "index.html"

# Matches the shell's bundle.json fetch URL whatever version it currently carries, so the
# substitution is idempotent across builds.
BUNDLE_VERSION_RE = re.compile(r'(bundle\.json\?v=)[^"]*')

# Desktop-only modules (tray.py, run_app.py) stay out; idle_watchdog is imported by app.py.
EXCLUDED_MODULES = {"tray.py", "run_app.py"}

# Text files the shell inlines into pages. Every <script>/<link> base.html pulls from static/
# must be a text file here, or the page's absolute "/static/..." URL 404s inside the srcdoc.
STATIC_SUFFIXES = {".css", ".js"}


def python_modules() -> list[Path]:
    mods = [p for p in sorted(ROOT.glob("*.py")) if p.name not in EXCLUDED_MODULES]
    mods += sorted((ROOT / "rulesets").rglob("*.py"))
    return mods


def collect() -> dict[str, str]:
    files: dict[str, str] = {}

    def add(path: Path) -> None:
        files[path.relative_to(ROOT).as_posix()] = path.read_text(encoding="utf-8")

    for p in python_modules():
        add(p)
    for p in sorted((ROOT / "templates").rglob("*.html")):
        add(p)
    for p in sorted((ROOT / "data").rglob("*.json")):
        add(p)
    for p in sorted((ROOT / "translations").glob("*.json")):
        add(p)
    for p in sorted((ROOT / "static").rglob("*")):
        # Vendored pdf.js is megabytes of third-party code that the viewer loads from its own
        # URL, not from a page the shell renders: it is copied next to index.html instead.
        if p.is_file() and p.suffix in STATIC_SUFFIXES and "pdfjs" not in p.parts:
            add(p)
    add(ROOT / "pyproject.toml")
    return files


def update_bundle_version(bundle_bytes: bytes) -> str:
    """Stamps the shell's bundle.json URL with a content hash, so Pages' HTTP caching works and
    the URL changes only when the bundle does."""
    version = hashlib.sha256(bundle_bytes).hexdigest()[:12]
    html = SHELL.read_text(encoding="utf-8")
    new_html, n = BUNDLE_VERSION_RE.subn(rf"\g<1>{version}", html)
    if n == 0:
        raise RuntimeError(f"Could not find the bundle.json version placeholder in {SHELL}")
    SHELL.write_text(new_html, encoding="utf-8")
    return version


def main() -> None:
    files = collect()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "files": files,
    }
    bundle_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    OUT.write_bytes(bundle_bytes)

    total = sum(len(v) for v in files.values())
    print(f"Wrote {OUT}: {len(files)} files, {total / 1024:.0f} KB uncompressed.")
    for name in files:
        print(f"  {name}")
    print(f"Stamped {SHELL} with bundle version {update_bundle_version(bundle_bytes)}")


if __name__ == "__main__":
    main()
