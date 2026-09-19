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


def _int(value: object, default: int = 0) -> int:
    """Stored designs are semi-untrusted (imports), so a bad number counts as default instead of
    raising; validation reports what matters."""
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return default


def _systems(design: dict) -> list[dict]:
    systems = design.get("systems")
    return [s for s in systems if isinstance(s, dict)] if isinstance(systems, list) else []


def _arcs(system: dict) -> list[str]:
    arcs = system.get("arcs")
    return arcs if isinstance(arcs, list) else []


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
        lambda s: _("Hangar bay ({n} fighter groups)", n=max(1, _int(s.get("bays"), 1))),
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
}


def _hold_label(kind: object) -> str:
    return {
        "passenger": _("Passenger space"),
        "troop": _("Troop space"),
        "lab": _("Science labs"),
    }.get(kind if isinstance(kind, str) else "", _("Cargo hold"))


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
        BreakdownRow("hull_integrity", _("Hull integrity ({n} boxes)", n=boxes), boxes, 2 * boxes),
    ]
    if armour:
        rows.append(BreakdownRow("armour", _("Armour ({n} boxes)", n=armour), armour, 2 * armour))
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
        "ftl_mass": ftl_mass,
        "drive_mass": drive_mass,
        "turn_thrust": _turn_thrust(thrust),
        "hull_descriptor": _hull_descriptor(boxes, tmf),
        "damage_track": split_rows(boxes, 4),
        "crew_factors": crew_factors(design),
        "cf_positions": cf_positions(design),
        "thresholds": threshold_numbers(design),
        "holds": holds,
        "core_systems": True,  # always drawn on FB SSDs; the fleet option decides use (PLAN 6.2)
    }
    return Breakdown(tuple(rows), mass_used, points, derived)


def _turn_thrust(thrust: int) -> int:
    # FB1 p.5: half, rounded down; thrust 1 may always turn 1.
    return 1 if thrust == 1 else thrust // 2


def _hull_descriptor(boxes: int, tmf: int) -> str:
    percent = 100 * boxes / tmf if tmf else 0
    for low, label in data.HULL_DESCRIPTORS:
        if percent >= low:
            return data.translated_hull_descriptor(label)
    return data.translated_hull_descriptor("Fragile")


# ---- Damage track, crew, thresholds -------------------------------------------------------------


def damage_track(design: dict) -> list[int]:
    return split_rows(_int(design.get("hull_boxes")), 4)


def crew_factors(design: dict) -> int:
    # FB1 p.7: warships 1 CF per 20 MASS or part, merchants per 50.
    per = 50 if design.get("hull_kind") == "merchant" else 20
    return math.ceil(max(0, _int(design.get("tmf"))) / per)


def cf_positions(design: dict) -> list[int]:
    return common.cf_positions(max(0, _int(design.get("hull_boxes"))), crew_factors(design))


def threshold_numbers(design: dict) -> list[int]:
    # FB1 p.5: checks at the end of rows 1-3; core systems roll at +1.
    return [6, 5, 4]


# ---- Loadout --------------------------------------------------------------------------------


def _loadout_entries(loadout: object, key: str) -> list[dict]:
    if not isinstance(loadout, dict) or not isinstance(loadout.get(key), list):
        return []
    return [e for e in loadout[key] if isinstance(e, dict)]


def loadout_points(design: dict, loadout: dict | None, options: dict) -> int:
    """Fighter groups cost extra (FB1 p.11); salvos cost nothing beyond their magazine space."""
    if loadout is None:
        loadout = design.get("default_loadout")
    return sum(data.FIGHTER_POINTS.get(f.get("type"), 0) for f in _loadout_entries(loadout, "fighters"))


# ---- Type suggestion -----------------------------------------------------------------------------


def _pick_class(tmf: int, classes: tuple) -> tuple[str, str]:
    """The band containing tmf whose centre is nearest (ties go to the smaller class). Open-ended
    bands count their lower bound as the centre."""
    best = None
    for label, code, low, high in classes:
        if tmf < low or (high is not None and tmf > high):
            continue
        centre = low if high is None else (low + high) / 2
        dist = abs(tmf - centre)
        if best is None or dist < best[0]:
            best = (dist, label, code)
    if best is None:  # below the smallest band
        label, code = classes[0][0], classes[0][1]
        return data.translated_class_label(label), code
    return data.translated_class_label(best[1]), best[2]


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


ARCED_TYPES = {"beam", "pulse_torpedo", "needle_beam", "sm_launcher", "sm_rack", "nova_cannon", "wave_gun"}
SINGLE_ARC_TYPES = {"needle_beam", "nova_cannon", "wave_gun"}


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
    if stype == "beam":
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
    fed_by: dict[str, list[str]] = {}
    for s in systems:
        if s.get("type") != "sm_magazine":
            continue
        uid = s.get("uid")
        feeds = s.get("feeds") if isinstance(s.get("feeds"), list) else []
        if not feeds:
            violation("magazine_unlinked", _("This magazine feeds no launcher."), uid)
        for target in feeds:
            if not isinstance(target, str) or by_uid.get(target, {}).get("type") != "sm_launcher":
                violation("magazine_bad_feed", _("A magazine can only feed salvo missile launchers."), uid)
            else:
                fed_by.setdefault(target, []).append(uid)
    for s in systems:
        if s.get("type") != "sm_launcher":
            continue
        feeders = fed_by.get(s.get("uid"), [])
        if not feeders:
            violation("launcher_unfed", _("This launcher is not fed by a magazine."), s.get("uid"))
        elif len(feeders) > 1:
            violation("launcher_fed_twice", _("A launcher may be fed from one magazine only."), s.get("uid"))

    for entry in _loadout_entries(design.get("default_loadout"), "magazines"):
        mag = by_uid.get(entry.get("magazine"))
        if not mag or mag.get("type") != "sm_magazine":
            violation("salvos_without_magazine", _("Salvo load for a magazine this design does not have."))
            continue
        salvos = entry.get("salvos") if isinstance(entry.get("salvos"), list) else []
        if any(x not in data.SALVO_SPACE for x in salvos):
            violation("unknown_salvo_type", _("Unknown salvo type."), mag.get("uid"))
            continue
        used = sum(data.SALVO_SPACE[x] for x in salvos)
        capacity = _int(mag.get("capacity"))
        if used > capacity:
            violation(
                "magazine_overloaded",
                _("Salvo load needs {used} MASS but the magazine holds {cap}.", used=used, cap=capacity),
                mag.get("uid"),
            )


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
