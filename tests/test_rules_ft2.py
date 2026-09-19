"""FT2 ruleset (FT core + More Thrust toggles), human tech. PLAN 6.3.

Golden tests first: FT p.31 Super Heavy Cruiser (267; the table's 276 is a misprint, see
data/errata.json), FT p.25 non-FTL System Defence Ship (95), FT p.15 Bulk Tanker (502) and Heavy
Freighter (306). Costs verified against the page images (the FT text layer is OCR).
"""

from __future__ import annotations

import json

import pytest
from conftest import ROOT

from rulesets import get_ruleset

FT2 = get_ruleset("ft2")
NO_MT: dict = {}
ALL_MT = {"mt_systems": True, "mt_superships": True, "mt_fighters": True}
PFS = ["P", "F", "S"]


def design(**kw) -> dict:
    d = {
        "schema_version": 1,
        "id": "t",
        "ruleset": "ft2",
        "race": "human",
        "faction": None,
        "name": "Test",
        "hull_kind": "warship",
        "tmf": 36,
        "hull_boxes": 0,
        "armour": 0,
        "thrust": 4,
        "ftl": True,
        "streamlining": "none",
        "systems": [],
        "default_loadout": {"fighters": [], "magazines": []},
        "source": {"kind": "custom"},
    }
    d.update(kw)
    return d


def sys_(uid, type_, **kw):
    return {"uid": uid, "type": type_, **kw}


def beam(uid, cls, arcs=PFS):
    return sys_(uid, "beam", arcs=list(arcs), **{"class": cls})


def fcs(n):
    return [sys_(f"fc{i}", "fire_control") for i in range(n)]


SUPER_HEAVY_CRUISER = design(
    tmf=36,
    thrust=4,
    ftl=True,
    systems=[
        sys_("sc", "screen", level=1),
        sys_("p1", "pdaf"),
        sys_("p2", "pdaf"),
        sys_("p3", "pdaf"),
        beam("a1", "A"),
        beam("a2", "A"),
        beam("b1", "B"),
        beam("b2", "B"),
        beam("b3", "B"),
        *fcs(2),
    ],
)

SYSTEM_DEFENCE_SHIP = design(
    tmf=14,
    thrust=6,
    ftl=False,
    systems=[
        beam("a", "A"),
        beam("b1", "B"),
        beam("b2", "B"),
        beam("b3", "B"),
        sys_("p1", "pdaf"),
        sys_("p2", "pdaf"),
        *fcs(1),
    ],
)

BULK_TANKER = design(
    hull_kind="merchant",
    tmf=100,
    thrust=2,
    ftl=True,
    systems=[
        beam("c1", "C"),
        beam("c2", "C"),
        beam("c3", "C"),
        *[sys_(f"p{i}", "pdaf") for i in range(4)],
        sys_("sc", "screen", level=1),
        *fcs(1),
    ],
)

HEAVY_FREIGHTER = design(
    hull_kind="merchant",
    tmf=60,
    thrust=2,
    ftl=True,
    systems=[beam("c1", "C"), sys_("p1", "pdaf"), sys_("p2", "pdaf"), sys_("sc", "screen", level=1), *fcs(1)],
)


def bd(d, opts=NO_MT):
    return FT2.design_breakdown(d, opts)


def codes(d, severity="violation", opts=NO_MT):
    return {i.code for i in FT2.validate_design(d, opts) if i.severity == severity}


def row(d, uid, opts=NO_MT):
    return next(r for r in bd(d, opts).rows if r.system_uid == uid)


def fixed(d, key, opts=NO_MT):
    return next(r for r in bd(d, opts).rows if r.key == key and r.system_uid is None)


# ---- Golden tests ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "d,points,capacity",
    [
        (SUPER_HEAVY_CRUISER, 267, 18),
        (SYSTEM_DEFENCE_SHIP, 95, 11),
        (BULK_TANKER, 502, 10),
        (HEAVY_FREIGHTER, 306, 6),
    ],
    ids=["super-heavy-cruiser-ft-p31", "sds-ft-p25", "bulk-tanker-ft-p15", "heavy-freighter-ft-p15"],
)
def test_golden_designs(d, points, capacity):
    b = bd(d)
    assert b.points == points
    assert b.derived["mass_limit"] == capacity
    assert b.mass_used == capacity
    assert codes(d) == set()


