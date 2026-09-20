"""FB ruleset (Fleet Book 1 + FB2 amendments), human tech. PLAN 6.2.

Golden tests first (FB1 pp.10-11 Heavy Cruiser, FB1 p.16 Furious and Vandenburg, FB1 p.5 damage
track, FB1 p.8 crew-factor dots), then one test per costing rule and per validator.
"""

from __future__ import annotations

import copy

import pytest

from rulesets import RULESETS, get_ruleset

FB = get_ruleset("fb")
OPTS: dict = {}

ALL = ["F", "FS", "AS", "A", "AP", "FP"]


def design(**kw) -> dict:
    d = {
        "schema_version": 1,
        "id": "t",
        "ruleset": "fb",
        "race": "human",
        "faction": None,
        "name": "Test",
        "type_label": "",
        "type_code": "",
        "hull_kind": "warship",
        "tmf": 50,
        "hull_boxes": 15,
        "armour": 0,
        "thrust": 4,
        "ftl": True,
        "streamlining": "none",
        "systems": [],
        "default_loadout": {"fighters": [], "magazines": []},
        "allow_rule_breaking": False,
        "layout_hints": {},
        "source": {"kind": "custom"},
        "notes": "",
    }
    d.update(kw)
    return d


def sys_(uid, type_, **kw):
    return {"uid": uid, "type": type_, **kw}


HEAVY_CRUISER = design(
    tmf=85,
    hull_boxes=26,
    thrust=4,
    ftl=True,
    systems=[
        sys_("b1", "beam", **{"class": 3, "arcs": ["F", "FP"]}),
        sys_("b2", "beam", **{"class": 3, "arcs": ["F", "FS"]}),
        sys_("b3", "beam", **{"class": 2, "arcs": ALL}),
        sys_("b4", "beam", **{"class": 1, "arcs": ALL}),
        sys_("b5", "beam", **{"class": 1, "arcs": ALL}),
        sys_("f1", "fire_control"),
        sys_("f2", "fire_control"),
        sys_("l1", "sm_launcher", arcs=["FP", "F", "FS"]),
        sys_("m1", "sm_magazine", capacity=6, feeds=["l1"]),
        sys_("sc", "screen", level=1),
        sys_("p1", "pds"),
        sys_("p2", "pds"),
        sys_("p3", "pds"),
    ],
    default_loadout={"fighters": [], "magazines": [{"magazine": "m1", "salvos": ["std", "std", "std"]}]},
)

FURIOUS = design(
    name="Furious",
    tmf=64,
    hull_boxes=19,
    armour=3,
    thrust=4,
    ftl=True,
    systems=[
        sys_("s1", "beam", **{"class": 3, "arcs": ["F"]}),
        sys_("s2", "beam", **{"class": 2, "arcs": ["FP", "F", "FS"]}),
        sys_("s3", "beam", **{"class": 2, "arcs": ["FP", "F", "FS"]}),
        sys_("s4", "beam", **{"class": 1, "arcs": ALL}),
        sys_("s5", "pulse_torpedo", arcs=["F"]),
        sys_("s6", "pds"),
        sys_("s7", "pds"),
        sys_("s8", "pds"),
        sys_("s9", "fire_control"),
        sys_("s10", "fire_control"),
        sys_("s11", "adfc"),
        sys_("s12", "screen", level=1),
    ],
)

VANDENBURG = design(
    name="Vandenburg",
    tmf=80,
    hull_boxes=24,
    armour=5,
    thrust=6,
    ftl=True,
    systems=[
        sys_("s1", "beam", **{"class": 3, "arcs": ["FP", "F", "FS"]}),
        sys_("s2", "beam", **{"class": 2, "arcs": ["FP", "F", "FS"]}),
        sys_("s3", "beam", **{"class": 2, "arcs": ["FP", "F", "FS"]}),
        sys_("s4", "beam", **{"class": 1, "arcs": ALL}),
        sys_("s5", "pds"),
        sys_("s6", "pds"),
        sys_("s7", "fire_control"),
        sys_("s8", "fire_control"),
        sys_("s9", "screen", level=1),
    ],
)


