"""FB ruleset data: books, the system picker, fighter types, ship classifications.

Sources: FB1 pp.10-12 (design system, MASS and points table, classifications), FB2 p.3 (free
hull box count), FB2 p.4 (fighter types). Page numbers are printed pages.
"""

from __future__ import annotations

from i18n import _
from rulesets import BookRef, ParamDef, SystemDef

BOOKS = (
    BookRef("FB1", "Full Thrust Fleet Book 1", "Fleet Book 1.pdf", 0),
    BookRef("FB2", "Full Thrust Fleet Book 2", "Fleet Book 2.pdf", 0),
)

# Fighter group (6 fighters) costs, FB1 p.11 / FB2 p.4. Long-range groups have 9 CEF instead of 6.
FIGHTER_POINTS = {
    "standard": 18,
    "interceptor": 18,
    "fast": 24,
    "attack": 24,
    "long_range": 24,
    "heavy": 30,
    "torpedo": 36,
}
FIGHTER_BAY_MASS = 9  # 1.5 MASS per fighter, 6 per group (FB1 p.11)

# Salvo load per standard / ER salvo in a magazine (FB1 p.9).
SALVO_SPACE = {"std": 2, "er": 3}

# FB1 p.12: (label, code, low, high); high None = open-ended ("160+").
SHIP_CLASSES = (
    ("Scout or Courier", "SC", 4, 10),
    ("Corvette", "CT", 8, 16),
    ("Frigate", "FF", 14, 26),
    ("Destroyer", "DD", 24, 36),
    ("Heavy Destroyer", "DH", 30, 50),
    ("Light Cruiser", "CL", 40, 60),
    ("Patrol or Escort Cruiser", "CE", 50, 70),
    ("Heavy Cruiser", "CH", 60, 90),
    ("Battlecruiser", "BC", 80, 110),
    ("Battleship", "BB", 100, 140),
    ("Heavy Battleship", "BDN", 120, 160),
    ("Dreadnought", "DN", 140, 180),
    ("Superdreadnought", "SDN", 160, None),
)
# Attack Carrier (CVA, 150+) is a role rather than a size band, so it is never suggested.
CARRIER_CLASSES = (
    ("Escort Carrier", "CVE", 80, 140),
    ("Light Carrier", "CVL", 120, 180),
    ("Heavy Carrier", "CVH", 160, None),
)
# Suggest a carrier class from this many fighter bays up.
CARRIER_MIN_BAYS = 2

# FB2 p.3: descriptive only. (lowest percentage, label key)
HULL_DESCRIPTORS = ((45, "Super"), (35, "Strong"), (25, "Average"), (15, "Weak"), (0, "Fragile"))


def translated_class_label(label: str) -> str:
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
        "Heavy Carrier": _("Heavy Carrier"),
        "Merchant": _("Merchant"),
    }[label]


def translated_hull_descriptor(label: str) -> str:
    return {
        "Fragile": _("Fragile"),
        "Weak": _("Weak"),
        "Average": _("Average"),
        "Strong": _("Strong"),
        "Super": _("Super"),
    }[label]


def fighter_type_label(ftype: str) -> str:
    return {
        "standard": _("Standard fighters"),
        "interceptor": _("Interceptors"),
        "fast": _("Fast fighters"),
        "attack": _("Attack fighters"),
        "long_range": _("Long-range fighters"),
        "heavy": _("Heavy fighters"),
        "torpedo": _("Torpedo fighters"),
    }[ftype]


def system_defs() -> list[SystemDef]:
    """The Add-system picker for human tech, in display order. Built per call so labels follow
    the current language."""
    weapons, defence, craft, special, other = (
        _("Weapons"),
        _("Defences"),
        _("Hangars and bays"),
        _("Special systems"),
        _("Holds"),
    )
    arcs_1 = ParamDef("arcs", "arcs", _("Arcs"), ["F"], 1, 1)
    arcs_1_3 = ParamDef("arcs", "arcs", _("Arcs"), ["F"], 1, 3)
    arcs_any = ParamDef("arcs", "arcs", _("Arcs"), ["F"], 1, 6)
    fb1 = {"book": "FB1", "page": 11}
    return [
        SystemDef(
            "beam",
            _("Beam battery"),
            weapons,
            (
                ParamDef("class", "int", _("Class"), 1, 1, 6),
                ParamDef("arcs", "arcs", _("Arcs"), ["F", "FS", "AS", "A", "AP", "FP"], 1, 6),
            ),
            **fb1,
        ),
        SystemDef("pulse_torpedo", _("Pulse torpedo"), weapons, (arcs_1_3,), **fb1),
        SystemDef("needle_beam", _("Needle beam"), weapons, (arcs_1,), **fb1),
        SystemDef("submunition", _("Submunition pack"), weapons, (arcs_1,), **fb1),
        SystemDef("sm_launcher", _("Salvo missile launcher"), weapons, (arcs_any,), **fb1),
        SystemDef(
            "sm_magazine",
            _("Salvo missile magazine"),
            weapons,
            (
                ParamDef("capacity", "int", _("Capacity (MASS)"), 6, 2, None),
                ParamDef("feeds", "uids", _("Feeds launchers"), []),
            ),
            **fb1,
        ),
        SystemDef(
            "sm_rack",
            _("Salvo missile rack"),
            weapons,
            (
                ParamDef(
                    "load",
                    "choice",
                    _("Load"),
                    "std",
                    choices=(("std", _("Standard salvo")), ("er", _("ER salvo"))),
                ),
                arcs_any,
            ),
            **fb1,
        ),
        SystemDef("pds", _("Point defence system"), defence, **fb1),
        SystemDef("fire_control", _("Fire control"), defence, **fb1),
        SystemDef("adfc", _("Area-defence fire control"), defence, **fb1),
        SystemDef("screen", _("Screen"), defence, (ParamDef("level", "int", _("Level"), 1, 1, None),), **fb1),
        SystemDef(
            "hangar",
            _("Fighter hangar bay"),
            craft,
            (ParamDef("bays", "int", _("Fighter groups"), 1, 1, None),),
            **fb1,
        ),
        SystemDef(
            "tender_bay",
            _("Tender bay"),
            craft,
            (ParamDef("capacity", "int", _("Craft MASS carried"), 10, 1, None),),
            book="FB1",
            page=8,
        ),
        SystemDef("nova_cannon", _("Nova cannon"), special, (arcs_1,), **fb1),
        SystemDef("wave_gun", _("Wave gun"), special, (arcs_1,), **fb1),
        SystemDef("mt_missile", _("Missile (MT type)"), special, **fb1),
        SystemDef("ortillery", _("Ortillery system"), special, **fb1),
        SystemDef(
            "minelayer",
            _("Minelayer"),
            special,
            (ParamDef("mines", "int", _("Mines carried"), 3, 0, None),),
            **fb1,
        ),
        SystemDef("minesweeper", _("Minesweeper"), special, **fb1),
        SystemDef("reflex_field", _("Reflex field"), special, **fb1),
        SystemDef("cloak", _("Cloaking field"), special, **fb1),
        SystemDef(
            "tug_drive",
            _("Tug jump drive"),
            special,
            (ParamDef("tow_mass", "int", _("Towable MASS"), 50, 1, None),),
            book="FB1",
            page=8,
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