def test_super_heavy_cruiser_line_items_match_ft_p31():
    d = SUPER_HEAVY_CRUISER
    assert (fixed(d, "hull").points, fixed(d, "ftl").points, fixed(d, "main_drive").points) == (72, 36, 72)
    assert fixed(d, "hull").mass == 0 and fixed(d, "main_drive").mass == 0
    assert (row(d, "a1").mass, row(d, "a1").points) == (3, 13)
    assert (row(d, "b1").mass, row(d, "b1").points) == (2, 9)
    assert (row(d, "sc").mass, row(d, "sc").points) == (3, 25)
    assert bd(d).derived["damage_points"] == 18


def test_super_heavy_cruiser_misprint_is_in_errata():
    errata = json.loads((ROOT / "data" / "errata.json").read_text(encoding="utf-8"))
    entry = next(e for e in errata if e["id"] == "ft2:ft:super-heavy-cruiser-example")
    assert (entry["book_value"], entry["rules_value"]) == (276, 267)
    assert entry["reason"]


# ---- Hull, class, drives --------------------------------------------------------------------


@pytest.mark.parametrize(
    "tmf,cls",
    [(18, "escort"), (19, "cruiser"), (36, "cruiser"), (37, "capital"), (100, "capital"), (101, "supership")],
)
def test_classification(tmf, cls):
    assert bd(design(tmf=tmf), ALL_MT).derived["class"] == cls


def test_merchant_classification():
    assert bd(design(hull_kind="merchant", tmf=20)).derived["class"] == "merchant"


def test_hull_cost():
    assert fixed(design(tmf=20), "hull").points == 40
    assert fixed(design(tmf=20, hull_kind="merchant"), "hull").points == 30
    # Odd merchant MASS: 1.5 x 25 = 37.5, rounded up like damage points (owner decision).
    assert fixed(design(tmf=25, hull_kind="merchant"), "hull").points == 38


def test_ftl_costs_mass_and_no_ftl_costs_nothing():
    assert fixed(design(tmf=12), "ftl").points == 12
    assert not [r for r in bd(design(ftl=False)).rows if r.key == "ftl"]


@pytest.mark.parametrize(
    "tmf,thrust,kind,points",
    [
        (12, 6, "warship", 18),  # FT p.30 examples
        (12, 4, "warship", 12),
        (12, 8, "warship", 24),
        (48, 4, "warship", 192),
        (48, 2, "warship", 96),
        (36, 4, "warship", 72),
        (60, 2, "merchant", 120),
        (5, 2, "warship", 3),  # 2.5 rounds up
        (150, 2, "warship", 600),  # MT p.22 supership: 2 x MASS per thrust
    ],
)
def test_drive_cost(tmf, thrust, kind, points):
    assert fixed(design(tmf=tmf, thrust=thrust, hull_kind=kind), "main_drive", ALL_MT).points == points


def test_max_thrust_is_8():
    assert "thrust_over_max" in codes(design(thrust=9))
    assert "thrust_over_max" not in codes(design(thrust=8))


@pytest.mark.parametrize(
    "tmf,kind,ftl,capacity",
    [
        (12, "warship", True, 6),
        (25, "warship", True, 13),
        (14, "warship", False, 11),
        (60, "merchant", True, 6),
        (8, "merchant", True, 1),
        (100, "merchant", False, 10),
    ],
)
def test_system_capacity(tmf, kind, ftl, capacity):
    assert bd(design(tmf=tmf, hull_kind=kind, ftl=ftl)).derived["mass_limit"] == capacity


