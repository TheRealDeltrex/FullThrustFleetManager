"""FB ruleset, Kra'Vak tech (FB2 pp.9-11).

Design procedure FB2 pp.10-11, weapons and defences FB2 pp.9-10, crew factors FB2 p.10. Hull
integrity, damage track, crew factors, thresholds, holds and tender bays follow the human rules
(FB2 p.9 says so in as many words), so they are imported from `rules` rather than restated.

Two differences from human tech carry the whole race:
- the Advanced Grav Drive costs 3 points per MASS instead of 2 (FB2 p.9);
- the weapon suite is K-guns, MKP packs and one-shot scatterguns, and nothing else. Kra'Vak
  ships carry no energy screens (FB2 p.8) and need no ADFC, because scatterguns have area
  defence built in (FB2 p.10).

Points and MASS are checked against the FB2 p.11 worked example (NPV 384) and every printed
TMF/NPV panel on pp.12-19 by tests/test_rules_fb_kravak.py and the NPV gate.
"""

from __future__ import annotations

from collections.abc import Callable

from i18n import _
from rulesets import Breakdown, BreakdownRow, Issue, ParamDef, SystemDef, common
from rulesets.common import ARCS, arcs_contiguous, arcs_valid, pct_mass, split_rows
from rulesets.fb import data
from rulesets.fb.rules import (
    _arcs,
    _int,
    _systems,
    cf_positions,
    crew_factors,
    damage_track,
    suggest_type,
    threshold_numbers,
)
from rulesets.fb.rules import _hull_descriptor as _hull_descriptor

__all__ = [
    "SYSTEM_RULES",
    "cf_positions",
    "crew_factors",
    "damage_track",
    "design_breakdown",
    "kgun_mass",
    "loadout_points",
    "suggest_type",
    "system_defs",
    "threshold_numbers",
    "validate_design",
]

ICON_SET = "fb_kravak"
CREWED = True  # crew factors and damage control parties


def kgun_mass(cls: int, arc_count: int) -> int:
    """FB2 p.9: K-1 (all-arc) 2, K-2 one arc 3 / two arcs 4, K-3 5, K-4 8, K-5 11, K-6 14,
    "the mass required rises by 3 per additional class" above that."""
    if cls <= 1:
        return 2
    if cls == 2:
        return 4 if arc_count > 1 else 3
    return 5 + 3 * (cls - 3)


def _kgun_mass(system: dict, tmf: int) -> int:
    return kgun_mass(max(1, _int(system.get("class"), 1)), max(1, len(_arcs(system))))


# type -> (mass(system, tmf), points(system, mass), label(system)); see rules.SYSTEM_RULES.
SystemRule = tuple[Callable[[dict, int], int], Callable[[dict, int], int], Callable[[dict], str]]

