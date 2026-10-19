"""FTPC ruleset data: the books, the system picker, fighter types, ship classifications.

Source: Full Thrust Project Continuum, section 13 (pp.106-117: design) and its summary tables in
section 14 (pp.118-124), with the systems of sections 5-7 and the errata. Page numbers are printed
pages, which for this book are also the PDF pages.
"""

from __future__ import annotations

from i18n import _
from rulesets import BookRef, ParamDef, SystemDef, fleet_common

BOOKS = (
    BookRef("PC", "Full Thrust: Project Continuum", "Full Thrust - Project Continuum.pdf", 0),
    BookRef("PCE", "Project Continuum Errata", "Full Thrust - Project Continuum Errata.pdf", 0),
)

# PC p.123, points per wing of six. Fast, long range and heavy are types of their own and also
# modifications other types can buy (FIGHTER_EXTRAS).
FIGHTER_POINTS = {
    "standard": 18,
    "interceptor": 18,
    "attack": 24,
    "fast": 24,
    "long_range": 24,
    "heavy": 36,
    "torpedo": 36,
    "graser": 42,
    "plasma": 42,
    "mkp": 36,
    "missile": 24,
    "multi_role": 30,
    "assault_shuttle": 6,
}
# PC p.123: "+mod" upgrades bought per wing on top of the type. A light wing is eight fighters
# for the price of six (p.75); robot fighters are 6 less a wing (p.76).
FIGHTER_EXTRAS = {"ftl": 6, "fast": 6, "long_range": 6, "heavy": 18, "light": 0, "robot": -6}
# PC p.75: what a light wing may be, and the modifications it may not take.
LIGHT_TYPES = frozenset({"standard", "interceptor", "attack", "fast", "missile"})
LIGHT_FORBIDDEN = frozenset({"heavy", "long_range"})
# PC p.110: a fighter rack holds one wing of robot fighters, 6 MASS at 1 point a MASS.
FIGHTER_RACK_MASS = 6

# PC pp.80-82, 123-124: points per gunboat; they fly in squadrons of six (p.79).
GUNBOAT_POINTS = {
    "beam": 9, "plasma": 9, "graser": 9, "gatling": 15, "needle": 9, "pulse_torpedo": 12,
    "submunition": 12, "mkp": 15, "kgun": 12, "missile": 12, "rocket": 12, "pds": 9, "ads": 12,
    "scatterpack": 15, "plasma_bomber": 15,
}
GUNBOAT_SQUADRON = 6
# Squadron modifications (p.124): FTL +6, heavy or screened +12; electronic warfare +3 a
# gunboat per ECM level, three levels at most.
GUNBOAT_EXTRAS = {"ftl": 6, "heavy": 12}
GUNBOAT_ECM_POINTS = 3
GUNBOAT_ECM_MAX = 3
# PC p.79: a gunboat rack is 18 MASS for a squadron, its cost in the gunboats'. FTL gunboats
# cannot ride racks and count as MASS 4 in a boat bay (p.80), so a squadron needs 24 craft MASS.
GUNBOAT_RACK_MASS = 18
GUNBOAT_BOAT_MASS = 4
GUNBOAT_CARRIERS = ("gunboat_rack", "boat_bay")

# PC p.46: how much weapon MASS one MASS of turret holds, by the arcs the turret bears into.
TURRET_HOLDS = {6: 2, 5: 3, 4: 4, 3: 5, 2: 6}

# PC p.109: a hangar bay holds one wing of six fighters; a combined bay (the older rules, p.110)
# is 9 MASS and holds the same.
BAY_CRAFT_MASS = 6
CRAFT_POINTS_PER_MASS = 2
CARRIER_BAY_TYPES = frozenset({"hangar", "hangar_bay"})

# PC p.52: magazine space per salvo, 2 standard, 3 extended range; multi-stage missiles (p.52)
# add 2 MASS a stage and double the points.
SALVO_SPACE = {"std": 2, "er": 3}
MAX_STAGES = 3

RIDER_MAX_MASS = fleet_common.RIDER_MAX_MASS
DUMMY_BOGEY_POINTS = 20  # PC p.95

# PC p.91: an artificial jump gate's FTL drive moves 10 transfer MASS per MASS; a portal's is as
# big as its transfer MASS. Hull boxes at least 10% of the transfer MASS.
GATE_TRANSFER_PER_MASS = 10
GATE_TYPES = frozenset({"jump_gate", "portal"})

# A starbase is always thrust 0 (PC p.115).
HULL_KINDS = ("warship", "merchant", "starbase")

