"""schema_version upgrades for every stored or exchanged file (PLAN 5).

Each step is a function upgrading one kind of document from version N to N+1, registered in
STEPS[kind][N]. Write the step and its test in the same commit as the schema change, and bump
CURRENT. Files newer than this build are refused rather than guessed at.
"""

from __future__ import annotations

from collections.abc import Callable

CURRENT = 2
KINDS = ("design", "fleet", "factions", "settings")

# STEPS[kind][from_version] = fn(doc) -> doc at from_version + 1
STEPS: dict[str, dict[int, Callable[[dict], dict]]] = {kind: {} for kind in KINDS}


def _design_1_to_2(doc: dict) -> dict:
    """v2 adds the Phalon multi-layered shell (FB2 p.35).

    `armour` keeps its meaning, the total number of armour or shell boxes, so a v1 design needs
    no conversion: an empty `armour_layers` means one layer, which is what every other race has.
    The field is spelled out here rather than left to normalize_design so that a file written by
    a newer build is recognisably v2 and an older build refuses it instead of silently dropping
    the layers and costing the ship wrong.
    """
    doc.setdefault("armour_layers", [])
    loadout = doc.get("default_loadout")
    if isinstance(loadout, dict):
        loadout.setdefault("pulsers", [])  # Phalon pulser L/M/C settings (FB2 p.35)
    return doc


def _fleet_1_to_2(doc: dict) -> dict:
    """Ship loadouts override the design's, so they gain the same pulser list."""
    for ship in doc.get("ships", []) if isinstance(doc.get("ships"), list) else []:
        loadout = ship.get("loadout") if isinstance(ship, dict) else None
        if isinstance(loadout, dict):
            loadout.setdefault("pulsers", [])
    return doc


class TooNewError(ValueError):
    pass


STEPS["design"][1] = _design_1_to_2
STEPS["fleet"][1] = _fleet_1_to_2
# factions and settings are unchanged by v2, so they step forward untouched.
STEPS["factions"][1] = lambda doc: doc
STEPS["settings"][1] = lambda doc: doc


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
