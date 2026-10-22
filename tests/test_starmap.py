"""Campaign star maps (PLAN 11.3, step C2): hex maths, the random generator, drawing a map by
hand, and star map files."""

from __future__ import annotations

import io
import json
import re

import pytest

import scenarios
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
    grid = starmap.generate(20, 16, 30, sides, 9, spacing=3, names="catalog",
                            counts={side: {"settled": 4, "outposts": 0, "bases": 3} for side in sides},
                            neutral={"settled": 0, "outposts": 0})
    cells = [(s["q"], s["r"]) for s in grid["systems"]]
    assert all(starmap.hex_distance(a, b) >= 3 for a in cells for b in cells if a != b)
    assert all(re.fullmatch(r"[A-Z]+-\d{3,4}", s["name"]) for s in grid["systems"])
    for side in sides:
        assert sum(s["base"] and s["owner"] == side for s in grid["systems"]) == 3
    assert sum(s["kind"] == "settled" for s in grid["systems"]) == 12
    assert {s["kind"] for s in grid["systems"] if not s["owner"]} == {"empty"}


def tally(grid: dict) -> dict:
    out: dict = {}
    for s in grid["systems"]:
        row = out.setdefault(s["owner"], {"settled": 0, "outposts": 0, "bases": 0})
        if s["kind"] != "empty":
            row["settled" if s["kind"] == "settled" else "outposts"] += 1
        row["bases"] += s["base"]
    return out


@pytest.mark.parametrize("seed", range(1, 30))
def test_counts_are_exact_for_every_side(seed):
    """Master 2026-10-22: counts are a hard rule, not a suggestion, and sides may differ."""
    counts = {"a": {"settled": 6, "outposts": 3, "bases": 3}, "b": {"settled": 1, "outposts": 0, "bases": 1},
              "c": {"settled": 2, "outposts": 4, "bases": 2}, "d": {"settled": 3, "outposts": 1, "bases": 1},
              "e": {"settled": 1, "outposts": 2, "bases": 1}}
    grid = starmap.generate(24, 18, 40, list(counts), seed, counts=counts,
                            neutral={"settled": 3, "outposts": 2, "place": "random"})
    got = tally(grid)
    assert {side: got[side] for side in counts} == counts
    assert (got[""]["settled"], got[""]["outposts"], got[""]["bases"]) == (3, 2, 0)
    for side in counts:
        home = next(s for s in grid["systems"] if s["owner"] == side and s["base"])
        assert home["kind"] == "settled"


def test_counts_that_do_not_fit_are_refused():
    with pytest.raises(starmap.CountsError) as e:
        starmap.generate(12, 10, 8, ["blue", "red"], 1, counts={"blue": {"settled": 5}})
    assert (e.value.needed, e.value.placed) == (9, 8)


def test_the_name_pool_is_large_and_unique():
    assert len(starmap.NAME_POOL) >= 1200
    assert len(set(starmap.NAME_POOL)) == len(starmap.NAME_POOL)
    assert max(len(n) for n in starmap.NAME_POOL) <= 40
    grid = starmap.generate(30, 30, 400, ["blue", "red"], 5, spacing=1)
    names = [s["name"] for s in grid["systems"]]
    assert len(names) == 400 and len(set(names)) == 400


def test_the_panel_passes_the_generator_settings(client):
    _fleet, campaign = a_campaign()
    post(client, campaign, action="random_starmap", width="12", height="10", stars="16", seed="3",
         spacing="3", names="catalog", **{"s-blue-settled": "3", "s-blue-outposts": "2", "s-blue-bases": "2",
                                          "s-red-settled": "1", "s-red-outposts": "0", "s-red-bases": "1",
                                          "n-settled": "0", "n-outposts": "1", "n-place": "random"})
    grid = store.get_campaign(campaign["id"])["map"]
    assert grid == starmap.generate(12, 10, 16, ["blue", "red"], 3, spacing=3, names="catalog", counts={
        "blue": {"settled": 3, "outposts": 2, "bases": 2}, "red": {"settled": 1, "outposts": 0, "bases": 1}},
        neutral={"settled": 0, "outposts": 1, "place": "random"})
    assert grid["draft"]["sides"]["blue"] == {"settled": 3, "outposts": 2, "bases": 2, "core": True}


def test_bad_counts_say_why_and_keep_the_old_map(client):
    _fleet, campaign = a_campaign()
    post(client, campaign, action="random_starmap", stars="16", seed="3")
    before = store.get_campaign(campaign["id"])["map"]
    page = text(post(client, campaign, action="random_starmap", stars="16", seed="3",
                     **{"s-red-settled": "20"}))
    assert "These counts need 24 systems; the map has 16 stars." in page
    page = text(post(client, campaign, action="random_starmap", stars="16", seed="3",
                     **{"s-red-settled": "2", "s-red-outposts": "0", "s-red-bases": "3"}))
    assert "Red: more bases than systems." in page
    page = text(post(client, campaign, action="random_starmap", stars="16", seed="3",
                     **{"s-red-settled": "0", "s-red-outposts": "0"}))
    assert "Red: at least one settled world or outpost." in page
    assert store.get_campaign(campaign["id"])["map"] == before


