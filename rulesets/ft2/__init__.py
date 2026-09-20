"""FT2 ruleset: Full Thrust 2nd edition design system with More Thrust toggles (PLAN 6.3)."""

from __future__ import annotations

from i18n import _
from rulesets import ParamDef, QuickRefEntry, Race, SystemDef
from rulesets.ft2 import data, mt, rules


def _system_defs(options: dict) -> list[SystemDef]:
    weapons, defence, craft, special = (
        _("Weapons"),
        _("Defences"),
        _("Hangars and bays"),
        _("Special systems"),
    )
    arcs_1 = ParamDef("arcs", "arcs", _("Arcs"), ["F"], 1, 1)
    arcs_beam = ParamDef("arcs", "arcs", _("Arcs"), ["P", "F", "S"], 1, 3)
    ft = {"book": "FT", "page": 31}
    defs = [
        SystemDef(
            "beam",
            _("Beam battery"),
            weapons,
            (
                ParamDef("class", "choice", _("Class"), "B", choices=(("A", "A"), ("B", "B"), ("C", "C"))),
                arcs_beam,
            ),
            **ft,
        ),
        SystemDef("needle_beam", _("Needle beam"), weapons, (arcs_1,), **ft),
        SystemDef("pulse_torpedo", _("Pulse torpedo tube"), weapons, (arcs_1,), **ft),
        SystemDef("nova_cannon", _("Spinal-mount nova cannon"), weapons, (arcs_1,), **ft),
        SystemDef("submunition", _("Submunition pack"), weapons, (arcs_1,), **ft),
        SystemDef("pdaf", _("PDAF system"), defence, **ft),
        SystemDef("adaf", _("ADAF system"), defence, **ft),
        SystemDef("screen", _("Screen"), defence, (ParamDef("level", "int", _("Level"), 1, 1, 3),), **ft),
        SystemDef("fire_control", _("Fire control"), defence, **ft),
        SystemDef("fighter_group", _("Fighter group incl. bay"), craft, **ft),
        SystemDef("minelayer", _("Minelayer (3 mines)"), special, **ft),
        SystemDef("minesweeper", _("Minesweeper"), special, **ft),
        SystemDef("tug_drive", _("Tug/tender FTL"), special, book="FT", page=26),
    ]
    if options.get("mt_systems"):
        mt_ref = {"book": "MT", "page": 3}
        defs += [
            SystemDef("mt_missile", _("Missile (MT)"), weapons, **mt_ref),
            SystemDef("aa_battery", _("AA megabattery"), weapons, (arcs_1,), **mt_ref),
            SystemDef("wave_gun", _("Wave gun"), weapons, (arcs_1,), **mt_ref),
            SystemDef("ortillery", _("Ortillery system"), special, book="MT", page=4),
            SystemDef("reflex_field", _("Reflex field"), defence, book="MT", page=4),
            SystemDef("cloak", _("Cloaking field"), defence, book="MT", page=4),
        ]
    return defs


class FT2Ruleset:
    id = "ft2"
    accent_color = "--rs-ft2"
    books = data.BOOKS
    arcs = data.ARCS
    icon_set = "ft2"  # the icon table in ssd_layout.ICON_SETS

    @property
    def name(self) -> str:
        return _("Full Thrust 2nd ed.")

    @property
    def short_label(self) -> str:
        return "FT2"

    def races(self) -> list[Race]:
        return [Race("human", _("Human"))]

    def system_types(self, race: str, options: dict) -> list[SystemDef]:
        return _system_defs(options if isinstance(options, dict) else {}) if race == "human" else []

    design_breakdown = staticmethod(rules.design_breakdown)
    validate_design = staticmethod(rules.validate_design)
    loadout_points = staticmethod(rules.loadout_points)
    required_options = staticmethod(rules.required_options)
    damage_track = staticmethod(rules.damage_track)
    crew_factors = staticmethod(rules.crew_factors)
    cf_positions = staticmethod(rules.cf_positions)
    threshold_numbers = staticmethod(rules.threshold_numbers)
    suggest_type = staticmethod(rules.suggest_type)

    def fighter_types(self, options: dict) -> list[str]:
        return list(mt.FIGHTER_SURCHARGE) if options.get("mt_fighters") else ["standard"]

    def quickref(self, systems_present: set[str], options: dict) -> list[QuickRefEntry]:
        return []  # M9: original rulebook wording per system


RULESET = FT2Ruleset()
