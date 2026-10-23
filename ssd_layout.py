"""Ship diagram (SSD) layout: design -> drawing primitives (PLAN 10.1).

Pure and side-effect free. `layout()` returns a `Diagram` of primitives in a top-left origin
coordinate system, in points (1 pt = 1/72 in), so the same numbers serve the screen (SVG, via
`to_svg()`) and the paper (fpdf2, M9): screen = paper.

Icons come from the ruleset's icon set for the design's race (`icon_set_for(race)`, falling back
to the `icon_set` attribute), so an FT2 sheet looks like the FT book, a human FB sheet like Fleet
Book 1 and a Kra'Vak one like Fleet Book 2 (FT p.14 / FB1 p.12 / FB2 p.11 keys). The tables live
here rather than in the rulesets because drawing is a consumer's job; a ruleset only names its
set.

Placement is arc-aware (PLAN 10.1): fore weapons top centre, port-covering ones in a left
column, starboard-covering in a right column, aft-only at the bottom, all-round systems in a
central row, larger classes nearer the top. A design's `layout_hints` may pin any system to a
position; the catalog may ship them and drag-to-arrange can write them later.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field, replace
from typing import Literal

from i18n import _
from rulesets import RULESETS

# ---- Primitives ---------------------------------------------------------------------------------


@dataclass(frozen=True)
class Rect:
    x: float
    y: float
    w: float
    h: float
    r: float = 0.0  # corner radius
    fill: str = "none"
    stroke: float = 0.9
    ref: str = ""  # what a click on this shape means (campaign tab)
    kind: str = "rect"


@dataclass(frozen=True)
class Circle:
    cx: float
    cy: float
    r: float
    fill: str = "none"
    stroke: float = 0.9
    ref: str = ""  # what a click on this shape means (campaign tab)
    kind: str = "circle"


@dataclass(frozen=True)
class Line:
    x1: float
    y1: float
    x2: float
    y2: float
    stroke: float = 0.9
    ref: str = ""  # what a click on this shape means (campaign tab)
    kind: str = "line"


@dataclass(frozen=True)
class Path:
    d: str
    fill: str = "none"
    stroke: float = 0.9
    ref: str = ""  # what a click on this shape means (campaign tab)
    kind: str = "path"


@dataclass(frozen=True)
class Text:
    x: float
    y: float
    text: str
    size: float = 8.0
    anchor: Literal["start", "middle", "end"] = "middle"
    bold: bool = False
    fill: str = "black"
    ref: str = ""  # what a click on this shape means (campaign tab)
    kind: str = "text"


Primitive = Rect | Circle | Line | Path | Text


@dataclass(frozen=True)
class Diagram:
    width: float
    height: float
    primitives: tuple[Primitive, ...] = field(default_factory=tuple)
    # uid -> (x, y): where each system's icon is centred, for drag-to-arrange.
    anchors: dict[str, tuple[float, float]] = field(default_factory=dict, compare=False)
    # The x the visible sheet starts at: a sheet is cropped to what it draws, so `width` runs
    # from here (pinned positions keep the coordinates of the uncropped box).
    left: float = 0.0


# ---- Geometry helpers ---------------------------------------------------------------------------

BLACK, WHITE, NONE = "black", "white", "none"
CROSS = 2.0  # stroke of a damage cross; black on paper (PLAN 10.1)


def _fmt(v: float) -> str:
    return f"{round(v, 2):g}"


def _star(cx: float, cy: float, r: float) -> Path:
    points = []
    for i in range(10):
        angle = -math.pi / 2 + i * math.pi / 5
        rr = r * (0.45 if i % 2 else 1.0)
        px, py = cx + rr * math.cos(angle), cy + rr * math.sin(angle)
        points.append(("L" if i else "M") + f"{_fmt(px)} {_fmt(py)}")
    return Path("".join(points) + "Z", fill=BLACK, stroke=0)


def _cross(cx: float, cy: float, r: float) -> Path:
    return Path(
        f"M{_fmt(cx - r)} {_fmt(cy - r)} L{_fmt(cx + r)} {_fmt(cy + r)} "
        f"M{_fmt(cx + r)} {_fmt(cy - r)} L{_fmt(cx - r)} {_fmt(cy + r)}",
        stroke=CROSS,
    )


def _slash(x: float, y: float, size: float) -> Path:
    """The single stroke that marks off a damage box or armour circle."""
    return Path(f"M{_fmt(x + 1.2)} {_fmt(y + size - 1.2)} L{_fmt(x + size - 1.2)} {_fmt(y + 1.2)}",
                stroke=1.5)


def _arc_ring(cx: float, cy: float, r: float, arcs: list[str], all_arcs: tuple[str, ...]) -> list[Primitive]:
    """The book's arc ring: every arc drawn thin, the covered ones heavy (FB1 p.12, FT p.14)."""
    out: list[Primitive] = []
    span = 360.0 / len(all_arcs)
    for i, name in enumerate(all_arcs):
        centre = -90.0 + i * span  # index 0 is fore, clockwise (SVG y grows downwards)
        a0 = math.radians(centre - span * 0.45)
        a1 = math.radians(centre + span * 0.45)
        covered = name in arcs
        # Sampled as a polyline rather than an SVG "A" command: the PDF renderer draws the very
        # same points, so screen and paper cannot drift apart.
        steps = 8
        points = []
        for step in range(steps + 1):
            angle = a0 + (a1 - a0) * step / steps
            points.append(("L" if step else "M")
                          + f"{_fmt(cx + r * math.cos(angle))} {_fmt(cy + r * math.sin(angle))}")
        out.append(Path(" ".join(points), stroke=2.4 if covered else 0.5))
    return out


# ---- Icons ---------------------------------------------------------------------------------------
#
# An icon function draws one system centred on (x, y) and returns its primitives; ICON_RADIUS is
# the space it claims. Anything not in a set falls back to a labelled box, so a new system type
# never breaks a sheet.

ICON_RADIUS = 13.0
WIDE_RADIUS = 18.0


def _beam(system: dict, x: float, y: float, arcs: tuple[str, ...]) -> list[Primitive]:
    cls = system.get("class", 1)
    return [
        Circle(x, y, 8.0, fill=WHITE, stroke=1.3),
        Text(x, y + 3.2, str(cls), size=9.5, bold=True),
        *_arc_ring(x, y, 11.5, system.get("arcs", []), arcs),
    ]


def _torpedo(system: dict, x: float, y: float, arcs: tuple[str, ...]) -> list[Primitive]:
    return [
        Circle(x, y, 8.0, fill=WHITE, stroke=1.3),
        Path(f"M{_fmt(x - 4)} {_fmt(y + 4)} L{_fmt(x)} {_fmt(y - 5)} L{_fmt(x + 4)} {_fmt(y + 4)} Z",
             fill=BLACK, stroke=0),
        *_arc_ring(x, y, 11.5, system.get("arcs", []), arcs),
    ]


def _needle(system: dict, x: float, y: float, arcs: tuple[str, ...]) -> list[Primitive]:
    return [
        Circle(x, y, 8.0, fill=WHITE, stroke=1.3),
        Line(x - 5, y, x + 5, y, stroke=1.6),
        *_arc_ring(x, y, 11.5, system.get("arcs", []), arcs),
    ]


def _big_gun(letter: str):
    def draw(system: dict, x: float, y: float, arcs: tuple[str, ...]) -> list[Primitive]:
        return [
            Circle(x, y, 9.0, fill=WHITE, stroke=1.6),
            Text(x, y + 3.4, letter, size=9.5, bold=True),
            *_arc_ring(x, y, 12.5, system.get("arcs", []), arcs),
        ]
    return draw


def _launcher(system: dict, x: float, y: float, arcs: tuple[str, ...]) -> list[Primitive]:
    return [
        Rect(x - 7, y - 7, 14, 14, fill=WHITE, stroke=1.2),
        Path(f"M{_fmt(x - 4)} {_fmt(y + 4)} L{_fmt(x)} {_fmt(y - 5)} L{_fmt(x + 4)} {_fmt(y + 4)} Z",
             fill=BLACK, stroke=0),
    ]


