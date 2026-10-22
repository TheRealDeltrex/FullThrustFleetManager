"""Task forces and movement on the star map (PLAN 11.3, step C3): who may jump, orders, the
weekly move, contacts, and the Task forces panel."""

from __future__ import annotations

import pytest

import fleet_rules
import store

FURIOUS = "fb:fb1:nac-furious"


@pytest.fixture(autouse=True)
def library(tmp_path, monkeypatch):
    monkeypatch.setenv("FTFM_DATA_DIR", str(tmp_path))
    return tmp_path


def a_design(**fields) -> str:
    design, _msg = store.new_design("fb", name=fields.pop("name", "Test design"))
    design.update(fields)
    store._write_design(design)
    return design["id"]


def a_campaign() -> tuple[dict, dict, dict]:
    """Blue (two Furious) and red (one) on a hand-made map: Alpha, Bravo 5 hexes east, Charlie 9."""
    blue, _msg = store.create_fleet("fb", "Home Fleet", faction="NAC")
    store.add_ship(blue, FURIOUS)
    store.add_ship(blue, FURIOUS)
    campaign, _msg = store.create_campaign(blue, "Lafayette Incident")
    red, _msg = store.create_fleet("fb", "Raiders", faction="NAC")
    store.add_ship(red, FURIOUS)
    store.join_campaign(red, campaign["id"], "red")
    store.new_starmap(campaign, 12, 10)
    for q, name in ((0, "Alpha"), (5, "Bravo"), (9, "Charlie")):
        store.set_star_system(campaign, q, 0, name=name, kind="settled", owner="", base=False)
    store.save_fleet(blue)
    store.save_fleet(red)
    store.save_campaign(campaign)
    return campaign, blue, red


def uids(fleet: dict) -> list[str]:
    return [s["uid"] for s in fleet["ships"]]


# ---- Who can jump ----------------------------------------------------------------------------------


def test_an_ftl_force_jumps_six_hexes_and_a_docked_or_fixed_one_does_not():
    furious = store.get_design(FURIOUS)
    ship = {"uid": "s1", "name": "Furious", "status": "ready", "damage": {}}
    assert fleet_rules.force_reach([(ship, furious)]) == (6, "")
    assert fleet_rules.force_reach([])[0] == 0
    assert fleet_rules.force_reach([(ship, None)])[0] == 0
    assert fleet_rules.force_reach([(dict(ship, status="docked"), furious)]) == (0, "Furious is docked.")
    base = store.get_design(a_design(hull_kind="starbase", ftl=False, thrust=0))
    assert fleet_rules.force_reach([(ship, furious), (ship, base)])[0] == 0
    # A ship the force has lost does not hold it back.
    assert fleet_rules.force_reach([(ship, furious), (dict(ship, status="destroyed"), base)])[0] == 6


def test_ships_without_ftl_need_carrying_in_the_force():
    ship = {"uid": "s1", "name": "Rider", "status": "ready", "damage": {}}
    rider = store.get_design(a_design(tmf=20, ftl=False))
    tender = store.get_design(a_design(tmf=80, systems=[{"uid": "t", "type": "tender_bay", "capacity": 20}]))
    assert fleet_rules.force_reach([(ship, rider)])[0] == 0
    assert fleet_rules.force_reach([(ship, rider), (ship, tender)])[0] == 6
    assert fleet_rules.force_reach([(ship, rider), (ship, rider), (ship, tender)])[0] == 0
    # A drive knocked out (FT p.35) leaves an FTL ship to be carried too.
    crippled = dict(ship, damage={"drive_hits": 2})
    assert fleet_rules.force_reach([(crippled, store.get_design(FURIOUS))])[0] == 0


# ---- Forces, orders and the week --------------------------------------------------------------------


def test_forces_form_on_systems_and_ships_belong_to_one_force():
    campaign, blue, red = a_campaign()
    assert store.add_force(campaign, "blue", "Nowhere", 2, 2)[0] is None
    assert store.add_force(campaign, "nobody", "Ghosts", 0, 0)[0] is None
    one, _msg = store.add_force(campaign, "blue", "1st Squadron", 0, 0)
    two, _msg = store.add_force(campaign, "blue", "", 0, 0)
    assert (one["id"], two["id"], two["name"]) == ("tf1", "tf2", "Task force 2")
    assert store.assign_ships(campaign, one["id"], red, uids(red))[0] is False
    assert store.assign_ships(campaign, one["id"], blue, uids(blue))[0]
    assert store.assign_ships(campaign, two["id"], blue, uids(blue)[:1])[0]
    assert [len(f["ships"]) for f in campaign["forces"]] == [1, 1]
    assert store.unassign_ship(campaign, two["id"], blue["id"], uids(blue)[0])[0]
    assert two["ships"] == []
    # Junk on disk is dropped: an unknown side, a ship listed twice, a force off the map.
    campaign["forces"] += [{"id": "x", "side": "nobody", "q": 0, "r": 0, "ships": []},
                           {"id": "y", "side": "blue", "q": 50, "r": 0, "ships": []},
                           {"id": "tf3", "side": "blue", "name": "Dup", "q": 5, "r": 0,
                            "ships": [{"fleet": blue["id"], "uid": uids(blue)[1]}]}]
    store.save_campaign(campaign)
    again = store.get_campaign(campaign["id"])
    assert [f["id"] for f in again["forces"]] == ["tf1", "tf2", "tf3"]
    assert again["forces"][2]["ships"] == []


