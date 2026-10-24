"""The Space Dock view of the Fleet overview and drag-to-arrange ship diagrams."""

from __future__ import annotations

import pytest

import store

ARK = "fb:fb1:nac-ark-royal"
FURIOUS = "fb:fb1:nac-furious"


@pytest.fixture(autouse=True)
def library(tmp_path, monkeypatch):
    monkeypatch.setenv("FTFM_DATA_DIR", str(tmp_path))
    return tmp_path


def fleet_with(*design_ids) -> dict:
    fleet, _msg = store.create_fleet("fb", "Home Fleet")
    for design_id in design_ids:
        store.add_ship(fleet, design_id)
    store.save_fleet(fleet)
    return fleet


def test_the_dock_shows_the_picked_ship_with_its_diagram_and_specs(client):
    fleet = fleet_with(FURIOUS, ARK)
    client.get(f"/fleet/{fleet['id']}")
    page = client.get("/fleet?view=dock&ship=sh2").get_data(as_text=True)
    assert "Space Dock" in page and 'class="ssd-edit"' in page and '<g class="sys"' in page
    assert "Hangar bay" in page and "Refit as variant" in page
    # The pick is remembered for the fleet.
    assert "Hangar bay" in client.get("/fleet?view=dock").get_data(as_text=True)


def test_the_dock_diagram_offers_arrange_for_touch_screens(client):
    fleet = fleet_with(FURIOUS)
    client.get(f"/fleet/{fleet['id']}")
    page = client.get("/fleet?view=dock").get_data(as_text=True)
    assert 'class="btn sm ghost ssd-arrange" type="button" aria-pressed="false"' in page


def test_an_empty_fleet_has_an_empty_dock(client):
    fleet = fleet_with()
    client.get(f"/fleet/{fleet['id']}")
    assert "No ships yet." in client.get("/fleet?view=dock").get_data(as_text=True)


def test_refit_moves_the_ship_to_another_design_and_drops_stale_damage(client):
    fleet = fleet_with(FURIOUS)
    fleet["ships"][0]["damage"]["systems_out"] = [store.get_design(FURIOUS)["systems"][0]["uid"] + "x"]
    store.save_fleet(fleet)
    client.post(f"/fleet/{fleet['id']}/action?view=dock&ship=sh1",
                data={"action": "refit_ship", "uid": "sh1", "design_id": ARK, "autosave": "1"})
    ship = store.get_fleet(fleet["id"])["ships"][0]
    assert ship["design_id"] == ARK and ship["damage"]["systems_out"] == []


def test_refit_refuses_a_design_of_another_ruleset():
    fleet = fleet_with(FURIOUS)
    ok, _msg = store.refit_ship(fleet, "sh1", "ft2:ft:courier")
    assert not ok and fleet["ships"][0]["design_id"] == FURIOUS


def test_refit_as_variant_gives_the_ship_its_own_design_and_opens_it(client):
    fleet = fleet_with(FURIOUS, FURIOUS)
    response = client.post(f"/fleet/{fleet['id']}/action", data={"action": "refit_variant", "uid": "sh1"})
    ships = store.get_fleet(fleet["id"])["ships"]
    assert ships[0]["design_id"] != FURIOUS and ships[1]["design_id"] == FURIOUS
    assert response.headers["Location"].endswith(f"/design/{ships[0]['design_id']}")


def test_dragging_pins_a_catalog_system_and_reset_clears_it(client):
    uid = store.get_design(FURIOUS)["systems"][0]["uid"]
    client.post(f"/design/{FURIOUS}/layout", data={"uid": uid, "x": "40", "y": "50", "next": "/fleet"})
    assert store.get_design(FURIOUS)["layout_hints"] == {uid: {"x": 40.0, "y": 50.0}}
    # A variant made from it starts with the same arrangement.
    variant, _msg = store.make_variant(FURIOUS)
    assert variant["layout_hints"] == {uid: {"x": 40.0, "y": 50.0}}
    client.post(f"/design/{FURIOUS}/layout", data={"action": "reset_layout"})
    assert store.get_design(FURIOUS)["layout_hints"] == {}


def test_dragging_a_library_design_saves_it_and_its_draft(client):
    design, _msg = store.make_variant(FURIOUS)
    store.save_draft(dict(design, name="Edited"))
    uid = design["systems"][0]["uid"]
    response = client.post(f"/design/{design['id']}/layout", data={"uid": uid, "x": "10", "y": "20"})
    assert response.headers["Location"].endswith(f"/design/{design['id']}")
    assert store.get_design(design["id"])["layout_hints"][uid] == {"x": 10.0, "y": 20.0}
    assert store.get_draft(design["id"])["layout_hints"][uid] == {"x": 10.0, "y": 20.0}


def test_a_bad_drag_is_refused(client):
    client.post(f"/design/{FURIOUS}/layout", data={"uid": "nope", "x": "1", "y": "2"})
    client.post(f"/design/{FURIOUS}/layout", data={"uid": "s1", "x": "nan", "y": "2"})
    assert store.get_design(FURIOUS)["layout_hints"] == {}


def test_next_must_stay_on_this_app(client):
    response = client.post(f"/design/{FURIOUS}/layout",
                           data={"action": "reset_layout", "next": "//evil.example/"})
    assert response.headers["Location"].endswith(f"/design/{FURIOUS}")


def test_backups_carry_catalog_layouts():
    fleet_with(FURIOUS)  # a backup needs something in it
    uid = store.get_design(FURIOUS)["systems"][0]["uid"]
    store.set_layout_hint(FURIOUS, uid, 5, 6)
    _name, data = store.export_backup()
    store.set_layout_hint(FURIOUS, None)
    assert store.import_file("b.FTBackup", data)[0]
    assert store.get_design(FURIOUS)["layout_hints"] == {uid: {"x": 5, "y": 6}}
