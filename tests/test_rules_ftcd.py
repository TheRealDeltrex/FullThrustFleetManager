"""FTCD ruleset: Full Thrust Cross Dimensions ship design (CD pp.41-47, printed pages).

Golden test first: the CD p.46 Heavy Cruiser, built line by line in the book, is 294 points.
"""

from __future__ import annotations

import pytest

from rulesets import RULESETS

CD = RULESETS["ftcd"]

BROADSIDE = ["FS", "AS", "AP", "FP"]
FRONT3 = ["FP", "F", "FS"]


def sys_(uid: str, stype: str, **params) -> dict:
    return {"uid": uid, "type": stype, **params}


def design(**fields) -> dict:
    base = {
        "id": "t", "ruleset": "ftcd", "race": "human", "name": "Test", "hull_kind": "warship",
        "tmf": 20, "hull_boxes": 4, "armour": 0, "armour_layers": [], "thrust": 0, "ftl": False,
        "streamlining": "none", "systems": [], "default_loadout": {"fighters": [], "magazines": []},
    }
    return {**base, **fields}


def heavy_cruiser() -> dict:
    """CD p.46: MASS 86, average hull 26, FTL, thrust 4, 2 x beam-3 (3 arcs), beam-2 (6 arcs),
    2 x beam-1, 2 FireCons, SML forward with a 3-salvo magazine, level-1 screen, 2 PDS."""
    return design(
        tmf=86, hull_boxes=26, thrust=4, ftl=True,
        systems=[
            sys_("b1", "beam", **{"class": 3, "arcs": ["AP", "FP", "F"]}),
            sys_("b2", "beam", **{"class": 3, "arcs": ["F", "FS", "AS"]}),
            sys_("b3", "beam", **{"class": 2, "arcs": ["F", "FS", "AS", "A", "AP", "FP"]}),
            sys_("b4", "beam", **{"class": 1, "arcs": ["F", "FS", "AS", "A", "AP", "FP"]}),
            sys_("b5", "beam", **{"class": 1, "arcs": ["F", "FS", "AS", "A", "AP", "FP"]}),
            sys_("f1", "fire_control"), sys_("f2", "fire_control"),
            sys_("l1", "sm_launcher", arcs=FRONT3),
            sys_("m1", "sm_magazine", capacity=6, feeds=["l1"]),
            sys_("s1", "screen", level=1),
            sys_("p1", "pds"), sys_("p2", "pds"),
        ],
        default_loadout={"fighters": [], "magazines": [{"magazine": "m1", "salvos": ["std"] * 3}]},
    )


def rows(d: dict, options: dict | None = None) -> dict:
    return {r.key: r for r in CD.design_breakdown(d, options or {}).rows}


def system_row(d: dict, uid: str, options: dict | None = None):
    return next(r for r in CD.design_breakdown(d, options or {}).rows if r.system_uid == uid)


def codes(d: dict, options: dict | None = None) -> set[str]:
    return {i.code for i in CD.validate_design(d, options or {}) if i.severity == "violation"}


def infos(d: dict, options: dict | None = None) -> set[str]:
    return {i.code for i in CD.validate_design(d, options or {}) if i.severity == "info"}


# ---- Golden ----------------------------------------------------------------------------------


def test_heavy_cruiser_is_294_points():
    b = CD.design_breakdown(heavy_cruiser(), {})
    assert (b.mass_used, b.points) == (86, 294)
    assert codes(heavy_cruiser()) == set()


def test_heavy_cruiser_line_items():
    r = rows(heavy_cruiser())
    assert (r["hull"].points, r["hull_integrity"].points) == (86, 52)
    assert (r["ftl"].mass, r["ftl"].points) == (9, 18)           # 8.6 rounds up
    assert (r["main_drive"].mass, r["main_drive"].points) == (17, 34)  # 17.2 rounds down
    assert (system_row(heavy_cruiser(), "s1").mass, system_row(heavy_cruiser(), "s1").points) == (4, 12)


def test_cd_p43_rounding_examples():
    d = design(tmf=64, ftl=True, thrust=4)
    assert (rows(d)["ftl"].mass, rows(d)["main_drive"].mass) == (6, 13)
    assert rows(design(tmf=64, thrust=6))["main_drive"].mass == 19


# ---- Hull, drives, FTL ------------------------------------------------------------------------


