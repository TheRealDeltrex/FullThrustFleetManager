"""The SSD layout engine (PLAN 10.1): placement, damage state, and SVG snapshots.

Snapshots are regenerated with:
    .venv/Scripts/python.exe tests/test_ssd_layout.py --update
Read the diff before committing one: a changed snapshot means every record sheet changed.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest
from conftest import ROOT

import ssd_layout
import store
from rulesets import RULESETS

SNAPSHOTS = Path(__file__).parent / "snapshots"
REFERENCE = [
    "fb:fb1:nac-furious",       # mixed arcs, torpedo, screens
    "fb:fb1:nac-vandenburg",    # bigger beam battery
    "fb:fb1:nac-ark-royal",     # carrier: hangars and a wide track
    "ft2:ft:courier",           # the smallest FT2 hull
    "ft2:ft:battleship",        # four-arc capital ship
    "ft2:ft:bulk-tanker",       # merchant: holds and a tug drive
    "fb:fb2:kv-lo-vok",         # Kra'Vak: hexagon icons, scatterguns, the advanced drive
    "fb:fb2:kv-to-rok",         # Kra'Vak non-combatant: lab space and a tender bay
    "fb:fb2:sv-vas-sa-rosh",    # Sa'Vasku: generators on the track, thrust table, power box
    "fb:fb2:sv-sa-an-tha",      # the smallest Sa'Vasku construct
    "fb:fb2:ph-voth",           # Phalon: a four-layer shell, pulser stars, plasma bolts
    "fb:fb2:ph-phyaa",          # the smallest Phalon hull, one shell layer
]


def test_a_phalon_shell_draws_one_row_per_layer_outermost_on_top():
    """FB2 p.35: the layers stack with the inner one nearest the hull, so the sheet draws the
    outermost at the top. The Voth's shell is 16/10/8/6 from the inside out."""
    d = design("fb:fb2:ph-voth")
    assert d["armour_layers"] == [16, 10, 8, 6] and d["armour"] == 40
    circles = [p for p in ssd_layout.layout(d, RULESETS["fb"]).primitives
               if p.kind == "circle" and p.ref.startswith("armour:")]
    rows: dict[float, int] = {}
    for c in circles:
        rows[round(c.cy, 1)] = rows.get(round(c.cy, 1), 0) + 1
    assert [n for _y, n in sorted(rows.items())] == [6, 8, 10, 16]


def test_shell_boxes_are_numbered_in_the_order_damage_removes_them():
    """Shell boxes are crossed off the outermost layer first (FB2 p.35), so box 1 is the first
    box of the top row - which is what the campaign tab's armour counter marks off."""
    d = design("fb:fb2:ph-voth")
    circles = [p for p in ssd_layout.layout(d, RULESETS["fb"]).primitives
               if p.kind == "circle" and p.ref.startswith("armour:")]
    first = min(circles, key=lambda c: int(c.ref.split(":")[1]))
    assert first.cy == min(c.cy for c in circles)


def test_a_single_layer_shell_draws_as_one_row():
    d = design("fb:fb2:ph-phyaa")
    assert d["armour_layers"] == [1]
    circles = [p for p in ssd_layout.layout(d, RULESETS["fb"]).primitives
               if p.kind == "circle" and p.ref.startswith("armour:")]
    assert len(circles) == 1


def test_a_pulser_carries_its_configured_letter():
    """The star's centre is the blank the player writes L, M or C into (FB2 p.35); an unset
    battery stays blank, as the printed sheets do."""
    d = design("fb:fb2:ph-phyaa")
    uid = next(s["uid"] for s in d["systems"] if s["type"] == "pulser")
    blank = [getattr(p, "text", "") for p in ssd_layout.layout(d, RULESETS["fb"]).primitives]
    assert "M" not in blank
    loadout = {"fighters": [], "magazines": [], "pulsers": [{"pulser": uid, "mode": "M"}]}
    set_ = [getattr(p, "text", "")
            for p in ssd_layout.layout(d, RULESETS["fb"], loadout=loadout).primitives]
    assert "M" in set_


