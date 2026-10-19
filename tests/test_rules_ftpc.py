"""FTPC ruleset: Full Thrust Project Continuum ship design (PC section 13, summary pp.118-124).

Golden test first: the PC pp.113-114 heavy cruiser, built line by line in the book, is 294
points. The other tests check one costing rule or validator each against the book's own numbers.
"""

from __future__ import annotations

import pytest

import fleet_rules
from rulesets import RULESETS
from rulesets.ftpc import data

PC = RULESETS["ftpc"]

SIX = ["F", "FS", "AS", "A", "AP", "FP"]
FRONT3 = ["FP", "F", "FS"]


def sys_(uid: str, stype: str, **params) -> dict:
    return {"uid": uid, "type": stype, **params}


def design(**fields) -> dict:
    base = {
        "id": "t", "ruleset": "ftpc", "race": "human", "name": "Test", "hull_kind": "warship",
        "tmf": 20, "hull_boxes": 4, "armour": 0, "armour_layers": [], "thrust": 0, "ftl": False,
        "streamlining": "none", "systems": [], "default_loadout": {"fighters": [], "magazines": []},
    }
    return {**base, **fields}


def heavy_cruiser() -> dict:
    """PC pp.113-114: MASS 86, average hull 26, FTL, thrust 4, 2 x beam-3 (3 arcs), beam-2
    (6 arcs), 2 x beam-1, 2 FireCons, SML forward with a 3-salvo magazine, level-1 screen, 2 PDS."""
    return design(
        tmf=86, hull_boxes=26, thrust=4, ftl=True,
        systems=[
            sys_("b1", "beam", **{"class": 3, "arcs": ["FP", "F", "AP"]}),
            sys_("b2", "beam", **{"class": 3, "arcs": ["F", "FS", "AS"]}),
            sys_("b3", "beam", **{"class": 2, "arcs": SIX}),
            sys_("b4", "beam", **{"class": 1, "arcs": SIX}),
            sys_("b5", "beam", **{"class": 1, "arcs": SIX}),
            sys_("f1", "fire_control"), sys_("f2", "fire_control"),
            sys_("l1", "sm_launcher", arcs=FRONT3),
            sys_("m1", "sm_magazine", capacity=6, feeds=["l1"]),
            sys_("s1", "screen", level=1),
            sys_("p1", "pds"), sys_("p2", "pds"),
        ],
        default_loadout={"fighters": [], "magazines": [{"magazine": "m1", "salvos": ["std"] * 3}]},
    )


def rows(d: dict, options: dict | None = None) -> dict:
    return {r.key: r for r in PC.design_breakdown(d, options or {}).rows}


