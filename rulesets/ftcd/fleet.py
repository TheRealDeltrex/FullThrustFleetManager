"""FTCD fleet-level rules: battle riders, motherships and system defence ships (CD pp.34-35),
and dummy bogeys (CD p.37).

These judge a fleet as a whole, so they take the fleet's ships with their designs. Ships marked
destroyed take no part, as in the fleet's points.
"""

from __future__ import annotations

from i18n import _
from rulesets import Issue
from rulesets.fb import rules as fb_rules
from rulesets.ftcd.data import RIDER_MAX_MASS

_int = fb_rules._int


def _carriers(design: dict) -> list[tuple[int, bool]]:
    """What one FTL ship can carry into battle as (MASS, combines), one entry per bay or drive.
    A tender bay carries ships of its capacity (CD p.34); a tug drive tows its transfer MASS,
    and only tugs with advanced FTL may combine to haul one ship bigger than each could."""
    if design.get("ftl") is not True:
        return []
    out = []
    for s in fb_rules._systems(design):
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


def fleet_issues(fleet: dict, ships: list[tuple[dict, dict]], options: dict) -> list[Issue]:
    issues: list[Issue] = []
    live = [(s, d) for s, d in ships if s.get("status") != "destroyed"]

    dummies = max(0, _int(fleet.get("dummy_bogeys"), 0))
    if dummies:
        if options.get("cd_optional_systems") is False:
            issues.append(Issue("option_off", "violation", _(
                "Dummy bogeys need the fleet option: {name}.",
                name=_("Sensors, ECM, mines and ortillery"))))
        if dummies > len(live):
            issues.append(Issue("too_many_dummies", "violation", _(
                "At most one dummy bogey per real ship: {n} bogeys for {m} ships.",
                n=dummies, m=len(live))))

    if options.get("cd_system_defence"):
        return issues
    riders = [(s, d) for s, d in live if d.get("ftl") is not True]
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

