"""Campaign star maps (PLAN 11.3, step C2): hex maths, the random generator, drawing a map by
hand, and star map files."""

from __future__ import annotations

import io
import json
import re

import pytest

import starmap
import store


@pytest.fixture(autouse=True)
def library(tmp_path, monkeypatch):
    monkeypatch.setenv("FTFM_DATA_DIR", str(tmp_path))
    return tmp_path


def a_campaign() -> tuple[dict, dict]:
    fleet, _msg = store.create_fleet("fb", "Home Fleet", faction="NAC")
    campaign, _msg = store.create_campaign(fleet, "Lafayette Incident")
    store.save_fleet(fleet)
    store.save_campaign(campaign)
    return fleet, campaign


def post(client, campaign, **data):
    return client.post(f"/campaigns/{campaign['id']}/action", data=data, follow_redirects=True)


def text(response) -> str:
    return response.get_data(as_text=True)


# ---- Hex maths and the generator -------------------------------------------------------------------


def test_hex_distance_on_odd_q_columns():
    assert starmap.hex_distance((0, 0), (0, 0)) == 0
    assert starmap.hex_distance((0, 0), (1, 0)) == 1      # odd column sits half a hex lower
    assert starmap.hex_distance((1, 0), (2, 0)) == 1
    assert starmap.hex_distance((1, 0), (0, 1)) == 1
    assert starmap.hex_distance((0, 0), (0, 6)) == 6
    assert starmap.hex_distance((0, 0), (6, 0)) == 6
    assert starmap.hex_distance((2, 2), (5, 1)) == 3


def test_the_generator_is_seeded_and_spaces_its_stars():
    one = starmap.generate(12, 10, 16, ["blue", "red"], 4242)
    assert one == starmap.generate(12, 10, 16, ["blue", "red"], 4242)
    assert one != starmap.generate(12, 10, 16, ["blue", "red"], 4243)
    cells = [(s["q"], s["r"]) for s in one["systems"]]
    assert len(cells) == 16 and len(set(s["name"] for s in one["systems"])) == 16
    assert all(starmap.hex_distance(a, b) >= 2 for a in cells for b in cells if a != b)
    homes = [s for s in one["systems"] if s["base"]]
    assert sorted(h["owner"] for h in homes) == ["blue", "red"]
    assert all(h["kind"] == "settled" for h in homes)
    assert one["seed"] == 4242


def test_the_generator_settings_shape_the_map():
    sides = ["blue", "red", "green"]
    grid = starmap.generate(20, 16, 30, sides, 9, spacing=3, settled=100, outposts=0, bases=3,
                            names="catalog")
    cells = [(s["q"], s["r"]) for s in grid["systems"]]
    assert all(starmap.hex_distance(a, b) >= 3 for a in cells for b in cells if a != b)
    assert {s["kind"] for s in grid["systems"]} == {"settled"}
    assert all(re.fullmatch(r"[A-Z]+-\d{3,4}", s["name"]) for s in grid["systems"])
    homes = {s["owner"] for s in grid["systems"] if s["base"]}
    assert homes == set(sides)
    for side in sides:
        assert 1 <= sum(s["base"] and s["owner"] == side for s in grid["systems"]) <= 3
    bare = starmap.generate(12, 10, 16, ["blue", "red"], 4, settled=0, outposts=0)
    assert [s["kind"] for s in bare["systems"] if not s["base"]] == ["empty"] * 14


def test_the_panel_passes_the_generator_settings(client):
    _fleet, campaign = a_campaign()
    post(client, campaign, action="random_starmap", width="12", height="10", stars="16", seed="3",
         spacing="3", settled="20", outposts="90", bases="9", names="catalog")
    grid = store.get_campaign(campaign["id"])["map"]
    assert grid == starmap.generate(12, 10, 16, ["blue", "red"], 3, spacing=3, settled=20,
                                    outposts=80, bases=5, names="catalog")


def test_a_crowded_map_stops_when_no_hex_is_free():
    grid = starmap.generate(4, 4, 100, ["blue", "red"], 1)
    assert 1 < len(grid["systems"]) < 16


# ---- The Star map panel -----------------------------------------------------------------------------


def test_a_random_map_from_the_panel(client):
    _fleet, campaign = a_campaign()
    assert "Make a star map" in text(client.get("/campaign"))
    page = text(post(client, campaign, action="random_starmap", width="14", height="9",
                     stars="12", seed="77"))
    assert "Random star map, seed 77" in page and 'class="starmap"' in page
    grid = store.get_campaign(campaign["id"])["map"]
    assert (grid["width"], grid["height"], len(grid["systems"])) == (14, 9, 12)
    assert grid == starmap.generate(14, 9, 12, ["blue", "red"], 77)