def _rack(system: dict, x: float, y: float, arcs: tuple[str, ...]) -> list[Primitive]:
    load = "ER" if system.get("load") == "er" else "S"
    return [
        Rect(x - 8, y - 7, 16, 14, fill=WHITE, stroke=1.2),
        Text(x, y + 3.2, load, size=7.5, bold=True),
    ]


def _magazine(system: dict, x: float, y: float, arcs: tuple[str, ...]) -> list[Primitive]:
    """Salvo boxes, one per salvo the magazine holds (2 MASS each)."""
    salvos = max(1, int(system.get("capacity", 2) or 2) // 2)
    box, per_row = 7.0, 8  # a big magazine wraps into rows rather than running off the sheet
    across = min(salvos, per_row)
    rows = math.ceil(salvos / per_row)
    left = x - across * box / 2
    top = y - (rows - 1) * 4.5
    out: list[Primitive] = [Rect(left - 2, top - 7, across * box + 4, 14 + (rows - 1) * 9,
                                 fill=WHITE, stroke=1.2)]
    for i in range(salvos):
        cx = left + (i % per_row) * box + box / 2
        cy = top + (i // per_row) * 9
        out.append(Path(f"M{_fmt(cx - 2.4)} {_fmt(cy + 3)} L{_fmt(cx)} {_fmt(cy - 3)} "
                        f"L{_fmt(cx + 2.4)} {_fmt(cy + 3)} Z", fill=WHITE, stroke=0.8))
    return out


def _pds(system: dict, x: float, y: float, arcs: tuple[str, ...]) -> list[Primitive]:
    return [
        Circle(x, y, 6.5, fill=WHITE, stroke=1.2),
        Path(f"M{_fmt(x - 4.5)} {_fmt(y - 4.5)} L{_fmt(x + 4.5)} {_fmt(y + 4.5)} "
             f"M{_fmt(x + 4.5)} {_fmt(y - 4.5)} L{_fmt(x - 4.5)} {_fmt(y + 4.5)}", stroke=1.1),
    ]


def _fire_control(system: dict, x: float, y: float, arcs: tuple[str, ...]) -> list[Primitive]:
    return [Rect(x - 6, y - 6, 12, 12, fill=WHITE, stroke=1.2), Circle(x, y, 2.4, fill=BLACK, stroke=0)]


def _area_fc(system: dict, x: float, y: float, arcs: tuple[str, ...]) -> list[Primitive]:
    return [
        Rect(x - 6, y - 6, 12, 12, fill=WHITE, stroke=1.2),
        Circle(x, y, 3.6, stroke=0.9),
        Circle(x, y, 1.3, fill=BLACK, stroke=0),
    ]


def _screen(system: dict, x: float, y: float, arcs: tuple[str, ...]) -> list[Primitive]:
    level = max(1, min(3, int(system.get("level", 1) or 1)))
    out: list[Primitive] = []
    for i in range(level):
        out.append(Rect(x - 3 + i * 7 - (level - 1) * 3.5, y - 8, 6, 16, r=2, fill=WHITE, stroke=1.2))
    return out


def _hangar(system: dict, x: float, y: float, arcs: tuple[str, ...]) -> list[Primitive]:
    return [
        Rect(x - 10, y - 7, 20, 14, r=3, fill=WHITE, stroke=1.2),
        Path(f"M{_fmt(x - 5)} {_fmt(y + 3)} L{_fmt(x)} {_fmt(y - 4)} L{_fmt(x + 5)} {_fmt(y + 3)} "
             f"L{_fmt(x)} {_fmt(y + 1)} Z", fill=BLACK, stroke=0),
    ]


def _submunition(system: dict, x: float, y: float, arcs: tuple[str, ...]) -> list[Primitive]:
    return [
        Rect(x - 6, y - 6, 12, 12, fill=WHITE, stroke=1.2),
        Path(f"M{_fmt(x - 3)} {_fmt(y)} L{_fmt(x + 3)} {_fmt(y)} "
             f"M{_fmt(x)} {_fmt(y - 3)} L{_fmt(x)} {_fmt(y + 3)}", stroke=1.4),
    ]


def _labelled(text, wide: bool = False):
    """A boxed abbreviation. `text` is a callable so the label is translated at draw time."""
    def draw(system: dict, x: float, y: float, arcs: tuple[str, ...]) -> list[Primitive]:
        w = 26.0 if wide else 16.0
        label = text() if callable(text) else text
        return [Rect(x - w / 2, y - 7, w, 14, fill=WHITE, stroke=1.2),
                Text(x, y + 3.0, label, size=7, bold=True)]
    return draw


def _gate(text):
    """A gate or portal drive, CD p.35: the FTL box widened to carry its transfer MASS, as the
    tug drive of figure 23 carries its own."""
    def draw(system: dict, x: float, y: float, arcs: tuple[str, ...]) -> list[Primitive]:
        mass = system.get("transfer_mass", 0)
        return [Rect(x - 17, y - 7, 34, 14, fill=WHITE, stroke=1.2),
                Text(x, y + 3.0, f"{text()} {mass}", size=7, bold=True)]
    return draw


_SHARED_ICONS = {
    "beam": _beam,
    "pulse_torpedo": _torpedo,
    "needle_beam": _needle,
    "nova_cannon": _big_gun("N"),
    "wave_gun": _big_gun("W"),
    "aa_battery": _big_gun("AA"),
    "sm_launcher": _launcher,
    "sm_rack": _rack,
    "sm_magazine": _magazine,
    "submunition": _submunition,
    "pds": _pds,
    "pdaf": _pds,
    "adaf": _area_fc,
    "fire_control": _fire_control,
    "adfc": _area_fc,
    "screen": _screen,
    "hangar": _hangar,
    "fighter_group": _hangar,
    "tender_bay": _labelled(lambda: _("TEN")),
    "minelayer": _labelled(lambda: _("MINE")),
    "minesweeper": _labelled(lambda: _("SWP")),
    "mt_missile": _labelled(lambda: _("MSL")),
    "ortillery": _labelled(lambda: _("ORT")),
    "reflex_field": _labelled(lambda: _("RFX")),
    "cloak": _labelled(lambda: _("CLK")),
    "tug_drive": _labelled(lambda: _("TUG")),
    "jump_gate": _gate(lambda: _("GATE")),
    "portal": _gate(lambda: _("PORT")),
    "hold": _labelled(lambda: _("HOLD"), wide=True),
}

# ---- Kra'Vak icons (FB2 p.11 key) -------------------------------------------------------------
#
# The Kra'Vak sheet is drawn with hexagons, not the human circles and boxes. On the printed SSD
# the hexagon's fill IS the arc information: an outline hexagon is an all-arc (class-1) K-gun and
# a filled one bears through a single arc. We keep that, and add the arc ring under a single-arc
# gun, because this app lets a designer point it anywhere while the book only ever prints fore.


def _hexagon(cx: float, cy: float, r: float) -> str:
    """Flat-topped hexagon path, the shape FB2 uses for every Kra'Vak weapon."""
    points = []
    for i in range(6):
        angle = math.radians(-90 + i * 60)
        points.append(("L" if i else "M")
                      + f"{_fmt(cx + r * math.cos(angle))} {_fmt(cy + r * math.sin(angle))}")
    return " ".join(points) + " Z"


def _kgun(system: dict, x: float, y: float, arcs: tuple[str, ...]) -> list[Primitive]:
    cls = system.get("class", 1)
    covered = system.get("arcs", []) or []
    all_round = len(covered) >= len(arcs)
    return [
        Path(_hexagon(x, y, 8.5), fill=WHITE if all_round else BLACK, stroke=1.3),
        Text(x, y + 3.2, str(cls), size=9.5, bold=True, fill=BLACK if all_round else WHITE),
        *([] if all_round else _arc_ring(x, y, 12.0, covered, arcs)),
    ]


def _mkp(system: dict, x: float, y: float, arcs: tuple[str, ...]) -> list[Primitive]:
    """One-shot: the book crosses the icon through once fired (FB2 p.9)."""
    return [
        Path(_hexagon(x, y, 8.5), fill=WHITE, stroke=1.3),
        Path(f"M{_fmt(x - 4.5)} {_fmt(y - 4)} L{_fmt(x + 4.5)} {_fmt(y - 4)} "
             f"L{_fmt(x)} {_fmt(y + 5)} Z", fill=BLACK, stroke=0),
        *_arc_ring(x, y, 12.0, system.get("arcs", []), arcs),
    ]


def _scattergun(system: dict, x: float, y: float, arcs: tuple[str, ...]) -> list[Primitive]:
    return [
        Path(_hexagon(x, y, 7.5), fill=BLACK, stroke=1.0),
        Path(f"M{_fmt(x - 4)} {_fmt(y + 3.5)} L{_fmt(x)} {_fmt(y - 4.5)} "
             f"L{_fmt(x + 4)} {_fmt(y + 3.5)} Z", fill=WHITE, stroke=0),
    ]


def _kv_fire_control(system: dict, x: float, y: float, arcs: tuple[str, ...]) -> list[Primitive]:
    return [Circle(x, y, 5.5, fill=WHITE, stroke=1.2), Circle(x, y, 2.2, fill=BLACK, stroke=0)]


def _kv_hangar(system: dict, x: float, y: float, arcs: tuple[str, ...]) -> list[Primitive]:
    return [Path(f"M{_fmt(x - 7)} {_fmt(y + 8)} L{_fmt(x)} {_fmt(y - 8)} "
                 f"L{_fmt(x + 7)} {_fmt(y + 8)} Z", fill=WHITE, stroke=1.3)]


def _kv_drive(system: dict, x: float, y: float, arcs: tuple[str, ...]) -> list[Primitive]:
    """FB2 p.9: a different icon from the human drive, and the rating is written "4A"."""
    return [
        Path(_hexagon(x, y, 11.0), fill=WHITE, stroke=1.3),
        Text(x, y + 3.4, _("{n}A", n=system.get("thrust", 0)), size=9.5, bold=True),
    ]


_KRAVAK_ICONS = dict(_SHARED_ICONS) | {
    "main_drive": _kv_drive,
    "kgun": _kgun,
    "mkp": _mkp,
    "scattergun": _scattergun,
    "fire_control": _kv_fire_control,
    "hangar": _kv_hangar,
}

# ---- Sa'Vasku icons (FB2 p.25 key) -------------------------------------------------------------
#
# The Sa'Vasku sheet is drawn with cogged discs: a stinger node carries an arc ring, a pod
# launcher an arrow along its single arc, and a power generator its power value. The drive node
# is the Kra'Vak hexagon with a star instead of a number, because a Sa'Vasku drive has no rating
# (FB2 p.22).


def _cog(cx: float, cy: float, r: float, teeth: int = 10) -> str:
    """The cogged disc FB2 draws every Sa'Vasku node with."""
    points = []
    for i in range(teeth * 2):
        angle = math.radians(-90 + i * 180 / teeth)
        rr = r if i % 2 == 0 else r * 0.78
        points.append(("L" if i else "M")
                      + f"{_fmt(cx + rr * math.cos(angle))} {_fmt(cy + rr * math.sin(angle))}")
    return " ".join(points) + " Z"


def _stinger(system: dict, x: float, y: float, arcs: tuple[str, ...]) -> list[Primitive]:
    return [
        Path(_cog(x, y, 7.5), fill=BLACK, stroke=0.8),
        Circle(x, y, 3.0, fill=WHITE, stroke=0),
        *_arc_ring(x, y, 11.5, system.get("arcs", []), arcs),
    ]


def _pod_launcher(system: dict, x: float, y: float, arcs: tuple[str, ...]) -> list[Primitive]:
    """Cog plus an arrow pointing along the launcher's single arc (FB2 p.25 key)."""
    covered = system.get("arcs") or []
    index = arcs.index(covered[0]) if covered and covered[0] in arcs else 0
    angle = math.radians(-90 + index * 360.0 / len(arcs))
    ux, uy = math.cos(angle), math.sin(angle)
    px, py = -uy, ux  # perpendicular, for the arrow's width
    tip = (x + ux * 15, y + uy * 15)
    base = (x + ux * 6.5, y + uy * 6.5)
    return [
        Path(_cog(x, y, 7.0), fill=BLACK, stroke=0.8),
        Circle(x, y, 2.8, fill=WHITE, stroke=0),
        Path(f"M{_fmt(tip[0])} {_fmt(tip[1])} "
             f"L{_fmt(base[0] + px * 4.5)} {_fmt(base[1] + py * 4.5)} "
             f"L{_fmt(base[0] - px * 4.5)} {_fmt(base[1] - py * 4.5)} Z", fill=BLACK, stroke=0),
    ]


def _spicule(system: dict, x: float, y: float, arcs: tuple[str, ...]) -> list[Primitive]:
    """A circle with the bowtie the book uses for point defence."""
    return [
        Circle(x, y, 6.0, fill=WHITE, stroke=1.2),
        Path(f"M{_fmt(x - 4)} {_fmt(y - 4)} L{_fmt(x + 4)} {_fmt(y - 4)} "
             f"L{_fmt(x - 4)} {_fmt(y + 4)} L{_fmt(x + 4)} {_fmt(y + 4)} Z", fill=BLACK, stroke=0),
    ]


def _cortex(system: dict, x: float, y: float, arcs: tuple[str, ...]) -> list[Primitive]:
    return [Circle(x, y, 5.0, fill=WHITE, stroke=1.2), Circle(x, y, 2.0, fill=BLACK, stroke=0)]


def _screen_node(system: dict, x: float, y: float, arcs: tuple[str, ...]) -> list[Primitive]:
    """The power the node needs is printed inside it (FB2 p.25); it equals the node's MASS."""
    mass = int(system.get("mass") or 0)
    return [
        Circle(x, y, 9.0, fill=WHITE, stroke=1.0),
        Circle(x, y, 6.5, fill=WHITE, stroke=0.7),
        Text(x, y + 3.0, str(mass) if mass else _("S"), size=8, bold=True),
    ]


def _drone_womb(system: dict, x: float, y: float, arcs: tuple[str, ...]) -> list[Primitive]:
    """The egg shape the broodship sheets use."""
    return [Path(f"M{_fmt(x)} {_fmt(y - 9)} C{_fmt(x + 7)} {_fmt(y - 5)} {_fmt(x + 7)} {_fmt(y + 8)} "
                 f"{_fmt(x)} {_fmt(y + 8)} C{_fmt(x - 7)} {_fmt(y + 8)} {_fmt(x - 7)} {_fmt(y - 5)} "
                 f"{_fmt(x)} {_fmt(y - 9)} Z", fill=WHITE, stroke=1.3)]


def _sv_drive(system: dict, x: float, y: float, arcs: tuple[str, ...]) -> list[Primitive]:
    """The Kra'Vak advanced-drive hexagon, "a star rather than a thrust number printed in the
    drive icon" because a Sa'Vasku drive has no set rating (FB2 p.22)."""
    return [Path(_hexagon(x, y, 11.0), fill=WHITE, stroke=1.3), _star(x, y, 6.5)]


def _power_generator(system: dict, x: float, y: float, arcs: tuple[str, ...]) -> list[Primitive]:
    """Drawn at the damage-track row ends by layout(), not in the system block."""
    return []


_SAVASKU_ICONS = dict(_SHARED_ICONS) | {
    "main_drive": _sv_drive,
    "stinger": _stinger,
    "pod_launcher": _pod_launcher,
    "spicule": _spicule,
    "cortex": _cortex,
    "screen_node": _screen_node,
    "drone_womb": _drone_womb,
    "power_generator": _power_generator,
}


# ---- Phalon icons (FB2 p.37 key) ---------------------------------------------------------------
#
# A pulser is a six-pointed star: the hexagon in the middle is the blank the player writes L, M
# or C into before a battle, and the six points around it are the arcs, white where the battery
# bears and black where it does not. Plasma bolt launchers are cogs carrying their class.


def _star_points(cx: float, cy: float, r_in: float, r_out: float,
                 arcs: tuple[str, ...], covered: list[str]) -> list[Primitive]:
    """One triangle per arc, white when the arc is covered (FB2 p.37)."""
    out: list[Primitive] = []
    span = 360.0 / len(arcs)
    for index, name in enumerate(arcs):
        middle = math.radians(-90.0 + index * span)
        base = math.radians(-90.0 + index * span - span / 2)
        tip = math.radians(-90.0 + index * span + span / 2)
        out.append(Path(
            f"M{_fmt(cx + r_out * math.cos(middle))} {_fmt(cy + r_out * math.sin(middle))} "
            f"L{_fmt(cx + r_in * math.cos(base))} {_fmt(cy + r_in * math.sin(base))} "
            f"L{_fmt(cx + r_in * math.cos(tip))} {_fmt(cy + r_in * math.sin(tip))} Z",
            fill=WHITE if name in covered else BLACK, stroke=0.7))
    return out


def _pulser(system: dict, x: float, y: float, arcs: tuple[str, ...]) -> list[Primitive]:
    mode = str(system.get("mode") or "")
    return [
        *_star_points(x, y, 5.5, 11.0, arcs, system.get("arcs", []) or []),
        Path(_hexagon(x, y, 5.5), fill=WHITE, stroke=1.0),
        *([Text(x, y + 3.0, mode, size=8, bold=True)] if mode else []),
    ]


def _plasma_bolt_launcher(system: dict, x: float, y: float, arcs: tuple[str, ...]) -> list[Primitive]:
    cls = system.get("class", 1)
    return [
        Path(_cog(x, y, 9.0, teeth=11), fill=WHITE, stroke=1.1),
        Text(x, y + 3.2, str(cls), size=9, bold=True),
        *_arc_ring(x, y, 12.5, system.get("arcs", []), arcs),
    ]


def _vapour_shroud(system: dict, x: float, y: float, arcs: tuple[str, ...]) -> list[Primitive]:
    """The gland: a ring of droplets around a centre (FB2 p.37)."""
    out: list[Primitive] = [Circle(x, y, 3.4, fill=BLACK, stroke=0)]
    for i in range(8):
        angle = math.radians(-90 + i * 45)
        out.append(Circle(x + 7.5 * math.cos(angle), y + 7.5 * math.sin(angle), 1.9,
                          fill=BLACK, stroke=0))
    return out


def _ph_adfc(system: dict, x: float, y: float, arcs: tuple[str, ...]) -> list[Primitive]:
    return [
        Rect(x - 6, y - 6, 12, 12, fill=BLACK, stroke=1.0),
        Path(f"M{_fmt(x - 3.5)} {_fmt(y - 3.5)} L{_fmt(x + 3.5)} {_fmt(y - 3.5)} "
             f"L{_fmt(x - 3.5)} {_fmt(y + 3.5)} L{_fmt(x + 3.5)} {_fmt(y + 3.5)} Z",
             fill=WHITE, stroke=0),
    ]


_PHALON_ICONS = dict(_SHARED_ICONS) | {
    "pulser": _pulser,
    "plasma_bolt_launcher": _plasma_bolt_launcher,
    "vapour_shroud": _vapour_shroud,
    "adfc": _ph_adfc,
    "hangar": _kv_hangar,   # the same plain triangle the Kra'Vak sheets use (FB2 p.37 key)
}


# ---- Cross Dimensions icons (CD p.21 figure 14, p.25 figure 17, p.39 figure 25) ------------------
#
# A graser is a beam circle with a downward triangle carrying the class; a classed torpedo writes
# its class under the tube; advanced screens are diamonds; a heavy missile is a missile outline,
# solid for extended range. The advanced drive is the Kra'Vak hexagon with its "A" rating (CD
# p.11 and figure 27) and is drawn from derived["advanced_drive"], so it needs no entry here.


def _graser(system: dict, x: float, y: float, arcs: tuple[str, ...]) -> list[Primitive]:
    return [
        Circle(x, y, 8.0, fill=WHITE, stroke=1.3),
        Path(f"M{_fmt(x - 6)} {_fmt(y - 4)} L{_fmt(x + 6)} {_fmt(y - 4)} L{_fmt(x)} {_fmt(y + 6.5)} Z",
             fill=BLACK, stroke=0),
        Text(x, y + 1.8, str(system.get("class", 1)), size=7, bold=True, fill=WHITE),
        *_arc_ring(x, y, 11.5, system.get("arcs", []), arcs),
    ]


def _classed_torpedo(system: dict, x: float, y: float, arcs: tuple[str, ...]) -> list[Primitive]:
    out = _torpedo(system, x, y, arcs)
    cls = system.get("class", 1)
    if isinstance(cls, int) and cls > 1:
        out.append(Text(x + 11, y + 12, str(cls), size=7, bold=True))
    return out


def _diamond(cx: float, cy: float, r: float) -> str:
    return (f"M{_fmt(cx)} {_fmt(cy - r)} L{_fmt(cx + r)} {_fmt(cy)} L{_fmt(cx)} {_fmt(cy + r)} "
            f"L{_fmt(cx - r)} {_fmt(cy)} Z")


def _advanced_screen(system: dict, x: float, y: float, arcs: tuple[str, ...]) -> list[Primitive]:
    level = max(1, min(3, int(system.get("level", 1) or 1)))
    return [Path(_diamond(x + i * 9 - (level - 1) * 4.5, y, 6.5), fill=WHITE, stroke=1.2)
            for i in range(level)]


def _heavy_missile(system: dict, x: float, y: float, arcs: tuple[str, ...]) -> list[Primitive]:
    fill = BLACK if system.get("load") == "er" else WHITE
    stages = system.get("stages", 1)
    out: list[Primitive] = [
        Path(f"M{_fmt(x)} {_fmt(y - 9)} L{_fmt(x + 3)} {_fmt(y - 4)} L{_fmt(x + 3)} {_fmt(y + 5)} "
             f"L{_fmt(x + 5)} {_fmt(y + 9)} L{_fmt(x - 5)} {_fmt(y + 9)} L{_fmt(x - 3)} {_fmt(y + 5)} "
             f"L{_fmt(x - 3)} {_fmt(y - 4)} Z", fill=fill, stroke=1.1),
    ]
    if isinstance(stages, int) and stages > 1:
        out.append(Text(x + 9, y + 9, str(stages), size=7, bold=True))
    return out


_CD_ICONS = dict(_SHARED_ICONS) | {
    "graser": _graser,
    "pulse_torpedo": _classed_torpedo,
    "advanced_screen": _advanced_screen,
    "scattergun": _scattergun,
    "heavy_missile": _heavy_missile,
    "enhanced_sensors": _labelled(lambda: _("ENH")),
    "superior_sensors": _labelled(lambda: _("SUP")),
    "weasel_cruiser": _labelled(lambda: _("WSL")),
    "weasel_capital": _labelled(lambda: _("WSL+")),
    "ecm": _labelled(lambda: _("ECM")),
    "area_ecm": _labelled(lambda: _("AECM"), wide=True),
}


# ---- Project Continuum icons ------------------------------------------------------------------
#
# PC draws most of its many weapons as variations on the beam circle. Until each has its own
# icon, a weapon is a boxed abbreviation with its class and, where it has arcs, the arc ring, so
# a sheet still shows what bears where; everything else PC shares with Cross Dimensions.


def _pc_weapon(prefix, classed: bool = True):
    """A boxed abbreviation (callable, translated at draw time) with the class and arc ring."""
    def draw(system: dict, x: float, y: float, arcs: tuple[str, ...]) -> list[Primitive]:
        label = prefix() if callable(prefix) else prefix
        cls = system.get("class")
        if classed and isinstance(cls, int):
            label = f"{label}{cls}"
        out: list[Primitive] = [Rect(x - 9, y - 7, 18, 14, fill=WHITE, stroke=1.2),
                                Text(x, y + 3.0, label, size=6.5, bold=True)]
        if system.get("arcs"):
            out += _arc_ring(x, y, 11.5, system.get("arcs", []), arcs)
        return out
    return draw


def _pc_counted(prefix):
    """Crew parties: the abbreviation and how many."""
    def draw(system: dict, x: float, y: float, arcs: tuple[str, ...]) -> list[Primitive]:
        return [Rect(x - 13, y - 7, 26, 14, fill=WHITE, stroke=1.2),
                Text(x, y + 3.0, f"{prefix()} {system.get('count', 1)}", size=7, bold=True)]
    return draw


_PC_ICONS = dict(_CD_ICONS) | {
    "pulse_torpedo": _torpedo,
    "advanced_fire_control": _labelled(lambda: _("AFC")),
    "emp": _pc_weapon(lambda: _("EMP")),
    "transporter": _pc_weapon(lambda: _("TB")),
    "grav_gun": _pc_weapon(lambda: _("GR")),
    "plasma_cannon": _pc_weapon(lambda: _("PL")),
    "phaser": _pc_weapon(lambda: _("PH")),
    "heavy_graser": _graser,
    "gatling": _pc_weapon(lambda: _("GAT"), classed=False),
    "twin_particle_array": _pc_weapon(lambda: _("TPA"), classed=False),
    "meson": _pc_weapon(lambda: _("MES"), classed=False),
    "pulser": _pc_weapon(lambda: _("PUL"), classed=False),
    "needle_beam": _pc_weapon(lambda: _("NB")),
    "kgun": _pc_weapon(lambda: _("K")),
    "mkp": _pc_weapon(lambda: _("MKP"), classed=False),
    "boarding_torpedo_launcher": _pc_weapon(lambda: _("BTL"), classed=False),
    "boarding_torpedoes": _pc_counted(lambda: _("BT")),
    "fusion_array": _pc_weapon(lambda: _("FUS"), classed=False),
    "plasma_bolt": _pc_weapon(lambda: _("PBL")),
    "am_missile": _pc_weapon(lambda: _("AM"), classed=False),
    "rocket_pod": _pc_weapon(lambda: _("RP"), classed=False),
    "spinal_mount": _big_gun("SM"),
    "area_screen": _labelled(lambda: _("ASCR"), wide=True),
    "advanced_area_screen": _labelled(lambda: _("AASC"), wide=True),
    "ads": _pc_weapon(lambda: _("ADS"), classed=False),
    "aadfc": _labelled(lambda: _("AADF"), wide=True),
    "grapeshot": _labelled(lambda: _("GS")),
    "amsc": _labelled(lambda: _("AMSC"), wide=True),
    "stealth_field": _labelled(lambda: _("STL")),
    "holofield": _labelled(lambda: _("HOLO"), wide=True),
    "cloaking_device": _labelled(lambda: _("CLD")),
    "cloaking_field": _labelled(lambda: _("CLF")),
    "hangar_bay": _hangar,
    "launch_tube": _labelled(lambda: _("LT")),
    "boat_bay": _labelled(lambda: _("BOAT"), wide=True),
    "fighter_rack": _labelled(lambda: _("RACK"), wide=True),
    "gunboat_rack": _labelled(lambda: _("GBR"), wide=True),
    "turret": _pc_weapon(lambda: _("TUR"), classed=False),
    "marines": _pc_counted(lambda: _("MAR")),
    "dcp": _pc_counted(lambda: _("DCP")),
    "troop_berthing": _labelled(lambda: _("TRB")),
    "passenger_berthing": _labelled(lambda: _("PSB")),
    "shipyard": _labelled(lambda: _("YARD"), wide=True),
    "flawed_design": _labelled(lambda: _("FLAW"), wide=True),
}


# Systems from the Star Ranger designs (fullthrust.star-ranger.com) on Fleet Book sheets, drawn
# like their Cross Dimensions and Project Continuum namesakes.
_FB_ICONS = dict(_SHARED_ICONS) | {
    "graser": _graser,
    "emp": _pc_weapon(lambda: _("EMP")),
    "rocket_cannon": _pc_weapon(lambda: _("RC")),
    "hdc": _pc_weapon(lambda: _("HDC")),
    "lrpt": _pc_weapon(lambda: _("LRT"), classed=False),
    "amt": _pc_weapon(lambda: _("AMT"), classed=False),
    "superior_sensors": _labelled(lambda: _("SUP")),
    "age_penalty": _labelled(lambda: _("AGE")),
}


ICON_SETS: dict[str, dict] = {
    "fb": _FB_ICONS,
    "ftcd": _CD_ICONS,
    "ftpc": _PC_ICONS | {k: _FB_ICONS[k] for k in ("rocket_cannon", "hdc", "amt", "age_penalty")}
    | {"compact_superior_sensors": _FB_ICONS["superior_sensors"]},
    "ft2": dict(_SHARED_ICONS),
    "fb_kravak": _KRAVAK_ICONS,
    "fb_savasku": _SAVASKU_ICONS,
    "fb_phalon": _PHALON_ICONS,
}


def _icon(icon_set: str, system: dict, x: float, y: float, arcs: tuple[str, ...],
          out: bool) -> list[Primitive]:
    draw = ICON_SETS.get(icon_set, ICON_SETS["fb"]).get(system.get("type"))
    if draw is None:
        draw = _labelled(str(system.get("type", "?"))[:4].upper(), wide=True)
    prims = [replace(shape, ref=f"system:{system.get('uid', '')}") for shape in draw(system, x, y, arcs)]
    if out:
        prims.append(replace(_cross(x, y, 10.5), ref=f"system:{system.get('uid', '')}"))
    return prims


# ---- Placement ------------------------------------------------------------------------------------

WEAPONS = {
    "beam", "pulse_torpedo", "needle_beam", "nova_cannon", "wave_gun", "aa_battery",
    "sm_launcher", "sm_rack", "submunition", "kgun", "mkp", "stinger", "pod_launcher",
    "pulser", "plasma_bolt_launcher", "graser", "heavy_missile",
    # Project Continuum
    "emp", "transporter", "grav_gun", "plasma_cannon", "phaser", "heavy_graser", "gatling",
    "twin_particle_array", "meson", "boarding_torpedo_launcher", "fusion_array", "plasma_bolt",
    "am_missile", "rocket_pod", "spinal_mount", "ads", "turret",
    # Star Ranger designs on Fleet Book sheets
    "rocket_cannon", "hdc", "lrpt", "amt",
}
BOTTOM_ROW = {"hold", "tug_drive", "tender_bay", "jump_gate", "portal"}
# Stacked straight above the armour and hull boxes, bottom up: the fire controls in one row,
# point defence (after the fire controls when the row has room), then the hangars.
FIRE_CONTROLS = {"fire_control", "adfc", "advanced_fire_control", "aadfc"}
POINT_DEFENCE = {"pds", "pdaf"}
HANGARS = {"hangar", "fighter_group", "hangar_bay"}
# Missiles and their magazines sit together at the bottom of the weapon space (owner's rule).
MISSILES = {"sm_launcher", "sm_rack", "sm_magazine", "mt_missile", "heavy_missile", "am_missile",
            "rocket_pod"}


def _side(arcs_of_system: list[str], all_arcs: tuple[str, ...]) -> str:
    """Where a system belongs: fore, port, starboard, aft or centre (all-round / no arc)."""
    if not arcs_of_system or set(arcs_of_system) >= set(all_arcs):
        return "centre"
    fore, aft = all_arcs[0], all_arcs[len(all_arcs) // 2]
    port = {a for a in all_arcs if a.endswith("P") and a != fore} | ({"P"} if "P" in all_arcs else set())
    starboard = {a for a in all_arcs if a.endswith("S") and a != fore} | ({"S"} if "S" in all_arcs else set())
    covered = set(arcs_of_system)
    if covered == {fore} or (fore in covered and not covered & (port | starboard)):
        return "fore"
    if covered == {aft}:
        return "aft"
    if covered & port and not covered & starboard:
        return "port"
    if covered & starboard and not covered & port:
        return "starboard"
    return "fore" if fore in covered else "centre"


def _weight(system: dict) -> int:
    """Bigger guns sit nearer the top."""
    cls = system.get("class")
    if isinstance(cls, str):
        return {"A": 3, "B": 2, "C": 1}.get(cls.upper(), 1)
    if isinstance(cls, int):
        return cls
    return {"nova_cannon": 5, "wave_gun": 5, "pulse_torpedo": 4, "sm_launcher": 4}.get(system.get("type"), 2)


def _classify(design: dict, all_arcs: tuple[str, ...]) -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = {k: [] for k in ("fore", "port", "starboard", "aft", "centre", "bottom",
                                                     "fire_control", "pds", "hangar", "missiles")}
    for system in design.get("systems", []):
        if not isinstance(system, dict):
            continue
        stype = system.get("type")
        if stype in BOTTOM_ROW:
            groups["bottom"].append(system)
        elif stype in FIRE_CONTROLS:
            groups["fire_control"].append(system)
        elif stype in POINT_DEFENCE:
            groups["pds"].append(system)
        elif stype in HANGARS:
            groups["hangar"].append(system)
        elif stype in MISSILES:
            groups["missiles"].append(system)
        elif stype in WEAPONS:
            groups[_side(system.get("arcs", []), all_arcs)].append(system)
        else:
            groups["centre"].append(system)
    for key in ("fore", "port", "starboard", "aft", "centre"):
        groups[key].sort(key=lambda s: -_weight(s))
    # Launchers and racks first, their magazines after them.
    groups["missiles"].sort(key=lambda s: (s.get("type") == "sm_magazine", -_weight(s)))
    return groups


def _icon_extent(icon_set: str, system: dict, arcs: tuple[str, ...]) -> tuple[float, float]:
    """How far an icon reaches from its centre: (across, up or down), from what it draws."""
    x0, y0, x1, y1 = _bbox(_icon(icon_set, system, 0.0, 0.0, arcs, False))
    return max(6.0, -x0, x1), max(6.0, -y0, y1)


# ---- The diagram ------------------------------------------------------------------------------------

BOX_WIDTHS = {"small": 170.0, "medium": 210.0, "large": 260.0, "xlarge": 330.0}


def box_size(design: dict, ruleset_id: str | None = None) -> str:
    """Sheet width band, from the widest damage-track row (PLAN 10.2 packs sheets by this)."""
    rs = RULESETS.get(ruleset_id or design.get("ruleset"))
    widest = max(rs.damage_track(design)) if rs else 0
    systems = len(design.get("systems", []))
    if widest <= 8 and systems <= 8:
        return "small"
    if widest <= 14 and systems <= 16:
        return "medium"
    if widest <= 22:
        return "large"
    return "xlarge"


def layout(design: dict, ruleset=None, damage: dict | None = None, loadout: dict | None = None,
           box: str = "auto") -> Diagram:
    """One ship record sheet. `damage` is a ship's campaign damage (PLAN 5.3) or None for a
    blank copy; `loadout` is accepted for the fighter/ordnance labels and may be None."""
    rs = ruleset or RULESETS.get(design.get("ruleset"))
    if rs is None:
        return Diagram(0, 0, ())
    arcs = tuple(rs.arcs)
    # Per race, so each race's sheets look like its own part of the book (PLAN decision 10).
    icon_set_for = getattr(rs, "icon_set_for", None)
    icon_set = (icon_set_for(design.get("race", "human")) if icon_set_for
                else getattr(rs, "icon_set", None) or rs.id)
    damage = damage or {}
    systems_out = set(damage.get("systems_out") or [])
    hints = design.get("layout_hints") if isinstance(design.get("layout_hints"), dict) else {}

    # The ruleset's derived values drive the parts of a sheet that are not systems: a race may
    # ask for generators on the damage track, a thrust table or a power box just by deriving
    # them, so nothing here branches on the race.
    try:
        breakdown = rs.design_breakdown(design, {})
        derived = breakdown.derived
        mass_by_uid = {r.system_uid: r.mass for r in breakdown.rows if r.system_uid}
        # A per-ship loadout overrides the design's (the Phalon pulser L/M/C setting, FB2 p.35).
        modes = dict(derived.get("pulser_modes") or {})
        if loadout is not None and hasattr(rs, "design_breakdown"):
            for entry in (loadout.get("pulsers") or []) if isinstance(loadout, dict) else []:
                if isinstance(entry, dict) and isinstance(entry.get("pulser"), str):
                    modes[entry["pulser"]] = str(entry.get("mode") or "")
    except Exception:  # a ruleset never raises, but a sheet must draw even if one does
        derived, mass_by_uid, modes = {}, {}, {}

    size = box if box != "auto" else box_size(design, rs.id)
    width = BOX_WIDTHS.get(size, BOX_WIDTHS["medium"])
    prims: list[Primitive] = []

    groups = _classify(design, arcs)
    gap = 2 * ICON_RADIUS + 6
    y = 16.0

    anchors: dict[str, tuple[float, float]] = {}
    lowest = 0.0  # the lowest pinned icon; the sheet grows to keep it on the page

    drawn_low = 0.0  # the bottom edge of the auto-placed icons so far

    def place(system: dict, x: float, cy: float) -> None:
        nonlocal lowest, drawn_low
        pinned = hints.get(system.get("uid")) if isinstance(hints.get(system.get("uid")), dict) else None
        if pinned:
            x = min(max(float(pinned.get("x", x)), 0.0), width)
            cy = max(float(pinned.get("y", cy)), 0.0)
            lowest = max(lowest, cy + ICON_RADIUS)
        if system.get("uid"):
            anchors[system["uid"]] = (round(x, 2), round(cy, 2))
        extra = {}
        if system.get("uid") in mass_by_uid:
            extra["mass"] = mass_by_uid[system["uid"]]
        if system.get("uid") in modes:
            extra["mode"] = modes[system["uid"]]
        shown = {**system, **extra} if extra else system
        icon = _icon(icon_set, shown, x, cy, arcs, system.get("uid") in systems_out)
        prims.extend(icon)
        if not pinned:
            drawn_low = max(drawn_low, _bbox(icon)[3])

    # Rows are packed by each icon's own width with a small gap: room to read, nothing wider
    # (owner's layout rule).
    Row = list[tuple[dict, float, float]]  # (system, half width, half height)

    def packed(systems: list[dict], wrap: bool = True, room: float | None = None) -> list[Row]:
        """Rows each as wide as `room` (the box) allows. Unwrapped, it is one row however
        long."""
        room = width - 16 if room is None else room
        rows: list[Row] = [[]]
        used = 0.0
        for system in systems:
            half, tall = _icon_extent(icon_set, system, arcs)
            if wrap and rows[-1] and used + 2 * half + 4 > room:
                rows.append([])
                used = 0.0
            rows[-1].append((system, half, tall))
            used += 2 * half + 4
        return [r for r in rows if r]

    def span(row: Row) -> float:
        return sum(2 * half + 4 for _s, half, _t in row) - 4

    def tall(row: Row) -> float:
        return max(t for _s, _h, t in row)

    def mirrored(row: Row) -> Row:
        """One symmetric row, smallest in the middle and the bigger ones paired outwards, so
        two class-1 and two class-2 guns read 2-1-1-2 (owner's rule). Rows only split, larger
        above smaller, when the box is too narrow for one."""
        out: Row = []
        for i, item in enumerate(reversed(row)):
            out.insert(0 if i % 2 else len(out), item)
        return out

    def place_row(row: Row, cy: float, squeeze: float = 1.0) -> None:
        x = width / 2 - span(row) * squeeze / 2
        for system, half, _t in row:
            place(system, x + half * squeeze, cy)
            x += (2 * half + 4) * squeeze

    def step(row: Row, least: float) -> float:
        """From one row's centre to the next: `least`, or more for a tall icon."""
        return max(least, 2 * tall(row) + 4)

    # Fore weapons: rows across the top, largest first.
    for row in packed(groups["fore"]):
        y += max(0.0, tall(row) - ICON_RADIUS)
        place_row(mirrored(row), y)
        y += step(row, gap) - max(0.0, tall(row) - ICON_RADIUS)

    # Port and starboard columns hug the centre block of all-round systems (C1 beams, screens).
    port_half = max((_icon_extent(icon_set, s, arcs)[0] for s in groups["port"]), default=0.0)
    star_half = max((_icon_extent(icon_set, s, arcs)[0] for s in groups["starboard"]), default=0.0)
    sides = (2 * port_half + 6 if groups["port"] else 0) + (2 * star_half + 6 if groups["starboard"] else 0)
    # All-round guns in their own symmetric rows, then the other all-round systems (screens).
    room = max(2 * ICON_RADIUS, width - 16 - sides)
    centre_rows = (packed([s for s in groups["centre"] if s.get("type") in WEAPONS], room=room)
                   + packed([s for s in groups["centre"] if s.get("type") not in WEAPONS], room=room))
    block = max((span(r) for r in centre_rows), default=0.0)
    centre_top = y
    cy = centre_top
    for row in centre_rows:
        cy += max(0.0, tall(row) - ICON_RADIUS)
        place_row(mirrored(row), cy)
        cy += step(row, 2 * ICON_RADIUS) - max(0.0, tall(row) - ICON_RADIUS)
    port_x = max(8 + port_half, width / 2 - block / 2 - 6 - port_half)
    star_x = min(width - 8 - star_half, width / 2 + block / 2 + 6 + star_half)
    side_end = centre_top
    for column, x in ((groups["port"], port_x), (groups["starboard"], star_x)):
        sy = centre_top
        for system in column:
            row = packed([system])[0]
            sy += max(0.0, tall(row) - ICON_RADIUS)
            place(system, x, sy)
            sy += step(row, gap) - max(0.0, tall(row) - ICON_RADIUS)
        side_end = max(side_end, sy)
    y = max(cy, side_end)

    # Aft-only weapons along the bottom of the system block, then the missiles and magazines.
    for rows, arrange in ((packed(groups["aft"]), mirrored), (packed(groups["missiles"]), None)):
        for row in rows:
            y += max(0.0, tall(row) - ICON_RADIUS)
            place_row(arrange(row) if arrange else row, y)
            y += step(row, gap) - max(0.0, tall(row) - ICON_RADIUS)

    # Hangars, point defence and the fire-control row, stacked down onto the armour and hull.
    def draw_row(row: Row) -> None:
        nonlocal y
        # A row too long for the box (the fire controls never wrap) is squeezed to fit.
        squeeze = min(1.0, (width - 16) / span(row)) if span(row) > 0 else 1.0
        cy = y + tall(row)
        place_row(row, cy, squeeze)
        y = cy + tall(row) + 4

    fc_row = packed(groups["fire_control"], wrap=False)
    pds_rows = packed(groups["pds"])
    if fc_row and len(pds_rows) == 1 and len(packed(groups["fire_control"] + groups["pds"])) == 1:
        fc_row = [fc_row[0] + pds_rows[0]]
        pds_rows = []
    stack = packed(groups["hangar"]) + pds_rows + fc_row
    if drawn_low:
        y = drawn_low + 6  # from the next row's centre to just under the icons drawn so far
    for row in stack:
        draw_row(row)
    y += 4

    # Armour circles, then the damage track with its crew-factor stars and threshold marks.
    track = rs.damage_track(design)
    cf = set(rs.cf_positions(design))
    columns = max(max(track, default=1), 1)
    cell = min(11.0, (width - 24) / columns)
    left = width / 2 - columns * cell / 2

    armour = int(design.get("armour") or 0)
    armour_done = int(damage.get("armour") or 0)
    per = max(1, int((width - 24) // cell))
    # A ruleset may stack the armour in layers (the Phalon shell, FB2 p.35): one row per layer,
    # outermost at the top, which is also the order damage takes them off.
    layers = derived.get("shell_layers") or ([armour] if armour else [])
    box_index = 0
    for row_len in reversed(layers):
        # A row that would run off the box's right edge is centred on its own width instead.
        armour_left = left
        if left + min(row_len, per) * cell > width - 12:
            armour_left = width / 2 - min(row_len, per) * cell / 2
        for i in range(row_len):
            ccx = armour_left + (i % per) * cell + cell / 2
            ccy = y + (i // per) * cell + cell / 2
            box_index += 1
            prims.append(Circle(ccx, ccy, cell / 2 - 0.8, fill=WHITE, stroke=0.9,
                                ref=f"armour:{box_index}"))
            if box_index <= armour_done:
                prims.append(_slash(ccx - cell / 2, ccy - cell / 2, cell))
        y += max(1, math.ceil(row_len / per)) * cell
    if layers:
        y += 2

    hull_done = int(damage.get("hull") or 0)
    numbered = 0
    for row_index, row_len in enumerate(track):
        for column in range(row_len):
            numbered += 1
            bx, by = left + column * cell, y + row_index * cell
            prims.append(Rect(bx, by, cell, cell, fill=WHITE, stroke=0.9,
                              ref=f"hull:{numbered}"))
            if numbered in cf:
                prims.append(_star(bx + cell / 2, by + cell / 2, cell * 0.3))
            if numbered <= hull_done:
                prims.append(_slash(bx, by, cell))
    # A row-end generator per damage-track row (FB2 p.22: the generator at the end of a row is
    # lost automatically when damage reaches it).
    generators = derived.get("power_generators") or []
    filled = [i for i, row_len in enumerate(track) if row_len]
    for row_index, value in zip(filled, generators):
        if not value:
            continue  # the book prints no generator rather than a zero
        gx = left + columns * cell + 10
        gy = y + row_index * cell + cell / 2
        prims.append(Path(_cog(gx, gy, 8.0), fill=BLACK, stroke=0.8))
        prims.append(Text(gx, gy + 3.0, str(value), size=8, bold=True, fill=WHITE))
        if sum(track[:row_index + 1]) <= hull_done:
            prims.append(_cross(gx, gy, 7.0))
    y += len(track) * cell + 8

    # Bottom row: FTL, main drive with its thrust, core systems (FB), holds and tugs; centred,
    # like every row (owner's layout rule). Drawn from x 16 and shifted by `ox`.
    core = derived.get("core_systems", rs.id == "fb")
    ox = width / 2 - (16 + (66 + 2 * 7 + 70 if core else 66)) / 2
    if design.get("ftl"):
        if derived.get("advanced_ftl"):
            # CD figure 27: the advanced FTL is a hexagon where the standard one is a box.
            prims.append(Path(_hexagon(ox + 26, y + 8, 10.5), fill=WHITE, stroke=1.2))
        else:
            prims.append(Rect(ox + 16, y, 20, 16, fill=WHITE, stroke=1.2))
        prims.append(Text(ox + 26, y + 11.5, _("FTL"), size=7, bold=True))
    thrust = int(design.get("thrust") or 0)
    # An icon set may draw the main drive itself: FB2 p.9 gives the Kra'Vak Advanced Grav Drive
    # its own icon and writes the rating with an "A".
    draw_drive = ICON_SETS.get(icon_set, {}).get("main_drive")
    if draw_drive is None and derived.get("advanced_drive"):
        draw_drive = _kv_drive  # CD p.11: the advanced drive's own icon, rating written "nA"
    if draw_drive:
        prims.extend(draw_drive({"type": "main_drive", "thrust": thrust}, ox + 55, y + 7.5, arcs))
    else:
        a, m, b = _fmt(ox + 44), _fmt(ox + 55), _fmt(ox + 66)
        prims.append(Path(f"M{a} {_fmt(y + 16)} L{a} {_fmt(y + 5)} L{m} {_fmt(y - 1)} L{b} {_fmt(y + 5)} "
                          f"L{b} {_fmt(y + 16)} Z", fill=WHITE, stroke=1.3))
        prims.append(Text(ox + 55, y + 13.5, str(thrust), size=9.5, bold=True))
    if int(damage.get("drive_hits") or 0):
        prims.append(_cross(ox + 55, y + 8, 9))
    # The core systems box is part of a human or Kra'Vak FB sheet but not an FT2 one (FT p.14),
    # and not a Sa'Vasku one: a construct has no bridge or life support, and the FB2 p.25 key
    # lists no such box. The ruleset says which, through derived["core_systems"].
    if core:
        # Beside the drive, at most twice the FTL-to-drive gap away (owner's layout rule).
        bx = ox + 66 + 2 * 7
        prims.append(Rect(bx, y - 2, 70, 20, r=4, fill=WHITE, stroke=1.1))
        for i, letter in enumerate((_("B"), _("L"), _("P"))):
            prims.append(Rect(bx + 5 + i * 21, y + 1, 16, 14, fill=BLACK, stroke=0))
            prims.append(Text(bx + 13 + i * 21, y + 11.5, letter, size=8, bold=True, fill=WHITE))
    y += 24

    for start in range(0, len(groups["bottom"]), 4):
        row = groups["bottom"][start:start + 4]
        x0 = width / 2 - (len(row) - 1) * (2 * WIDE_RADIUS) / 2
        for i, system in enumerate(row):
            place(system, x0 + i * 2 * WIDE_RADIUS, y + 7)
        y += 20

    y = _play_aids(prims, derived, width, y)
    # Cropped to what it draws, with a small margin, so no sheet is wider than it needs to be;
    # evenly on both sides, so the centre line every row sits on stays the sheet's centre (and
    # the middle of the PDF's hull silhouette).
    lo, hi = _x_extent(prims)
    half = min(width / 2, max(width / 2 - lo, hi - width / 2) + 8) if hi > lo else width / 2
    lo, hi = width / 2 - half, width / 2 + half
    return Diagram(round(hi - lo, 2), round(max(y + 6, lowest), 2), tuple(prims), anchors, round(lo, 2))


def _x_extent(prims: list[Primitive]) -> tuple[float, float]:
    """The leftmost and rightmost x the primitives reach."""
    x0, _y0, x1, _y1 = _bbox(prims)
    return x0, x1


def _bbox(prims) -> tuple[float, float, float, float]:
    """(left, top, right, bottom) of the primitives; text by an estimate of its size."""
    xs: list[float] = []
    ys: list[float] = []
    for p in prims:
        if isinstance(p, Rect):
            xs += [p.x, p.x + p.w]
            ys += [p.y, p.y + p.h]
        elif isinstance(p, Circle):
            xs += [p.cx - p.r, p.cx + p.r]
            ys += [p.cy - p.r, p.cy + p.r]
        elif isinstance(p, Line):
            xs += [p.x1, p.x2]
            ys += [p.y1, p.y2]
        elif isinstance(p, Path):
            points = _path_points(p.d)
            xs += [x for x, _y in points]
            ys += [y for _x, y in points]
        elif isinstance(p, Text):
            w = len(p.text) * p.size * 0.6
            x0 = {"middle": p.x - w / 2, "end": p.x - w}.get(p.anchor, p.x)
            xs += [x0, x0 + w]
            ys += [p.y - p.size * 0.75, p.y + p.size * 0.2]
    return (min(xs), min(ys), max(xs), max(ys)) if xs else (0.0, 0.0, 0.0, 0.0)


def _path_points(d: str) -> list[tuple[float, float]]:
    """Every point of an absolute M/L/C/Z path."""
    points: list[tuple[float, float]] = []
    for chunk in re.split(r"[A-Za-z]", d):
        numbers = [float(n) for n in re.findall(r"-?\d+(?:\.\d+)?", chunk)]
        points += list(zip(numbers[0::2], numbers[1::2]))
    return points


def _play_aids(prims: list[Primitive], derived: dict, width: float, y: float) -> float:
    """The parts of a sheet a player writes on or reads off during a turn, when the ruleset
    derives them: the thrust table and the power-allocation box a Sa'Vasku ship needs (FB2 p.22
    and the record chart on p.33). A race that derives neither gets nothing."""
    table = derived.get("thrust_table") or []
    power = derived.get("power") or 0
    if not table and not power:
        return y

    y += 6
    top = y
    if table:
        # Two columns when the table is long, so a big ship's sheet does not grow a tail.
        per_column = len(table) if len(table) <= 8 else (len(table) + 1) // 2
        col_w, row_h = 46.0, 9.5
        prims.append(Text(16 + col_w / 2, y + 7, _("Thrust / power"), size=6.5, bold=True))
        y += 10
        for index, (thrust, cost, damaged) in enumerate(table):
            cx = 16 + (index // per_column) * (col_w + 6)
            cy = y + (index % per_column) * row_h
            prims.append(Rect(cx, cy, 18, row_h - 1, fill=WHITE, stroke=0.6))
            prims.append(Text(cx + 9, cy + row_h - 3, str(thrust), size=6.5))
            prims.append(Rect(cx + 19, cy, col_w - 19, row_h - 1, fill=WHITE, stroke=0.6))
            label = f"{cost}/{damaged if damaged is not None else '-'}"
            prims.append(Text(cx + 19 + (col_w - 19) / 2, cy + row_h - 3, label, size=6.5))
        y += min(len(table), per_column) * row_h

    if power:
        # Empty boxes: allocation is rewritten every turn and never stored (FB2 p.22).
        # Beside the thrust table rather than at the far edge.
        columns = (1 if len(table) <= 8 else 2) if table else 0
        bx = min(width - 96, 16 + columns * 52 + 10) if table else 16
        prims.append(Text(bx + 40, top + 7, _("Power {n} per turn", n=power), size=6.5, bold=True))
        for i, pool in enumerate((_("M"), _("A"), _("D"), _("R"))):
            px = bx + i * 20
            prims.append(Text(px + 9, top + 18, pool, size=7, bold=True))
            prims.append(Rect(px, top + 20, 18, 14, fill=WHITE, stroke=0.9))
        y = max(y, top + 36)
    return y


# ---- SVG (the app renders the same primitives the PDF does) -------------------------------------


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def to_svg(diagram: Diagram, class_name: str = "ssd", draggable: bool = False) -> str:
    """The diagram as inline SVG. `draggable` wraps each system's shapes in a
    `<g class="sys" data-uid data-x data-y>` (its anchor) for static/ssddrag.js."""
    parts = [
        f'<svg viewBox="{_fmt(diagram.left)} 0 {_fmt(diagram.width)} {_fmt(diagram.height)}" '
        f'xmlns="http://www.w3.org/2000/svg" class="{class_name}">'
    ]
    group = None
    for p in diagram.primitives:
        ref = f' data-ref="{p.ref}"' if p.ref else ""
        if draggable:
            uid = p.ref[7:] if p.ref and p.ref.startswith("system:") else None
            if group is not None and uid != group:
                parts.append("</g>")
                group = None
            if uid is not None and group is None and uid in diagram.anchors:
                ax, ay = diagram.anchors[uid]
                parts.append(f'<g class="sys" data-uid="{_escape(uid)}" data-x="{_fmt(ax)}" '
                             f'data-y="{_fmt(ay)}">')
                group = uid
        if isinstance(p, Rect):
            radius = f' rx="{_fmt(p.r)}"' if p.r else ""
            parts.append(f'<rect x="{_fmt(p.x)}" y="{_fmt(p.y)}" width="{_fmt(p.w)}" height="{_fmt(p.h)}"'
                         f'{radius} fill="{p.fill}" stroke="{"none" if not p.stroke else "black"}" '
                         f'stroke-width="{_fmt(p.stroke)}"{ref}/>')
        elif isinstance(p, Circle):
            stroke = "none" if not p.stroke else "black"
            parts.append(f'<circle cx="{_fmt(p.cx)}" cy="{_fmt(p.cy)}" r="{_fmt(p.r)}" fill="{p.fill}" '
                         f'stroke="{stroke}" stroke-width="{_fmt(p.stroke)}"{ref}/>')
        elif isinstance(p, Line):
            parts.append(f'<line x1="{_fmt(p.x1)}" y1="{_fmt(p.y1)}" x2="{_fmt(p.x2)}" y2="{_fmt(p.y2)}" '
                         f'stroke="black" stroke-width="{_fmt(p.stroke)}"{ref}/>')
        elif isinstance(p, Path):
            parts.append(f'<path d="{p.d}" fill="{p.fill}" stroke="{"none" if not p.stroke else "black"}" '
                         f'stroke-width="{_fmt(p.stroke)}"{ref}/>')
        else:
            weight = ' font-weight="700"' if p.bold else ""
            parts.append(f'<text x="{_fmt(p.x)}" y="{_fmt(p.y)}" font-size="{_fmt(p.size)}" '
                         f'text-anchor="{p.anchor}" fill="{p.fill}"{weight}{ref}>{_escape(p.text)}</text>')
    if group is not None:
        parts.append("</g>")
    parts.append("</svg>")
    return "".join(parts)
