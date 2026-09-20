"""More Thrust additions to FT2, each behind a fleet toggle (PLAN 6.3).

- mt_systems: missiles, AA megabatteries, wave gun (MT p.3), ortillery, reflex field, cloaking
  field (MT p.4).
- mt_superships: hulls over MASS 100 (MT p.22).
- mt_fighters: specialised fighter types, surcharges on the 20-point group (MT p.12).
MT has a native text layer; values are as printed.
"""

from __future__ import annotations

import math

# type -> (MASS(ship MASS), points(ship MASS))
SYSTEMS = {
    "mt_missile": (lambda m: 2, lambda m: 6),  # per missile
    "aa_battery": (lambda m: 5, lambda m: 15),  # capital ships and superships, one arc
    "wave_gun": (lambda m: 10, lambda m: 30),
    "ortillery": (lambda m: 3, lambda m: 10),
    "reflex_field": (lambda m: 6, lambda m: 40),
    # "1 per 10 MASS of ship", rounded up like the owner's FT2 rounding elsewhere.
    "cloak": (lambda m: max(1, math.ceil(m / 10)), lambda m: 2 * m),
}

# Extra points per group of 6 on top of the 20-point group (MT p.12).
FIGHTER_SURCHARGE = {
    "standard": 0,
    "interceptor": 0,
    "fast": 12,
    "heavy": 12,
    "attack": 6,
    "long_range": 12,
    "torpedo": 18,
}


def is_supership(mass: int) -> bool:
    return mass > 100


def supership_extra_fire_controls(mass: int) -> int:
    """One more standard fire control per full 50 MASS over 100 (MT p.22)."""
    return max(0, (mass - 100) // 50)


def supership_extra_rows(mass: int) -> int:
    """One more damage row per (part of) 50 MASS over 100: 101-150 has 5 rows (MT p.22)."""
    return max(0, math.ceil((mass - 100) / 50))


def fighter_requires_toggle(ftype: object) -> bool:
    return ftype != "standard"
