"""The Fleet overview tab (PLAN 9.3, 9.2 and the badges of section 7)."""

from __future__ import annotations

import pytest

import fleet_rules
import store

FURIOUS = "fb:fb1:nac-furious"
COURIER = "ft2:ft:courier"


@pytest.fixture(autouse=True)
def library(tmp_path, monkeypatch):
    monkeypatch.setenv("FTFM_DATA_DIR", str(tmp_path))
    return tmp_path


def make_fleet(client, name="Home Fleet", ruleset="fb", **extra) -> str:
    data = {"ruleset": ruleset, "name": name, "points_limit": "1000"}
    data.update(extra)
    client.post("/fleet/new", data=data)
    return next(f["id"] for f in store.list_fleets() if f["name"] == name)


def add_ship(client, fleet_id, design_id=FURIOUS, **extra):
    data = {"action": "add_ship", "design_id": design_id, "squadron": "sq1"}
    data.update(extra)
    return client.post(f"/fleet/{fleet_id}/action", data=data, follow_redirects=True)


def text(response) -> str:
    return response.get_data(as_text=True)


# ---- Fleets, selection and the top bar ----------------------------------------------------------


def test_the_tab_invites_a_first_fleet(client):
    page = text(client.get("/fleet"))
    assert "Create a fleet to get started." in page and "No fleets yet." in page
    assert "No fleet yet" in page  # the top-bar selector


def test_the_new_fleet_form_labels_its_dropdowns_and_numbers_rulesets_by_publication(client):
    page = text(client.get("/fleet"))
    form = page[page.index('name="ruleset"') - 200:page.index("Create fleet")]
    assert '<label class="field">Ruleset' in form and '<label class="field">Race' in form
    assert form.index("1. Full Thrust 2nd ed.") < form.index("2. Fleet Books") \
        < form.index("3. Cross Dimensions")
    assert 'value="fb" selected>2. Fleet Books' in form    # still the default pick
    assert '<optgroup label="1. Full Thrust 2nd ed.">' in form


def test_creating_a_fleet_selects_it_and_fills_the_top_bar(client):
    page = text(client.post("/fleet/new", data={"ruleset": "fb", "name": "Home Fleet",
                                                "points_limit": "1000"}, follow_redirects=True))
    assert "Fleet created." in page and "Home Fleet" in page
    assert "0 / 1000" in page                      # points meter
    assert 'ruleset-strip rs-fb' in page           # the ruleset strip (PLAN 9.2)
    assert 'badge rs-fb' in page


def test_fleets_are_listed_with_their_ruleset_and_can_be_switched(client):
    fb = make_fleet(client, "Home Fleet")
    ft2 = make_fleet(client, "Task Force", ruleset="ft2")
    page = text(client.get("/fleet"))
    assert "Home Fleet" in page and "Task Force" in page
    assert client.get(f"/fleet/{fb}", follow_redirects=True).status_code == 200
    assert "Home Fleet" in text(client.get("/fleet"))
    client.get(f"/fleet/{ft2}", follow_redirects=True)
    assert 'ruleset-strip rs-ft2' in text(client.get("/fleet"))
    assert client.get("/fleet/nope").status_code == 404


def test_deleting_a_fleet_clears_the_selection(client):
    fleet_id = make_fleet(client)
    page = text(client.post(f"/fleet/{fleet_id}/action", data={"action": "delete_fleet"},
                            follow_redirects=True))
    assert "Fleet deleted." in page and "Create a fleet to get started." in page


# ---- Ships and squadrons --------------------------------------------------------------------------


def test_adding_a_ship_numbers_it_and_shows_a_card(client):
    fleet_id = make_fleet(client)
    page = text(add_ship(client, fleet_id))
    assert "Furious added." in page and "CE-1" in page
    assert "<svg viewBox=" in page                  # the mini SSD on the card
    assert "219 / 1000" in text(client.get("/fleet"))


def test_a_ship_of_another_ruleset_is_refused(client):
    fleet_id = make_fleet(client)
    assert "another ruleset" in text(add_ship(client, fleet_id, design_id=COURIER))


def test_a_ruleset_with_no_designs_points_to_the_design_tab(client, monkeypatch):
    # An empty picker whose button says "Design not found." left people stuck, so the panel says
    # where designs come from instead. Every ruleset has catalog designs now, so take them away.
    real = store.catalog_designs
    monkeypatch.setattr(store, "catalog_designs",
                        lambda ruleset=None: [] if ruleset == "ftcd" else real(ruleset))
    make_fleet(client, "Explorers", ruleset="ftcd")
    page = text(client.get("/fleet"))
    assert "No ship designs for" in page and 'href="/design"' in page
    assert 'value="add_ship"' not in page
    assert 'value="add_ship"' in text(client.get(f"/fleet/{make_fleet(client)}", follow_redirects=True))

