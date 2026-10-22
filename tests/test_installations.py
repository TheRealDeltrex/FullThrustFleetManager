"""Installations in a campaign (PLAN 11.3, step C8): stations placed in systems as designs,
which stay put, fight where they stand and serve as repair yards (FT pp.27-28, CD p.51, PC p.115)."""

from __future__ import annotations

import pytest

import fleet_rules
import store
from rulesets import fleet_common

FURIOUS = "fb:fb1:nac-furious"


@pytest.fixture(autouse=True)
def library(tmp_path, monkeypatch):
    monkeypatch.setenv("FTFM_DATA_DIR", str(tmp_path))
    return tmp_path


def a_design(**fields) -> str:
    design, _msg = store.new_design("fb", name=fields.pop("name", "Station"))
    design.update(fields)
    store._write_design(design)
    return design["id"]


def test_what_counts_as_an_installation():
    assert fleet_common.installation({"hull_kind": "starbase", "ftl": True, "thrust": 2})
    gate = {"systems": [{"uid": "g", "type": "jump_gate"}], "ftl": True, "thrust": 1}
    assert fleet_common.installation(gate)
    assert fleet_common.installation({"ftl": False, "thrust": 0})
    assert not fleet_common.installation({"ftl": False, "thrust": 4})           # a battle rider
    assert not fleet_common.installation({"hull_kind": "section", "ftl": False, "thrust": 0})
    assert not fleet_common.installation(store.get_design(FURIOUS))


def setup() -> tuple[dict, dict, dict]:
    blue, _msg = store.create_fleet("fb", "Home Fleet", faction="NAC")
    store.add_ship(blue, FURIOUS)
    station = a_design(tmf=200, ftl=False, thrust=0)
    store.add_ship(blue, station)
    campaign, _msg = store.create_campaign(blue, "Border")
    red, _msg = store.create_fleet("fb", "Strike Group", faction="NAC")
    store.add_ship(red, FURIOUS)
    store.join_campaign(red, campaign["id"], "red")
    store.new_starmap(campaign, 12, 10)
    for q, name in ((0, "Alpha"), (5, "Bravo")):
        store.set_star_system(campaign, q, 0, name=name, kind="settled", owner="blue", base=False)
    furious, fort = blue["ships"]
    garrison, _msg = store.add_force(campaign, "blue", "Bravo Station", 5, 0)
    store.assign_ships(campaign, garrison["id"], blue, [fort["uid"]])
    raiders, _msg = store.add_force(campaign, "red", "Raiders", 0, 0)
    store.assign_ships(campaign, raiders["id"], red, [s["uid"] for s in red["ships"]])
    store.save_fleet(blue)
    store.save_fleet(red)
    store.save_campaign(campaign)
    return campaign, blue, red


def test_an_installation_holds_its_force_and_cannot_withdraw():
    campaign, blue, _red = setup()
    garrison, raiders = campaign["forces"]
    assert store.reachable_systems(campaign, garrison)[0] == []
    station = store.get_design(blue["ships"][1]["design_id"])
    assert fleet_rules.force_reach([(blue["ships"][1], station)])[0] == 0
    store.set_force_order(campaign, raiders["id"], (5, 0))
    store.next_week(campaign)
    contact = store.this_weeks_contacts(campaign)[0]
    ok, msg = store.set_contact_choice(campaign, contact["id"], "blue", "withdraw")
    assert not ok and "cannot leave" in msg
    assert store.set_contact_choice(campaign, contact["id"], "blue", "fight")[0]


def test_an_installation_is_a_repair_yard():
    campaign, blue, _red = setup()
    furious, fort = blue["ships"]
    assert "naval base or installation" in store.yard_block(blue, furious)
    assert store.yard_block(blue, fort) == ""              # a station repairs where it stands
    store.assign_ships(campaign, campaign["forces"][0]["id"], blue, [furious["uid"]])
    store.save_campaign(campaign)
    assert store.yard_block(blue, furious) == "Dock the ship at Bravo first."
    furious["status"] = "docked"
    assert store.yard_block(blue, furious) == ""
    fort["status"] = "destroyed"
    store.save_fleet(blue)
    assert "naval base or installation" in store.yard_block(blue, furious)


def test_the_panel_marks_the_installation(client):
    campaign, blue, _red = setup()
    client.get(f"/fleet/{blue['id']}")
    page = client.get("/campaign").get_data(as_text=True)
    assert ">Installation</span>" in page
