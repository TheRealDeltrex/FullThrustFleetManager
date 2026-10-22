"""Weekly events and war weariness (PLAN 11.3, roadmap step G4), all app rules."""

from __future__ import annotations

import pytest

import events
import store

FURIOUS = "fb:fb1:nac-furious"


@pytest.fixture(autouse=True)
def library(tmp_path, monkeypatch):
    monkeypatch.setenv("FTFM_DATA_DIR", str(tmp_path))
    return tmp_path


def setup() -> tuple[dict, dict]:
    blue, _msg = store.create_fleet("fb", "Home Fleet", faction="NAC")
    store.add_ship(blue, FURIOUS)
    campaign, _msg = store.create_campaign(blue, "Border")
    store.new_starmap(campaign, 12, 10)
    for q, name, kind, base in ((0, "Alpha", "settled", True), (3, "Bravo", "settled", False),
                                (6, "Charlie", "outpost", False)):
        store.set_star_system(campaign, q, 0, name=name, kind=kind, owner="blue", base=base)
    force, _msg = store.add_force(campaign, "blue", "Hunters", 0, 0)
    store.assign_ships(campaign, force["id"], blue, [s["uid"] for s in blue["ships"]])
    campaign["events"] = True
    store.save_fleet(blue)
    return campaign, blue


def test_the_table():
    assert [events.kind_for(n) for n in range(2, 13)] == [
        "unrest", "unrest", "supply", "pirates", "quiet", "quiet", "quiet", "leak", "late", "early", "early"]


def test_unrest_and_pirates_take_unguarded_worlds():
    campaign, _blue = setup()
    campaign["week"] = 2
    store._weekly_events(campaign, {"blue": 2, "red": 5})
    owners = {s["name"]: s["owner"] for s in campaign["map"]["systems"]}
    assert owners == {"Alpha": "blue", "Bravo": "", "Charlie": "blue"}   # red holds no outpost
    assert "Bravo breaks away" in campaign["log"][-2]["text"] and "sides" not in campaign["log"][-2]
    assert campaign["log"][-1]["sides"] == ["red"] and "quiet week" in campaign["log"][-1]["text"]


def test_supply_trouble_closes_the_yard_and_a_leak_exposes_the_forces():
    campaign, blue = setup()
    campaign["hidden"] = True
    store._weekly_events(campaign, {"blue": 4, "red": 9})
    store.save_campaign(campaign)
    assert store.yard_block(blue, blue["ships"][0]).startswith("Supply trouble")
    red_force, _msg = store.add_force(campaign, "red", "Raiders", 6, 0)
    assert store.sees_force(campaign, "blue", red_force)
    campaign["week"] += 1
    assert not store.sees_force(campaign, "blue", red_force)


def test_reinforcements_come_early_or_late():
    campaign, blue = setup()
    campaign["reinforcements"] = [{"id": "rf1", "side": "blue", "name": "Second wave", "week": 4,
                                   "q": 3, "r": 0, "ships": []}]
    store._weekly_events(campaign, {"blue": 10, "red": 7})
    assert campaign["reinforcements"][0]["week"] == 5
    store._weekly_events(campaign, {"blue": 12, "red": 7})
    assert campaign["reinforcements"][0]["week"] == campaign["week"]


def test_war_weariness_shortens_the_clock_and_reopening_restores_it():
    campaign, _blue = setup()
    campaign["objectives"] = {"red": {"count": 2, "include": "", "draw": []}}
    campaign["end_week"] = 7
    campaign["contacts"] = [{"id": "k1", "week": 1, "q": 3, "r": 0, "sides": ["blue", "red"],
                             "reports": {}, "choices": {"blue": "fight", "red": "fight"}, "roll": None,
                             "outcome": "battle", "leaving": [], "result": "", "owner_before": None,
                             "notes": ""}]
    store.save_campaign(campaign)
    ok, text = store.set_battle_result(campaign, "k1", "blue")
    assert ok and "War weariness" in text and campaign["end_week"] == 6
    store.reopen_contact(campaign, "k1")
    assert campaign["end_week"] == 7
