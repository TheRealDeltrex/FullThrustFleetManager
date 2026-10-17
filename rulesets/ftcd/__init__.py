"""FTCD ruleset: Full Thrust Cross Dimensions (PLAN 6.4), human tech.

The alien races of FB2 are not part of this ruleset yet: CD p.21 only adjusts how their weapons
meet advanced screens, and their designs stay with the FB ruleset.
"""

from __future__ import annotations

from i18n import _
from rulesets import Breakdown, Issue, QuickRefEntry, Race, SystemDef, common
from rulesets.fb import _quickref
from rulesets.ftcd import data, rules


class FTCDRuleset:
    id = "ftcd"
    accent_color = "--rs-ftcd"
    books = data.BOOKS
    arcs = common.ARCS
    icon_set = "ftcd"
    max_stages = data.MAX_STAGES  # the loadout editor's stage choice per magazine (CD p.25)
    # In the order a player reads them: what the fleet may field, then how points are counted,
    # then play rules the quick reference adds. Re-rolls are standard in CD (p.14), so no toggle.
    option_keys = (
        "cd_optional_systems", "cd_multistage", "cd_super_weapons",
        "cd_cpv", "cd_advanced_ftl",
        "core_systems", "fighter_endurance", "vector_movement",
    )

    @property
    def name(self) -> str:
        return _("Cross Dimensions")

    @property
    def short_label(self) -> str:
        return "FTCD"

    def races(self) -> list[Race]:
        return [Race("human", _("Human"))]

    def icon_set_for(self, race: str) -> str:
        return self.icon_set

    def system_types(self, race: str, options: dict) -> list[SystemDef]:
        return data.system_defs() if race == "human" else []

    def design_breakdown(self, design: dict, options: dict) -> Breakdown:
        return rules.design_breakdown(design, options)

    def validate_design(self, design: dict, options: dict) -> list[Issue]:
        return rules.validate_design(design, options)

    def loadout_points(self, design: dict, loadout: dict | None, options: dict) -> int:
        return rules.loadout_points(design, loadout, options)

    def fighter_types(self, options: dict, race: str = "human") -> list[str]:
        return list(data.FIGHTER_POINTS)

    def fighter_label(self, fighter_type: str) -> str:
        return data.fighter_label(fighter_type)

    def required_options(self, design: dict, loadout: dict | None) -> set[str]:
        return rules.required_options(design, loadout)

    def damage_track(self, design: dict) -> list[int]:
        return rules.damage_track(design)

    def crew_factors(self, design: dict) -> int:
        return rules.crew_factors(design)

    def cf_positions(self, design: dict) -> list[int]:
        return rules.cf_positions(design)

    def threshold_numbers(self, design: dict) -> list[int]:
        return rules.threshold_numbers(design)

    def suggest_type(self, design: dict) -> tuple[str, str]:
        return rules.suggest_type(design)

    def quickref(self, systems_present: set[str], options: dict,
                 races: frozenset[str] = frozenset({"human"})) -> list[QuickRefEntry]:
        always = ("turn_sequence", "arcs", "hull_track", "threshold", "crew", "fire_control",
                  "rerolls")
        wanted = set(systems_present)
        # Systems the book describes together share one entry.
        for system, entries in SHARED_ENTRIES.items():
            if system in wanted:
                wanted |= entries
        return _quickref("ftcd", wanted, always, options)


SHARED_ENTRIES = {
    "sm_launcher": {"missile_damage", "sm_magazine"},
    "sm_rack": {"sm_launcher", "missile_damage", "sm_magazine"},
    "heavy_missile": {"sm_launcher", "missile_damage", "sm_magazine"},
    "superior_sensors": {"enhanced_sensors"},
    "weasel_capital": {"weasel_cruiser"},
    "area_ecm": {"ecm"},
}


RULESET = FTCDRuleset()
