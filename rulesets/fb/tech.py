"""Tech modules of the FB ruleset, one per race (PLAN 3, decision 3: races are additive modules
inside a ruleset, not new rulesets).

A tech module is a plain module exposing the per-design half of the `Ruleset` protocol:
`system_defs()`, `design_breakdown`, `validate_design`, `loadout_points`, `damage_track`,
`crew_factors`, `cf_positions`, `threshold_numbers`, `suggest_type`, plus `ICON_SET` and
`FIGHTER_POINTS`. `rulesets/fb/__init__.py` dispatches on `design["race"]`; nothing above the
ruleset layer knows the modules exist.

Adding a race is: write the module, add a `Race` here, add its icon set to `ssd_layout`.
"""

from __future__ import annotations

from types import ModuleType

from i18n import _
from rulesets import Race
from rulesets.fb import kravak, phalon, rules, savasku

# race id -> (name factory, module). The name is a callable so it follows the language.
_TECH: dict[str, tuple[object, ModuleType]] = {
    "human": (lambda: _("Human"), rules),
    "kravak": (lambda: _("Kra'Vak"), kravak),
    "savasku": (lambda: _("Sa'Vasku"), savasku),
    "phalon": (lambda: _("Phalon"), phalon),
}


def races() -> list[Race]:
    return [Race(rid, name()) for rid, (name, _mod) in _TECH.items()]


def race_ids() -> tuple[str, ...]:
    return tuple(_TECH)


def module_for(race: object) -> ModuleType:
    """The tech module for a race id; unknown races fall back to human, because a design read
    from disk is semi-untrusted and nothing in a ruleset may raise on a malformed design."""
    entry = _TECH.get(race if isinstance(race, str) else "")
    return entry[1] if entry else rules


def module_for_design(design: dict) -> ModuleType:
    return module_for(design.get("race") if isinstance(design, dict) else None)
