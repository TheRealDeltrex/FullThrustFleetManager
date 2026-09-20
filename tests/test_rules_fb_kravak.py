"""FB ruleset, Kra'Vak tech (FB2 pp.9-11).

Golden test first: the FB2 p.11 worked example, NPV 384 (PLAN 17). Then one test per costing
rule and per validator. The printed TMF/NPV panels of pp.12-19 are the NPV gate's job
(tests/test_catalog_gate.py); what is checked here is the design system itself.
"""

from __future__ import annotations

import pytest

from rulesets import get_ruleset

FB = get_ruleset("fb")
OPTS: dict = {}

ALL = ["F", "FS", "AS", "A", "AP", "FP"]


def design(**kw) -> dict:
    d = {
        "schema_version": 1,
        "id": "t",
        "ruleset": "fb",
        "race": "kravak",
        "faction": "KV",
        "name": "Test",
        "type_label": "",
        "type_code": "",
        "hull_kind": "warship",
        "tmf": 100,
        "hull_boxes": 40,
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


def kgun(uid, cls, arcs):
    return {"uid": uid, "type": "kgun", "class": cls, "arcs": arcs}


# FB2 p.11: MASS 100, hull 40, thrust 4A, FTL, 2 x K-5 (F), 1 x K-1 (all arc), 4 scatterguns,
# 2 fire controls. The book prints every intermediate figure, so they are all asserted.
EXAMPLE = design(
    tmf=100,
    hull_boxes=40,
    thrust=4,
    ftl=True,
    systems=[
        kgun("k1", 5, ["F"]),
        kgun("k2", 5, ["F"]),
        kgun("k3", 1, ALL),
        sys_("f1", "fire_control"),
        sys_("f2", "fire_control"),
        sys_("g1", "scattergun"),
        sys_("g2", "scattergun"),
        sys_("g3", "scattergun"),
        sys_("g4", "scattergun"),
    ],
)


def test_golden_fb2_p11_example_costs_384():
    b = FB.design_breakdown(EXAMPLE, OPTS)
    assert b.points == 384
    assert b.mass_used == 100
    assert not [i for i in FB.validate_design(EXAMPLE, OPTS) if i.severity == "violation"]


def test_golden_fb2_p11_example_rows():
    rows = {r.key: r for r in FB.design_breakdown(EXAMPLE, OPTS).rows if r.key != "kgun"}
    assert (rows["hull"].mass, rows["hull"].points) == (0, 100)
    assert (rows["hull_integrity"].mass, rows["hull_integrity"].points) == (40, 80)
    # The one rule that makes the race: 3 points per MASS of Advanced Grav Drive (FB2 p.9).
    assert (rows["main_drive"].mass, rows["main_drive"].points) == (20, 60)
    assert (rows["ftl"].mass, rows["ftl"].points) == (10, 20)
    kguns = [r for r in FB.design_breakdown(EXAMPLE, OPTS).rows if r.key == "kgun"]
    assert sum(r.mass for r in kguns) == 24 and sum(r.points for r in kguns) == 96


def test_golden_fb2_p11_example_derived():
    d = FB.design_breakdown(EXAMPLE, OPTS).derived
    assert d["damage_track"] == [10, 10, 10, 10]  # "four rows of 10"
    assert d["crew_factors"] == 5  # 1 per 20 MASS (FB2 p.10)
    assert d["thresholds"] == [6, 5, 4]
    assert d["turn_thrust"] == 4  # up to ALL thrust for course changes (FB2 p.9)


# ---- Costing rules ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("cls", "arcs", "mass"),
    [(1, ALL, 2), (2, ["F"], 3), (2, ["F", "FS"], 4), (3, ["F"], 5), (4, ["F"], 8),
     (5, ["F"], 11), (6, ["F"], 14), (7, ["F"], 17), (9, ["F"], 23)],
)
def test_kgun_mass_table(cls, arcs, mass):
    """FB2 p.9, incl. "the mass required rises by 3 per additional class" above K-6."""
    d = design(systems=[kgun("k", cls, arcs)])
    row = next(r for r in FB.design_breakdown(d, OPTS).rows if r.key == "kgun")
    assert row.mass == mass
    assert row.points == 4 * mass  # "All K-guns cost 4 points per MASS used."


@pytest.mark.parametrize(
    ("stype", "extra", "mass", "points"),
    [("mkp", {"arcs": ["F"]}, 1, 4), ("scattergun", {}, 1, 5), ("fire_control", {}, 1, 4)],
)
def test_small_system_costs(stype, extra, mass, points):
    d = design(systems=[sys_("s", stype, **extra)])
    row = next(r for r in FB.design_breakdown(d, OPTS).rows if r.key == stype)
    assert (row.mass, row.points) == (mass, points)


def test_hangar_bay_costs_three_points_per_mass():
    """FB2 p.10 prints 18 points, but every Kra'Vak design in the book costs bays at the human
    27 (3 per MASS); the printed 18 is the Ra'San group's own cost on the same page."""
    d = design(systems=[sys_("h", "hangar", bays=1)])
    row = next(r for r in FB.design_breakdown(d, OPTS).rows if r.key == "hangar")
    assert (row.mass, row.points) == (9, 27)


