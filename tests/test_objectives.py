"""Objectives and the end of a campaign (PLAN 11.3, step C7), and the Lafayette Incident
sample campaign (FT pp.36-38)."""

from __future__ import annotations

import pytest

import starmap
import store


@pytest.fixture(autouse=True)
def library(tmp_path, monkeypatch):
    monkeypatch.setenv("FTFM_DATA_DIR", str(tmp_path))
    return tmp_path


def lafayette() -> tuple[dict, dict]:
    fleet, _msg = store.create_fleet("fb", "Kiev Squadron", faction="ESU")
    campaign, _msg = store.lafayette_campaign(fleet)
    store.save_fleet(fleet)
    return store.get_campaign(campaign["id"]), fleet


def take(campaign: dict, *names: str) -> None:
    for system in campaign["map"]["systems"]:
        if system["name"] in names:
            system["owner"] = "esu"


def test_the_sample_campaign_follows_the_book():
    campaign, fleet = lafayette()
    assert [s["name"] for s in campaign["sides"]] == ["NAC", "ESU"] and fleet["campaign_side"] == "esu"
    systems = {s["name"]: s for s in campaign["map"]["systems"]}
    assert len(systems) == 10 and sum(s["kind"] == "settled" for s in systems.values()) == 6
    assert systems["New Toledo"]["base"] and systems["X"]["owner"] == ""
    assert starmap.hex_distance((13, 5), (6, 13)) > 6       # Lafayette is more than a jump from X
    assert campaign["end_week"] == 7 and "10,000" in campaign["notes"]


def test_holding_three_with_lafayette_wins_at_once():
    campaign, _fleet = lafayette()
    take(campaign, "Lafayette", "Hudson")
    assert store.next_week(campaign) == (True, "Week 2.")
    take(campaign, "Kakisa")
    ok, msg = store.next_week(campaign)
    assert ok and msg == "ESU wins: objective met." and campaign["week"] == 2
    assert store.next_week(campaign)[0] is False
    store.reopen_campaign(campaign)
    assert campaign["result"] is None


@pytest.mark.parametrize(("held", "winner"), [
    ((), "nac"), (("Lafayette", "Hudson"), "draw"), (("Hudson", "Baffin", "Kakisa"), "esu"),
    (("Hudson", "Baffin"), "nac"), (("Rock", "VN-459", "HR-1306"), "nac")])
def test_after_the_last_week_a_lesser_holding_draws_and_the_defender_wins(held, winner):
    campaign, _fleet = lafayette()
    campaign["objectives"]["esu"]["include"] = "Lafayette" if winner != "esu" else ""
    campaign["week"] = 7
    take(campaign, *held)
    store.next_week(campaign)
    assert campaign["result"]["winner"] == winner and campaign["week"] == 7


def test_objectives_are_set_on_the_tab(client):
    campaign, fleet = lafayette()
    client.get(f"/fleet/{fleet['id']}")
    page = client.get("/campaign").get_data(as_text=True)
    assert "Objectives" in page and 'value="Lafayette" selected' in page
    client.post(f"/campaigns/{campaign['id']}/action", data={
        "action": "set_objectives", "end_week": "5", "obj-nac-count": "6", "obj-nac-include": "",
        "obj-esu-count": "2", "obj-esu-include": "Hudson", "obj-esu-d0-count": "junk"})
    again = store.get_campaign(campaign["id"])
    assert again["end_week"] == 5
    assert again["objectives"]["esu"] == {"count": 2, "include": "Hudson", "draw": []}
    assert again["objectives"]["nac"]["count"] == 6


def test_the_sample_is_offered_without_a_campaign(client):
    fleet, _msg = store.create_fleet("fb", "Home Fleet", faction="NAC")
    client.get(f"/fleet/{fleet['id']}")
    assert "The Lafayette Incident" in client.get("/campaign").get_data(as_text=True)
    client.post(f"/campaign/{fleet['id']}/action", data={"action": "new_lafayette"})
    assert store.get_fleet(fleet["id"])["campaign_side"] == "nac"
