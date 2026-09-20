"""FB ruleset, Sa'Vasku tech (FB2 pp.21-25).

Design procedure FB2 p.24, systems pp.22-24, thrust table pp.21-22 and 25.

The Sa'Vasku economy looks unlike the human one, but it maps onto the same design dict without
new fields, because the parts that differ are either the same quantity under another name or
per-turn play state that no design holds:

- BIOMASS is `hull_boxes`: 1 MASS, 2 points, a four-row damage track, a threshold check at the
  end of each row. That it may also be *consumed* to grow drones, fire pods and pay for repairs
  is a rule about play, not about the design.
- CARAPACE is `armour`: 1 MASS, 2 points, a row of circles, "treated like armour in all
  respects" (FB2 p.22).
- The FTL node is `ftl`, 10% of MASS at 2 points per MASS, exactly as every other race's.
- The main drive node is always 10% of MASS at 2 points per MASS and has NO thrust rating, so
  `thrust` is unused and must be 0: thrust is bought turn by turn out of the power pools.
- POWER GENERATORS are a system carrying the total (`capacity`); the four generators at the ends
  of the damage-track rows are derived, not stored.
- The M/A/D/R power pools are written on the record chart every turn and explicitly do not carry
  over ("Any power points that are not used by the end of the turn ... are lost", FB2 p.22), so
  they are play state like movement orders and live nowhere in the design.

Checked against the FB2 p.24 worked example (NPV 342) and every printed panel on pp.26-32.
"""

from __future__ import annotations

from collections.abc import Callable

from i18n import _
from rulesets import Breakdown, BreakdownRow, Issue, ParamDef, SystemDef
from rulesets.common import arcs_contiguous, arcs_valid, pct_mass, round_half_up, split_rows
from rulesets.fb.rules import _arcs, _int, _systems, suggest_type, threshold_numbers
from rulesets.fb.rules import _hull_descriptor as _hull_descriptor

__all__ = [
    "SYSTEM_RULES",
    "cf_positions",
    "crew_factors",
    "damage_track",
    "design_breakdown",
    "generator_row_split",
    "loadout_points",
    "suggest_type",
    "system_defs",
    "threshold_numbers",
    "thrust_table",
    "validate_design",
]

ICON_SET = "fb_savasku"
# A construct is a single bioconstruct with no crew (FB2 p.21); repairs come out of the R pool.
CREWED = False

# Drones are grown from biomass in play, never bought, so a drone group adds nothing to the NPV
# ("not including the necessary biomass to convert into drones", FB2 p.23).
FIGHTER_POINTS = {"drone": 0}


def _screen_node_mass(system: dict, tmf: int) -> int:
    """FB2 p.23: 5% of ship MASS, minimum 3 MASS."""
    return max(3, pct_mass(tmf, 5))


# type -> (mass(system, tmf), points(system, mass), label(system)); see rules.SYSTEM_RULES.
SystemRule = tuple[Callable[[dict, int], int], Callable[[dict, int], int], Callable[[dict], str]]

SYSTEM_RULES: dict[str, SystemRule] = {
    "power_generator": (
        lambda s, t: max(0, _int(s.get("capacity"), 0)),
        lambda s, m: 2 * m,
        lambda s: _("Power generators ({n} power points)", n=max(0, _int(s.get("capacity"), 0))),
    ),
    "stinger": (lambda s, t: 2, lambda s, m: 3 * m, lambda s: _("Stinger node")),
    "pod_launcher": (lambda s, t: 3, lambda s, m: 3 * m, lambda s: _("Pod launcher node")),
    "spicule": (lambda s, t: 1, lambda s, m: 3 * m, lambda s: _("PD spicule")),
    "cortex": (lambda s, t: 1, lambda s, m: 4, lambda s: _("Cortex node")),
    "screen_node": (_screen_node_mass, lambda s, m: 3 * m, lambda s: _("Screen node")),
    "drone_womb": (lambda s, t: 3, lambda s, m: 9, lambda s: _("Drone womb")),
}