# PC p.108: four rows is the warship norm, five old or civilian ships, six bulk carriers and the
# like; an advanced hull (p.108) has three. Points per hull box for each.
HULL_ROW_CHOICES = (4, 5, 6)

# PC p.106: escorts up to MASS 44, cruisers up to 90, capitals above; 300 suggested at most.
ESCORT_MAX, CRUISER_MAX, MAX_MASS = 44, 90, 300

# PC p.106: (label, code, low, high).
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
CARRIER_CLASSES = (
    ("Escort Carrier", "CVE", 60, 140),
    ("Light Carrier", "CVL", 120, 180),
    ("Attack Carrier", "CVA", 150, 300),
)
CARRIER_MIN_BAYS = 2

# PC p.108: descriptive only; 10/20/30/40/50 per cent. (lowest percentage, label)
HULL_DESCRIPTORS = ((50, "Super"), (40, "Strong"), (30, "Average"), (20, "Weak"), (0, "Fragile"))

# Systems PC marks optional, "only if everyone agrees": launch catapults (p.110) and flawed
# designs (p.113).
OPTIONAL_SYSTEMS = {"flawed_design"}

# PC p.46 and the errata: 16 MASS of spinal mount per 50 MASS of ship or part of it.
SPINAL_MASS = {"small": 8, "medium": 16, "large": 32}
SPINAL_POINTS = {"beam": 4, "plasma": 4, "psp": 5}
SPINAL_MASS_PER_50 = 16