def test_tender_bay_is_one_and_a_half_mass_per_craft_mass():
    """FB2 p.10; the To'Rok's 2 x MASS-2 shuttles need a 6-MASS bay costing 18."""
    d = design(systems=[sys_("t", "tender_bay", capacity=4)])
    row = next(r for r in FB.design_breakdown(d, OPTS).rows if r.key == "tender_bay")
    assert (row.mass, row.points) == (6, 18)


def test_holds_cost_nothing_but_take_mass():
    d = design(systems=[sys_("h", "hold", kind="cargo", mass=18)])
    row = next(r for r in FB.design_breakdown(d, OPTS).rows if r.key == "hold")
    assert (row.mass, row.points) == (18, 0)


def test_armour_is_permitted_at_the_human_price():
    """FB2 p.9: "the same MASS (1 per box) and cost (2 points per box) as human armour"."""
    d = design(armour=3)
    row = next(r for r in FB.design_breakdown(d, OPTS).rows if r.key == "armour")
    assert (row.mass, row.points) == (3, 6)
    assert "kv_armour" in {i.code for i in FB.validate_design(d, OPTS)}


def test_merchant_crew_factor_is_one_per_fifty_mass():
    """The Sha'Ken (FB2 p.19) is MASS 40 with "Crew Factor: 1 (Merchant)"."""
    assert FB.crew_factors(design(tmf=40, hull_kind="merchant")) == 1
    assert FB.crew_factors(design(tmf=40)) == 2


def test_fighter_groups_are_rasan_and_vasan():
    assert sorted(FB.fighter_types(OPTS, "kravak")) == ["heavy", "standard"]
    d = design(
        systems=[sys_("h", "hangar", bays=2)],
        default_loadout={"fighters": [{"hangar": "h", "type": "standard"},
                                      {"hangar": "h", "type": "heavy"}], "magazines": []},
    )
    assert FB.loadout_points(d, None, OPTS) == 18 + 30


# ---- Validation ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("cls", "arcs", "ok"),
    [(1, ALL, True), (1, ["F"], False),
     (2, ["F"], True), (2, ["F", "FS"], True), (2, ["F", "AS"], False), (2, ["F", "FS", "AS"], False),
     (3, ["F"], True), (3, ["F", "FS"], False), (5, ["A"], True)],
)
def test_kgun_arc_rules(cls, arcs, ok):
    """FB2 p.9: class 1 is always all-round, class 2 has one or two arcs, larger classes one."""
    d = design(systems=[kgun("k", cls, arcs)])
    codes = {i.code for i in FB.validate_design(d, OPTS) if i.severity == "violation"}
    assert ("kgun_arcs" in codes) is not ok


def test_mkp_fires_through_one_arc():
    bad = design(systems=[sys_("m", "mkp", arcs=["F", "FS"])])
    assert "mkp_arcs" in {i.code for i in FB.validate_design(bad, OPTS)}
    good = design(systems=[sys_("m", "mkp", arcs=["F"])])
    assert "mkp_arcs" not in {i.code for i in FB.validate_design(good, OPTS)}


@pytest.mark.parametrize("stype", ["screen", "pds", "adfc", "beam", "sm_launcher", "cloak"])
def test_human_systems_are_not_available_to_kravak(stype):
    """FB2 p.8: "Kra'Vak warships do not carry energy screens"; p.10: no ADFC. Their weapons
    are K-guns, MKPs and scatterguns, and nothing else."""
    d = design(systems=[sys_("s", stype)])
    assert "race_system" in {i.code for i in FB.validate_design(d, OPTS) if i.severity == "violation"}


def test_kravak_systems_are_not_available_to_humans():
    d = design(race="human", systems=[kgun("k", 3, ["F"])])
    assert "unknown_system" in {i.code for i in FB.validate_design(d, OPTS) if i.severity == "violation"}


def test_hull_minimum_is_ten_percent():
    d = design(tmf=100, hull_boxes=9)
    assert "hull_below_minimum" in {i.code for i in FB.validate_design(d, OPTS)}


def test_mass_must_equal_tmf():
    codes = {i.code for i in FB.validate_design(design(tmf=100, hull_boxes=40), OPTS)}
    assert "mass_under" in codes


def test_picker_offers_kravak_systems_only():
    types = {s.type for s in FB.system_types("kravak", OPTS)}
    assert {"kgun", "mkp", "scattergun", "fire_control", "hangar"} <= types
    assert not types & {"beam", "screen", "pds", "adfc", "sm_launcher"}


def test_races_lists_human_and_kravak():
    # This module's subject; the other races are tested beside it.
    assert [r.id for r in FB.races()][:2] == ["human", "kravak"]


def test_kravak_has_its_own_icon_set():
    assert FB.icon_set_for("kravak") == "fb_kravak"
    assert FB.icon_set_for("human") == "fb"


def test_malformed_design_never_raises():
    d = design(race="kravak", tmf="x", hull_boxes=None, systems=[{"uid": "k", "type": "kgun"}, 7])
    FB.design_breakdown(d, OPTS)
    FB.validate_design(d, OPTS)
