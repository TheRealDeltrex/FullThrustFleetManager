"""FB ruleset, Phalon tech (FB2 pp.35-37).

Golden test first: the FB2 p.37 worked example, NPV 379. Then one test per costing rule and per
validator, with the layered shell getting the most attention because it is the only part of the
race that needed a new field. The printed TMF/NPV panels of pp.38-45 are the NPV gate's job
(tests/test_catalog_gate.py).
"""

from __future__ import annotations

import pytest

from rulesets import get_ruleset
from rulesets.fb import phalon

FB = get_ruleset("fb")
OPTS: dict = {}

ALL = ["F", "FS", "AS", "A", "AP", "FP"]
FORE3 = ["FP", "F", "FS"]


def design(**kw) -> dict:
    d = {
        "schema_version": 2,
        "id": "t",
        "ruleset": "fb",
        "race": "phalon",
        "faction": "PH",
        "name": "Test",
        "type_label": "",
        "type_code": "",
        "hull_kind": "warship",
        "tmf": 100,
        "hull_boxes": 20,
        "armour": 0,
        "armour_layers": [],
        "thrust": 4,
        "ftl": True,
        "streamlining": "none",
        "systems": [],
        "default_loadout": {"fighters": [], "magazines": [], "pulsers": []},
        "allow_rule_breaking": False,
        "layout_hints": {},
        "source": {"kind": "custom"},
        "notes": "",
    }
    d.update(kw)
    return d


def sys_(uid, type_, **kw):
    return {"uid": uid, "type": type_, **kw}


# FB2 p.37: MASS 100, hull 20, shell 12 as an inner layer of 8 and an outer of 4, thrust 4, FTL,
# 2 one-arc pulsers, 1 three-arc, 2 all-arc, a class-3 plasma bolt launcher, 3 fire controls and
# a vapour shroud. The book prints every intermediate figure, so they are all asserted.
EXAMPLE = design(
    tmf=100,
    hull_boxes=20,
    armour=12,
    armour_layers=[8, 4],
    thrust=4,
    ftl=True,
    systems=[
        sys_("p1", "pulser", arcs=["F"]),
        sys_("p2", "pulser", arcs=["F"]),
        sys_("p3", "pulser", arcs=FORE3),
        sys_("p4", "pulser", arcs=ALL),
        sys_("p5", "pulser", arcs=ALL),
        sys_("b1", "plasma_bolt_launcher", **{"class": 3, "arcs": FORE3}),
        sys_("f1", "fire_control"),
        sys_("f2", "fire_control"),
        sys_("f3", "fire_control"),
        sys_("v1", "vapour_shroud"),
    ],
)


def test_golden_fb2_p37_example_costs_379():
    b = FB.design_breakdown(EXAMPLE, OPTS)
    assert b.points == 379
    assert b.mass_used == 100
    assert not [i for i in FB.validate_design(EXAMPLE, OPTS) if i.severity == "violation"]


def test_golden_fb2_p37_example_rows():
    rows: dict[str, list[int]] = {}
    for r in FB.design_breakdown(EXAMPLE, OPTS).rows:
        rows.setdefault(r.key, [0, 0])
        rows[r.key][0] += r.mass
        rows[r.key][1] += r.points
    assert rows["hull"] == [0, 100]
    assert rows["hull_integrity"] == [20, 40]
    assert rows["armour"] == [12, 32]                  # (8 x 2) + (4 x 4)
    assert rows["main_drive"] == [20, 40]
    assert rows["ftl"] == [10, 20]
    assert rows["pulser"] == [15, 75]                  # 4 + 3 + 8 MASS at 5 points each
    assert rows["plasma_bolt_launcher"] == [15, 45]    # 5 x class 3, at 3 points per MASS
    assert rows["fire_control"] == [3, 12]
    assert rows["vapour_shroud"] == [5, 15]            # 5% of MASS, at 3 points per MASS


def test_golden_fb2_p37_example_derived():
    d = FB.design_breakdown(EXAMPLE, OPTS).derived
    assert d["damage_track"] == [5, 5, 5, 5]   # "four rows of 5"
    assert d["shell_layers"] == [8, 4]
    assert d["crew_factors"] == 5              # 1 per 20 MASS (FB2 p.36)


# ---- The shell ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("layers", "points"),
    [([8, 4], 32), ([1], 2), ([3, 2], 14), ([16, 10, 8, 6], 168), ([12, 8, 6, 4], 124), ([], 0)],
)
def test_shell_costs_two_points_per_layer_number(layers, points):
    """FB2 p.35: "the cost is 2 x layer number", so a fourth-layer box costs 8. The last two are
    the Voth's and the Draath's shells (FB2 pp.44-45)."""
    assert phalon.shell_points(layers) == points


