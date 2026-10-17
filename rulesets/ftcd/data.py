"""FTCD ruleset data: the book, the system picker, fighter types, ship classifications.

Source: Full Thrust Cross Dimensions, chapter 11 (pp.41-47: design, the MASS and points table on
p.47), plus the optional systems of chapters 6, 9, 10 and 14. Page numbers are printed pages
(PDF page = printed + 1).
"""

from __future__ import annotations

from i18n import _
from rulesets import BookRef, ParamDef, SystemDef

BOOKS = (BookRef("CD", "Full Thrust: Cross Dimensions", "Full Thrust Cross Dimensions.pdf", 1),)

# CD p.47: group of 6, in the order of the book's table there.
FIGHTER_POINTS = {
    "standard": 18,
    "interceptor": 18,
    "fast": 24,
    "attack": 24,
    "long_range": 24,
    "heavy": 30,
    "torpedo": 36,
}
# CD p.30 and the p.47 table: +1 a fighter, +6 a group, each, on top of the type. Kinetic can be
# bought for every type but is of no benefit to interceptors and torpedo fighters.
FIGHTER_EXTRAS = {"ftl": 6, "kinetic": 6}
NO_KINETIC_BENEFIT = frozenset({"interceptor", "torpedo"})

# CD p.47: 1.5 MASS of hangar per fighter or per MASS of light vessel, so a 9-MASS bay holds a
# group of 6 or 6 MASS of craft. Light vessels (interface craft, shuttles) cost 2 a MASS.
BAY_CRAFT_MASS = 6
CRAFT_POINTS_PER_MASS = 2

# CD p.47: magazine space per salvo (2, ER 3) at 3 points per MASS; CD p.25: each extra stage
# adds 2 MASS and doubles the points, standard missiles only.
SALVO_SPACE = {"std": 2, "er": 3}
MAX_STAGES = 3


def fighter_label(fighter_type: str) -> str:
    return {
        "standard": _("Standard"), "interceptor": _("Interceptor"), "fast": _("Fast"),
        "attack": _("Attack"), "long_range": _("Long range"), "heavy": _("Heavy"),
        "torpedo": _("Torpedo"),
    }.get(fighter_type, fighter_type)

# CD p.42: escorts up to MASS 44, cruisers up to 90, anything bigger is a capital; 300 at most.
ESCORT_MAX, CRUISER_MAX, MAX_MASS = 44, 90, 300

# CD p.42: (label, code, low, high).
SHIP_CLASSES = (
    ("Scout or Courier", "SC", 4, 10),
    ("Corvette", "CT", 8, 16),
    ("Frigate", "FF", 14, 28),
    ("Destroyer", "DD", 24, 36),
    ("Heavy Destroyer", "DH", 30, 44),
    ("Light Cruiser", "CL", 40, 60),
    ("Patrol or Escort Cruiser", "CE", 50, 70),
    ("Heavy Cruiser", "CA", 60, 90),
    ("Battlecruiser", "BC", 80, 110),
    ("Battleship", "BB", 100, 140),
    ("Heavy Battleship", "BDN", 120, 160),
    ("Dreadnought", "DN", 140, 180),
    ("Superdreadnought", "SDN", 160, 300),
)
# The Attack Carrier (CVA, 150-300) is a role, so like FB it is never suggested.
CARRIER_CLASSES = (
    ("Escort Carrier", "CVE", 60, 140),
    ("Light Carrier", "CVL", 120, 180),
    ("Heavy Carrier", "CVH", 160, 300),
)
CARRIER_MIN_BAYS = 2

# CD p.43: descriptive only; 10/20/30/40/50 per cent. (lowest percentage, label)
HULL_DESCRIPTORS = ((50, "Super"), (40, "Strong"), (30, "Average"), (20, "Weak"), (0, "Fragile"))

# Systems behind a fleet option: chapter 10's optional rules, the multi-stage missiles of CD p.25
# and the "extremely optional" chapter 14 weapons.
OPTIONAL_SYSTEMS = {
    "enhanced_sensors", "superior_sensors", "weasel_cruiser", "weasel_capital", "ecm", "area_ecm",
    "minelayer", "minesweeper", "ortillery",
}
SUPER_WEAPONS = {"nova_cannon", "wave_gun", "reflex_field", "cloak"}