def test_damage_track_four_rows_extra_boxes_up_top():
    assert CD.damage_track(design(hull_boxes=26)) == [7, 7, 6, 6]
    assert CD.damage_track(design(hull_boxes=2)) == [1, 1, 0, 0]
    assert CD.threshold_numbers(design(hull_boxes=12)) == [6, 5, 4]


def test_advanced_hull_three_rows_and_triple_cost():
    d = design(tmf=60, hull_boxes=24, hull_advanced=True)
    assert CD.damage_track(d) == [8, 8, 8]
    assert CD.threshold_numbers(d) == [6, 5]
    assert rows(d)["hull_integrity"].points == 72


def test_advanced_hull_below_four_boxes_is_standard():
    d = design(tmf=20, hull_boxes=3, hull_advanced=True)
    assert CD.damage_track(d) == [1, 1, 1, 0]
    assert rows(d)["hull_integrity"].points == 6
    assert "advanced_hull_too_small" in infos(d)


def test_advanced_drive_costs_triple_and_turns_full_thrust():
    d = design(tmf=40, thrust=6, drive_advanced=True)
    assert (rows(d)["main_drive"].mass, rows(d)["main_drive"].points) == (12, 36)
    derived = CD.design_breakdown(d, {}).derived
    assert derived["turn_thrust"] == 6 and derived["advanced_drive"] is True
    assert CD.design_breakdown(design(tmf=40, thrust=6), {}).derived["turn_thrust"] == 3


def test_advanced_ftl_is_paid_only_with_the_fleet_option():
    d = design(tmf=40, ftl=True, ftl_advanced=True)
    assert rows(d)["ftl"].points == 8                       # CD p.33: standard cost by default
    assert rows(d, {"cd_advanced_ftl": True})["ftl"].points == 12


def test_streamlining_is_5_and_10_percent():
    assert (rows(design(tmf=50, streamlining="partial"))["streamlining"].mass,
            rows(design(tmf=50, streamlining="partial"))["streamlining"].points) == (3, 6)
    assert rows(design(tmf=50, streamlining="full"))["streamlining"].points == 10


def test_mass_limits():
    assert "odd_mass" in codes(design(tmf=21, hull_boxes=3))
    assert "odd_mass" not in codes(design(tmf=9, hull_boxes=1))
    assert "mass_over_300" in codes(design(tmf=302, hull_boxes=31))
    assert "hull_below_minimum" in codes(design(tmf=60, hull_boxes=5))


def test_unused_mass_is_info_not_violation():
    d = design(tmf=20, hull_boxes=4)
    assert "mass_under" in infos(d) and "mass_under" not in codes(d)
    assert "mass_over" in codes(design(tmf=20, hull_boxes=25))


def test_cpv_option_changes_the_hull_cost():
    # CD p.58: the Suffren (MASS 54) hull costs 29 instead of 54; Excalibur (140) 196.
    assert rows(design(tmf=54, hull_boxes=6), {"cd_cpv": True})["hull"].points == 29
    assert rows(design(tmf=140, hull_boxes=14), {"cd_cpv": True})["hull"].points == 196
    assert rows(design(tmf=6, hull_boxes=1), {"cd_cpv": True})["hull"].points == 1


# ---- Armour and screens ------------------------------------------------------------------------


def test_shell_armour_doubles_per_layer():
    d = design(tmf=60, hull_boxes=6, armour=7, armour_layers=[4, 2, 1])
    assert rows(d)["armour"].mass == 7
    assert rows(d)["armour"].points == 4 * 2 + 2 * 4 + 1 * 8
    assert CD.design_breakdown(d, {}).derived["shell_layers"] == [4, 2, 1]


@pytest.mark.parametrize("tmf,level,mass,points", [
    (60, 1, 3, 9), (86, 1, 4, 12), (60, 2, 6, 18), (140, 2, 14, 42),
])
def test_screens(tmf, level, mass, points):
    r = system_row(design(tmf=tmf, systems=[sys_("s", "screen", level=level)]), "s")
    assert (r.mass, r.points) == (mass, points)


@pytest.mark.parametrize("tmf,level,mass,points", [
    (40, 1, 4, 16), (60, 1, 5, 20), (40, 2, 8, 32), (100, 2, 15, 60),
])
def test_advanced_screens(tmf, level, mass, points):
    r = system_row(design(tmf=tmf, systems=[sys_("s", "advanced_screen", level=level)]), "s")
    assert (r.mass, r.points) == (mass, points)


