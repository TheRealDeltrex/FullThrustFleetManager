"""FTPC ruleset: Full Thrust Project Continuum (PLAN 6.4).

Human tech is the PC design system (rules.py). The Fleet Book 2 races are their FB2 tech modules
unchanged: PC's authors decided that "nothing we wrote ... would invalidate what was previously
established in Fleet Books one and two" (errata, Rule clarifications). PC prints no fleet lists
of its own, so the catalog is the Fleet Book catalog adopted at load time (`adopt_design`),
costed by PC's rules, as Cross Dimensions does.
"""

from __future__ import annotations

import copy
from types import ModuleType

from i18n import _
from rulesets import Breakdown, Issue, QuickRefEntry, Race, SystemDef, common, fleet_common
from rulesets.fb import _load_quickref, _quickref
from rulesets.fb import tech as fb_tech
from rulesets.ftpc import data, rules

ALIEN_RACES = ("kravak", "savasku", "phalon")


class FTPCRuleset:
    id = "ftpc"
    accent_color = "--rs-ftpc"
    books = data.BOOKS
    arcs = common.ARCS
    icon_set = "ftpc"
    max_stages = data.MAX_STAGES
    # What the fleet may field, then how points are counted, then play rules.
    option_keys = (
        "pc_optional_systems", "cd_multistage", "cd_system_defence", "pc_adfc_no_mass",
        "pc_hangar_criticals", "pc_overload_torpedoes", "cd_cpv", "cd_patrol_battle",
        "cd_capital_limit", "core_systems", "fighter_endurance", "vector_movement",
    )
    catalog_sources = ("fb",)
    dummy_bogey_points = data.DUMMY_BOGEY_POINTS
    hull_kinds = data.HULL_KINDS

    @property
    def name(self) -> str:
        return _("Project Continuum")

    @property
    def short_label(self) -> str:
        return "FTPC"

    @property
    def fighter_extras(self) -> tuple[tuple[str, str], ...]:
        """The per-wing modifications the loadout editor offers (PC p.123)."""
        return (("ftl", _("FTL")), ("fast", _("Fast")), ("long_range", _("Long range")),
                ("heavy", _("Heavy")))

    def fleet_issues(self, fleet_doc: dict, ships: list[tuple[dict, dict]],
                     options: dict) -> list[Issue]:
        """Battle riders and motherships, system defence ships, dummy bogeys and the
        composition limits (PC pp.89-95, 139)."""
        def points(ship: dict, design: dict) -> int:
            return (self.design_breakdown(design, options).points
                    + self.loadout_points(design, ship.get("loadout"), options))
        return fleet_common.fleet_issues(
            fleet_doc, ships, options, ship_class=rules.ship_class, stationary=rules.stationary,
            ship_points=points)

    def morale_mass(self, ships: list[tuple[dict, dict]]) -> tuple[int, int] | None:
        return fleet_common.morale_mass(ships)

    def races(self) -> list[Race]:
        return [Race("human", _("Human")), *(r for r in fb_tech.races() if r.id in ALIEN_RACES)]

    def icon_set_for(self, race: str) -> str:
        return fb_tech.module_for(race).ICON_SET if _is_alien(race) else self.icon_set

    def system_types(self, race: str, options: dict) -> list[SystemDef]:
        if _is_alien(race):
            return fb_tech.module_for(race).system_defs()
        return data.system_defs() if race == "human" else []

    def design_breakdown(self, design: dict, options: dict) -> Breakdown:
        return _engine(design).design_breakdown(design, options)

    def validate_design(self, design: dict, options: dict) -> list[Issue]:
        return _engine(design).validate_design(design, options)

    def loadout_points(self, design: dict, loadout: dict | None, options: dict) -> int:
        return _engine(design).loadout_points(design, loadout, options)

    def fighter_types(self, options: dict, race: str = "human") -> list[str]:
        if _is_alien(race):
            return list(fb_tech.module_for(race).FIGHTER_POINTS)
        return list(data.FIGHTER_POINTS)

    def required_options(self, design: dict, loadout: dict | None) -> set[str]:
        return set() if _alien(design) else rules.required_options(design, loadout)

    def damage_track(self, design: dict) -> list[int]:
        return _engine(design).damage_track(design)

    def crew_factors(self, design: dict) -> int:
        return _engine(design).crew_factors(design)

    def cf_positions(self, design: dict) -> list[int]:
        return _engine(design).cf_positions(design)

    def threshold_numbers(self, design: dict) -> list[int]:
        return _engine(design).threshold_numbers(design)

    def suggest_type(self, design: dict) -> tuple[str, str]:
        return _engine(design).suggest_type(design)

    def adopt_design(self, design: dict) -> dict:
        """A Fleet Book catalog design as a Project Continuum one: the same ship under an
        `ftpc:` id, costed by PC's rules. The printed NPV is kept only while it still holds."""
        out = copy.deepcopy(design)
        out["id"] = "ftpc:" + str(design.get("id", "")).split(":", 1)[-1]
        out["ruleset"] = self.id
        source = out.get("source") if isinstance(out.get("source"), dict) else {}
        printed = source.get("npv_book")
        points = self.design_breakdown(out, {}).points
        if printed and printed != points:
            source["npv_book"] = 0
            out["notes"] = " ".join([
                f"Project Continuum: {source.get('book')} p.{source.get('page')} prints NPV "
                f"{printed}; under Project Continuum the design costs {points}.",
                out.get("notes") or ""]).strip()
        return out

    def quickref(self, systems_present: set[str], options: dict,
                 races: frozenset[str] = frozenset({"human"})) -> list[QuickRefEntry]:
        races = frozenset(races)
        always = {"turn_sequence", "arcs", "hull_track", "threshold", "fleet_morale"}
        if any(r == "human" or fb_tech.module_for(r).CREWED for r in races):
            always |= {"crew", "fire_control"}
        alien: set[str] = set()
        for race, prefix, base in ALIEN_ENTRIES:
            if race in races:
                alien |= base | {f"{prefix}{t}" for t in systems_present}
        fb = [e for e in _load_quickref("fb") if e.key in alien]
        return _quickref("ftpc", set(systems_present), tuple(sorted(always)), options) + fb


# (race, FB2 entry prefix, the FB2 entries every sheet of that race carries), as the FB ruleset.
ALIEN_ENTRIES = (
    ("kravak", "kv_", {"kv_thrust", "kv_crew"}),
    ("phalon", "ph_", {"ph_shell", "ph_pds"}),
    ("savasku", "sv_", {"sv_power", "sv_thrust", "sv_biomass", "sv_repair"}),
)


def _is_alien(race: object) -> bool:
    return race in ALIEN_RACES


def _alien(design: dict) -> bool:
    return isinstance(design, dict) and _is_alien(design.get("race"))


def _engine(design: dict) -> ModuleType:
    """PC human rules, or the race's FB2 tech module, which PC leaves as it is."""
    return fb_tech.module_for(design.get("race")) if _alien(design) else rules


RULESET = FTPCRuleset()
