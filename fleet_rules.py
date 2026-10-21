"""Pure fleet logic (layer 2): points incl. loadouts, conformance, badges, tournament check.

Never branches on a ruleset id; everything ruleset-specific goes through the Ruleset protocol.
Conformance and badges are computed here on demand and never stored (PLAN 7). Campaign damage
and ship status never affect conformance.

`designs` is a mapping design id -> design dict covering every design the fleet references
(store.designs_for_fleet() builds it). A ship whose design is missing counts as a violation.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from i18n import _
from rulesets import RULESETS, Issue, fleet_common

DESTROYED = "destroyed"
FLEET_OPTION_KEYS = (
    "core_systems", "rerolls", "fighter_endurance", "vector_movement",
    "mt_systems", "mt_superships", "mt_fighters",
    "cd_optional_systems", "cd_multistage", "cd_super_weapons", "cd_system_defence", "cd_cpv",
    "cd_advanced_ftl", "cd_patrol_battle", "cd_capital_limit",
    "pc_optional_systems", "pc_tech_base", "pc_adfc_no_mass", "pc_hangar_criticals",
    "pc_overload_torpedoes",
)
# What a new fleet starts with: options that add gear or mechanics are on; options that limit
# fleet selection (patrol battle, capital limit, tech base) and alternative core rules (vector
# movement, CPV hulls, paid advanced FTL, massless ADFC) are off. Saved fleets keep their own.
DEFAULT_ON_OPTIONS = frozenset({
    "core_systems", "rerolls", "fighter_endurance",
    "mt_systems", "mt_superships", "mt_fighters",
    "cd_optional_systems", "cd_multistage", "cd_super_weapons", "cd_system_defence",
    "pc_optional_systems", "pc_hangar_criticals", "pc_overload_torpedoes",
})


def option_label(key: str) -> str:
    """What a fleet option is called on screen and on paper; the key itself is storage."""
    return {
        "core_systems": _("Core systems"),
        "rerolls": _("Beam re-rolls"),
        "fighter_endurance": _("Fighter endurance"),
        "vector_movement": _("Vector movement"),
        "mt_systems": _("More Thrust systems"),
        "mt_superships": _("More Thrust superships"),
        "mt_fighters": _("More Thrust fighter types"),
        "cd_optional_systems": _("Sensors, ECM, mines and ortillery"),
        "cd_multistage": _("Multi-stage missiles"),
        "cd_super_weapons": _("Nova cannon, wave gun, reflex field, cloak"),
        "cd_system_defence": _("System defence ships (non-FTL)"),
        "cd_patrol_battle": _("Patrol battle: no capitals, at most half the points on cruisers"),
        "cd_capital_limit": _("At most half the points on capital ships"),
        "cd_cpv": _("Combat Points Value (CPV) hull cost"),
        "cd_advanced_ftl": _("Pay for advanced FTL"),
        "pc_optional_systems": _("Launch catapults and flawed designs"),
        "pc_tech_base": _("Imperial tech base (10 technology choices)"),
        "pc_adfc_no_mass": _("ADFC takes no MASS on ships over MASS 20"),
        "pc_hangar_criticals": _("Critical hits to hangar bays (bays 2 points a MASS)"),
        "pc_overload_torpedoes": _("Overloadable pulse torpedoes"),
    }.get(key, key)


def ruleset_option_keys(ruleset_id: str) -> tuple[str, ...]:
    """The options a fleet of this ruleset can switch, in the ruleset's display order."""
    rs = RULESETS.get(ruleset_id)
    return tuple(getattr(rs, "option_keys", FLEET_OPTION_KEYS)) if rs else ()


def default_options(ruleset_id: str) -> dict:
    """The options a new fleet of this ruleset starts with."""
    return {k: k in DEFAULT_ON_OPTIONS for k in ruleset_option_keys(ruleset_id)}


def ruleset_of(fleet: dict):
    return RULESETS.get(fleet.get("ruleset"))


def fleet_options(fleet: dict) -> dict:
    opts = fleet.get("options")
    return {k: bool(opts.get(k)) for k in FLEET_OPTION_KEYS} if isinstance(opts, dict) else {}