def test_a_design_without_layers_has_one_layer():
    """Every other race's armour is a single layer, and so is a Phalon shell that records none."""
    d = design(armour=5, armour_layers=[])
    assert phalon.shell_layers(d) == [5]
    row = next(r for r in FB.design_breakdown(d, OPTS).rows if r.key == "armour")
    assert (row.mass, row.points) == (5, 10)


def test_layers_are_clamped_to_the_shell_total():
    """A malformed design can never cost more shell than it bought."""
    assert phalon.shell_layers(design(armour=6, armour_layers=[4, 4, 4])) == [4, 2, 0]


def test_layers_that_do_not_add_up_are_a_violation():
    d = design(armour=10, armour_layers=[4, 4])
    assert "shell_layers_total" in {i.code for i in FB.validate_design(d, OPTS)}
    ok = design(armour=8, armour_layers=[4, 4])
    assert "shell_layers_total" not in {i.code for i in FB.validate_design(ok, OPTS)}


def test_a_deep_shell_is_allowed_but_noted():
    """FB2 p.35 allows "theoretically even more" than four layers, so this is info, not a
    violation."""
    d = design(armour=5, armour_layers=[1, 1, 1, 1, 1])
    issues = {i.code: i.severity for i in FB.validate_design(d, OPTS)}
    assert issues.get("shell_deep") == "info"


# ---- Costing rules ---------------------------------------------------------------------------


@pytest.mark.parametrize(("arcs", "mass"), [(["F"], 2), (FORE3, 3), (ALL, 4)])
def test_pulser_mass_by_arc_count(arcs, mass):
    """FB2 p.35: one, three or six arcs for 2, 3 or 4 MASS, at 5 points per MASS."""
    d = design(systems=[sys_("p", "pulser", arcs=arcs)])
    row = next(r for r in FB.design_breakdown(d, OPTS).rows if r.key == "pulser")
    assert (row.mass, row.points) == (mass, 5 * mass)


@pytest.mark.parametrize("cls", [1, 2, 3, 4, 5, 6])
def test_plasma_bolt_launcher_is_five_mass_per_class(cls):
    d = design(systems=[sys_("b", "plasma_bolt_launcher", **{"class": cls, "arcs": FORE3})])
    row = next(r for r in FB.design_breakdown(d, OPTS).rows if r.key == "plasma_bolt_launcher")
    assert (row.mass, row.points) == (5 * cls, 15 * cls)


@pytest.mark.parametrize(("tmf", "mass"), [(100, 5), (250, 13), (41, 2), (10, 1), (4, 1)])
def test_vapour_shroud_is_five_percent_with_a_minimum_of_one(tmf, mass):
    d = design(tmf=tmf, systems=[sys_("v", "vapour_shroud")])
    row = next(r for r in FB.design_breakdown(d, OPTS).rows if r.key == "vapour_shroud")
    assert (row.mass, row.points) == (mass, 3 * mass)


def test_hangar_bay_costs_three_points_per_mass():
    """FB2 p.36 prints 18 points, as the Kra'Vak section does, and is wrong the same way: the
    Taanis (641) and Draath (1002) only reconcile at the human 27."""
    d = design(systems=[sys_("h", "hangar", bays=1)])
    row = next(r for r in FB.design_breakdown(d, OPTS).rows if r.key == "hangar")
    assert (row.mass, row.points) == (9, 27)


def test_fire_control_and_adfc_match_the_human_prices():
    d = design(systems=[sys_("f", "fire_control"), sys_("a", "adfc")])
    rows = {r.key: (r.mass, r.points) for r in FB.design_breakdown(d, OPTS).rows}
    assert rows["fire_control"] == (1, 4) and rows["adfc"] == (2, 8)


def test_crew_factors_are_one_per_twenty_mass():
    """FB2 p.36 restates the human rule, with its own example: MASS 41 is crew factor 3."""
    assert FB.crew_factors(design(tmf=41)) == 3
    assert FB.crew_factors(design(tmf=30)) == 2


# ---- Pulser configuration (a loadout setting, PLAN 5.4) ------------------------------------------