def bd(d):
    return FB.design_breakdown(d, OPTS)


def codes(d, severity="violation"):
    return {i.code for i in FB.validate_design(d, OPTS) if i.severity == severity}


def row_for(d, uid):
    return next(r for r in bd(d).rows if r.system_uid == uid)


def one_system(tmf=100, **system):
    """Mass and points of a single system on an otherwise empty hull."""
    d = design(tmf=tmf, systems=[{"uid": "x", **system}])
    r = row_for(d, "x")
    return r.mass, r.points


# ---- Golden tests ---------------------------------------------------------------------------


def test_registry():
    assert "fb" in RULESETS
    assert FB.id == "fb"


@pytest.mark.parametrize(
    "d,mass,points",
    [(HEAVY_CRUISER, 85, 290), (FURIOUS, 64, 219), (VANDENBURG, 80, 261)],
    ids=["heavy-cruiser-fb1-p10", "furious-fb1-p16", "vandenburg-fb1-p16"],
)
def test_golden_designs(d, mass, points):
    b = bd(d)
    assert b.mass_used == mass == d["tmf"]
    assert b.points == points
    assert codes(d) == set()


def test_heavy_cruiser_line_items_match_fb1_p11():
    b = bd(HEAVY_CRUISER)
    fixed = {r.key: (r.mass, r.points) for r in b.rows if r.system_uid is None}
    assert fixed["hull"] == (0, 85)
    assert fixed["hull_integrity"] == (26, 52)
    assert fixed["ftl"] == (9, 18)
    assert fixed["main_drive"] == (17, 34)
    assert row_for(HEAVY_CRUISER, "b1").mass == 5
    assert row_for(HEAVY_CRUISER, "m1").mass == 6
    assert row_for(HEAVY_CRUISER, "sc").mass == 4


@pytest.mark.parametrize(
    "boxes,rows",
    [(19, [5, 5, 5, 4]), (15, [4, 4, 4, 3]), (26, [7, 7, 6, 6]), (2, [1, 1, 0, 0]), (24, [6, 6, 6, 6])],
)
def test_damage_track(boxes, rows):
    assert FB.damage_track(design(hull_boxes=boxes)) == rows


def test_cf_dots_27_boxes_5_cf():
    d = design(tmf=90, hull_boxes=27)
    assert FB.crew_factors(d) == 5
    assert FB.cf_positions(d) == [6, 12, 18, 24, 27]


# ---- Costing rules --------------------------------------------------------------------------


def test_rounding_half_up_and_never_zero():
    # FB1 p.10: MASS 64 FTL = 6.4 -> 6; thrust-4 drive = 12.8 -> 13; MASS 4 FTL = 0.4 -> 1.
    assert bd(design(tmf=64, thrust=4)).derived["ftl_mass"] == 6
    assert bd(design(tmf=64, thrust=4)).derived["drive_mass"] == 13
    assert bd(design(tmf=4, hull_boxes=1, thrust=0)).derived["ftl_mass"] == 1


def test_no_ftl_no_drive_cost_nothing():
    b = bd(design(ftl=False, thrust=0))
    assert b.derived["ftl_mass"] == 0 and b.derived["drive_mass"] == 0


def test_hull_armour_and_basic_hull_points():
    b = bd(design(tmf=50, hull_boxes=15, armour=4, thrust=0, ftl=False))
    assert b.mass_used == 19
    assert b.points == 50 + 30 + 8


@pytest.mark.parametrize("kind,mass", [("partial", 5), ("full", 10)])
def test_streamlining(kind, mass):
    # FB1 p.10 example: MASS 50 partial = 5 MASS / 10 pts, full = 10 / 20.
    base = bd(design(tmf=50, thrust=0, ftl=False))
    b = bd(design(tmf=50, thrust=0, ftl=False, streamlining=kind))
    assert b.mass_used - base.mass_used == mass
    assert b.points - base.points == 2 * mass


