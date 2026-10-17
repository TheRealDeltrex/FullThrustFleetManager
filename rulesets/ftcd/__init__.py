"""FTCD ruleset: Full Thrust Cross Dimensions (PLAN 6.4).

Human tech is the CD design system (rules.py). The Fleet Book 2 races are their FB2 tech modules
with the changes of CD p.21 (aliens.py). CD prints no ship designs: "all of the ships in fleet
book 1 can be used unchanged" and FB2's "may require slight changes" (CD p.3), so the catalog is
the Fleet Book catalog adopted at load time (`adopt_design`), never a second copy on disk.
"""

from __future__ import annotations

import copy
from types import ModuleType

from i18n import _
from rulesets import Breakdown, Issue, QuickRefEntry, Race, SystemDef, common
from rulesets.fb import _load_quickref, _quickref
from rulesets.fb import tech as fb_tech
from rulesets.ftcd import aliens, data, rules


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

    catalog_sources = ("fb",)

    def races(self) -> list[Race]:
        return [Race("human", _("Human")), *aliens.races()]

    def icon_set_for(self, race: str) -> str:
        return aliens.module_for(race).ICON_SET if aliens.is_alien(race) else self.icon_set

    def system_types(self, race: str, options: dict) -> list[SystemDef]:
        if aliens.is_alien(race):
            return aliens.system_defs(race)
        return data.system_defs() if race == "human" else []

    def design_breakdown(self, design: dict, options: dict) -> Breakdown:
        return _engine(design).design_breakdown(design, options)

    def validate_design(self, design: dict, options: dict) -> list[Issue]:
        return _engine(design).validate_design(design, options)

    def loadout_points(self, design: dict, loadout: dict | None, options: dict) -> int:
        return _engine(design).loadout_points(design, loadout, options)

    def fighter_types(self, options: dict, race: str = "human") -> list[str]:
        if aliens.is_alien(race):
            return list(aliens.module_for(race).FIGHTER_POINTS)
        return list(data.FIGHTER_POINTS)

    def required_options(self, design: dict, loadout: dict | None) -> set[str]:
        return set() if _alien(design) else rules.required_options(design, loadout)

    def damage_track(self, design: dict) -> list[int]:
        return _tech(design).damage_track(design)

    def crew_factors(self, design: dict) -> int:
        return _tech(design).crew_factors(design)

    def cf_positions(self, design: dict) -> list[int]:
        return _tech(design).cf_positions(design)

    def threshold_numbers(self, design: dict) -> list[int]:
        return _tech(design).threshold_numbers(design)

    def suggest_type(self, design: dict) -> tuple[str, str]:
        return _tech(design).suggest_type(design)

    def adopt_design(self, design: dict) -> dict | None:
        """A Fleet Book catalog design as a Cross Dimensions one (CD p.3): the same ship under
        an `ftcd:` id, costed by this ruleset. Where CD p.21 changes an FB2 design the changes
        go in its notes, and the printed NPV is kept only while it still holds."""
        out = copy.deepcopy(design)
        out["id"] = "ftcd:" + str(design.get("id", "")).split(":", 1)[-1]
        out["ruleset"] = self.id
        changes = aliens.adopt(out) if _alien(out) else []
        source = out.get("source") if isinstance(out.get("source"), dict) else {}
        printed = source.get("npv_book")
        points = self.design_breakdown(out, {}).points
        if printed and printed != points:
            source["npv_book"] = 0
            changes.append(f"{source.get('book')} p.{source.get('page')} prints NPV {printed}; "
                           f"under Cross Dimensions the design costs {points}.")
        if changes:
            out["notes"] = " ".join(["Cross Dimensions:", *changes, out.get("notes") or ""]).strip()
        return out

    def quickref(self, systems_present: set[str], options: dict,
                 races: frozenset[str] = frozenset({"human"})) -> list[QuickRefEntry]:
        races = frozenset(races)
        always = {"turn_sequence", "arcs", "hull_track", "threshold", "rerolls"}
        if any(r == "human" or aliens.module_for(r).CREWED for r in races):
            always |= {"crew", "fire_control"}  # a Sa'Vasku construct has neither (FB2 p.22)
        wanted = set(systems_present)
        # Systems the book describes together share one entry.
        for system, entries in SHARED_ENTRIES.items():
            if system in wanted:
                wanted |= entries
        # Each FB2 race keeps its own FB2 entries, with CD p.21's paragraph on what changes
        # beside them. Kra'Vak scatterguns follow the CD scattergun rules, whose entry the
        # "scattergun" system already brings, so FB2's is left out.
        alien: set[str] = set()
        for race, prefix, base in ALIEN_ENTRIES:
            if race in races:
                always.add(f"cd_{race}")
                alien |= base | {f"{prefix}{t}" for t in systems_present}
        alien.discard("kv_scattergun")
        fb = [e for e in _load_quickref("fb") if e.key in alien]
        return _quickref("ftcd", wanted, tuple(sorted(always)), options) + fb


SHARED_ENTRIES = {
    "sm_launcher": {"missile_damage", "sm_magazine"},
    "sm_rack": {"sm_launcher", "missile_damage", "sm_magazine"},
    "heavy_missile": {"sm_launcher", "missile_damage", "sm_magazine"},
    "superior_sensors": {"enhanced_sensors"},
    "weasel_capital": {"weasel_cruiser"},
    "area_ecm": {"ecm"},
}


# (race, FB2 entry prefix, the FB2 entries every sheet of that race carries), as the FB ruleset.
ALIEN_ENTRIES = (
    ("kravak", "kv_", {"kv_thrust", "kv_crew"}),
    ("phalon", "ph_", {"ph_shell", "ph_pds"}),
    ("savasku", "sv_", {"sv_power", "sv_thrust", "sv_biomass", "sv_repair"}),
)


def _alien(design: dict) -> bool:
    return isinstance(design, dict) and aliens.is_alien(design.get("race"))


def _engine(design: dict) -> ModuleType:
    """Costing and validation: CD human rules, or an FB2 race with the CD p.21 changes."""
    return aliens if _alien(design) else rules


def _tech(design: dict) -> ModuleType:
    """Damage track, crew and type suggestion: unchanged from the race's FB2 module."""
    return fb_tech.module_for(design.get("race")) if _alien(design) else rules


RULESET = FTCDRuleset()
