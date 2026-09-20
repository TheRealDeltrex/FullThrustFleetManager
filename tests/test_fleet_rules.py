"""Conformance, badges, points and the tournament check: every row of PLAN section 7."""

from __future__ import annotations

import pytest

import fleet_rules


def design(**kw) -> dict:
    d = {
        "schema_version": 1, "id": "d1", "ruleset": "fb", "race": "human", "faction": "NAC",
        "name": "Test", "type_label": "", "type_code": "CE", "hull_kind": "warship",
        "tmf": 20, "hull_boxes": 6, "armour": 0, "thrust": 4, "ftl": True, "streamlining": "none",
        # 20 MASS: hull 6 + drive 4 + FTL 2 + 2 beams 2 + PDS 1 + FC 1 = 16 -> pad with a hold
        "systems": [
            {"uid": "s1", "type": "beam", "class": 1, "arcs": ["F", "FS", "AS", "A", "AP", "FP"]},
            {"uid": "s2", "type": "beam", "class": 1, "arcs": ["F", "FS", "AS", "A", "AP", "FP"]},
            {"uid": "s3", "type": "pds"},
            {"uid": "s4", "type": "fire_control"},
            {"uid": "s5", "type": "hold", "kind": "cargo", "mass": 4},
        ],
        "default_loadout": {"fighters": [], "magazines": []},
        "allow_rule_breaking": False, "layout_hints": {}, "source": {"kind": "catalog"}, "notes": "",
    }
    d.update(kw)
    return d


def fleet(**kw) -> dict:
    f = {
        "schema_version": 1, "id": "f1", "ruleset": "fb", "race": "human", "allow_race_mixing": False,
        "faction": "NAC", "name": "Fleet", "admiral": "", "points_limit": 1000,
        "options": {}, "squadrons": [{"id": "sq1", "name": "Main"}], "ships": [], "campaign_id": None,
        "log": [], "notes": "",
    }
    f.update(kw)
    return f


def ship(uid="sh1", design_id="d1", **kw) -> dict:
    s = {"uid": uid, "design_id": design_id, "name": "N", "table_id": "CE-1", "squadron": "sq1",
         "status": "ready", "location": "", "loadout": None,
         "damage": {"hull": 0, "armour": 0, "systems_out": [], "drive_hits": 0,
                    "fighters_lost": {}, "salvos_spent": {}, "one_shot_used": []},
         "notes": ""}
    s.update(kw)
    return s


DESIGNS = {"d1": design()}


def test_design_conformance_is_computed_from_violations_only():
    assert fleet_rules.design_conforming(design(), {})
    broken = design(tmf=50)  # MASS no longer adds up
    assert not fleet_rules.design_conforming(broken, {})
    # allow_rule_breaking permits saving, it does not make a design conforming
    assert not fleet_rules.design_conforming(design(tmf=50, allow_rule_breaking=True), {})
    # ... and a design saved in bookkeeping mode that passes every check is conforming
    assert fleet_rules.design_conforming(design(allow_rule_breaking=True), {})


def test_points_include_loadouts_and_exclude_destroyed():
    d = design(systems=design()["systems"] + [{"uid": "h", "type": "hangar", "bays": 1}], tmf=29)
    designs = {"d1": d}
    f = fleet(ships=[ship()])
    npv = fleet_rules.design_points(d, {})
    # the design's default loadout is empty, so the ship costs its NPV
    assert fleet_rules.fleet_points(f, designs) == npv
    f["ships"][0]["loadout"] = {"fighters": [{"hangar": "h", "type": "heavy"}], "magazines": []}
    assert fleet_rules.fleet_points(f, designs) == npv + 30
    f["ships"][0]["status"] = "destroyed"
    assert fleet_rules.fleet_points(f, designs) == 0


def test_fleet_over_points_limit():
    f = fleet(points_limit=10, ships=[ship()])
    report = fleet_rules.fleet_report(f, DESIGNS)
    assert "over_points" in {i.code for i in report.fleet_issues}
    assert not report.conforming
    assert fleet_rules.fleet_conforming(fleet(points_limit=1000, ships=[ship()]), DESIGNS)


def test_no_limit_never_exceeds():
    assert fleet_rules.fleet_conforming(fleet(points_limit=0, ships=[ship()]), DESIGNS)


def test_non_conforming_ship_makes_the_fleet_non_conforming():
    designs = {"d1": design(tmf=50)}
    assert not fleet_rules.fleet_conforming(fleet(ships=[ship()]), designs)


