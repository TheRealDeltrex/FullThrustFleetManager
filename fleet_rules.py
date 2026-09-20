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
from rulesets import RULESETS, Issue

DESTROYED = "destroyed"
FLEET_OPTION_KEYS = (
    "core_systems", "rerolls", "fighter_endurance", "vector_movement",
    "mt_systems", "mt_superships", "mt_fighters",
)


def ruleset_of(fleet: dict):
    return RULESETS.get(fleet.get("ruleset"))


def fleet_options(fleet: dict) -> dict:
    opts = fleet.get("options")
    return {k: bool(opts.get(k)) for k in FLEET_OPTION_KEYS} if isinstance(opts, dict) else {}


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


def fleet_points(fleet: dict, designs: dict) -> int:
    opts = fleet_options(fleet)
    return sum(
        ship_points(s, designs.get(s.get("design_id")), opts)
        for s in fleet.get("ships", [])
        if s.get("status") != DESTROYED
    )


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
    issues = list(design_issues(design, options))
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
    fleet_issues = []
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
    """PLAN 7: non_conforming, mixed_faction, custom_ships (the ruleset badge is always shown)."""
    ships = fleet.get("ships", [])
    faction = fleet.get("faction")
    ship_designs = [designs.get(s.get("design_id")) for s in ships]
    mixed = faction is None or any(d is None or d.get("faction") != faction for d in ship_designs)
    return {
        "non_conforming": not fleet_conforming(fleet, designs),
        "mixed_faction": mixed,
        "custom_ships": any(design_is_custom(d) for d in ship_designs),
    }


def ship_counts(fleet: dict) -> dict[str, int]:
    counts: dict[str, int] = {}
    for s in fleet.get("ships", []):
        counts[s.get("status", "ready")] = counts.get(s.get("status", "ready"), 0) + 1
    return counts