def one(stype: str, tmf: int = 100, options: dict | None = None, **params):
    """The breakdown row of a single system on an otherwise empty ship."""
    d = design(tmf=tmf, hull_boxes=tmf // 10, systems=[sys_("x", stype, **params)])
    return next(r for r in PC.design_breakdown(d, options or {}).rows if r.system_uid == "x")


def mass_points(stype: str, tmf: int = 100, **params) -> tuple[int, int]:
    r = one(stype, tmf, **params)
    return r.mass, r.points


def codes(d: dict, options: dict | None = None) -> set[str]:
    return {i.code for i in PC.validate_design(d, options or {}) if i.severity == "violation"}


def infos(d: dict, options: dict | None = None) -> set[str]:
    return {i.code for i in PC.validate_design(d, options or {}) if i.severity == "info"}


# ---- Golden ----------------------------------------------------------------------------------


def test_heavy_cruiser_is_294_points():
    b = PC.design_breakdown(heavy_cruiser(), {})
    assert (b.mass_used, b.points) == (86, 294)
    assert codes(heavy_cruiser()) == set()


def test_heavy_cruiser_line_items():
    r = rows(heavy_cruiser())
    assert (r["hull"].points, r["hull_integrity"].points) == (86, 52)
    assert (r["ftl"].mass, r["ftl"].points) == (9, 18)
    assert (r["main_drive"].mass, r["main_drive"].points) == (17, 34)
    assert r["screen"].mass == 4                                  # 4.3 rounds down
    assert PC.damage_track(heavy_cruiser()) == [7, 7, 6, 6]


# ---- Hull, drives, streamlining (PC pp.107-109) -----------------------------------------------


def test_drives_round_half_up_never_to_zero():
    # p.107: MASS 64, FTL 6.4 -> 6, thrust-4 12.8 -> 13; MASS 4 still pays 1 for FTL.
    r = rows(design(tmf=64, hull_boxes=7, thrust=4, ftl=True))
    assert (r["ftl"].mass, r["main_drive"].mass) == (6, 13)
    assert rows(design(tmf=4, hull_boxes=1, ftl=True))["ftl"].mass == 1


@pytest.mark.parametrize("hull_rows, points", [(4, 48), (5, 36), (6, 24)])
def test_hull_rows_price_the_boxes(hull_rows, points):
    # p.108: x2 for four rows, x1.5 for five, x1 for six.
    d = design(tmf=80, hull_boxes=24, hull_rows=hull_rows)
    assert rows(d)["hull_integrity"].points == points
    assert len(PC.damage_track(d)) == hull_rows


def test_five_rows_round_half_points_up():
    assert rows(design(tmf=80, hull_boxes=23, hull_rows=5))["hull_integrity"].points == 35


def test_advanced_hull_is_three_rows_at_x3_and_needs_four_boxes():
    d = design(tmf=60, hull_boxes=24, hull_advanced=True, hull_rows=6)
    assert rows(d)["hull_integrity"].points == 72
    assert PC.damage_track(d) == [8, 8, 8]                       # p.108's strong hull, 8/8/8
    assert PC.threshold_numbers(d) == [6, 5]
    small = design(tmf=20, hull_boxes=3, hull_advanced=True)
    assert len(PC.damage_track(small)) == 4
    assert "advanced_hull_too_small" in infos(small)


def test_extra_rows_keep_checking_on_4_plus():
    assert PC.threshold_numbers(design(hull_rows=6, hull_boxes=12)) == [6, 5, 4, 4, 4]


def test_advanced_drive_and_ftl_cost_x3():
    r = rows(design(tmf=100, hull_boxes=10, thrust=4, ftl=True, drive_advanced=True,
                    ftl_advanced=True))
    assert (r["main_drive"].points, r["ftl"].points) == (60, 30)
    assert PC.design_breakdown(design(thrust=4, drive_advanced=True), {}).derived["turn_thrust"] == 4


def test_streamlining_is_5_or_10_percent_at_2_a_mass():
    # p.109: a MASS 50 ship's partial streamlining is 3 MASS, full 5.
    assert rows(design(tmf=50, hull_boxes=5, streamlining="partial"))["streamlining"].mass == 3
    full = rows(design(tmf=50, hull_boxes=5, streamlining="full"))["streamlining"]
    assert (full.mass, full.points) == (5, 10)


def test_crew_factors_and_their_stars():
    # p.86: MASS 90, 5 CF, 27 boxes as 7/7/7/6, stars in boxes 6, 12, 18, 24, 27.
    d = design(tmf=90, hull_boxes=27)
    assert PC.crew_factors(d) == 5
    assert PC.damage_track(d) == [7, 7, 7, 6]
    assert PC.cf_positions(d) == [6, 12, 18, 24, 27]
    assert PC.crew_factors(design(tmf=90, hull_kind="merchant")) == 2


def test_hull_minimum_is_10_percent():
    assert "hull_below_minimum" in codes(design(tmf=50, hull_boxes=4))


# ---- Armour, stealth hull ---------------------------------------------------------------------


def test_shell_armour_costs_2_times_the_layer():
    # p.57: inner 2 a box, first shell 4, second 6, third 8, fourth 10.
    d = design(tmf=60, hull_boxes=6, armour=10, armour_layers=[4, 3, 2, 1])
    assert rows(d)["armour"].points == 8 + 12 + 12 + 8
    assert "shell_layers_max" in codes(design(armour=6, armour_layers=[1] * 6))


def test_regenerative_armour_adds_2_a_box():
    assert rows(design(armour=4, armour_regen=True))["armour"].points == 16
    shell = design(armour=4, armour_layers=[2, 2], armour_regen=True)
    assert rows(shell)["armour"].points == 2 * 4 + 2 * 6       # p.58: 4 and 6 a box


def test_stealth_hull_costs_per_hull_and_armour_box():
    d = design(tmf=40, hull_boxes=8, armour=2, stealth_hull=2)
    assert (rows(d)["stealth_hull"].mass, rows(d)["stealth_hull"].points) == (0, 40)
    over = design(stealth_hull=2, systems=[sys_("s", "stealth_field", level=1)])
    assert "stealth_over_2" in codes(over)


# ---- Weapons (PC pp.36-55, 120-123) -----------------------------------------------------------


@pytest.mark.parametrize("cls, arcs, mass", [
    (1, SIX, 1), (2, FRONT3, 2), (2, SIX, 3), (2, ["FP", "AP"], 1),
    (3, ["F"], 4), (3, FRONT3, 6), (4, ["F"], 8), (4, ["F", "FS"], 10), (5, ["F"], 16),
])
def test_beam_mass(cls, arcs, mass):
    assert mass_points("beam", **{"class": cls, "arcs": arcs}) == (mass, 3 * mass)


@pytest.mark.parametrize("stype", ["emp", "transporter", "grav_gun"])
def test_beam_like_weapons_cost_as_beams(stype):
    assert mass_points(stype, **{"class": 3, "arcs": FRONT3}) == (6, 18)


@pytest.mark.parametrize("cls, arcs, mass", [
    (1, FRONT3, 1), (1, SIX, 2), (2, FRONT3, 4), (2, SIX, 6), (3, ["F"], 8), (4, ["F", "FS"], 20),
])
def test_plasma_and_grasers_are_double_a_beam(cls, arcs, mass):
    assert mass_points("plasma_cannon", **{"class": cls, "arcs": arcs}) == (mass, 3 * mass)
    assert mass_points("graser", **{"class": cls, "arcs": arcs}) == (mass, 3 * mass)


def test_phaser_costs_3_a_mass_plus_2_or_6_with_afc():
    # p.38: "a Phaser-2 (3 arc) would be mass 4 and cost 14 points, 24 points if the ship had AFC".
    assert mass_points("phaser", **{"class": 2, "arcs": FRONT3}) == (4, 14)
    d = design(tmf=100, hull_boxes=10, systems=[
        sys_("x", "phaser", **{"class": 2, "arcs": FRONT3}), sys_("a", "advanced_fire_control")])
    assert next(r for r in PC.design_breakdown(d, {}).rows if r.system_uid == "x").points == 24


@pytest.mark.parametrize("cls, arcs, mass", [
    (1, ["F"], 2), (1, FRONT3, 3), (1, SIX, 4), (2, ["F", "FS"], 12), (3, ["F"], 24),
])
def test_heavy_graser_mass_and_hig_points(cls, arcs, mass):
    assert mass_points("heavy_graser", **{"class": cls, "arcs": arcs}) == (mass, 3 * mass)
    hig = mass_points("heavy_graser", **{"class": cls, "arcs": arcs, "intensity": "high"})
    assert hig == (mass, 4 * mass)


def test_batteries_and_broadside_pairs():
    # p.40: 2/3/4 for one, three or six arcs; a broadside pair of gatlings is 5 MASS for two.
    assert mass_points("gatling", arcs=["F"]) == (2, 8)
    assert mass_points("meson", arcs=SIX) == (4, 16)
    assert mass_points("pulser", arcs=FRONT3) == (3, 15)
    d = design(tmf=100, hull_boxes=10, systems=[
        sys_("a", "gatling", arcs=["FP", "AP"]), sys_("b", "gatling", arcs=["FS", "AS"])])
    pair = [r for r in PC.design_breakdown(d, {}).rows if r.key == "gatling"]
    assert sum(r.mass for r in pair) == 5 and sum(r.points for r in pair) == 20


@pytest.mark.parametrize("cls, arcs, mass", [(1, ["F", "FS"], 2), (1, FRONT3, 3), (2, ["F"], 4),
                                             (3, ["F", "FS"], 12), (4, FRONT3, 32)])
def test_needle_beam_mass(cls, arcs, mass):
    assert mass_points("needle_beam", **{"class": cls, "arcs": arcs}) == (mass, 3 * mass)


@pytest.mark.parametrize("kind, arcs, mass, points", [
    ("standard", ["F"], 4, 12), ("standard", FRONT3, 6, 18), ("short", ["F"], 2, 6),
    ("short", FRONT3, 3, 9), ("long", ["F", "FS"], 10, 30), ("variable", ["F"], 8, 40),
])
def test_pulse_torpedoes(kind, arcs, mass, points):
    assert mass_points("pulse_torpedo", range=kind, arcs=arcs) == (mass, points)


def test_overloadable_torpedoes_cost_1_a_mass_more_but_not_short_range():
    opts = {"pc_overload_torpedoes": True}
    assert one("pulse_torpedo", options=opts, range="standard", arcs=["F"]).points == 16
    assert one("pulse_torpedo", options=opts, range="short", arcs=["F"]).points == 6


@pytest.mark.parametrize("cls, kind, arcs, mass", [
    (1, "standard", SIX, 2), (2, "standard", ["F"], 3), (2, "standard", ["F", "FS"], 4),
    (6, "standard", ["F"], 14), (2, "short", ["F", "FS"], 2), (5, "short", ["F"], 6),
    (1, "long", SIX, 4), (2, "long", ["F", "FS"], 8), (6, "long", ["F"], 28),
])
def test_kgun_mass(cls, kind, arcs, mass):
    assert mass_points("kgun", **{"class": cls, "range": kind, "arcs": arcs}) == (mass, 4 * mass)


def test_short_range_k1s_come_in_pairs_for_3_mass():
    d = design(tmf=50, hull_boxes=5, systems=[
        sys_("a", "kgun", **{"class": 1, "range": "short", "arcs": SIX}),
        sys_("b", "kgun", **{"class": 1, "range": "short", "arcs": SIX})])
    assert sum(r.mass for r in PC.design_breakdown(d, {}).rows if r.key == "kgun") == 3


def test_flak_is_2_points_a_gun_and_all_or_none():
    assert one("kgun", **{"class": 3, "arcs": ["F"], "flak": "yes"}).points == 22
    d = design(tmf=100, hull_boxes=10, systems=[
        sys_("a", "kgun", **{"class": 3, "arcs": ["F"], "flak": "yes"}),
        sys_("b", "kgun", **{"class": 2, "arcs": ["F"]})])
    assert "flak_all" in codes(d)


def test_kgun_arcs():
    def gun(cls):
        return design(systems=[sys_("a", "kgun", **{"class": cls, "arcs": ["F", "FS"]})])
    assert "too_many_arcs" in codes(gun(3))
    assert "too_many_arcs" not in codes(gun(2))


def test_torpedoes_take_three_arcs_at_most_but_need_not_be_adjacent():
    assert "too_many_arcs" in codes(design(systems=[sys_("a", "pulse_torpedo", arcs=SIX[:4])]))
    # p.45: "like multi-arc weapons, turret arcs do not have to be contiguous".
    assert codes(design(tmf=50, hull_boxes=5, systems=[sys_("a", "pulse_torpedo", arcs=["F", "A"])])) <= {
        "mass_over"}


@pytest.mark.parametrize("stype, params, mass, points", [
    ("mkp", {"arcs": ["F"]}, 1, 4),
    ("boarding_torpedo_launcher", {"arcs": FRONT3}, 2, 6),
    ("boarding_torpedoes", {"count": 4}, 4, 12),
    ("fusion_array", {"arcs": FRONT3}, 5, 15),
    ("plasma_bolt", {"class": 3, "arcs": FRONT3}, 15, 45),
    ("am_missile", {"arcs": FRONT3}, 2, 10),
    ("rocket_pod", {"arcs": ["F"]}, 1, 3),
    ("minelayer", {"mines": 4}, 6, 14),
    ("heavy_missile", {"arcs": FRONT3}, 2, 6),
    ("heavy_missile", {"arcs": FRONT3, "load": "er"}, 3, 9),
    ("heavy_missile", {"arcs": FRONT3, "stages": 2}, 4, 12),
    ("sm_rack", {"arcs": FRONT3}, 4, 12),
    ("nova_cannon", {}, 20, 60),
    ("wave_gun", {}, 12, 36),
])
def test_fixed_weapons(stype, params, mass, points):
    assert mass_points(stype, **params) == (mass, points)


def test_plasma_bolt_launchers_one_per_50_mass():
    pbl = sys_("a", "plasma_bolt", **{"class": 1, "arcs": ["F"]})
    assert "plasma_bolt_count" in codes(design(tmf=50, hull_boxes=5, systems=[pbl, dict(pbl, uid="b")]))
    assert "plasma_bolt_count" not in codes(design(tmf=51, hull_boxes=6, systems=[pbl, dict(pbl, uid="b")]))


def test_spinal_mounts():
    # p.122: 8/16/32 MASS; beam and plasma 4 a MASS, a PSP 5; 16 MASS per 50 MASS or part.
    assert mass_points("spinal_mount", kind="beam", size="medium") == (16, 64)
    assert mass_points("spinal_mount", kind="psp", size="small") == (8, 40)
    big = sys_("a", "spinal_mount", kind="plasma", size="large")
    assert "spinal_mass" in codes(design(tmf=50, hull_boxes=5, systems=[big]))
    assert "spinal_mass" not in codes(design(tmf=51, hull_boxes=6, systems=[big]))


# ---- Defences (PC pp.56-64, 119) --------------------------------------------------------------


def test_screens_have_no_minimum_mass():
    # p.56: 5% per level with no minimum; the FB/CD minimum of 3 is gone.
    assert mass_points("screen", tmf=30, level=1) == (2, 6)
    assert mass_points("screen", tmf=100, level=2) == (10, 30)
    assert mass_points("advanced_screen", tmf=100, level=1) == (8, 32)     # 7.5 rounds up


def test_area_screens_have_errata_minimums():
    assert mass_points("area_screen", tmf=50, level=1) == (15, 53)          # 20% = 10, min 15
    assert mass_points("area_screen", tmf=100, level=2) == (40, 140)
    assert mass_points("advanced_area_screen", tmf=50, level=1) == (20, 70)  # 30% = 15, min 20


@pytest.mark.parametrize("stype, params, mass, points", [
    ("pds", {}, 1, 3), ("ads", {"arcs": FRONT3}, 2, 6), ("ads", {"arcs": SIX}, 3, 9),
    ("adfc", {}, 2, 8), ("aadfc", {}, 2, 10), ("scattergun", {}, 1, 5), ("grapeshot", {}, 1, 4),
    ("amsc", {}, 1, 5), ("ecm", {"level": 2}, 2, 6), ("area_ecm", {"level": 2}, 4, 12),
    ("stealth_field", {"level": 2}, 10, 60), ("holofield", {}, 10, 50),
    ("reflex_field", {}, 10, 60), ("cloak", {}, 10, 100),
    ("cloaking_device", {}, 1, 50), ("cloaking_field", {}, 1, 100),
])
def test_defences(stype, params, mass, points):
    assert mass_points(stype, tmf=100, **params) == (mass, points)


def test_adfc_may_take_no_mass_on_ships_over_20():
    assert (one("adfc", tmf=40, options={"pc_adfc_no_mass": True}).mass,
            one("adfc", tmf=40, options={"pc_adfc_no_mass": True}).points) == (0, 8)
    assert one("adfc", tmf=20, options={"pc_adfc_no_mass": True}).mass == 2


def test_mixed_screens():
    assert "mixed_screens" in codes(design(systems=[sys_("a", "screen"), sys_("b", "advanced_screen")]))


# ---- Hangars, tugs, crew, the rest (PC pp.89-113) ---------------------------------------------


def test_hangar_bays_and_launch_tubes():
    assert mass_points("hangar_bay") == (6, 18)
    assert mass_points("launch_tube") == (3, 9)
    assert mass_points("launch_tube", catapult="yes") == (3, 10)
    assert mass_points("hangar") == (9, 27)                        # the combined bay, p.110
    assert one("hangar_bay", options={"pc_hangar_criticals": True}).points == 12


def test_hangar_bays_need_a_launch_tube():
    bays = [sys_("h", "hangar_bay")]
    assert "bays_without_tubes" in codes(design(systems=bays))
    assert "bays_without_tubes" not in codes(design(systems=bays + [sys_("t", "launch_tube")]))


def test_catapults_are_all_or_none_and_optional():
    d = design(tmf=60, hull_boxes=6, systems=[
        sys_("a", "launch_tube", catapult="yes"), sys_("b", "launch_tube")])
    assert "catapult_all" in codes(d)
    assert "option_needed" in infos(d)
    assert "option_off" in codes(d, {"pc_optional_systems": False})


def test_fighter_wings_and_modifications():
    groups = [{"hangar": "h", "type": "attack", "extras": ["ftl", "heavy"]},
              {"hangar": "h2", "type": "fast", "extras": ["fast"]}]
    d = design(systems=[sys_("h", "hangar_bay"), sys_("h2", "hangar_bay"), sys_("t", "launch_tube")],
               default_loadout={"fighters": groups, "magazines": []})
    # p.123: attack 24 + FTL 6 + heavy 18; a fast wing is 24, its own "fast" adds nothing.
    assert PC.loadout_points(d, None, {}) == 48 + 24
    assert set(PC.fighter_types({})) == set(data.FIGHTER_POINTS)


def test_tug_and_tender():
    # p.89: towing MASS 108 takes 22 more FTL MASS; a tender bay is 1.5 a MASS carried.
    assert mass_points("tug_drive", tow_mass=108) == (22, 44)
    assert mass_points("tender_bay", capacity=20) == (30, 90)
    assert mass_points("boat_bay", mass=4) == (6, 0)


def test_extra_crew_up_to_the_crew_factor_then_berthing():
    # Errata: up to the crew factor in any mix; more need troop (3) or passenger (4) berthing.
    crew = [sys_("m", "marines", count=3), sys_("d", "dcp", count=2)]
    d = design(tmf=100, hull_boxes=10, systems=crew)                   # CF 5
    assert rows(d)["marines"].points == 15 and "crew_over" not in codes(d)
    more = design(tmf=100, hull_boxes=10, systems=[*crew, sys_("x", "marines", count=3)])
    assert "crew_over" in codes(more)
    berthed = design(tmf=100, hull_boxes=10,
                     systems=[*crew, sys_("x", "marines", count=3), sys_("b", "troop_berthing", mass=1)])
    assert "crew_over" not in codes(berthed)


def test_shipyards_only_on_starbases():
    assert mass_points("shipyard", mass=50) == (50, 100)
    assert "starbase_only" in codes(design(systems=[sys_("y", "shipyard", mass=5)]))


def test_flawed_design_is_20_percent_off_and_not_on_small_ships():
    base = design(tmf=100, hull_boxes=10)
    full = PC.design_breakdown(base, {}).points
    flawed = dict(base, systems=[sys_("f", "flawed_design")])
    assert PC.design_breakdown(flawed, {}).points == full - (full + 2) // 5
    assert "flawed_not_allowed" in codes(design(tmf=50, hull_boxes=5, systems=[sys_("f", "flawed_design")]))


def test_cpv_hull():
    assert rows(design(tmf=140, hull_boxes=14), {"cd_cpv": True})["hull"].points == 196


def test_every_system_costs_and_validates_with_its_defaults():
    import store

    for definition in PC.system_types("human", {}):
        d = store.normalize_design(design(tmf=300, hull_boxes=30, hull_kind="starbase"))
        store.add_system(d, definition.type)
        b = PC.design_breakdown(d, {})
        assert b.rows[-1].label != "Unknown system", definition.type
        assert "unknown_system" not in codes(d), definition.type


# ---- The ruleset ------------------------------------------------------------------------------


def test_fb2_races_cost_as_in_fb2():
    fb = RULESETS["fb"]
    import store

    for d in store.catalog_designs("fb"):
        if d["race"] != "human":
            assert PC.design_breakdown(d, {}).points == fb.design_breakdown(d, {}).points, d["id"]


def test_the_fleet_book_catalog_is_adopted():
    import store

    adopted = store.catalog_designs("ftpc")
    assert len(adopted) == len(store.catalog_designs("fb"))
    changed = {d["id"] for d in adopted if not d["source"].get("npv_book")}
    # The Tibet's level-1 screen is 3 MASS under the FB minimum and 2 under PC's 5% (PC p.56);
    # the Do'San is the FB2 misprint in data/errata.json.
    assert changed == {"ftpc:fb1:esu-tibet", "ftpc:fb2:kv-do-san"}
    for d in adopted:
        assert codes(d, {k: True for k in PC.required_options(d, None)}) == set(), d["id"]


def test_fleet_rules_are_the_cross_dimensions_ones():
    from test_fleet_rules import fleet, ship

    rider = design(tmf=30, hull_boxes=3, ftl=False)
    f = fleet(ruleset="ftpc", ships=[ship(design_id="r")], points_limit=0)
    codes_ = {i.code for i in fleet_rules.fleet_report(f, {"r": rider}).fleet_issues}
    assert codes_ == {"riders_without_mothership"}
    assert PC.dummy_bogey_points == 20
