"""FB ruleset, Sa'Vasku tech (FB2 pp.21-25).

Golden test first: the FB2 p.24 worked example. Then the thrust tables printed on the
SSDs, one test per costing rule, and the validators. The printed TMF/NPV panels of pp.26-32 are
the NPV gate's job (tests/test_catalog_gate.py).
"""

from __future__ import annotations

import pytest

from rulesets import get_ruleset
from rulesets.fb import savasku

FB = get_ruleset("fb")
OPTS: dict = {}


def design(**kw) -> dict:
    d = {
        "schema_version": 1,
        "id": "t",
        "ruleset": "fb",
        "race": "savasku",
        "faction": "SV",
        "name": "Test",
        "type_label": "",
        "type_code": "",
        "hull_kind": "warship",
        "tmf": 100,
        "hull_boxes": 30,
        "armour": 0,
        "thrust": 0,
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


# FB2 p.24: MASS 100, biomass 30, carapace 10, power generators 22, drive node, FTL node,
# 3 stingers, 1 pod launcher, 2 spicules, 2 cortex nodes, 1 screen node.
EXAMPLE = design(
    tmf=100,
    hull_boxes=30,
    armour=10,
    ftl=True,
    systems=[
        sys_("g", "power_generator", capacity=22),
        sys_("s1", "stinger", arcs=["AP", "FP", "F"]),
        sys_("s2", "stinger", arcs=["FP", "F", "FS"]),
        sys_("s3", "stinger", arcs=["F", "FS", "AS"]),
        sys_("p1", "pod_launcher", arcs=["F"]),
        sys_("d1", "spicule"),
        sys_("d2", "spicule"),
        sys_("c1", "cortex"),
        sys_("c2", "cortex"),
        sys_("n1", "screen_node"),
    ],
)


def test_golden_fb2_p24_example_costs_its_printed_line_items():
    """FB2 p.24's worked example. Its MASS closes at exactly 100 and its eleven printed line
    items (100 + 60 + 20 + 44 + 20 + 20 + 18 + 9 + 6 + 8 + 15) come to 320, but the total line
    under them reads "342 points". The line items are right: all fourteen printed ship panels on
    pp.26-32 recompute exactly, so the total is an addition slip, like the FT p.31 example
    already in data/errata.json. The same page's thrust table is wrong too (see below)."""
    b = FB.design_breakdown(EXAMPLE, OPTS)
    assert b.points == 320
    assert b.mass_used == 100
    assert not [i for i in FB.validate_design(EXAMPLE, OPTS) if i.severity == "violation"]


def test_golden_fb2_p24_example_rows():
    rows = {}
    for r in FB.design_breakdown(EXAMPLE, OPTS).rows:
        rows.setdefault(r.key, [0, 0])
        rows[r.key][0] += r.mass
        rows[r.key][1] += r.points
    assert rows["hull"] == [0, 100]
    assert rows["hull_integrity"] == [30, 60]      # biomass
    assert rows["armour"] == [10, 20]              # carapace
    assert rows["power_generator"] == [22, 44]
    assert rows["main_drive"] == [10, 20]          # 10% of MASS, no thrust rating
    assert rows["ftl"] == [10, 20]
    assert rows["stinger"] == [6, 18]
    assert rows["pod_launcher"] == [3, 9]
    assert rows["spicule"] == [2, 6]
    assert rows["cortex"] == [2, 8]
    assert rows["screen_node"] == [5, 15]


def test_golden_fb2_p24_example_derived():
    d = FB.design_breakdown(EXAMPLE, OPTS).derived
    assert d["damage_track"] == [8, 8, 7, 7]   # "split 8/8/7/7" (FB2 p.24)
    assert d["power"] == 22
    # "2 PGs each of factor 6, and 2 of factor 5; the stronger PGs are always on the lower
    # damage track rows ... so the four PGs will be arranged as 5/5/6/6" (FB2 p.24).
    assert d["power_generators"] == [5, 5, 6, 6]
    assert d["crew_factors"] == 0 and d["cf_positions"] == []


# ---- Thrust tables (FB2 pp.21-22, 25-26) ---------------------------------------------------------


def test_thrust_table_of_the_shyythavar():
    """FB2 p.30, MASS 100 with 24 power. The rules chapter prints this same table on p.25 as the
    worked example's, although that ship has 22 power generators, not 24 - which is why its
    damaged column still reads 24 at thrust 6, a figure a 22-power ship could never pay."""
    assert savasku.thrust_table(100, 24) == [
        (1, 2, 4), (2, 4, 8), (3, 6, 12), (4, 8, 16), (5, 10, 20), (6, 12, 24),
        (7, 14, None), (8, 16, None), (9, 18, None), (10, 20, None), (11, 22, None),
        (12, 24, None),
    ]


def test_thrust_table_of_the_saantha():
    """FB2 p.26, MASS 10, power 2: the printed table is 3 1/1, 6 1/2, 7 1/-, 12 2/-."""
    assert savasku.thrust_table(10, 2) == [(3, 1, 1), (6, 1, 2), (7, 1, None), (12, 2, None)]


def test_thrust_table_of_the_sakesstha():
    """FB2 p.26, MASS 11, power 3: 3 1/1, 5 1/2, 6 1/3, 7 2/3, 11 2/-, 15 3/-."""
    assert savasku.thrust_table(11, 3) == [
        (3, 1, 1), (5, 1, 2), (6, 1, 3), (7, 2, 3), (11, 2, None), (15, 3, None),
    ]


def test_thrust_power_is_round_half_up_not_rounded_up():
    """FB2 p.21 says "rounded up" and shows 9.6 -> 10, but every printed table is round-half-up:
    the Sa'Kess'Tha needs 1 PP at thrust 6 (1.32) and 2 at thrust 7 (1.54)."""
    assert savasku.thrust_power(11, 6) == 1
    assert savasku.thrust_power(11, 7) == 2
    assert savasku.thrust_power(80, 6) == 10   # the p.21 worked example, 9.6
    assert savasku.thrust_power(100, 3, damaged=True) == 12


def test_thrust_table_of_the_fovurath_differs_from_the_book_in_one_cell():
    """FB2 p.28, MASS 40 with 9 power. The book ends the 6-power band at thrust 7, but
    2% x 8 x 40 = 6.4 rounds to 6 as well, so the band runs to 8. Eleven of the other thirteen
    tables match the book to the cell, so this row is a slip, recorded in the extractor."""
    ours = savasku.thrust_table(40, 9)
    book = [(1, 1, 2), (2, 2, 3), (3, 2, 5), (4, 3, 6), (5, 4, 8),
            (6, 5, None), (7, 6, None), (9, 7, None), (10, 8, None), (11, 9, None)]
    assert [row for row in ours if row not in book] == [(8, 6, None)]
    assert savasku.thrust_power(40, 8) == 6


def test_a_ship_with_no_power_has_an_empty_thrust_table():
    assert savasku.thrust_table(100, 0) == []


# ---- Costing rules ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("stype", "extra", "mass", "points"),
    [("stinger", {"arcs": ["FP", "F", "FS"]}, 2, 6), ("pod_launcher", {"arcs": ["F"]}, 3, 9),
     ("spicule", {}, 1, 3), ("cortex", {}, 1, 4), ("drone_womb", {}, 3, 9)],
)
def test_node_costs(stype, extra, mass, points):
    d = design(systems=[sys_("s", stype, **extra)])
    row = next(r for r in FB.design_breakdown(d, OPTS).rows if r.key == stype)
    assert (row.mass, row.points) == (mass, points)


