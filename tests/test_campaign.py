"""Campaign bookkeeping (PLAN 9.5, 11.1): damage, crew factors, repairs, replenishment, log."""

from __future__ import annotations

import pytest

import fleet_rules
import ssd_layout
import store

FURIOUS = "fb:fb1:nac-furious"


@pytest.fixture(autouse=True)
def library(tmp_path, monkeypatch):
    monkeypatch.setenv("FTFM_DATA_DIR", str(tmp_path))
    return tmp_path


def a_fleet(client=None) -> tuple[dict, str]:
    fleet, _msg = store.create_fleet("fb", "Home Fleet", faction="NAC", points_limit=1500)
    store.add_ship(fleet, FURIOUS)
    store.save_fleet(fleet)
    return fleet, fleet["ships"][0]["uid"]


def post(client, fleet, **data):
    return client.post(f"/campaign/{fleet['id']}/action", data=data, follow_redirects=True)


def text(response) -> str:
    return response.get_data(as_text=True)


# ---- Campaign maths -------------------------------------------------------------------------------


def test_crew_factors_fall_with_hull_damage():
    design = store.get_design(FURIOUS)
    left, total = fleet_rules.crew_factors_left(design, {"hull": 0})
    assert left == total > 0
    positions = sorted(fleet_rules.RULESETS["fb"].cf_positions(design))
    fewer, _total = fleet_rules.crew_factors_left(design, {"hull": positions[0]})
    assert fewer == left - 1
    none_left, _total = fleet_rules.crew_factors_left(design, {"hull": positions[-1]})
    assert none_left == 0


def test_a_ship_with_every_box_gone_is_crippled():
    design = store.get_design(FURIOUS)
    boxes = fleet_rules.hull_boxes(design)
    assert not fleet_rules.ship_is_crippled(design, {"hull": boxes - 1})
    assert fleet_rules.ship_is_crippled(design, {"hull": boxes})


def test_repair_plan_follows_ft_p35():
    design = store.get_design(FURIOUS)
    out = [s["uid"] for s in design["systems"]][:4]
    damage = {"hull": 4, "systems_out": out, "drive_hits": 2}

    plan = fleet_rules.repair_plan(design, damage, 6, out[:3], {out[0]: 1, out[1]: 0, out[2]: 1})
    assert plan["hull"] == 4                       # never more than the damage taken
    assert plan["systems"] == [out[0], out[2]]     # 3+ succeeded for two of the three
    assert not plan["too_many"]

    assert fleet_rules.repair_plan(design, damage, 1, out, {})["too_many"]   # only three a week

    # A disabled drive needs two successes, like the two hits that disabled it.
    assert fleet_rules.repair_plan(design, damage, 0, [], {"drive": 1})["drive_hits"] == 1
    assert fleet_rules.repair_plan(design, damage, 0, [], {"drive": 2})["drive_hits"] == 2


def test_repair_ignores_systems_the_ship_does_not_have():
    design = store.get_design(FURIOUS)
    plan = fleet_rules.repair_plan(design, {"systems_out": ["gone"]}, 0, ["gone"], {"gone": 1})
    assert plan["systems"] == []


# ---- Damage entry ----------------------------------------------------------------------------------


def test_damage_is_clamped_to_what_the_design_has():
    fleet, uid = a_fleet()
    design = store.get_design(FURIOUS)
    store.set_ship_damage(fleet, uid, hull=9999, armour=9999, drive_hits=9)
    damage = fleet["ships"][0]["damage"]
    assert damage["hull"] == fleet_rules.hull_boxes(design)
    assert damage["armour"] == design["armour"]
    assert damage["drive_hits"] == 2
    assert store.set_ship_damage(fleet, "nope", hull=1)[0] is False


def test_unknown_systems_are_dropped_from_the_damage():
    fleet, uid = a_fleet()
    real = store.get_design(FURIOUS)["systems"][0]["uid"]
    store.set_ship_damage(fleet, uid, systems_out=[real, "made-up"])
    assert fleet["ships"][0]["damage"]["systems_out"] == [real]


def test_toggling_a_system_knocks_it_out_and_back():
    fleet, uid = a_fleet()
    system = store.get_design(FURIOUS)["systems"][0]["uid"]
    assert store.toggle_system_out(fleet, uid, system)[0]
    assert fleet["ships"][0]["damage"]["systems_out"] == [system]
    assert store.toggle_system_out(fleet, uid, system)[0]
    assert fleet["ships"][0]["damage"]["systems_out"] == []
    assert store.toggle_system_out(fleet, uid, "nope")[0] is False


def test_repairs_and_replenishment_clear_the_right_state():
    fleet, uid = a_fleet()
    system = store.get_design(FURIOUS)["systems"][0]["uid"]
    store.set_ship_damage(fleet, uid, hull=6, drive_hits=2, systems_out=[system],
                          fighters_lost={"h": 2}, salvos_spent={"m": 1}, one_shot_used=["s"])
    store.repair_ship(fleet, uid, {"hull": 4, "systems": [system], "drive_hits": 1})
    damage = fleet["ships"][0]["damage"]
    assert damage["hull"] == 2 and damage["drive_hits"] == 1 and damage["systems_out"] == []
    assert damage["fighters_lost"] == {"h": 2}        # repairs are not replenishment

    store.replenish_ship(fleet, uid)
    damage = fleet["ships"][0]["damage"]
    assert damage["fighters_lost"] == {} and damage["salvos_spent"] == {}
    assert damage["one_shot_used"] == [] and damage["hull"] == 2


