"""Fleet-level rules Cross Dimensions and Project Continuum share: battle riders, motherships and
system defence ships (CD pp.34-35, PC pp.89-90), dummy bogeys (CD p.37, PC p.95), the fleet
composition limits (CD p.57, PC p.139) and fleet morale (CD p.40).

These judge a fleet as a whole, so they take the fleet's ships with their designs. Ships marked
destroyed take no part, as in the fleet's points. The ruleset hands in what differs: how it
classes a ship, what it counts as stationary and which option, if any, dummy bogeys need.
"""

from __future__ import annotations

from collections.abc import Callable

from i18n import _
from rulesets import Issue, common

_int = common.as_int

# CD p.35, PC p.90: "the maximum mass for any battle rider is 60".
RIDER_MAX_MASS = 60


def _carriers(design: dict) -> list[tuple[int, bool]]:
    """What one FTL ship can carry into battle as (MASS, combines), one entry per bay or drive.
    A tender bay carries ships of its capacity (CD p.34); a tug drive tows its transfer MASS,
    and only tugs with advanced FTL may combine to haul one ship bigger than each could."""
    if design.get("ftl") is not True:
        return []
    out = []
    for s in common.systems_of(design):
        if s.get("type") == "tender_bay":
            out.append((max(1, _int(s.get("capacity"), 1)), False))
        elif s.get("type") == "tug_drive":
            out.append((max(1, _int(s.get("tow_mass"), 1)), design.get("ftl_advanced") is True))
    return out


def _fits(riders: list[int], bins: list[int]) -> bool:
    """Every rider in some bin without overfilling it: an exact search, riders biggest first.
    Fleets are small, and bins of equal space left are tried once, so this stays quick."""
    if not riders:
        return True
    if sum(riders) > sum(bins):
        return False
    head, rest = riders[0], riders[1:]
    tried = set()
    for i, space in enumerate(bins):
        if space < head or space in tried:
            continue
        tried.add(space)
        bins[i] -= head
        ok = _fits(rest, bins)
        bins[i] += head
        if ok:
            return True
    return False


def jump_blockers(ships: list[tuple[dict, dict]]) -> tuple[list[dict], bool]:
    """For a group travelling together between stars: (ships that cannot travel at all, whether
    the rest all make the jump). A ship jumps on its own FTL drive, or rides in a tender bay or
    behind a tug of the group (FT p.27, CD p.34): a ship without FTL, with its main drive
    knocked out, or a hulk needs carrying (FT p.35 points drive-disabled ships at tugs). A
    starbase or gate never moves. Destroyed ships are left out."""
    fixed, riders, carriers = [], [], []
    for s, d in ships:
        if s.get("status") == "destroyed":
            continue
        if d.get("hull_kind") == "starbase" or any(
                x.get("type") in ("jump_gate", "portal") for x in common.systems_of(d)):
            fixed.append(s)
            continue
        disabled = _int((s.get("damage") or {}).get("drive_hits")) >= 2 or s.get("status") == "hulk"
        if d.get("ftl") is True and not disabled:
            carriers += _carriers(d)
        else:
            riders.append(max(1, _int(d.get("tmf"), 1)))
    bins = [mass for mass, combines in carriers if not combines]
    pooled = sum(mass for mass, combines in carriers if combines)
    if pooled:
        bins.append(pooled)
    return fixed, _fits(sorted(riders, reverse=True), bins)


