"""FTPC costing, derived values and validation (Project Continuum section 13, human tech).

Project Continuum gathers the Fleet Book and Cross Dimensions design systems with many more
systems, so the shapes match rulesets/ftcd/rules.py and the shared helpers come from
rulesets/common.py. What PC changes on the way: hulls of four, five or six rows (x2, x1.5, x1,
p.108), advanced FTL always paid at x3 once chosen, hangar bays (6 MASS) with launch tubes
(3 MASS) beside the old combined bay (9), screens with no minimum MASS, shell armour at
2 x the layer number, arcs that need not be adjacent (p.45), stealth hulls, regenerative armour,
and the many systems of sections 5-7.

Page numbers are printed pages of Full Thrust Project Continuum (PDF page = printed).
"""

from __future__ import annotations

import math
from collections.abc import Callable

from i18n import _
from rulesets import Breakdown, BreakdownRow, Issue, common
from rulesets.common import ARCS, arcs_valid, round_half_up, split_rows
from rulesets.ftpc import data

_int = common.as_int
_systems = common.systems_of
_arcs = common.arcs_of

STREAMLINING_PERCENT = {"none": 0, "partial": 5, "full": 10}  # PC p.109
SIDES = (frozenset({"FP", "AP"}), frozenset({"FS", "AS"}))  # a broadside mount: one side's arcs


def pct(tmf: int, tenths_percent: int) -> int:
    """tenths_percent/10 % of tmf, .5 up, never 0 (PC p.107). Tenths, for 7.5% screens."""
    return max(1, round_half_up(tmf * tenths_percent, 1000))


def _class(system: dict, top: int = 99) -> int:
    return min(top, max(1, _int(system.get("class"), 1)))


def _n(system: dict) -> int:
    return max(1, len(_arcs(system)))


def _one_side(system: dict) -> bool:
    """Exactly the two arcs of one side: PC's broadside mounts (pp.36, 40)."""
    return frozenset(_arcs(system)) in SIDES and len(_arcs(system)) == 2


def _tmf(design: dict) -> int:
    return max(0, _int(design.get("tmf")))


def _transfer(system: dict) -> int:
    return max(1, _int(system.get("transfer_mass"), 1))


def transfer_mass(design: dict) -> int:
    """What the design's gate or portal drives move in one turn (PC p.91); 0 for a ship."""
    return sum(_transfer(s) for s in _systems(design) if s.get("type") in data.GATE_TYPES)


def stationary(design: dict) -> bool:
    """A starbase section or an artificial gate: terrain that never moves (PC pp.91, 115)."""
    return design.get("hull_kind") == "starbase" or transfer_mass(design) > 0


def has_afc(design: dict) -> bool:
    return any(s.get("type") == "advanced_fire_control" for s in _systems(design))


# ---- Per-system MASS ------------------------------------------------------------------------
# Each takes the system and the design: some prices depend on the ship's MASS, and the paired
# broadside mounts on how many of the same kind the ship carries.


