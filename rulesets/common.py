"""What more than one ruleset shares: reading stored designs, rounding, arcs, damage-track
splits, CF dots, labels, class bands and the salvo-missile checks. A ruleset imports these from
here rather than from another ruleset."""

from __future__ import annotations

import math
from collections.abc import Callable

from i18n import _


def fighter_label(fighter_type: str) -> str:
    """The name a loadout key is shown by, in every ruleset (FB1 p.11, FT/MT, FB2, CD p.47,
    PC p.123)."""
    return {
        "standard": _("Standard"), "interceptor": _("Interceptor"), "fast": _("Fast"),
        "attack": _("Attack"), "long_range": _("Long range"), "heavy": _("Heavy"),
        "torpedo": _("Torpedo"), "drone": _("Drone"), "graser": _("Graser"),
        "plasma": _("Plasma"), "mkp": _("MKP"), "missile": _("Missile"),
        "multi_role": _("Multi-role"), "assault_shuttle": _("Assault shuttles"),
    }.get(fighter_type, fighter_type)


# FB six arcs, clockwise from fore (PLAN 5.1). FT2 has its own four (rulesets/ft2/data.py).
ARCS = ("F", "FS", "AS", "A", "AP", "FP")

# Systems that hold fighter groups, in every ruleset: a hangar (FB, CD; PC's combined bay), a PC
# hangar bay or fighter rack, an FT2 fighter group and a Sa'Vasku drone womb. The loadout
# editor, the loadout reader and the PDF tracker all list fighters by these.
FIGHTER_BAY_TYPES = ("hangar", "hangar_bay", "fighter_rack", "fighter_group", "drone_womb")
# Systems that carry a PC gunboat squadron (PC pp.79-80).
GUNBOAT_CARRIER_TYPES = ("gunboat_rack", "boat_bay")


def round_half_up(numerator: int, denominator: int = 1) -> int:
    """numerator/denominator rounded .5 up, in integers so 25.5 never becomes 25.4999."""
    return (2 * numerator + denominator) // (2 * denominator)


def pct_mass(tmf: int, percent: int) -> int:
    """percent % of tmf, rounded .5 up, never below 1 (FB1 p.10)."""
    return max(1, round_half_up(tmf * percent, 100))


def arcs_valid(arcs: object, allowed: tuple[str, ...] = ARCS) -> bool:
    return (
        isinstance(arcs, list)
        and len(arcs) > 0
        and all(isinstance(a, str) and a in allowed for a in arcs)
        and len(set(arcs)) == len(arcs)
    )


def arcs_contiguous(arcs: list[str]) -> bool:
    """True if the arcs form one unbroken run around the ship (all six counts)."""
    idx = sorted(ARCS.index(a) for a in set(arcs))
    if len(idx) in (0, len(ARCS)):
        return len(idx) > 0
    # Exactly one gap between consecutive members, going round the circle.
    gaps = sum(1 for i, a in enumerate(idx) if (idx[(i + 1) % len(idx)] - a) % len(ARCS) != 1)
    return gaps == 1


def split_rows(total: int, rows: int) -> list[int]:
    """total split into rows, extras in the upper rows (FB1 p.5; also FB1 p.8 holds)."""
    base, extra = divmod(max(0, total), rows)
    return [base + (1 if i < extra else 0) for i in range(rows)]


def cf_positions(boxes: int, crew_factors: int) -> list[int]:
    """1-based damage-track boxes carrying a crew-factor dot (FB1 p.8): step = ceil(boxes / CF),
    a dot every step boxes, the last dot in the last box. With fewer boxes than CFs a box carries
    several dots (positions repeat), so losing it costs all of them."""
    if boxes <= 0 or crew_factors <= 0:
        return []
    step = math.ceil(boxes / crew_factors)
    return [min(i * step, boxes) for i in range(1, crew_factors)] + [boxes]


# Catalog sources that are not rulebooks: web pages a design links to by its source url.
WEB_SOURCES = {"SR": "Star Ranger"}


def source_ref(source: dict) -> str:
    """Where a catalog design is printed: "FB1 p.16", or a web source's name."""
    book = str(source.get("book") or "")
    if book in WEB_SOURCES:
        return WEB_SOURCES[book]
    return f"{book} p.{source.get('page')}"


def convert_star_ranger(design: dict, long_torpedo: dict) -> list[str]:
    """A Star Ranger design's systems in the CD and PC terms that equal them; the notes it adds.
    The long-range pulse torpedo (MASS 8 +2 an arc, 3 a MASS) is CD's class-2 torpedo and PC's
    long-range one (`long_torpedo` holds the fields), the IF heavy missile rack (2 MASS, 6
    points, one shot) their standard heavy missile."""
    if (design.get("source") or {}).get("book") != "SR":
        return []
    changes = []
    for s in systems_of(design):
        if s.get("type") == "lrpt":
            s.update({"type": "pulse_torpedo", **long_torpedo})
            if "torpedo" not in changes:
                changes.append("torpedo")
        elif s.get("type") == "mt_missile":
            s.update({"type": "heavy_missile", "load": "std", "arcs": ["FP", "F", "FS"]})
            if "missile" not in changes:
                changes.append("missile")
    return changes


# ---- Reading stored designs ---------------------------------------------------------------------


def as_int(value: object, default: int = 0) -> int:
    """Stored designs are semi-untrusted (imports), so a bad number counts as default instead of
    raising; validation reports what matters."""
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return default