def test_a_cross_dimensions_fleet_fields_the_fleet_book_ships(client):
    # CD p.3: the Fleet Book designs serve Cross Dimensions, costed by its rules.
    fleet_id = make_fleet(client, "Explorers", ruleset="ftcd")
    add_ship(client, fleet_id, "ftcd:fb1:nac-furious")
    fleet = store.get_fleet(fleet_id)
    assert [s["design_id"] for s in fleet["ships"]] == ["ftcd:fb1:nac-furious"]
    assert '"fb:fb1:nac-furious"' not in text(client.get(f"/fleet/{fleet_id}"))


def test_ship_status_and_squadron_are_edited_from_the_card(client):
    fleet_id = make_fleet(client)
    add_ship(client, fleet_id)
    uid = store.get_fleet(fleet_id)["ships"][0]["uid"]
    client.post(f"/fleet/{fleet_id}/action",
                data={"action": "update_ship", "uid": uid, "status": "damaged", "squadron": "sq1"})
    assert store.get_fleet(fleet_id)["ships"][0]["status"] == "damaged"

    page = text(client.post(f"/fleet/{fleet_id}/action", data={"action": "remove_ship", "uid": uid},
                            follow_redirects=True))
    assert "Ship removed." in page
    assert store.get_fleet(fleet_id)["ships"] == []


def test_squadrons_are_added_renamed_moved_and_removed(client):
    fleet_id = make_fleet(client)
    client.post(f"/fleet/{fleet_id}/action", data={"action": "add_squadron", "name": "Escort"})
    assert [q["name"] for q in store.get_fleet(fleet_id)["squadrons"]] == ["Main body", "Escort"]

    client.post(f"/fleet/{fleet_id}/action",
                data={"action": "rename_squadron", "squadron": "sq2", "name": "Screen"})
    client.post(f"/fleet/{fleet_id}/action",
                data={"action": "move_squadron", "squadron": "sq2", "delta": "-1"})
    assert [q["name"] for q in store.get_fleet(fleet_id)["squadrons"]] == ["Screen", "Main body"]

    client.post(f"/fleet/{fleet_id}/action", data={"action": "remove_squadron", "squadron": "sq2"})
    assert len(store.get_fleet(fleet_id)["squadrons"]) == 1


def test_fleet_details_and_options_are_saved(client):
    fleet_id = make_fleet(client, ruleset="ft2")
    page = text(client.post(f"/fleet/{fleet_id}/action", data={
        "action": "update_details", "name": "Task Force", "admiral": "Brigstone",
        "points_limit": "1500", "faction": "NAC", "allow_race_mixing": "on",
        "opt-mt_systems": "on", "notes": "raiding",
    }, follow_redirects=True))
    assert "Fleet updated." in page
    fleet = store.get_fleet(fleet_id)
    assert fleet["name"] == "Task Force" and fleet["points_limit"] == 1500
    assert fleet["faction"] == "NAC" and fleet["allow_race_mixing"] is True
    assert fleet["options"]["mt_systems"] is True and fleet["options"]["rerolls"] is False


def test_a_bad_number_is_reported_not_raised(client):
    fleet_id = make_fleet(client)
    page = text(client.post(f"/fleet/{fleet_id}/action",
                            data={"action": "update_details", "name": "x", "points_limit": "lots"},
                            follow_redirects=True))
    assert "valid number" in page


def test_an_unknown_action_is_refused(client):
    fleet_id = make_fleet(client)
    assert "Unknown action." in text(client.post(f"/fleet/{fleet_id}/action", data={"action": "dance"},
                                                 follow_redirects=True))
    assert client.post("/fleet/nope/action", data={"action": "add_squadron"}).status_code == 404


# ---- Views ------------------------------------------------------------------------------------------


def test_the_three_views_render(client):
    fleet_id = make_fleet(client)
    add_ship(client, fleet_id)
    cards = text(client.get("/fleet?view=cards"))
    assert "Main body" in cards

    roster = text(client.get("/fleet?view=roster"))
    assert "Roster" in roster and "CE-1" in roster and "Furious" in roster

    sheet = text(client.get("/fleet?view=sheet"))
    assert "Record sheets" in sheet and "<svg viewBox=" in sheet


def test_docked_and_destroyed_ships_are_left_off_the_record_sheets(client):
    fleet_id = make_fleet(client)
    add_ship(client, fleet_id)
    uid = store.get_fleet(fleet_id)["ships"][0]["uid"]
    client.post(f"/fleet/{fleet_id}/action",
                data={"action": "update_ship", "uid": uid, "status": "docked", "squadron": "sq1"})
    page = text(client.get("/fleet?view=sheet"))
    assert "Not printed:" in page and "CE-1" in page


def test_an_unknown_view_falls_back_to_cards(client):
    make_fleet(client)
    assert "Main body" in text(client.get("/fleet?view=nonsense"))


# ---- Badges and the tournament check --------------------------------------------------------------