def test_drawing_a_map_by_hand(client):
    _fleet, campaign = a_campaign()
    post(client, campaign, action="new_starmap", width="8", height="6")
    assert store.get_campaign(campaign["id"])["map"]["systems"] == []
    page = text(client.get("/campaign?hex=2,3"))
    assert "Hex 0304" in page and "Add system" in page
    page = text(post(client, campaign, action="set_star_system", hex="2,3", name="Lafayette",
                     kind="settled", owner="blue", base="on"))
    assert "System added" in page and "Lafayette" in page and "Remove system" in page
    post(client, campaign, action="set_star_system", hex="2,3", name="Lafayette",
         kind="outpost", owner="", autosave="1")
    system = store.get_campaign(campaign["id"])["map"]["systems"][0]
    assert system == {"q": 2, "r": 3, "name": "Lafayette", "kind": "outpost", "owner": "",
                      "base": False}
    assert "System removed" in text(post(client, campaign, action="remove_star_system", hex="2,3"))
    assert "not on the map" in text(post(client, campaign, action="set_star_system", hex="9,9",
                                         name="Far", kind="settled"))


def test_a_map_downloads_and_loads_into_another_campaign(client):
    _fleet, campaign = a_campaign()
    store.random_starmap(campaign, 10, 8, 10, 5)
    store.update_campaign(campaign, sides={"blue": "NAC", "red": "ESU"})
    store.save_campaign(campaign)
    response = client.get(f"/export/starmap/{campaign['id']}")
    assert response.status_code == 200 and ".FTStarmap" in response.headers["Content-Disposition"]
    data = response.get_data()

    other_fleet, _msg = store.create_fleet("fb", "Raiders")
    other, _msg = store.create_campaign(other_fleet, "Second front")
    store.add_side(other, "Pirates")
    other["sides"][0]["id"], other["sides"][1]["id"] = "east", "west"   # different side ids
    store.save_fleet(other_fleet)
    store.save_campaign(other)
    page = text(client.post(f"/campaigns/{other['id']}/map", data={"file": (io.BytesIO(data), "m.FTStarmap")},
                            content_type="multipart/form-data", follow_redirects=True))
    assert "Star map loaded: 10 systems" in page
    loaded = store.get_campaign(other["id"])["map"]
    original = store.get_campaign(campaign["id"])["map"]
    swap = {"blue": "east", "red": "west", "": ""}
    assert [(s["q"], s["r"], s["name"], swap[s["owner"]]) for s in original["systems"]] == \
        [(s["q"], s["r"], s["name"], s["owner"]) for s in loaded["systems"]]


def test_a_wrong_file_is_refused_and_settings_import_points_to_the_panel(client):
    _fleet, campaign = a_campaign()
    page = text(client.post(f"/campaigns/{campaign['id']}/map",
                            data={"file": (io.BytesIO(b"{}"), "m.FTStarmap")},
                            content_type="multipart/form-data", follow_redirects=True))
    assert "Not a star map file" in page
    doc = json.dumps({"schema_version": 2, "kind": "FTStarmap", "map": starmap.blank()}).encode()
    ok, msg, _c = store.import_file("m.FTStarmap", doc)
    assert not ok and "Star map panel" in msg


def test_normalising_drops_bad_systems_and_unknown_owners():
    grid = store.normalize_starmap({"width": 99, "height": 2, "systems": [
        {"q": 0, "r": 0, "name": "A", "kind": "settled", "owner": "blue"},
        {"q": 0, "r": 0, "name": "Duplicate"},
        {"q": 1, "r": 5, "name": "Off the grid"},
        {"q": 1, "r": 1, "name": "B", "kind": "nebula", "owner": "nobody", "base": "yes"},
        "junk",
    ]}, {"blue"})
    assert (grid["width"], grid["height"]) == (starmap.MAX_SIZE, starmap.MIN_SIZE)
    assert [s["name"] for s in grid["systems"]] == ["A", "B"]
    assert grid["systems"][1] == {"q": 1, "r": 1, "name": "B", "kind": "settled", "owner": "",
                                  "base": False}


def test_a_removed_side_leaves_its_systems_unclaimed():
    _fleet, campaign = a_campaign()
    store.add_side(campaign, "Pirates")
    store.new_starmap(campaign, 6, 6)
    store.set_star_system(campaign, 1, 1, name="Hideout", kind="outpost", owner="side3", base=False)
    store.remove_side(campaign, "side3")
    store.save_campaign(campaign)
    assert store.get_campaign(campaign["id"])["map"]["systems"][0]["owner"] == ""
