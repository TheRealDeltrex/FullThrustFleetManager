"""The Imperial Tech Base (PC pp.125-127): an optional limit on the technologies one empire fields.

Each technology costs a number of "technology choices"; some come free, some come with another,
and some need a prerequisite, which then counts as well. A fleet's tech base is every technology
its live human designs use, with their prerequisites; the book recommends ten choices at most
(p.125), which is the limit the fleet option sets. The Fleet Book races are left out: the list is
written for the PC systems, which their tech modules do not use.
"""

from __future__ import annotations

from i18n import _
from rulesets import common

_int = common.as_int

LIMIT = 10  # PC p.125: "We recommend no more than ten but it's up to the players."

# key: (label, choices, prerequisites)
TECH: dict[str, tuple] = {
    "advanced_hull": (lambda: _("Advanced 3-row hull"), 1, ()),
    "catapult": (lambda: _("Launch tube catapults"), 1, ()),
    "advanced_drive": (lambda: _("Advanced gravity drive"), 3, ()),
    "advanced_ftl": (lambda: _("Advanced FTL drives"), 1, ()),
    "armour": (lambda: _("Armour"), 1, ()),
    "shell_armour": (lambda: _("Layered or shell armour"), 1, ("armour",)),
    "regen_armour": (lambda: _("Regenerative armour"), 2, ()),
    "stealth_hull": (lambda: _("Stealth hull"), 1, ()),
    "aadfc": (lambda: _("Advanced ADFC"), 1, ()),
    "pds": (lambda: _("PDS"), 1, ()),
    "ads": (lambda: _("ADS"), 1, ("pds",)),
    "scattergun": (lambda: _("Scattergun"), 1, ("grapeshot",)),
    "grapeshot": (lambda: _("Grapeshot"), 1, ()),
    "screens": (lambda: _("Screens"), 1, ()),
    "advanced_screens": (lambda: _("Advanced screens"), 2, ("screens",)),
    "area_screens": (lambda: _("Area screens"), 3, ("advanced_screens",)),
    "holofield": (lambda: _("Holofield"), 1, ()),
    "stealth_field": (lambda: _("Stealth fields"), 1, ()),
    "ecm": (lambda: _("ECM and area ECM"), 2, ()),
    "cloaking_device": (lambda: _("Cloaking device"), 1, ("stealth_field",)),
    "cloaking_field": (lambda: _("Cloaking field"), 1, ("stealth_field",)),
    "tuffley_cloak": (lambda: _("Tuffley cloak"), 1, ("stealth_field",)),
    "amsc": (lambda: _("Antimatter suicide charge"), 1, ()),
    "afc": (lambda: _("Advanced fire control"), 1, ()),
    "beams": (lambda: _("Beams, class 1-3"), 1, ()),
    "heavy_beams": (lambda: _("Beams, class 4-6"), 1, ("beams",)),
    "emp": (lambda: _("EMP projectors"), 1, ()),
    "plasma_cannon": (lambda: _("Plasma cannon"), 1, ()),
    "grasers": (lambda: _("Standard grasers"), 1, ("beams",)),
    "heavy_grasers": (lambda: _("Heavy grasers"), 1, ("grasers",)),
    "phasers": (lambda: _("Phasers"), 1, ("beams", "grasers")),
    "transporter": (lambda: _("Transporter beams"), 1, ()),
    "gatling": (lambda: _("Gatling battery"), 1, ("beams",)),
    "tpa": (lambda: _("Twin particle array"), 1, ("beams",)),
    "needle": (lambda: _("Needle beams"), 1, ()),
    "torpedoes": (lambda: _("Pulse torpedoes"), 1, ()),
    "overloaded_torpedoes": (lambda: _("Overloaded pulse torpedoes"), 1, ("torpedoes",)),
    "lr_torpedoes": (lambda: _("Long range pulse torpedoes"), 1, ("torpedoes",)),
    "vs_torpedoes": (lambda: _("Variable strength pulse torpedoes"), 1, ("torpedoes",)),
    "fusion_array": (lambda: _("Fusion array"), 1, ()),
    "submunition": (lambda: _("Submunition pack"), 1, ()),
    "kguns": (lambda: _("K-guns"), 1, ()),
    "lr_kguns": (lambda: _("Long range K-guns"), 1, ("kguns",)),
    "flak": (lambda: _("Flak ammunition"), 1, ()),
    "grav_gun": (lambda: _("Gravitic guns"), 1, ()),
    "boarding_torpedoes": (lambda: _("Boarding torpedoes"), 1, ()),
    "pulsers": (lambda: _("Pulsers"), 2, ("beams",)),
    "turrets": (lambda: _("Turrets"), 1, ()),
    "spinal_psp": (lambda: _("Spinal point singularity projector"), 2, ("grav_gun",)),
    "spinal_beam": (lambda: _("Spinal beam"), 1, ("beams",)),
    "spinal_plasma": (lambda: _("Spinal plasma"), 1, ("plasma_cannon",)),
    "am_missile": (lambda: _("Antimatter missiles"), 1, ()),
    "sml": (lambda: _("Salvo missile launchers and racks"), 1, ()),
    "er_missiles": (lambda: _("Extended range salvo missiles"), 1, ("sml",)),
    "rocket_pods": (lambda: _("Rocket pods"), 1, ()),
    "heavy_missiles": (lambda: _("Heavy missiles"), 1, ()),
    "mines": (lambda: _("Mine layer rack"), 1, ()),
    "mkp": (lambda: _("Multiple kinetic penetrators"), 1, ("kguns",)),
    "plasma_bolt": (lambda: _("Plasma bolt launcher"), 1, ()),
    "beam_fighter": (lambda: _("Standard beam fighters and interceptors"), 1, ("beams",)),
    "gun_fighter": (lambda: _("Standard gun fighters and interceptors"), 1, ("kguns",)),
    "heavy_fighters": (lambda: _("Heavy fighters"), 1, ()),
    "fast_fighters": (lambda: _("Fast fighters"), 1, ()),
    "long_range_fighters": (lambda: _("Long range fighters"), 1, ()),
    "attack_fighters": (lambda: _("Attack fighters"), 1, ()),
    "torpedo_fighters": (lambda: _("Torpedo fighters"), 1, ("torpedoes",)),
    "graser_fighters": (lambda: _("Graser fighters"), 1, ("grasers",)),
    "plasma_fighters": (lambda: _("Plasma fighters"), 1, ("plasma_cannon",)),
    "mkp_fighters": (lambda: _("MKP fighters"), 1, ("mkp",)),
    "missile_fighters": (lambda: _("Missile fighters"), 1, ("sml",)),
    "multi_role": (lambda: _("Multi-role fighters"), 3, ("attack_fighters",)),
    "robot_fighters": (lambda: _("Robot fighters and fighter racks"), 1, ()),
    "ftl_fighters": (lambda: _("FTL fighters"), 1, ()),
    "assault_shuttles": (lambda: _("Assault shuttles"), 1, ()),
    "gunboats": (lambda: _("Gunboats and gunboat racks"), 1, ()),
    "ftl_gunboats": (lambda: _("FTL gunboats"), 1, ("gunboats",)),
    "heavy_gunboats": (lambda: _("Heavy or screened gunboats"), 1, ("gunboats",)),
    "superior_sensors": (lambda: _("Superior sensors"), 1, ()),
    "minesweeper": (lambda: _("Minesweeper"), 1, ()),
}

