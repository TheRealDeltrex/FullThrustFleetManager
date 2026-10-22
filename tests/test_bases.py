"""Naval bases and reinforcements (PLAN 11.3, step C5): repairs and replenishment only docked at
one's own base, once a week (FT p.35), and ships that arrive as a task force in a later week."""

from __future__ import annotations

import pytest

import store

FURIOUS = "fb:fb1:nac-furious"


@pytest.fixture(autouse=True)
def library(tmp_path, monkeypatch):
    monkeypatch.setenv("FTFM_DATA_DIR", str(tmp_path))
    return tmp_path


def setup() -> tuple[dict, dict]:
    """Blue with three Furious; Alpha is blue's naval base, Bravo a plain blue world."""
    fleet, _msg = store.create_fleet("fb", "Home Fleet", faction="NAC")
    for _i in range(3):
        store.add_ship(fleet, FURIOUS)
    campaign, _msg = store.create_campaign(fleet, "Lafayette Incident")
    store.new_starmap(campaign, 12, 10)
    store.set_star_system(campaign, 0, 0, name="Alpha", kind="settled", owner="blue", base=True)
    store.set_star_system(campaign, 5, 0, name="Bravo", kind="settled", owner="blue", base=False)
    store.save_fleet(fleet)
    store.save_campaign(campaign)
    return campaign, fleet


def test_repairs_need_a_dock_at_an_own_base_once_a_week():
    campaign, fleet = setup()
    ship = fleet["ships"][0]
    store.set_ship_damage(fleet, ship["uid"], hull=5)
    plan = {"hull": 3, "drive_hits": 0, "systems": []}
    assert store.repair_ship(fleet, ship["uid"], plan) == (False, "Only at a naval base of your side.")
    force, _msg = store.add_force(campaign, "blue", "Yard", 0, 0)
    store.assign_ships(campaign, force["id"], fleet, [ship["uid"]])
    store.save_campaign(campaign)
    assert store.repair_ship(fleet, ship["uid"], plan) == (False, "Dock the ship at Alpha first.")
    store.update_ship(fleet, ship["uid"], status="docked")
    assert store.repair_ship(fleet, ship["uid"], plan)[0]
    assert ship["damage"]["hull"] == 2
    assert store.repair_ship(fleet, ship["uid"], plan) == (False, "Repaired this week already.")
    assert store.replenish_ship(fleet, ship["uid"])[0]
    # A base the other side holds repairs nothing.
    campaign["map"]["systems"][0]["owner"] = "red"
    store.save_campaign(campaign)
    assert store.replenish_ship(fleet, ship["uid"])[0] is False


def test_a_fleet_without_a_map_repairs_anywhere():
    fleet, _msg = store.create_fleet("fb", "Home Fleet", faction="NAC")
    store.add_ship(fleet, FURIOUS)
    uid = fleet["ships"][0]["uid"]
    store.set_ship_damage(fleet, uid, hull=2)
    assert store.repair_ship(fleet, uid, {"hull": 2, "drive_hits": 0, "systems": []})[0]


def test_reinforcements_arrive_as_a_task_force_in_their_week():
    campaign, fleet = setup()
    uids = [s["uid"] for s in fleet["ships"]]
    assert store.schedule_reinforcement(campaign, fleet, uids[:2], 1, 5, 0)[0] is False   # this week
    assert store.schedule_reinforcement(campaign, fleet, uids[:2], 3, 5, 0, "Relief")[0]
    assert store.schedule_reinforcement(campaign, fleet, uids[:1], 4, 5, 0)[1] == "Tick the ships to add."
    assert store.remove_star_system(campaign, 5, 0)[0] is False
    store.save_campaign(campaign)
    campaign = store.get_campaign(campaign["id"])
    assert campaign["reinforcements"][0]["ships"] == [{"fleet": fleet["id"], "uid": u} for u in uids[:2]]
    store.next_week(campaign)
    assert campaign["forces"] == []
    store.next_week(campaign)
    [force] = campaign["forces"]
    assert (force["name"], force["q"], len(force["ships"])) == ("Relief", 5, 2)
    assert campaign["reinforcements"] == []
    assert campaign["log"][-1]["text"] == "Relief (Blue) arrive at Bravo."
    assert store.get_fleet(fleet["id"])["ships"][0]["location"] == "Bravo"


def test_the_panel_schedules_and_cancels_reinforcements(client):
    campaign, fleet = setup()
    client.get(f"/fleet/{fleet['id']}")
    url = f"/campaigns/{campaign['id']}/action"
    client.post(url, data={"action": "schedule_reinforcement", "fleet": fleet["id"], "at": "5,0",
                           "week": "4", "name": "Relief", "ship": [fleet["ships"][0]["uid"]]})
    page = client.get("/campaign").get_data(as_text=True)
    assert "Relief" in page and "week 4 at Bravo" in page
    assert "Only at a naval base of your side." in page
    client.post(url, data={"action": "cancel_reinforcement", "reinforcement": "rf1"})
    assert store.get_campaign(campaign["id"])["reinforcements"] == []