def test_human_armour_is_unaffected_by_the_layer_code():
    d = design("fb:fb1:nac-furious")
    circles = [p for p in ssd_layout.layout(d, RULESETS["fb"]).primitives
               if p.kind == "circle" and p.ref.startswith("armour:")]
    assert len(circles) == d["armour"] == 3


def test_savasku_sheets_carry_the_play_aids_the_book_prints():
    """FB2 p.22 puts a thrust table on every Sa'Vasku SSD, and the record chart (p.33) a power
    allocation grid; neither is design data, both are drawn from derived values."""
    d = design("fb:fb2:sv-vas-sa-rosh")
    prims = ssd_layout.layout(d, RULESETS["fb"]).primitives
    texts = [getattr(p, "text", "") for p in prims]
    assert "Thrust / power" in texts
    assert [t for t in texts if t in ("M", "A", "D", "R")] == ["M", "A", "D", "R"]
    assert "Power 40 per turn" in texts
    # The four power generators sit at the ends of the damage-track rows (FB2 p.22).
    assert texts.count("10") == 4


def test_a_savasku_sheet_has_no_core_systems_box():
    """A construct has no bridge, life support or power core, and the FB2 p.25 key shows no
    such box - unlike the human and Kra'Vak FB sheets, which both have one."""
    sv = [getattr(p, "text", "") for p in
          ssd_layout.layout(design("fb:fb2:sv-sa-an-tha"), RULESETS["fb"]).primitives]
    kv = [getattr(p, "text", "") for p in
          ssd_layout.layout(design("fb:fb2:kv-lo-vok"), RULESETS["fb"]).primitives]
    assert "B" not in sv and "L" not in sv and "P" not in sv
    assert "B" in kv and "L" in kv and "P" in kv


def test_a_savasku_drive_is_a_star_and_carries_no_rating():
    """FB2 p.22: "there is a star rather than a thrust number printed in the drive icon"."""
    d = design("fb:fb2:sv-sa-an-tha")
    prims = ssd_layout.layout(d, RULESETS["fb"]).primitives
    assert d["thrust"] == 0
    # The Kra'Vak drive writes its rating ("4A"); this one writes no rating at all.
    assert not [p for p in prims if re.fullmatch(r"\d+A", getattr(p, "text", ""))]
    assert ssd_layout.ICON_SETS["fb_savasku"]["main_drive"] is not ssd_layout.ICON_SETS[
        "fb_kravak"
    ]["main_drive"]


def test_generators_follow_the_rows_a_small_construct_actually_has():
    """The Sa'Kess'Tha has 2 biomass, so two damage rows, and prints its 3 power as 1 and 2
    rather than four generators with two of them zero (FB2 p.26)."""
    prims = ssd_layout.layout(design("fb:fb2:sv-sa-kess-tha"), RULESETS["fb"]).primitives
    # A generator's value is the white-on-black number on its cog; nothing else on the sheet is.
    assert [p.text for p in prims if getattr(p, "fill", "") == "white" and p.kind == "text"] == [
        "1", "2"
    ]


def test_pod_launcher_arrows_point_along_their_arc():
    """The Vas'Sa'Rosh is the one ship whose three launchers do not all bear fore (FB2 p.32)."""
    import math
    import re

    d = design("fb:fb2:sv-vas-sa-rosh")
    prims = ssd_layout.layout(d, RULESETS["fb"]).primitives
    seen = {}
    for system in (s for s in d["systems"] if s["type"] == "pod_launcher"):
        own = [p for p in prims if getattr(p, "ref", "") == f"system:{system['uid']}"]
        disc = next(p for p in own if p.kind == "circle")
        arrow = next(p for p in own if p.kind == "path" and p.fill == "black" and p.d.count("L") == 2)
        x, y = (float(v) for v in re.findall(r"-?\d+\.?\d*", arrow.d)[:2])
        seen[system["arcs"][0]] = round(math.degrees(math.atan2(y - disc.cy, x - disc.cx)))
    assert seen == {"F": -90, "FP": -150, "FS": -30}