def test_over_capacity_is_a_violation_under_is_not():
    over = design(tmf=12, systems=[beam("a", "A"), beam("b", "A"), sys_("p", "pdaf"), *fcs(1)])
    assert "mass_over" in codes(over)
    assert "mass_over" not in codes(design(tmf=12, systems=[sys_("p", "pdaf"), *fcs(1)]))


@pytest.mark.parametrize(
    "tmf,kind,dp", [(36, "warship", 18), (25, "warship", 13), (100, "merchant", 25), (50, "merchant", 13)]
)
def test_damage_points_round_up(tmf, kind, dp):
    assert bd(design(tmf=tmf, hull_kind=kind)).derived["damage_points"] == dp


@pytest.mark.parametrize(
    "tmf,kind,rows",
    [
        (14, "warship", [3, 4]),  # FT p.12: 7 DP, extras on the LOWER rows
        (36, "warship", [6, 6, 6]),
        (40, "warship", [5, 5, 5, 5]),
        (98, "warship", [12, 12, 12, 13]),
        (100, "merchant", [6, 6, 6, 7]),
        (150, "warship", [15, 15, 15, 15, 15]),  # MT p.22: 5 rows for 101-150
        (151, "warship", [12, 12, 13, 13, 13, 13]),
    ],
)
def test_damage_track(tmf, kind, rows):
    assert FT2.damage_track(design(tmf=tmf, hull_kind=kind)) == rows


@pytest.mark.parametrize("tmf,expected", [(14, [6]), (36, [6, 5]), (60, [6, 5, 4]), (160, [6, 5, 4, 4, 4])])
def test_thresholds(tmf, expected):
    assert FT2.threshold_numbers(design(tmf=tmf)) == expected


def test_no_crew_factors_in_ft2():
    assert FT2.crew_factors(SUPER_HEAVY_CRUISER) == 0 and FT2.cf_positions(SUPER_HEAVY_CRUISER) == []


@pytest.mark.parametrize("thrust,turn", [(4, 2), (5, 3), (1, 1), (0, 0)])
def test_turn_thrust_rounds_up(thrust, turn):
    # FT p.5: an odd thrust's course-change share rounds UP.
    assert bd(design(thrust=thrust)).derived["turn_thrust"] == turn


# ---- Systems --------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "cls,arcs,mass,points",
    [
        ("A", ["F"], 3, 7),
        ("A", PFS, 3, 13),
        ("B", ["F", "S"], 2, 7),
        ("B", PFS, 2, 9),
        ("C", PFS, 1, 5),
        ("C", ["F"], 1, 3),
    ],
)
def test_beam_costs(cls, arcs, mass, points):
    d = design(systems=[beam("x", cls, arcs)])
    assert (row(d, "x").mass, row(d, "x").points) == (mass, points)


@pytest.mark.parametrize(
    "system,mass,points",
    [
        ({"type": "pdaf"}, 1, 3),
        ({"type": "adaf"}, 3, 10),
        ({"type": "screen", "level": 2}, 6, 50),
        ({"type": "screen", "level": 3}, 9, 75),
        ({"type": "fighter_group"}, 6, 20),
        ({"type": "needle_beam", "arcs": ["F"]}, 2, 6),
        ({"type": "pulse_torpedo", "arcs": ["F"]}, 5, 15),
        ({"type": "nova_cannon", "arcs": ["F"]}, 16, 50),
        ({"type": "submunition", "arcs": ["F"]}, 1, 3),
        ({"type": "minelayer"}, 3, 10),
        ({"type": "minesweeper"}, 5, 20),
    ],
)
def test_fixed_systems(system, mass, points):
    d = design(tmf=60, systems=[{"uid": "x", **system}])
    assert (row(d, "x").mass, row(d, "x").points) == (mass, points)


@pytest.mark.parametrize("tmf,standard", [(18, 1), (36, 2), (60, 3), (150, 4), (200, 5), (40, 1)])
def test_standard_fire_controls_are_free_extras_cost_3_mass_10_points(tmf, standard):
    kind = "merchant" if tmf == 40 else "warship"
    d = design(tmf=tmf, hull_kind=kind, systems=fcs(standard + 1))
    rows = [row(d, f"fc{i}", ALL_MT) for i in range(standard + 1)]
    assert [(r.mass, r.points) for r in rows] == [(0, 0)] * standard + [(3, 10)]


