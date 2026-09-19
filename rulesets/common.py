"""Maths shared by more than one ruleset: rounding, arcs, damage-track splits, CF dots."""

from __future__ import annotations

import math

# FB six arcs, clockwise from fore (PLAN 5.1). FT2 has its own four (rulesets/ft2/data.py).
ARCS = ("F", "FS", "AS", "A", "AP", "FP")


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
