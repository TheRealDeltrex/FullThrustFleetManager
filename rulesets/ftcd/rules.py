"""FTCD costing, derived values and validation (Cross Dimensions chapter 11, human tech).

Cross Dimensions is the Fleet Book design system gathered into one book with a few additions,
so the shapes match rulesets/fb/rules.py and its missile and fighter checks are reused. What CD
changes: advanced hulls (three rows, x3), advanced drives and FTL (x3), streamlining at 5% and
10%, broadside arcs, classed torpedoes, grasers, advanced screens, scatterguns, heavy and
multi-stage missiles, the chapter 10 sensors and ECM, MASS limits, and the CPV hull cost.

Page numbers are printed pages of Full Thrust Cross Dimensions.
"""

from __future__ import annotations

import math
from collections.abc import Callable

from i18n import _
from rulesets import Breakdown, BreakdownRow, Issue, common
from rulesets.common import ARCS, arcs_contiguous, arcs_valid, round_half_up, split_rows
from rulesets.fb import rules as fb_rules
from rulesets.ftcd import data

_int = fb_rules._int
_systems = fb_rules._systems
_arcs = fb_rules._arcs

STREAMLINING_PERCENT = {"none": 0, "partial": 5, "full": 10}  # CD p.44
BROADSIDE = frozenset({"FS", "AS", "AP", "FP"})  # CD p.15: both side arcs each way, not F or A


def pct(tmf: int, tenths_percent: int) -> int:
    """tenths_percent/10 % of tmf, .5 up, never 0 (CD p.43). Tenths, for 7.5% screens."""
    return max(1, round_half_up(tmf * tenths_percent, 1000))


def _is_broadside(system: dict) -> bool:
    return set(_arcs(system)) == BROADSIDE and len(_arcs(system)) == 4


def _extra_arcs(system: dict) -> int:
    """Extra arcs beyond the first a weapon pays for; a broadside mount pays for two (CD p.45)."""
    return 2 if _is_broadside(system) else max(0, len(_arcs(system)) - 1)


def _transfer(system: dict) -> int:
    return max(1, _int(system.get("transfer_mass"), 1))


def transfer_mass(design: dict) -> int:
    """What the design's gate or portal drives move in one turn (CD p.35); 0 for a ship."""
    return sum(_transfer(s) for s in _systems(design) if s.get("type") in data.GATE_TYPES)


def stationary(design: dict) -> bool:
    """A starbase section or an artificial gate: terrain that never moves (CD pp.35, 51)."""
    return design.get("hull_kind") == "starbase" or transfer_mass(design) > 0


def _class(system: dict) -> int:
    return max(1, _int(system.get("class"), 1))


# ---- Per-system MASS and points ---------------------------------------------------------------