def test_kravak_designs_use_the_fb2_icon_set():
    """A Kra'Vak sheet is drawn with FB2's hexagons, not Fleet Book 1's circles and boxes, and
    nothing on it falls back to a labelled box (PLAN decision 10)."""
    d = design("fb:fb2:kv-lo-vok")
    types = {s["type"] for s in d["systems"]}
    assert types <= set(ssd_layout.ICON_SETS["fb_kravak"])
    # The race's own weapons exist only in its set; the human sheet would fall back to a box.
    assert not {"kgun", "mkp", "scattergun"} & set(ssd_layout.ICON_SETS["fb"])
    assert ssd_layout.ICON_SETS["fb_kravak"]["fire_control"] is not ssd_layout.ICON_SETS["fb"][
        "fire_control"
    ]
    prims = ssd_layout.layout(d, RULESETS["fb"]).primitives
    # The advanced drive is a hexagon reading "4A", never the human lozenge (FB2 p.9).
    assert any(getattr(p, "text", "") == "4A" for p in prims)


def test_human_designs_keep_the_fb1_icon_set():
    d = design("fb:fb1:nac-furious")
    prims = ssd_layout.layout(d, RULESETS["fb"]).primitives
    assert any(getattr(p, "text", "") == "4" for p in prims)  # plain thrust, no "A"


def design(design_id: str) -> dict:
    d = store.get_design(design_id)
    assert d, design_id
    return d


# ---- Placement ---------------------------------------------------------------------------------


def beam_positions(d) -> list[tuple[float, float]]:
    """(x, y) of each beam icon: the class circle, radius 8."""
    return [(p.cx, p.cy) for p in ssd_layout.layout(d).primitives
            if isinstance(p, ssd_layout.Circle) and p.r == 8.0]


def test_fore_weapons_sit_above_aft_weapons():
    d = design("fb:fb1:nac-furious")
    d["systems"] = [
        {"uid": "a", "type": "beam", "class": 3, "arcs": ["A"]},
        {"uid": "f", "type": "beam", "class": 3, "arcs": ["F"]},
    ]
    fore, aft = beam_positions(d)  # placement order, not systems order
    assert fore[1] < aft[1]


@pytest.mark.parametrize("arcs,side", [
    (["F"], "fore"),
    (["FP", "F", "FS"], "fore"),
    (["A"], "aft"),
    (["FP", "AP"], "port"),
    (["FS", "AS"], "starboard"),
    (["F", "FS", "AS", "A", "AP", "FP"], "centre"),
    ([], "centre"),
])
def test_arc_sides_fb(arcs, side):
    assert ssd_layout._side(arcs, RULESETS["fb"].arcs) == side


@pytest.mark.parametrize("arcs,side", [
    (["F"], "fore"), (["A"], "aft"), (["P"], "port"), (["S"], "starboard"),
    (["F", "S", "A", "P"], "centre"),
])
def test_arc_sides_ft2(arcs, side):
    assert ssd_layout._side(arcs, RULESETS["ft2"].arcs) == side


def test_port_and_starboard_batteries_flank_the_centre():
    d = design("fb:fb1:nac-furious")
    d["systems"] = [
        {"uid": "p", "type": "beam", "class": 2, "arcs": ["FP", "AP"]},
        {"uid": "s", "type": "beam", "class": 2, "arcs": ["FS", "AS"]},
    ]
    circles = [p for p in ssd_layout.layout(d).primitives if isinstance(p, ssd_layout.Circle)]
    xs = sorted(c.cx for c in circles)
    assert xs[0] < ssd_layout.BOX_WIDTHS["medium"] / 2 < xs[-1]


