"""The force generator (PLAN 11.3, roadmap step G3): a points budget bought from the catalog,
no class over half the ships (FT p.37), placed at the side's home and as garrisons."""

from __future__ import annotations

import copy
import random
from collections import Counter

import pytest

import fleet_rules
import forcegen
import store


@pytest.fixture(autouse=True)
def library(tmp_path, monkeypatch):
    monkeypatch.setenv("FTFM_DATA_DIR", str(tmp_path))
    return tmp_path


def test_the_pick_stays_in_budget_and_no_class_is_over_half():
    candidates = [("e", 60, "escort"), ("c", 200, "cruiser"), ("k", 700, "capital")]
    for seed in range(20):
        ids = forcegen.pick(candidates, 3000, random.Random(seed))
        cost = {"e": 60, "c": 200, "k": 700}
        assert sum(cost[i] for i in ids) <= 3000
        counts = Counter(ids)
        assert len(ids) > 1 and max(counts.values()) * 2 <= len(ids)
    assert forcegen.pick(candidates, 50, random.Random(1)) == []
    assert forcegen.pick([("e", 60, "escort")], 1000, random.Random(1)) == ["e"]


def test_a_generated_fleet_joins_the_side_and_forms_up_at_home():
    fleet, _msg = store.create_fleet("fb", "Home Fleet", faction="NAC")
    campaign, _msg = store.create_campaign(fleet, "Border")
    store.random_starmap(campaign, 16, 12, 20, 11, settled=60, outposts=20)
    store.save_fleet(fleet)
    twin = copy.deepcopy(campaign)
    made, msg = store.generate_forces(campaign, "red", "ESU", 3000, defence=300, seed=5)
    assert made and made["campaign_side"] == "red" and made["faction"] == "ESU"
    designs = store.designs_for_fleet(made)
    assert fleet_rules.fleet_points(made, designs) <= 3000 + 300 * 20
    assert all(d["faction"] == "ESU" and d["ftl"] for d in designs.values())
    forces = [f for f in campaign["forces"] if f["side"] == "red"]
    home = next(s for s in campaign["map"]["systems"] if s["owner"] == "red" and s["base"])
    assert forces[0]["name"] == "Main fleet" and (forces[0]["q"], forces[0]["r"]) == (home["q"], home["r"])
    assert sum(len(f["ships"]) for f in forces) == len(made["ships"])
    assert f"{len(made['ships'])} ships" in msg
    again, _msg = store.generate_forces(twin, "red", "ESU", 3000, defence=300, seed=5)
    assert [s["design_id"] for s in again["ships"]] == [s["design_id"] for s in made["ships"]]
    assert store.generate_forces(campaign, "red", "ESU", 10)[0] is None
    assert store.generate_forces(campaign, "red", "nobody", 3000)[0] is None


def test_the_campaign_bar_generates_a_fleet(client):
    fleet, _msg = store.create_fleet("ft2", "Home Fleet")
    campaign, _msg = store.create_campaign(fleet, "Border")
    store.save_fleet(fleet)
    client.get(f"/fleet/{fleet['id']}")
    assert "Generate a fleet" in client.get("/campaign").get_data(as_text=True)
    client.post(f"/campaigns/{campaign['id']}/action", data={
        "action": "generate_forces", "side": "red", "faction": "", "points": "1500", "seed": "3"})
    made = [f for f in store.campaign_fleets(campaign["id"]) if f["campaign_side"] == "red"]
    assert len(made) == 1 and made[0]["ships"]
