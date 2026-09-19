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
    for label in ("Fleet overview", "Design", "Campaign", "Settings", "Fleet points", "Print fleet PDF"):
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