@pytest.mark.parametrize(("tmf", "mass"), [(120, 6), (100, 5), (94, 5), (40, 3), (10, 3)])
def test_screen_node_is_five_percent_with_a_minimum_of_three(tmf, mass):
    """FB2 p.23, with its own example: a MASS 120 ship's node is 6 MASS and needs 6 power."""
    d = design(tmf=tmf, systems=[sys_("n", "screen_node")])
    row = next(r for r in FB.design_breakdown(d, OPTS).rows if r.key == "screen_node")
    assert (row.mass, row.points) == (mass, 3 * mass)


def test_power_generators_cost_two_points_per_mass():
    d = design(systems=[sys_("g", "power_generator", capacity=16)])
    row = next(r for r in FB.design_breakdown(d, OPTS).rows if r.key == "power_generator")
    assert (row.mass, row.points) == (16, 32)


@pytest.mark.parametrize(
    ("total", "split"), [(22, [5, 5, 6, 6]), (16, [4, 4, 4, 4]), (2, [0, 0, 1, 1]), (0, [0, 0, 0, 0])]
)
def test_generators_put_the_stronger_ones_on_the_lower_rows(total, split):
    assert savasku.generator_row_split(total) == split


def test_the_drive_node_is_ten_percent_and_has_no_thrust_rating():
    d = design(tmf=94)
    row = next(r for r in FB.design_breakdown(d, OPTS).rows if r.key == "main_drive")
    assert (row.mass, row.points) == (9, 18)
    assert FB.design_breakdown(d, OPTS).derived["turn_thrust"] == 0


