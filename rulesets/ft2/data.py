"""FT2 ruleset data: books, arcs, the FT p.31 systems table, FT p.14 basic classes.

All values checked against the page images (the FT text layer is OCR). Printed page numbers.
"""

from __future__ import annotations

from i18n import _
from rulesets import BookRef

BOOKS = (
    BookRef("FT", "Full Thrust (2nd Edition)", "Full Thrust.pdf", 1),
    BookRef("MT", "More Thrust", "More Thrust.pdf", 0),
)

# FT p.8: four 90-degree arcs, clockwise from fore. No offensive fire through A (aft).
ARCS = ("F", "S", "A", "P")

# FT p.29: warship classification of a hull by MASS.
ESCORT_MAX, CRUISER_MAX, SHIP_MAX = 18, 36, 100
MERCHANT_MIN = 2
MAX_THRUST = 8  # FT p.30

# FT p.31 beam batteries: MASS, base points, points per arc covered (including the first).
BEAMS = {"A": (3, 4, 3), "B": (2, 3, 2), "C": (1, 2, 1)}

# FT p.31 fixed systems: type -> (MASS, points).
FIXED = {
    "pdaf": (1, 3),
    "adaf": (3, 10),
    "fighter_group": (6, 20),  # group incl. bay
    "needle_beam": (2, 6),
    "pulse_torpedo": (5, 15),
    "nova_cannon": (16, 50),
    "submunition": (1, 3),
    "minelayer": (3, 10),  # incl. 3 mines
    "minesweeper": (5, 20),
}
SCREEN_PER_LEVEL = (3, 25)  # FT p.31; levels 1-3 (FT p.10: level 3 is the maximum)
MAX_SCREEN_LEVEL = 3
EXTRA_FIRE_CONTROL = (3, 10)  # FT p.31, beyond the class allotment
STANDARD_FIRE_CONTROLS = {"escort": 1, "cruiser": 2, "capital": 3, "merchant": 1}  # FT pp.12, 15, 31

OFFENSIVE = {"beam", "needle_beam", "pulse_torpedo", "nova_cannon", "submunition", "aa_battery", "wave_gun"}
SINGLE_ARC = {"needle_beam", "pulse_torpedo", "nova_cannon", "aa_battery", "wave_gun"}
FORE_ONLY = {"nova_cannon", "wave_gun"}  # FT p.30 spinal mount; MT p.3 "along the main axis"
# FT p.31 "CAPITAL SHIPS ONLY" (nova), "Carriers and D/Noughts only" (fighters, read as capital
# class since the book never defines a carrier), MT p.3 (AA megabattery).
CAPITAL_ONLY = {"nova_cannon", "fighter_group", "aa_battery"}
# FT p.30: merchants may carry only these (plus their fire control and a tug drive).
MERCHANT_SYSTEMS = {"beam", "pdaf", "screen", "submunition", "fire_control", "tug_drive"}

# FT p.14 basic classes: (label, code, MASS). Codes follow FB1 p.12 where the name matches;
# FT2 prints none. Carriers and merchants are separate lists for type suggestion.
BASIC_CLASSES = {
    "escort": (
        ("Courier Boat", "SC", 2),
        ("Scoutship", "SC", 4),
        ("Corvette", "CT", 6),
        ("Frigate", "FF", 10),
        ("Destroyer", "DD", 14),
    ),
    "cruiser": (
        ("Light Cruiser", "CL", 22),
        ("Escort Cruiser", "CE", 26),
        ("Heavy Cruiser", "CH", 32),
    ),
    "capital": (
        ("Battlecruiser", "BC", 40),
        ("Battleship", "BB", 48),
        ("Battledreadnought", "BDN", 60),
        ("Superdreadnought", "SDN", 80),
    ),
    "carrier": (("Light Carrier", "CVL", 70), ("Fleet Carrier", "CV", 98)),
    "merchant": (("Exploration Cruiser", "M", 48), ("Heavy Freighter", "M", 60), ("Bulk Tanker", "M", 100)),
}
CARRIER_MIN_GROUPS = 2


def class_label(label: str) -> str:
    return {
        "Courier Boat": _("Courier Boat"),
        "Scoutship": _("Scoutship"),
        "Corvette": _("Corvette"),
        "Frigate": _("Frigate"),
        "Destroyer": _("Destroyer"),
        "Light Cruiser": _("Light Cruiser"),
        "Escort Cruiser": _("Escort Cruiser"),
        "Heavy Cruiser": _("Heavy Cruiser"),
        "Battlecruiser": _("Battlecruiser"),
        "Battleship": _("Battleship"),
        "Battledreadnought": _("Battledreadnought"),
        "Superdreadnought": _("Superdreadnought"),
        "Light Carrier": _("Light Carrier"),
        "Fleet Carrier": _("Fleet Carrier"),
        "Exploration Cruiser": _("Exploration Cruiser"),
        "Heavy Freighter": _("Heavy Freighter"),
        "Bulk Tanker": _("Bulk Tanker"),
    }[label]
