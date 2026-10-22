"""Hidden movement (PLAN 11.3, step C6): each side sees its own markers and what it has met,
behind a hand-over screen; the umpire sees everything (FT p.34). Dummy markers."""

from __future__ import annotations

import pytest

import store

FURIOUS = "fb:fb1:nac-furious"


@pytest.fixture(autouse=True)
def library(tmp_path, monkeypatch):
    monkeypatch.setenv("FTFM_DATA_DIR", str(tmp_path))
    return tmp_path


def setup() -> tuple[dict, dict, dict]:
    blue, _msg = store.create_fleet("fb", "Home Fleet", faction="NAC")
    store.add_ship(blue, FURIOUS)
    campaign, _msg = store.create_campaign(blue, "Lafayette Incident")
    red, _msg = store.create_fleet("fb", "Strike Group", faction="NAC")
    store.add_ship(red, FURIOUS)
    store.join_campaign(red, campaign["id"], "red")
    store.new_starmap(campaign, 12, 10)
    for q, name in ((0, "Alpha"), (5, "Bravo"), (9, "Charlie")):
        store.set_star_system(campaign, q, 0, name=name, kind="settled", owner="", base=False)
    for side, fleet, q, name in (("blue", blue, 0, "Hunters"), ("red", red, 9, "Raiders")):
        force, _msg = store.add_force(campaign, side, name, q, 0)
        store.assign_ships(campaign, force["id"], fleet, [s["uid"] for s in fleet["ships"]])
    store.update_campaign(campaign, hidden=True)
    store.save_fleet(blue)
    store.save_fleet(red)
    store.save_campaign(campaign)
    return campaign, blue, red


def test_a_side_sees_only_its_own_forces_until_contact():
    campaign, _blue, _red = setup()
    hunters, raiders = campaign["forces"]
    assert store.sees_force(campaign, "blue", hunters) and not store.sees_force(campaign, "blue", raiders)
    store.set_force_order(campaign, hunters["id"], (5, 0))
    store.set_force_order(campaign, raiders["id"], (5, 0))
    assert store.next_week(campaign) == (True, "Week 2.")     # no news for whoever pressed it
    assert store.sees_force(campaign, "blue", raiders)
    assert not store.sees_log(campaign, "green", campaign["log"][-1])
    campaign["hidden"] = False
    assert store.sees_force(campaign, "green", raiders)


def test_a_dummy_marker_moves_freely_and_is_exposed_by_an_enemy():
    campaign, blue, _red = setup()
    hunters = campaign["forces"][0]
    dummy, _msg = store.add_force(campaign, "red", "Ghost", 9, 0, dummy=True)
    assert store.assign_ships(campaign, dummy["id"], blue, [blue["ships"][0]["uid"]])[0] is False
    assert [s["name"] for s, _d in store.reachable_systems(campaign, dummy)[0]] == ["Bravo"]
    store.set_force_order(campaign, dummy["id"], (5, 0))
    store.set_force_order(campaign, hunters["id"], (5, 0))
    store.next_week(campaign)
    assert dummy not in campaign["forces"]
    assert store.this_weeks_contacts(campaign) == []
    assert campaign["log"][-1]["text"] == "Ghost (Red) at Bravo was a dummy marker."
    store.save_campaign(campaign)
    assert store.get_campaign(campaign["id"])["hidden"] is True


def test_the_tab_hands_over_and_hides_the_other_side(client):
    campaign, blue, red = setup()
    client.get(f"/fleet/{blue['id']}")
    page = client.get("/campaign").get_data(as_text=True)
    assert "Hand over to Blue" in page and "Hunters" not in page
    view = f"/campaigns/{campaign['id']}/view"
    client.post(view, data={"view": "show"})
    page = client.get("/campaign").get_data(as_text=True)
    assert "Hunters" in page and "Raiders" not in page
    client.post(view, data={"view": "umpire"})
    page = client.get("/campaign").get_data(as_text=True)
    assert "Hunters" in page and "Raiders" in page
    client.post(view, data={"view": "show"})
    client.get(f"/fleet/{red['id']}")                # the next player takes the screen
    assert "Hand over to Red" in client.get("/campaign").get_data(as_text=True)
    client.post(f"/campaigns/{campaign['id']}/action", data={
        "action": "update_campaign", "name": "Lafayette Incident", "week": "1", "hidden": ["0"]})
    assert store.get_campaign(campaign["id"])["hidden"] is False
