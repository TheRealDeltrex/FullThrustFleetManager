"""Weekly campaign events (PLAN 11.3, roadmap step G4), all app rules: each side rolls 2D6 at
the start of every week when a campaign has events turned on. Pure: the table and its labels;
the store applies the result.

2-3 unrest (an unguarded settled world of the side's breaks away), 4 supply trouble (no repairs
or replenishment for the side this week), 5 pirates (an unguarded outpost of the side is lost),
6-8 a quiet week, 9 intelligence leak (the side's forces are seen by everyone this week under
hidden movement), 10 reinforcements late (the side's next group comes a week later), 11-12
reinforcements early (its next group arrives now).
"""

from __future__ import annotations

KINDS = ("unrest", "supply", "pirates", "quiet", "leak", "late", "early")


def kind_for(total: int) -> str:
    if total <= 3:
        return "unrest"
    if total == 4:
        return "supply"
    if total == 5:
        return "pirates"
    if total <= 8:
        return "quiet"
    if total == 9:
        return "leak"
    if total == 10:
        return "late"
    return "early"