def test_drones_are_grown_not_bought():
    d = design(
        systems=[sys_("w", "drone_womb")],
        default_loadout={"fighters": [{"hangar": "w", "type": "drone"}], "magazines": []},
    )
    assert FB.loadout_points(d, None, OPTS) == 0
    assert FB.fighter_types(OPTS, "savasku") == ["drone"]


# ---- Validation ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("arcs", "ok"),
    [(["FP", "F", "FS"], True), (["F", "FS", "AS"], True), (["AP", "A", "AS"], True),
     (["F", "FS"], False), (["F", "FS", "AS", "A"], False), (["F", "AS", "AP"], False)],
)
def test_stinger_covers_three_adjacent_arcs(arcs, ok):
    d = design(systems=[sys_("s", "stinger", arcs=arcs)])
    codes = {i.code for i in FB.validate_design(d, OPTS) if i.severity == "violation"}
    assert ("stinger_arcs" in codes) is not ok


def test_pod_launcher_is_single_arc():
    bad = design(systems=[sys_("p", "pod_launcher", arcs=["F", "FS"])])
    assert "pod_arcs" in {i.code for i in FB.validate_design(bad, OPTS)}


def test_a_thrust_rating_is_a_violation():
    """Sa'Vasku buy thrust per turn out of the M pool; there is no design-time rating."""
    assert "sv_thrust" in {i.code for i in FB.validate_design(design(thrust=4), OPTS)}
    assert "sv_thrust" not in {i.code for i in FB.validate_design(design(thrust=0), OPTS)}


@pytest.mark.parametrize("stype", ["beam", "kgun", "screen", "pds", "scattergun", "hangar"])
def test_other_races_systems_are_refused(stype):
    d = design(systems=[sys_("s", stype)])
    assert "race_system" in {i.code for i in FB.validate_design(d, OPTS) if i.severity == "violation"}


def test_savasku_systems_are_not_available_to_humans_or_kravak():
    for race in ("human", "kravak"):
        d = design(race=race, systems=[sys_("s", "stinger", arcs=["FP", "F", "FS"])])
        codes = {i.code for i in FB.validate_design(d, OPTS) if i.severity == "violation"}
        assert codes & {"unknown_system", "race_system"}, race


def test_biomass_minimum_is_ten_percent():
    d = design(tmf=100, hull_boxes=9)
    assert "biomass_below_minimum" in {i.code for i in FB.validate_design(d, OPTS)}


def test_a_womb_holds_one_drone_group():
    d = design(
        systems=[sys_("w", "drone_womb")],
        default_loadout={"fighters": [{"hangar": "w", "type": "drone"},
                                      {"hangar": "w", "type": "drone"}], "magazines": []},
    )
    assert "hangar_overfull" in {i.code for i in FB.validate_design(d, OPTS)}


def test_picker_offers_savasku_nodes_only():
    types = {s.type for s in FB.system_types("savasku", OPTS)}
    assert {"power_generator", "stinger", "pod_launcher", "spicule", "cortex", "screen_node",
            "drone_womb"} == types


def test_races_now_lists_three():
    assert [r.id for r in FB.races()] == ["human", "kravak", "savasku"]
    assert FB.icon_set_for("savasku") == "fb_savasku"


def test_malformed_design_never_raises():
    d = design(tmf="x", hull_boxes=None, armour={}, systems=[{"uid": "g", "type": "power_generator"}, 7])
    FB.design_breakdown(d, OPTS)
    FB.validate_design(d, OPTS)