@pytest.mark.parametrize(
    "cls,arcs,mass,points",
    [
        (1, ALL, 1, 3),
        (2, ["FP", "F", "FS"], 2, 6),
        (2, ALL, 3, 9),
        (3, ["F"], 4, 12),
        (3, ["FP", "F", "FS"], 6, 18),
        (4, ["F"], 8, 24),
        (4, ["FP", "F", "FS"], 12, 36),
        (5, ["F", "FS"], 20, 60),
    ],
)
def test_beam_costs(cls, arcs, mass, points):
    assert one_system(type="beam", arcs=arcs, **{"class": cls}) == (mass, points)


@pytest.mark.parametrize("arcs,mass", [(["F"], 4), (["F", "FS"], 5), (["FP", "F", "FS"], 6)])
def test_pulse_torpedo(arcs, mass):
    assert one_system(type="pulse_torpedo", arcs=arcs) == (mass, 3 * mass)


@pytest.mark.parametrize(
    "system,mass,points",
    [
        ({"type": "needle_beam", "arcs": ["F"]}, 2, 6),
        ({"type": "submunition"}, 1, 3),
        ({"type": "sm_launcher", "arcs": ["F"]}, 3, 9),
        ({"type": "sm_rack", "load": "std", "arcs": ["F"]}, 4, 12),
        ({"type": "sm_rack", "load": "er", "arcs": ["F"]}, 5, 15),
        ({"type": "pds"}, 1, 3),
        ({"type": "fire_control"}, 1, 4),
        ({"type": "adfc"}, 2, 8),
        ({"type": "hangar", "bays": 2}, 18, 54),
        ({"type": "hold", "kind": "cargo", "mass": 50}, 50, 0),
        ({"type": "nova_cannon", "arcs": ["F"]}, 20, 60),
        ({"type": "wave_gun", "arcs": ["F"]}, 12, 36),
        ({"type": "mt_missile"}, 2, 6),
        ({"type": "ortillery"}, 3, 9),
        ({"type": "minelayer", "mines": 3}, 5, 12),
        ({"type": "minesweeper"}, 5, 15),
        ({"type": "tender_bay", "capacity": 20}, 30, 90),
        ({"type": "tender_bay", "capacity": 5}, 8, 24),
    ],
)
def test_fixed_systems(system, mass, points):
    assert one_system(**system) == (mass, points)


def test_magazine_mass_is_its_capacity():
    d = design(
        systems=[
            sys_("l", "sm_launcher", arcs=["F"]),
            sys_("m", "sm_magazine", capacity=8, feeds=["l"]),
        ]
    )
    assert (row_for(d, "m").mass, row_for(d, "m").points) == (8, 24)


@pytest.mark.parametrize(
    "tmf,level,mass",
    [(60, 1, 3), (80, 1, 4), (85, 1, 4), (100, 1, 5), (50, 2, 6), (100, 2, 10), (100, 3, 15)],
)
def test_screens(tmf, level, mass):
    assert one_system(tmf=tmf, type="screen", level=level) == (mass, 3 * mass)


@pytest.mark.parametrize("tmf,mass", [(50, 10), (150, 15)])
def test_reflex_field(tmf, mass):
    assert one_system(tmf=tmf, type="reflex_field") == (mass, 6 * mass)


@pytest.mark.parametrize("tmf,mass", [(15, 2), (80, 8)])
def test_cloak(tmf, mass):
    assert one_system(tmf=tmf, type="cloak") == (mass, 10 * mass)


def test_tug_drive():
    # FB1 p.8: MASS 60 tug towing MASS 100 needs 6 + 20 = 26 MASS of jump drive.
    d = design(tmf=60, ftl=True, systems=[sys_("t", "tug_drive", tow_mass=100)])
    assert bd(d).derived["ftl_mass"] + row_for(d, "t").mass == 26
    assert row_for(d, "t").points == 40


def test_design_points_exclude_loadout():
    d = design(
        systems=[sys_("h", "hangar", bays=1)],
        default_loadout={"fighters": [{"hangar": "h", "type": "heavy"}], "magazines": []},
    )
    assert row_for(d, "h").points == 27
    assert FB.loadout_points(d, d["default_loadout"], OPTS) == 30