def system_defs() -> list[SystemDef]:
    """The Add-system picker, grouped and in the book's order within each group."""
    weapons, missiles, defence, craft, sensors, special, other = (
        _("Weapons"),
        _("Missiles"),
        _("Defences"),
        _("Hangars and bays"),
        _("Sensors and ECM"),
        _("Special systems"),
        _("Holds"),
    )
    six = ["F", "FS", "AS", "A", "AP", "FP"]
    arcs_1 = ParamDef("arcs", "arcs", _("Arcs"), ["F"], 1, 1)
    arcs_3 = ParamDef("arcs", "arcs", _("Arcs"), ["FP", "F", "FS"], 1, 6)
    arcs_any = ParamDef("arcs", "arcs", _("Arcs"), ["F"], 1, 6)
    stages = ParamDef("stages", "int", _("Stages"), 1, 1, 3)
    load = ParamDef("load", "choice", _("Load"), "std",
                    choices=(("std", _("Standard")), ("er", _("Extended range"))))

    def ref(page: int) -> dict:
        return {"book": "CD", "page": page}

    return [
        SystemDef("beam", _("Beam battery"), weapons,
                  (ParamDef("class", "int", _("Class"), 1, 1, 6),
                   ParamDef("arcs", "arcs", _("Arcs"), six, 1, 6)), **ref(45)),
        SystemDef("graser", _("Graser"), weapons,
                  (ParamDef("class", "int", _("Class"), 1, 1, 4), arcs_any), **ref(45)),
        SystemDef("pulse_torpedo", _("Torpedo"), weapons,
                  (ParamDef("class", "int", _("Class"), 1, 1, 4), arcs_any), **ref(45)),
        SystemDef("needle_beam", _("Needle weapon"), weapons, (arcs_1,), **ref(45)),
        SystemDef("submunition", _("Submunition pack"), weapons, (arcs_1,), **ref(45)),
        SystemDef("sm_launcher", _("Salvo missile launcher"), missiles, (arcs_3,), **ref(45)),
        SystemDef("sm_magazine", _("Salvo missile magazine"), missiles,
                  (ParamDef("capacity", "int", _("Capacity (MASS)"), 6, 2, None),
                   ParamDef("feeds", "uids", _("Feeds launchers"), [])), **ref(45)),
        SystemDef("sm_rack", _("Salvo missile rack"), missiles, (load, stages, arcs_3), **ref(45)),
        SystemDef("heavy_missile", _("Heavy missile"), missiles, (load, stages, arcs_3), **ref(45)),
        SystemDef("fire_control", _("Fire control"), defence, **ref(45)),
        SystemDef("pds", _("Point defence system"), defence, **ref(45)),
        SystemDef("scattergun", _("Scattergun"), defence, **ref(45)),
        SystemDef("adfc", _("Area-defence fire control"), defence, **ref(45)),
        SystemDef("screen", _("Screen"), defence,
                  (ParamDef("level", "int", _("Level"), 1, 1, None),), **ref(44)),
        SystemDef("advanced_screen", _("Advanced screen"), defence,
                  (ParamDef("level", "int", _("Level"), 1, 1, None),), **ref(44)),
        SystemDef("hangar", _("Fighter hangar bay"), craft,
                  (ParamDef("bays", "int", _("Fighter groups"), 1, 1, None),), **ref(44)),
        SystemDef("tender_bay", _("Tender bay"), craft,
                  (ParamDef("capacity", "int", _("Craft MASS carried"), 10, 1, None),), **ref(34)),
        SystemDef("tug_drive", _("Tug jump drive"), craft,
                  (ParamDef("tow_mass", "int", _("Towable MASS"), 50, 1, None),), **ref(34)),
        SystemDef("enhanced_sensors", _("Enhanced sensors"), sensors, **ref(37)),
        SystemDef("superior_sensors", _("Superior sensors"), sensors, **ref(37)),
        SystemDef("weasel_cruiser", _("Weasel emitter (cruiser)"), sensors, **ref(38)),
        SystemDef("weasel_capital", _("Weasel emitter (capital)"), sensors, **ref(38)),
        SystemDef("ecm", _("ECM system"), sensors, **ref(38)),
        SystemDef("area_ecm", _("Area-effect ECM"), sensors, **ref(38)),
        SystemDef("minelayer", _("Minelayer"), special,
                  (ParamDef("mines", "int", _("Mines carried"), 3, 0, None),), **ref(47)),
        SystemDef("minesweeper", _("Minesweeper"), special, **ref(47)),
        SystemDef("ortillery", _("Ortillery system"), special, **ref(39)),
        SystemDef("nova_cannon", _("Spinal-mount nova cannon"), special, (arcs_1,), **ref(55)),
        SystemDef("wave_gun", _("Wave gun"), special, (arcs_1,), **ref(55)),
        SystemDef("reflex_field", _("Reflex field"), special, **ref(56)),
        SystemDef("cloak", _("Cloaking field"), special, **ref(56)),
        SystemDef("hold", _("Hold"), other,
                  (ParamDef("kind", "choice", _("Kind"), "cargo",
                            choices=(("cargo", _("Cargo (H)")), ("passenger", _("Passengers (P)")),
                                     ("troop", _("Troops (T)")), ("lab", _("Science labs (S)")))),
                   ParamDef("mass", "int", _("MASS"), 10, 1, None)), **ref(44)),
    ]