def test_screens_cannot_mix_and_pds_cannot_mix_with_scatterguns():
    d = design(systems=[sys_("a", "screen", level=1), sys_("b", "advanced_screen", level=1)])
    assert "mixed_screens" in codes(d)
    d = design(systems=[sys_("a", "pds"), sys_("b", "scattergun")])
    assert "mixed_point_defence" in codes(d)
    assert system_row(design(systems=[sys_("b", "scattergun")]), "b").points == 4


# ---- Weapons ---------------------------------------------------------------------------------


@pytest.mark.parametrize("cls,arcs,mass", [
    (1, ["F", "FS", "AS", "A", "AP", "FP"], 1), (1, BROADSIDE, 1),
    (2, FRONT3, 2), (2, BROADSIDE, 3),
    (3, ["F"], 4), (3, FRONT3, 6), (3, BROADSIDE, 6),
    (4, FRONT3, 12), (4, BROADSIDE, 12),
])
def test_beam_mass(cls, arcs, mass):
    r = system_row(design(systems=[sys_("b", "beam", **{"class": cls, "arcs": arcs})]), "b")
    assert (r.mass, r.points) == (mass, 3 * mass)


def test_beam_arc_rules():
    assert "beam_arcs" in codes(design(systems=[sys_("b", "beam", **{"class": 2, "arcs": ["F", "FS"]})]))
    assert "beam_arcs" in codes(design(systems=[sys_("b", "beam", **{"class": 3, "arcs": ["F", "A"]})]))
    assert "beam_arcs" not in codes(design(systems=[sys_("b", "beam", **{"class": 3, "arcs": BROADSIDE})]))


@pytest.mark.parametrize("cls,arcs,mass", [
    (1, ["F"], 2), (1, FRONT3, 3), (1, BROADSIDE, 4), (1, ["F", "FS", "AS", "A", "AP", "FP"], 4),
    (2, ["F"], 9), (2, FRONT3, 15), (2, BROADSIDE, 15),
    (3, ["F"], 24), (3, FRONT3, 36), (4, ["F"], 72), (4, ["F", "FS"], 84),
])
def test_graser_mass(cls, arcs, mass):
    r = system_row(design(systems=[sys_("g", "graser", **{"class": cls, "arcs": arcs})]), "g")
    assert (r.mass, r.points) == (mass, 4 * mass)


@pytest.mark.parametrize("cls,arcs,mass", [
    (1, ["F"], 4), (1, FRONT3, 6), (1, BROADSIDE, 6), (2, ["F"], 8), (2, ["F", "FS"], 10),
    (2, BROADSIDE, 12), (3, ["F"], 16),
])
def test_torpedo_mass(cls, arcs, mass):
    r = system_row(design(systems=[sys_("t", "pulse_torpedo", **{"class": cls, "arcs": arcs})]), "t")
    assert (r.mass, r.points) == (mass, 3 * mass)


def test_torpedo_arc_limit():
    d = design(systems=[sys_("t", "pulse_torpedo", **{"class": 1, "arcs": ["FP", "F", "FS", "AS"]})])
    assert "torpedo_arcs" in codes(d)


def test_missile_launchers_fire_through_three_arcs_or_broadside():
    ok = design(systems=[sys_("r", "sm_rack", load="std", arcs=BROADSIDE)])
    bad = design(systems=[sys_("r", "sm_rack", load="std", arcs=["F"])])
    assert "missile_arcs" not in codes(ok) and "missile_arcs" in codes(bad)


@pytest.mark.parametrize("load,stages,mass,points", [
    ("std", 1, 2, 6), ("er", 1, 3, 9), ("std", 2, 4, 12), ("std", 3, 6, 24),
])
def test_heavy_missiles(load, stages, mass, points):
    r = system_row(design(systems=[sys_("h", "heavy_missile", load=load, stages=stages, arcs=FRONT3)]), "h")
    assert (r.mass, r.points) == (mass, points)


def test_multistage_rules():
    er = design(systems=[sys_("h", "heavy_missile", load="er", stages=2, arcs=FRONT3)])
    assert "multistage_er" in codes(er)
    rack = design(systems=[sys_("r", "sm_rack", load="std", stages=2, arcs=FRONT3)])
    assert (system_row(rack, "r").mass, system_row(rack, "r").points) == (6, 24)
    assert "option_off" in codes(rack, {"cd_multistage": False})


# ---- Optional and super systems ---------------------------------------------------------------