def _beam_mass(system: dict, tmf: int) -> int:
    cls = _class(system)
    n = len(_arcs(system))
    if cls == 1:
        return 1
    if cls == 2:
        # 3 adjacent arcs at base; six arcs or a broadside cost 3 (CD p.45).
        return 3 if n > 3 or _is_broadside(system) else 2
    base = 2 ** (cls - 1)
    return base + (base // 4) * _extra_arcs(system)


def _graser_mass(system: dict, tmf: int) -> int:
    cls = _class(system)
    if cls == 1:
        # CD p.45 prices one arc at 2, three at 3, broadside or six at 4. Two arcs is not
        # listed; it is charged as three, the cheapest listed mount that covers it.
        n = len(_arcs(system))
        if _is_broadside(system) or n > 3:
            return 4
        return 2 if n <= 1 else 3
    # Class 2 is 9 +3 per extra arc, class 3 is 24 +6, and "each higher class triples the base
    # mass and doubles the extra per arc". 24 is not 3 x 9, so the tripling runs from class 3.
    base = 9 if cls == 2 else 24 * 3 ** (cls - 3)
    per_arc = 3 * 2 ** (cls - 2)
    return base + per_arc * _extra_arcs(system)


def _torpedo_mass(system: dict, tmf: int) -> int:
    scale = 2 ** (_class(system) - 1)
    return 4 * scale + scale * _extra_arcs(system)  # CD p.45


def _screen_mass(system: dict, tmf: int) -> int:
    # CD p.44: level-1 5% (min 3), level-2 10% (min 6); generators beyond 2 are backups (p.20).
    level = max(1, _int(system.get("level"), 1))
    mass = max(3, pct(tmf, 50)) if level == 1 else max(6, pct(tmf, 100))
    return mass + max(0, level - 2) * pct(tmf, 50)


def _advanced_screen_mass(system: dict, tmf: int) -> int:
    # CD p.44: 7.5% per generator, minimum 4 for level-1 and 8 for level-2.
    level = max(1, _int(system.get("level"), 1))
    mass = max(4, pct(tmf, 75)) if level == 1 else max(8, pct(tmf, 150))
    return mass + max(0, level - 2) * pct(tmf, 75)


def _stages(system: dict) -> int:
    return max(1, _int(system.get("stages"), 1))


def _missile_mass(base_std: int, base_er: int) -> Callable[[dict, int], int]:
    # CD p.25: each extra stage adds 2 MASS (standard missiles only).
    def mass(system: dict, tmf: int) -> int:
        base = base_er if system.get("load") == "er" else base_std
        return base + 2 * (_stages(system) - 1)
    return mass


def _missile_points(base_std: int, base_er: int) -> Callable[[dict, int], int]:
    # Each extra stage doubles the points of the missile it is added to (CD p.25).
    def points(system: dict, mass: int) -> int:
        base = base_er if system.get("load") == "er" else base_std
        return 3 * base * 2 ** (_stages(system) - 1)
    return points


def _missile_label(plain: str, er: str) -> Callable[[dict], str]:
    def label(system: dict) -> str:
        text = er if system.get("load") == "er" else plain
        stages = _stages(system)
        return _("{name}, {n} stages", name=text, n=stages) if stages > 1 else text
    return label


SystemRule = tuple[Callable[[dict, int], int], Callable[[dict, int], int], Callable[[dict], str]]

SYSTEM_RULES: dict[str, SystemRule] = {
    "beam": (
        _beam_mass,
        lambda s, m: 3 * m,
        lambda s: _("Class-{n} beam battery", n=_class(s)),
    ),
    "graser": (_graser_mass, lambda s, m: 4 * m, lambda s: _("Class-{n} graser", n=_class(s))),
    "pulse_torpedo": (_torpedo_mass, lambda s, m: 3 * m, lambda s: _("Class-{n} torpedo", n=_class(s))),
    "needle_beam": (lambda s, t: 2, lambda s, m: 6, lambda s: _("Needle weapon")),
    "submunition": (lambda s, t: 1, lambda s, m: 3, lambda s: _("Submunition pack")),
    "sm_launcher": (lambda s, t: 3, lambda s, m: 9, lambda s: _("Salvo missile launcher")),
    "sm_magazine": (
        lambda s, t: max(1, _int(s.get("capacity"), 0)),
        lambda s, m: 3 * m,
        lambda s: _("SM magazine (capacity {n})", n=_int(s.get("capacity"), 0)),
    ),
    "sm_rack": (
        _missile_mass(4, 5),
        _missile_points(4, 5),
        _missile_label(_("Salvo missile rack"), _("Salvo missile rack (ER)")),
    ),
    "heavy_missile": (
        _missile_mass(2, 3),
        _missile_points(2, 3),
        _missile_label(_("Heavy missile"), _("Heavy missile (ER)")),
    ),
    "fire_control": (lambda s, t: 1, lambda s, m: 4, lambda s: _("Fire control")),
    "pds": (lambda s, t: 1, lambda s, m: 3, lambda s: _("Point defence system")),
    "scattergun": (lambda s, t: 1, lambda s, m: 4, lambda s: _("Scattergun")),
    "adfc": (lambda s, t: 2, lambda s, m: 8, lambda s: _("Area-defence fire control")),
    "screen": (
        _screen_mass,
        lambda s, m: 3 * m,
        lambda s: _("Screen level-{n}", n=max(1, _int(s.get("level"), 1))),
    ),
    "advanced_screen": (
        _advanced_screen_mass,
        lambda s, m: 4 * m,
        lambda s: _("Advanced screen level-{n}", n=max(1, _int(s.get("level"), 1))),
    ),
    "hangar": (
        lambda s, t: 9 * max(1, _int(s.get("bays"), 1)),
        lambda s, m: 3 * m,
        lambda s: fb_rules._hangar_label(max(1, _int(s.get("bays"), 1))),
    ),
    "tender_bay": (
        lambda s, t: max(1, round_half_up(3 * max(1, _int(s.get("capacity"), 1)), 2)),
        lambda s, m: 3 * m,
        lambda s: _("Tender bay (carries MASS {n})", n=max(1, _int(s.get("capacity"), 1))),
    ),
    "tug_drive": (
        # CD p.34: 1 extra FTL MASS per 5 transfer MASS. Rounded up, since the drive has to
        # cover the whole ship it tows (the book's 108 -> 22 agrees either way).
        lambda s, t: max(1, math.ceil(max(1, _int(s.get("tow_mass"), 1)) / 5)),
        lambda s, m: 2 * m,
        lambda s: _("Tug jump drive (tows MASS {n})", n=max(1, _int(s.get("tow_mass"), 1))),
    ),
    # CD p.35: the drive is paid as an FTL drive, 2 a MASS; it need not cover the gate's own MASS.
    "jump_gate": (
        lambda s, t: max(1, round_half_up(_transfer(s), data.GATE_TRANSFER_PER_MASS)),
        lambda s, m: 2 * m,
        lambda s: _("Jump gate drive (transfer MASS {n})", n=_transfer(s)),
    ),
    "portal": (
        lambda s, t: _transfer(s),
        lambda s, m: 2 * m,
        lambda s: _("Portal drive (transfer MASS {n})", n=_transfer(s)),
    ),
    "enhanced_sensors": (lambda s, t: 2, lambda s, m: 8, lambda s: _("Enhanced sensors")),
    "superior_sensors": (lambda s, t: 4, lambda s, m: 16, lambda s: _("Superior sensors")),
    "weasel_cruiser": (lambda s, t: 2, lambda s, m: 8, lambda s: _("Weasel emitter (cruiser)")),
    "weasel_capital": (lambda s, t: 4, lambda s, m: 16, lambda s: _("Weasel emitter (capital)")),
    "ecm": (lambda s, t: 4, lambda s, m: 16, lambda s: _("ECM system")),
    "area_ecm": (lambda s, t: 6, lambda s, m: 24, lambda s: _("Area-effect ECM")),
    "minelayer": (
        lambda s, t: 2 + max(0, _int(s.get("mines"), 0)),
        lambda s, m: 6 + 2 * (m - 2),
        lambda s: _("Minelayer ({n} mines)", n=max(0, _int(s.get("mines"), 0))),
    ),
    "minesweeper": (lambda s, t: 5, lambda s, m: 15, lambda s: _("Minesweeper")),
    "ortillery": (lambda s, t: 3, lambda s, m: 9, lambda s: _("Ortillery system")),
    "nova_cannon": (lambda s, t: 20, lambda s, m: 60, lambda s: _("Nova cannon")),
    "wave_gun": (lambda s, t: 12, lambda s, m: 36, lambda s: _("Wave gun")),
    "reflex_field": (lambda s, t: max(10, pct(t, 100)), lambda s, m: 6 * m, lambda s: _("Reflex field")),
    "cloak": (lambda s, t: max(2, pct(t, 100)), lambda s, m: 10 * m, lambda s: _("Cloaking field")),
    "hold": (
        lambda s, t: max(1, _int(s.get("mass"), 1)),
        lambda s, m: 0,
        lambda s: fb_rules._hold_label(s.get("kind")),
    ),
}


# ---- Hull and armour ----------------------------------------------------------------------------


def _advanced_hull(design: dict) -> bool:
    """CD p.43: fewer than four hull boxes is always a standard hull."""
    return design.get("hull_advanced") is True and _int(design.get("hull_boxes")) >= 4


def hull_rows(design: dict) -> int:
    return 3 if _advanced_hull(design) else 4


def shell_layers(design: dict) -> list[int]:
    """Armour boxes per layer, inner first (CD p.20), the same shape as the Phalon shell."""
    total = max(0, _int(design.get("armour")))
    raw = design.get("armour_layers")
    layers = [max(0, _int(n)) for n in raw] if isinstance(raw, list) else []
    while layers and layers[-1] == 0:
        layers.pop()
    if not layers:
        return [total] if total else []
    out: list[int] = []
    left = total
    for boxes in layers:
        out.append(min(boxes, left))
        left -= out[-1]
    return out


def shell_points(layers: list[int]) -> int:
    """CD p.44: standard armour (2 a box) times the layer number, which the table on p.47
    writes as "each layer x 2" and the text spells out as 2, 4, 8: each layer doubles."""
    return sum(2 ** (index + 1) * boxes for index, boxes in enumerate(layers))


def hull_cost(tmf: int, options: dict) -> int:
    """Basic hull points: MASS, or with the CPV option MASS squared / 100, at least 1 (CD p.58)."""
    if options.get("cd_cpv"):
        return max(1, round_half_up(tmf * tmf, 100)) if tmf > 0 else 0
    return tmf


# ---- Breakdown ------------------------------------------------------------------------------


def design_breakdown(design: dict, options: dict) -> Breakdown:
    tmf = max(0, _int(design.get("tmf")))
    boxes = max(0, _int(design.get("hull_boxes")))
    armour = max(0, _int(design.get("armour")))
    thrust = max(0, _int(design.get("thrust")))
    advanced_hull = _advanced_hull(design)
    advanced_drive = design.get("drive_advanced") is True
    advanced_ftl = design.get("ftl_advanced") is True and design.get("ftl") is True
    ftl_mass = pct(tmf, 100) if design.get("ftl") is True and tmf > 0 else 0
    drive_mass = pct(tmf, 50 * thrust) if thrust > 0 and tmf > 0 else 0
    stream_pct = STREAMLINING_PERCENT.get(design.get("streamlining"), 0)
    stream_mass = pct(tmf, 10 * stream_pct) if stream_pct and tmf > 0 else 0
    layers = shell_layers(design)

    rows = [
        BreakdownRow("hull", _("Basic hull (MASS {n})", n=tmf), 0, hull_cost(tmf, options)),
        BreakdownRow(
            "hull_integrity",
            _("Advanced hull ({n} boxes)", n=boxes) if advanced_hull
            else _("Hull integrity ({n} boxes)", n=boxes),
            boxes,
            (3 if advanced_hull else 2) * boxes,
        ),
    ]
    if armour:
        label = (_("Shell armour ({n} boxes)", n=armour) if len(layers) > 1
                 else _("Armour ({n} boxes)", n=armour))
        rows.append(BreakdownRow("armour", label, armour, shell_points(layers)))
    if drive_mass:
        rows.append(BreakdownRow(
            "main_drive",
            _("Advanced drive (thrust-{n})", n=thrust) if advanced_drive
            else _("Main drive (thrust-{n})", n=thrust),
            drive_mass, (3 if advanced_drive else 2) * drive_mass))
    if ftl_mass:
        # CD p.33: an advanced FTL is paid at the standard rate unless the players agree to
        # pay for it (always in a campaign); the fleet option says they do.
        paid = advanced_ftl and options.get("cd_advanced_ftl")
        rows.append(BreakdownRow("ftl", _("Advanced FTL drive") if advanced_ftl else _("FTL drive"),
                                 ftl_mass, (3 if paid else 2) * ftl_mass))
    if stream_mass:
        label = _("Full streamlining") if design.get("streamlining") == "full" else _("Partial streamlining")
        rows.append(BreakdownRow("streamlining", label, stream_mass, 2 * stream_mass))

    holds = []
    for s in _systems(design):
        rule = SYSTEM_RULES.get(s.get("type"))
        uid = s.get("uid") if isinstance(s.get("uid"), str) else None
        if rule is None:
            rows.append(BreakdownRow(str(s.get("type")), _("Unknown system"), 0, 0, uid))
            continue
        mass_fn, points_fn, label_fn = rule
        mass = mass_fn(s, tmf)
        rows.append(BreakdownRow(s["type"], label_fn(s), mass, points_fn(s, mass), uid))
        if s["type"] == "hold":
            kind = s.get("kind") if s.get("kind") in ("cargo", "passenger", "troop", "lab") else "cargo"
            holds.append({"uid": uid, "kind": kind, "spaces": split_rows(mass, hull_rows(design))})

    derived = {
        "tmf": tmf,
        "mass_limit": tmf,  # CD p.42: at most the total MASS
        "ship_class": ship_class(tmf),
        "ftl_mass": ftl_mass,
        "drive_mass": drive_mass,
        "turn_thrust": thrust if advanced_drive else fb_rules._turn_thrust(thrust),
        "hull_descriptor": _hull_descriptor(boxes, tmf),
        "damage_track": damage_track(design),
        "crew_factors": crew_factors(design),
        "cf_positions": cf_positions(design),
        "thresholds": threshold_numbers(design),
        "holds": holds,
        "core_systems": True,  # CD p.31: optional but drawn; the fleet option decides use
        "shell_layers": layers,
        "advanced_tech": True,  # the Design tab offers the advanced hull/drive/FTL choices
        # ...and the loadout editor a row per fighter group with its extras and swing roles,
        # light vessels per hangar and a stage count per magazine (CD pp.25, 30, 47).
        "rich_loadout": True,
        "advanced_drive": advanced_drive,
        "advanced_ftl": advanced_ftl,
        "transfer_mass": transfer_mass(design),
    }
    return Breakdown(tuple(rows), sum(r.mass for r in rows), sum(r.points for r in rows), derived)


def ship_class(tmf: int) -> str:
    """"escort", "cruiser" or "capital" (CD p.42)."""
    if tmf <= data.ESCORT_MAX:
        return "escort"
    return "cruiser" if tmf <= data.CRUISER_MAX else "capital"


def _hull_descriptor(boxes: int, tmf: int) -> str:
    percent = 100 * boxes / tmf if tmf else 0
    for low, label in data.HULL_DESCRIPTORS:
        if percent >= low:
            return fb_rules.data.translated_hull_descriptor(label)
    return fb_rules.data.translated_hull_descriptor("Fragile")


# ---- Damage track, crew, thresholds -------------------------------------------------------------


def damage_track(design: dict) -> list[int]:
    return split_rows(_int(design.get("hull_boxes")), hull_rows(design))


def crew_factors(design: dict) -> int:
    # CD p.32: warships 1 CF per 20 MASS or part, merchants per 50.
    per = 50 if design.get("hull_kind") == "merchant" else 20
    return math.ceil(max(0, _int(design.get("tmf"))) / per)


def cf_positions(design: dict) -> list[int]:
    return common.cf_positions(max(0, _int(design.get("hull_boxes"))), crew_factors(design))


def threshold_numbers(design: dict) -> list[int]:
    # CD p.17: 6, 5+, 4+ at the end of each row but the last; three rows stop at 5+.
    return [6, 5, 4][: hull_rows(design) - 1]


# ---- Loadout, options ---------------------------------------------------------------------------


def _entries(loadout: object, key: str) -> list[dict]:
    return fb_rules._loadout_entries(loadout, key)


def _magazine_stages(entry: dict) -> int:
    return max(1, _int(entry.get("stages"), 1))


def _group_types(entry: dict) -> list[str]:
    """The types a group may launch as: its own, then its swing roles (CD p.30), no repeats."""
    swing = entry.get("swing") if isinstance(entry.get("swing"), list) else []
    out: list[str] = []
    for t in [entry.get("type"), *swing]:
        if isinstance(t, str) and t not in out:
            out.append(t)
    return out


def _group_extras(entry: dict) -> list[str]:
    extras = entry.get("extras") if isinstance(entry.get("extras"), list) else []
    return list(dict.fromkeys(x for x in extras if isinstance(x, str)))


def fighter_group_points(entry: dict) -> int:
    """CD p.30: a swing-role group pays its dearest type in full and half of each other type;
    FTL and kinetic capability are +6 a group each (CD p.47)."""
    costs = sorted((data.FIGHTER_POINTS[t] for t in _group_types(entry) if t in data.FIGHTER_POINTS),
                   reverse=True)
    if not costs:
        return 0
    return (costs[0] + sum(c // 2 for c in costs[1:])
            + sum(data.FIGHTER_EXTRAS.get(x, 0) for x in _group_extras(entry)))


def salvo_space(entry: dict, salvo: str) -> int | None:
    """Magazine MASS one salvo of this load takes: an extra stage adds 2 (CD p.25)."""
    if salvo not in data.SALVO_SPACE:
        return None
    return data.SALVO_SPACE[salvo] + (2 * (_magazine_stages(entry) - 1) if salvo == "std" else 0)


def _salvo_surcharge(entry: dict) -> int:
    """Points a multi-stage load costs beyond the magazine space it fills. Each stage doubles
    the points of a standard load (2 MASS at 3 = 6, CD pp.25, 47) while the space it takes is
    already priced at 3 a MASS in the magazine, so two stages cost nothing more and three 6."""
    stages = _magazine_stages(entry)
    if stages == 1:
        return 0
    salvos = entry.get("salvos") if isinstance(entry.get("salvos"), list) else []
    per_load = 6 * 2 ** (stages - 1) - 3 * salvo_space(entry, "std")
    return per_load * sum(1 for x in salvos if x == "std")


def loadout_points(design: dict, loadout: dict | None, options: dict) -> int:
    if loadout is None:
        loadout = design.get("default_loadout")
    craft_mass = sum(max(0, _int(c.get("mass"))) for c in _entries(loadout, "craft"))
    return (sum(fighter_group_points(f) for f in _entries(loadout, "fighters"))
            + data.CRAFT_POINTS_PER_MASS * craft_mass
            + sum(_salvo_surcharge(m) for m in _entries(loadout, "magazines")))


def _option_for(system: dict) -> str | None:
    stype = system.get("type")
    if stype in data.OPTIONAL_SYSTEMS:
        return "cd_optional_systems"
    if stype in data.SUPER_WEAPONS:
        return "cd_super_weapons"
    if stype in ("sm_rack", "heavy_missile") and _stages(system) > 1:
        return "cd_multistage"
    return None


def required_options(design: dict, loadout: dict | None) -> set[str]:
    keys = {key for key in (_option_for(s) for s in _systems(design)) if key}
    if loadout is None:
        loadout = design.get("default_loadout")
    if any(_magazine_stages(m) > 1 for m in _entries(loadout, "magazines")):
        keys.add("cd_multistage")
    return keys


# The same wording as fleet_rules.option_label(), which this layer may not import.
OPTION_NAMES = {
    "cd_optional_systems": lambda: _("Sensors, ECM, mines and ortillery"),
    "cd_super_weapons": lambda: _("Nova cannon, wave gun, reflex field, cloak"),
    "cd_multistage": lambda: _("Multi-stage missiles"),
}


# ---- Type suggestion ----------------------------------------------------------------------------


def suggest_type(design: dict) -> tuple[str, str]:
    tmf = max(0, _int(design.get("tmf")))
    if design.get("hull_kind") == "merchant":
        return fb_rules.data.translated_class_label("Merchant"), "M"
    # CD prints no codes for these; the letters only have to be short and distinct.
    if any(s.get("type") == "portal" for s in _systems(design)):
        return _("Portal"), "PT"
    if transfer_mass(design):
        return _("Jump gate"), "JG"
    if design.get("hull_kind") == "starbase":
        return _("Starbase section"), "SB"
    bays = sum(max(1, _int(s.get("bays"), 1)) for s in _systems(design) if s.get("type") == "hangar")
    if bays >= data.CARRIER_MIN_BAYS and tmf >= data.CARRIER_CLASSES[0][2]:
        return _pick(tmf, data.CARRIER_CLASSES)
    return _pick(tmf, data.SHIP_CLASSES)


def _pick(tmf: int, classes: tuple) -> tuple[str, str]:
    """The band containing tmf whose centre is nearest, ties to the smaller (as FB)."""
    best = None
    for label, code, low, high in classes:
        if low <= tmf <= high:
            dist = abs(tmf - (low + high) / 2)
            if best is None or dist < best[0]:
                best = (dist, label, code)
    if best is None:
        label, code = (classes[0] if tmf < classes[0][2] else classes[-1])[:2]
        return fb_rules.data.translated_class_label(label), code
    return fb_rules.data.translated_class_label(best[1]), best[2]


# ---- Validation ---------------------------------------------------------------------------------


def validate_design(design: dict, options: dict) -> list[Issue]:
    """Violations and infos. `options` are the fleet's: a system behind a fleet option is a
    violation only where the fleet has that option off; with no fleet (the Design tab passes
    no options) it is a note, so a design can be built before it joins a fleet."""
    issues: list[Issue] = []

    def violation(code: str, message: str, uid: str | None = None) -> None:
        issues.append(Issue(code, "violation", message, uid))

    def info(code: str, message: str, uid: str | None = None) -> None:
        issues.append(Issue(code, "info", message, uid))

    tmf = _int(design.get("tmf"))
    boxes = _int(design.get("hull_boxes"))
    if tmf <= 0:
        violation("bad_tmf", _("Total MASS must be at least 1."))
    if tmf > data.MAX_MASS:
        violation("mass_over_300", _("A ship's MASS is at most {n}.", n=data.MAX_MASS))
    if tmf > 10 and tmf % 2:
        violation("odd_mass", _("A ship over MASS 10 must have an even MASS."))
    b = design_breakdown(design, options)
    if b.mass_used > tmf:
        violation("mass_over", _("MASS used ({used}) exceeds the total MASS ({tmf}).",
                                 used=b.mass_used, tmf=tmf))
    elif b.mass_used < tmf:
        info("mass_under", _("{n} MASS unused.", n=tmf - b.mass_used))
    if tmf > 0 and boxes < pct(tmf, 100):
        violation("hull_below_minimum",
                  _("Hull integrity needs at least {n} boxes (10% of MASS).", n=pct(tmf, 100)))
    if design.get("hull_advanced") is True and boxes < 4:
        info("advanced_hull_too_small", _("Fewer than four hull boxes is always a standard hull."))
    if _int(design.get("thrust")) < 0 or _int(design.get("armour")) < 0:
        violation("negative_value", _("Thrust and armour cannot be negative."))
    raw_layers = design.get("armour_layers")
    if isinstance(raw_layers, list) and raw_layers:
        total = sum(max(0, _int(n)) for n in raw_layers)
        if total != max(0, _int(design.get("armour"))):
            violation("shell_layers_total", _("Shell layers total {n} boxes but the armour is {m}.",
                                              n=total, m=max(0, _int(design.get("armour")))))

    systems = _systems(design)
    by_uid = {s["uid"]: s for s in systems if isinstance(s.get("uid"), str)}
    capital = ship_class(tmf) == "capital"
    for s in systems:
        uid = s.get("uid") if isinstance(s.get("uid"), str) else None
        stype = s.get("type")
        if stype not in SYSTEM_RULES:
            violation("unknown_system", _("Unknown system type: {t}.", t=str(stype)), uid)
            continue
        _validate_arcs(s, uid, violation)
        key = _option_for(s)
        if key:
            _option_issue(key, options, uid, violation, info)
        if stype == "nova_cannon" and not capital:
            violation("capital_only", _("Only capital ships may mount this system."), uid)
        if stype in ("sm_rack", "heavy_missile") and _stages(s) > 1 and s.get("load") == "er":
            violation("multistage_er", _("Only standard missiles may have extra stages."), uid)

    types = {s.get("type") for s in systems}
    if {"screen", "advanced_screen"} <= types:
        violation("mixed_screens", _("A ship cannot have both advanced and standard screens."))
    if {"pds", "scattergun"} <= types:
        violation("mixed_point_defence", _("A ship cannot have both PDS and scatterguns."))

    fb_rules._validate_missiles(design, systems, by_uid, violation, salvo_space)
    _validate_magazine_loads(design, by_uid, options, violation, info)
    _validate_hangars(design, by_uid, violation, info)

    _validate_stationary(design, systems, violation)

    if not any(s.get("type") == "fire_control" for s in systems):
        info("no_fire_control", _("No fire control: weapons that need one cannot fire."))
    if design.get("ftl") is not True and not stationary(design):
        # CD pp.34-35: a battle rider (MASS 60 at most, carried by a mothership) or a system
        # defence ship; the fleet decides which (rulesets/ftcd/fleet.py).
        info("no_ftl", _("No FTL drive: a battle rider (MASS {n} at most) needs a mothership; "
                         "a system defence ship needs the fleet's agreement.", n=data.RIDER_MAX_MASS))
    for s in systems:
        if s.get("type") in ("screen", "advanced_screen") and _int(s.get("level"), 1) > 2:
            info("screen_backups", _("Screen generators beyond level 2 are backups only."), s.get("uid"))
    return issues


def _validate_stationary(design: dict, systems: list[dict], violation) -> None:
    """Gates and starbases (CD pp.35, 51): stationary, so thrust 0; a gate needs hull boxes of
    at least 10% of its transfer MASS and is either a jump gate or a portal."""
    gates = [s for s in systems if s.get("type") in data.GATE_TYPES]
    if not stationary(design):
        return
    if _int(design.get("thrust")) > 0:
        violation("stationary_thrust",
                  _("A starbase section or gate is stationary: its thrust is always 0."))
    if not gates:
        return
    if len({s.get("type") for s in gates}) > 1:
        violation("gate_and_portal", _("A gate is either a jump gate or a portal, not both."))
    need = pct(transfer_mass(design), 100)
    if _int(design.get("hull_boxes")) < need:
        violation("gate_hull", _("A gate needs at least {n} hull boxes (10% of its transfer MASS).",
                                 n=need))


ARCED_TYPES = {
    "beam", "graser", "pulse_torpedo", "needle_beam", "sm_launcher", "sm_rack", "heavy_missile",
    "nova_cannon", "wave_gun",
}


def _validate_arcs(s: dict, uid: str | None, violation) -> None:
    stype = s["type"]
    arcs = s.get("arcs")
    if stype == "submunition" and arcs is None:
        return
    if stype not in ARCED_TYPES and stype != "submunition":
        return
    if not arcs_valid(arcs):
        violation("bad_arcs",
                  _("Choose at least one fire arc ({arcs}), each once.", arcs=", ".join(ARCS)), uid)
        return
    broadside = _is_broadside(s)
    adjacent = arcs_contiguous(arcs)
    cls = _int(s.get("class"), 1)
    if stype == "beam":
        if cls < 1:
            violation("beam_arcs", _("Beam class must be at least 1."), uid)
        elif cls == 1 and not (len(arcs) == 6 or broadside):
            violation("beam_arcs", _("A class-1 battery always fires through all six arcs."), uid)
        elif cls == 2 and not (len(arcs) == 6 or broadside or (len(arcs) == 3 and adjacent)):
            violation("beam_arcs",
                      _("A class-2 battery fires through 3 adjacent arcs, all six or a broadside."), uid)
        elif cls >= 3 and not (adjacent or broadside):
            violation("beam_arcs", _("Arcs must be adjacent, or a broadside."), uid)
    elif stype == "graser" and not (adjacent or broadside):
        violation("graser_arcs", _("Arcs must be adjacent, or a broadside."), uid)
    elif stype == "pulse_torpedo" and not (broadside or (len(arcs) <= 3 and adjacent)):
        violation("torpedo_arcs", _("A torpedo covers at most 3 adjacent arcs, or a broadside."), uid)
    elif stype in ("sm_launcher", "sm_rack", "heavy_missile") and not (
            broadside or (len(arcs) == 3 and adjacent)):
        # CD p.45: launchers and racks fire through 3 consecutive arcs or broadside arcs.
        violation("missile_arcs", _("Missiles fire through 3 adjacent arcs or a broadside."), uid)
    elif stype == "needle_beam" and len(arcs) != 1:
        violation("needle_arcs", _("This weapon fires through one arc only."), uid)
    elif stype in ("nova_cannon", "wave_gun") and arcs != ["F"]:
        # CD p.55: along the centreline only, whichever way the bow points.
        violation("single_arc", _("This weapon fires straight ahead only."), uid)


def _option_issue(key: str, options: dict, uid: str | None, violation, info) -> None:
    if options.get(key) is False:
        violation("option_off", _("This system needs the fleet option: {name}.",
                                  name=OPTION_NAMES[key]()), uid)
    elif key not in options:
        info("option_needed", _("A fleet must switch on: {name}.", name=OPTION_NAMES[key]()), uid)


def _validate_magazine_loads(design: dict, by_uid: dict, options: dict, violation, info) -> None:
    """CD p.25: a magazine carries regular or multi-stage loads, never a mix, and only standard
    missiles take extra stages. The stage count is the magazine's, so the only possible mix is an
    ER salvo in a multi-stage magazine."""
    for entry in _entries(design.get("default_loadout"), "magazines"):
        mag = by_uid.get(entry.get("magazine"))
        if _magazine_stages(entry) == 1 or not mag or mag.get("type") != "sm_magazine":
            continue
        _option_issue("cd_multistage", options, mag["uid"], violation, info)
        salvos = entry.get("salvos") if isinstance(entry.get("salvos"), list) else []
        if "er" in salvos:
            violation("multistage_er", _("Only standard missiles may have extra stages."), mag["uid"])


def _validate_hangars(design: dict, by_uid: dict, violation, info) -> None:
    """Fighter groups and light vessels share the hangar: 6 craft MASS a bay (CD p.47)."""
    loadout = design.get("default_loadout")
    used: dict[str, int] = {}
    for entry in _entries(loadout, "fighters"):
        hangar = by_uid.get(entry.get("hangar"))
        if not hangar or hangar.get("type") != "hangar":
            violation("fighters_without_hangar",
                      _("Fighter group assigned to a hangar this design does not have."))
            continue
        types = _group_types(entry)
        if (any(t not in data.FIGHTER_POINTS for t in types)
                or any(x not in data.FIGHTER_EXTRAS for x in _group_extras(entry))):
            violation("unknown_fighter_type", _("Unknown fighter type."), hangar["uid"])
        if "kinetic" in _group_extras(entry) and set(types) <= data.NO_KINETIC_BENEFIT:
            info("kinetic_no_benefit",
                 _("Kinetic weapons are of no benefit to interceptors or torpedo fighters."),
                 hangar["uid"])
        used[hangar["uid"]] = used.get(hangar["uid"], 0) + data.BAY_CRAFT_MASS
    for entry in _entries(loadout, "craft"):
        hangar = by_uid.get(entry.get("hangar"))
        if not hangar or hangar.get("type") != "hangar":
            violation("craft_without_hangar",
                      _("Light vessels assigned to a hangar this design does not have."))
            continue
        used[hangar["uid"]] = used.get(hangar["uid"], 0) + max(0, _int(entry.get("mass")))
    for uid, craft_mass in used.items():
        bays = max(1, _int(by_uid[uid].get("bays"), 1))
        if craft_mass > bays * data.BAY_CRAFT_MASS:
            violation("hangar_overfull",
                      _("The hangar holds {cap} MASS of fighters and light vessels; {n} are loaded.",
                        cap=bays * data.BAY_CRAFT_MASS, n=craft_mass), uid)