def test_a_draft_follows_its_inputs_until_finalized(client):
    _fleet, campaign = a_campaign()
    page = text(post(client, campaign, action="random_starmap", stars="20", seed="8"))
    assert "Finalize" in page and 'data-autosave="random_starmap"' in page
    first = store.get_campaign(campaign["id"])["map"]
    post(client, campaign, action="random_starmap", stars="20", seed="8", autosave="1",
         **{"s-blue-outposts": "4"})
    second = store.get_campaign(campaign["id"])["map"]
    assert [(s["q"], s["r"]) for s in second["systems"]] == [(s["q"], s["r"]) for s in first["systems"]]
    assert tally(second)["blue"]["outposts"] == 4
    assert "Finalize the star map first" in text(post(client, campaign, action="set_star_system", hex="0,0",
                                                     name="X", kind="settled"))
    post(client, campaign, action="reroll_starmap", stars="20", seed="8")
    assert store.get_campaign(campaign["id"])["map"]["seed"] != 8
    page = text(post(client, campaign, action="finalize_starmap"))
    assert "Star map finalised" in page and 'data-autosave="random_starmap"' not in page
    assert store.get_campaign(campaign["id"])["map"]["draft"] is None


def test_the_generator_sets_the_number_of_sides(client):
    _fleet, campaign = a_campaign()
    post(client, campaign, action="random_starmap", stars="30", sides="5")
    grid = store.get_campaign(campaign["id"])["map"]
    assert len(store.get_campaign(campaign["id"])["sides"]) == 5 and len(grid["draft"]["sides"]) == 5
    assert len({s["owner"] for s in grid["systems"] if s["base"]}) == 5
    post(client, campaign, action="random_starmap", stars="30", sides="3")
    assert len(store.get_campaign(campaign["id"])["sides"]) == 3


def test_a_side_may_start_with_one_outpost_and_no_base():
    """Master 2026-10-22: an invader through a wormhole has no support structure yet."""
    counts = {"blue": {"settled": 3, "outposts": 1, "bases": 1},
              "red": {"settled": 0, "outposts": 1, "bases": 0}}
    grid = starmap.generate(14, 10, 16, ["blue", "red"], 2, counts=counts)
    red = [s for s in grid["systems"] if s["owner"] == "red"]
    assert [(s["kind"], s["base"]) for s in red] == [("outpost", False)]
    assert scenarios.home(grid, "red") is red[0]
    outposts_only = starmap.generate(14, 10, 16, ["blue", "red"], 2, counts={
        "blue": {"settled": 0, "outposts": 3, "bases": 2}})
    blue = tally(outposts_only)["blue"]
    assert (blue["settled"], blue["outposts"], blue["bases"]) == (0, 3, 2)


def test_core_worlds_off_mixes_settled_worlds_and_outposts():
    def core(on: bool, seed: int) -> bool:
        """Whether every settled world (bar home) is at least as near home as every outpost."""
        counts = {"blue": {"settled": 5, "outposts": 5, "bases": 1, "core": on}}
        grid = starmap.generate(20, 14, 30, ["blue", "red"], seed, counts=counts)
        home = next(s for s in grid["systems"] if s["owner"] == "blue" and s["base"])
        own = [s for s in grid["systems"] if s["owner"] == "blue" and s is not home]
        apart = {kind: [starmap.hex_distance((s["q"], s["r"]), (home["q"], home["r"]))
                        for s in own if s["kind"] == kind] for kind in ("settled", "outpost")}
        assert (len(apart["settled"]), len(apart["outpost"])) == (4, 5)
        return max(apart["settled"]) <= min(apart["outpost"])

    assert all(core(True, seed) for seed in range(1, 8))
    assert not all(core(False, seed) for seed in range(1, 8))


def test_neutral_systems_none_random_or_a_border_region():
    """Master 2026-10-22: three choices for neutral systems."""
    def neutral(place: str, seed: int) -> tuple[dict, list[dict]]:
        grid = starmap.generate(24, 12, 40, ["blue", "red"], seed,
                                neutral={"settled": 2, "outposts": 2, "place": place})
        return grid, [s for s in grid["systems"] if not s["owner"] and s["kind"] != "empty"]

    assert neutral("none", 1)[1] == []
    for seed in range(1, 6):
        grid, border = neutral("border", seed)
        assert sorted(s["kind"] for s in border) == ["outpost", "outpost", "settled", "settled"]
        held = {side: [s for s in grid["systems"] if s["owner"] == side] for side in ("blue", "red")}

        def gap(s: dict) -> int:
            blue, red = (min(starmap.hex_distance((s["q"], s["r"]), (h["q"], h["r"]))
                             for h in held[side]) for side in ("blue", "red"))
            return abs(blue - red)
        bare = [s for s in grid["systems"] if s["kind"] == "empty"]
        assert max(gap(s) for s in border) <= min(gap(s) for s in bare)
    assert len(neutral("random", 1)[1]) == 4


def a_line(*owners: str) -> dict:
    grid = starmap.blank(12, 4)
    for q, owner in owners:
        grid["systems"].append({"q": q, "r": 0, "name": f"S{q}", "kind": "settled", "owner": owner,
                                "base": False})
    return grid


