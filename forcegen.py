"""The force generator (PLAN 11.3, roadmap step G3): a points budget turned into a list of
catalog designs. Pure: the caller hands in the candidates with their points and scan class.

FT p.37's rule for the Lafayette forces is that no class may be more than half of a force's
ships, and the generator holds every force to it (an app rule elsewhere): each pick goes to
the least-used class that still fits the budget and the rule, a random design within it. A
single ship is a force of one class, so the rule starts to bind from the second ship on.
"""

from __future__ import annotations

import random

MAX_SHIPS = 60


def allowed(counts: dict[str, int], cls: str) -> bool:
    """Whether one more ship of the class keeps it at half the force or less."""
    n = sum(counts.values())
    return n == 0 or (counts.get(cls, 0) + 1) * 2 <= n + 1


def pick(candidates: list[tuple[str, int, str]], budget: int, rng: random.Random) -> list[str]:
    """Design ids whose points add up to at most `budget`, from (id, points, class) candidates."""
    chosen: list[str] = []
    counts: dict[str, int] = {}
    left = budget
    while len(chosen) < MAX_SHIPS:
        fits = [c for c in candidates if 0 < c[1] <= left and allowed(counts, c[2])]
        if not fits:
            break
        least = min(counts.get(c[2], 0) for c in fits)
        design_id, points, cls = rng.choice([c for c in fits if counts.get(c[2], 0) == least])
        chosen.append(design_id)
        counts[cls] = counts.get(cls, 0) + 1
        left -= points
    return chosen
