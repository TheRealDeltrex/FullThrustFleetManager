"""Campaign scenarios (PLAN 11.3, roadmap step G2): a template turned into objectives, a last
week and who holds what, on whatever star map the campaign has. Pure: takes the map and the
sides, returns the settings, and the store applies them. Every template is an app rule; the
invasion follows the shape of FT pp.36-38's Lafayette Incident.

A side's home is its first naval base on the map, which the generator gives every side.
"""

from __future__ import annotations

import math

import starmap as maps
from i18n import _

KINDS = ("invasion", "raid", "border_war")
INVASION_WEEKS, RAID_WEEKS, BORDER_WAR_WEEKS = 7, 4, 10


def label(kind: str) -> str:
    return {"invasion": _("Invasion"), "raid": _("Raid"), "border_war": _("Border war")}.get(kind, kind)


def home(starmap: dict, side: str) -> dict | None:
    """The side's first naval base, else its first settled world, else its first outpost (a side
    may start with no base)."""
    own = [s for s in starmap["systems"] if s["owner"] == side]
    return next((s for test in (lambda s: s["base"], lambda s: s["kind"] == "settled",
                                lambda s: s["kind"] == "outpost") for s in own if test(s)), None)


def _apart(a: dict, b: dict) -> int:
    return maps.hex_distance((a["q"], a["r"]), (b["q"], b["r"]))


def build(kind: str, starmap: dict, sides: list[dict], attacker: str) -> tuple[dict | None, str]:
    """({owners {system name: side}, objectives, end_week, notes}, "") or (None, why not).

    - Invasion: the defender holds every system but the attacker's home; the attacker must take
      half the defender's settled worlds, rounded up, the defender's home among them, within
      seven weeks. One fewer with the home, or as many without it, is a draw.
    - Raid: the attacker must take the defender's settled world nearest to the attacker's home
      within four weeks.
    - Border war: both sides want more than half of all settled worlds within ten weeks;
      otherwise it is a draw.
    """
    if kind not in KINDS:
        return None, _("Unknown scenario.")
    ids = [s["id"] for s in sides]
    if attacker not in ids or len(ids) < 2:
        return None, _("Side not found.")
    defender = next(s for s in ids if s != attacker)
    names = {s["id"]: s["name"] for s in sides}
    own_home, their_home = home(starmap, attacker), home(starmap, defender)
    if not own_home or not their_home:
        return None, _("Both sides need a naval base on the map.")
    systems = starmap["systems"]
    owners = {s["name"]: s["owner"] for s in systems}
    if kind == "invasion":
        for s in systems:
            if s["kind"] != "empty" and s is not own_home:
                owners[s["name"]] = defender
        targets = [s for s in systems if s["kind"] == "settled" and owners[s["name"]] == defender]
        start = sum(s["kind"] == "settled" and owners[s["name"]] == attacker for s in systems)
        need = max(1, math.ceil(len(targets) / 2))
        draws = [{"count": start + need, "include": ""}]
        if need > 1:
            draws.insert(0, {"count": start + need - 1, "include": their_home["name"]})
        objectives = {attacker: {"count": start + need, "include": their_home["name"], "draw": draws}}
        notes = _("Invasion (app rule): {a} must hold {n} of {d}'s settled worlds, {home} among "
                  "them, by week {w}.", a=names[attacker], d=names[defender], n=need,
                  home=their_home["name"], w=INVASION_WEEKS)
        return {"owners": owners, "objectives": objectives, "end_week": INVASION_WEEKS,
                "notes": notes}, ""
    if kind == "raid":
        targets = [s for s in systems if s["kind"] == "settled" and s["owner"] == defender
                   and s is not their_home] or [their_home]
        target = min(targets, key=lambda s: (_apart(s, own_home), s["name"]))
        objectives = {attacker: {"count": 1, "include": target["name"], "draw": []}}
        notes = _("Raid (app rule): {a} must take {target} from {d} by week {w}.",
                  a=names[attacker], d=names[defender], target=target["name"], w=RAID_WEEKS)
        return {"owners": owners, "objectives": objectives, "end_week": RAID_WEEKS, "notes": notes}, ""
    settled = sum(s["kind"] == "settled" for s in systems)
    need = settled // 2 + 1
    objectives = {side: {"count": need, "include": "", "draw": []} for side in (attacker, defender)}
    notes = _("Border war (app rule): the first side to hold {n} of the {total} settled worlds "
              "wins; after week {w} it is a draw.", n=need, total=settled, w=BORDER_WAR_WEEKS)
    return {"owners": owners, "objectives": objectives, "end_week": BORDER_WAR_WEEKS, "notes": notes}, ""
