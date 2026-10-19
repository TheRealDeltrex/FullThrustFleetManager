"""The web build boots in headless Chromium, saves a fleet and backs it up (PLAN 15).

It needs Playwright with Chromium and the network (Pyodide comes from jsdelivr), so it runs only
with FTFM_WEB_BOOT=1, which the Tests workflow's web-build job sets. The site is assembled the
way deploy-pages.yml does it, minus the rulebooks, which boot does not touch.
"""

from __future__ import annotations

import functools
import http.server
import os
import shutil
import subprocess
import sys
import threading

import pytest
from conftest import ROOT

pytestmark = pytest.mark.skipif(os.environ.get("FTFM_WEB_BOOT") != "1",
                                reason="set FTFM_WEB_BOOT=1 (needs Playwright and the network)")


@pytest.fixture(scope="module")
def site_url(tmp_path_factory):
    site = tmp_path_factory.mktemp("site")
    subprocess.run([sys.executable, "scripts/build_browser_bundle.py"], cwd=ROOT, check=True,
                   capture_output=True)
    app = site / "app"
    app.mkdir()
    shutil.copy(ROOT / "web" / "index.html", app)
    shutil.copy(ROOT / "web" / "bundle.json", app)
    shutil.copytree(ROOT / "static", app / "static")
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(site))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


def test_the_web_build_boots_and_saves_a_fleet(site_url):
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        errors: list[str] = []
        page.on("pageerror", lambda exc: errors.append(str(exc)))
        page.goto(f"{site_url}/app/")
        # Pyodide, Flask and fpdf2 download on first load.
        page.wait_for_selector("#app-frame", state="visible", timeout=300_000)
        frame = page.frame_locator("#app-frame")
        frame.locator("header.topbar").wait_for(timeout=60_000)

        form = frame.locator('form[action="/fleet/new"]')
        form.locator('[name="name"]').fill("Web boot check")
        form.locator('[name="ruleset"]').select_option("ftpc")
        form.locator("button").last.click()
        # The new fleet becomes the current one in the top bar's fleet selector.
        frame.locator("option[selected]", has_text="Web boot check").first.wait_for(
            state="attached", timeout=60_000)
        page.wait_for_function(
            "() => (localStorage.getItem('ftfm_library_v1') || '').includes('Web boot check')",
            timeout=30_000)
        # The library now holds something, so the page offers a backup; it downloads as a file.
        with page.expect_download(timeout=60_000) as download:
            frame.locator("form.backup-due button.primary").click()
        assert download.value.suggested_filename.endswith(".FTBackup")
        # Artwork has a separate persistence path and explicit form actions in the iframe.
        frame.locator("body").evaluate(
            "() => window.ftNavigate('/portrait/design/ftpc:fb1:nac-harrison')")
        frame.locator('input[name="art"][value="custom:SC:2"]').check(timeout=30_000)
        frame.get_by_role("button", name="Use selected picture", exact=True).click()
        page.wait_for_function(
            "() => JSON.parse(localStorage.getItem('ftfm_library_v1') || '{}')"
            "['/data/portraits.json'] === '@indexeddb'", timeout=30_000)
        page.reload()
        frame.locator("header.topbar").wait_for(timeout=300_000)
        # The chosen atlas cell persists, rather than reverting to the official NAC default.
        assert "custom-1.webp" in frame.locator(".ship-portrait").first.get_attribute("style")
        browser.close()
    assert errors == []
