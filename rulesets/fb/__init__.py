"""FB ruleset: Fleet Book 1 design system with the Fleet Book 2 amendments (PLAN 6.2)."""

from __future__ import annotations

import json

import paths
from i18n import _
from rulesets import QuickRefEntry, Race, SystemDef, common
from rulesets.fb import data, rules


class FBRuleset:
    id = "fb"
    accent_color = "--rs-fb"
    books = data.BOOKS
    arcs = common.ARCS
    icon_set = "fb"  # the icon table in ssd_layout.ICON_SETS

    @property
    def name(self) -> str:
        return _("Fleet Books")

    @property
    def short_label(self) -> str:
        return "FB"

    def races(self) -> list[Race]:
        return [Race("human", _("Human"))]

    def system_types(self, race: str, options: dict) -> list[SystemDef]:
        return data.system_defs() if race == "human" else []

    design_breakdown = staticmethod(rules.design_breakdown)
    validate_design = staticmethod(rules.validate_design)
    loadout_points = staticmethod(rules.loadout_points)
    damage_track = staticmethod(rules.damage_track)
    crew_factors = staticmethod(rules.crew_factors)
    cf_positions = staticmethod(rules.cf_positions)
    threshold_numbers = staticmethod(rules.threshold_numbers)
    suggest_type = staticmethod(rules.suggest_type)

    def fighter_types(self, options: dict) -> list[str]:
        return list(data.FIGHTER_POINTS)

    def required_options(self, design: dict, loadout: dict | None) -> set[str]:
        return set()

    def quickref(self, systems_present: set[str], options: dict) -> list[QuickRefEntry]:
        always = ("turn_sequence", "arcs", "hull_track", "threshold", "crew", "fire_control")
        return _quickref("fb", systems_present, always, options)


def _load_quickref(ruleset_id: str) -> list[QuickRefEntry]:
    """Entries from data/quickref/<id>.json, built by tools/extract_quickref.py from the books
    (PLAN 2.5: original wording, never a paraphrase, so this text is data, not source)."""
    path = paths.bundle_dir() / "data" / "quickref" / f"{ruleset_id}.json"
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [
        QuickRefEntry(key=e["key"], title=e["title"], text=e["text"], book=e["book"], page=e["page"])
        for e in doc.get("entries", []) if isinstance(e, dict)
    ]


def _quickref(ruleset_id: str, systems_present: set[str], keys_always: tuple[str, ...],
              options: dict) -> list[QuickRefEntry]:
    wanted = set(systems_present) | set(keys_always)
    if options.get("core_systems"):
        wanted.add("core_systems")
    if options.get("rerolls"):
        wanted.add("rerolls")
    if options.get("vector_movement"):
        wanted.add("vector_movement")
    return [e for e in _load_quickref(ruleset_id) if e.key in wanted]


RULESET = FBRuleset()