@pytest.mark.parametrize(
    "ftype,points",
    [
        ("standard", 18),
        ("interceptor", 18),
        ("fast", 24),
        ("attack", 24),
        ("long_range", 24),
        ("heavy", 30),
        ("torpedo", 36),
    ],
)
def test_fighter_group_costs(ftype, points):
    d = design(systems=[sys_("h", "hangar", bays=1)])
    assert (
        FB.loadout_points(d, {"fighters": [{"hangar": "h", "type": ftype}], "magazines": []}, OPTS) == points
    )


# ---- Derived values -------------------------------------------------------------------------


def test_thresholds():
    assert FB.threshold_numbers(FURIOUS) == [6, 5, 4]


@pytest.mark.parametrize(
    "tmf,kind,cf",
    [(20, "warship", 1), (21, "warship", 2), (100, "warship", 5), (120, "merchant", 3), (50, "merchant", 1)],
)
def test_crew_factors(tmf, kind, cf):
    assert FB.crew_factors(design(tmf=tmf, hull_kind=kind)) == cf


@pytest.mark.parametrize("thrust,turn", [(4, 2), (5, 2), (1, 1), (0, 0), (6, 3)])
def test_turn_thrust(thrust, turn):
    assert bd(design(thrust=thrust)).derived["turn_thrust"] == turn


def test_holds_split_larger_first():
    d = design(tmf=100, systems=[sys_("h", "hold", kind="cargo", mass=50)])
    assert bd(d).derived["holds"] == [{"uid": "h", "kind": "cargo", "spaces": [13, 13, 12, 12]}]


@pytest.mark.parametrize(
    "boxes,label", [(10, "Fragile"), (15, "Weak"), (30, "Average"), (40, "Strong"), (50, "Super")]
)
def test_hull_descriptor(boxes, label):
    assert bd(design(tmf=100, hull_boxes=boxes)).derived["hull_descriptor"] == label


@pytest.mark.parametrize(
    "tmf,systems,expected",
    [
        (64, [], ("Patrol or Escort Cruiser", "CE")),
        (85, [], ("Heavy Cruiser", "CH")),
        (6, [], ("Scout or Courier", "SC")),
        (20, [], ("Frigate", "FF")),
        (250, [], ("Superdreadnought", "SDN")),
        (150, [sys_("h", "hangar", bays=4)], ("Light Carrier", "CVL")),
    ],
)
def test_suggest_type(tmf, systems, expected):
    assert FB.suggest_type(design(tmf=tmf, systems=systems)) == expected


# ---- Validators -----------------------------------------------------------------------------


def test_mass_over_and_under():
    assert "mass_over" in codes(design(tmf=50, hull_boxes=60))
    assert "mass_under" in codes(design(tmf=50, hull_boxes=5))


def test_hull_minimum_is_rounded_ten_percent():
    # FB2 p.3: minimum 10% of total mass; FB1 designs with a rounded 10% hull stay legal.
    assert "hull_below_minimum" not in codes(design(tmf=64, hull_boxes=6))
    assert "hull_below_minimum" in codes(design(tmf=64, hull_boxes=5))


def test_class1_must_be_all_arcs():
    assert "beam_arcs" in codes(design(systems=[sys_("b", "beam", **{"class": 1, "arcs": ["F"]})]))


@pytest.mark.parametrize(
    "arcs,bad", [(["FP", "F", "FS"], False), (ALL, False), (["F", "FS"], True), (["F", "AS", "AP"], True)]
)
def test_class2_three_adjacent_or_six(arcs, bad):
    assert ("beam_arcs" in codes(design(systems=[sys_("b", "beam", **{"class": 2, "arcs": arcs})]))) is bad


def test_pulse_torpedo_max_three_adjacent_arcs():
    assert "torpedo_arcs" in codes(design(systems=[sys_("t", "pulse_torpedo", arcs=["FP", "F", "FS", "AS"])]))
    assert "torpedo_arcs" in codes(design(systems=[sys_("t", "pulse_torpedo", arcs=["F", "A"])]))
    assert "torpedo_arcs" not in codes(design(systems=[sys_("t", "pulse_torpedo", arcs=["AP", "FP"])]))