def system_defs() -> list[SystemDef]:
    """The Add-system picker for Sa'Vasku tech. Built per call so labels follow the language."""
    power, weapons, defence, craft = (
        _("Power"),
        _("Weapons"),
        _("Defences"),
        _("Hangars and bays"),
    )
    return [
        SystemDef(
            "power_generator",
            _("Power generators"),
            power,
            (ParamDef("capacity", "int", _("Power points per turn"), 4, 0, None),),
            book="FB2",
            page=22,
        ),
        SystemDef(
            "stinger",
            _("Stinger node"),
            weapons,
            # FB2 p.22: "All stinger nodes may fire through 3 arcs ... any three contiguous arcs".
            (ParamDef("arcs", "arcs", _("Arcs"), ["FP", "F", "FS"], 3, 3),),
            book="FB2",
            page=22,
        ),
        SystemDef(
            "pod_launcher",
            _("Pod launcher node"),
            weapons,
            (ParamDef("arcs", "arcs", _("Arcs"), ["F"], 1, 1),),
            book="FB2",
            page=22,
        ),
        SystemDef("spicule", _("PD spicule"), defence, book="FB2", page=23),
        SystemDef("cortex", _("Cortex node"), defence, book="FB2", page=24),
        SystemDef("screen_node", _("Screen node"), defence, book="FB2", page=23),
        SystemDef("drone_womb", _("Drone womb"), craft, book="FB2", page=23),
    ]


# ---- Derived: power generators and the thrust table ---------------------------------------------


def generator_row_split(total: int, rows: int = 4) -> list[int]:
    """The generators at the ends of the damage-track rows, top row first.

    FB2 p.24: "the stronger PGs are always on the lower damage track rows (so that the weaker
    ones are lost first)", so 22 over four rows is 5/5/6/6, not split_rows()'s 6/6/5/5. `rows` is
    how many damage rows the ship actually has: a construct too small for four rows spreads its
    power over the rows it has, which is why the Sa'Kess'Tha (2 biomass, 3 power, FB2 p.26)
    prints 1 and 2 rather than four generators with two of them zero.
    """
    return list(reversed(split_rows(max(0, total), max(1, rows))))


def power_total(design: dict) -> int:
    return sum(
        max(0, _int(s.get("capacity"), 0)) for s in _systems(design) if s.get("type") == "power_generator"
    )


def thrust_power(tmf: int, thrust: int, damaged: bool = False) -> int:
    """Power points for a thrust factor: 2% x thrust x MASS, doubled for a damaged drive node
    (FB2 p.21).

    FB2 p.21 says "rounded up" and illustrates it with 9.6 -> 10, but the thrust tables printed
    on the SSDs are round-half-up throughout: the Sa'Kess'Tha (MASS 11, p.26) needs 2 PP at
    thrust 7 (1.54) and only 1 at thrust 6 (1.32), which rounding up cannot produce. Every row of
    every printed table fits round-half-up, so that is what the tables here use.
    """
    if thrust <= 0 or tmf <= 0:
        return 0
    # Never free: the smallest ships round to nothing at low thrust, but every printed table
    # starts at 1 PP (eg the Fo'Sath'Aan, MASS 24, p.27: thrust 1 costs 1 although 0.48 rounds
    # to zero).
    return max(1, round_half_up((4 if damaged else 2) * thrust * tmf, 100))


