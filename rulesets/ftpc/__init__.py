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
from rulesets import Breakdown, BreakdownRow, Issue, QuickRefEntry, Race, SystemDef, common, fleet_common
from rulesets.fb import _load_quickref, _quickref
from rulesets.fb import tech as fb_tech
from rulesets.ftpc import data, rules, techbase

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
        "pc_optional_systems", "cd_multistage", "cd_system_defence", "pc_tech_base", "pc_adfc_no_mass",
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
                ("heavy", _("Heavy")), ("light", _("Light")), ("robot", _("Robot")))

    @property
    def gunboat_types(self) -> tuple[tuple[str, str], ...]:
        """The gunboat squadrons the loadout editor offers (PC pp.80-82), dearest last."""
        return tuple((key, gunboat_label(key)) for key in data.GUNBOAT_POINTS)

    @property
    def gunboat_extras(self) -> tuple[tuple[str, str], ...]:
        return (("ftl", _("FTL")), ("heavy", _("Heavy or screened")))

    def fleet_issues(self, fleet_doc: dict, ships: list[tuple[dict, dict]],
                     options: dict) -> list[Issue]:
        """Battle riders and motherships, system defence ships, dummy bogeys and the
        composition limits (PC pp.89-95, 139)."""
        def points(ship: dict, design: dict) -> int:
            return (self.design_breakdown(design, options).points
                    + self.loadout_points(design, ship.get("loadout"), options))
        issues = fleet_common.fleet_issues(
            fleet_doc, ships, options, ship_class=rules.ship_class,
            # A monster ship section without drives is part of a ship, not a battle rider.
            stationary=lambda d: rules.stationary(d) or rules.is_section(d), ship_points=points)
        if options.get("pc_tech_base"):
            issues += _tech_base_issues(ships, options)
        return issues

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
        b = _engine(design).design_breakdown(design, options)
        if not _alien(design) or not options.get("cd_cpv"):
            return b
        # The CPV option (PC p.140) prices every basic hull, alien ones too, as CD's does.
        rows = tuple(BreakdownRow(r.key, r.label, r.mass, rules.hull_cost(rules._tmf(design), options),
                                  r.system_uid) if r.key == "hull" else r for r in b.rows)
        return Breakdown(rows, b.mass_used, sum(r.points for r in rows), b.derived)

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
        always = {"turn_sequence", "arcs", "hull_track", "threshold", "rerolls", "fleet_morale"}
        if any(r == "human" or fb_tech.module_for(r).CREWED for r in races):
            always |= {"crew", "fire_control"}  # a Sa'Vasku construct has neither (FB2 p.22)
        wanted = set(systems_present)
        for system, entries in SHARED_ENTRIES.items():
            if system in wanted:
                wanted |= entries
        if options.get("pc_hangar_criticals") and wanted & set(common.FIGHTER_BAY_TYPES):
            wanted.add("hangar_criticals")
        if options.get("fighter_endurance"):
            wanted.add("fighter_endurance")
        alien: set[str] = set()
        for race, prefix, base in ALIEN_ENTRIES:
            if race in races:
                alien |= base | {f"{prefix}{t}" for t in systems_present}
        fb = [e for e in _load_quickref("fb") if e.key in alien]
        return _quickref("ftpc", wanted, tuple(sorted(always)), options) + fb


# Systems the book describes together share one entry; the keys after the comment are not
# systems but what the fleet sheet adds for a design (pdf_export.quickref_page).
SHARED_ENTRIES = {
    "hangar_bay": {"hangar", "launch_tube"},
    "launch_tube": {"hangar"},
    "boarding_torpedoes": {"boarding_torpedo_launcher", "boarding"},
    "boarding_torpedo_launcher": {"boarding"},
    "transporter": {"boarding"},
    "marines": {"boarding"},
    "sm_rack": {"sm_launcher", "missile_damage", "sm_magazine"},
    "sm_launcher": {"missile_damage", "sm_magazine"},
    "heavy_missile": {"sm_launcher", "missile_damage", "sm_magazine"},
    "advanced_area_screen": {"area_screen"},
    "superior_sensors": {"enhanced_sensors"},
    "weasel_cruiser": {"dummy_bogeys"},
    "weasel_capital": {"dummy_bogeys"},
    "area_ecm": {"ecm"},
    "tender_bay": {"tug_drive", "battle_riders"},
    "portal": {"jump_gate"},
    "troop_berthing": {"boarding"},
    # Not systems.
    "no_ftl": {"battle_riders", "system_defence"},
    "troop_hold": {"boarding"},
}


# (race, FB2 entry prefix, the FB2 entries every sheet of that race carries), as the FB ruleset.
ALIEN_ENTRIES = (
    ("kravak", "kv_", {"kv_thrust", "kv_crew"}),
    ("phalon", "ph_", {"ph_shell", "ph_pds"}),
    ("savasku", "sv_", {"sv_power", "sv_thrust", "sv_biomass", "sv_repair"}),
)


def _tech_base_issues(ships: list[tuple[dict, dict]], options: dict) -> list[Issue]:
    """PC pp.125-127: the technologies the fleet's live human designs use, prerequisites
    included, against the book's recommended ten choices; gunboats exclude fighters."""
    used: set[str] = set()
    for ship, design in ships:
        if ship.get("status") in ("destroyed", "hulk") or _alien(design):
            continue
        used |= techbase.design_techs(design, ship.get("loadout"), options)
    used = techbase.with_prerequisites(used)
    if not used:
        return []
    n = techbase.choices(used)
    names = ", ".join(sorted(techbase.label(t) for t in used if techbase.TECH[t][1]))
    issues = [Issue("tech_base", "info", _("Tech base: {n} technology choices ({names}).",
                                           n=n, names=names))]
    if n > techbase.LIMIT:
        issues.append(Issue("tech_base_over", "violation", _(
            "The tech base takes {n} technology choices; the limit is {limit}.",
            n=n, limit=techbase.LIMIT)))
    if used & techbase.GUNBOAT_TECHS and used & techbase.FIGHTER_TECHS:
        issues.append(Issue("gunboats_and_fighters", "violation",
                            _("An empire fielding gunboats may not also field fighters.")))
    return issues


def gunboat_label(key: str) -> str:
    return {
        "beam": _("Beam gunboats"), "plasma": _("Plasma gun gunboats"),
        "graser": _("Graser gunboats"), "gatling": _("Gatling gunboats"),
        "needle": _("Needle gunboats"), "pulse_torpedo": _("Pulse torpedo gunboats"),
        "submunition": _("Submunition gunboats"), "mkp": _("MKP gunboats"),
        "kgun": _("K-gunboats"), "missile": _("Missile gunboats"), "rocket": _("Rocket gunboats"),
        "pds": _("Point defence gunboats"), "ads": _("ADS gunboats"),
        "scatterpack": _("Scatterpack gunboats"), "plasma_bomber": _("Plasma bomber gunboats"),
    }.get(key, key)


def _is_alien(race: object) -> bool:
    return race in ALIEN_RACES


def _alien(design: dict) -> bool:
    return isinstance(design, dict) and _is_alien(design.get("race"))


def _engine(design: dict) -> ModuleType:
    """PC human rules, or the race's FB2 tech module, which PC leaves as it is."""
    return fb_tech.module_for(design.get("race")) if _alien(design) else rules


RULESET = FTPCRuleset()
