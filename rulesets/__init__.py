"""Rulesets (layers 1+2): per-ruleset game data and pure rules behind one protocol.

The `Ruleset` protocol and the registry are built in M2 (PLAN 6.1). Each ruleset is a package
here (`fb`, `ft2`) and registers itself in RULESETS; fleet_rules.py never branches on an id.
"""

from __future__ import annotations

RULESETS: dict[str, object] = {}