def system_defs() -> list[SystemDef]:
    """The Add-system picker, grouped and in the book's order within each group."""
    targeting, beams, projectiles, ordnance, spinal, defence, fields, craft, gates, sensors, \
        crew, other = (
            _("Fire control"),
            _("Beam weapons"),
            _("Projectile weapons"),
            _("Missiles and ordnance"),
            _("Spinal mounts"),
            _("Defences"),
            _("Fields, ECM and cloaks"),
            _("Hangars and bays"),
            _("Jump gates and portals"),
            _("Sensors"),
            _("Crew and boarding"),
            _("Holds and special systems"),
        )
    six = ["F", "FS", "AS", "A", "AP", "FP"]
    arcs_1 = ParamDef("arcs", "arcs", _("Arcs"), ["F"], 1, 1)
    arcs_3 = ParamDef("arcs", "arcs", _("Arcs"), ["FP", "F", "FS"], 1, 3)
    arcs_any = ParamDef("arcs", "arcs", _("Arcs"), ["FP", "F", "FS"], 1, 6)
    arcs_six = ParamDef("arcs", "arcs", _("Arcs"), six, 1, 6)
    stages = ParamDef("stages", "int", _("Stages"), 1, 1, 3)
    load = ParamDef("load", "choice", _("Load"), "std",
                    choices=(("std", _("Standard")), ("er", _("Extended range"))))
    level2 = ParamDef("level", "int", _("Level"), 1, 1, 2)

    def cls(top: int) -> ParamDef:
        return ParamDef("class", "int", _("Class"), 1, 1, top)

    def mass(label: str, default: int) -> ParamDef:
        return ParamDef("mass", "int", label, default, 1, None)

    def ref(page: int) -> dict:
        return {"book": "PC", "page": page}

    return [
        SystemDef("fire_control", _("Fire control"), targeting, **ref(36)),
        SystemDef("advanced_fire_control", _("Advanced fire control"), targeting, **ref(36)),
        SystemDef("beam", _("Beam battery"), beams, (cls(6), arcs_six), **ref(36)),
        SystemDef("emp", _("EMP projector"), beams, (cls(4), arcs_six), **ref(37)),
        SystemDef("plasma_cannon", _("Plasma cannon"), beams, (cls(4), arcs_any), **ref(37)),
        SystemDef("graser", _("Graser"), beams, (cls(4), arcs_any), **ref(38)),
        SystemDef("heavy_graser", _("Heavy graser"), beams,
                  (cls(3), arcs_any,
                   ParamDef("intensity", "choice", _("Kind"), "standard",
                            choices=(("standard", _("Standard")),
                                     ("high", _("High intensity (HiG)"))))), **ref(38)),
        SystemDef("phaser", _("Phaser"), beams, (cls(4), arcs_any), **ref(38)),
        SystemDef("transporter", _("Transporter beam"), beams, (cls(4), arcs_six), **ref(39)),
        SystemDef("gatling", _("Gatling battery"), beams, (arcs_any,), **ref(40)),
        SystemDef("twin_particle_array", _("Twin particle array"), beams, (arcs_any,), **ref(40)),
        SystemDef("meson", _("Meson projector"), beams, (arcs_any,), **ref(40)),
        SystemDef("needle_beam", _("Needle beam"), beams, (cls(4), arcs_3), **ref(41)),
        SystemDef("grav_gun", _("Gravitic gun"), beams, (cls(4), arcs_six), **ref(45)),
        SystemDef("pulser", _("Pulser"), beams, (arcs_any,), **ref(45)),
        SystemDef("turret", _("Turret"), beams,
                  (ParamDef("arcs", "arcs", _("Arcs"), ["FP", "F", "FS"], 2, 6),
                   ParamDef("mounts", "uids", _("Weapons"), [])), **ref(46)),
        SystemDef("pulse_torpedo", _("Pulse torpedo"), projectiles,
                  (ParamDef("range", "choice", _("Kind"), "standard",
                            choices=(("standard", _("Standard")), ("short", _("Short range")),
                                     ("long", _("Long range")),
                                     ("variable", _("Variable strength")))), arcs_3), **ref(41)),
        SystemDef("submunition", _("Submunition pack"), projectiles, (arcs_3,), **ref(42)),
        SystemDef("kgun", _("K-gun"), projectiles,
                  (cls(6),
                   ParamDef("range", "choice", _("Kind"), "standard",
                            choices=(("standard", _("Standard")), ("short", _("Short range")),
                                     ("long", _("Long range")))),
                   ParamDef("flak", "choice", _("Flak"), "no",
                            choices=(("no", _("No")), ("yes", _("Yes")))),
                   arcs_1), **ref(43)),
        SystemDef("mkp", _("Multiple kinetic penetrator"), projectiles, (arcs_1,), **ref(44)),
        SystemDef("boarding_torpedo_launcher", _("Boarding torpedo launcher"), projectiles,
                  (arcs_3,), **ref(44)),
        SystemDef("boarding_torpedoes", _("Boarding torpedoes"), projectiles,
                  (ParamDef("count", "int", _("Torpedoes"), 2, 1, None),), **ref(44)),
        SystemDef("fusion_array", _("Fusion array"), projectiles, (arcs_3,), **ref(44)),
        SystemDef("plasma_bolt", _("Plasma bolt launcher"), projectiles, (cls(6), arcs_3), **ref(54)),
        SystemDef("sm_launcher", _("Salvo missile launcher"), ordnance, (arcs_3,), **ref(52)),
        SystemDef("sm_magazine", _("Salvo missile magazine"), ordnance,
                  (ParamDef("capacity", "int", _("Capacity (MASS)"), 6, 2, None),
                   ParamDef("feeds", "uids", _("Feeds launchers"), [])), **ref(52)),
        SystemDef("sm_rack", _("One-shot salvo missile launcher"), ordnance,
                  (load, stages, arcs_3), **ref(52)),
        SystemDef("heavy_missile", _("Heavy missile"), ordnance, (load, stages, arcs_3), **ref(49)),
        SystemDef("am_missile", _("Antimatter missile"), ordnance, (arcs_3,), **ref(53)),
        SystemDef("rocket_pod", _("Rocket pod"), ordnance, (arcs_1,), **ref(53)),
        SystemDef("minelayer", _("Mine rack"), ordnance,
                  (ParamDef("mines", "int", _("Mines carried"), 2, 2, None),), **ref(55)),
        SystemDef("spinal_mount", _("Spinal mount"), spinal,
                  (ParamDef("kind", "choice", _("Kind"), "beam",
                            choices=(("beam", _("Beam")), ("plasma", _("Plasma")),
                                     ("psp", _("Point singularity projector")))),
                   ParamDef("size", "choice", _("Size"), "small",
                            choices=(("small", _("Small")), ("medium", _("Medium")),
                                     ("large", _("Large"))))), **ref(46)),
        SystemDef("nova_cannon", _("Nova cannon"), spinal, **ref(63)),
        SystemDef("wave_gun", _("Wave gun"), spinal, **ref(63)),
        SystemDef("screen", _("Screen"), defence,
                  (ParamDef("level", "int", _("Level"), 1, 1, None),), **ref(56)),
        SystemDef("advanced_screen", _("Advanced screen"), defence,
                  (ParamDef("level", "int", _("Level"), 1, 1, None),), **ref(56)),
        SystemDef("area_screen", _("Area screen"), defence, (level2,), **ref(60)),
        SystemDef("advanced_area_screen", _("Advanced area screen"), defence, (level2,), **ref(60)),
        SystemDef("pds", _("Point defence system"), defence, **ref(59)),
        SystemDef("ads", _("Area defence system"), defence, (arcs_any,), **ref(59)),
        SystemDef("adfc", _("Area-defence fire control"), defence, **ref(58)),
        SystemDef("aadfc", _("Advanced area-defence fire control"), defence, **ref(59)),
        SystemDef("scattergun", _("Scattergun"), defence, **ref(59)),
        SystemDef("grapeshot", _("Grapeshot launcher"), defence, **ref(60)),
        SystemDef("amsc", _("Antimatter suicide charge"), defence, **ref(58)),
        SystemDef("reflex_field", _("Reflex field"), defence, **ref(64)),
        SystemDef("stealth_field", _("Stealth field"), fields, (level2,), **ref(57)),
        SystemDef("holofield", _("Holofield"), fields, **ref(60)),
        SystemDef("ecm", _("ECM"), fields, (ParamDef("level", "int", _("Level"), 1, 1, 3),), **ref(61)),
        SystemDef("area_ecm", _("Area ECM"), fields,
                  (ParamDef("level", "int", _("Level"), 1, 1, 3),), **ref(61)),
        SystemDef("cloaking_device", _("Cloaking device"), fields, **ref(61)),
        SystemDef("cloaking_field", _("Cloaking field"), fields, **ref(62)),
        SystemDef("cloak", _("Tuffley cloak"), fields, **ref(63)),
        SystemDef("hangar_bay", _("Hangar bay"), craft, **ref(109)),
        SystemDef("launch_tube", _("Launch tube or flight deck"), craft,
                  (ParamDef("catapult", "choice", _("Catapult"), "no",
                            choices=(("no", _("No")), ("yes", _("Yes")))),), **ref(109)),
        SystemDef("hangar", _("Combined hangar bay"), craft, **ref(110)),
        SystemDef("boat_bay", _("Boat bay"), craft, (mass(_("Craft MASS carried"), 4),), **ref(110)),
        SystemDef("fighter_rack", _("Fighter rack"), craft, **ref(110)),
        SystemDef("gunboat_rack", _("Gunboat rack"), craft, **ref(79)),
        SystemDef("tender_bay", _("Tender bay"), craft,
                  (ParamDef("capacity", "int", _("Craft MASS carried"), 10, 1, None),), **ref(89)),
        SystemDef("tug_drive", _("Tug jump drive"), craft,
                  (ParamDef("tow_mass", "int", _("Towable MASS"), 50, 1, None),), **ref(89)),
        SystemDef("jump_gate", _("Jump gate drive"), gates,
                  (ParamDef("transfer_mass", "int", _("Transfer MASS"), 60, 1, None),), **ref(91)),
        SystemDef("portal", _("Portal drive"), gates,
                  (ParamDef("transfer_mass", "int", _("Transfer MASS"), 20, 1, None),), **ref(91)),
        SystemDef("enhanced_sensors", _("Enhanced sensors"), sensors, **ref(111)),
        SystemDef("superior_sensors", _("Superior sensors"), sensors, **ref(112)),
        SystemDef("weasel_cruiser", _("Weasel emitter (cruiser)"), sensors, **ref(95)),
        SystemDef("weasel_capital", _("Weasel emitter (capital)"), sensors, **ref(95)),
        SystemDef("marines", _("Marine boarding parties"), crew,
                  (ParamDef("count", "int", _("Parties"), 1, 1, None),), **ref(111)),
        SystemDef("dcp", _("Additional damage control parties"), crew,
                  (ParamDef("count", "int", _("Parties"), 1, 1, None),), **ref(111)),
        SystemDef("troop_berthing", _("Troop berthing"), crew, (mass(_("MASS"), 1),), **ref(110)),
        SystemDef("passenger_berthing", _("Passenger berthing"), crew, (mass(_("MASS"), 1),),
                  **ref(111)),
        SystemDef("hold", _("Hold"), other,
                  (ParamDef("kind", "choice", _("Kind"), "cargo",
                            choices=(("cargo", _("Cargo (H)")), ("passenger", _("Passengers (P)")),
                                     ("troop", _("Troops (T)")), ("lab", _("Science labs (S)")))),
                   mass(_("MASS"), 10)), **ref(110)),
        SystemDef("minesweeper", _("Minesweeper"), other, **ref(112)),
        SystemDef("ortillery", _("Ortillery system"), other, **ref(113)),
        SystemDef("shipyard", _("Shipyard"), other, (mass(_("MASS"), 50),), **ref(111)),
        SystemDef("flawed_design", _("Flawed design"), other, **ref(113)),
    ]
