"""FB ruleset: Fleet Book 1 design system with the Fleet Book 2 amendments (PLAN 6.2), plus the
Fleet Book 2 alien races as tech modules (rulesets/fb/tech.py).

Every per-design call dispatches on `design["race"]`, so a race is added by writing its module,
never by branching here.
"""

from __future__ import annotations

import json

import paths
from i18n import _
from rulesets import Breakdown, Issue, QuickRefEntry, Race, SystemDef, common
from rulesets.fb import data, tech


class FBRuleset:
    id = "fb"
    accent_color = "--rs-fb"
    books = data.BOOKS
    arcs = common.ARCS
    icon_set = "fb"  # human default; per race, use icon_set_for()

    @property
    def name(self) -> str:
        return _("Fleet Books")

    @property
    def short_label(self) -> str:
        return "FB"

    def races(self) -> list[Race]:
        return tech.races()

    def icon_set_for(self, race: str) -> str:
        return tech.module_for(race).ICON_SET

    def system_types(self, race: str, options: dict) -> list[SystemDef]:
        return tech.module_for(race).system_defs() if race in tech.race_ids() else []

    def design_breakdown(self, design: dict, options: dict) -> Breakdown:
        return tech.module_for_design(design).design_breakdown(design, options)

    def validate_design(self, design: dict, options: dict) -> list[Issue]:
        return tech.module_for_design(design).validate_design(design, options)

    def loadout_points(self, design: dict, loadout: dict | None, options: dict) -> int:
        return tech.module_for_design(design).loadout_points(design, loadout, options)

    def damage_track(self, design: dict) -> list[int]:
        return tech.module_for_design(design).damage_track(design)

    def crew_factors(self, design: dict) -> int:
        return tech.module_for_design(design).crew_factors(design)

    def cf_positions(self, design: dict) -> list[int]:
        return tech.module_for_design(design).cf_positions(design)

    def threshold_numbers(self, design: dict) -> list[int]:
        return tech.module_for_design(design).threshold_numbers(design)

    def suggest_type(self, design: dict) -> tuple[str, str]:
        return tech.module_for_design(design).suggest_type(design)

    def fighter_types(self, options: dict, race: str = "human") -> list[str]:
        return list(tech.module_for(race).FIGHTER_POINTS)

    def required_options(self, design: dict, loadout: dict | None) -> set[str]:
        return set()

    def quickref(self, systems_present: set[str], options: dict,
                 races: frozenset[str] = frozenset({"human"})) -> list[QuickRefEntry]:
        races = frozenset(races)
        always = {"turn_sequence", "arcs", "hull_track", "threshold"}
        if races & {"human", "kravak"}:
            # A Sa'Vasku construct has no crew factors and no fire control (it has cortex
            # nodes), so FB1's entries for those belong on a sheet only when a crewed race is
            # in the fleet.
            always |= {"crew", "fire_control"}
        wanted = set(systems_present)
        # FB2 restates movement, damage and the weapon summaries per race, so an alien sheet gets
        # its own entries beside the shared ones. The keys are prefixed, so the FB1 entry for the
        # same system still appears for the human designs in a mixed fleet.
        if "kravak" in races:
            always |= {"kv_thrust", "kv_crew"}
            wanted |= {f"kv_{t}" for t in systems_present}
        if "savasku" in races:
            # Power allocation, biomass and repair are the race's whole economy, so they are on
            # every Sa'Vasku sheet whatever nodes the ship carries.
            always |= {"sv_power", "sv_thrust", "sv_biomass", "sv_repair"}
            wanted |= {f"sv_{t}" for t in systems_present}
        return _quickref("fb", wanted, tuple(sorted(always)), options)


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