def test_race_mixing():
    designs = {"d1": design(race="kravak")}
    f = fleet(ships=[ship()])
    assert "race_mixing" in {i.code for s in fleet_rules.fleet_report(f, designs).ships for i in s.issues}
    f["allow_race_mixing"] = True
    assert "race_mixing" not in {i.code for s in fleet_rules.fleet_report(f, designs).ships for i in s.issues}


def test_other_ruleset_is_guarded():
    designs = {"d1": design(ruleset="ft2", tmf=20, hull_boxes=0, systems=[])}
    codes = {i.code for s in fleet_rules.fleet_report(fleet(ships=[ship()]), designs).ships for i in s.issues}
    assert "wrong_ruleset" in codes


def test_missing_design_is_a_violation():
    report = fleet_rules.fleet_report(fleet(ships=[ship(design_id="gone")]), {})
    assert "missing_design" in {i.code for s in report.ships for i in s.issues}
    assert not report.conforming


def test_more_thrust_content_needs_the_fleet_toggle():
    d = {
        "schema_version": 1, "id": "m1", "ruleset": "ft2", "race": "human", "faction": None,
        "name": "MT", "type_label": "", "type_code": "", "hull_kind": "warship", "tmf": 60,
        "hull_boxes": 0, "armour": 0, "thrust": 2, "ftl": True, "streamlining": "none",
        "systems": [{"uid": "w", "type": "wave_gun", "arcs": ["F"]}, {"uid": "f", "type": "fire_control"}],
        "default_loadout": {"fighters": [], "magazines": []}, "allow_rule_breaking": False,
        "layout_hints": {}, "source": {"kind": "custom"}, "notes": "",
    }
    f = fleet(ruleset="ft2", faction=None, ships=[ship(design_id="m1")])
    codes = lambda: {i.code for s in fleet_rules.fleet_report(f, {"m1": d}).ships for i in s.issues}  # noqa: E731
    assert "mt_toggle_off" in codes()
    f["options"] = {"mt_systems": True}
    assert "mt_toggle_off" not in codes()


def test_campaign_damage_never_affects_conformance():
    f = fleet(ships=[ship(status="hulk", damage={"hull": 5, "armour": 0, "systems_out": ["s1"],
                                                 "drive_hits": 2, "fighters_lost": {}, "salvos_spent": {},
                                                 "one_shot_used": []})])
    assert fleet_rules.fleet_conforming(f, DESIGNS)


# ---- Badges ----------------------------------------------------------------------------------


def test_badge_non_conforming():
    assert badges(fleet(ships=[ship()]), DESIGNS)["non_conforming"] is False
    assert badges(fleet(points_limit=1, ships=[ship()]), DESIGNS)["non_conforming"] is True


def badges(f, d):
    return fleet_rules.badges(f, d)


@pytest.mark.parametrize(
    "fleet_faction,design_faction,mixed",
    [("NAC", "NAC", False), ("NAC", "NSL", True), ("NAC", None, True),
     (None, "NAC", True), (None, None, True)],
)
def test_badge_mixed_faction(fleet_faction, design_faction, mixed):
    designs = {"d1": design(faction=design_faction)}
    assert badges(fleet(faction=fleet_faction, ships=[ship()]), designs)["mixed_faction"] is mixed


def test_badge_custom_ships_and_variants():
    assert badges(fleet(ships=[ship()]), DESIGNS)["custom_ships"] is False
    for source in ({"kind": "custom"}, {"kind": "variant", "of": "fb:fb1:nac-furious"}):
        designs = {"d1": design(source=source)}
        assert badges(fleet(ships=[ship()]), designs)["custom_ships"] is True


def test_custom_faction_fleet_of_own_designs_is_not_mixed():
    designs = {"d1": design(faction="cf1", source={"kind": "custom"})}
    b = badges(fleet(faction="cf1", ships=[ship()]), designs)
    assert b["custom_ships"] is True and b["mixed_faction"] is False


def test_empty_fleet_with_faction_is_not_mixed():
    assert badges(fleet(ships=[]), DESIGNS)["mixed_faction"] is False


# ---- Tournament check ------------------------------------------------------------------------


def test_report_lists_infos_as_well_as_violations():
    designs = {"d1": design(ftl=False, tmf=18)}
    report = fleet_rules.fleet_report(fleet(ships=[ship()]), designs)
    codes = {(i.code, i.severity) for s in report.ships for i in s.issues}
    assert ("no_ftl", "info") in codes
    assert report.ships[0].conforming


def test_ship_counts():
    f = fleet(ships=[ship(), ship(uid="sh2", status="damaged"), ship(uid="sh3", status="damaged")])
    assert fleet_rules.ship_counts(f) == {"ready": 1, "damaged": 2}