def test_badges_follow_the_fleet(client):
    fleet_id = make_fleet(client)
    add_ship(client, fleet_id)
    page = text(client.get("/fleet"))
    assert "No faction" in page and "Mixed faction" not in page    # no faction chosen yet
    assert "Non-conforming" not in page and "Custom ships" not in page

    client.post(f"/fleet/{fleet_id}/action",
                data={"action": "update_details", "name": "Home Fleet", "faction": "NAC",
                      "points_limit": "1000"})
    page = text(client.get("/fleet"))
    assert "Mixed faction" not in page and "No faction" not in page

    client.post(f"/fleet/{fleet_id}/action",
                data={"action": "update_details", "name": "Home Fleet", "faction": "NAC",
                      "points_limit": "10"})
    assert "Non-conforming" in text(client.get("/fleet"))


def test_a_variant_shows_the_custom_ships_badge(client):
    fleet_id = make_fleet(client)
    variant, _msg = store.make_variant(FURIOUS)
    add_ship(client, fleet_id, design_id=variant["id"])
    assert "Custom ships" in text(client.get("/fleet"))


def test_the_tournament_check_lists_issues_per_ship(client):
    fleet_id = make_fleet(client)
    add_ship(client, fleet_id)
    client.post(f"/fleet/{fleet_id}/action",
                data={"action": "update_details", "name": "Home Fleet", "points_limit": "10"})
    page = text(client.get(f"/fleet/{fleet_id}/check"))
    assert "Tournament check" in page
    assert "exceed the limit" in page
    assert "CE-1" in page and "Furious" in page
    assert client.get("/fleet/nope/check").status_code == 404


def test_the_check_of_an_empty_fleet_says_so(client):
    fleet_id = make_fleet(client)
    page = text(client.get(f"/fleet/{fleet_id}/check"))
    assert "no ships yet" in page and "Nothing to report at fleet level." in page


def test_new_fleet_form_offers_the_races_of_each_ruleset(client):
    body = client.get("/fleet").get_data(as_text=True)
    assert 'name="race"' in body and ("Kra'Vak" in body or "Kra&#39;Vak" in body)


def test_a_kravak_fleet_can_be_created_and_is_not_mixed_faction(client):
    """FB2's races have no factions of their own, so each gets the one its ship pages are
    headed with; without it every alien fleet would wear the mixed-faction badge."""
    client.post("/fleet/new", data={"ruleset": "fb", "name": "Spear Host", "race": "kravak",
                                    "faction": "KV"}, follow_redirects=True)
    fleet = next(f for f in store.list_fleets() if f["name"] == "Spear Host")
    assert fleet["race"] == "kravak" and fleet["faction"] == "KV"
    assert "KV" in {f["id"] for f in store.builtin_factions("fb")}
    designs = store.designs_for_fleet(fleet)
    assert not fleet_rules.badges(fleet, designs)["mixed_faction"]


def test_a_race_a_ruleset_does_not_have_is_refused(client):
    created, _msg = store.create_fleet("ft2", "Wrong race", "kravak")
    assert created is None


def test_a_savasku_fleet_is_not_mixed_faction(client):
    client.post("/fleet/new", data={"ruleset": "fb", "name": "Constructs", "race": "savasku",
                                    "faction": "SV"}, follow_redirects=True)
    fleet = next(f for f in store.list_fleets() if f["name"] == "Constructs")
    assert fleet["race"] == "savasku"
    assert "SV" in {f["id"] for f in store.builtin_factions("fb")}
    assert not fleet_rules.badges(fleet, store.designs_for_fleet(fleet))["mixed_faction"]


def test_a_phalon_fleet_is_not_mixed_faction(client):
    client.post("/fleet/new", data={"ruleset": "fb", "name": "Grand Fleet", "race": "phalon",
                                    "faction": "PH"}, follow_redirects=True)
    fleet = next(f for f in store.list_fleets() if f["name"] == "Grand Fleet")
    assert fleet["race"] == "phalon"
    assert "PH" in {f["id"] for f in store.builtin_factions("fb")}
    assert not fleet_rules.badges(fleet, store.designs_for_fleet(fleet))["mixed_faction"]


def test_a_fleet_offers_only_its_rulesets_options_by_name(client):
    fleet_id = make_fleet(client, ruleset="ftcd")
    page = text(client.get("/fleet"))
    assert 'badge rs-ftcd' in page and "ruleset-strip rs-ftcd" in page
    assert "Combat Points Value (CPV) hull cost" in page
    assert "opt-cd_cpv" in page and "opt-mt_systems" not in page and "opt-rerolls" not in page
    client.post(f"/fleet/{fleet_id}/action", data={
        "action": "update_details", "name": "Home Fleet", "points_limit": "1000", "opt-cd_cpv": "on",
    })
    options = store.get_fleet(fleet_id)["options"]
    assert options["cd_cpv"] is True and options["cd_advanced_ftl"] is False