@pytest.mark.parametrize("stype,mass,points", [
    ("enhanced_sensors", 2, 8), ("superior_sensors", 4, 16), ("weasel_cruiser", 2, 8),
    ("weasel_capital", 4, 16), ("ecm", 4, 16), ("area_ecm", 6, 24), ("ortillery", 3, 9),
    ("minesweeper", 5, 15),
])
def test_optional_systems(stype, mass, points):
    r = system_row(design(systems=[sys_("x", stype)]), "x")
    assert (r.mass, r.points) == (mass, points)


def test_optional_systems_need_their_fleet_option():
    d = design(systems=[sys_("x", "ecm")])
    assert "option_off" not in codes(d)                    # the Design tab: a note only
    assert "option_needed" in infos(d)
    assert "option_off" in codes(d, {"cd_optional_systems": False})
    assert "option_off" not in codes(d, {"cd_optional_systems": True})
    assert CD.required_options(d, None) == {"cd_optional_systems"}


def test_super_weapons():
    d = design(tmf=60, hull_boxes=6, systems=[sys_("n", "nova_cannon", arcs=["F"])])
    assert (system_row(d, "n").mass, system_row(d, "n").points) == (20, 60)
    assert "capital_only" in codes(d)
    assert CD.required_options(d, None) == {"cd_super_weapons"}
    assert system_row(design(tmf=120, systems=[sys_("r", "reflex_field")]), "r").mass == 12
    assert system_row(design(tmf=40, systems=[sys_("r", "reflex_field")]), "r").points == 60
    assert system_row(design(tmf=40, systems=[sys_("c", "cloak")]), "c").points == 40


def test_tug_drive_tows_five_per_mass():
    # CD p.34: towing a MASS 108 ship needs 22 spare FTL MASS.
    r = system_row(design(tmf=60, systems=[sys_("t", "tug_drive", tow_mass=108)]), "t")
    assert (r.mass, r.points) == (22, 44)


# ---- Crew, holds, loadouts, type ----------------------------------------------------------------


def test_crew_factors_and_dots():
    d = design(tmf=90, hull_boxes=27)
    assert CD.crew_factors(d) == 5
    assert CD.cf_positions(d) == [6, 12, 18, 24, 27]       # CD p.32 example
    assert CD.crew_factors(design(tmf=90, hull_kind="merchant")) == 2


def test_holds_split_per_hull_row():
    d = design(tmf=80, hull_boxes=8, systems=[sys_("h", "hold", kind="cargo", mass=50)])
    assert CD.design_breakdown(d, {}).derived["holds"][0]["spaces"] == [13, 13, 12, 12]


def test_fighter_loadout_points():
    d = design(tmf=60, systems=[sys_("h", "hangar", bays=2)],
               default_loadout={"fighters": [{"hangar": "h", "type": "heavy"},
                                             {"hangar": "h", "type": "torpedo"}], "magazines": []})
    assert CD.loadout_points(d, None, {}) == 66
    assert system_row(d, "h").points == 54


def carrier(*fighters, craft=(), bays=1) -> dict:
    return design(tmf=60, hull_boxes=6, systems=[sys_("h", "hangar", bays=bays)],
                  default_loadout={"fighters": [{"hangar": "h", **f} for f in fighters],
                                   "magazines": [], "craft": [{"hangar": "h", "mass": m} for m in craft]})


@pytest.mark.parametrize("group,points", [
    ({"type": "attack"}, 24),
    ({"type": "attack", "extras": ["ftl"]}, 30),                         # CD p.47: +6 a group
    ({"type": "heavy", "extras": ["ftl", "kinetic"]}, 42),
    ({"type": "attack", "swing": ["standard", "interceptor"]}, 42),      # the CD p.30 example
    ({"type": "standard", "swing": ["attack", "interceptor"]}, 42),      # dearest type in full
    ({"type": "attack", "swing": ["standard", "interceptor"], "extras": ["ftl"]}, 48),
    ({"type": "torpedo", "swing": ["torpedo"]}, 36),                     # a repeat adds nothing
])
def test_fighter_extras_and_swing_role(group, points):
    d = carrier(group)
    assert CD.loadout_points(d, None, {}) == points
    assert not codes(d)