def system_labels(design: dict | None) -> dict[str, str]:
    """uid -> the system's name as the ruleset labels it (the breakdown rows), for lists that
    name systems outside the Design tab: knocked-out systems, the PDF tracker."""
    rs = RULESETS.get((design or {}).get("ruleset"))
    if not rs:
        return {}
    return {row.system_uid: row.label
            for row in rs.design_breakdown(design, {}).rows if row.system_uid}


def design_points(design: dict, options: dict) -> int:
    rs = RULESETS.get(design.get("ruleset"))
    return rs.design_breakdown(design, options).points if rs else 0


def ship_points(ship: dict, design: dict | None, options: dict) -> int:
    """NPV plus the ship's loadout (its own, else the design default; PLAN 5.4)."""
    if not design:
        return 0
    rs = RULESETS.get(design.get("ruleset"))
    if not rs:
        return 0
    return design_points(design, options) + rs.loadout_points(design, ship.get("loadout"), options)


def dummy_bogeys(fleet: dict) -> int:
    """Dummy bogeys the fleet buys, where its ruleset offers them (CD p.37); else 0."""
    rs = ruleset_of(fleet)
    n = fleet.get("dummy_bogeys")
    return n if rs and rs.dummy_bogey_points and isinstance(n, int) and n > 0 else 0


def dummy_bogey_points(fleet: dict) -> int:
    rs = ruleset_of(fleet)
    return dummy_bogeys(fleet) * rs.dummy_bogey_points if rs else 0


def gunboat_squadrons(fleet: dict) -> list[dict]:
    """The FTL gunboat squadrons the fleet fields without a carrier, where its ruleset has
    gunboats (PC p.80); else none."""
    rs = ruleset_of(fleet)
    squadrons = fleet.get("gunboat_squadrons")
    if not getattr(rs, "gunboat_types", ()) or not isinstance(squadrons, list):
        return []
    return [g for g in squadrons if isinstance(g, dict)]


def gunboat_squadron_points(fleet: dict) -> int:
    rs = ruleset_of(fleet)
    return sum(rs.gunboat_squadron_points(g) for g in gunboat_squadrons(fleet))


def morale(fleet: dict, designs: dict) -> tuple[int, int] | None:
    """(MASS destroyed, MASS at which the fleet withdraws), where the ruleset has a fleet morale
    rule (CD p.40). Ships whose design is missing count for nothing."""
    rs = ruleset_of(fleet)
    ships = [(s, designs[s.get("design_id")]) for s in fleet.get("ships", [])
             if s.get("design_id") in designs]
    return rs.morale_mass(ships) if rs and ships else None


def fleet_points(fleet: dict, designs: dict) -> int:
    opts = fleet_options(fleet)
    return sum(
        ship_points(s, designs.get(s.get("design_id")), opts)
        for s in fleet.get("ships", [])
        if s.get("status") != DESTROYED
    ) + dummy_bogey_points(fleet) + gunboat_squadron_points(fleet)


def design_issues(design: dict, options: dict) -> list[Issue]:
    rs = RULESETS.get(design.get("ruleset"))
    if not rs:
        return [Issue("unknown_ruleset", "violation", _("Unknown ruleset."))]
    return rs.validate_design(design, options)


def design_conforming(design: dict, options: dict) -> bool:
    """Non-conforming iff at least one violation; allow_rule_breaking plays no part (PLAN 7)."""
    return not any(i.severity == "violation" for i in design_issues(design, options))


@dataclass
class ShipReport:
    ship: dict
    design: dict | None
    issues: list[Issue] = field(default_factory=list)

    @property
    def conforming(self) -> bool:
        return not any(i.severity == "violation" for i in self.issues)


@dataclass
class FleetReport:
    fleet_issues: list[Issue]
    ships: list[ShipReport]
    points: int

    @property
    def conforming(self) -> bool:
        return not any(i.severity == "violation" for i in self.fleet_issues) and all(
            s.conforming for s in self.ships
        )