# A system type and the technology it takes; types missing here are free (p.125 marks them 0).
SYSTEM_TECH = {
    "advanced_fire_control": "afc", "aadfc": "aadfc", "pds": "pds", "ads": "ads",
    "scattergun": "scattergun", "grapeshot": "grapeshot", "screen": "screens",
    "advanced_screen": "advanced_screens", "area_screen": "area_screens",
    "advanced_area_screen": "area_screens", "holofield": "holofield",
    "stealth_field": "stealth_field", "ecm": "ecm", "area_ecm": "ecm",
    "cloaking_device": "cloaking_device", "cloaking_field": "cloaking_field",
    "cloak": "tuffley_cloak", "amsc": "amsc", "emp": "emp", "plasma_cannon": "plasma_cannon",
    "graser": "grasers", "heavy_graser": "heavy_grasers", "phaser": "phasers",
    "transporter": "transporter", "gatling": "gatling", "twin_particle_array": "tpa",
    "needle_beam": "needle", "fusion_array": "fusion_array", "submunition": "submunition",
    "grav_gun": "grav_gun", "boarding_torpedo_launcher": "boarding_torpedoes",
    "boarding_torpedoes": "boarding_torpedoes", "pulser": "pulsers", "turret": "turrets",
    "am_missile": "am_missile", "sm_launcher": "sml", "sm_rack": "sml", "rocket_pod": "rocket_pods",
    "heavy_missile": "heavy_missiles", "minelayer": "mines", "mkp": "mkp",
    "plasma_bolt": "plasma_bolt", "fighter_rack": "robot_fighters", "gunboat_rack": "gunboats",
    "superior_sensors": "superior_sensors", "compact_superior_sensors": "superior_sensors",
    "minesweeper": "minesweeper",
}
FIGHTER_TECH = {
    "heavy": "heavy_fighters", "fast": "fast_fighters", "long_range": "long_range_fighters",
    "attack": "attack_fighters", "torpedo": "torpedo_fighters", "graser": "graser_fighters",
    "plasma": "plasma_fighters", "mkp": "mkp_fighters", "missile": "missile_fighters",
    "multi_role": "multi_role", "assault_shuttle": "assault_shuttles", "robot": "robot_fighters",
    "ftl": "ftl_fighters",
}
# p.127: a gunboat type "comes with" the matching ship technology.
GUNBOAT_TECH = {
    "beam": "beams", "plasma": "plasma_cannon", "graser": "grasers", "gatling": "gatling",
    "needle": "needle", "pulse_torpedo": "torpedoes", "submunition": "submunition", "mkp": "mkp",
    "kgun": "kguns", "missile": "sml", "rocket": "rocket_pods", "pds": "pds", "ads": "ads",
    "scatterpack": "scattergun", "plasma_bomber": "plasma_bolt",
}
SPINAL_TECH = {"psp": "spinal_psp", "beam": "spinal_beam", "plasma": "spinal_plasma"}