def test_single_arc_weapons():
    assert "needle_arcs" in codes(design(systems=[sys_("n", "needle_beam", arcs=["F", "FS"])]))


def test_arcs_must_be_known_and_present():
    assert "bad_arcs" in codes(design(systems=[sys_("b", "beam", **{"class": 3, "arcs": ["X"]})]))
    assert "bad_arcs" in codes(design(systems=[sys_("b", "beam", **{"class": 3, "arcs": []})]))


def test_magazine_links():
    unlinked = design(
        systems=[sys_("l", "sm_launcher", arcs=["F"]), sys_("m", "sm_magazine", capacity=4, feeds=[])]
    )
    assert {"magazine_unlinked", "launcher_unfed"} <= codes(unlinked)
    two = design(
        systems=[
            sys_("l", "sm_launcher", arcs=["F"]),
            sys_("m", "sm_magazine", capacity=4, feeds=["l"]),
            sys_("n", "sm_magazine", capacity=4, feeds=["l"]),
        ]
    )
    assert "launcher_fed_twice" in codes(two)
    wrong = design(systems=[sys_("p", "pds"), sys_("m", "sm_magazine", capacity=4, feeds=["p"])])
    assert "magazine_bad_feed" in codes(wrong)


def test_salvo_load_must_fit_magazine():
    d = copy.deepcopy(HEAVY_CRUISER)
    d["default_loadout"]["magazines"] = [{"magazine": "m1", "salvos": ["er", "er", "std"]}]
    assert "magazine_overloaded" in codes(d)
    d["default_loadout"]["magazines"] = [{"magazine": "m1", "salvos": ["er", "er"]}]
    assert "magazine_overloaded" not in codes(d)


def test_fighter_loadout_needs_hangar():
    d = design(default_loadout={"fighters": [{"hangar": "nope", "type": "standard"}], "magazines": []})
    assert "fighters_without_hangar" in codes(d)
    full = design(
        systems=[sys_("h", "hangar", bays=1)],
        default_loadout={
            "fighters": [{"hangar": "h", "type": "standard"}, {"hangar": "h", "type": "fast"}],
            "magazines": [],
        },
    )
    assert "hangar_overfull" in codes(full)


def test_unknown_system_and_fighter_type():
    assert "unknown_system" in codes(design(systems=[sys_("z", "death_ray")]))
    d = design(
        systems=[sys_("h", "hangar", bays=1)],
        default_loadout={"fighters": [{"hangar": "h", "type": "ninja"}], "magazines": []},
    )
    assert "unknown_fighter_type" in codes(d)


def test_infos():
    d = design(tmf=50, hull_boxes=15, ftl=False, thrust=4, systems=[sys_("s", "screen", level=3)])
    infos = codes(d, "info")
    assert {"no_fire_control", "no_ftl", "screen_backups"} <= infos
    assert not ({"no_fire_control", "no_ftl", "screen_backups"} & codes(d))


def test_issues_carry_system_uid_and_translated_message():
    issues = FB.validate_design(design(systems=[sys_("b", "beam", **{"class": 1, "arcs": ["F"]})]), OPTS)
    beam = next(i for i in issues if i.code == "beam_arcs")
    assert beam.system_uid == "b" and beam.message


# ---- Picker and interface -------------------------------------------------------------------


def test_system_types_cover_every_costed_type():
    types = {s.type for s in FB.system_types("human", OPTS)}
    assert types >= {
        "beam",
        "pulse_torpedo",
        "needle_beam",
        "submunition",
        "sm_launcher",
        "sm_magazine",
        "sm_rack",
        "pds",
        "fire_control",
        "adfc",
        "screen",
        "hangar",
        "hold",
        "nova_cannon",
        "wave_gun",
        "mt_missile",
        "ortillery",
        "minelayer",
        "minesweeper",
        "reflex_field",
        "cloak",
        "tug_drive",
        "tender_bay",
    }


def test_races_and_books():
    # Human is this module's subject; the alien tech modules are tested beside it.
    assert [r.id for r in FB.races()][0] == "human"
    assert {b.code for b in FB.books} == {"FB1", "FB2"}
    assert all(b.page_offset == 0 for b in FB.books)