def _ship_report(fleet: dict, ship: dict, design: dict | None, options: dict) -> ShipReport:
    if design is None:
        missing = Issue("missing_design", "violation", _("This ship's design is missing."))
        return ShipReport(ship, None, [missing])
    # The ship's own loadout, when it has one, is what it carries (and what it costs), so that
    # is what is checked: rulesets read the loadout from `default_loadout`.
    loadout = ship.get("loadout")
    issues = list(design_issues(design if loadout is None else {**design, "default_loadout": loadout},
                                options))
    if design.get("ruleset") != fleet.get("ruleset"):
        issues.append(Issue("wrong_ruleset", "violation", _("This design belongs to another ruleset.")))
    if design.get("race") != fleet.get("race") and not fleet.get("allow_race_mixing"):
        issues.append(
            Issue("race_mixing", "violation", _("A design of another race, and race mixing is off."))
        )
    rs = RULESETS.get(design.get("ruleset"))
    if rs:
        # The design may be fine alone yet need a More Thrust option this fleet has off; the
        # loadout (e.g. MT fighter types) can need one too.
        missing = {o for o in rs.required_options(design, ship.get("loadout")) if not options.get(o)}
        known = {i.code for i in issues}
        if missing and "mt_toggle_off" not in known and "mass_over_100" not in known:
            issues.append(
                Issue("mt_toggle_off", "violation",
                      _("Uses More Thrust content this fleet has switched off."))
            )
    return ShipReport(ship, design, issues)


def fleet_report(fleet: dict, designs: dict) -> FleetReport:
    """Every violation and info of the fleet and each ship (the tournament check, PLAN 7)."""
    options = fleet_options(fleet)
    ships = [
        _ship_report(fleet, s, designs.get(s.get("design_id")), options) for s in fleet.get("ships", [])
    ]
    points = fleet_points(fleet, designs)
    rs = ruleset_of(fleet)
    with_designs = [(s, designs[s.get("design_id")]) for s in fleet.get("ships", [])
                    if s.get("design_id") in designs]
    fleet_issues = list(rs.fleet_issues(fleet, with_designs, options)) if rs else []
    limit = fleet.get("points_limit")
    if isinstance(limit, int) and limit > 0 and points > limit:
        fleet_issues.append(
            Issue("over_points", "violation",
                  _("{used} points exceed the limit of {limit}.", used=points, limit=limit))
        )
    return FleetReport(fleet_issues, ships, points)


def fleet_conforming(fleet: dict, designs: dict) -> bool:
    return fleet_report(fleet, designs).conforming


def design_is_custom(design: dict | None) -> bool:
    source = design.get("source") if design else None
    return not (isinstance(source, dict) and source.get("kind") == "catalog")


def badges(fleet: dict, designs: dict) -> dict[str, bool]:
    """PLAN 7: non_conforming, no_faction, mixed_faction, custom_ships (the ruleset badge is
    always shown). A fleet without a faction says so rather than calling itself mixed: there is
    nothing for its ships to be mixed against."""
    ships = fleet.get("ships", [])
    faction = fleet.get("faction")
    ship_designs = [designs.get(s.get("design_id")) for s in ships]
    mixed = faction is not None and any(d is None or d.get("faction") != faction for d in ship_designs)
    return {
        "non_conforming": not fleet_conforming(fleet, designs),
        "no_faction": faction is None,
        "mixed_faction": mixed,
        "custom_ships": any(design_is_custom(d) for d in ship_designs),
    }


def badge_label(key: str) -> str:
    return {
        "non_conforming": _("Non-conforming"),
        "no_faction": _("No faction"),
        "mixed_faction": _("Mixed faction"),
        "custom_ships": _("Custom ships"),
    }.get(key, key)


# ---- Campaign maths (PLAN 11.1; the repair rules are FT p.35) ----------------------------------

REPAIR_SYSTEMS_PER_WEEK = 3   # "you may roll for up to three systems on each ship ... per Turn"
REPAIR_TARGET = 3             # "on a D6 roll of 3 or more the system ... is repaired"
DRIVE_SUCCESSES = 2           # "Drive systems require TWO successful repair rolls if fully disabled"


