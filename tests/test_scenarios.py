"""Scenario templates (PLAN 11.3, roadmap step G2): objectives, a clock and ownership set up
on a generated or hand-made map."""

from __future__ import annotations

import pytest

import scenarios
import starmap
import store

SIDES = [{"id": "blue", "name": "Blue"}, {"id": "red", "name": "Red"}]


@pytest.fixture(autouse=True)
def library(tmp_path, monkeypatch):
    monkeypatch.setenv("FTFM_DATA_DIR", str(tmp_path))
    return tmp_path


def a_map() -> dict:
    return starmap.generate(16, 12, 20, ["blue", "red"], 11)


def test_an_invasion_hands_the_defender_the_sector():
    grid = a_map()
    setup, why = scenarios.build("invasion", grid, SIDES, "red")
    assert why == ""
    owners = setup["owners"]
    red_home = scenarios.home(grid, "red")
    assert {o for name, o in owners.items() if name != red_home["name"]
            and next(s for s in grid["systems"] if s["name"] == name)["kind"] != "empty"} == {"blue"}
    blue_settled = sum(s["kind"] == "settled" and owners[s["name"]] == "blue" for s in grid["systems"])
    obj = setup["objectives"]["red"]
    assert obj["include"] == scenarios.home(grid, "blue")["name"]
    assert obj["count"] == 1 + -(-blue_settled // 2)            # its own home plus half, rounded up
    assert setup["end_week"] == 7 and "blue" not in setup["objectives"]


def test_a_raid_targets_the_nearest_enemy_world_and_a_border_war_needs_a_majority():
    grid = a_map()
    raid, _why = scenarios.build("raid", grid, SIDES, "red")
    target = raid["objectives"]["red"]["include"]
    assert next(s for s in grid["systems"] if s["name"] == target)["owner"] == "blue"
    war, _why = scenarios.build("border_war", grid, SIDES, "blue")
    settled = sum(s["kind"] == "settled" for s in grid["systems"])
    assert {o["count"] for o in war["objectives"].values()} == {settled // 2 + 1}
    assert set(war["objectives"]) == {"blue", "red"}
    assert scenarios.build("raid", starmap.blank(), SIDES, "red")[0] is None


def test_the_campaign_bar_sets_up_a_scenario(client):
    fleet, _msg = store.create_fleet("fb", "Home Fleet", faction="NAC")
    campaign, _msg = store.create_campaign(fleet, "Border")
    store.random_starmap(campaign, 16, 12, 20, 11)
    store.finalize_starmap(campaign)
    store.save_campaign(campaign)
    store.save_fleet(fleet)
    client.get(f"/fleet/{fleet['id']}")
    assert "Set up scenario" in client.get("/campaign").get_data(as_text=True)
    url = f"/campaigns/{campaign['id']}/action"
    client.post(url, data={"action": "apply_scenario", "scenario": "invasion", "attacker": "red"})
    again = store.get_campaign(campaign["id"])
    assert again["end_week"] == 7 and "Invasion (app rule)" in again["notes"]
    again["week"] = 2
    assert store.apply_scenario(again, "raid", "red")[0] is False