SYSTEM_RULES: dict[str, SystemRule] = {
    "kgun": (
        _kgun_mass,
        lambda s, m: 4 * m,
        lambda s: _("Class-{n} K-gun", n=max(1, _int(s.get("class"), 1))),
    ),
    "mkp": (lambda s, t: 1, lambda s, m: 4, lambda s: _("MKP pack")),
    "scattergun": (lambda s, t: 1, lambda s, m: 5, lambda s: _("Scattergun")),
    "fire_control": (lambda s, t: 1, lambda s, m: 4, lambda s: _("Fire control")),
    # FB2 p.10 prints "9 MASS and costs 18 points" for a fighter bay, but every Kra'Vak design
    # in the book (Lo'Vok 626, Yu'Kas 883, Ko'San 917) costs its bays at the human 3 points per
    # MASS, ie: 27. The printed 18 is the Ra'San fighter group's own cost (same page).
    "hangar": (
        lambda s, t: data.FIGHTER_BAY_MASS * max(1, _int(s.get("bays"), 1)),
        lambda s, m: 3 * m,
        lambda s: _("Hangar bay ({n} fighter groups)", n=max(1, _int(s.get("bays"), 1))),
    ),
    "tender_bay": (
        lambda s, t: max(1, common.round_half_up(3 * max(1, _int(s.get("capacity"), 1)), 2)),
        lambda s, m: 3 * m,
        lambda s: _("Tender bay (carries MASS {n})", n=max(1, _int(s.get("capacity"), 1))),
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


def system_defs() -> list[SystemDef]:
    """The Add-system picker for Kra'Vak tech. Built per call so labels follow the language."""
    weapons, defence, craft, other = (
        _("Weapons"),
        _("Defences"),
        _("Hangars and bays"),
        _("Holds"),
    )
    fb2 = {"book": "FB2", "page": 9}
    return [
        SystemDef(
            "kgun",
            _("K-gun"),
            weapons,
            (
                ParamDef("class", "int", _("Class"), 1, 1, 9),
                ParamDef("arcs", "arcs", _("Arcs"), list(ARCS), 1, 6),
            ),
            **fb2,
        ),
        SystemDef(
            "mkp",
            _("MKP pack (one-shot)"),
            weapons,
            (ParamDef("arcs", "arcs", _("Arcs"), ["F"], 1, 1),),
            **fb2,
        ),
        SystemDef("scattergun", _("Scattergun (one-shot)"), defence, book="FB2", page=10),
        SystemDef("fire_control", _("Fire control"), defence, book="FB2", page=10),
        SystemDef(
            "hangar",
            _("Fighter hangar bay"),
            craft,
            (ParamDef("bays", "int", _("Fighter groups"), 1, 1, None),),
            book="FB2",
            page=10,
        ),
        SystemDef(
            "tender_bay",
            _("Tender bay"),
            craft,
            (ParamDef("capacity", "int", _("Craft MASS carried"), 10, 1, None),),
            book="FB2",
            page=10,
        ),
        SystemDef(
            "hold",
            _("Hold"),
            other,
            (
                ParamDef(
                    "kind",
                    "choice",
                    _("Kind"),
                    "cargo",
                    choices=(
                        ("cargo", _("Cargo (H)")),
                        ("passenger", _("Passengers (P)")),
                        ("troop", _("Troops (T)")),
                        ("lab", _("Science labs (S)")),
                    ),
                ),
                ParamDef("mass", "int", _("MASS"), 10, 1, None),
            ),
            book="FB1",
            page=8,
        ),
    ]


# ---- Breakdown ------------------------------------------------------------------------------


def design_breakdown(design: dict, options: dict) -> Breakdown:
    tmf = max(0, _int(design.get("tmf")))
    boxes = max(0, _int(design.get("hull_boxes")))
    armour = max(0, _int(design.get("armour")))
    thrust = max(0, _int(design.get("thrust")))
    ftl_mass = pct_mass(tmf, 10) if design.get("ftl") is True and tmf > 0 else 0
    drive_mass = pct_mass(tmf, 5 * thrust) if thrust > 0 and tmf > 0 else 0

    rows = [
        BreakdownRow("hull", _("Basic hull (MASS {n})", n=tmf), 0, tmf),
        BreakdownRow("hull_integrity", _("Hull integrity ({n} boxes)", n=boxes), boxes, 2 * boxes),
    ]
    if armour:
        rows.append(BreakdownRow("armour", _("Armour ({n} boxes)", n=armour), armour, 2 * armour))
    if drive_mass:
        # FB2 p.9: Advanced Grav Drives are 3 points per MASS, not the human 2.
        rows.append(
            BreakdownRow(
                "main_drive", _("Advanced grav drive (thrust-{n}A)", n=thrust), drive_mass, 3 * drive_mass
            )
        )
    if ftl_mass:
        rows.append(BreakdownRow("ftl", _("FTL drive"), ftl_mass, 2 * ftl_mass))

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
        "mass_limit": tmf,
        "ftl_mass": ftl_mass,
        "drive_mass": drive_mass,
        # FB2 p.9: Kra'Vak may use up to ALL their thrust for course changes, not half.
        "turn_thrust": thrust,
        "hull_descriptor": _hull_descriptor(boxes, tmf),
        "damage_track": split_rows(boxes, 4),
        "crew_factors": crew_factors(design),
        "cf_positions": cf_positions(design),
        "thresholds": threshold_numbers(design),
        "holds": holds,
        "core_systems": True,
    }
    return Breakdown(tuple(rows), mass_used, points, derived)


def loadout_points(design: dict, loadout: dict | None, options: dict) -> int:
    """Ra'San groups cost 18 points, Va'San (heavy) 30 (FB2 p.10) — the human standard and heavy
    prices, so the shared table covers both."""
    if loadout is None:
        loadout = design.get("default_loadout")
    entries = []
    if isinstance(loadout, dict) and isinstance(loadout.get("fighters"), list):
        entries = [e for e in loadout["fighters"] if isinstance(e, dict)]
    return sum(FIGHTER_POINTS.get(f.get("type"), 0) for f in entries)


# FB2 p.10: the Ra'San is a regular multirole fighter, the Va'San a "heavy" one.
FIGHTER_POINTS = {"standard": 18, "heavy": 30}


# ---- Validation ---------------------------------------------------------------------------------


def validate_design(design: dict, options: dict) -> list[Issue]:
    issues: list[Issue] = []

    def violation(code: str, message: str, uid: str | None = None) -> None:
        issues.append(Issue(code, "violation", message, uid))

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
    if tmf > 0 and boxes < pct_mass(tmf, 10):
        violation(
            "hull_below_minimum",
            _("Hull integrity needs at least {n} boxes (10% of MASS).", n=pct_mass(tmf, 10)),
        )
    if _int(design.get("thrust")) < 0 or _int(design.get("armour")) < 0:
        violation("negative_value", _("Thrust and armour cannot be negative."))
    if design.get("streamlining") not in (None, "", "none"):
        violation("kv_streamlining", _("Kra'Vak designs in Fleet Book 2 are not streamlined."))

    systems = _systems(design)
    by_uid = {s["uid"]: s for s in systems if isinstance(s.get("uid"), str)}
    for s in systems:
        uid = s.get("uid") if isinstance(s.get("uid"), str) else None
        stype = s.get("type")
        if stype not in SYSTEM_RULES:
            violation(
                "race_system",
                _("Kra'Vak ships do not carry this system: {t}.", t=str(stype)),
                uid,
            )
            continue
        if stype == "kgun":
            _validate_kgun(s, uid, violation)
        elif stype == "mkp" and not (arcs_valid(_arcs(s)) and len(_arcs(s)) == 1):
            violation("mkp_arcs", _("An MKP pack fires through one arc only."), uid)

    _validate_fighters(design, by_uid, violation)

    if not any(s.get("type") == "fire_control" for s in systems):
        issues.append(
            Issue("no_fire_control", "info", _("No fire control: K-guns cannot fire."), None)
        )
    if design.get("ftl") is not True:
        issues.append(Issue("no_ftl", "info", _("No FTL drive: this is a system defence ship."), None))
    if _int(design.get("armour")) > 0:
        issues.append(
            Issue("kv_armour", "info", _("Kra'Vak ships rarely carry armour; it is permitted."), None)
        )
    return issues


def _validate_kgun(s: dict, uid: str | None, violation) -> None:
    arcs = s.get("arcs")
    cls = _int(s.get("class"), 1)
    if cls < 1:
        violation("kgun_class", _("K-gun class must be at least 1."), uid)
        return
    if not arcs_valid(arcs):
        violation(
            "bad_arcs", _("Choose at least one fire arc ({arcs}), each once.", arcs=", ".join(ARCS)), uid
        )
        return
    # FB2 p.9: class 1 is always all-round, class 2 has one or two arcs, everything larger one.
    if cls == 1 and len(arcs) != 6:
        violation("kgun_arcs", _("A class-1 K-gun always fires through all six arcs."), uid)
    elif cls == 2 and (len(arcs) > 2 or not arcs_contiguous(arcs)):
        violation("kgun_arcs", _("A class-2 K-gun covers one or two adjacent arcs."), uid)
    elif cls > 2 and len(arcs) != 1:
        violation("kgun_arcs", _("K-guns of class 3 and above fire through one arc only."), uid)


def _validate_fighters(design: dict, by_uid: dict, violation) -> None:
    loadout = design.get("default_loadout")
    entries = []
    if isinstance(loadout, dict) and isinstance(loadout.get("fighters"), list):
        entries = [e for e in loadout["fighters"] if isinstance(e, dict)]
    per_hangar: dict[str, int] = {}
    for entry in entries:
        hangar = by_uid.get(entry.get("hangar"))
        if not hangar or hangar.get("type") != "hangar":
            violation(
                "fighters_without_hangar", _("Fighter group assigned to a hangar this design does not have.")
            )
            continue
        if entry.get("type") not in FIGHTER_POINTS:
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