def test_the_frontline_lies_between_opposing_systems():
    """Master 2026-10-22: one hex wide where the systems are an even number of hexes apart, two
    wide otherwise, and two opposing neighbours are both on it."""
    on_row = {cell for cell in starmap.frontline(a_line((0, "blue"), (4, "red")), reach=30) if cell[1] == 0}
    assert on_row == {(2, 0)}                                # distance 4: three hexes between
    on_row = {cell for cell in starmap.frontline(a_line((0, "blue"), (3, "red")), reach=30) if cell[1] == 0}
    assert on_row == {(1, 0), (2, 0)}                        # distance 3: two hexes between
    on_row = {cell for cell in starmap.frontline(a_line((4, "blue"), (5, "red")), reach=30) if cell[1] == 0}
    assert on_row == {(4, 0), (5, 0)}                        # side by side


def test_sides_project_their_front_only_so_far():
    """Master 2026-10-22: 4 hexes by default, set per campaign."""
    apart = a_line((0, "blue"), (10, "red"))
    assert {cell for cell in starmap.frontline(apart) if cell[1] == 0} == {(4, 0), (6, 0)}
    assert {cell for cell in starmap.frontline(apart, reach=5) if cell[1] == 0} == {(5, 0)}
    lone = a_line((5, "blue"))                            # a side alone still outlines its sphere
    assert {cell for cell in starmap.frontline(lone, reach=2) if cell[1] == 0} == {(3, 0), (7, 0)}
    odd = a_line((0, "blue"), (9, "red"))
    assert {cell for cell in starmap.frontline(odd) if cell[1] == 0} == {(4, 0), (5, 0)}


def test_neutral_worlds_project_a_frontline():
    """Master 2026-10-22: a neutral world is ringed by front however far the empire is; a cluster
    projects it up to two hexes out."""
    grid = starmap.blank(16, 12)

    def add(q: int, r: int, owner: str) -> None:
        grid["systems"].append({"q": q, "r": r, "name": f"S{q}{r}", "kind": "settled", "owner": owner,
                                "base": False})

    add(0, 0, "blue")
    add(10, 6, "")
    lone = (10, 6)
    assert not set(starmap.neighbours(*lone)) & starmap.frontline(grid)   # beyond blue's reach
    assert starmap.frontline(grid, reach=30) == set(starmap.neighbours(*lone))
    add(10, 8, "")                                     # two hexes away: a cluster
    front = starmap.frontline(grid, reach=30)
    pair = [(10, 6), (10, 8)]
    assert all(min(starmap.hex_distance(cell, w) for w in pair) == 2 for cell in front)
    assert (10, 4) in front and (10, 7) not in front
    far = starmap.blank(16, 12)
    far["systems"] = [dict(grid["systems"][0]), {"q": 4, "r": 4, "name": "A", "kind": "outpost",
                                                 "owner": "", "base": False}]
    far["systems"].append(dict(far["systems"][1], r=7, name="B"))       # three hexes: still a cluster
    assert (4, 2) in starmap.frontline(far, reach=30)
    far["systems"][2]["r"] = 8                                           # four: two lone worlds
    assert (4, 2) not in starmap.frontline(far, reach=30)
    add(11, 6, "blue")                                 # an empire system beside a neutral world
    front = starmap.frontline(grid)
    assert {(10, 6), (11, 6)} <= front


def test_the_frontline_toggle_shades_the_map(client):
    _fleet, campaign = a_campaign()
    post(client, campaign, action="random_starmap", stars="16", seed="3")
    assert 'class="hex front"' not in text(client.get("/campaign"))
    post(client, campaign, action="set_frontline", frontline="on", autosave="1")
    assert 'class="hex front"' in text(client.get("/campaign"))
    post(client, campaign, action="random_starmap", stars="16", seed="4", autosave="1")
    assert store.get_campaign(campaign["id"])["map"]["frontline"] is True
    post(client, campaign, action="set_frontline", autosave="1")
    assert store.get_campaign(campaign["id"])["map"]["frontline"] is False
    assert store.get_campaign(campaign["id"])["front_reach"] == starmap.DEFAULT_FRONT_REACH
    post(client, campaign, action="update_campaign", front_reach="7", autosave="1")
    assert store.get_campaign(campaign["id"])["front_reach"] == 7


def test_the_core_checkbox_reaches_the_generator(client):
    _fleet, campaign = a_campaign()
    post(client, campaign, action="random_starmap", stars="16", seed="3", **{"core-present": "1",
                                                                             "s-blue-core": "on"})
    sides = store.get_campaign(campaign["id"])["map"]["draft"]["sides"]
    assert (sides["blue"]["core"], sides["red"]["core"]) == (True, False)


def test_a_crowded_map_stops_when_no_hex_is_free():
    one = {"settled": 1, "outposts": 0, "bases": 1}
    grid = starmap.generate(4, 4, 100, ["blue", "red"], 1, counts={"blue": one, "red": one},
                            neutral={"settled": 0, "outposts": 0})
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