def test_pulser_mode_comes_from_the_loadout_and_costs_nothing():
    d = design(
        systems=[sys_("p1", "pulser", arcs=["F"]), sys_("p2", "pulser", arcs=ALL)],
        default_loadout={"fighters": [], "magazines": [],
                         "pulsers": [{"pulser": "p1", "mode": "M"}, {"pulser": "p2", "mode": "C"}]},
    )
    assert phalon.pulser_modes(d, None) == {"p1": "M", "p2": "C"}
    assert FB.loadout_points(d, None, OPTS) == 0
    assert FB.design_breakdown(d, OPTS).derived["pulser_modes"] == {"p1": "M", "p2": "C"}


def test_an_unset_pulser_stays_blank():
    """FB2 p.35 prints blank pulser icons for the player to write into, so an unset battery is
    left blank rather than given a default."""
    d = design(systems=[sys_("p1", "pulser", arcs=["F"])])
    assert phalon.pulser_modes(d, None) == {}


def test_a_ships_loadout_overrides_the_designs():
    d = design(
        systems=[sys_("p1", "pulser", arcs=["F"])],
        default_loadout={"fighters": [], "magazines": [], "pulsers": [{"pulser": "p1", "mode": "L"}]},
    )
    ship = {"fighters": [], "magazines": [], "pulsers": [{"pulser": "p1", "mode": "C"}]}
    assert phalon.pulser_modes(d, ship) == {"p1": "C"}


def test_a_bad_pulser_setting_is_a_violation():
    d = design(
        systems=[sys_("p1", "pulser", arcs=["F"])],
        default_loadout={"fighters": [], "magazines": [], "pulsers": [{"pulser": "nope", "mode": "L"}]},
    )
    assert "pulser_setting_unknown" in {i.code for i in FB.validate_design(d, OPTS)}


# ---- Validation ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("arcs", "ok"),
    [(["F"], True), (FORE3, True), (ALL, True), (["F", "FS"], False),
     (["F", "AS", "AP"], False), (["F", "FS", "AS", "A"], False)],
)
def test_pulser_arc_rules(arcs, ok):
    """FB2 p.35: "it may have one, three or six arcs of fire"; three must be adjacent."""
    d = design(systems=[sys_("p", "pulser", arcs=arcs)])
    codes = {i.code for i in FB.validate_design(d, OPTS) if i.severity == "violation"}
    assert ("pulser_arcs" in codes) is not ok


@pytest.mark.parametrize(
    ("arcs", "ok"),
    [(FORE3, True), (["AS", "A", "AP"], True), (["F"], False), (["F", "AS", "AP"], False)],
)
def test_plasma_bolt_launcher_is_a_three_arc_system(arcs, ok):
    """FB2 p.36: "The launcher is a 3-arc (180 degree) system"."""
    d = design(systems=[sys_("b", "plasma_bolt_launcher", **{"class": 1, "arcs": arcs})])
    codes = {i.code for i in FB.validate_design(d, OPTS) if i.severity == "violation"}
    assert ("pbl_arcs" in codes) is not ok


@pytest.mark.parametrize("stype", ["beam", "kgun", "stinger", "screen", "pds", "scattergun"])
def test_other_races_systems_are_refused(stype):
    """Phalons have no separate PDS - their pulsers do that job (FB2 p.35) - and none of the
    other races' weapons."""
    d = design(systems=[sys_("s", stype)])
    assert "race_system" in {i.code for i in FB.validate_design(d, OPTS) if i.severity == "violation"}


def test_phalon_systems_are_not_available_to_other_races():
    for race in ("human", "kravak", "savasku"):
        d = design(race=race, systems=[sys_("p", "pulser", arcs=["F"])])
        codes = {i.code for i in FB.validate_design(d, OPTS) if i.severity == "violation"}
        assert codes & {"unknown_system", "race_system"}, race


def test_hull_minimum_is_ten_percent():
    assert "hull_below_minimum" in {i.code for i in FB.validate_design(design(hull_boxes=9), OPTS)}


def test_picker_offers_phalon_systems_only():
    types = {s.type for s in FB.system_types("phalon", OPTS)}
    assert {"pulser", "plasma_bolt_launcher", "vapour_shroud", "adfc", "fire_control"} <= types
    assert not types & {"beam", "kgun", "stinger", "screen", "pds"}


def test_races_now_lists_four():
    assert [r.id for r in FB.races()] == ["human", "kravak", "savasku", "phalon"]
    assert FB.icon_set_for("phalon") == "fb_phalon"


def test_malformed_design_never_raises():
    d = design(tmf="x", hull_boxes=None, armour_layers="no",
               systems=[{"uid": "p", "type": "pulser"}, 7])
    FB.design_breakdown(d, OPTS)
    FB.validate_design(d, OPTS)