def test_larger_classes_sit_nearer_the_top():
    d = design("fb:fb1:nac-furious")
    d["systems"] = [
        {"uid": "small", "type": "beam", "class": 1, "arcs": ["F"]},
        {"uid": "big", "type": "beam", "class": 4, "arcs": ["F"]},
    ]
    big, small = beam_positions(d)  # the class-4 battery is placed first
    assert big[1] <= small[1]


def test_layout_hints_pin_a_system():
    d = design("fb:fb1:nac-furious")
    d["systems"] = [{"uid": "b", "type": "beam", "class": 1, "arcs": ["F"]}]
    d["layout_hints"] = {"b": {"x": 5, "y": 7}}
    circle = next(p for p in ssd_layout.layout(d).primitives if isinstance(p, ssd_layout.Circle))
    assert (circle.cx, circle.cy) == (5, 7)


def test_an_unknown_system_type_still_draws():
    d = design("fb:fb1:nac-furious")
    d["systems"] = [{"uid": "x", "type": "quantum_widget"}]
    texts = [p.text for p in ssd_layout.layout(d).primitives if isinstance(p, ssd_layout.Text)]
    assert "QUAN" in texts


def test_a_design_of_an_unknown_ruleset_yields_an_empty_diagram():
    assert ssd_layout.layout({"ruleset": "nope"}) == ssd_layout.Diagram(0, 0, ())


# ---- Track and bottom row ----------------------------------------------------------------------


def test_damage_track_boxes_match_the_ruleset():
    for design_id in ("fb:fb1:nac-furious", "ft2:ft:battleship"):
        d = design(design_id)
        rs = RULESETS[d["ruleset"]]
        boxes = [p for p in ssd_layout.layout(d).primitives if isinstance(p, ssd_layout.Rect)]
        square = [p for p in boxes if abs(p.w - p.h) < 0.01 and p.w <= 11.0]
        assert len(square) >= sum(rs.damage_track(d))


def test_crew_factor_stars_are_drawn_once_per_position():
    d = design("fb:fb1:nac-vandenburg")
    rs = RULESETS["fb"]
    stars = [p for p in ssd_layout.layout(d).primitives
             if isinstance(p, ssd_layout.Path) and p.fill == "black" and p.d.count("L") == 9]
    assert len(stars) == len(rs.cf_positions(d))


def core_boxes(design_id: str) -> list[str]:
    """The three reversed-out core system letters of an FB sheet (bridge, life support, power)."""
    prims = ssd_layout.layout(design(design_id)).primitives
    return [p.text for p in prims if isinstance(p, ssd_layout.Text) and p.fill == "white"]


def test_ft2_has_no_core_systems_box_and_fb_does():
    assert core_boxes("fb:fb1:nac-furious") == ["B", "L", "P"]
    assert core_boxes("ft2:ft:battleship") == []


def test_ftl_and_thrust_are_on_the_bottom_row():
    d = design("fb:fb1:nac-furious")
    texts = {p.text for p in ssd_layout.layout(d).primitives if isinstance(p, ssd_layout.Text)}
    assert "FTL" in texts and str(d["thrust"]) in texts
    d["ftl"] = False
    assert "FTL" not in {p.text for p in ssd_layout.layout(d).primitives
                         if isinstance(p, ssd_layout.Text)}


# ---- Damage state -------------------------------------------------------------------------------


def _crosses(diagram) -> int:
    return sum(1 for p in diagram.primitives
               if isinstance(p, ssd_layout.Path) and p.stroke == ssd_layout.CROSS)


def _slashes(diagram) -> int:
    return sum(1 for p in diagram.primitives
               if isinstance(p, ssd_layout.Path) and p.stroke == 1.5)


