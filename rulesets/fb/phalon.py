"""FB ruleset, Phalon tech (FB2 pp.35-37).

Design procedure FB2 p.37, systems pp.35-36, weapons summary p.45.

The Phalons are the closest of the three races to human tech: hull integrity, main drive
(5% of MASS per thrust), FTL, fire control, ADFC, hangar bays, tender bays and crew factors are
all the human rules, which FB2 pp.35-36 say outright, so they come from `rules` unchanged.

Two things are their own:

- The SHELL is armour stacked in layers, and a box costs 2 x its layer number, so a fourth-layer
  box costs 8 points (FB2 p.35). `armour` stays the total box count, which is what the damage
  track and the campaign clamp use; `armour_layers` holds the split, inner layer first.
- The PULSER is one weapon with three configurations. Which one is a per-battle choice written
  on the sheet, not a design property, so it lives in the loadout (PLAN 5.4) and costs nothing.

Checked against the FB2 p.37 worked example (NPV 379) and every printed panel on pp.38-45.
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
    "PULSER_MODES",
    "SYSTEM_RULES",
    "cf_positions",
    "crew_factors",
    "damage_track",
    "design_breakdown",
    "loadout_points",
    "pulser_modes",
    "shell_layers",
    "shell_points",
    "suggest_type",
    "system_defs",
    "threshold_numbers",
    "validate_design",
]

ICON_SET = "fb_phalon"
CREWED = True  # crew factors and damage control parties

# FB2 p.36: the Phalons use the standard fighter types and "the usual points costs".
FIGHTER_POINTS = dict(data.FIGHTER_POINTS)

# FB2 p.35: configured before each battle, never changed during one.
PULSER_MODES = ("L", "M", "C")


def pulser_mode_label(mode: str) -> str:
    return {
        "L": _("Long range (1 die, 36mu)"),
        "M": _("Medium range (2 dice, 24mu)"),
        "C": _("Close range (6 dice, 12mu)"),
    }.get(mode, mode)


def _pulser_mass(system: dict, tmf: int) -> int:
    """FB2 p.35: one, three or six arcs for 2, 3 or 4 MASS."""
    arcs = len(_arcs(system))
    if arcs >= 6:
        return 4
    return 3 if arcs >= 3 else 2


def _shroud_mass(system: dict, tmf: int) -> int:
    """FB2 p.36: 5% of total ship mass, minimum 1 MASS."""
    return max(1, pct_mass(tmf, 5))


# type -> (mass(system, tmf), points(system, mass), label(system)); see rules.SYSTEM_RULES.
SystemRule = tuple[Callable[[dict, int], int], Callable[[dict, int], int], Callable[[dict], str]]

SYSTEM_RULES: dict[str, SystemRule] = {
    "pulser": (_pulser_mass, lambda s, m: 5 * m, lambda s: _("Pulser battery")),
    "plasma_bolt_launcher": (
        lambda s, t: 5 * max(1, _int(s.get("class"), 1)),
        lambda s, m: 3 * m,
        lambda s: _("Class-{n} plasma bolt launcher", n=max(1, _int(s.get("class"), 1))),
    ),
    "vapour_shroud": (_shroud_mass, lambda s, m: 3 * m, lambda s: _("Vapour shroud gland")),
    "fire_control": (lambda s, t: 1, lambda s, m: 4, lambda s: _("Fire control")),
    "adfc": (lambda s, t: 2, lambda s, m: 8, lambda s: _("Area-defence fire control")),
    # FB2 p.36 prints "9 MASS and costs 18 points" for a fighter bay, as the Kra'Vak section
    # does, and it is wrong in the same way: the Taanis (641) and Draath (1002) only reconcile
    # at the human 3 points per MASS, ie: 27. The printed 18 is a fighter group's own cost.
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
    """The Add-system picker for Phalon tech. Built per call so labels follow the language."""
    weapons, defence, craft, other = (
        _("Weapons"),
        _("Defences"),
        _("Hangars and bays"),
        _("Holds"),
    )
    return [
        SystemDef(
            "pulser",
            _("Pulser battery"),
            weapons,
            # FB2 p.35: one, three or six arcs. The L/M/C setting is a loadout choice.
            (ParamDef("arcs", "arcs", _("Arcs"), ["F"], 1, 6),),
            book="FB2",
            page=35,
        ),
        SystemDef(
            "plasma_bolt_launcher",
            _("Plasma bolt launcher"),
            weapons,
            (
                ParamDef("class", "int", _("Class"), 1, 1, 9),
                ParamDef("arcs", "arcs", _("Arcs"), ["FP", "F", "FS"], 3, 3),
            ),
            book="FB2",
            page=36,
        ),
        SystemDef("vapour_shroud", _("Vapour shroud gland"), defence, book="FB2", page=36),
        SystemDef("fire_control", _("Fire control"), defence, book="FB2", page=36),
        SystemDef("adfc", _("Area-defence fire control"), defence, book="FB2", page=35),
        SystemDef(
            "hangar",
            _("Fighter hangar bay"),
            craft,
            (ParamDef("bays", "int", _("Fighter groups"), 1, 1, None),),
            book="FB2",
            page=36,
        ),
        SystemDef(
            "tender_bay",
            _("Tender bay"),
            craft,
            (ParamDef("capacity", "int", _("Craft MASS carried"), 10, 1, None),),
            book="FB2",
            page=36,
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


# ---- The shell ---------------------------------------------------------------------------------


def shell_layers(design: dict) -> list[int]:
    """Boxes per shell layer, inner layer first (FB2 p.35).

    A design with no layers recorded has the one layer every other race has, so its whole
    `armour` total is the inner layer. Trailing empty layers are dropped, and the layers are
    clamped to the total so a malformed design can never cost more shell than it bought.
    """
    total = max(0, _int(design.get("armour")))
    raw = design.get("armour_layers")
    layers = [max(0, _int(n)) for n in raw] if isinstance(raw, list) else []
    while layers and layers[-1] == 0:
        layers.pop()
    if not layers:
        return [total] if total else []
    out: list[int] = []
    left = total
    for boxes in layers:
        out.append(min(boxes, left))
        left -= out[-1]
    return out


def shell_points(layers: list[int]) -> int:
    """FB2 p.35: "the cost is 2 x layer number", counting the inner layer as one."""
    return sum(2 * (index + 1) * boxes for index, boxes in enumerate(layers))


# ---- Loadout: pulser configuration ---------------------------------------------------------------


def pulser_modes(design: dict, loadout: dict | None) -> dict[str, str]:
    """uid -> "L" / "M" / "C" for each pulser, from the loadout (PLAN 5.4).

    FB2 p.35 prints blank pulser icons for the player to write into before a battle, so a pulser
    with nothing chosen keeps an empty setting rather than being given a default here.
    """
    if loadout is None:
        loadout = design.get("default_loadout")
    entries = []
    if isinstance(loadout, dict) and isinstance(loadout.get("pulsers"), list):
        entries = [e for e in loadout["pulsers"] if isinstance(e, dict)]
    chosen = {}
    for entry in entries:
        uid, mode = entry.get("pulser"), entry.get("mode")
        if isinstance(uid, str) and isinstance(mode, str) and mode in PULSER_MODES:
            chosen[uid] = mode
    return {s["uid"]: chosen[s["uid"]] for s in _systems(design)
            if s.get("type") == "pulser" and isinstance(s.get("uid"), str) and s["uid"] in chosen}


# ---- Breakdown ------------------------------------------------------------------------------


def design_breakdown(design: dict, options: dict) -> Breakdown:
    tmf = max(0, _int(design.get("tmf")))
    boxes = max(0, _int(design.get("hull_boxes")))
    thrust = max(0, _int(design.get("thrust")))
    layers = shell_layers(design)
    shell_mass = sum(layers)
    ftl_mass = pct_mass(tmf, 10) if design.get("ftl") is True and tmf > 0 else 0
    drive_mass = pct_mass(tmf, 5 * thrust) if thrust > 0 and tmf > 0 else 0

    rows = [
        BreakdownRow("hull", _("Basic hull (MASS {n})", n=tmf), 0, tmf),
        BreakdownRow("hull_integrity", _("Hull integrity ({n} boxes)", n=boxes), boxes, 2 * boxes),
    ]
    if shell_mass:
        label = (
            _("Shell ({n} boxes in {k} layers)", n=shell_mass, k=len(layers)) if len(layers) > 1
            else _("Shell ({n} boxes)", n=shell_mass)
        )
        rows.append(BreakdownRow("armour", label, shell_mass, shell_points(layers)))
    if drive_mass:
        rows.append(
            BreakdownRow("main_drive", _("Main drive (thrust-{n})", n=thrust), drive_mass, 2 * drive_mass)
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
        "turn_thrust": thrust // 2 if thrust != 1 else 1,
        "hull_descriptor": _hull_descriptor(boxes, tmf),
        "damage_track": split_rows(boxes, 4),
        "crew_factors": crew_factors(design),
        "cf_positions": cf_positions(design),
        "thresholds": threshold_numbers(design),
        "holds": holds,
        "core_systems": True,
        # The shell is drawn as one row of circles per layer, outermost at the top (FB2 p.35).
        "shell_layers": layers,
        "pulser_modes": pulser_modes(design, None),
    }
    return Breakdown(tuple(rows), mass_used, points, derived)


def loadout_points(design: dict, loadout: dict | None, options: dict) -> int:
    """Fighter groups cost extra (FB2 p.36 uses the standard types and prices); the pulser
    configuration is free, being a setting rather than a fitting."""
    if loadout is None:
        loadout = design.get("default_loadout")
    entries = []
    if isinstance(loadout, dict) and isinstance(loadout.get("fighters"), list):
        entries = [e for e in loadout["fighters"] if isinstance(e, dict)]
    return sum(FIGHTER_POINTS.get(f.get("type"), 0) for f in entries)


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
        violation("negative_value", _("Thrust and shell cannot be negative."))
    if design.get("streamlining") not in (None, "", "none"):
        violation("ph_streamlining", _("Phalon designs in Fleet Book 2 are not streamlined."))

    raw = design.get("armour_layers")
    if isinstance(raw, list) and raw:
        total = sum(max(0, _int(n)) for n in raw)
        if total != max(0, _int(design.get("armour"))):
            violation(
                "shell_layers_total",
                _("Shell layers total {n} boxes but the shell is {m}.",
                  n=total, m=max(0, _int(design.get("armour")))),
            )

    systems = _systems(design)
    by_uid = {s["uid"]: s for s in systems if isinstance(s.get("uid"), str)}
    for s in systems:
        uid = s.get("uid") if isinstance(s.get("uid"), str) else None
        stype = s.get("type")
        if stype not in SYSTEM_RULES:
            violation("race_system", _("Phalon ships do not carry this system: {t}.", t=str(stype)), uid)
            continue
        if stype == "pulser":
            _validate_pulser(s, uid, violation)
        elif stype == "plasma_bolt_launcher":
            _validate_launcher(s, uid, violation)

    _validate_loadout(design, by_uid, violation)

    if not any(s.get("type") == "fire_control" for s in systems):
        issues.append(
            Issue("no_fire_control", "info",
                  _("No fire control: pulsers and plasma bolts cannot fire."), None)
        )
    if design.get("ftl") is not True:
        issues.append(Issue("no_ftl", "info", _("No FTL drive: this is a system defence ship."), None))
    if len(shell_layers(design)) > 4:
        # FB2 p.35 allows more "theoretically ... if required", so this is not a violation.
        issues.append(
            Issue("shell_deep", "info", _("Shells beyond four layers are outside the book's designs."), None)
        )
    return issues


def _validate_pulser(s: dict, uid: str | None, violation) -> None:
    arcs = s.get("arcs")
    if not arcs_valid(arcs):
        violation(
            "bad_arcs", _("Choose at least one fire arc ({arcs}), each once.", arcs=", ".join(ARCS)), uid
        )
        return
    # FB2 p.35: "it may have one, three or six arcs of fire".
    if len(arcs) not in (1, 3, 6):
        violation("pulser_arcs", _("A pulser battery covers one, three or all six arcs."), uid)
    elif len(arcs) == 3 and not arcs_contiguous(arcs):
        violation("pulser_arcs", _("A three-arc pulser battery covers three adjacent arcs."), uid)


def _validate_launcher(s: dict, uid: str | None, violation) -> None:
    if _int(s.get("class"), 1) < 1:
        violation("pbl_class", _("Plasma bolt launcher class must be at least 1."), uid)
    arcs = s.get("arcs")
    if not arcs_valid(arcs):
        violation(
            "bad_arcs", _("Choose at least one fire arc ({arcs}), each once.", arcs=", ".join(ARCS)), uid
        )
    elif len(arcs) != 3 or not arcs_contiguous(arcs):
        # FB2 p.36: "The launcher is a 3-arc (180 degree) system".
        violation("pbl_arcs", _("A plasma bolt launcher covers three adjacent arcs."), uid)


def _validate_loadout(design: dict, by_uid: dict, violation) -> None:
    loadout = design.get("default_loadout")
    entries = loadout.get("fighters") if isinstance(loadout, dict) else None
    entries = [e for e in entries if isinstance(e, dict)] if isinstance(entries, list) else []
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

    pulsers = loadout.get("pulsers") if isinstance(loadout, dict) else None
    pulsers = [e for e in pulsers if isinstance(e, dict)] if isinstance(pulsers, list) else []
    for entry in pulsers:
        target = by_uid.get(entry.get("pulser"))
        if not target or target.get("type") != "pulser":
            violation("pulser_setting_unknown", _("Pulser setting for a battery this design lacks."))
        elif entry.get("mode") not in PULSER_MODES:
            violation("pulser_mode", _("A pulser is configured L, M or C."), target["uid"])