def test_kinetic_is_allowed_but_no_use_to_interceptors_and_torpedo_fighters():
    # CD p.30: "can be bought for all types of fighter, but has no benefit" for those two.
    assert "kinetic_no_benefit" in infos(carrier({"type": "interceptor", "extras": ["kinetic"]}))
    assert "kinetic_no_benefit" in infos(carrier({"type": "torpedo", "swing": ["interceptor"],
                                                  "extras": ["kinetic"]}))
    assert "kinetic_no_benefit" not in infos(carrier({"type": "torpedo", "swing": ["attack"],
                                                      "extras": ["kinetic"]}))


def test_unknown_fighter_extras_and_swing_types_are_violations():
    assert "unknown_fighter_type" in codes(carrier({"type": "attack", "swing": ["dragon"]}))
    assert "unknown_fighter_type" in codes(carrier({"type": "attack", "extras": ["cloaked"]}))


def test_light_vessels_in_hangars():
    # CD p.47: 2 points per MASS of craft, 1.5 hangar MASS per craft MASS (a 9-MASS bay holds 6).
    shuttles = carrier(craft=[6])
    assert CD.loadout_points(shuttles, None, {}) == 12
    assert not codes(shuttles)
    assert "hangar_overfull" in codes(carrier(craft=[7]))
    assert "hangar_overfull" in codes(carrier({"type": "standard"}, craft=[1]))
    mixed = carrier({"type": "standard"}, craft=[2, 4], bays=2)
    assert CD.loadout_points(mixed, None, {}) == 18 + 12
    assert not codes(mixed)
    assert "craft_without_hangar" in codes(design(default_loadout={
        "fighters": [], "magazines": [], "craft": [{"hangar": "nope", "mass": 2}]}))


def magazine_ship(capacity: int, salvos: list[str], stages: int = 1) -> dict:
    return design(tmf=40, hull_boxes=4, systems=[
        sys_("l", "sm_launcher", arcs=FRONT3), sys_("m", "sm_magazine", capacity=capacity, feeds=["l"])],
        default_loadout={"fighters": [], "magazines": [
            {"magazine": "m", "salvos": salvos, **({"stages": stages} if stages > 1 else {})}]})


def test_multistage_salvo_loads_in_magazines():
    # CD p.25: an extra stage adds 2 MASS and doubles the points. A standard load is 2 MASS of
    # magazine at 3 points (6); two stages are 4 MASS and 12 points, which the magazine space
    # already pays; three stages are 6 MASS and 24 points, 6 more than the space.
    two = magazine_ship(8, ["std", "std"], stages=2)
    assert not codes(two)
    assert CD.loadout_points(two, None, {}) == 0
    assert CD.loadout_points(magazine_ship(6, ["std"], stages=3), None, {}) == 6
    assert CD.loadout_points(magazine_ship(12, ["std", "std"], stages=3), None, {}) == 12
    assert "magazine_overloaded" in codes(magazine_ship(8, ["std"] * 3, stages=2))
    assert not codes(magazine_ship(8, ["std"] * 4))                # regular loads are unchanged
    assert CD.loadout_points(magazine_ship(8, ["std"] * 4), None, {}) == 0


def test_a_multistage_magazine_carries_standard_missiles_only():
    # CD p.25: only standard missiles may be multi-stage, and no mixing in one magazine.
    assert "multistage_er" in codes(magazine_ship(10, ["std", "er"], stages=2))
    assert "multistage_er" not in codes(magazine_ship(10, ["std", "std", "er"]))


def test_multistage_loads_need_the_fleet_option():
    d = magazine_ship(8, ["std", "std"], stages=2)
    assert CD.required_options(d, None) == {"cd_multistage"}
    assert CD.required_options(d, {"magazines": [{"magazine": "m", "salvos": ["std"]}]}) == set()
    assert "option_needed" in infos(d)
    assert "option_off" in codes(d, {"cd_multistage": False})
    assert CD.required_options(magazine_ship(8, ["std"] * 4), None) == set()


def test_type_suggestion():
    assert CD.suggest_type(design(tmf=72))[1] == "CA"            # CD p.42 calls it CA, not CH
    assert CD.suggest_type(design(tmf=200))[1] == "SDN"


def test_ruleset_identity():
    assert CD.short_label == "FTCD"
    assert CD.arcs == ("F", "FS", "AS", "A", "AP", "FP")
    assert [b.code for b in CD.books] == ["CD"]
    assert "cd_cpv" in CD.option_keys and "mt_systems" not in CD.option_keys


# ---- The Fleet Book ships under Cross Dimensions (CD pp.3, 21) ----------------------------------


def _catalog() -> list[dict]:
    import store

    return store.catalog_designs("ftcd")