FTL_HEXES_PER_WEEK = 6        # "each fleet of FTL ships can move up to 6 hexes" (FT p.35)


def force_reach(ships: list[tuple[dict, dict | None]]) -> tuple[int, str]:
    """(hexes a task force may move this week, why not when 0). Every ship must make the jump,
    on its own FTL or carried, and none may be docked for repairs (FT p.36)."""
    if not any(s.get("status") != "destroyed" for s, _d in ships):
        return 0, _("No ships.")
    if any(d is None for _s, d in ships):
        return 0, _("A ship's design is missing.")
    docked = [s for s, _d in ships if s.get("status") == "docked"]
    if docked:
        return 0, _("{name} is docked.", name=docked[0].get("name") or docked[0].get("table_id"))
    fixed, carried = fleet_common.jump_blockers(ships)
    if fixed:
        return 0, _("{name} cannot move.", name=fixed[0].get("name") or fixed[0].get("table_id"))
    if not carried:
        return 0, _("Ships without a working FTL drive need tender bays or tugs in the force.")
    return FTL_HEXES_PER_WEEK, ""


def hull_boxes(design: dict | None) -> int:
    rs = RULESETS.get(design.get("ruleset")) if design else None
    return sum(rs.damage_track(design)) if rs and design else 0


def crew_factors_left(design: dict | None, damage: dict | None) -> tuple[int, int]:
    """(crew factors left, total). A CF is lost when its marked box is crossed off (FB1 p.7)."""
    rs = RULESETS.get(design.get("ruleset")) if design else None
    if not rs or not design:
        return 0, 0
    positions = rs.cf_positions(design)
    done = int((damage or {}).get("hull") or 0)
    return sum(1 for position in positions if position > done), len(positions)


def ship_is_crippled(design: dict | None, damage: dict | None) -> bool:
    """Every hull box crossed off: the ship is a hulk for campaign purposes (FB1 p.4)."""
    total = hull_boxes(design)
    return bool(total) and int((damage or {}).get("hull") or 0) >= total


def repairable_systems(design: dict | None, damage: dict | None) -> list[str]:
    out = (damage or {}).get("systems_out") or []
    known = {s["uid"] for s in (design or {}).get("systems", [])}
    return [uid for uid in out if uid in known]


def repair_plan(design: dict | None, damage: dict | None, hull_rolled: int,
                system_uids: list[str], successes: dict[str, int], drive_attempts: int = 0) -> dict:
    """What a week at a repair facility does (FT p.35), given rolls the player made or typed.

    hull_rolled: damage points repaired (1D6 at a base). system_uids: the systems the player
    rolled for; successes maps a uid to how many successful rolls it got. A drive needs two
    (`drive_hits` counts down by one per success). Ruling: the drive is a system too, so each
    drive roll takes one of the three a week; failed attempts count too. Callers must
    reject too_many or invalid_drive plans before applying repairs."""
    hull_done = int((damage or {}).get("hull") or 0)
    repaired_hull = max(0, min(hull_done, 6, int(hull_rolled or 0)))
    chosen = [uid for uid in system_uids[:REPAIR_SYSTEMS_PER_WEEK]
              if uid in repairable_systems(design, damage)]
    fixed = [uid for uid in chosen if int(successes.get(uid, 0)) >= 1]
    drive_hits = int((damage or {}).get("drive_hits") or 0)
    drive_success = int(successes.get("drive", 0))
    invalid_drive = not 0 <= drive_success <= drive_attempts
    drive_repaired = 0 if invalid_drive else min(drive_hits, drive_success)
    return {
        "hull": repaired_hull,
        "systems": fixed,
        "drive_hits": drive_repaired,
        "too_many": len(system_uids) + drive_attempts > REPAIR_SYSTEMS_PER_WEEK,
        "invalid_drive": invalid_drive,
    }


def ship_counts(fleet: dict) -> dict[str, int]:
    counts: dict[str, int] = {}
    for s in fleet.get("ships", []):
        counts[s.get("status", "ready")] = counts.get(s.get("status", "ready"), 0) + 1
    return counts