def _systems(design: dict) -> list[dict]:
    return common.systems_of(design)


def design_techs(design: dict, loadout: dict | None, options: dict) -> set[str]:
    """The technologies a human PC design and its loadout use, before prerequisites."""
    out: set[str] = set()
    systems = _systems(design)
    types = {s.get("type") for s in systems}
    if design.get("hull_advanced") is True and _int(design.get("hull_boxes")) >= 4:
        out.add("advanced_hull")
    if design.get("drive_advanced") is True and _int(design.get("thrust")) > 0:
        out.add("advanced_drive")
    if design.get("ftl_advanced") is True and design.get("ftl") is True:
        out.add("advanced_ftl")
    if _int(design.get("armour")) > 0:
        out.add("armour")
        layers = design.get("armour_layers")
        if isinstance(layers, list) and sum(1 for n in layers if _int(n)) > 1:
            out.add("shell_armour")
        if design.get("armour_regen") is True:
            out.add("regen_armour")
    if _int(design.get("stealth_hull")) > 0:
        out.add("stealth_hull")
    for s in systems:
        stype = s.get("type")
        if stype in SYSTEM_TECH:
            out.add(SYSTEM_TECH[stype])
        if stype == "beam":
            out.add("heavy_beams" if _int(s.get("class"), 1) >= 4 else "beams")
        elif stype == "pulse_torpedo":
            out.add({"long": "lr_torpedoes", "variable": "vs_torpedoes"}.get(s.get("range"), "torpedoes"))
            if options.get("pc_overload_torpedoes"):
                out.add("overloaded_torpedoes")
        elif stype == "kgun":
            out.add("lr_kguns" if s.get("range") == "long" else "kguns")
            if s.get("flak") == "yes":
                out.add("flak")
        elif stype == "spinal_mount":
            out.add(SPINAL_TECH.get(s.get("kind"), "spinal_beam"))
        elif stype == "meson" and not types & {"gatling", "twin_particle_array"}:
            out.add("gatling")  # p.126: it comes free with either; the cheaper chain is Gatling
        elif stype == "launch_tube" and s.get("catapult") == "yes":
            out.add("catapult")
        elif stype in ("sm_rack", "heavy_missile") and s.get("load") == "er":
            out.add("er_missiles")
    if loadout is None:
        loadout = design.get("default_loadout")
    for m in common.loadout_entries(loadout, "magazines"):
        if "er" in (m.get("salvos") if isinstance(m.get("salvos"), list) else []):
            out.add("er_missiles")
    for f in common.loadout_entries(loadout, "fighters"):
        kinds = [f.get("type"), *(f.get("extras") if isinstance(f.get("extras"), list) else [])]
        for kind in kinds:
            if kind in FIGHTER_TECH:
                out.add(FIGHTER_TECH[kind])
        if f.get("type") in ("standard", "interceptor", "multi_role"):
            # p.126: standard fighters come as beam or gun fighters; a ship with K-guns and no
            # beams flies the gun kind.
            out.add("gun_fighter" if "kgun" in types and "beam" not in types else "beam_fighter")
    for g in common.loadout_entries(loadout, "gunboats"):
        out.add("gunboats")
        if g.get("type") in GUNBOAT_TECH:
            out.add(GUNBOAT_TECH[g["type"]])
        extras = g.get("extras") if isinstance(g.get("extras"), list) else []
        if "ftl" in extras:
            out.add("ftl_gunboats")
        if "heavy" in extras:
            out.add("heavy_gunboats")
        if _int(g.get("ecm")) > 0:
            out.add("ecm")
    return out


def with_prerequisites(techs: set[str]) -> set[str]:
    out = set(techs)
    todo = list(techs)
    while todo:
        for need in TECH.get(todo.pop(), ("", 0, ()))[2]:
            if need not in out:
                out.add(need)
                todo.append(need)
    return {t for t in out if t in TECH}


def choices(techs: set[str]) -> int:
    return sum(TECH[t][1] for t in techs)


def label(tech: str) -> str:
    return TECH[tech][0]()


FIGHTER_TECHS = frozenset(FIGHTER_TECH.values()) | {"beam_fighter", "gun_fighter"}
GUNBOAT_TECHS = frozenset({"gunboats", "ftl_gunboats", "heavy_gunboats"})
