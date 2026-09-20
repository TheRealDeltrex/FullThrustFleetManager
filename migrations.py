"""schema_version upgrades for every stored or exchanged file (PLAN 5).

Each step is a function upgrading one kind of document from version N to N+1, registered in
STEPS[kind][N]. Write the step and its test in the same commit as the schema change, and bump
CURRENT. Files newer than this build are refused rather than guessed at.
"""

from __future__ import annotations

from collections.abc import Callable

CURRENT = 1
KINDS = ("design", "fleet", "factions", "settings")

# STEPS[kind][from_version] = fn(doc) -> doc at from_version + 1
STEPS: dict[str, dict[int, Callable[[dict], dict]]] = {kind: {} for kind in KINDS}


class TooNewError(ValueError):
    pass


def upgrade(kind: str, doc: dict) -> dict:
    """Upgrade doc to CURRENT. A missing or bad schema_version counts as 1."""
    version = doc.get("schema_version")
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        version = 1
    if version > CURRENT:
        raise TooNewError(f"{kind} schema_version {version} is newer than this app ({CURRENT})")
    while version < CURRENT:
        doc = STEPS[kind][version](dict(doc))
        version += 1
    doc["schema_version"] = CURRENT
    return doc