def test_orders_reach_six_hexes_and_next_week_moves_and_logs_the_contact():
    campaign, blue, red = a_campaign()
    hunters, _msg = store.add_force(campaign, "blue", "Hunters", 0, 0)
    store.assign_ships(campaign, hunters["id"], blue, uids(blue))
    raiders, _msg = store.add_force(campaign, "red", "Raiders", 9, 0)
    store.assign_ships(campaign, raiders["id"], red, uids(red))
    options, why = store.reachable_systems(campaign, hunters)
    assert [(s["name"], d) for s, d in options] == [("Bravo", 5)] and why == ""
    assert store.set_force_order(campaign, hunters["id"], (9, 0))[0] is False
    assert store.set_force_order(campaign, hunters["id"], (5, 0))[0]
    assert store.set_force_order(campaign, raiders["id"], (5, 0))[0]
    ok, msg = store.next_week(campaign)
    assert ok and msg == "Week 2: contact at Bravo."
    assert (hunters["q"], hunters["order"]) == (5, None)
    assert campaign["log"][-1] == {"week": 2, "text": "Contact at Bravo: Hunters (Blue), Raiders (Red).",
                                   "sides": ["blue", "red"]}
    assert {s["location"] for s in store.get_fleet(blue["id"])["ships"]} == {"Bravo"}
    assert [system["name"] for system, _forces in store.meetings(campaign)] == ["Bravo"]


def test_a_docked_force_holds_and_a_new_map_clears_the_forces():
    campaign, blue, _red = a_campaign()
    force, _msg = store.add_force(campaign, "blue", "Yard", 0, 0)
    store.assign_ships(campaign, force["id"], blue, uids(blue))
    store.update_ship(blue, uids(blue)[0], status="docked")
    store.save_fleet(blue)
    options, why = store.reachable_systems(campaign, force)
    assert options == [] and "docked" in why
    assert store.set_force_order(campaign, force["id"], (5, 0))[0] is False
    assert store.remove_star_system(campaign, 0, 0)[0] is False
    assert store.next_week(campaign) == (True, "Week 2.")
    store.new_starmap(campaign, 8, 8)
    assert campaign["forces"] == []


# ---- The Task forces panel ---------------------------------------------------------------------------


def test_the_panel_forms_a_force_plots_its_jump_and_moves_it(client):
    campaign, blue, _red = a_campaign()
    client.get(f"/fleet/{blue['id']}")
    page = client.get("/campaign").get_data(as_text=True)
    assert "Task forces" in page and "New task force" in page
    url = f"/campaigns/{campaign['id']}/action"
    client.post(url, data={"action": "add_force", "side": "blue", "name": "Hunters", "at": "0,0",
                           "fleet": blue["id"], "ship": uids(blue)})
    force = store.get_campaign(campaign["id"])["forces"][0]
    assert force["name"] == "Hunters" and len(force["ships"]) == 2
    page = client.get("/campaign").get_data(as_text=True)
    assert "Jump to Bravo (5 hexes)" in page and 'class="pennant side-0"' in page
    client.post(url, data={"action": "update_force", "force": "tf1", "name": "Hunters", "order": "5,0"})
    assert store.get_campaign(campaign["id"])["forces"][0]["order"] == [5, 0]
    assert 'class="order side-0"' in client.get("/campaign").get_data(as_text=True)
    client.post(url, data={"action": "next_week"})
    assert store.get_campaign(campaign["id"])["forces"][0]["q"] == 5
    client.post(f"{url}?ship={blue['id']}:{uids(blue)[0]}", data={"action": "unassign_ship", "force": "tf1"})
    assert len(store.get_campaign(campaign["id"])["forces"][0]["ships"]) == 1
    client.post(url, data={"action": "remove_force", "force": "tf1"})
    assert store.get_campaign(campaign["id"])["forces"] == []