def _beam_mass(s: dict, d: dict) -> int:
    """Beams, EMP projectors, transporters, gravitic guns (PC pp.36-39, 45): class 1 1 MASS
    (all six arcs), class 2 2 for three arcs and 3 for more, or 1 as a two-arc broadside;
    class 3 4 MASS and each class above doubles it, +1/4 of that per extra arc."""
    cls, n = _class(s), _n(s)
    if cls == 1:
        return 1
    if cls == 2:
        if _one_side(s):
            return 1
        return 2 if n <= 3 else 3
    base = 2 ** (cls - 1)
    return base + (base // 4) * (n - 1)


def _plasma_mass(s: dict, d: dict) -> int:
    """Plasma cannon, grasers and phasers (PC pp.37-38): double a beam. Class 1 1 for three arcs
    and 2 for six, class 2 4 and 6, class 3 8 +2 an extra arc, class 4 16 +4."""
    cls, n = _class(s), _n(s)
    if cls == 1:
        return 1 if n <= 3 else 2
    if cls == 2:
        return 4 if n <= 3 else 6
    base = 2 ** cls
    return base + (base // 4) * (n - 1)


def _heavy_graser_mass(s: dict, d: dict) -> int:
    """PC p.38: class 1 2/3/4 for one, three or six arcs; class 2 9 +3, class 3 24 +6."""
    cls, n = _class(s, 3), _n(s)
    if cls == 1:
        return 2 if n == 1 else 3 if n <= 3 else 4
    base, per = (9, 3) if cls == 2 else (24, 6)
    return base + per * (n - 1)


def _paired(s: dict, d: dict, pred: Callable[[dict], bool]) -> int:
    """0-based position of s among the design's systems that pred picks."""
    same = [x for x in _systems(d) if pred(x)]
    return next((i for i, x in enumerate(same) if x is s), 0)


def _battery_mass(s: dict, d: dict) -> int:
    """Gatling batteries, twin particle arrays, meson projectors and pulsers (PC pp.40, 45):
    2 for one arc, 3 for three, 4 for six. A broadside pair of gatlings or TPAs is 5 MASS for
    two batteries (p.40), drawn here as 3 for the first of each pair and 2 for the second."""
    if s.get("type") in ("gatling", "twin_particle_array") and _one_side(s):
        index = _paired(s, d, lambda x: x.get("type") == s.get("type") and _one_side(x))
        return 3 if index % 2 == 0 else 2
    n = _n(s)
    return 2 if n == 1 else 3 if n <= 3 else 4


def _needle_mass(s: dict, d: dict) -> int:
    """PC p.41: NB-1 2 MASS for two arcs +1 for a third; NB-2 4 +2 an arc, NB-3 8 +4, NB-4 16 +8."""
    cls, n = _class(s, 4), min(3, _n(s))
    if cls == 1:
        return 2 + max(0, n - 2)
    base = 2 ** cls
    return base + (base // 2) * (n - 1)


def _torpedo_mass(s: dict, d: dict) -> int:
    """PC pp.41-42: standard 4 +1 an extra arc, short range 2 +1 for both extra arcs, long range
    and variable strength 8 +2 an arc; three arcs at most."""
    n = min(3, _n(s))
    kind = s.get("range")
    if kind == "short":
        return 2 if n == 1 else 3
    if kind in ("long", "variable"):
        return 8 + 2 * (n - 1)
    return 4 + (n - 1)


# PC p.43: K-gun MASS by class, one arc (K-1 all six; K-2 +1 for a second arc).
KGUN_MASS = {1: 2, 2: 3, 3: 5, 4: 8, 5: 11, 6: 14}
SR_KGUN_MASS = {2: 2, 3: 3, 4: 4, 5: 6, 6: 7}  # "half the mass, rounded up"; SRK-1 is 1.5


def _kgun_mass(s: dict, d: dict) -> int:
    cls = _class(s, 6)
    kind = s.get("range")
    extra = 1 if cls == 2 and _n(s) >= 2 else 0
    if kind == "short":
        if cls == 1:
            # "Short range K-1's can be bought in pairs for 3 mass": 2 for the first of each pair.
            index = _paired(s, d, lambda x: x.get("type") == "kgun" and x.get("range") == "short"
                            and _class(x, 6) == 1)
            return 2 if index % 2 == 0 else 1
        return SR_KGUN_MASS[cls]  # SRK-2 is 2 MASS for its two arcs
    base = KGUN_MASS[cls] + extra
    return 2 * base if kind == "long" else base


def _plasma_bolt_mass(s: dict, d: dict) -> int:
    """PC p.55: 3 MASS a class, + the class per extra arc, three arcs at most."""
    cls = _class(s, 6)
    return 3 * cls + cls * (min(3, _n(s)) - 1)


def _level(s: dict, top: int = 99) -> int:
    return min(top, max(1, _int(s.get("level"), 1)))


def _screen_mass(s: dict, d: dict) -> int:
    # PC p.56: 5% of MASS per level, no minimum; generators beyond 2 are backups.
    return pct(_tmf(d), 50 * _level(s))


def _advanced_screen_mass(s: dict, d: dict) -> int:
    return pct(_tmf(d), 75 * _level(s))  # PC p.56: 7.5% per level


def _area_screen_mass(tenths: int, minimum: int) -> Callable[[dict, dict], int]:
    # PC p.60 and the errata: 20% (15 at least) or 30% advanced (20 at least) per level, 2 at most.
    def mass(s: dict, d: dict) -> int:
        return _level(s, 2) * max(minimum, pct(_tmf(d), tenths))
    return mass


def _stages(system: dict) -> int:
    return max(1, _int(system.get("stages"), 1))


def _missile_mass(base_std: int, base_er: int) -> Callable[[dict, dict], int]:
    # PC p.52: each extra stage adds 2 MASS (standard missiles only).
    def mass(s: dict, d: dict) -> int:
        base = base_er if s.get("load") == "er" else base_std
        return base + 2 * (_stages(s) - 1)
    return mass


def _missile_points(base_std: int, base_er: int) -> Callable[[dict, int, dict], int]:
    # ... and doubles the points cost of the missile it is added to.
    def points(s: dict, m: int, d: dict) -> int:
        base = base_er if s.get("load") == "er" else base_std
        return 3 * base * 2 ** (_stages(s) - 1)
    return points


def _missile_label(plain: str, er: str) -> Callable[[dict], str]:
    def label(s: dict) -> str:
        text = er if s.get("load") == "er" else plain
        stages = _stages(s)
        return _("{name}, {n} stages", name=text, n=stages) if stages > 1 else text
    return label


def _count(s: dict) -> int:
    return max(1, _int(s.get("count"), 1))


def _mass_param(s: dict) -> int:
    return max(1, _int(s.get("mass"), 1))


def _spinal_size(s: dict) -> str:
    return s.get("size") if s.get("size") in data.SPINAL_MASS else "small"


def _spinal_kind(s: dict) -> str:
    return s.get("kind") if s.get("kind") in data.SPINAL_POINTS else "beam"


def _yes(s: dict, key: str) -> bool:
    return s.get(key) == "yes"


def _times(k: int) -> Callable[[dict, int, dict], int]:
    return lambda s, m, d: k * m


def _flat(mass: int, points: int, label: Callable[[], str]):
    return (lambda s, d: mass, lambda s, m, d: points, lambda s: label())


def _torpedo_points(s: dict, m: int, d: dict) -> int:
    return (5 if s.get("range") == "variable" else 3) * m  # PC p.42: VPTs 5 a MASS


def _kgun_points(s: dict, m: int, d: dict) -> int:
    # PC p.44: flak ammunition +2 a gun, all of a ship's K-guns but its K-1s.
    return 4 * m + (2 if _yes(s, "flak") and _class(s, 6) > 1 else 0)


def _phaser_points(s: dict, m: int, d: dict) -> int:
    # PC p.38: 3 a MASS +2 a weapon, or 6 a MASS on a ship that also mounts an advanced FireCon.
    return 6 * m if has_afc(d) else 3 * m + 2


TORPEDO_LABELS = {
    "short": lambda: _("Short-range pulse torpedo"),
    "long": lambda: _("Long-range pulse torpedo"),
    "variable": lambda: _("Variable strength pulse torpedo"),
}
KGUN_PREFIX = {"short": "SRK", "long": "LRK"}
SPINAL_LABELS = {
    "beam": lambda: _("beam"), "plasma": lambda: _("plasma"),
    "psp": lambda: _("point singularity projector"),
}
SPINAL_SIZE_LABELS = {"small": lambda: _("Small"), "medium": lambda: _("Medium"),
                      "large": lambda: _("Large")}


SystemRule = tuple[Callable[[dict, dict], int], Callable[[dict, int, dict], int], Callable[[dict], str]]

SYSTEM_RULES: dict[str, SystemRule] = {
    "fire_control": _flat(1, 4, lambda: _("Fire control")),
    "advanced_fire_control": _flat(1, 5, lambda: _("Advanced fire control")),
    # ---- Beam weapons (PC pp.36-45) ----
    "beam": (_beam_mass, _times(3), lambda s: _("Beam-{n}", n=_class(s))),
    "emp": (_beam_mass, _times(3), lambda s: _("EMP-{n}", n=_class(s))),
    "transporter": (_beam_mass, _times(3), lambda s: _("TB-{n}", n=_class(s))),
    "grav_gun": (_beam_mass, _times(3), lambda s: _("Grav-{n}", n=_class(s))),
    "plasma_cannon": (_plasma_mass, _times(3), lambda s: _("Plasma-{n}", n=_class(s))),
    "graser": (_plasma_mass, _times(3), lambda s: _("Graser-{n}", n=_class(s))),
    "phaser": (_plasma_mass, _phaser_points, lambda s: _("Phaser-{n}", n=_class(s))),
    "heavy_graser": (
        _heavy_graser_mass,
        lambda s, m, d: (4 if s.get("intensity") == "high" else 3) * m,
        lambda s: (_("HiG-{n}", n=_class(s, 3)) if s.get("intensity") == "high"
                   else _("Heavy graser-{n}", n=_class(s, 3))),
    ),
    "gatling": (_battery_mass, _times(4), lambda s: _("Gatling battery")),
    "twin_particle_array": (_battery_mass, _times(4), lambda s: _("Twin particle array")),
    "meson": (_battery_mass, _times(4), lambda s: _("Meson projector")),
    "pulser": (_battery_mass, _times(5), lambda s: _("Pulser")),
    "needle_beam": (_needle_mass, _times(3), lambda s: _("NB-{n}", n=_class(s, 4))),
    # ---- Projectile weapons (PC pp.41-45, 54) ----
    "pulse_torpedo": (
        _torpedo_mass, _torpedo_points,
        lambda s: TORPEDO_LABELS.get(s.get("range"), lambda: _("Pulse torpedo"))(),
    ),
    "submunition": _flat(1, 3, lambda: _("Submunition pack")),
    "kgun": (
        _kgun_mass, _kgun_points,
        lambda s: f"{KGUN_PREFIX.get(s.get('range'), 'K')}-{_class(s, 6)}"
                  + (" " + _("(flak)") if _yes(s, "flak") and _class(s, 6) > 1 else ""),
    ),
    "mkp": _flat(1, 4, lambda: _("Multiple kinetic penetrator")),
    "boarding_torpedo_launcher": _flat(2, 6, lambda: _("Boarding torpedo launcher")),
    "boarding_torpedoes": (
        lambda s, d: _count(s), _times(3),
        lambda s: _("Boarding torpedoes ({n})", n=_count(s)),
    ),
    "fusion_array": (lambda s, d: 3 + min(3, _n(s)) - 1, _times(3), lambda s: _("Fusion array")),
    "plasma_bolt": (_plasma_bolt_mass, _times(3), lambda s: _("Class-{n} PBL", n=_class(s, 6))),
    # ---- Ordnance (PC pp.49-55) ----
    "sm_launcher": _flat(3, 9, lambda: _("Salvo missile launcher")),
    "sm_magazine": (
        lambda s, d: max(1, _int(s.get("capacity"), 0)), _times(3),
        lambda s: _("SM magazine (capacity {n})", n=_int(s.get("capacity"), 0)),
    ),
    "sm_rack": (
        _missile_mass(4, 5), _missile_points(4, 5),
        _missile_label(_("One-shot salvo missile launcher"), _("One-shot salvo missile launcher (ER)")),
    ),
    "heavy_missile": (
        _missile_mass(2, 3), _missile_points(2, 3),
        _missile_label(_("Heavy missile"), _("Heavy missile (ER)")),
    ),
    "am_missile": _flat(2, 10, lambda: _("Antimatter missile")),
    "rocket_pod": _flat(1, 3, lambda: _("Rocket pod")),
    "minelayer": (
        # PC p.55: the rack is 2 MASS at 3 a MASS, each mine 1 MASS and 2 points.
        lambda s, d: 2 + max(2, _int(s.get("mines"), 2)),
        lambda s, m, d: 6 + 2 * (m - 2),
        lambda s: _("Mine rack ({n} mines)", n=max(2, _int(s.get("mines"), 2))),
    ),
    # ---- Spinal mounts and super weapons (PC pp.46-48, 63-64) ----
    "spinal_mount": (
        lambda s, d: data.SPINAL_MASS[_spinal_size(s)],
        lambda s, m, d: data.SPINAL_POINTS[_spinal_kind(s)] * m,
        lambda s: _("{size} spinal {kind}", size=SPINAL_SIZE_LABELS[_spinal_size(s)](),
                    kind=SPINAL_LABELS[_spinal_kind(s)]()),
    ),
    "nova_cannon": _flat(20, 60, lambda: _("Nova cannon")),
    "wave_gun": _flat(12, 36, lambda: _("Wave gun")),
    # ---- Defences (PC pp.56-64) ----
    "screen": (_screen_mass, _times(3), lambda s: _("Screen level-{n}", n=_level(s))),
    "advanced_screen": (
        _advanced_screen_mass, _times(4), lambda s: _("Advanced screen level-{n}", n=_level(s)),
    ),
    "area_screen": (
        _area_screen_mass(200, 15), lambda s, m, d: round_half_up(7 * m, 2),
        lambda s: _("Area screen level-{n}", n=_level(s, 2)),
    ),
    "advanced_area_screen": (
        _area_screen_mass(300, 20), lambda s, m, d: round_half_up(7 * m, 2),
        lambda s: _("Advanced area screen level-{n}", n=_level(s, 2)),
    ),
    "pds": _flat(1, 3, lambda: _("Point defence system")),
    "ads": (lambda s, d: 2 if _n(s) <= 3 else 3, _times(3), lambda s: _("Area defence system")),
    "adfc": (lambda s, d: 2, lambda s, m, d: 8, lambda s: _("Area-defence fire control")),
    "aadfc": _flat(2, 10, lambda: _("Advanced area-defence fire control")),
    "scattergun": _flat(1, 5, lambda: _("Scattergun")),
    "grapeshot": _flat(1, 4, lambda: _("Grapeshot launcher")),
    "amsc": _flat(1, 5, lambda: _("Antimatter suicide charge")),
    "reflex_field": (
        lambda s, d: pct(_tmf(d), 100), _times(6), lambda s: _("Reflex field"),
    ),
    "stealth_field": (
        lambda s, d: pct(_tmf(d), 50 * _level(s, 2)), _times(6),
        lambda s: _("Stealth field level-{n}", n=_level(s, 2)),
    ),
    "holofield": (lambda s, d: pct(_tmf(d), 100), _times(5), lambda s: _("Holofield")),
    "ecm": (lambda s, d: _level(s), _times(3), lambda s: _("ECM level-{n}", n=_level(s))),
    "area_ecm": (lambda s, d: 2 * _level(s), _times(3), lambda s: _("Area ECM level-{n}", n=_level(s))),
    # PC p.61 and the errata: half the ship's MASS in points; a cloaking field the full MASS.
    "cloaking_device": (lambda s, d: 1, lambda s, m, d: max(1, round_half_up(_tmf(d), 2)),
                        lambda s: _("Cloaking device")),
    "cloaking_field": (lambda s, d: 1, lambda s, m, d: max(1, _tmf(d)), lambda s: _("Cloaking field")),
    "cloak": (lambda s, d: pct(_tmf(d), 100), _times(10), lambda s: _("Tuffley cloak")),
    # ---- Hangars, bays, tugs and gates (PC pp.89-91, 109-110) ----
    "hangar_bay": (lambda s, d: 6, _times(3), lambda s: _("Hangar bay")),
    "launch_tube": (
        lambda s, d: 3, lambda s, m, d: 3 * m + (1 if _yes(s, "catapult") else 0),
        lambda s: _("Launch tube with catapult") if _yes(s, "catapult") else _("Launch tube"),
    ),
    "hangar": (lambda s, d: 9, _times(3), lambda s: _("Combined hangar bay")),
    "boat_bay": (
        lambda s, d: max(1, round_half_up(3 * _mass_param(s), 2)), lambda s, m, d: 0,
        lambda s: _("Boat bay (craft MASS {n})", n=_mass_param(s)),
    ),
    "tender_bay": (
        lambda s, d: max(1, round_half_up(3 * max(1, _int(s.get("capacity"), 1)), 2)), _times(3),
        lambda s: _("Tender bay (carries MASS {n})", n=max(1, _int(s.get("capacity"), 1))),
    ),
    "tug_drive": (
        # PC p.89: 1 extra FTL MASS per 5 transfer MASS, rounded up to cover the whole ship.
        lambda s, d: max(1, math.ceil(max(1, _int(s.get("tow_mass"), 1)) / 5)), _times(2),
        lambda s: _("Tug jump drive (tows MASS {n})", n=max(1, _int(s.get("tow_mass"), 1))),
    ),
    "jump_gate": (
        lambda s, d: max(1, round_half_up(_transfer(s), data.GATE_TRANSFER_PER_MASS)), _times(2),
        lambda s: _("Jump gate drive (transfer MASS {n})", n=_transfer(s)),
    ),
    "portal": (
        lambda s, d: _transfer(s), _times(2),
        lambda s: _("Portal drive (transfer MASS {n})", n=_transfer(s)),
    ),
    # ---- Sensors (PC pp.95, 111-112) ----
    "enhanced_sensors": _flat(2, 8, lambda: _("Enhanced sensors")),
    "superior_sensors": _flat(4, 16, lambda: _("Superior sensors")),
    "weasel_cruiser": _flat(2, 8, lambda: _("Weasel emitter (cruiser)")),
    "weasel_capital": _flat(4, 16, lambda: _("Weasel emitter (capital)")),
    # ---- Crew (PC pp.110-111) ----
    "marines": (lambda s, d: 0, lambda s, m, d: 5 * _count(s),
                lambda s: _("Marine boarding parties ({n})", n=_count(s))),
    "dcp": (lambda s, d: 0, lambda s, m, d: 5 * _count(s),
            lambda s: _("Additional damage control parties ({n})", n=_count(s))),
    "troop_berthing": (lambda s, d: _mass_param(s), lambda s, m, d: 0,
                       lambda s: _("Troop berthing ({n} marines)", n=3 * _mass_param(s))),
    "passenger_berthing": (lambda s, d: _mass_param(s), lambda s, m, d: 0,
                           lambda s: _("Passenger berthing ({n} parties)", n=4 * _mass_param(s))),
    # ---- Holds and the rest (PC pp.110-113) ----
    "hold": (lambda s, d: _mass_param(s), lambda s, m, d: 0, lambda s: common.hold_label(s.get("kind"))),
    "minesweeper": _flat(5, 15, lambda: _("Minesweeper")),
    "ortillery": _flat(3, 9, lambda: _("Ortillery system")),
    "shipyard": (lambda s, d: _mass_param(s), _times(2),
                 lambda s: _("Shipyard (MASS {n})", n=_mass_param(s))),
    "flawed_design": (lambda s, d: 0, lambda s, m, d: 0, lambda s: _("Flawed design")),
}

BAY_TYPES = ("hangar_bay", "hangar")


# ---- Hull and armour ----------------------------------------------------------------------------


def _advanced_hull(design: dict) -> bool:
    """PC p.108: fewer than four hull boxes is always a standard hull."""
    return design.get("hull_advanced") is True and _int(design.get("hull_boxes")) >= 4


def hull_rows(design: dict) -> int:
    if _advanced_hull(design):
        return 3
    rows = _int(design.get("hull_rows"), 4)
    return rows if rows in data.HULL_ROW_CHOICES else 4


def hull_integrity_points(design: dict) -> int:
    """PC p.108: per box x2 for four rows, x1.5 for five, x1 for six, x3 advanced (.5 up)."""
    boxes = max(0, _int(design.get("hull_boxes")))
    halves = {3: 6, 4: 4, 5: 3, 6: 2}[hull_rows(design)]
    return round_half_up(halves * boxes, 2)


def shell_layers(design: dict) -> list[int]:
    """Armour boxes per layer, inner first, the same shape as the Phalon and CD shells."""
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


def armour_points(design: dict) -> int:
    """PC pp.57-58: the inner layer 2 a box, each shell 2 more (4, 6, 8, 10); regenerative
    armour adds 2 a box to every layer."""
    regen = 2 if design.get("armour_regen") is True else 0
    return sum((2 * (i + 1) + regen) * boxes for i, boxes in enumerate(shell_layers(design)))


def stealth_hull(design: dict) -> int:
    level = _int(design.get("stealth_hull"), 0)
    return level if level in (1, 2) else 0


def hull_cost(tmf: int, options: dict) -> int:
    """Basic hull points: MASS, or with the CPV option MASS squared / 100, at least 1 (PC p.140)."""
    if options.get("cd_cpv"):
        return max(1, round_half_up(tmf * tmf, 100)) if tmf > 0 else 0
    return tmf


# ---- Breakdown ------------------------------------------------------------------------------


def system_row(s: dict, design: dict, options: dict) -> BreakdownRow:
    uid = s.get("uid") if isinstance(s.get("uid"), str) else None
    rule = SYSTEM_RULES.get(s.get("type"))
    if rule is None:
        return BreakdownRow(str(s.get("type")), _("Unknown system"), 0, 0, uid)
    mass_fn, points_fn, label_fn = rule
    mass = mass_fn(s, design)
    stype = s["type"]
    if stype == "adfc" and options.get("pc_adfc_no_mass") and _tmf(design) > 20:
        mass = 0  # PC p.58, optional: no MASS on a ship over 20, still 8 points
        return BreakdownRow(stype, label_fn(s), mass, 8, uid)
    points = points_fn(s, mass, design)
    if stype in BAY_TYPES and options.get("pc_hangar_criticals"):
        points = 2 * mass  # PC p.109: 2 a MASS with the optional critical hits to hangar bays
    if stype == "pulse_torpedo" and options.get("pc_overload_torpedoes") \
            and s.get("range") not in ("short", "variable"):
        points += mass  # PC p.42: +1 a MASS, every torpedo but the short-range ones
    return BreakdownRow(stype, label_fn(s), mass, points, uid)


def design_breakdown(design: dict, options: dict) -> Breakdown:
    tmf = _tmf(design)
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
    rows_n = hull_rows(design)

    if advanced_hull:
        hull_label = _("Advanced hull ({n} boxes)", n=boxes)
    elif rows_n == 4:
        hull_label = _("Hull integrity ({n} boxes)", n=boxes)
    else:
        hull_label = _("Hull integrity ({n} boxes, {rows} rows)", n=boxes, rows=rows_n)
    rows = [
        BreakdownRow("hull", _("Basic hull (MASS {n})", n=tmf), 0, hull_cost(tmf, options)),
        BreakdownRow("hull_integrity", hull_label, boxes, hull_integrity_points(design)),
    ]
    if armour:
        regen = design.get("armour_regen") is True
        if len(layers) > 1:
            label = (_("Regenerative shell armour ({n} boxes)", n=armour) if regen
                     else _("Shell armour ({n} boxes)", n=armour))
        else:
            label = (_("Regenerative armour ({n} boxes)", n=armour) if regen
                     else _("Armour ({n} boxes)", n=armour))
        rows.append(BreakdownRow("armour", label, armour, armour_points(design)))
    if stealth_hull(design):
        # PC p.57: +2 (level 1) or +4 (level 2) for every hull and armour box, no MASS.
        level = stealth_hull(design)
        rows.append(BreakdownRow("stealth_hull", _("Stealth hull level-{n}", n=level), 0,
                                 2 * level * (boxes + armour)))
    if drive_mass:
        rows.append(BreakdownRow(
            "main_drive",
            _("Advanced drive (thrust-{n})", n=thrust) if advanced_drive
            else _("Main drive (thrust-{n})", n=thrust),
            drive_mass, (3 if advanced_drive else 2) * drive_mass))
    if ftl_mass:
        # PC p.108: x2, or x3 for a ship that pays for advanced FTL.
        rows.append(BreakdownRow("ftl", _("Advanced FTL drive") if advanced_ftl else _("FTL drive"),
                                 ftl_mass, (3 if advanced_ftl else 2) * ftl_mass))
    if stream_mass:
        # PC p.109 prices streamlining at 2 a MASS; the summary table on p.118 says 0. The text
        # is followed: it gives a worked example and matches the Fleet Books and CD.
        label = _("Full streamlining") if design.get("streamlining") == "full" else _("Partial streamlining")
        rows.append(BreakdownRow("streamlining", label, stream_mass, 2 * stream_mass))

    holds = []
    for s in _systems(design):
        row = system_row(s, design, options)
        rows.append(row)
        if s.get("type") == "hold":
            kind = s.get("kind") if s.get("kind") in ("cargo", "passenger", "troop", "lab") else "cargo"
            holds.append({"uid": row.system_uid, "kind": kind, "spaces": split_rows(row.mass, rows_n)})

    points = sum(r.points for r in rows)
    if any(s.get("type") == "flawed_design" for s in _systems(design)):
        # PC p.113: "Any ship built as a flawed design is discounted by 20%".
        discount = round_half_up(points, 5)
        rows.append(BreakdownRow("flawed_discount", _("Flawed design discount (20%)"), 0, -discount))
        points -= discount

    derived = {
        "tmf": tmf,
        "mass_limit": tmf,  # PC p.106: at most the total MASS
        "ship_class": ship_class(tmf),
        "ftl_mass": ftl_mass,
        "drive_mass": drive_mass,
        "turn_thrust": thrust if advanced_drive else common.half_turn_thrust(thrust),
        "hull_descriptor": _hull_descriptor(boxes, tmf),
        "damage_track": damage_track(design),
        "crew_factors": crew_factors(design),
        "cf_positions": cf_positions(design),
        "thresholds": threshold_numbers(design),
        "holds": holds,
        "core_systems": True,
        "shell_layers": layers,
        "advanced_tech": True,
        "hull_row_choices": data.HULL_ROW_CHOICES,  # the Design tab's hull rows choice
        "pc_hull_options": True,  # ...and its stealth hull and regenerative armour
        "rich_loadout": True,
        "advanced_drive": advanced_drive,
        "advanced_ftl": advanced_ftl,
        "transfer_mass": transfer_mass(design),
    }
    return Breakdown(tuple(rows), sum(r.mass for r in rows), points, derived)


def ship_class(tmf: int) -> str:
    """"escort", "cruiser" or "capital" (PC p.106)."""
    if tmf <= data.ESCORT_MAX:
        return "escort"
    return "cruiser" if tmf <= data.CRUISER_MAX else "capital"


def _hull_descriptor(boxes: int, tmf: int) -> str:
    return common.hull_descriptor(boxes, tmf, data.HULL_DESCRIPTORS)


# ---- Damage track, crew, thresholds -------------------------------------------------------------


def damage_track(design: dict) -> list[int]:
    return split_rows(_int(design.get("hull_boxes")), hull_rows(design))


def crew_factors(design: dict) -> int:
    # PC p.85: warships 1 CF per 20 MASS or part, merchants per 50.
    per = 50 if design.get("hull_kind") == "merchant" else 20
    return math.ceil(_tmf(design) / per)


def cf_positions(design: dict) -> list[int]:
    return common.cf_positions(max(0, _int(design.get("hull_boxes"))), crew_factors(design))


def threshold_numbers(design: dict) -> list[int]:
    """PC p.32: 6, 5+, 4+ at the end of each row but the last. The book stops at the third row;
    a five- or six-row hull keeps checking on 4+ at the rows after it."""
    return [6, 5, 4, 4, 4][: hull_rows(design) - 1]


# ---- Loadout, options ---------------------------------------------------------------------------


def _entries(loadout: object, key: str) -> list[dict]:
    return common.loadout_entries(loadout, key)


def _magazine_stages(entry: dict) -> int:
    return max(1, _int(entry.get("stages"), 1))


def _group_types(entry: dict) -> list[str]:
    swing = entry.get("swing") if isinstance(entry.get("swing"), list) else []
    out: list[str] = []
    for t in [entry.get("type"), *swing]:
        if isinstance(t, str) and t not in out:
            out.append(t)
    return out


def _group_extras(entry: dict) -> list[str]:
    extras = entry.get("extras") if isinstance(entry.get("extras"), list) else []
    # A modification the group's own type already is costs nothing more ("Fast" is a fast wing).
    return [x for x in dict.fromkeys(e for e in extras if isinstance(e, str)) if x != entry.get("type")]


def fighter_group_points(entry: dict) -> int:
    """PC p.123, per wing: the type, then its modifications. Swing roles are the CD rule (CD
    p.30): the dearest type in full and half of each other."""
    costs = sorted((data.FIGHTER_POINTS[t] for t in _group_types(entry) if t in data.FIGHTER_POINTS),
                   reverse=True)
    if not costs:
        return 0
    return (costs[0] + sum(c // 2 for c in costs[1:])
            + sum(data.FIGHTER_EXTRAS.get(x, 0) for x in _group_extras(entry)))


def salvo_space(entry: dict, salvo: str) -> int | None:
    """Magazine MASS one salvo of this load takes: an extra stage adds 2 (PC p.52)."""
    if salvo not in data.SALVO_SPACE:
        return None
    return data.SALVO_SPACE[salvo] + (2 * (_magazine_stages(entry) - 1) if salvo == "std" else 0)


def _salvo_surcharge(entry: dict) -> int:
    """Points a multi-stage load costs beyond the magazine space it fills (as in CD)."""
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
    if stype in data.OPTIONAL_SYSTEMS or (stype == "launch_tube" and _yes(system, "catapult")):
        return "pc_optional_systems"
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
    "pc_optional_systems": lambda: _("Launch catapults and flawed designs"),
    "cd_multistage": lambda: _("Multi-stage missiles"),
}


# ---- Type suggestion ----------------------------------------------------------------------------


def _bays(design: dict) -> int:
    return sum(max(1, _int(s.get("bays"), 1)) for s in _systems(design) if s.get("type") in BAY_TYPES)


def suggest_type(design: dict) -> tuple[str, str]:
    tmf = _tmf(design)
    if design.get("hull_kind") == "merchant":
        return common.class_label("Merchant"), "M"
    if any(s.get("type") == "portal" for s in _systems(design)):
        return _("Portal"), "PT"
    if transfer_mass(design):
        return _("Jump gate"), "JG"
    if design.get("hull_kind") == "starbase":
        return _("Starbase section"), "SB"
    if _bays(design) >= data.CARRIER_MIN_BAYS and tmf >= data.CARRIER_CLASSES[0][2]:
        return common.pick_class(tmf, data.CARRIER_CLASSES)
    return common.pick_class(tmf, data.SHIP_CLASSES)


# ---- Validation ---------------------------------------------------------------------------------

# Most arcs a weapon may have (PC pp.41-55); None for no limit. Weapons not listed take any arcs:
# "like multi-arc weapons, turret arcs do not have to be contiguous" (p.45).
MAX_ARCS = {
    "needle_beam": 3, "pulse_torpedo": 3, "fusion_array": 3, "plasma_bolt": 3,
    "submunition": 3, "sm_launcher": 3, "sm_rack": 3, "heavy_missile": 3, "am_missile": 3,
    "boarding_torpedo_launcher": 3, "mkp": 1, "rocket_pod": 1,
}
ARCED_TYPES = {
    "beam", "emp", "transporter", "grav_gun", "plasma_cannon", "graser", "phaser", "heavy_graser",
    "gatling", "twin_particle_array", "meson", "pulser", "needle_beam", "pulse_torpedo",
    "submunition", "kgun", "mkp", "boarding_torpedo_launcher", "fusion_array", "plasma_bolt",
    "sm_launcher", "sm_rack", "heavy_missile", "am_missile", "rocket_pod", "ads",
}


def validate_design(design: dict, options: dict) -> list[Issue]:
    """Violations and infos. A system behind a fleet option is a violation only where the fleet
    has that option off; the Design tab passes no options, so there it is a note."""
    issues: list[Issue] = []

    def violation(code: str, message: str, uid: str | None = None) -> None:
        issues.append(Issue(code, "violation", message, uid))

    def info(code: str, message: str, uid: str | None = None) -> None:
        issues.append(Issue(code, "info", message, uid))

    tmf = _int(design.get("tmf"))
    boxes = _int(design.get("hull_boxes"))
    if tmf <= 0:
        violation("bad_tmf", _("Total MASS must be at least 1."))
    if tmf > data.MAX_MASS and design.get("hull_kind") != "starbase":
        info("mass_over_300", _("PC suggests MASS {n} at most; bigger ships are better built "
                                "as monster ship sections.", n=data.MAX_MASS))
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
        if len(shell_layers(design)) > 5:
            violation("shell_layers_max", _("Shell armour has an inner layer and four shells at most."))

    systems = _systems(design)
    by_uid = {s["uid"]: s for s in systems if isinstance(s.get("uid"), str)}
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
        if stype in ("sm_rack", "heavy_missile") and _stages(s) > 1 and s.get("load") == "er":
            violation("multistage_er", _("Only standard missiles may have extra stages."), uid)
        if stype == "shipyard" and design.get("hull_kind") != "starbase":
            violation("starbase_only", _("Shipyards are built only into space stations."), uid)
        if stype == "kgun" and _class(s, 6) == 1 and _yes(s, "flak"):
            info("k1_flak", _("Flak ammunition is for K-guns of class 2 or larger."), uid)

    _validate_counts(design, systems, violation, info)
    common.validate_missiles(design, systems, by_uid, violation, salvo_space)
    _validate_magazine_loads(design, by_uid, options, violation, info)
    _validate_hangars(design, systems, by_uid, violation, info)
    _validate_crew(design, systems, violation)
    _validate_stationary(design, systems, violation)

    if not any(s.get("type") in ("fire_control", "advanced_fire_control") for s in systems):
        info("no_fire_control", _("No fire control: weapons that need one cannot fire."))
    if design.get("ftl") is not True and not stationary(design):
        info("no_ftl", _("No FTL drive: a battle rider (MASS {n} at most) needs a mothership; "
                         "a system defence ship needs the fleet's agreement.", n=data.RIDER_MAX_MASS))
    for s in systems:
        if s.get("type") in ("screen", "advanced_screen") and _int(s.get("level"), 1) > 2:
            info("screen_backups", _("Screen generators beyond level 2 are backups only."), s.get("uid"))
    return issues


def _validate_counts(design: dict, systems: list[dict], violation, info) -> None:
    """Limits that count systems on the whole ship."""
    tmf = _tmf(design)
    per_50 = max(1, math.ceil(tmf / 50))
    types = [s.get("type") for s in systems]
    if {"screen", "advanced_screen"} <= set(types):
        violation("mixed_screens", _("A ship cannot have both advanced and standard screens."))
    if types.count("plasma_bolt") > per_50:
        # PC p.54: one launcher per 50 MASS of ship (1-50 one, 101-150 three).
        violation("plasma_bolt_count", _("A ship mounts one plasma bolt launcher per 50 MASS: "
                                         "{n} at most.", n=per_50))
    spinal = sum(data.SPINAL_MASS[_spinal_size(s)] for s in systems if s.get("type") == "spinal_mount")
    if spinal > data.SPINAL_MASS_PER_50 * per_50:
        # PC p.46 and the errata: 16 MASS of spinal mounts per 50 MASS of ship or part of it.
        violation("spinal_mass", _("At most {n} MASS of spinal mounts on this ship (16 per 50 MASS).",
                                   n=data.SPINAL_MASS_PER_50 * per_50))
    stealth = stealth_hull(design) + sum(_level(s, 2) for s in systems if s.get("type") == "stealth_field")
    if stealth > 2:
        violation("stealth_over_2", _("Stealth hulls and fields add up to level 2 at most."))
    kguns = [s for s in systems if s.get("type") == "kgun" and _class(s, 6) > 1]
    if kguns and 0 < sum(1 for s in kguns if _yes(s, "flak")) < len(kguns):
        violation("flak_all", _("All of a ship's K-guns but its K-1s carry flak, or none do."))
    tubes = [s for s in systems if s.get("type") == "launch_tube"]
    if tubes and 0 < sum(1 for s in tubes if _yes(s, "catapult")) < len(tubes):
        violation("catapult_all", _("If one launch tube has a catapult, they all must."))
    if "flawed_design" in types:
        # PC p.113: not on escorts, cruisers under MASS 60 or ships with advanced hulls.
        if tmf < 60 or _advanced_hull(design):
            violation("flawed_not_allowed", _("Escorts, cruisers under MASS 60 and advanced hulls "
                                              "cannot be flawed designs."))
        if types.count("flawed_design") > 1:
            violation("flawed_twice", _("A design is flawed once."))
    if "pds" in types and ("scattergun" in types or "grapeshot" in types):
        info("pds_and_scatterguns", _("The book's authors do not combine PDS with scatterguns."))


def _validate_crew(design: dict, systems: list[dict], violation) -> None:
    """PC p.111 and the errata: extra marines and damage control parties up to the crew factor
    in any mix; more need troop berthing (3 marines a MASS) or passenger berthing (4 DCPs)."""
    marines = sum(_count(s) for s in systems if s.get("type") == "marines")
    dcps = sum(_count(s) for s in systems if s.get("type") == "dcp")
    if not marines and not dcps:
        return
    troops = 3 * sum(_mass_param(s) for s in systems if s.get("type") == "troop_berthing")
    berths = 4 * sum(_mass_param(s) for s in systems if s.get("type") == "passenger_berthing")
    beyond = max(0, marines - troops) + max(0, dcps - berths)
    if beyond > crew_factors(design):
        violation("crew_over", _(
            "{n} marine and damage control parties need berthing: the crew factor houses {cf} "
            "beyond what troop and passenger berthing hold.", n=marines + dcps, cf=crew_factors(design)))


def _validate_stationary(design: dict, systems: list[dict], violation) -> None:
    """Gates and starbases (PC pp.91, 115): stationary, so thrust 0; a gate needs hull boxes of
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


def _validate_arcs(s: dict, uid: str | None, violation) -> None:
    stype = s["type"]
    arcs = s.get("arcs")
    if stype not in ARCED_TYPES:
        return
    if stype == "submunition" and arcs is None:
        return
    if not arcs_valid(arcs):
        violation("bad_arcs",
                  _("Choose at least one fire arc ({arcs}), each once.", arcs=", ".join(ARCS)), uid)
        return
    most = MAX_ARCS.get(stype)
    if stype == "kgun":
        most = 6 if _class(s, 6) == 1 else 2 if _class(s, 6) == 2 else 1
    if most is not None and len(arcs) > most:
        violation("too_many_arcs", _("This weapon fires through {n} arcs at most.", n=most), uid)


def _option_issue(key: str, options: dict, uid: str | None, violation, info) -> None:
    if options.get(key) is False:
        violation("option_off", _("This system needs the fleet option: {name}.",
                                  name=OPTION_NAMES[key]()), uid)
    elif key not in options:
        info("option_needed", _("A fleet must switch on: {name}.", name=OPTION_NAMES[key]()), uid)


def _validate_magazine_loads(design: dict, by_uid: dict, options: dict, violation, info) -> None:
    """A magazine carries regular or multi-stage loads, never a mix; only standard missiles
    take extra stages (PC p.52)."""
    for entry in _entries(design.get("default_loadout"), "magazines"):
        mag = by_uid.get(entry.get("magazine"))
        if _magazine_stages(entry) == 1 or not mag or mag.get("type") != "sm_magazine":
            continue
        _option_issue("cd_multistage", options, mag["uid"], violation, info)
        salvos = entry.get("salvos") if isinstance(entry.get("salvos"), list) else []
        if "er" in salvos:
            violation("multistage_er", _("Only standard missiles may have extra stages."), mag["uid"])


def _validate_hangars(design: dict, systems: list[dict], by_uid: dict, violation, info) -> None:
    """A bay holds one wing (6 MASS of craft, PC p.109). Hangar bays launch through launch tubes;
    the combined bay launches by itself (p.110) and the book advises against mixing the two."""
    types = {s.get("type") for s in systems}
    if "hangar_bay" in types and "launch_tube" not in types:
        violation("bays_without_tubes", _("Hangar bays launch and recover through launch tubes, "
                                          "and this design has none."))
    if {"hangar_bay", "hangar"} <= types:
        info("mixed_hangars", _("The book advises against combined bays beside hangar bays."))
    loadout = design.get("default_loadout")
    used: dict[str, int] = {}
    for entry in _entries(loadout, "fighters"):
        hangar = by_uid.get(entry.get("hangar"))
        if not hangar or hangar.get("type") not in BAY_TYPES:
            violation("fighters_without_hangar",
                      _("Fighter group assigned to a hangar this design does not have."))
            continue
        if (any(t not in data.FIGHTER_POINTS for t in _group_types(entry))
                or any(x not in data.FIGHTER_EXTRAS for x in _group_extras(entry))):
            violation("unknown_fighter_type", _("Unknown fighter type."), hangar["uid"])
        used[hangar["uid"]] = used.get(hangar["uid"], 0) + data.BAY_CRAFT_MASS
    for entry in _entries(loadout, "craft"):
        hangar = by_uid.get(entry.get("hangar"))
        if not hangar or hangar.get("type") not in BAY_TYPES:
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
