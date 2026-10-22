"""M1 scaffold: the Layout C shell renders, the request guards hold, nothing loads from a CDN."""

from __future__ import annotations

import re

import pytest
from conftest import ROOT

TAB_PATHS = ["/fleet", "/design", "/campaign", "/settings"]


def test_home_redirects_to_fleet_overview(client):
    resp = client.get("/")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/fleet")


@pytest.mark.parametrize("path", TAB_PATHS)
def test_tab_renders_top_bar(client, path):
    html = client.get(path).get_data(as_text=True)
    for label in ("Fleet overview", "Ship Design", "Campaign", "Settings", "Fleet points", "Print fleet PDF"):
        assert label in html
    # Exactly the requested tab is highlighted.
    assert len(re.findall(r'class="on"', html)) == 1
    assert re.search(rf'href="{path}" class="on"', html)


def test_unknown_page_is_404(client):
    assert client.get("/nope").status_code == 404


def test_rejects_foreign_host(client):
    assert client.get("/fleet", headers={"Host": "evil.example"}).status_code == 403


def test_rejects_cross_site_post(client):
    resp = client.post("/heartbeat", headers={"Origin": "https://evil.example"})
    assert resp.status_code == 403
    assert client.post("/heartbeat", headers={"Origin": "http://127.0.0.1:5000"}).status_code == 204


def test_no_remote_urls_in_templates_or_static():
    """The desktop build must work offline (PLAN 2.1): nothing the app serves may pull from the
    network. Plain links to a website (NOTICE, GZG shop) would be fine, but none exist yet."""
    offenders = []
    for folder in ("templates", "static"):
        for path in (ROOT / folder).rglob("*"):
            # Vendored pdf.js carries URLs in comments and metadata but fetches nothing at
            # runtime; it is third-party code we do not edit, so it is not scanned.
            if "pdfjs" in path.parts:
                continue
            if path.is_file() and path.suffix in {".html", ".css", ".js"}:
                if re.search(r"(https?:)?//[a-z0-9.-]+\.[a-z]{2,}", path.read_text(encoding="utf-8"), re.I):
                    offenders.append(path.relative_to(ROOT).as_posix())
    assert offenders == []


def test_register_action_rejects_duplicates():
    import app as appmod

    @appmod.register_action("_test_noop")
    def _noop(_target):
        return True, ""

    try:
        with pytest.raises(ValueError):
            appmod.register_action("_test_noop")(_noop)
    finally:
        appmod.ACTION_HANDLERS.pop("_test_noop", None)


def test_vendored_fonts_exist_with_licence():
    css = (ROOT / "static" / "style.css").read_text(encoding="utf-8")
    urls = re.findall(r'url\("(fonts/[^"]+)"\)', css)
    assert urls
    for url in urls:
        assert (ROOT / "static" / url).is_file(), url
    assert (ROOT / "static" / "fonts" / "OFL-IBMPlexSans.txt").is_file()


def test_the_appearance_setting_themes_every_tab(client):
    import store
    css = (ROOT / "static" / "style.css").read_text(encoding="utf-8")
    assert 'data-theme="full-thrust"' in client.get("/fleet").get_data(as_text=True)  # the default
    css += (ROOT / "static" / "artwork.css").read_text(encoding="utf-8")
    assert len(store.THEMES) == 11 and "classic" not in store.THEMES  # Classic was retired
    for theme in store.THEMES:
        assert f':root[data-theme="{theme}"]' in css               # every choice has its palette
    client.post("/settings", data={"theme": "nebula"})
    for path in TAB_PATHS:
        assert 'data-theme="nebula"' in client.get(path).get_data(as_text=True)
    # Another panel's form leaves the look alone; a retired look falls back to the default.
    client.post("/settings", data={"pdf_viewer": "app", "paper": "A4"})
    assert store.load_settings()["theme"] == "nebula"
    client.post("/settings", data={"theme": "classic"})
    assert store.load_settings()["theme"] == "full-thrust"


def test_the_old_default_look_follows_the_new_default_unless_picked(client):
    import json

    import paths
    import store
    path = paths.user_data_dir() / "settings.json"
    # Before Full Thrust, any save wrote the then-default Admiralty: that is not a choice.
    path.write_text(json.dumps({"schema_version": 1, "theme": "admiralty", "paper": "Letter"}))
    assert store.load_settings()["theme"] == "full-thrust"
    path.write_text(json.dumps({"schema_version": 1, "theme": "nebula"}))
    assert store.load_settings()["theme"] == "nebula"           # any other stored look stays
    client.post("/settings", data={"theme": "admiralty"})
    client.post("/settings", data={"paper": "A4"})
    assert store.load_settings()["theme"] == "admiralty"        # picked now, so it is kept


def test_the_top_bar_look_picker_shares_the_setting(client):
    import store
    page = client.get("/design").get_data(as_text=True)
    bar = page.split('id="theme-select"', 1)[1].split("</select>", 1)[0]
    assert all(f'value="{t}"' in bar for t in store.THEMES)    # every look, short names
    assert ">Night Sky<" in bar
    names = [o.split(">", 1)[1].split("<", 1)[0].strip() for o in bar.split("<option")[1:]]
    assert names == sorted(names) and len(names) == len(store.THEMES)  # alphabetical
    resp = client.post("/settings", data={"theme": "aurora", "next": "/design"})
    assert resp.status_code == 302 and resp.headers["Location"].endswith("/design")
    assert store.load_settings()["theme"] == "aurora"
    settings = client.get("/settings").get_data(as_text=True)
    assert '<option value="aurora" selected>Aurora: northern lights, green' in " ".join(settings.split())
    assert "Settings saved" not in client.get("/design").get_data(as_text=True)  # no flash
    # Only same-site paths are followed back.
    resp = client.post("/settings", data={"theme": "lunar", "next": "//evil.example/"})
    assert resp.headers["Location"].endswith("/settings")
