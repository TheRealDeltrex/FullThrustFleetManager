"""The GitHub Pages front door: web/landing.html and the two scripts that finish it.

Nothing here renders the page — that is a job for eyes. What these tests hold is the contract
between the hand-written page and the build steps that rewrite it, which is invisible until a
deploy silently produces a page with a vDEV badge or a dead preview link on it.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
LANDING = ROOT / "web" / "landing.html"
WORKFLOW = ROOT / ".github" / "workflows" / "deploy-pages.yml"

sys.path.insert(0, str(ROOT / "scripts"))
import stamp_landing_page_versions as stamp  # noqa: E402


@pytest.fixture(scope="module")
def html() -> str:
    return LANDING.read_text(encoding="utf-8")


def _release(tag: str, asset: str) -> dict:
    return {"tag_name": tag, "draft": False,
            "assets": [{"name": asset, "browser_download_url": f"https://x/{asset}"}]}


# ---- The markers the stamp script rewrites ------------------------------------------------------


def test_every_download_marker_is_one_the_stamp_script_knows(html):
    """A card the script has no platform for would ship advertising vDEV for ever."""
    for attr in ("data-version-badge", "data-download", "data-platform-card"):
        keys = set(re.findall(rf'{attr}="([a-z]+)"', html))
        assert keys, f"no {attr} markers on the landing page"
        assert keys <= set(stamp.PLATFORMS) | {"online"}


def test_each_platform_has_a_badge_a_link_and_a_card(html):
    for key in stamp.PLATFORMS:
        assert f'data-version-badge="{key}"' in html
        assert f'data-download="{key}"' in html
        assert f'data-platform-card="{key}"' in html


def test_stamping_fills_the_badges_and_the_download_links(html, monkeypatch, tmp_path):
    monkeypatch.setattr(stamp, "_fetch_releases", lambda: [
        _release("v9.9", "FullThrustFleetManager-9.9-win64.zip"),
        _release("v9.8", "FullThrustFleetManager-9.8-linux-x64.tar.gz"),
    ])
    target = tmp_path / "index.html"
    target.write_text(html, encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["stamp", str(target)])
    stamp.main()

    out = target.read_text(encoding="utf-8")
    assert 'data-version-badge="windows">v9.9<' in out
    assert 'data-version-badge="linux">v9.8<' in out
    assert 'data-version-badge="online">v' in out and "vDEV" not in out
    assert out.count("https://x/") == 2


def test_a_platform_with_no_build_loses_its_whole_card(html, monkeypatch, tmp_path):
    monkeypatch.setattr(stamp, "_fetch_releases", lambda: [
        _release("v9.9", "FullThrustFleetManager-9.9-win64.zip"),
    ])
    target = tmp_path / "index.html"
    target.write_text(html, encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["stamp", str(target)])
    stamp.main()

    out = target.read_text(encoding="utf-8")
    assert 'data-platform-card="linux"' not in out
    assert "Download for Linux" not in out
    assert 'data-platform-card="windows"' in out           # the one with a build stays
    assert out.count("<div") == out.count("</div>")        # and the cut left the page whole


def test_an_unreachable_api_changes_nothing_but_the_online_badge(html, monkeypatch, tmp_path):
    """A GitHub outage must not quietly un-advertise a platform that does have a build."""
    def boom():
        raise OSError("no network")

    monkeypatch.setattr(stamp, "_fetch_releases", boom)
    target = tmp_path / "index.html"
    target.write_text(html, encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["stamp", str(target)])
    stamp.main()

    out = target.read_text(encoding="utf-8")
    assert 'data-platform-card="linux"' in out and 'data-platform-card="windows"' in out
    assert out.count("vDEV") == 2                          # both download badges left alone


def test_a_draft_release_is_not_offered_as_a_download():
    draft = dict(_release("v9.9", "FullThrustFleetManager-9.9-win64.zip"), draft=True)
    shipped = _release("v9.0", "FullThrustFleetManager-9.0-win64.zip")
    assert stamp.latest_asset([draft, shipped], "-win64.zip")[0] == "9.0"
    assert stamp.latest_asset([shipped], "-linux-x64.tar.gz") is None


# ---- The prose, which has no build step to keep it honest ---------------------------------------
#
# The badges stamp themselves; the sentences do not. The page sat claiming 96 catalog designs for
# the whole of the alien-race work, which is what these two tests exist to stop happening again.


def test_the_page_states_the_catalog_size_the_app_actually_has(html):
    import store

    stated = {int(n) for n in re.findall(r"(\d+) ship classes", html)}
    assert stated == {len(store.catalog_designs())}, (
        "web/landing.html advertises a catalog size the app no longer has"
    )


def test_the_page_names_every_race_the_rules_engines_offer(html):
    from rulesets import RULESETS

    # The page sets its apostrophes typographically and the rules engines type them straight,
    # so compare with both flattened: Kra'Vak and Kra’Vak are the same race.
    page = html.replace("’", "'")
    races = {race.name for rs in RULESETS.values() for race in rs.races()} - {"Human"}
    for name in races:
        assert name.replace("’", "'") in page, f"web/landing.html never mentions {name}"


# ---- The preview pages -------------------------------------------------------------------------


@pytest.fixture(scope="module")
def previews(tmp_path_factory) -> dict[str, str]:
    """Runs the real builder in a subprocess: it sets FTFM_DATA_DIR at import time."""
    out = tmp_path_factory.mktemp("site")
    subprocess.run([sys.executable, str(ROOT / "scripts" / "build_preview_pages.py"), str(out)],
                   cwd=ROOT, check=True, capture_output=True)
    return {p.name: p.read_text(encoding="utf-8") for p in out.glob("preview-*.html")}


def test_the_landing_page_links_exactly_the_previews_that_get_built(html, previews):
    linked = set(re.findall(r'href="(preview-[a-z]+\.html)"', html))
    assert linked == set(previews), "a preview link and the builder's output disagree"


def test_the_previews_carry_the_real_app(previews):
    design = previews["preview-design.html"]
    assert "Ko" in design and "Battleship" in design          # the catalog design it was built from
    assert 'class="ssd"' in design                            # the record sheet the app draws
    fleet = previews["preview-fleet.html"]
    assert "Task Force Meridian" in fleet and "Ark Royal" in fleet


def test_nothing_in_a_preview_points_at_a_server_that_is_not_there(previews):
    for name, page in previews.items():
        assert "/static/" not in page.replace("app/static/", ""), f"{name} keeps an absolute asset"
        assert 'class="flashes"' not in page, f"{name} kept a flash message"
        assert "preview-banner" in page, f"{name} lost its banner"
        assert "e.preventDefault()" in page, f"{name} lost the script that inerts its controls"


# ---- The deploy workflow -----------------------------------------------------------------------


def test_the_deploy_workflow_runs_both_build_steps():
    """Either script silently dropped from the workflow publishes a half-built site."""
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "scripts/build_preview_pages.py _site" in workflow
    assert "scripts/stamp_landing_page_versions.py _site/index.html" in workflow
    # The preview builder imports the app, so the deps have to be installed before it runs.
    assert workflow.index("pip install") < workflow.index("build_preview_pages.py")