def thrust_table(tmf: int, power: int) -> list[tuple[int, int, int | None]]:
    """The SSD's T/P table as (max thrust, power, power when the drive node is damaged).

    One row per distinct power pair, carrying the HIGHEST thrust that pair buys, because FB2 p.22
    reads the table upwards: "if the factor required is greater than one entry in the T column
    but less than the next, then the power point cost is as for the next higher entry". Rows stop
    once even an undamaged drive would need more power than the ship can generate, and a damaged
    figure beyond that is printed as a dash.
    """
    rows: list[tuple[int, int, int | None]] = []
    previous: tuple[int, int | None] | None = None
    thrust = 0
    # The last row is the highest thrust the ship can still pay for, so the loop runs until the
    # undamaged cost passes the generation rather than to a thrust guessed in advance; the cap is
    # only there so a malformed design cannot spin.
    while thrust < 500:
        thrust += 1
        undamaged = thrust_power(tmf, thrust)
        if undamaged > power:
            break
        damaged = thrust_power(tmf, thrust, damaged=True)
        pair = (undamaged, damaged if damaged <= power else None)
        if pair == previous:
            rows[-1] = (thrust, *pair)
        else:
            rows.append((thrust, *pair))
            previous = pair
    return rows


# ---- Breakdown ------------------------------------------------------------------------------


def design_breakdown(design: dict, options: dict) -> Breakdown:
    tmf = max(0, _int(design.get("tmf")))
    biomass = max(0, _int(design.get("hull_boxes")))
    carapace = max(0, _int(design.get("armour")))
    drive_mass = pct_mass(tmf, 10) if tmf > 0 else 0
    ftl_mass = pct_mass(tmf, 10) if design.get("ftl") is True and tmf > 0 else 0

    rows = [
        BreakdownRow("hull", _("Basic hull (MASS {n})", n=tmf), 0, tmf),
        BreakdownRow("hull_integrity", _("Biomass ({n} boxes)", n=biomass), biomass, 2 * biomass),
    ]
    if carapace:
        rows.append(BreakdownRow("armour", _("Carapace ({n} boxes)", n=carapace), carapace, 2 * carapace))
    if drive_mass:
        # FB2 p.24: 10% of MASS at 2 points per MASS, and no thrust rating of its own.
        rows.append(BreakdownRow("main_drive", _("Main drive node"), drive_mass, 2 * drive_mass))
    if ftl_mass:
        rows.append(BreakdownRow("ftl", _("FTL drive node"), ftl_mass, 2 * ftl_mass))

    for s in _systems(design):
        rule = SYSTEM_RULES.get(s.get("type"))
        uid = s.get("uid") if isinstance(s.get("uid"), str) else None
        if rule is None:
            rows.append(BreakdownRow(str(s.get("type")), _("Unknown system"), 0, 0, uid))
            continue
        mass_fn, points_fn, label_fn = rule
        mass = mass_fn(s, tmf)
        rows.append(BreakdownRow(s["type"], label_fn(s), mass, points_fn(s, mass), uid))

    mass_used = sum(r.mass for r in rows)
    points = sum(r.points for r in rows)
    power = power_total(design)
    derived = {
        "tmf": tmf,
        "mass_limit": tmf,
        "ftl_mass": ftl_mass,
        "drive_mass": drive_mass,
        "turn_thrust": 0,  # thrust is bought per turn; the sheet carries the table instead
        "hull_descriptor": _hull_descriptor(biomass, tmf),
        "damage_track": split_rows(biomass, 4),
        "crew_factors": 0,
        "cf_positions": [],
        "thresholds": threshold_numbers(design),
        "holds": [],
        # A construct has no command bridge, life support or power core: the FB2 p.25 key lists
        # no core systems box, and damage control is paid for out of the Repair pool (p.24).
        "core_systems": False,
        "power": power,
        "power_generators": generator_row_split(power, sum(1 for n in split_rows(biomass, 4) if n)),
        "thrust_table": thrust_table(tmf, power),
    }
    return Breakdown(tuple(rows), mass_used, points, derived)


def damage_track(design: dict) -> list[int]:
    return split_rows(max(0, _int(design.get("hull_boxes"))), 4)


def crew_factors(design: dict) -> int:
    """A Sa'Vasku ship is a single bioconstruct with no crew (FB2 p.21), and its spec panels
    print no crew factor. Damage control is paid for out of the Repair pool instead (p.24)."""
    return 0


def cf_positions(design: dict) -> list[int]:
    return []


