"""FB ruleset: Fleet Book 1 design system with the Fleet Book 2 amendments (PLAN 6.2)."""

from __future__ import annotations

from i18n import _
from rulesets import QuickRefEntry, Race, SystemDef
from rulesets.fb import data, rules


class FBRuleset:
    id = "fb"
    accent_color = "--rs-fb"
    books = data.BOOKS
    icon_set = None  # M6

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

    def quickref(self, systems_present: set[str], options: dict) -> list[QuickRefEntry]:
        return []  # M9: original rulebook wording per system


RULESET = FBRuleset()