# ---- The tab ------------------------------------------------------------------------------------------


def test_the_tab_needs_a_fleet(client):
    assert "Create a fleet" in text(client.get("/campaign"))


def test_the_tab_shows_a_clickable_diagram_and_the_crew_factors(client):
    fleet, _uid = a_fleet()
    page = text(client.get("/campaign"))
    assert "CE-1" in page and "data-ref=" in page
    assert "Crew factors" in page and "campaign.js" in page


def test_clicking_the_diagram_marks_and_unmarks(client):
    fleet, uid = a_fleet()
    post(client, fleet, action="click_ssd", uid=uid, ref="hull:5")
    assert store.get_fleet(fleet["id"])["ships"][0]["damage"]["hull"] == 5
    post(client, fleet, action="click_ssd", uid=uid, ref="hull:5")   # the same box again
    assert store.get_fleet(fleet["id"])["ships"][0]["damage"]["hull"] == 4

    post(client, fleet, action="click_ssd", uid=uid, ref="armour:2")
    assert store.get_fleet(fleet["id"])["ships"][0]["damage"]["armour"] == 2

    system = store.get_design(FURIOUS)["systems"][0]["uid"]
    post(client, fleet, action="click_ssd", uid=uid, ref=f"system:{system}")
    assert store.get_fleet(fleet["id"])["ships"][0]["damage"]["systems_out"] == [system]

    assert "Nothing to change" in text(post(client, fleet, action="click_ssd", uid=uid, ref="odd:1"))


def test_the_diagram_refs_cover_hull_armour_and_systems():
    design = store.get_design(FURIOUS)
    refs = {p.ref.split(":")[0] for p in ssd_layout.layout(design).primitives if p.ref}
    assert refs == {"hull", "armour", "system"}


def test_recording_damage_through_the_form(client):
    fleet, uid = a_fleet()
    system = store.get_design(FURIOUS)["systems"][0]["uid"]
    page = text(post(client, fleet, action="set_damage", uid=uid, hull="7", armour="1",
                     drive_hits="1", systems_out=system))
    assert "Damage recorded." in page
    damage = store.get_fleet(fleet["id"])["ships"][0]["damage"]
    assert (damage["hull"], damage["armour"], damage["drive_hits"]) == (7, 1, 1)
    assert damage["systems_out"] == [system]


def test_repairing_through_the_form(client):
    fleet, uid = a_fleet()
    system = store.get_design(FURIOUS)["systems"][0]["uid"]
    post(client, fleet, action="set_damage", uid=uid, hull="6", drive_hits="2",
         systems_out=system)
    page = text(post(client, fleet, action="repair", uid=uid, hull_repaired="4",
                     repair_system=system, repair_success=system, drive_successes="1"))
    assert "repaired" in page
    damage = store.get_fleet(fleet["id"])["ships"][0]["damage"]
    assert damage["hull"] == 2 and damage["systems_out"] == [] and damage["drive_hits"] == 1


def test_replenishing_through_the_form(client):
    fleet, uid = a_fleet()
    fleet["ships"][0]["damage"]["fighters_lost"] = {"h": 3}
    store.save_fleet(fleet)
    assert "replenished" in text(post(client, fleet, action="replenish", uid=uid))
    assert store.get_fleet(fleet["id"])["ships"][0]["damage"]["fighters_lost"] == {}


def test_status_and_location_are_campaign_hooks(client):
    fleet, uid = a_fleet()
    post(client, fleet, action="update_ship", uid=uid, status="docked", location="Lafayette",
         squadron="sq1")
    ship = store.get_fleet(fleet["id"])["ships"][0]
    assert ship["status"] == "docked" and ship["location"] == "Lafayette"


def test_the_fleet_log_keeps_week_numbers(client):
    fleet, _uid = a_fleet()
    post(client, fleet, action="add_log", week="3", text="Raid on Chiang")
    assert store.get_fleet(fleet["id"])["log"] == [{"week": 3, "text": "Raid on Chiang"}]
    assert "Week 3" in text(client.get("/campaign"))


def test_campaign_damage_shows_on_the_diagram_and_the_pdf(client):
    fleet, uid = a_fleet()
    post(client, fleet, action="set_damage", uid=uid, hull="5", armour="2")
    design = store.get_design(FURIOUS)
    damaged = ssd_layout.layout(design, damage=store.get_fleet(fleet["id"])["ships"][0]["damage"])
    slashes = sum(1 for p in damaged.primitives
                  if isinstance(p, ssd_layout.Path) and p.stroke == 1.5)
    assert slashes == 7                      # 5 hull boxes + 2 armour circles


def test_the_dice_route_rolls_one_die(client):
    values = {int(client.get("/dice/6").get_data(as_text=True)) for _ in range(40)}
    assert values <= set(range(1, 7)) and len(values) > 1
    assert client.get("/dice/20").status_code == 404


def test_unknown_fleet_and_action(client):
    fleet, _uid = a_fleet()
    assert client.post("/campaign/nope/action", data={"action": "replenish"}).status_code == 404
    assert "Unknown action." in text(post(client, fleet, action="dance"))
