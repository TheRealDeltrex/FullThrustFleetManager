"""FTCD fleet-level rules: battle riders and motherships, system defence ships (CD pp.34-35)
and dummy bogeys (CD p.37)."""

from __future__ import annotations

from test_fleet_rules import fleet, ship
from test_rules_ftcd import design, heavy_cruiser, sys_

import fleet_rules


def cd_fleet(*pairs, **kw) -> tuple[dict, dict]:
    """A Cross Dimensions fleet of (design, status) pairs; returns (fleet, designs)."""
    designs, ships = {}, []
    for i, (d, status) in enumerate(pairs):
        d = {**d, "id": f"d{i}"}
        designs[d["id"]] = d
        ships.append(ship(uid=f"s{i}", design_id=d["id"], status=status, name=f"Ship {i}"))
    return fleet(ruleset="ftcd", ships=ships, points_limit=0, **kw), designs


def rider(tmf: int) -> dict:
    return design(tmf=tmf, hull_boxes=tmf // 10 or 1, ftl=False)


def tender(capacity: int, **kw) -> dict:
    return design(tmf=100, hull_boxes=10, ftl=True,
                  systems=[sys_("t", "tender_bay", capacity=capacity)], **kw)


def tug(tow: int, advanced: bool = False) -> dict:
    return design(tmf=100, hull_boxes=10, ftl=True, ftl_advanced=advanced,
                  systems=[sys_("g", "tug_drive", tow_mass=tow)])


def fleet_codes(f: dict, designs: dict) -> dict[str, str]:
    return {i.code: i.severity for i in fleet_rules.fleet_report(f, designs).fleet_issues}


def test_ftl_fleet_has_no_rider_issues():
    f, designs = cd_fleet((heavy_cruiser(), "ready"))
    assert fleet_codes(f, designs) == {}


def test_rider_without_a_mothership_is_a_violation():
    f, designs = cd_fleet((rider(30), "ready"))
    assert fleet_codes(f, designs) == {"riders_without_mothership": "violation"}


def test_tender_bay_carries_riders_and_says_so():
    f, designs = cd_fleet((rider(30), "ready"), (rider(20), "ready"), (tender(50), "ready"))
    assert fleet_codes(f, designs) == {"battle_riders": "info"}


def test_riders_must_each_fit_one_bay():
    # 40 + 40 MASS of riders, 30 + 50 of bays: the total fits, but one rider has nowhere to go.
    f, designs = cd_fleet((rider(40), "ready"), (rider(40), "ready"),
                          (tender(30), "ready"), (tender(50), "ready"))
    assert fleet_codes(f, designs) == {"riders_without_mothership": "violation"}


def test_bin_search_finds_a_packing_first_fit_would_miss():
    # Two bays of 7, riders 3, 3, 2, 2, 2, 2: first-fit puts both 3s in one bay and strands a
    # 2, but 3 + 2 + 2 in each bay carries them all.
    f, designs = cd_fleet(*[(rider(m), "ready") for m in (3, 3, 2, 2, 2, 2)],
                          (tender(7), "ready"), (tender(7), "ready"))
    assert fleet_codes(f, designs) == {"battle_riders": "info"}


def test_standard_tugs_do_not_combine_advanced_ones_do():
    # CD p.34: a crippled MASS 60 rider, two tugs of 30 transfer MASS each.
    f, designs = cd_fleet((rider(60), "ready"), (tug(30), "ready"), (tug(30), "ready"))
    assert fleet_codes(f, designs) == {"riders_without_mothership": "violation"}
    f, designs = cd_fleet((rider(60), "ready"), (tug(30, True), "ready"), (tug(30, True), "ready"))
    assert fleet_codes(f, designs) == {"battle_riders": "info"}


def test_mothership_needs_its_own_ftl_and_must_survive():
    no_ftl = {**tender(50), "ftl": False}
    f, designs = cd_fleet((rider(30), "ready"), (no_ftl, "ready"))
    assert "riders_without_mothership" in fleet_codes(f, designs)
    f, designs = cd_fleet((rider(30), "ready"), (tender(50), "destroyed"))
    assert "riders_without_mothership" in fleet_codes(f, designs)


def test_rider_over_mass_60_is_a_system_defence_ship():
    f, designs = cd_fleet((rider(62), "ready"), (tender(100), "ready"))
    assert fleet_codes(f, designs) == {"non_ftl_ship": "violation"}


def test_system_defence_option_allows_any_non_ftl_ship():
    f, designs = cd_fleet((rider(62), "ready"), (rider(30), "ready"),
                          options={"cd_system_defence": True})
    assert fleet_codes(f, designs) == {}


def test_dummy_bogeys_cost_20_and_are_capped_by_real_ships():
    f, designs = cd_fleet((heavy_cruiser(), "ready"), dummy_bogeys=1,
                          options={"cd_optional_systems": True})
    ship_points = fleet_rules.ship_points(f["ships"][0], designs["d0"], fleet_rules.fleet_options(f))
    assert fleet_rules.fleet_points(f, designs) == ship_points + 20
    assert fleet_codes(f, designs) == {}
    f["dummy_bogeys"] = 2
    assert fleet_codes(f, designs) == {"too_many_dummies": "violation"}


def test_dummy_bogeys_need_the_sensors_option():
    f, designs = cd_fleet((heavy_cruiser(), "ready"), dummy_bogeys=1)
    assert fleet_codes(f, designs) == {"option_off": "violation"}


def test_other_rulesets_ignore_dummy_bogeys():
    f = fleet(dummy_bogeys=3)
    assert fleet_rules.dummy_bogeys(f) == 0
    assert fleet_rules.fleet_points(f, {}) == 0


def test_fleet_details_form_saves_dummy_bogeys(client, tmp_path, monkeypatch):
    import store

    monkeypatch.setenv("FTFM_DATA_DIR", str(tmp_path))

    created, _ = store.create_fleet("ftcd", "Riders", "human", None, 0, False, "")
    store.add_ship(created, "ftcd:fb1:nac-ticonderoga", "", "", "")
    store.save_fleet(created)
    page = client.get(f"/fleet/{created['id']}", follow_redirects=True).get_data(as_text=True)
    assert 'name="dummy_bogeys"' in page
    client.post(f"/fleet/{created['id']}/action", data={
        "action": "update_details", "name": "Riders", "dummy_bogeys": "1",
        "opt-cd_optional_systems": "on"})
    saved = store.get_fleet(created["id"])
    assert saved["dummy_bogeys"] == 1 and saved["options"]["cd_optional_systems"]
    page = client.get("/fleet").get_data(as_text=True)
    assert "incl. 1 dummy bogeys (20)" in page
