"""Contacts and battles (PLAN 11.3, step C4): the long-range scan, fight, withdraw or stand off
with the catch roll (FT pp.34-35), the battle result and who holds the system afterwards."""

from __future__ import annotations

import pytest

import fleet_rules
import store
from rulesets import RULESETS

FURIOUS = "fb:fb1:nac-furious"


@pytest.fixture(autouse=True)
def library(tmp_path, monkeypatch):
    monkeypatch.setenv("FTFM_DATA_DIR", str(tmp_path))
    return tmp_path


def met() -> tuple[dict, dict, dict]:
    """Blue (two Furious) and red (one) both jump into blue's settled Bravo: one contact."""
    blue, _msg = store.create_fleet("fb", "Home Fleet", faction="NAC")
    store.add_ship(blue, FURIOUS)
    store.add_ship(blue, FURIOUS)
    campaign, _msg = store.create_campaign(blue, "Lafayette Incident")
    red, _msg = store.create_fleet("fb", "Raiders", faction="NAC")
    store.add_ship(red, FURIOUS)
    store.join_campaign(red, campaign["id"], "red")
    store.new_starmap(campaign, 12, 10)
    for q, name in ((0, "Alpha"), (5, "Bravo"), (9, "Charlie")):
        store.set_star_system(campaign, q, 0, name=name, kind="settled", owner="blue" if q == 5 else "",
                              base=False)
    store.save_fleet(blue)
    store.save_fleet(red)
    for side, fleet, q in (("blue", blue, 0), ("red", red, 9)):
        force, _msg = store.add_force(campaign, side, side.title(), q, 0)
        store.assign_ships(campaign, force["id"], fleet, [s["uid"] for s in fleet["ships"]])
        store.set_force_order(campaign, force["id"], (5, 0))
    store.next_week(campaign)
    store.save_campaign(campaign)
    return campaign, blue, red


def test_scan_classes_follow_each_ruleset():
    assert fleet_rules.scan_counts([({"status": "ready"}, store.get_design(FURIOUS))]) == {
        "escort": 0, "cruiser": 1, "capital": 0}
    assert RULESETS["ft2"].scan_class({"ruleset": "ft2", "tmf": 18}) == "escort"
    assert RULESETS["ft2"].scan_class({"ruleset": "ft2", "tmf": 200}) == "capital"
    assert RULESETS["ftcd"].scan_class({"tmf": 91}) == "capital"
    assert RULESETS["fb"].scan_class({"tmf": 44}) == "escort"


def test_the_choices_settle_a_contact_as_ft_p35_says():
    outcome = fleet_rules.contact_outcome
    assert outcome({"a": "fight", "b": "fight"}, None) == ("battle", [])
    assert outcome({"a": "fight", "b": "standoff"}, None) == ("battle", [])
    assert outcome({"a": "standoff", "b": "standoff"}, None) == ("standoff", [])
    assert outcome({"a": "withdraw", "b": "standoff"}, None) == ("leave", ["a", "b"])
    assert outcome({"a": "fight", "b": "withdraw"}, 5) == ("escaped", ["b"])
    assert outcome({"a": "fight", "b": "withdraw"}, 6) == ("battle", [])
    assert fleet_rules.catch_roll_needed({"a": "fight", "b": "withdraw"})
    assert not fleet_rules.catch_roll_needed({"a": "fight", "b": "standoff"})


def test_a_meeting_opens_a_contact_with_each_sides_real_scan():
    campaign, _blue, _red = met()
    [contact] = store.this_weeks_contacts(campaign)
    assert contact["sides"] == ["blue", "red"] and contact["week"] == 2
    assert contact["reports"]["blue"]["cruiser"] == 2 and contact["reports"]["red"]["cruiser"] == 1
    # Decoys and weasel boats: a side shows what it likes until the choices are in.
    assert store.set_contact_report(campaign, contact["id"], "red", {"capital": 3})[0]
    assert contact["reports"]["red"] == {"escort": 0, "cruiser": 0, "capital": 3}
    assert store.next_week(campaign)[0] is False      # not settled yet
    store.save_campaign(campaign)
    assert store.get_campaign(campaign["id"])["contacts"][0]["reports"]["red"]["capital"] == 3


def test_a_won_battle_takes_the_system_and_drives_the_loser_out():
    campaign, _blue, _red = met()
    cid = campaign["contacts"][0]["id"]
    assert store.set_contact_choice(campaign, cid, "blue", "fight") == (True, "Choice made.")
    ok, text = store.set_contact_choice(campaign, cid, "red", "standoff")
    assert ok and text == "Bravo: battle."
    assert store.next_week(campaign) == (False, "Record the battle at Bravo first.")
    ok, text = store.set_battle_result(campaign, cid, "red", "Blue lost both cruisers")
    assert text == "Bravo: battle won by Red. Bravo is now held by Red."
    assert campaign["map"]["systems"][1]["owner"] == "red"
    assert store.next_week(campaign) == (False, "Blue must leave Bravo this week.")
    store.reopen_contact(campaign, cid)
    assert campaign["map"]["systems"][1]["owner"] == "blue"
    assert campaign["contacts"][0]["outcome"] == ""


def test_a_caught_fleet_fights_and_one_that_gets_away_must_leave():
    campaign, _blue, _red = met()
    cid = campaign["contacts"][0]["id"]
    store.set_contact_choice(campaign, cid, "red", "withdraw")
    ok, text = store.set_contact_choice(campaign, cid, "blue", "fight", roll=6)
    assert text == "Bravo: battle (catch roll 6)."
    store.reopen_contact(campaign, cid)
    store.set_contact_choice(campaign, cid, "red", "withdraw")
    ok, text = store.set_contact_choice(campaign, cid, "blue", "fight", roll=3)
    assert text == "Bravo: Red got away (catch roll 3)."     # blue already holds Bravo
    assert campaign["contacts"][0]["leaving"] == ["red"]
    red_force = campaign["forces"][1]
    assert store.next_week(campaign)[1] == "Red must leave Bravo this week."
    assert store.set_force_order(campaign, red_force["id"], (9, 0))[0]
    assert store.next_week(campaign)[0]


def test_the_contacts_panel_takes_choices_and_records_the_battle(client):
    campaign, blue, _red = met()
    client.get(f"/fleet/{blue['id']}")
    page = client.get("/campaign").get_data(as_text=True)
    assert "Contacts" in page and "Scan shows" in page and "1 cruiser" in page and "Choosing" in page
    url = f"/campaigns/{campaign['id']}/action"
    client.post(url, data={"action": "contact_choice", "contact": "k1", "side": "blue", "choice": "fight"})
    client.post(url, data={"action": "contact_choice", "contact": "k1", "side": "red", "choice": "fight"})
    page = client.get("/campaign").get_data(as_text=True)
    assert "Record battle" in page and "Won by Red" in page
    client.post(url, data={"action": "battle_result", "contact": "k1", "result": "drawn", "notes": ""})
    saved = store.get_campaign(campaign["id"])
    assert saved["contacts"][0]["result"] == "drawn"
    assert saved["log"][-1]["text"] == "Bravo: battle broken off."
    assert "Broken off" in client.get("/campaign").get_data(as_text=True)
