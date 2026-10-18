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


# ---- Jump gates, portals and starbase sections (CD pp.35, 51) ---------------------------------


def gate(transfer: int, kind: str = "jump_gate", **kw) -> dict:
    return design(**{"tmf": 20, "hull_boxes": 6, "ftl": False,
                     "systems": [sys_("g", kind, transfer_mass=transfer)], **kw})


def test_jump_gate_drive_moves_10_transfer_mass_per_mass():
    from test_rules_ftcd import CD, system_row

    row = system_row(gate(60), "g")
    assert (row.mass, row.points) == (6, 12)  # CD p.35, paid as FTL at 2 a MASS
    assert system_row(gate(64), "g").mass == 6 and system_row(gate(65), "g").mass == 7
    assert system_row(gate(4), "g").mass == 1  # never 0 MASS (CD p.42)
    assert CD.design_breakdown(gate(60), {}).derived["transfer_mass"] == 60


def test_portal_drive_is_as_big_as_its_transfer_mass():
    from test_rules_ftcd import system_row

    row = system_row(gate(12, "portal", tmf=20, hull_boxes=2), "g")
    assert (row.mass, row.points) == (12, 24)


def test_gate_needs_hull_of_10_percent_of_transfer_mass_and_no_thrust():
    from test_rules_ftcd import codes

    assert "gate_hull" in codes(gate(70, hull_boxes=6))
    assert "gate_hull" not in codes(gate(60, hull_boxes=6))
    assert "stationary_thrust" in codes(gate(60, thrust=2))
    assert "no_ftl" not in codes(gate(60))


def test_gate_is_jump_gate_or_portal_not_both():
    from test_rules_ftcd import codes

    both = gate(20, systems=[sys_("a", "jump_gate", transfer_mass=20),
                             sys_("b", "portal", transfer_mass=2)])
    assert "gate_and_portal" in codes(both)


def test_starbase_section_is_stationary():
    from test_rules_ftcd import CD, codes

    section = design(hull_kind="starbase", tmf=100, hull_boxes=30, thrust=0, ftl=False)
    assert "stationary_thrust" not in codes(section) and "no_ftl" not in codes(section)
    assert "stationary_thrust" in codes({**section, "thrust": 1})
    assert CD.suggest_type(section)[1] == "SB"
    assert CD.suggest_type(gate(60))[1] == "JG"
    assert CD.suggest_type(gate(6, "portal"))[1] == "PT"


def test_starbases_and_gates_are_not_battle_riders():
    section = design(hull_kind="starbase", tmf=200, hull_boxes=60, ftl=False)
    f, designs = cd_fleet((section, "ready"), (gate(60), "ready"))
    assert fleet_codes(f, designs) == {}


def test_design_tab_offers_starbase_only_for_cross_dimensions(client, tmp_path, monkeypatch):
    import store

    monkeypatch.setenv("FTFM_DATA_DIR", str(tmp_path))
    cd, _ = store.new_design("ftcd", "human", None, "Station", "")
    fb, _ = store.new_design("fb", "human", None, "Ship", "")
    assert 'value="starbase"' in client.get(f"/design/{cd['id']}").get_data(as_text=True)
    assert 'value="starbase"' not in client.get(f"/design/{fb['id']}").get_data(as_text=True)


def test_gate_draws_its_transfer_mass():
    import ssd_layout

    svg = ssd_layout.to_svg(ssd_layout.layout(gate(60)))
    assert "GATE 60" in svg
