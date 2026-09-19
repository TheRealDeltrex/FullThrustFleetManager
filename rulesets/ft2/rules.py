"""FT2 costing, derived values and validation for human tech (PLAN 6.3).

Design procedure FT pp.29-31, non-FTL ships FT p.25, tugs and tenders FT p.26, damage track
FT pp.10-12, More Thrust additions in mt.py. Checked against the page images.

Rounding: FT2 prints no rule for odd results. Owner decision: damage points round up; the same
direction is used for every other fraction (merchant hull 1.5 x MASS, drives, capacity), which
is also what the FT p.25 example does ("75% of 14, rounded up"). The one exception is merchant
capacity: FT p.29 grants "a MINIMUM of 1 MASS of weaponry" to small merchants, which only makes
sense if 10% rounds down.
"""

from __future__ import annotations

from i18n import _
from rulesets import Breakdown, BreakdownRow, Issue
from rulesets.common import arcs_valid
from rulesets.ft2 import data, mt


def _ceil_div(a: int, b: int) -> int:
    return -(-a // b)


def _int(value: object, default: int = 0) -> int:
    """Stored designs are semi-untrusted, so a bad number reads as default instead of raising."""
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


def _arcs(system: dict) -> list:
    arcs = system.get("arcs")
    return arcs if isinstance(arcs, list) else []


def _mass(design: dict) -> int:
    return max(0, _int(design.get("tmf")))


def _is_merchant(design: dict) -> bool:
    return design.get("hull_kind") == "merchant"


def ship_class(design: dict) -> str:
    """escort | cruiser | capital | supership, or merchant (FT p.29, MT p.22)."""
    if _is_merchant(design):
        return "merchant"
    m = _mass(design)
    if m <= data.ESCORT_MAX:
        return "escort"
    if m <= data.CRUISER_MAX:
        return "cruiser"
    return "capital" if m <= data.SHIP_MAX else "supership"


def _is_capital(design: dict) -> bool:
    return ship_class(design) in ("capital", "supership")


def standard_fire_controls(design: dict) -> int:
    cls = ship_class(design)
    if cls == "supership":
        return data.STANDARD_FIRE_CONTROLS["capital"] + mt.supership_extra_fire_controls(_mass(design))
    return data.STANDARD_FIRE_CONTROLS[cls]


def damage_points(design: dict) -> int:
    # FT p.29: warships half their MASS, merchants a quarter; odd results round up (owner).
    return _ceil_div(_mass(design), 4 if _is_merchant(design) else 2)


def _row_count(mass: int) -> int:
    # FT p.11: escorts 2 rows, cruisers 3, capitals 4; merchants use the box that fits their
    # size (FT p.12), so the same MASS bands apply. Superships add rows (MT p.22).
    if mass <= data.ESCORT_MAX:
        return 2
    if mass <= data.CRUISER_MAX:
        return 3
    return 4 + mt.supership_extra_rows(mass)


def damage_track(design: dict) -> list[int]:
    # FT p.12: "the UPPER lines should have fewer boxes", the opposite of FB.
    dp, rows = damage_points(design), _row_count(_mass(design))
    base, extra = divmod(dp, rows)
    return [base + (1 if i >= rows - extra else 0) for i in range(rows)]


def threshold_numbers(design: dict) -> list[int]:
    # One check per row end except the last: 6, 5, then 4+ for every later row (MT p.22).
    return [max(4, 6 - i) for i in range(_row_count(_mass(design)) - 1)]


def crew_factors(design: dict) -> int:
    return 0  # crew factors are a Fleet Book rule


def cf_positions(design: dict) -> list[int]:
    return []


def mass_limit(design: dict) -> int:
    """MASS available for weapons and systems (FT p.29, p.25; MT p.22)."""
    m = _mass(design)
    if _is_merchant(design):
        return max(1, m // 10)
    return _ceil_div(3 * m, 4) if design.get("ftl") is not True else _ceil_div(m, 2)


# ---- Per-system MASS and points ---------------------------------------------------------------


def _beam_class(s: dict) -> str:
    cls = s.get("class")
    return cls if cls in data.BEAMS else "C"


def _system_cost(s: dict, design: dict) -> tuple[int, int, str] | None:
    """(MASS, points, label) of one non-fire-control system; None for an unknown type."""
    stype, m = s.get("type"), _mass(design)
    if stype == "beam":
        cls = _beam_class(s)
        mass, base, per_arc = data.BEAMS[cls]
        return mass, base + per_arc * max(1, len(_arcs(s))), _("Class-{c} battery", c=cls)
    if stype == "screen":
        level = max(1, _int(s.get("level"), 1))
        mass, points = data.SCREEN_PER_LEVEL
        return mass * level, points * level, _("Screen level-{n}", n=level)
    if stype == "tug_drive":
        # FT p.26: a tug's FTL costs three times its MASS; the FTL row holds the first third.
        return 0, 2 * m, _("Tug/tender FTL (extra)")
    if stype in data.FIXED:
        mass, points = data.FIXED[stype]
        return mass, points, _system_label(stype)
    if stype in mt.SYSTEMS:
        mass_fn, points_fn = mt.SYSTEMS[stype]
        return mass_fn(m), points_fn(m), _system_label(stype)
    return None


def _system_label(stype: str) -> str:
    return {
        "pdaf": _("PDAF system"),
        "adaf": _("ADAF system"),
        "fighter_group": _("Fighter group incl. bay"),
        "needle_beam": _("Needle beam"),
        "pulse_torpedo": _("Pulse torpedo tube"),
        "nova_cannon": _("Spinal-mount nova cannon"),
        "submunition": _("Submunition pack"),
        "minelayer": _("Minelayer (3 mines)"),
        "minesweeper": _("Minesweeper"),
        "mt_missile": _("Missile (MT)"),
        "aa_battery": _("AA megabattery"),
        "wave_gun": _("Wave gun"),
        "ortillery": _("Ortillery system"),
        "reflex_field": _("Reflex field"),
        "cloak": _("Cloaking field"),
    }[stype]


# ---- Breakdown ------------------------------------------------------------------------------


def _drive_points(design: dict) -> int:
    m, thrust = _mass(design), max(0, _int(design.get("thrust")))
    if mt.is_supership(m):
        return 2 * m * thrust  # MT p.22
    # FT p.30: 1 x MASS per 4 thrust (escort), per 2 (cruiser), per 1 (capital, merchant).
    per = {"escort": 4, "cruiser": 2}.get(ship_class(design), 1)
    return _ceil_div(m * thrust, per)


def design_breakdown(design: dict, options: dict) -> Breakdown:
    m = _mass(design)
    merchant = _is_merchant(design)
    thrust = max(0, _int(design.get("thrust")))
    hull_points = _ceil_div(3 * m, 2) if merchant else 2 * m
    rows = [BreakdownRow("hull", _("Hull (MASS {n})", n=m), 0, hull_points)]
    if design.get("ftl") is True:
        rows.append(BreakdownRow("ftl", _("FTL drive"), 0, m))
    drive = _drive_points(design)
    if drive:
        rows.append(BreakdownRow("main_drive", _("Normal space drive (thrust {n})", n=thrust), 0, drive))

    free_fcs = standard_fire_controls(design)
    for s in _systems(design):
        uid = s.get("uid") if isinstance(s.get("uid"), str) else None
        if s.get("type") == "fire_control":
            if free_fcs > 0:
                free_fcs -= 1
                rows.append(BreakdownRow("fire_control", _("Fire control (standard)"), 0, 0, uid))
            else:
                mass, points = data.EXTRA_FIRE_CONTROL
                rows.append(BreakdownRow("fire_control", _("Fire control (extra)"), mass, points, uid))
            continue
        cost = _system_cost(s, design)
        if cost is None:
            rows.append(BreakdownRow(str(s.get("type")), _("Unknown system"), 0, 0, uid))
        else:
            rows.append(BreakdownRow(s["type"], cost[2], cost[0], cost[1], uid))

    derived = {
        "tmf": m,
        "class": ship_class(design),
        "hull_type": _hull_type(design),
        "mass_limit": mass_limit(design),  # FT2: MASS used may not exceed this
        "damage_points": damage_points(design),
        "damage_track": damage_track(design),
        "thresholds": threshold_numbers(design),
        "standard_fire_controls": standard_fire_controls(design),
        # FT p.5: an odd thrust's course-change share rounds UP.
        "turn_thrust": _ceil_div(thrust, 2),
        "crew_factors": 0,
        "cf_positions": [],
        "core_systems": False,
    }
    return Breakdown(tuple(rows), sum(r.mass for r in rows), sum(r.points for r in rows), derived)


def _hull_type(design: dict) -> str:
    """ "standard" if the MASS is one of the FT p.14 basic hulls of its kind, else "special"."""
    m = _mass(design)
    kinds = ("merchant",) if _is_merchant(design) else ("escort", "cruiser", "capital", "carrier")
    return "standard" if any(m == c[2] for k in kinds for c in data.BASIC_CLASSES[k]) else "special"


# ---- Loadout and More Thrust requirements ------------------------------------------------------


def _loadout_entries(loadout: object, key: str) -> list[dict]:
    if not isinstance(loadout, dict) or not isinstance(loadout.get(key), list):
        return []
    return [e for e in loadout[key] if isinstance(e, dict)]


def loadout_points(design: dict, loadout: dict | None, options: dict) -> int:
    """FT2 fighter groups are paid for in the design (FT p.31); the loadout adds only the MT
    specialised-type surcharge (MT p.12)."""
    if loadout is None:
        loadout = design.get("default_loadout")
    return sum(mt.FIGHTER_SURCHARGE.get(f.get("type"), 0) for f in _loadout_entries(loadout, "fighters"))


def required_options(design: dict, loadout: dict | None) -> set[str]:
    needed = set()
    if any(s.get("type") in mt.SYSTEMS for s in _systems(design)):
        needed.add("mt_systems")
    if mt.is_supership(_mass(design)):
        needed.add("mt_superships")
    if loadout is None:
        loadout = design.get("default_loadout")
    if any(mt.fighter_requires_toggle(f.get("type")) for f in _loadout_entries(loadout, "fighters")):
        needed.add("mt_fighters")
    return needed


# ---- Type suggestion -----------------------------------------------------------------------------


def suggest_type(design: dict) -> tuple[str, str]:
    """Nearest FT p.14 basic class of the same kind (ties to the smaller)."""
    m = _mass(design)
    cls = ship_class(design)
    groups = sum(1 for s in _systems(design) if s.get("type") == "fighter_group")
    if cls in ("capital", "supership") and groups >= data.CARRIER_MIN_GROUPS:
        table = data.BASIC_CLASSES["carrier"]
    elif cls == "supership":
        table = data.BASIC_CLASSES["capital"]
    else:
        table = data.BASIC_CLASSES[cls]
    label, code, _mass_ = min(table, key=lambda c: (abs(c[2] - m), c[2]))
    return data.class_label(label), code


# ---- Validation ---------------------------------------------------------------------------------


def validate_design(design: dict, options: dict) -> list[Issue]:
    issues: list[Issue] = []

    def violation(code: str, message: str, uid: str | None = None) -> None:
        issues.append(Issue(code, "violation", message, uid))

    options = options if isinstance(options, dict) else {}
    m, merchant = _mass(design), _is_merchant(design)
    if m < (data.MERCHANT_MIN if merchant else 1):
        violation("bad_tmf", _("MASS must be at least {n}.", n=data.MERCHANT_MIN if merchant else 1))
    if mt.is_supership(m) and not options.get("mt_superships"):
        violation("mass_over_100", _("Ships over MASS 100 need the More Thrust superships option."))
    thrust = _int(design.get("thrust"))
    if thrust > data.MAX_THRUST:
        violation("thrust_over_max", _("Thrust cannot exceed {n}.", n=data.MAX_THRUST))
    if thrust < 0:
        violation("negative_value", _("Thrust cannot be negative."))
    if _int(design.get("armour")) != 0:
        violation("no_armour_in_ft2", _("FT2 ships have no armour."))
    if design.get("streamlining") not in (None, "none"):
        violation("no_streamlining_in_ft2", _("FT2 ships have no streamlining."))

    b = design_breakdown(design, options)
    limit = b.derived["mass_limit"]
    if b.mass_used > limit:
        violation(
            "mass_over",
            _("Systems use {used} MASS; this hull carries {limit}.", used=b.mass_used, limit=limit),
        )

    systems = _systems(design)
    by_uid = {s["uid"]: s for s in systems if isinstance(s.get("uid"), str)}
    capital = _is_capital(design)
    for s in systems:
        uid = s.get("uid") if isinstance(s.get("uid"), str) else None
        stype = s.get("type")
        if stype != "fire_control" and _system_cost(s, design) is None:
            violation("unknown_system", _("Unknown system type: {t}.", t=str(stype)), uid)
            continue
        if stype in mt.SYSTEMS and not options.get("mt_systems"):
            violation(
                "mt_toggle_off", _("This More Thrust system needs the More Thrust systems option."), uid
            )
        if stype == "beam" and s.get("class") not in data.BEAMS:
            violation("beam_class", _("Beam batteries are class A, B or C."), uid)
        if stype == "screen" and not 1 <= _int(s.get("level"), 1) <= data.MAX_SCREEN_LEVEL:
            violation("screen_level", _("Screens have levels 1 to 3."), uid)
        if stype in data.CAPITAL_ONLY and not capital:
            violation("capital_only", _("Only capital ships may mount this system."), uid)
        if merchant and (
            stype not in data.MERCHANT_SYSTEMS
            or (stype == "beam" and s.get("class") != "C")
            or (stype == "screen" and _int(s.get("level"), 1) > 1)
        ):
            violation(
                "merchant_system",
                _("Merchants may carry only C batteries, PDAF, level-1 screens and submunitions."),
                uid,
            )
        if stype == "tug_drive":
            if not merchant:
                violation("tug_not_merchant", _("Tugs and tenders are merchant ships."), uid)
            if design.get("ftl") is not True:
                violation("tug_without_ftl", _("A tug or tender needs an FTL drive."), uid)
        _validate_arcs(s, uid, violation)

    for entry in _loadout_entries(design.get("default_loadout"), "fighters"):
        group = by_uid.get(entry.get("hangar"))
        if not group or group.get("type") != "fighter_group":
            violation(
                "fighters_without_hangar",
                _("Fighter type set for a fighter group this design does not have."),
            )
            continue
        if entry.get("type") not in mt.FIGHTER_SURCHARGE:
            violation("unknown_fighter_type", _("Unknown fighter type."), group["uid"])
        elif mt.fighter_requires_toggle(entry.get("type")) and not options.get("mt_fighters"):
            violation(
                "mt_toggle_off", _("Specialised fighters need the More Thrust fighters option."), group["uid"]
            )
    if _loadout_entries(design.get("default_loadout"), "magazines"):
        violation("salvos_without_magazine", _("FT2 ships have no salvo missile magazines."))

    if design.get("ftl") is not True:
        issues.append(Issue("no_ftl", "info", _("No FTL drive: this is a system defence ship.")))
    return issues


def _validate_arcs(s: dict, uid: str | None, violation) -> None:
    stype = s.get("type")
    if stype not in data.OFFENSIVE:
        return
    arcs = s.get("arcs")
    if stype == "submunition" and arcs is None:
        return
    if not arcs_valid(arcs, data.ARCS):
        violation(
            "bad_arcs", _("Choose at least one fire arc ({arcs}), each once.", arcs=", ".join(data.ARCS)), uid
        )
        return
    if "A" in arcs:
        violation("aft_arc", _("No offensive weapon may fire through the aft arc."), uid)
    if stype in data.SINGLE_ARC and len(arcs) != 1:
        violation("single_arc", _("This weapon fires through one arc only."), uid)
    if stype in data.FORE_ONLY and arcs != ["F"]:
        violation("fore_only", _("This weapon fires straight ahead only."), uid)
