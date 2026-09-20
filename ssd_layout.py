"""Ship diagram (SSD) layout: design -> drawing primitives (PLAN 10.1).

Pure and side-effect free. `layout()` returns a `Diagram` of primitives in a top-left origin
coordinate system, in points (1 pt = 1/72 in), so the same numbers serve the screen (SVG, via
`to_svg()`) and the paper (fpdf2, M9): screen = paper.

Icons come from the ruleset's `icon_set` id, so an FT2 sheet looks like the FT book and an FB
sheet like Fleet Book 1 (FT p.14 / FB1 p.12 keys). The tables live here rather than in the
rulesets because drawing is a consumer's job; a ruleset only names its set.

Placement is arc-aware (PLAN 10.1): fore weapons top centre, port-covering ones in a left
column, starboard-covering in a right column, aft-only at the bottom, all-round systems in a
central row, larger classes nearer the top. A design's `layout_hints` may pin any system to a
position; the catalog may ship them and drag-to-arrange can write them later.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
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
    kind: str = "rect"


@dataclass(frozen=True)
class Circle:
    cx: float
    cy: float
    r: float
    fill: str = "none"
    stroke: float = 0.9
    kind: str = "circle"


@dataclass(frozen=True)
class Line:
    x1: float
    y1: float
    x2: float
    y2: float
    stroke: float = 0.9
    kind: str = "line"


@dataclass(frozen=True)
class Path:
    d: str
    fill: str = "none"
    stroke: float = 0.9
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
    kind: str = "text"


Primitive = Rect | Circle | Line | Path | Text


@dataclass(frozen=True)
class Diagram:
    width: float
    height: float
    primitives: tuple[Primitive, ...] = field(default_factory=tuple)


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
        out.append(Path(
            f"M{_fmt(cx + r * math.cos(a0))} {_fmt(cy + r * math.sin(a0))} "
            f"A{_fmt(r)} {_fmt(r)} 0 0 1 {_fmt(cx + r * math.cos(a1))} {_fmt(cy + r * math.sin(a1))}",
            stroke=2.4 if covered else 0.5,
        ))
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
    box = 7.0
    left = x - salvos * box / 2
    out: list[Primitive] = [Rect(left - 2, y - 7, salvos * box + 4, 14, fill=WHITE, stroke=1.2)]
    for i in range(salvos):
        cx = left + i * box + box / 2
        out.append(Path(f"M{_fmt(cx - 2.4)} {_fmt(y + 3)} L{_fmt(cx)} {_fmt(y - 3)} "
                        f"L{_fmt(cx + 2.4)} {_fmt(y + 3)} Z", fill=WHITE, stroke=0.8))
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
    "hold": _labelled(lambda: _("HOLD"), wide=True),
}

ICON_SETS: dict[str, dict] = {"fb": dict(_SHARED_ICONS), "ft2": dict(_SHARED_ICONS)}


def _icon(icon_set: str, system: dict, x: float, y: float, arcs: tuple[str, ...],
          out: bool) -> list[Primitive]:
    draw = ICON_SETS.get(icon_set, ICON_SETS["fb"]).get(system.get("type"))
    if draw is None:
        draw = _labelled(str(system.get("type", "?"))[:4].upper(), wide=True)
    prims = list(draw(system, x, y, arcs))
    if out:
        prims.append(_cross(x, y, 10.5))
    return prims


# ---- Placement ------------------------------------------------------------------------------------

WEAPONS = {
    "beam", "pulse_torpedo", "needle_beam", "nova_cannon", "wave_gun", "aa_battery",
    "sm_launcher", "sm_rack", "submunition",
}
BOTTOM_ROW = {"hold", "tug_drive", "tender_bay"}


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
    groups: dict[str, list[dict]] = {k: [] for k in ("fore", "port", "starboard", "aft", "centre", "bottom")}
    for system in design.get("systems", []):
        if not isinstance(system, dict):
            continue
        stype = system.get("type")
        if stype in BOTTOM_ROW:
            groups["bottom"].append(system)
        elif stype in WEAPONS:
            groups[_side(system.get("arcs", []), all_arcs)].append(system)
        else:
            groups["centre"].append(system)
    for key in ("fore", "port", "starboard", "aft", "centre"):
        groups[key].sort(key=lambda s: -_weight(s))
    return groups


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
    icon_set = getattr(rs, "icon_set", None) or rs.id
    damage = damage or {}
    systems_out = set(damage.get("systems_out") or [])
    hints = design.get("layout_hints") if isinstance(design.get("layout_hints"), dict) else {}

    size = box if box != "auto" else box_size(design, rs.id)
    width = BOX_WIDTHS.get(size, BOX_WIDTHS["medium"])
    prims: list[Primitive] = []

    groups = _classify(design, arcs)
    gap = 2 * ICON_RADIUS + 6
    y = 16.0

    def place(system: dict, x: float, cy: float) -> None:
        pinned = hints.get(system.get("uid")) if isinstance(hints.get(system.get("uid")), dict) else None
        if pinned:
            x = float(pinned.get("x", x))
            cy = float(pinned.get("y", cy))
        prims.extend(_icon(icon_set, system, x, cy, arcs, system.get("uid") in systems_out))

    # Fore weapons: rows across the top, largest first.
    per_row = max(1, int((width - 40) // gap))
    fore = groups["fore"]
    for start in range(0, len(fore), per_row):
        row = fore[start:start + per_row]
        x0 = width / 2 - (len(row) - 1) * gap / 2
        for i, system in enumerate(row):
            place(system, x0 + i * gap, y)
        y += gap

    # Port and starboard columns flank the centre block.
    side_rows = max(len(groups["port"]), len(groups["starboard"]))
    centre_top = y
    for i, system in enumerate(groups["port"]):
        place(system, 22.0, centre_top + i * gap)
    for i, system in enumerate(groups["starboard"]):
        place(system, width - 22.0, centre_top + i * gap)

    # All-round systems (C1 beams, PDS, fire controls) in central rows between the columns.
    inner = max(1, int((width - 100) // (2 * ICON_RADIUS)))
    centre = groups["centre"]
    cy = centre_top
    for start in range(0, len(centre), inner):
        row = centre[start:start + inner]
        step = 2 * ICON_RADIUS
        x0 = width / 2 - (len(row) - 1) * step / 2
        for i, system in enumerate(row):
            place(system, x0 + i * step, cy)
        cy += step
    y = max(cy, centre_top + side_rows * gap)

    # Aft-only weapons along the bottom of the system block.
    for start in range(0, len(groups["aft"]), per_row):
        row = groups["aft"][start:start + per_row]
        x0 = width / 2 - (len(row) - 1) * gap / 2
        for i, system in enumerate(row):
            place(system, x0 + i * gap, y)
        y += gap
    y += 4

    # Armour circles, then the damage track with its crew-factor stars and threshold marks.
    track = rs.damage_track(design)
    cf = set(rs.cf_positions(design))
    columns = max(max(track, default=1), 1)
    cell = min(11.0, (width - 24) / columns)
    left = width / 2 - columns * cell / 2

    armour = int(design.get("armour") or 0)
    if armour:
        per = min(armour, int((width - 24) // cell) or 1)
        for i in range(armour):
            ccx = left + (i % per) * cell + cell / 2
            ccy = y + (i // per) * cell + cell / 2
            prims.append(Circle(ccx, ccy, cell / 2 - 0.8, fill=WHITE, stroke=0.9))
            if i < int(damage.get("armour") or 0):
                prims.append(_slash(ccx - cell / 2, ccy - cell / 2, cell))
        y += math.ceil(armour / per) * cell + 2

    hull_done = int(damage.get("hull") or 0)
    numbered = 0
    for row_index, row_len in enumerate(track):
        for column in range(row_len):
            numbered += 1
            bx, by = left + column * cell, y + row_index * cell
            prims.append(Rect(bx, by, cell, cell, fill=WHITE, stroke=0.9))
            if numbered in cf:
                prims.append(_star(bx + cell / 2, by + cell / 2, cell * 0.3))
            if numbered <= hull_done:
                prims.append(_slash(bx, by, cell))
    y += len(track) * cell + 8

    # Bottom row: FTL, main drive with its thrust, core systems (FB), holds and tugs.
    if design.get("ftl"):
        prims.append(Rect(16, y, 20, 16, fill=WHITE, stroke=1.2))
        prims.append(Text(26, y + 11.5, _("FTL"), size=7, bold=True))
    thrust = int(design.get("thrust") or 0)
    prims.append(Path(f"M44 {_fmt(y + 16)} L44 {_fmt(y + 5)} L55 {_fmt(y - 1)} L66 {_fmt(y + 5)} "
                      f"L66 {_fmt(y + 16)} Z", fill=WHITE, stroke=1.3))
    prims.append(Text(55, y + 13.5, str(thrust), size=9.5, bold=True))
    if int(damage.get("drive_hits") or 0):
        prims.append(_cross(55, y + 8, 9))
    # The core systems box is part of every FB sheet; FT2 has no such box (FT p.14).
    if rs.id == "fb":
        bx = width - 86
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

    return Diagram(width, round(y + 6, 2), tuple(prims))


# ---- SVG (the app renders the same primitives the PDF does) -------------------------------------


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def to_svg(diagram: Diagram, class_name: str = "ssd") -> str:
    parts = [
        f'<svg viewBox="0 0 {_fmt(diagram.width)} {_fmt(diagram.height)}" '
        f'xmlns="http://www.w3.org/2000/svg" class="{class_name}">'
    ]
    for p in diagram.primitives:
        if isinstance(p, Rect):
            radius = f' rx="{_fmt(p.r)}"' if p.r else ""
            parts.append(f'<rect x="{_fmt(p.x)}" y="{_fmt(p.y)}" width="{_fmt(p.w)}" height="{_fmt(p.h)}"'
                         f'{radius} fill="{p.fill}" stroke="{"none" if not p.stroke else "black"}" '
                         f'stroke-width="{_fmt(p.stroke)}"/>')
        elif isinstance(p, Circle):
            parts.append(f'<circle cx="{_fmt(p.cx)}" cy="{_fmt(p.cy)}" r="{_fmt(p.r)}" fill="{p.fill}" '
                         f'stroke="{"none" if not p.stroke else "black"}" stroke-width="{_fmt(p.stroke)}"/>')
        elif isinstance(p, Line):
            parts.append(f'<line x1="{_fmt(p.x1)}" y1="{_fmt(p.y1)}" x2="{_fmt(p.x2)}" y2="{_fmt(p.y2)}" '
                         f'stroke="black" stroke-width="{_fmt(p.stroke)}"/>')
        elif isinstance(p, Path):
            parts.append(f'<path d="{p.d}" fill="{p.fill}" stroke="{"none" if not p.stroke else "black"}" '
                         f'stroke-width="{_fmt(p.stroke)}"/>')
        else:
            weight = ' font-weight="700"' if p.bold else ""
            parts.append(f'<text x="{_fmt(p.x)}" y="{_fmt(p.y)}" font-size="{_fmt(p.size)}" '
                         f'text-anchor="{p.anchor}" fill="{p.fill}"{weight}>{_escape(p.text)}</text>')
    parts.append("</svg>")
    return "".join(parts)