def loadout_points(design: dict, loadout: dict | None, options: dict) -> int:
    return 0  # drones are grown from biomass, never bought (FB2 p.23)


# ---- Validation ---------------------------------------------------------------------------------


def validate_design(design: dict, options: dict) -> list[Issue]:
    issues: list[Issue] = []

    def violation(code: str, message: str, uid: str | None = None) -> None:
        issues.append(Issue(code, "violation", message, uid))

    tmf = _int(design.get("tmf"))
    biomass = _int(design.get("hull_boxes"))
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
    # FB2 p.24: "the MINIMUM amount of biomass is 10% of the ship's total MASS".
    if tmf > 0 and biomass < pct_mass(tmf, 10):
        violation(
            "biomass_below_minimum",
            _("Biomass needs at least {n} boxes (10% of MASS).", n=pct_mass(tmf, 10)),
        )
    if _int(design.get("armour")) < 0:
        violation("negative_value", _("Carapace cannot be negative."))
    if _int(design.get("thrust")) != 0:
        violation(
            "sv_thrust",
            _("Sa'Vasku drive nodes have no thrust rating: thrust is paid for with power."),
        )
    if design.get("streamlining") not in (None, "", "none"):
        violation("sv_streamlining", _("Sa'Vasku constructs are not streamlined."))

    systems = _systems(design)
    by_uid = {s["uid"]: s for s in systems if isinstance(s.get("uid"), str)}
    for s in systems:
        uid = s.get("uid") if isinstance(s.get("uid"), str) else None
        stype = s.get("type")
        if stype not in SYSTEM_RULES:
            violation(
                "race_system", _("Sa'Vasku constructs do not carry this system: {t}.", t=str(stype)), uid
            )
            continue
        if stype == "stinger" and not (arcs_valid(_arcs(s)) and len(_arcs(s)) == 3
                                       and arcs_contiguous(_arcs(s))):
            violation("stinger_arcs", _("A stinger node covers three adjacent arcs."), uid)
        elif stype == "pod_launcher" and not (arcs_valid(_arcs(s)) and len(_arcs(s)) == 1):
            violation("pod_arcs", _("A pod launcher node fires through one arc only."), uid)

    _validate_drones(design, by_uid, violation)

    if not any(s.get("type") == "cortex" for s in systems):
        issues.append(Issue("no_fire_control", "info", _("No cortex node: weapons cannot fire."), None))
    if design.get("ftl") is not True:
        issues.append(Issue("no_ftl", "info", _("No FTL drive: this is a system defence ship."), None))
    # FB2 never states a minimum, but a construct with no generators can neither move nor fire.
    if power_total(design) <= 0:
        issues.append(
            Issue("no_power", "info", _("No power generators: this construct cannot act."), None)
        )
    if sum(1 for s in systems if s.get("type") == "screen_node") > 2:
        issues.append(
            Issue("screen_backups", "info", _("Screen nodes beyond the second are backups only."), None)
        )
    return issues


def _validate_drones(design: dict, by_uid: dict, violation) -> None:
    loadout = design.get("default_loadout")
    entries = []
    if isinstance(loadout, dict) and isinstance(loadout.get("fighters"), list):
        entries = [e for e in loadout["fighters"] if isinstance(e, dict)]
    per_womb: dict[str, int] = {}
    for entry in entries:
        womb = by_uid.get(entry.get("hangar"))
        if not womb or womb.get("type") != "drone_womb":
            violation("fighters_without_hangar", _("Drone group assigned to a womb this design lacks."))
            continue
        if entry.get("type") not in FIGHTER_POINTS:
            violation("unknown_fighter_type", _("Unknown drone type."), womb["uid"])
        per_womb[womb["uid"]] = per_womb.get(womb["uid"], 0) + 1
    for uid, groups in per_womb.items():
        if groups > 1:
            # FB2 p.23: "each womb can grow (or launch) one 6-drone group at a time".
            violation("hangar_overfull", _("A drone womb holds one drone group."), uid)