def test_damage_marks_hull_armour_systems_and_drive():
    d = design("fb:fb1:nac-vandenburg")
    blank = ssd_layout.layout(d)
    assert _crosses(blank) == 0 and _slashes(blank) == 0

    out = d["systems"][0]["uid"]
    damaged = ssd_layout.layout(d, damage={"hull": 4, "armour": 2, "systems_out": [out],
                                           "drive_hits": 1})
    assert _slashes(damaged) == 6            # 4 hull boxes + 2 armour circles
    assert _crosses(damaged) == 2            # the dead system and the damaged drive


def test_a_blank_copy_ignores_campaign_damage():
    d = design("fb:fb1:nac-vandenburg")
    assert ssd_layout.layout(d, damage=None) == ssd_layout.layout(d, damage={})


# ---- Size bands and SVG --------------------------------------------------------------------------


def test_box_sizes_grow_with_the_ship():
    assert ssd_layout.box_size(design("ft2:ft:courier")) == "small"
    assert ssd_layout.box_size(design("fb:fb1:nac-vandenburg")) in ("medium", "large")
    assert ssd_layout.BOX_WIDTHS["small"] < ssd_layout.BOX_WIDTHS["xlarge"]
    d = design("ft2:ft:courier")
    assert ssd_layout.layout(d, box="large").width == ssd_layout.BOX_WIDTHS["large"]


def test_svg_is_well_formed_and_escapes_text():
    d = design("fb:fb1:nac-furious")
    svg = ssd_layout.to_svg(ssd_layout.layout(d))
    assert svg.startswith("<svg viewBox=") and svg.endswith("</svg>")
    assert "<text" in svg and "<circle" in svg
    d["systems"] = [{"uid": "x", "type": "a&b<c"}]
    assert "&amp;" in ssd_layout.to_svg(ssd_layout.layout(d))


def test_every_catalog_design_fits_inside_its_box():
    """A sheet that draws outside its own box overlaps its neighbour in the packed PDF."""
    for d in store.catalog_designs():
        diagram = ssd_layout.layout(d)
        xs: list[float] = []
        ys: list[float] = []
        for p in diagram.primitives:
            if isinstance(p, ssd_layout.Rect):
                xs += [p.x, p.x + p.w]
                ys += [p.y, p.y + p.h]
            elif isinstance(p, ssd_layout.Circle):
                xs += [p.cx - p.r, p.cx + p.r]
                ys += [p.cy - p.r, p.cy + p.r]
            elif isinstance(p, ssd_layout.Line):
                xs += [p.x1, p.x2]
                ys += [p.y1, p.y2]
            elif isinstance(p, ssd_layout.Text):
                xs.append(p.x)
                ys.append(p.y)
        assert min(xs) >= -1 and max(xs) <= diagram.width + 1, d["id"]
        assert max(ys) <= diagram.height + 1, d["id"]


# ---- Snapshots -----------------------------------------------------------------------------------


def snapshot_path(design_id: str) -> Path:
    return SNAPSHOTS / (design_id.replace(":", "_") + ".svg")


@pytest.mark.parametrize("design_id", REFERENCE)
def test_reference_ships_match_their_snapshot(design_id):
    svg = ssd_layout.to_svg(ssd_layout.layout(design(design_id)))
    path = snapshot_path(design_id)
    assert path.is_file(), "run: python tests/test_ssd_layout.py --update"
    assert svg == path.read_text(encoding="utf-8"), f"layout changed for {design_id}"


def _update() -> None:
    SNAPSHOTS.mkdir(exist_ok=True)
    for design_id in REFERENCE:
        snapshot_path(design_id).write_text(
            ssd_layout.to_svg(ssd_layout.layout(design(design_id))), encoding="utf-8"
        )
        print("wrote", snapshot_path(design_id).name)


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    if "--update" in sys.argv:
        _update()
    else:
        print(json.dumps(REFERENCE, indent=1))
