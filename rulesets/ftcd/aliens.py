"""FTCD ruleset, the Fleet Book 2 races (CD p.21, section 5.12: "Alien technologies").

Cross Dimensions has no alien design system of its own: it takes the Fleet Book 2 races as they
are and lists what changes. Most of that is how their weapons meet advanced screens and armour,
which is play, not design; the quick reference carries it. What changes a design:

- Kra'Vak scatterguns follow the CD scattergun rules and cost 4 points, not 5;
- Kra'Vak scatterguns no longer give area defence, so the Si'Tek "or similar ships should
  exchange one K-1 gun for an ADFC": Kra'Vak ships may carry an ADFC (2 MASS, 8 points, CD p.45);
- Kra'Vak fighters pay the kinetic extra (+6 a group, CD pp.30, 47) on top of their FB2 price.

Sa'Vasku and Phalon designs cost what FB2 says. The CPV fleet option prices every hull the same
way (CD p.58), so it reaches alien hulls too. Everything else is the race's FB2 tech module.
"""

from __future__ import annotations

from types import ModuleType

from i18n import _
from rulesets import Breakdown, BreakdownRow, Issue, Race, SystemDef
from rulesets.fb import kravak
from rulesets.fb import tech as fb_tech
from rulesets.ftcd import data
from rulesets.ftcd import rules as cd_rules

RACE_IDS = ("kravak", "savasku", "phalon")

KV_SCATTERGUN_POINTS = 4  # CD p.21
ADFC_MASS, ADFC_POINTS = 2, 8  # CD p.45, as for human ships


def races() -> list[Race]:
    return [r for r in fb_tech.races() if r.id in RACE_IDS]


def is_alien(race: object) -> bool:
    return race in RACE_IDS


def module_for(race: str) -> ModuleType:
    return fb_tech.module_for(race)


def system_defs(race: str) -> list[SystemDef]:
    defs = module_for(race).system_defs()
    if race == "kravak":
        scattergun = next((i for i, d in enumerate(defs) if d.type == "scattergun"), len(defs) - 1)
        defs.insert(scattergun + 1, SystemDef("adfc", _("Area-defence fire control"),
                                              defs[scattergun].group, book="CD", page=21))
    return defs


def design_breakdown(design: dict, options: dict) -> Breakdown:
    b = module_for(design.get("race")).design_breakdown(design, options)
    kv = design.get("race") == "kravak"
    rows = []
    for row in b.rows:
        if row.key == "hull":
            row = BreakdownRow(row.key, row.label, row.mass,
                               cd_rules.hull_cost(b.derived.get("tmf", 0), options), row.system_uid)
        elif kv and row.key == "scattergun":
            row = BreakdownRow(row.key, row.label, row.mass, KV_SCATTERGUN_POINTS, row.system_uid)
        elif kv and row.key == "adfc":
            row = BreakdownRow(row.key, _("Area-defence fire control"), ADFC_MASS, ADFC_POINTS,
                               row.system_uid)
        rows.append(row)
    return Breakdown(tuple(rows), sum(r.mass for r in rows), sum(r.points for r in rows),
                     b.derived)


def validate_design(design: dict, options: dict) -> list[Issue]:
    issues = module_for(design.get("race")).validate_design(design, options)
    if design.get("race") != "kravak":
        return issues
    # FB2 knows no Kra'Vak ADFC: it calls one a foreign system and leaves its 2 MASS out of the
    # total. Judge both here with the CD breakdown instead.
    adfcs = {s.get("uid") for s in cd_rules._systems(design) if s.get("type") == "adfc"}
    issues = [i for i in issues if i.code not in ("mass_over", "mass_under")
              and not (i.code == "race_system" and i.system_uid in adfcs)]
    tmf = cd_rules._int(design.get("tmf"))
    used = design_breakdown(design, options).mass_used
    if used > tmf:
        issues.insert(0, Issue("mass_over", "violation", _(
            "MASS used ({used}) exceeds the total MASS ({tmf}).", used=used, tmf=tmf)))
    elif used < tmf:
        # A violation, as in the FB2 Kra'Vak checks.
        issues.insert(0, Issue("mass_under", "violation", _(
            "MASS used ({used}) is less than the total MASS ({tmf}).", used=used, tmf=tmf)))
    return issues


def loadout_points(design: dict, loadout: dict | None, options: dict) -> int:
    module = module_for(design.get("race"))
    points = module.loadout_points(design, loadout, options)
    if design.get("race") == "kravak":
        if loadout is None:
            loadout = design.get("default_loadout")
        groups = [f for f in cd_rules._entries(loadout, "fighters")
                  if f.get("type") in kravak.FIGHTER_POINTS]
        points += data.FIGHTER_EXTRAS["kinetic"] * len(groups)
    return points


# ---- Adopting the FB2 catalog ---------------------------------------------------------------


def adopt(design: dict) -> list[str]:
    """Change an FB2 catalog design in place for Cross Dimensions; returns what changed, one
    sentence each, for the design's notes. Plain English like the rest of the catalog data,
    which is read once and cached."""
    changes: list[str] = []
    if design.get("race") != "kravak":
        return changes
    systems = cd_rules._systems(design)
    scatterguns = sum(1 for s in systems if s.get("type") == "scattergun")
    if scatterguns:
        noun = "scattergun" if scatterguns == 1 else "scatterguns"
        changes.append(f"{scatterguns} {noun} at 4 points instead of 5 (CD p.21).")
    if design.get("name") == "Si'Tek":
        k1 = next((s for s in systems if s.get("type") == "kgun" and cd_rules._int(s.get("class"), 1) == 1),
                  None)
        if k1 is not None:
            for key in [k for k in k1 if k != "uid"]:
                del k1[key]
            k1["type"] = "adfc"
            changes.append("One K-1 gun exchanged for an ADFC, as CD p.21 says for the Si'Tek.")
    groups = len(cd_rules._entries(design.get("default_loadout"), "fighters"))
    if groups:
        changes.append("Fighter groups pay +6 each for kinetic weapons (CD p.21).")
    return changes