def _composition(live: list[tuple[dict, dict]], options: dict, ship_points,
                 ship_class: Callable[[int], str]) -> list[Issue]:
    """CD p.57's fleet composition limits, each a fleet option: a patrol battle has no capitals
    and at most half its points on cruisers; a larger battle at most half on capitals, "including
    their fighters", so a ship's points are its loadout's too."""
    if not (options.get("cd_patrol_battle") or options.get("cd_capital_limit")):
        return []
    by_class: dict[str, int] = {}
    for s, d in live:
        cls = ship_class(_int(d.get("tmf")))
        by_class[cls] = by_class.get(cls, 0) + ship_points(s, d)
    total = sum(by_class.values())
    issues = []
    if options.get("cd_patrol_battle"):
        if by_class.get("capital"):
            issues.append(Issue("patrol_capital", "violation",
                                _("A patrol battle fleet has no capital ships.")))
        if 2 * by_class.get("cruiser", 0) > total:
            issues.append(Issue("patrol_cruisers", "violation", _(
                "A patrol battle fleet spends at most half its points on cruisers "
                "({n} of {m}).", n=by_class.get("cruiser", 0), m=total)))
    if options.get("cd_capital_limit") and 2 * by_class.get("capital", 0) > total:
        issues.append(Issue("capital_limit", "violation", _(
            "At most half the fleet's points on capital ships, fighters included ({n} of {m}).",
            n=by_class.get("capital", 0), m=total)))
    return issues


def morale_mass(ships: list[tuple[dict, dict]]) -> tuple[int, int]:
    """(MASS destroyed, MASS at which the fleet withdraws): half the fleet's MASS (CD p.40)."""
    total = sum(max(0, _int(d.get("tmf"))) for _, d in ships)
    lost = sum(max(0, _int(d.get("tmf"))) for s, d in ships if s.get("status") == "destroyed")
    return lost, (total + 1) // 2


def fleet_issues(fleet: dict, ships: list[tuple[dict, dict]], options: dict, *,
                 ship_class: Callable[[int], str], stationary: Callable[[dict], bool],
                 ship_points=lambda ship, design: 0,
                 dummy_option: tuple[str, str] | None = None) -> list[Issue]:
    """`dummy_option` is (option key, its name) where dummy bogeys need a fleet option."""
    issues: list[Issue] = []
    live = [(s, d) for s, d in ships if s.get("status") != "destroyed"]
    issues += _composition(live, options, ship_points, ship_class)

    dummies = max(0, _int(fleet.get("dummy_bogeys"), 0))
    if dummies:
        if dummy_option and options.get(dummy_option[0]) is False:
            issues.append(Issue("option_off", "violation", _(
                "Dummy bogeys need the fleet option: {name}.", name=dummy_option[1])))
        if dummies > len(live):
            issues.append(Issue("too_many_dummies", "violation", _(
                "At most one dummy bogey per real ship: {n} bogeys for {m} ships.",
                n=dummies, m=len(live))))

    if options.get("cd_system_defence"):
        return issues
    # Starbase sections and gates are terrain, not battle riders: they never move.
    riders = [(s, d) for s, d in live if d.get("ftl") is not True and not stationary(d)]
    if not riders:
        return issues
    for s, d in riders:
        if _int(d.get("tmf")) > RIDER_MAX_MASS:
            issues.append(Issue("non_ftl_ship", "violation", _(
                "{name} has no FTL drive and is over MASS {n}, so it cannot be a battle rider. "
                "A system defence ship needs the fleet option.",
                name=s.get("name") or d.get("name", ""), n=RIDER_MAX_MASS)))
    small = sorted((_int(d.get("tmf")) for _, d in riders if _int(d.get("tmf")) <= RIDER_MAX_MASS),
                   reverse=True)
    if not small:
        return issues
    carriers = [c for _, d in live for c in _carriers(d)]
    bins = [mass for mass, combines in carriers if not combines]
    pooled = sum(mass for mass, combines in carriers if combines)
    if pooled:
        bins.append(pooled)
    if not _fits(small, bins):
        issues.append(Issue("riders_without_mothership", "violation", _(
            "Battle riders of {need} MASS need motherships to carry them, and the fleet's "
            "tender bays and tug drives cannot carry them all ({have} MASS).",
            need=sum(small), have=sum(bins))))
    else:
        issues.append(Issue("battle_riders", "info", _(
            "Battle riders ride on the fleet's motherships, which must deploy with them.")))
    return issues