def systems_of(design: dict) -> list[dict]:
    systems = design.get("systems")
    return [s for s in systems if isinstance(s, dict)] if isinstance(systems, list) else []


def arcs_of(system: dict) -> list[str]:
    arcs = system.get("arcs")
    return arcs if isinstance(arcs, list) else []


def loadout_entries(loadout: object, key: str) -> list[dict]:
    if not isinstance(loadout, dict) or not isinstance(loadout.get(key), list):
        return []
    return [e for e in loadout[key] if isinstance(e, dict)]


def half_turn_thrust(thrust: int) -> int:
    """FB1 p.5, CD p.10: half the thrust, rounded down; thrust 1 may always turn 1."""
    return 1 if thrust == 1 else thrust // 2


# ---- Labels -------------------------------------------------------------------------------------


def hangar_label(bays: int) -> str:
    """FB1 p.10, CD p.46: a bay holds one fighter group. A row normally is one bay; designs saved
    before the picker stopped offering a group count may still hold several."""
    if bays == 1:
        return _("Hangar bay (1 fighter group)")
    return _("Hangar bay ({n} fighter groups)", n=bays)


def hold_label(kind: object) -> str:
    return {
        "passenger": _("Passenger space"),
        "troop": _("Troop space"),
        "lab": _("Science labs"),
    }.get(kind if isinstance(kind, str) else "", _("Cargo hold"))


def class_label(label: str) -> str:
    """A ship classification from the Fleet Book family of class tables, translated."""
    return {
        "Scout or Courier": _("Scout or Courier"),
        "Corvette": _("Corvette"),
        "Frigate": _("Frigate"),
        "Destroyer": _("Destroyer"),
        "Heavy Destroyer": _("Heavy Destroyer"),
        "Light Cruiser": _("Light Cruiser"),
        "Patrol or Escort Cruiser": _("Patrol or Escort Cruiser"),
        "Heavy Cruiser": _("Heavy Cruiser"),
        "Battlecruiser": _("Battlecruiser"),
        "Battleship": _("Battleship"),
        "Heavy Battleship": _("Heavy Battleship"),
        "Dreadnought": _("Dreadnought"),
        "Superdreadnought": _("Superdreadnought"),
        "Escort Carrier": _("Escort Carrier"),
        "Light Carrier": _("Light Carrier"),
        "Attack Carrier": _("Attack Carrier"),
        "Merchant": _("Merchant"),
    }[label]


def hull_descriptor_label(label: str) -> str:
    return {
        "Fragile": _("Fragile"),
        "Weak": _("Weak"),
        "Average": _("Average"),
        "Strong": _("Strong"),
        "Super": _("Super"),
    }[label]


def hull_descriptor(boxes: int, tmf: int, descriptors: tuple[tuple[int, str], ...]) -> str:
    """The descriptor of the highest (lowest percentage, label) band the hull reaches."""
    percent = 100 * boxes / tmf if tmf else 0
    for low, label in descriptors:
        if percent >= low:
            return hull_descriptor_label(label)
    return hull_descriptor_label("Fragile")


def pick_class(tmf: int, classes: tuple) -> tuple[str, str]:
    """(label, code) of the (label, code, low, high) band containing tmf whose centre is nearest,
    ties to the smaller class. An open-ended band (high None) counts its lower bound as the
    centre; below the smallest band is the smallest, above the largest the largest."""
    best = None
    for label, code, low, high in classes:
        if tmf < low or (high is not None and tmf > high):
            continue
        centre = low if high is None else (low + high) / 2
        dist = abs(tmf - centre)
        if best is None or dist < best[0]:
            best = (dist, label, code)
    if best is None:
        label, code = (classes[0] if tmf < classes[0][2] else classes[-1])[:2]
        return class_label(label), code
    return class_label(best[1]), best[2]


# ---- Salvo missiles (FB1 p.9, CD p.25) ----------------------------------------------------------


def validate_missiles(design: dict, systems: list[dict], by_uid: dict, violation: Callable,
                      salvo_space: Callable[[dict, str], int | None]) -> None:
    """Magazine feeds and salvo loads. `salvo_space(entry, salvo)` is the magazine MASS one salvo
    of a load takes, or None for an unknown salvo."""
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

    loaded: dict[str, int] = {}  # magazine uid -> MASS its loads take, over every entry for it
    seen: set[str] = set()
    for entry in loadout_entries(design.get("default_loadout"), "magazines"):
        mag = by_uid.get(entry.get("magazine"))
        if not mag or mag.get("type") != "sm_magazine":
            violation("salvos_without_magazine", _("Salvo load for a magazine this design does not have."))
            continue
        if mag["uid"] in seen:
            # One load per magazine, so its stage count is one too (CD p.25, PC p.52).
            violation("magazine_loaded_twice", _("A magazine has one salvo load."), mag["uid"])
        seen.add(mag["uid"])
        salvos = entry.get("salvos") if isinstance(entry.get("salvos"), list) else []
        spaces = [salvo_space(entry, x) for x in salvos]
        if any(space is None for space in spaces):
            violation("unknown_salvo_type", _("Unknown salvo type."), mag.get("uid"))
            continue
        loaded[mag["uid"]] = loaded.get(mag["uid"], 0) + sum(spaces)
    for uid, used in loaded.items():
        capacity = as_int(by_uid[uid].get("capacity"))
        if used > capacity:
            violation(
                "magazine_overloaded",
                _("Salvo load needs {used} MASS but the magazine holds {cap}.", used=used, cap=capacity),
                uid,
            )
