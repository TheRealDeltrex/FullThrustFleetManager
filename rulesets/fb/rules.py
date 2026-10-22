"""FB costing, derived values and validation for human tech (PLAN 6.2).

Design procedure FB1 pp.10-11, MASS and points table FB1 p.11, hull boxes FB2 p.3, damage track
FB1 p.5, crew factors FB1 pp.7-8, holds/tugs/tenders FB1 p.8, salvo missiles FB1 p.9.
"""

from __future__ import annotations

import math
from collections.abc import Callable

from i18n import _
from rulesets import Breakdown, BreakdownRow, Issue, common
from rulesets.common import (
    ARCS,
    arcs_contiguous,
    arcs_valid,
    pct_mass,
    round_half_up,
    split_rows,
)
from rulesets.fb import data

STREAMLINING_PERCENT = {"none": 0, "partial": 10, "full": 20}


# The shared readers and labels (rulesets/common.py), under the names the FB modules use.
_int = common.as_int
_systems = common.systems_of
_arcs = common.arcs_of
_loadout_entries = common.loadout_entries
_turn_thrust = common.half_turn_thrust
_hangar_label = common.hangar_label
_hold_label = common.hold_label


# ---- Per-system MASS and points ---------------------------------------------------------------


def _beam_mass(system: dict, tmf: int) -> int:
    cls = max(1, _int(system.get("class"), 1))
    n = max(1, len(_arcs(system)))
    if cls == 1:
        return 1
    if cls == 2:
        # 3 adjacent arcs at base; a full 6-arc turret costs 50% more (FB1 p.7).
        return 3 if n > 3 else 2
    base = 2 ** (cls - 1)
    return base + (base // 4) * (n - 1)  # +25% of base per extra arc


def _screen_mass(system: dict, tmf: int) -> int:
    level = max(1, _int(system.get("level"), 1))
    mass = max(3, pct_mass(tmf, 5)) if level == 1 else max(6, pct_mass(tmf, 10))
    # Generators beyond level 2 are backups at 5% each (FB1 p.7).
    return mass + max(0, level - 2) * pct_mass(tmf, 5)


def _magazine_mass(system: dict, tmf: int) -> int:
    return max(1, _int(system.get("capacity"), 0))


def _graser_mass(system: dict, tmf: int) -> int:
    """The Star Ranger graser table, as CD p.45: class 1 is 2 for one arc, 3 for three, 4 for
    more; class 2 is 9 +3 per extra arc, class 3 is 24 +6, each larger class triples the base and
    doubles the extra."""
    cls = max(1, _int(system.get("class"), 1))
    n = max(1, len(_arcs(system)))
    if cls == 1:
        return 2 if n <= 1 else 3 if n <= 3 else 4
    base = 9 if cls == 2 else 24 * 3 ** (cls - 3)
    return base + 3 * 2 ** (cls - 2) * (n - 1)


# type -> (mass(system, tmf), points(system, mass), label(system))
SystemRule = tuple[Callable[[dict, int], int], Callable[[dict, int], int], Callable[[dict], str]]

SYSTEM_RULES: dict[str, SystemRule] = {
    "beam": (
        _beam_mass,
        lambda s, m: 3 if _int(s.get("class"), 1) <= 1 else 3 * m,
        lambda s: _("Class-{n} beam battery", n=_int(s.get("class"), 1)),
    ),
    "pulse_torpedo": (
        lambda s, t: 4 + max(0, len(_arcs(s)) - 1),
        lambda s, m: 3 * m,
        lambda s: _("Pulse torpedo"),
    ),
    "needle_beam": (lambda s, t: 2, lambda s, m: 6, lambda s: _("Needle beam")),
    # The Star Ranger fleet pages' extra weapons. An EMP battery has the MASS and cost of a beam
    # of its class and arcs (ORC page); a graser costs 4 x MASS, or 3 x on the NAC's version
    # that may not re-roll (UNSC and NAC pages); an anti-matter torpedo is MASS 2, 8 points.
    "emp": (
        _beam_mass,
        lambda s, m: 3 if _int(s.get("class"), 1) <= 1 else 3 * m,
        lambda s: _("Class-{n} EMP battery", n=_int(s.get("class"), 1)),
    ),
    # The Crusty rocket cannon: "same mass, cost, arcs and range bands as a beam battery of the
    # same size" (Star Ranger Crusty page).
    "rocket_cannon": (
        _beam_mass,
        lambda s, m: 3 if _int(s.get("class"), 1) <= 1 else 3 * m,
        lambda s: _("Class-{n} rocket cannon", n=_int(s.get("class"), 1)),
    ),
    "graser": (
        _graser_mass,
        lambda s, m: (3 if s.get("no_reroll") else 4) * m,
        lambda s: _("Class-{n} graser", n=_int(s.get("class"), 1)),
    ),
    "amt": (lambda s, t: 2, lambda s, m: 8, lambda s: _("Anti-matter torpedo")),
    # The New Israeli long-range pulse torpedo: MASS 8 +2 per extra arc, 3 points a MASS.
    "lrpt": (
        lambda s, t: 8 + 2 * max(0, len(_arcs(s)) - 1),
        lambda s, m: 3 * m,
        lambda s: _("Long-range pulse torpedo"),
    ),
    # The IJSF's spinal hyperspatial distortion cannon: MASS class x 8 - 4, 3 points a MASS.
    "hdc": (
        lambda s, t: 8 * max(1, _int(s.get("class"), 1)) - 4,
        lambda s, m: 3 * m,
        lambda s: _("Class-{n} hyperspatial distortion cannon", n=_int(s.get("class"), 1)),
    ),
    "superior_sensors": (lambda s, t: 2, lambda s, m: 30, lambda s: _("Superior sensors")),
    "enhanced_sensors": (lambda s, t: 2, lambda s, m: 8, lambda s: _("Enhanced sensors")),  # as CD/PC
    "submunition": (lambda s, t: 1, lambda s, m: 3, lambda s: _("Submunition pack")),
    "sm_launcher": (lambda s, t: 3, lambda s, m: 9, lambda s: _("Salvo missile launcher")),
    "sm_magazine": (
        _magazine_mass,
        lambda s, m: 3 * m,
        lambda s: _("SM magazine (capacity {n})", n=_int(s.get("capacity"), 0)),
    ),
    "sm_rack": (
        lambda s, t: 5 if s.get("load") == "er" else 4,
        lambda s, m: 15 if s.get("load") == "er" else 12,
        lambda s: _("Salvo missile rack (ER)") if s.get("load") == "er" else _("Salvo missile rack"),
    ),
    "pds": (lambda s, t: 1, lambda s, m: 3, lambda s: _("Point defence system")),
    "fire_control": (lambda s, t: 1, lambda s, m: 4, lambda s: _("Fire control")),
    "adfc": (lambda s, t: 2, lambda s, m: 8, lambda s: _("Area-defence fire control")),
    "screen": (
        _screen_mass,
        lambda s, m: 3 * m,
        lambda s: _("Screen level-{n}", n=max(1, _int(s.get("level"), 1))),
    ),
    "hangar": (
        lambda s, t: data.FIGHTER_BAY_MASS * max(1, _int(s.get("bays"), 1)),
        lambda s, m: 3 * m,
        lambda s: _hangar_label(max(1, _int(s.get("bays"), 1))),
    ),
    "tender_bay": (
        lambda s, t: max(1, round_half_up(3 * max(1, _int(s.get("capacity"), 1)), 2)),
        lambda s, m: 3 * m,
        lambda s: _("Tender bay (carries MASS {n})", n=max(1, _int(s.get("capacity"), 1))),
    ),
    "nova_cannon": (lambda s, t: 20, lambda s, m: 60, lambda s: _("Nova cannon")),
    "wave_gun": (lambda s, t: 12, lambda s, m: 36, lambda s: _("Wave gun")),
    "mt_missile": (lambda s, t: 2, lambda s, m: 6, lambda s: _("Missile (MT type)")),
    "ortillery": (lambda s, t: 3, lambda s, m: 9, lambda s: _("Ortillery system")),
    "minelayer": (
        lambda s, t: 2 + max(0, _int(s.get("mines"), 0)),
        lambda s, m: 6 + 2 * (m - 2),
        lambda s: _("Minelayer ({n} mines)", n=max(0, _int(s.get("mines"), 0))),
    ),
    "minesweeper": (lambda s, t: 5, lambda s, m: 15, lambda s: _("Minesweeper")),
    "reflex_field": (lambda s, t: max(10, pct_mass(t, 10)), lambda s, m: 6 * m, lambda s: _("Reflex field")),
    "cloak": (lambda s, t: max(2, pct_mass(t, 10)), lambda s, m: 10 * m, lambda s: _("Cloaking field")),
    "tug_drive": (
        # FB1 p.8: 20% of the towable MASS on top of the tug's own 10% FTL drive.
        lambda s, t: pct_mass(max(1, _int(s.get("tow_mass"), 1)), 20),
        lambda s, m: 2 * m,
        lambda s: _("Tug jump drive (tows MASS {n})", n=max(1, _int(s.get("tow_mass"), 1))),
    ),
    "hold": (
        lambda s, t: max(1, _int(s.get("mass"), 1)),
        lambda s, m: 0,
        lambda s: _hold_label(s.get("kind")),
    ),
    # An old design's "mass penalty for age" on the Star Ranger pages: MASS it cannot use.
    "age_penalty": (
        lambda s, t: max(1, _int(s.get("mass"), 1)),
        lambda s, m: 0,
        lambda s: _("MASS lost to age ({n})", n=max(1, _int(s.get("mass"), 1))),
    ),
}


# ---- Breakdown ------------------------------------------------------------------------------


def design_breakdown(design: dict, options: dict) -> Breakdown:
    tmf = max(0, _int(design.get("tmf")))
    boxes = max(0, _int(design.get("hull_boxes")))
    armour = max(0, _int(design.get("armour")))
    thrust = max(0, _int(design.get("thrust")))
    ftl_mass = pct_mass(tmf, 10) if design.get("ftl") is True and tmf > 0 else 0
    drive_mass = pct_mass(tmf, 5 * thrust) if thrust > 0 and tmf > 0 else 0
    stream_pct = STREAMLINING_PERCENT.get(design.get("streamlining"), 0)
    stream_mass = pct_mass(tmf, stream_pct) if stream_pct and tmf > 0 else 0

    rows = [
        BreakdownRow("hull", _("Basic hull (MASS {n})", n=tmf), 0, tmf),
        BreakdownRow("hull_integrity", _hull_label(design, boxes), boxes, hull_integrity_points(design)),
    ]
    if armour:
        rows.append(BreakdownRow("armour", _("Armour ({n} boxes)", n=armour), armour, 2 * armour))
    stealth = stealth_level(design)
    if stealth:
        # The New Israeli stealth hulls (Star Ranger NI page): no MASS, 2 points a hull or
        # armour box per level.
        rows.append(BreakdownRow("stealth_hull", _("Stealth hull level-{n}", n=stealth), 0,
                                 2 * stealth * (boxes + armour)))
    if drive_mass:
        rows.append(
            BreakdownRow("main_drive", _("Main drive (thrust-{n})", n=thrust), drive_mass, 2 * drive_mass)
        )
    if ftl_mass:
        rows.append(BreakdownRow("ftl", _("FTL drive"), ftl_mass, 2 * ftl_mass))
    if stream_mass:
        label = _("Full streamlining") if design.get("streamlining") == "full" else _("Partial streamlining")
        rows.append(BreakdownRow("streamlining", label, stream_mass, 2 * stream_mass))

    holds = []
    for s in _systems(design):
        rule = SYSTEM_RULES.get(s.get("type"))
        uid = s.get("uid") if isinstance(s.get("uid"), str) else None
        if rule is None:
            rows.append(BreakdownRow(str(s.get("type")), _("Unknown system"), 0, 0, uid))
            continue
        mass_fn, points_fn, label_fn = rule
        mass = mass_fn(s, tmf)
        rows.append(BreakdownRow(s["type"], label_fn(s), mass, points_fn(s, mass), uid))
        if s["type"] == "hold":
            kind = s.get("kind") if s.get("kind") in ("cargo", "passenger", "troop", "lab") else "cargo"
            holds.append({"uid": uid, "kind": kind, "spaces": split_rows(mass, 4)})

    mass_used = sum(r.mass for r in rows)
    points = sum(r.points for r in rows)
    derived = {
        "tmf": tmf,
        "mass_limit": tmf,  # FB: MASS used must equal TMF exactly
        "ftl_mass": ftl_mass,
        "drive_mass": drive_mass,
        "turn_thrust": _turn_thrust(thrust),
        "hull_descriptor": _hull_descriptor(boxes, tmf),
        "damage_track": damage_track(design),
        "hull_row_choices": HULL_ROW_CHOICES,
        "crew_factors": crew_factors(design),
        "cf_positions": cf_positions(design),
        "thresholds": threshold_numbers(design),
        "holds": holds,
        "core_systems": True,  # always drawn on FB SSDs; the fleet option decides use (PLAN 6.2)
    }
    return Breakdown(tuple(rows), mass_used, points, derived)


def _hull_descriptor(boxes: int, tmf: int) -> str:
    return common.hull_descriptor(boxes, tmf, data.HULL_DESCRIPTORS)


# ---- Damage track, crew, thresholds -------------------------------------------------------------


# The GZG-authorized designs on the Star Ranger fleet pages (data/catalog/fb_starranger.json)
# print each hull's row split and price a box by its rows, as Kra'Vak-style three-row hulls and
# Project Continuum's five and six (PC p.108) do: x3, x2, x1.5, x1. Four rows is FB1's track.
HULL_ROW_CHOICES = (3, 4, 5, 6)


def stealth_level(design: dict) -> int:
    level = _int(design.get("stealth_hull"), 0)
    return level if level in (1, 2) else 0


def hull_rows(design: dict) -> int:
    rows = _int(design.get("hull_rows"), 4)
    return rows if rows in HULL_ROW_CHOICES else 4


def hull_integrity_points(design: dict) -> int:
    """2 a box on four rows; x3 / x1.5 / x1 on three / five / six (.5 up). A hull of three
    boxes or fewer can only be drawn on three rows, so it costs 2 a box however it is drawn
    (owner's ruling: a ship is not dearer for being small)."""
    boxes = max(0, _int(design.get("hull_boxes")))
    halves = {3: 6, 4: 4, 5: 3, 6: 2}[hull_rows(design)] if boxes > 3 else 4
    return round_half_up(halves * boxes, 2)


def _hull_label(design: dict, boxes: int) -> str:
    rows = hull_rows(design)
    if rows == 4:
        return _("Hull integrity ({n} boxes)", n=boxes)
    return _("Hull integrity ({n} boxes, {rows} rows)", n=boxes, rows=rows)


def damage_track(design: dict) -> list[int]:
    return split_rows(_int(design.get("hull_boxes")), hull_rows(design))


def crew_factors(design: dict) -> int:
    # FB1 p.7: warships 1 CF per 20 MASS or part, merchants per 50.
    per = 50 if design.get("hull_kind") == "merchant" else 20
    return math.ceil(max(0, _int(design.get("tmf"))) / per)


def cf_positions(design: dict) -> list[int]:
    return common.cf_positions(max(0, _int(design.get("hull_boxes"))), crew_factors(design))


def threshold_numbers(design: dict) -> list[int]:
    # FB1 p.5: checks at the end of rows 1-3; core systems roll at +1. The Star Ranger pages
    # give a three-row hull 6 and 5, five rows 6 to 3 and six rows 6 to 2.
    return [6, 5, 4, 3, 2][: hull_rows(design) - 1]


# ---- Loadout --------------------------------------------------------------------------------


def loadout_points(design: dict, loadout: dict | None, options: dict) -> int:
    """Fighter groups cost extra (FB1 p.11); salvos cost nothing beyond their magazine space."""
    if loadout is None:
        loadout = design.get("default_loadout")
    return sum(data.FIGHTER_POINTS.get(f.get("type"), 0) for f in _loadout_entries(loadout, "fighters"))


# ---- Type suggestion -----------------------------------------------------------------------------


_pick_class = common.pick_class


def suggest_type(design: dict) -> tuple[str, str]:
    tmf = max(0, _int(design.get("tmf")))
    if design.get("hull_kind") == "merchant":
        # FB1 p.42 names merchant designs, not a classification; "M" is the app's code.
        return data.translated_class_label("Merchant"), "M"
    bays = sum(max(1, _int(s.get("bays"), 1)) for s in _systems(design) if s.get("type") == "hangar")
    if bays >= data.CARRIER_MIN_BAYS and tmf >= data.CARRIER_CLASSES[0][2]:
        return _pick_class(tmf, data.CARRIER_CLASSES)
    return _pick_class(tmf, data.SHIP_CLASSES)


# ---- Validation ---------------------------------------------------------------------------------


def validate_design(design: dict, options: dict) -> list[Issue]:
    issues: list[Issue] = []

    def violation(code: str, message: str, uid: str | None = None) -> None:
        issues.append(Issue(code, "violation", message, uid))

    def info(code: str, message: str, uid: str | None = None) -> None:
        issues.append(Issue(code, "info", message, uid))

    tmf = _int(design.get("tmf"))
    boxes = _int(design.get("hull_boxes"))
    if tmf <= 0:
        violation("bad_tmf", _("Total MASS must be at least 1."))
    b = design_breakdown(design, options)
    if b.mass_used > tmf:
        violation(
            "mass_over", _("MASS used ({used}) exceeds the total MASS ({tmf}).", used=b.mass_used, tmf=tmf)
        )
    elif b.mass_used < tmf:
        violation(
            "mass_under",
            _("MASS used ({used}) is less than the total MASS ({tmf}).", used=b.mass_used, tmf=tmf),
        )
    # FB2 p.3: at least 10% of total MASS. Rounded like every percentage (FB1 p.10), because FB2
    # says FB1's Fragile (exactly 10%, rounded) designs stay legal.
    if tmf > 0 and boxes < pct_mass(tmf, 10):
        violation(
            "hull_below_minimum",
            _("Hull integrity needs at least {n} boxes (10% of MASS).", n=pct_mass(tmf, 10)),
        )
    if _int(design.get("thrust")) < 0 or _int(design.get("armour")) < 0:
        violation("negative_value", _("Thrust and armour cannot be negative."))

    systems = _systems(design)
    by_uid = {s["uid"]: s for s in systems if isinstance(s.get("uid"), str)}
    for s in systems:
        uid = s.get("uid") if isinstance(s.get("uid"), str) else None
        stype = s.get("type")
        if stype not in SYSTEM_RULES:
            violation("unknown_system", _("Unknown system type: {t}.", t=str(stype)), uid)
            continue
        _validate_arcs(s, uid, violation)

    _validate_missiles(design, systems, by_uid, violation)
    _validate_fighters(design, systems, by_uid, violation)

    if not any(s.get("type") == "fire_control" for s in systems):
        info("no_fire_control", _("No fire control: weapons that need one cannot fire."))
    if design.get("ftl") is not True:
        info("no_ftl", _("No FTL drive: this is a system defence ship."))
    for s in systems:
        if s.get("type") == "screen" and _int(s.get("level"), 1) > 2:
            info("screen_backups", _("Screen generators beyond level 2 are backups only."), s.get("uid"))
    return issues


ARCED_TYPES = {
    "beam", "emp", "rocket_cannon", "graser", "pulse_torpedo", "needle_beam", "sm_launcher",
    "sm_rack", "nova_cannon", "wave_gun", "hdc", "lrpt",
}
SINGLE_ARC_TYPES = {"needle_beam", "nova_cannon", "wave_gun", "hdc"}


def _validate_arcs(s: dict, uid: str | None, violation) -> None:
    stype = s["type"]
    arcs = s.get("arcs")
    if stype == "submunition" and arcs is None:
        return  # arcs optional; the SSD draws the pack's firing arc when given
    if stype not in ARCED_TYPES and stype != "submunition":
        return
    if not arcs_valid(arcs):
        violation(
            "bad_arcs", _("Choose at least one fire arc ({arcs}), each once.", arcs=", ".join(ARCS)), uid
        )
        return
    if stype in ("beam", "emp", "rocket_cannon"):
        cls = _int(s.get("class"), 1)
        if cls == 1 and len(arcs) != 6:
            violation("beam_arcs", _("A class-1 battery always fires through all six arcs."), uid)
        elif cls == 2 and not (len(arcs) == 6 or (len(arcs) == 3 and arcs_contiguous(arcs))):
            violation("beam_arcs", _("A class-2 battery fires through 3 adjacent arcs or all six."), uid)
        elif cls < 1:
            violation("beam_arcs", _("Beam class must be at least 1."), uid)
    elif stype == "pulse_torpedo" and (len(arcs) > 3 or not arcs_contiguous(arcs)):
        # FB1 p.7: the tube "traverses" through up to three arcs, so they must be adjacent.
        violation("torpedo_arcs", _("A pulse torpedo covers at most 3 adjacent arcs."), uid)
    elif stype in SINGLE_ARC_TYPES and len(arcs) != 1:
        violation(
            "needle_arcs" if stype == "needle_beam" else "single_arc",
            _("This weapon fires through one arc only."),
            uid,
        )


def _validate_missiles(design: dict, systems: list[dict], by_uid: dict, violation) -> None:
    common.validate_missiles(design, systems, by_uid, violation,
                             lambda entry, salvo: data.SALVO_SPACE.get(salvo))


def _validate_fighters(design: dict, systems: list[dict], by_uid: dict, violation) -> None:
    per_hangar: dict[str, int] = {}
    for entry in _loadout_entries(design.get("default_loadout"), "fighters"):
        hangar = by_uid.get(entry.get("hangar"))
        if not hangar or hangar.get("type") != "hangar":
            violation(
                "fighters_without_hangar", _("Fighter group assigned to a hangar this design does not have.")
            )
            continue
        if entry.get("type") not in data.FIGHTER_POINTS:
            violation("unknown_fighter_type", _("Unknown fighter type."), hangar["uid"])
        per_hangar[hangar["uid"]] = per_hangar.get(hangar["uid"], 0) + 1
    for uid, groups in per_hangar.items():
        bays = max(1, _int(by_uid[uid].get("bays"), 1))
        if groups > bays:
            violation(
                "hangar_overfull",
                _("{groups} fighter groups in a hangar with {bays} bays.", groups=groups, bays=bays),
                uid,
            )


# ---- Tech-module interface (rulesets/fb/tech.py) -------------------------------------------------

ICON_SET = "fb"
CREWED = True
FIGHTER_POINTS = data.FIGHTER_POINTS
system_defs = data.system_defs