def test_tug_ftl_costs_three_times_mass():
    d = design(hull_kind="merchant", tmf=50, systems=[sys_("t", "tug_drive"), *fcs(1)])
    assert fixed(d, "ftl").points + row(d, "t").points == 150
    assert row(d, "t").mass == 0
    assert "tug_not_merchant" in codes(design(systems=[sys_("t", "tug_drive")]))
    assert "tug_without_ftl" in codes(
        design(hull_kind="merchant", tmf=50, ftl=False, systems=[sys_("t", "tug_drive")])
    )


# ---- More Thrust ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "system,tmf,mass,points",
    [
        ({"type": "mt_missile"}, 60, 2, 6),
        ({"type": "aa_battery", "arcs": ["F"]}, 60, 5, 15),
        ({"type": "wave_gun", "arcs": ["F"]}, 60, 10, 30),
        ({"type": "ortillery"}, 60, 3, 10),
        ({"type": "reflex_field"}, 60, 6, 40),
        ({"type": "cloak"}, 60, 6, 120),
        ({"type": "cloak"}, 36, 4, 72),
    ],
)
def test_mt_systems(system, tmf, mass, points):
    d = design(tmf=tmf, systems=[{"uid": "x", **system}])
    assert (row(d, "x", ALL_MT).mass, row(d, "x", ALL_MT).points) == (mass, points)


def test_mt_systems_offered_only_with_toggle():
    base = {s.type for s in FT2.system_types("human", NO_MT)}
    with_mt = {s.type for s in FT2.system_types("human", {"mt_systems": True})}
    mt = {"mt_missile", "aa_battery", "wave_gun", "ortillery", "reflex_field", "cloak"}
    assert not (base & mt)
    assert mt <= with_mt
    assert base >= {
        "beam",
        "pdaf",
        "adaf",
        "screen",
        "fighter_group",
        "needle_beam",
        "pulse_torpedo",
        "nova_cannon",
        "submunition",
        "minelayer",
        "minesweeper",
        "fire_control",
        "tug_drive",
    }


@pytest.mark.parametrize(
    "ftype,surcharge",
    [
        ("standard", 0),
        ("interceptor", 0),
        ("fast", 12),
        ("heavy", 12),
        ("attack", 6),
        ("long_range", 12),
        ("torpedo", 18),
    ],
)
def test_mt_fighter_surcharges(ftype, surcharge):
    d = design(tmf=60, systems=[sys_("g", "fighter_group")])
    assert (
        FT2.loadout_points(d, {"fighters": [{"hangar": "g", "type": ftype}], "magazines": []}, ALL_MT)
        == surcharge
    )


def test_required_options():
    assert FT2.required_options(SUPER_HEAVY_CRUISER, None) == set()
    assert FT2.required_options(design(systems=[sys_("w", "wave_gun", arcs=["F"])]), None) == {"mt_systems"}
    assert FT2.required_options(design(tmf=120), None) == {"mt_superships"}
    d = design(tmf=60, systems=[sys_("g", "fighter_group")])
    assert FT2.required_options(d, {"fighters": [{"hangar": "g", "type": "heavy"}], "magazines": []}) == {
        "mt_fighters"
    }
    assert (
        FT2.required_options(d, {"fighters": [{"hangar": "g", "type": "standard"}], "magazines": []}) == set()
    )


# ---- Validators -----------------------------------------------------------------------------


def test_no_offensive_fire_through_aft():
    assert "aft_arc" in codes(design(systems=[beam("b", "B", ["P", "A", "S"])]))
    assert "aft_arc" in codes(design(systems=[sys_("n", "needle_beam", arcs=["A"])]))


def test_ft2_arcs_only():
    assert "bad_arcs" in codes(design(systems=[beam("b", "B", ["FP"])]))
    assert "bad_arcs" in codes(design(systems=[beam("b", "B", [])]))


