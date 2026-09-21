#!/usr/bin/env python3
"""Builds the static "See it in action" pages the landing page links to.

    python scripts/build_preview_pages.py _site

Drives the real app through its Flask test client rather than hand-writing approximate markup,
so a preview cannot drift from what the templates and the rules engine actually produce: the
record sheet on preview-design.html is the same SVG the app and the PDF draw (PLAN 10.1).

The pages are written beside the landing page and read the app's own stylesheet and assets from
app/static/, so the site carries one copy of each and there is nothing to keep in sync. The demo
fleet is built in a throwaway temp directory via FTFM_DATA_DIR and never touches real user data.

Written, not committed: deploy-pages.yml runs this into _site/ on every deploy.
"""
from __future__ import annotations

import os
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Before importing the app, so the demo fleet can only ever land in scratch space.
os.environ["FTFM_DATA_DIR"] = tempfile.mkdtemp(prefix="ftfm-preview-")

sys.path.insert(0, str(ROOT))
import app as app_module  # noqa: E402
import store  # noqa: E402

client = app_module.app.test_client()

# A Kra'Vak battleship for the workbench: K-guns, scattergun and its own icon set, which is the
# most the sheet has to say. The fleet is human, so between them the two pages show both.
DESIGN_ID = "fb:fb2:kv-ko-vol"
FLEET_SHIPS = [
    "fb:fb1:nac-victoria",
    "fb:fb1:nac-vandenburg",
    "fb:fb1:nac-vandenburg",
    "fb:fb1:nac-ticonderoga",
    "fb:fb1:nac-ticonderoga",
    "fb:fb1:nac-ark-royal",
]

BANNER_STYLE = """
    <style>
      /* Scoped to the preview banner: static/style.css stays the app's own file, untouched. */
      .preview-banner {
        max-width: 1400px;
        margin: 0.9rem auto 0;
        padding: 0.65rem 1rem;
        background: var(--surface-2, #16202c);
        border: 1px solid var(--border, #2a3a4d);
        border-radius: 8px;
        font-size: 0.9rem;
      }
      .preview-banner a { margin-left: 0.4rem; }
    </style>
"""

# Nothing here has a server behind it, so every control is made inert rather than left to fail.
PREVIEW_SCRIPT = """
    <script>
      (function () {
        document.addEventListener("submit", function (e) { e.preventDefault(); }, true);
        document.addEventListener("click", function (e) {
          var a = e.target.closest ? e.target.closest("a") : null;
          if (a && a.getAttribute("href") && a.getAttribute("href").charAt(0) === "/") {
            e.preventDefault();
          }
        }, true);
        // The topbar fleet picker navigates from onchange, which never reaches 'submit'.
        document.querySelectorAll("select[onchange]").forEach(function (s) {
          s.removeAttribute("onchange");
        });
      })();
    </script>
"""


def build_fleet() -> str:
    fleet, msg = store.create_fleet("fb", "Task Force Meridian", faction="NAC", points_limit=3000,
                                    admiral="Adm. R. Calder")
    assert fleet, msg
    for design_id in FLEET_SHIPS:
        ok, msg = store.add_ship(fleet, design_id)
        assert ok, f"{design_id}: {msg}"
    store.save_fleet(fleet)
    return fleet["id"]


def get(path: str, follow: bool = False) -> str:
    resp = client.get(path, follow_redirects=follow)
    assert resp.status_code == 200, f"GET {path} -> {resp.status_code}"
    return resp.get_data(as_text=True)


def sanitize(html: str, *, banner: str) -> str:
    """Rewrites app-absolute asset paths to the ones the Pages site serves, and neuters the UI."""
    html = re.sub(r'(href|src)="/static/', r'\1="app/static/', html)
    html = re.sub(r'<ul class="flashes".*?</ul>', "", html, flags=re.S)
    html = html.replace("</head>", BANNER_STYLE + "  </head>", 1)
    html = html.replace('<main class="work', banner + '<main class="work', 1)
    return html.replace("</body>", PREVIEW_SCRIPT + "  </body>", 1)


def banner_html(other: str, label: str) -> str:
    return (
        '\n    <div class="preview-banner">\n'
        "      <strong>Preview</strong> \u2014 a static, read-only snapshot of the real app.\n"
        "      Nothing on this page saves.\n"
        '      <a href="index.html">&larr; Get the app</a> &middot;\n'
        f'      <a href="{other}">{label}</a>\n'
        "    </div>\n"
    )


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "_site"
    out.mkdir(parents=True, exist_ok=True)

    fleet_id = build_fleet()
    pages = {
        # /fleet/<id> selects the fleet into the session and redirects to the overview.
        "preview-fleet.html": (
            get(f"/fleet/{fleet_id}", follow=True),
            banner_html("preview-design.html", "See the design workbench"),
        ),
        "preview-design.html": (
            get(f"/design/{DESIGN_ID}"),
            banner_html("preview-fleet.html", "See a fleet"),
        ),
    }
    for name, (html, banner) in pages.items():
        target = out / name
        target.write_text(sanitize(html, banner=banner), encoding="utf-8")
        print(f"  wrote {target} ({target.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