def test_every_fleet_book_design_is_adopted():
    import store

    fb_ids = {d["id"].split(":", 1)[1] for d in store.catalog_designs("fb")}
    assert {d["id"].split(":", 1)[1] for d in _catalog()} == fb_ids
    assert all(d["id"].startswith("ftcd:") and d["ruleset"] == "ftcd" for d in _catalog())


@pytest.mark.parametrize("d", _catalog(), ids=lambda d: d["id"])
def test_adopted_designs_are_legal_under_cross_dimensions(d):
    opts = {o: True for o in CD.required_options(d, None)}
    assert [i.code for i in CD.validate_design(d, opts) if i.severity == "violation"] == []


def test_fleet_book_1_ships_cost_what_the_book_prints():
    # CD p.3: "All of the ships in fleet book 1 can be used unchanged with cross dimensions."
    fb1 = [d for d in _catalog() if d["source"]["book"] == "FB1"]
    assert len(fb1) == 65
    for d in fb1:
        assert CD.design_breakdown(d, {}).points == d["source"]["npv_book"], d["id"]
        assert "Cross Dimensions" not in d["notes"]


def _adopted(name: str) -> dict:
    return next(d for d in _catalog() if d["name"] == name)


def test_kravak_scatterguns_cost_4_points():
    # CD p.21; the Vo'Bok (FB2 p.14, NPV 238) has four, so it costs 4 less.
    vobok = _adopted("Vo'Bok")
    assert CD.design_breakdown(vobok, {}).points == 234
    assert vobok["source"]["npv_book"] == 0  # the printed NPV no longer holds
    assert "prints NPV 238" in vobok["notes"]


def test_the_si_tek_trades_a_k1_gun_for_an_adfc():
    # CD p.21: Kra'Vak scatterguns lose area defence, so the Si'Tek takes an ADFC instead of a K-1.
    sitek = _adopted("Si'Tek")
    types = [s["type"] for s in sitek["systems"]]
    assert types.count("adfc") == 1
    assert sum(1 for s in sitek["systems"] if s["type"] == "kgun" and s.get("class") == 1) == 1
    b = CD.design_breakdown(sitek, {})
    assert b.mass_used == sitek["tmf"] == 70
    assert b.points == 278 - 5  # the swap is points-neutral (2 MASS each at 4); 5 scatterguns
    assert "adfc" in {s.type for s in CD.system_types("kravak", {})}


def test_kravak_fighters_pay_for_kinetic_weapons():
    # CD p.21 and p.47: +6 a group on the FB2 Ra'San price of 18.
    assert CD.loadout_points(_adopted("Lo'Vok"), None, {}) == 24
    assert CD.loadout_points(_adopted("Ko'San"), None, {}) == 6 * 24


def test_phalon_and_savasku_designs_keep_their_fleet_book_cost():
    for d in _catalog():
        if d["race"] in ("phalon", "savasku"):
            assert CD.design_breakdown(d, {}).points == d["source"]["npv_book"], d["id"]


def test_cpv_reaches_alien_hulls():
    # CD p.58: the CPV hull cost is MASS squared / 100, for every hull.
    kotek = _adopted("Ko'Tek")
    plain = CD.design_breakdown(kotek, {}).points
    assert CD.design_breakdown(kotek, {"cd_cpv": True}).points == plain - 70 + 49


def test_alien_races_are_offered():
    assert [r.id for r in CD.races()] == ["human", "kravak", "savasku", "phalon"]
    assert CD.icon_set_for("kravak") == "fb_kravak" and CD.icon_set_for("human") == "ftcd"
    assert CD.fighter_types({}, "kravak") == ["standard", "heavy"]
    assert CD.required_options(_adopted("Lo'Vok"), None) == set()


def test_quick_reference_for_an_alien_fleet():
    keys = {e.key for e in CD.quickref({"kgun", "scattergun"}, {}, frozenset({"kravak"}))}
    assert {"cd_kravak", "kv_kgun", "kv_thrust", "scattergun"} <= keys
    assert "kv_scattergun" not in keys  # CD's scattergun rules replace FB2's (CD p.21)
    savasku = {e.key for e in CD.quickref({"stinger"}, {}, frozenset({"savasku"}))}
    assert {"cd_savasku", "sv_stinger", "sv_power"} <= savasku and "crew" not in savasku
    assert "cd_kravak" not in {e.key for e in CD.quickref(set(), {})}