def test_single_arc_weapons():
    assert "single_arc" in codes(design(systems=[sys_("t", "pulse_torpedo", arcs=["F", "P"])]))


def test_capital_only_systems():
    assert "capital_only" in codes(design(tmf=36, systems=[sys_("n", "nova_cannon", arcs=["F"])]))
    assert "capital_only" not in codes(design(tmf=60, systems=[sys_("n", "nova_cannon", arcs=["F"])]))
    assert "capital_only" in codes(design(tmf=36, systems=[sys_("g", "fighter_group")]))
    assert "capital_only" in codes(design(tmf=36, systems=[sys_("a", "aa_battery", arcs=["F"])]), opts=ALL_MT)


def test_nova_and_wave_gun_fire_forward_only():
    assert "fore_only" in codes(design(tmf=60, systems=[sys_("n", "nova_cannon", arcs=["P"])]))


def test_merchant_system_limits():
    assert "merchant_system" in codes(design(hull_kind="merchant", tmf=60, systems=[beam("b", "B")]))
    assert "merchant_system" in codes(
        design(hull_kind="merchant", tmf=60, systems=[sys_("s", "screen", level=2)])
    )
    assert "merchant_system" not in codes(HEAVY_FREIGHTER)


def test_hull_mass_limits():
    assert "mass_over_100" in codes(design(tmf=120))
    assert "mass_over_100" not in codes(design(tmf=120), opts={"mt_superships": True})
    assert "bad_tmf" in codes(design(hull_kind="merchant", tmf=1))


def test_screen_levels_1_to_3():
    assert "screen_level" in codes(design(tmf=60, systems=[sys_("s", "screen", level=4)]))


def test_fb_only_fields_are_violations():
    assert "no_armour_in_ft2" in codes(design(armour=2))
    assert "no_streamlining_in_ft2" in codes(design(streamlining="partial"))


def test_fighter_loadout_checks():
    d = design(
        tmf=60,
        systems=[sys_("g", "fighter_group")],
        default_loadout={"fighters": [{"hangar": "nope", "type": "standard"}], "magazines": []},
    )
    assert "fighters_without_hangar" in codes(d)
    d["default_loadout"]["fighters"] = [{"hangar": "g", "type": "ninja"}]
    assert "unknown_fighter_type" in codes(d)


def test_infos():
    assert {"no_ftl"} <= codes(design(ftl=False), "info")


# ---- Derived and interface ------------------------------------------------------------------


def test_standard_or_special_hull():
    assert bd(design(tmf=32)).derived["hull_type"] == "standard"
    assert bd(design(tmf=36)).derived["hull_type"] == "special"


@pytest.mark.parametrize(
    "d,expected",
    [
        (design(tmf=14), ("Destroyer", "DD")),
        (design(tmf=36), ("Heavy Cruiser", "CH")),
        (design(tmf=98, systems=[sys_(f"g{i}", "fighter_group") for i in range(6)]), ("Fleet Carrier", "CV")),
        (design(tmf=60, hull_kind="merchant"), ("Heavy Freighter", "M")),
    ],
)
def test_suggest_type(d, expected):
    assert FT2.suggest_type(d) == expected


def test_books_and_badge():
    assert FT2.short_label == "FT2"
    offsets = {b.code: b.page_offset for b in FT2.books}
    assert offsets == {"FT": 1, "MT": 0}


def test_mt_content_needs_its_toggle():
    wave = design(tmf=60, systems=[sys_("w", "wave_gun", arcs=["F"])])
    assert "mt_toggle_off" in codes(wave)
    assert "mt_toggle_off" not in codes(wave, opts={"mt_systems": True})
    fighters = design(
        tmf=60,
        systems=[sys_("g", "fighter_group")],
        default_loadout={"fighters": [{"hangar": "g", "type": "fast"}], "magazines": []},
    )
    assert "mt_toggle_off" in codes(fighters)
    assert "mt_toggle_off" not in codes(fighters, opts={"mt_fighters": True})
