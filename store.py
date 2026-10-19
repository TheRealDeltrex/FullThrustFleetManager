"""Persistence and every mutation (layer 3). Mutators return (ok: bool, msg: str).

User library under paths.user_data_dir(): designs/<id>.json, fleets/<id>.json, factions.json,
settings.json (PLAN 5.7). Catalog designs come from the bundled data/catalog/*.json, are never
written, and are read-only: editing one makes a variant.

Untrusted input: library files and imports pass through normalize_design() / normalize_fleet(),
the single place types are enforced (Frostgrave lesson: a field that slips through imports fine
and then 500s every page that shows it). Every new field goes through them.
"""

from __future__ import annotations

import io
import json
import re
import uuid
import zipfile
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

import fleet_rules
import migrations
import paths
from i18n import _
from rulesets import RULESETS, presets

STATUSES = ("ready", "damaged", "docked", "hulk", "destroyed")
EXTENSIONS = {"fleet": ".FTFleet", "design": ".FTDesign", "backup": ".FTBackup"}
DEFAULT_SETTINGS = {"paper": "A4", "pdf_viewer": "app", "theme": "admiralty", "language": "en",
                    "last_backup": None,
                    # The Design tab's faction pickers: the player's own factions are shown and
                    # other races' (Kra'Vak while designing a human ship) are not, until ticked.
                    "show_custom_factions": True, "show_other_race_factions": False}
# Appearance choices, keyed on <html data-theme> in static/style.css.
THEMES = ("admiralty", "lunar", "bridge", "carbon-armor", "night-sky", "nebula", "aurora", "asteroid")


def new_id() -> str:
    return uuid.uuid4().hex[:12]


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _dir(name: str) -> Path:
    d = paths.user_data_dir() / name
    d.mkdir(parents=True, exist_ok=True)
    return d


_SAFE_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def _safe_id(value: object) -> str | None:
    """User-file ids end up in file names; anything else is rejected."""
    return value if isinstance(value, str) and _SAFE_ID.match(value) else None


def _write_json(path: Path, doc: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def _read_json(path: Path) -> dict | None:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return doc if isinstance(doc, dict) else None


# ---- Normalisation of untrusted documents ------------------------------------------------------


def _as_int(v: object, default: int = 0, lo: int | None = None, hi: int | None = None) -> int:
    bad_float = isinstance(v, float) and not v.is_integer()
    if isinstance(v, bool) or not isinstance(v, (int, float)) or bad_float:
        v = default
    v = int(v)
    if lo is not None:
        v = max(lo, v)
    if hi is not None:
        v = min(hi, v)
    return v


def _as_str(v: object, default: str = "", limit: int = 200) -> str:
    return v[:limit] if isinstance(v, str) else default


def _as_opt_str(v: object, limit: int = 64) -> str | None:
    return v[:limit] if isinstance(v, str) and v else None


def _as_str_list(v: object) -> list[str]:
    return [x for x in v if isinstance(x, str)] if isinstance(v, list) else []


def _norm_system(s: object) -> dict | None:
    if not isinstance(s, dict) or not isinstance(s.get("type"), str) or not _safe_id(s.get("uid")):
        return None
    out = {"uid": s["uid"], "type": s["type"][:40]}
    for key, value in s.items():
        if key in out:
            continue
        if key in ("arcs", "feeds", "mounts"):
            out[key] = _as_str_list(value)
        elif key == "class":
            out[key] = value if isinstance(value, str) and len(value) == 1 else _as_int(value, 1, 1, 9)
        elif isinstance(value, bool):
            out[key] = value
        elif isinstance(value, (int, float)):
            out[key] = _as_int(value, 0, 0, 100000)
        elif isinstance(value, str):
            out[key] = value[:40]
    return out


def _norm_loadout(v: object) -> dict | None:
    if not isinstance(v, dict):
        return None
    fighters = [
        {"hangar": f["hangar"], "type": f["type"], **_fighter_extras(f)}
        for f in v.get("fighters", []) if isinstance(v.get("fighters"), list)
        if isinstance(f, dict) and isinstance(f.get("hangar"), str) and isinstance(f.get("type"), str)
    ] if isinstance(v.get("fighters"), list) else []
    magazines = [
        {"magazine": m["magazine"], "salvos": _as_str_list(m.get("salvos")),
         # Cross Dimensions multi-stage loads (CD p.25); a regular magazine carries no key.
         **({"stages": _as_int(m["stages"], 1, 1, 9)}
            if isinstance(m.get("stages"), int) and m["stages"] > 1 else {})}
        for m in v.get("magazines", [])
        if isinstance(m, dict) and isinstance(m.get("magazine"), str)
    ] if isinstance(v.get("magazines"), list) else []
    # Cross Dimensions light vessels in hangars (CD p.47), MASS of craft per entry.
    craft = [
        {"hangar": c["hangar"], "mass": _as_int(c["mass"], 1, 1, 1000)}
        for c in v.get("craft", [])
        if isinstance(c, dict) and isinstance(c.get("hangar"), str)
        and isinstance(c.get("mass"), int) and c["mass"] > 0
    ] if isinstance(v.get("craft"), list) else []
    pulsers = [
        {"pulser": x["pulser"], "mode": x["mode"][:1].upper()}
        for x in v.get("pulsers", [])
        if isinstance(x, dict) and isinstance(x.get("pulser"), str)
        and isinstance(x.get("mode"), str) and x["mode"][:1].upper() in ("L", "M", "C")
    ] if isinstance(v.get("pulsers"), list) else []
    # Project Continuum gunboat squadrons (PC pp.79-82) on a rack or in a boat bay.
    gunboats = [
        {"carrier": g["carrier"], "type": g["type"][:20],
         **({"extras": [x[:20] for x in _as_str_list(g["extras"])]}
            if _as_str_list(g.get("extras")) else {}),
         **({"ecm": _as_int(g["ecm"], 0, 0, 9)} if isinstance(g.get("ecm"), int) and g["ecm"] > 0 else {})}
        for g in v.get("gunboats", [])
        if isinstance(g, dict) and isinstance(g.get("carrier"), str) and isinstance(g.get("type"), str)
    ] if isinstance(v.get("gunboats"), list) else []
    out = {"fighters": fighters, "magazines": magazines, "pulsers": pulsers}
    if craft:
        out["craft"] = craft
    if gunboats:
        out["gunboats"] = gunboats
    return out


def _fighter_extras(f: dict) -> dict:
    """Cross Dimensions FTL/kinetic capability and swing roles (CD p.30); absent when unused, so
    the rulesets that have neither keep their entries as they were."""
    out = {}
    for key in ("extras", "swing"):
        values = [x[:20] for x in _as_str_list(f.get(key))]
        if values:
            out[key] = values
    return out


# Carrier codes folded into CVA (CVE < CVL < CVA); designs saved earlier still carry them.
_RENAMED_CLASSES = {"CV": "CVA", "CVH": "CVA"}


def normalize_design(doc: object) -> dict | None:
    """A clean design dict, or None when the document is not a usable design at all."""
    if not isinstance(doc, dict):
        return None
    doc = migrations.upgrade("design", dict(doc))
    if doc.get("ruleset") not in RULESETS or not isinstance(doc.get("id"), str) or not doc["id"]:
        return None
    source = doc.get("source") if isinstance(doc.get("source"), dict) else {}
    streamlining = doc.get("streamlining")
    streamlining = streamlining if streamlining in ("none", "partial", "full") else "none"
    kind = source.get("kind") if source.get("kind") in ("catalog", "custom", "variant") else "custom"
    clean_source = {"kind": kind}
    if kind == "variant":
        clean_source["of"] = _as_str(source.get("of"), limit=120)
    if kind == "catalog":
        clean_source.update(
            book=_as_str(source.get("book"), limit=10),
            page=_as_int(source.get("page"), 0, 0),
            npv_book=_as_int(source.get("npv_book"), 0, 0),
        )
    raw_systems = doc.get("systems") if isinstance(doc.get("systems"), list) else []
    systems = [s for s in (_norm_system(x) for x in raw_systems) if s]
    return {
        "schema_version": migrations.CURRENT,
        "id": doc["id"][:120],
        "ruleset": doc["ruleset"],
        "race": _as_str(doc.get("race"), "human", 40),
        "faction": _as_opt_str(doc.get("faction")),
        "name": _as_str(doc.get("name"), _("Unnamed design"), 80),
        "type_label": _as_str(doc.get("type_label"), limit=60),
        "type_code": _RENAMED_CLASSES.get(code := _as_str(doc.get("type_code"), limit=8), code),
        # A ruleset that knows no starbases reads one as a warship (FTCD and FTPC offer it).
        "hull_kind": (doc["hull_kind"] if doc.get("hull_kind") in ("merchant", "starbase", "section")
                      else "warship"),
        "tmf": _as_int(doc.get("tmf"), 10, 0, 10000),
        "hull_boxes": _as_int(doc.get("hull_boxes"), 0, 0, 10000),
        "armour": _as_int(doc.get("armour"), 0, 0, 10000),
        # Phalon shells stack in layers whose cost depends on the layer (FB2 p.35); every other
        # race leaves this empty and uses `armour` alone, which stays the total box count.
        "armour_layers": [_as_int(n, 0, 0, 10000) for n in doc.get("armour_layers", [])[:8]]
        if isinstance(doc.get("armour_layers"), list) else [],
        "thrust": _as_int(doc.get("thrust"), 0, 0, 20),
        "ftl": doc.get("ftl") is True,
        # Cross Dimensions tech levels (CD pp.43-44); rulesets without them ignore the flags.
        "hull_advanced": doc.get("hull_advanced") is True,
        "drive_advanced": doc.get("drive_advanced") is True,
        "ftl_advanced": doc.get("ftl_advanced") is True,
        # Project Continuum hulls (PC pp.57-58, 108): four, five or six rows, a stealth hull
        # level and regenerative armour. Other rulesets ignore them.
        "hull_rows": doc["hull_rows"] if doc.get("hull_rows") in (5, 6) else 4,
        "stealth_hull": doc["stealth_hull"] if doc.get("stealth_hull") in (1, 2) else 0,
        # A PC monster ship section's whole-ship MASS, which its drives are sized for (PC p.116).
        "ship_mass": _as_int(doc.get("ship_mass"), 0, 0, 100000),
        "armour_regen": doc.get("armour_regen") is True,
        "streamlining": streamlining,
        "systems": systems,
        "default_loadout": _norm_loadout(doc.get("default_loadout"))
        or {"fighters": [], "magazines": [], "pulsers": []},
        "allow_rule_breaking": doc.get("allow_rule_breaking") is True,
        "layout_hints": doc.get("layout_hints") if isinstance(doc.get("layout_hints"), dict) else {},
        "source": clean_source,
        "notes": _as_str(doc.get("notes"), limit=4000),
        "modified": _as_str(doc.get("modified"), limit=40),
    }


def _norm_ship(s: object) -> dict | None:
    if not isinstance(s, dict) or not _safe_id(s.get("uid")) or not isinstance(s.get("design_id"), str):
        return None
    dmg = s.get("damage") if isinstance(s.get("damage"), dict) else {}

    def counts(v: object) -> dict:
        if not isinstance(v, dict):
            return {}
        return {k: _as_int(n, 0, 0, 1000) for k, n in v.items() if isinstance(k, str)}

    return {
        "uid": s["uid"],
        "design_id": s["design_id"][:120],
        "name": _as_str(s.get("name"), limit=80),
        "table_id": _as_str(s.get("table_id"), limit=16),
        "squadron": _as_str(s.get("squadron"), limit=64),
        "status": s.get("status") if s.get("status") in STATUSES else "ready",
        "location": _as_str(s.get("location"), limit=120),
        "loadout": _norm_loadout(s.get("loadout")),
        "damage": {
            "hull": _as_int(dmg.get("hull"), 0, 0, 10000),
            "armour": _as_int(dmg.get("armour"), 0, 0, 10000),
            "systems_out": _as_str_list(dmg.get("systems_out")),
            "drive_hits": _as_int(dmg.get("drive_hits"), 0, 0, 2),
            "fighters_lost": counts(dmg.get("fighters_lost")),
            "salvos_spent": counts(dmg.get("salvos_spent")),
            "one_shot_used": _as_str_list(dmg.get("one_shot_used")),
        },
        "notes": _as_str(s.get("notes"), limit=2000),
    }


def normalize_fleet(doc: object) -> dict | None:
    if not isinstance(doc, dict):
        return None
    doc = migrations.upgrade("fleet", dict(doc))
    if doc.get("ruleset") not in RULESETS or not _safe_id(doc.get("id")):
        return None
    squadrons = [
        {"id": q["id"], "name": _as_str(q.get("name"), limit=60)}
        for q in doc.get("squadrons", []) if isinstance(q, dict) and _safe_id(q.get("id"))
    ] if isinstance(doc.get("squadrons"), list) else []
    if not squadrons:
        squadrons = [{"id": "sq1", "name": _("Main body")}]
    raw_ships = doc.get("ships") if isinstance(doc.get("ships"), list) else []
    ships = [s for s in (_norm_ship(x) for x in raw_ships) if s]
    sq_ids = {q["id"] for q in squadrons}
    for s in ships:
        if s["squadron"] not in sq_ids:
            s["squadron"] = squadrons[0]["id"]
    log = [
        {"week": _as_int(e.get("week"), 0, 0, 100000), "text": _as_str(e.get("text"), limit=1000)}
        for e in doc.get("log", []) if isinstance(e, dict)
    ] if isinstance(doc.get("log"), list) else []
    options = doc.get("options") if isinstance(doc.get("options"), dict) else {}
    limit = doc.get("points_limit")
    return {
        "schema_version": migrations.CURRENT,
        "id": doc["id"],
        "ruleset": doc["ruleset"],
        "race": _as_str(doc.get("race"), "human", 40),
        "allow_race_mixing": doc.get("allow_race_mixing") is True,
        "faction": _as_opt_str(doc.get("faction")),
        "name": _as_str(doc.get("name"), _("Unnamed fleet"), 80),
        "admiral": _as_str(doc.get("admiral"), limit=80),
        "points_limit": _as_int(limit, 0, 0, 1000000) if limit is not None else 0,
        "options": {k: options.get(k) is True for k in fleet_rules.FLEET_OPTION_KEYS},
        "dummy_bogeys": _as_int(doc.get("dummy_bogeys"), 0, 0, 1000),
        "squadrons": squadrons,
        "ships": ships,
        "campaign_id": _as_opt_str(doc.get("campaign_id")),  # reserved for the campaign module
        "log": log,
        "notes": _as_str(doc.get("notes"), limit=4000),
        "modified": _as_str(doc.get("modified"), limit=40),
    }


# ---- Catalog ------------------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _catalog() -> dict[str, dict]:
    out: dict[str, dict] = {}
    for path in sorted((paths.bundle_dir() / "data" / "catalog").glob("*.json")):
        doc = _read_json(path) or {}
        for d in doc.get("designs", []):
            clean = normalize_design(d)
            if clean:
                out[clean["id"]] = clean
    # A ruleset with no designs of its own may adopt another's (Cross Dimensions takes the Fleet
    # Book ships, CD p.3), converted by the ruleset rather than kept as a second file.
    for rs in RULESETS.values():
        for source in rs.catalog_sources:
            for d in [d for d in out.values() if d["ruleset"] == source]:
                clean = normalize_design(rs.adopt_design(json.loads(json.dumps(d))))
                if clean and clean["ruleset"] == rs.id and clean["id"] not in out:
                    out[clean["id"]] = clean
    return out


def catalog_designs(ruleset: str | None = None) -> list[dict]:
    return [dict(d) for d in _catalog().values() if ruleset in (None, d["ruleset"])]


def is_catalog(design_id: str) -> bool:
    return design_id in _catalog()


# ---- Designs -------------------------------------------------------------------------------------


def _design_path(design_id: str) -> Path | None:
    sid = _safe_id(design_id)
    return _dir("designs") / f"{sid}.json" if sid else None


def get_design(design_id: str) -> dict | None:
    """Catalog or library design (a copy; callers may mutate it)."""
    if design_id in _catalog():
        return json.loads(json.dumps(_catalog()[design_id]))
    path = _design_path(design_id)
    return normalize_design(_read_json(path)) if path and path.is_file() else None


def list_designs(ruleset: str | None = None) -> list[dict]:
    out = []
    for path in sorted(_dir("designs").glob("*.json")):
        d = normalize_design(_read_json(path))
        if d and ruleset in (None, d["ruleset"]):
            out.append(d)
    return sorted(out, key=lambda d: (d["ruleset"], d["name"].lower()))


def _write_design(design: dict) -> None:
    design["modified"] = now()
    _write_json(_design_path(design["id"]), design)


def new_design(ruleset: str, race: str = "human", faction: str | None = None,
               name: str = "", class_preset: str = "") -> tuple[dict | None, str]:
    """A fresh design; `class_preset` (a presets.preset_key value) gives it a head
    start of that class's MASS, hull, armour, thrust and fire controls."""
    rs = RULESETS.get(ruleset)
    if not rs:
        return None, _("Unknown ruleset.")
    if race not in {r.id for r in rs.races()}:
        return None, _("Unknown race for this ruleset.")
    design = normalize_design({
        "id": new_id(), "ruleset": ruleset, "race": race, "faction": faction or None,
        "name": name.strip() or _("New design"), "tmf": 50 if ruleset in ("fb", "ftcd", "ftpc") else 20,
        "hull_boxes": 15 if ruleset in ("fb", "ftcd", "ftpc") else 0, "thrust": 4, "ftl": True,
        "source": {"kind": "custom"},
    })
    preset = presets.find_preset(ruleset, class_preset)
    if preset:
        presets.apply_preset(design, preset)
        for system_type in presets.preset_systems(ruleset, race, preset):
            add_system(design, system_type)
    _write_design(design)
    return design, _("Design created.")


def make_variant(design_id: str) -> tuple[dict | None, str]:
    """A saved, editable copy. Variants of catalog classes keep the class's faction (PLAN 7)."""
    base = get_design(design_id)
    if not base:
        return None, _("Design not found.")
    variant = dict(base, id=new_id(), name=_("{name} variant", name=base["name"]))
    variant["source"] = {"kind": "variant", "of": design_id}
    _write_design(variant)
    return variant, _("Variant created.")


def design_save_issues(design: dict) -> list:
    """Violations that block saving in strict mode (checked with no MT options)."""
    return [i for i in fleet_rules.design_issues(design, {}) if i.severity == "violation"]


def save_design(design: dict, mode: str = "save",
                options: dict | None = None) -> tuple[bool, str, str | None]:
    """(ok, msg, saved id). mode: "save" (a design no ship uses, or explicit refit of all ships
    using it: "refit") or "variant" (save as a new design, ships keep the old one). Catalog
    designs cannot be saved. Strict mode: violations block the save unless allow_rule_breaking."""
    clean = normalize_design(design)
    if not clean:
        return False, _("Not a valid design."), None
    if is_catalog(clean["id"]):
        return False, _("Catalog designs are read-only; make a variant."), None
    violations = [i for i in fleet_rules.design_issues(clean, options or {}) if i.severity == "violation"]
    if violations and not clean["allow_rule_breaking"]:
        return False, _("The design breaks the rules; fix it or allow rule-breaking."), None
    used = ships_using(clean["id"])
    if mode == "variant":
        original = get_design(clean["id"])
        clean["id"] = new_id()
        clean["source"] = {"kind": "variant", "of": original["id"] if original else clean["id"]}
        _write_design(clean)
        discard_draft(original["id"] if original else clean["id"])
        return True, _("Saved as a new variant."), clean["id"]
    if used and mode != "refit":
        return False, _("{n} ships use this design: refit them or save as a variant.", n=len(used)), None
    _write_design(clean)
    discard_draft(clean["id"])
    if used:
        return True, _("Saved; {n} ships refitted.", n=len(used)), clean["id"]
    return True, _("Design saved."), clean["id"]


def ships_using(design_id: str) -> list[tuple[str, str]]:
    """[(fleet id, ship uid)] of every ship built to design_id."""
    return [(f["id"], s["uid"]) for f in list_fleets() for s in f["ships"] if s["design_id"] == design_id]


def delete_design(design_id: str) -> tuple[bool, str]:
    if is_catalog(design_id):
        return False, _("Catalog designs cannot be deleted.")
    if ships_using(design_id):
        return False, _("Ships still use this design.")
    path = _design_path(design_id)
    if not path or not path.is_file():
        return False, _("Design not found.")
    path.unlink()
    discard_draft(design_id)
    return True, _("Design deleted.")


# Design mutators: change the design dict in place; the caller saves the draft iff ok.


def add_system(design: dict, system_type: str) -> tuple[bool, str]:
    """Append a system of `system_type` with the ruleset's default parameters."""
    rs = RULESETS.get(design.get("ruleset"))
    if not rs:
        return False, _("Unknown ruleset.")
    options = {k: True for k in fleet_rules.FLEET_OPTION_KEYS}
    picker = rs.system_types(design.get("race", "human"), options)
    definition = next((s for s in picker if s.type == system_type), None)
    if not definition:
        return False, _("This ruleset has no such system.")
    uids = {s["uid"] for s in design["systems"]}
    n = len(uids) + 1
    while f"s{n}" in uids:
        n += 1
    system = {"uid": f"s{n}", "type": system_type}
    for param in definition.params:
        if param.kind == "arcs":
            # The picker's own default (a class-1 beam's six arcs, a launcher's front three),
            # so a freshly added system is legal; fore alone when it declares none.
            default = param.default
            valid = isinstance(default, list) and default and all(a in rs.arcs for a in default)
            system[param.name] = list(default) if valid else [rs.arcs[0]]
        elif param.default is not None:
            system[param.name] = param.default
    design["systems"].append(system)
    # The list sorts itself into the picker's order (its groups, then the book's order within
    # each); the sort is stable, so systems of one type keep the order they were added in.
    order = {d.type: i for i, d in enumerate(picker)}
    design["systems"].sort(key=lambda s: order.get(s.get("type"), len(order)))
    return True, _("{name} added.", name=definition.label)


def remove_system(design: dict, uid: str) -> tuple[bool, str]:
    if not any(s["uid"] == uid for s in design["systems"]):
        return False, _("System not found.")
    design["systems"] = [s for s in design["systems"] if s["uid"] != uid]
    for s in design["systems"]:  # a magazine may feed, a turret hold, the system just removed
        for key in ("feeds", "mounts"):
            if isinstance(s.get(key), list):
                s[key] = [u for u in s[key] if u != uid]
    return True, _("System removed.")


# ---- Drafts ----------------------------------------------------------------------------------
#
# The Design tab edits a draft, not the library copy: strict mode (PLAN 9.4) refuses to save a
# violating design, so the workbench has to hold changes that are not saveable yet. A draft
# lives beside the library under drafts/ and disappears on save or discard. Catalog designs are
# read-only and never get one (their ids are not safe file names either).


def _draft_path(design_id: str) -> Path | None:
    sid = _safe_id(design_id)
    return _dir("drafts") / f"{sid}.json" if sid else None


def get_draft(design_id: str) -> dict | None:
    path = _draft_path(design_id)
    return normalize_design(_read_json(path)) if path and path.is_file() else None


def save_draft(design: dict) -> tuple[bool, str]:
    clean = normalize_design(design)
    if not clean or is_catalog(clean["id"]):
        return False, _("Not a valid design.")
    path = _draft_path(clean["id"])
    if not path:
        return False, _("Not a valid design.")
    clean["modified"] = now()
    _write_json(path, clean)
    return True, ""


def discard_draft(design_id: str) -> tuple[bool, str]:
    path = _draft_path(design_id)
    if path and path.is_file():
        path.unlink()
        return True, _("Changes discarded.")
    return False, _("Nothing to discard.")


def working_design(design_id: str) -> tuple[dict | None, bool]:
    """(design, has unsaved changes): the draft if one exists, else the saved design."""
    draft = get_draft(design_id)
    if draft:
        return draft, True
    return get_design(design_id), False


# ---- Factions -------------------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _builtin_factions() -> dict:
    return (_read_json(paths.bundle_dir() / "data" / "factions.json") or {}).get("factions", {})


def builtin_factions(ruleset: str) -> list[dict]:
    return [dict(f) for f in _builtin_factions().get(ruleset, [])]


def custom_factions() -> list[dict]:
    doc = _read_json(paths.user_data_dir() / "factions.json") or {}
    doc = migrations.upgrade("factions", doc)
    out = []
    for f in doc.get("factions", []):
        if isinstance(f, dict) and _safe_id(f.get("id")):
            entry = {"id": f["id"], "name": _as_str(f.get("name"), limit=80)}
            if _safe_id(f.get("race")):
                entry["race"] = f["race"]
            out.append(entry)
    return out


def _save_custom_factions(factions: list[dict]) -> None:
    paths.user_data_dir().mkdir(parents=True, exist_ok=True)
    doc = {"schema_version": migrations.CURRENT, "factions": factions}
    _write_json(paths.user_data_dir() / "factions.json", doc)


def add_custom_faction(name: str, faction_id: str | None = None,
                       race: str | None = None) -> tuple[bool, str, str | None]:
    name = name.strip()[:80]
    if not name:
        return False, _("Enter a faction name."), None
    factions = custom_factions()
    if any(f["name"].lower() == name.lower() for f in factions):
        return False, _("That faction already exists."), None
    fid = _safe_id(faction_id) or "cf" + new_id()
    entry = {"id": fid, "name": name}
    if _safe_id(race):
        entry["race"] = race
    factions.append(entry)
    _save_custom_factions(factions)
    return True, _("Faction added."), fid


def faction_for_name(name: str, race: str | None = None) -> tuple[str | None, str]:
    """The "New faction" choice: the id of the faction called `name`, made if it is new. A name
    already taken, built-in or custom, picks that faction, so typing it twice makes no twin."""
    name = name.strip()[:80]
    if not name:
        return None, _("Enter a faction name.")
    known = [f for r in _builtin_factions() for f in builtin_factions(r)] + custom_factions()
    for f in known:
        if f["name"].lower() == name.lower() or f["id"].lower() == name.lower():
            return f["id"], ""
    _ok, msg, fid = add_custom_faction(name, race=race)
    return fid, msg


def faction_choices(ruleset: str | None = None, keep: str | None = None) -> list[dict]:
    """What a faction picker offers: the ruleset's built-in factions (every ruleset's, once each,
    when none is named), then the custom ones that have at least one saved design. ``keep`` is
    the value already chosen; it stays on the list even when it is not offered any more, so
    saving a form does not drop it. Each choice says whether it is custom and which races it
    belongs to (a custom faction's own race plus its ships'), for the pickers' show/hide toggles."""
    rulesets = [ruleset] if ruleset else list(_builtin_factions())
    custom = custom_factions()
    ship_races: dict[str, set[str]] = {}
    if custom:
        for d in list_designs():
            if d.get("faction"):
                ship_races.setdefault(d["faction"], set()).add(d.get("race") or "human")
    choices: list[dict] = []
    for f in [f for r in rulesets for f in builtin_factions(r)]:
        if not any(c["id"] == f["id"] for c in choices):
            choices.append({"id": f["id"], "name": f["name"], "custom": False,
                            "races": [f.get("race") or "human"]})
    for f in custom:
        if any(c["id"] == f["id"] for c in choices) or (f["id"] not in ship_races and f["id"] != keep):
            continue
        races = ship_races.get(f["id"], set()) | ({f["race"]} if f.get("race") else set())
        choices.append({"id": f["id"], "name": f["name"], "custom": True, "races": sorted(races)})
    if keep and not any(c["id"] == keep for c in choices):
        choices.append({"id": keep, "name": faction_name(keep), "custom": True, "races": []})
    return choices


def faction_name(faction_id: str | None, ruleset: str | None = None) -> str:
    if not faction_id:
        return ""
    known = builtin_factions(ruleset) if ruleset else [
        f for r in _builtin_factions() for f in builtin_factions(r)
    ]
    for f in known:
        if f["id"] == faction_id:
            return f["name"]
    for f in custom_factions():
        if f["id"] == faction_id:
            return f["name"]
    return faction_id


# ---- Fleets ---------------------------------------------------------------------------------------


def _fleet_path(fleet_id: str) -> Path | None:
    sid = _safe_id(fleet_id)
    return _dir("fleets") / f"{sid}.json" if sid else None


def get_fleet(fleet_id: str) -> dict | None:
    path = _fleet_path(fleet_id)
    return normalize_fleet(_read_json(path)) if path and path.is_file() else None


def list_fleets() -> list[dict]:
    out = [f for f in (normalize_fleet(_read_json(p)) for p in sorted(_dir("fleets").glob("*.json"))) if f]
    return sorted(out, key=lambda f: (f["ruleset"], f["name"].lower()))


def save_fleet(fleet: dict) -> tuple[bool, str]:
    clean = normalize_fleet(fleet)
    if not clean:
        return False, _("Not a valid fleet.")
    clean["modified"] = now()
    _write_json(_fleet_path(clean["id"]), clean)
    fleet.clear()
    fleet.update(clean)
    return True, ""


def create_fleet(ruleset: str, name: str, race: str = "human", faction: str | None = None,
                 points_limit: int = 0, allow_race_mixing: bool = False, admiral: str = "",
                 options: dict | None = None) -> tuple[dict | None, str]:
    rs = RULESETS.get(ruleset)
    if not rs:
        return None, _("Unknown ruleset.")
    if race not in {r.id for r in rs.races()}:
        return None, _("Unknown race for this ruleset.")
    fleet = normalize_fleet({
        "id": new_id(), "ruleset": ruleset, "race": race, "faction": faction or None,
        "name": name.strip() or _("New fleet"), "admiral": admiral, "points_limit": points_limit,
        "allow_race_mixing": allow_race_mixing, "options": options or {},
        "squadrons": [{"id": "sq1", "name": _("Main body")}],
    })
    save_fleet(fleet)
    return fleet, _("Fleet created.")


def delete_fleet(fleet_id: str) -> tuple[bool, str]:
    path = _fleet_path(fleet_id)
    if not path or not path.is_file():
        return False, _("Fleet not found.")
    path.unlink()
    return True, _("Fleet deleted.")


def designs_for_fleet(fleet: dict) -> dict[str, dict]:
    out = {}
    for s in fleet.get("ships", []):
        if s["design_id"] not in out:
            d = get_design(s["design_id"])
            if d:
                out[s["design_id"]] = d
    return out


# Fleet mutators: operate on a fleet dict in place; the caller saves iff ok.


def update_fleet_details(fleet: dict, *, name: str | None = None, admiral: str | None = None,
                         faction: str | None = "", points_limit: int | None = None,
                         allow_race_mixing: bool | None = None, options: dict | None = None,
                         notes: str | None = None,
                         dummy_bogeys: int | None = None) -> tuple[bool, str]:
    if name is not None:
        if not name.strip():
            return False, _("Enter a fleet name.")
        fleet["name"] = name.strip()[:80]
    if admiral is not None:
        fleet["admiral"] = admiral.strip()[:80]
    if faction != "":
        fleet["faction"] = faction or None
    if points_limit is not None:
        if points_limit < 0:
            return False, _("The points limit cannot be negative.")
        fleet["points_limit"] = points_limit
    if allow_race_mixing is not None:
        fleet["allow_race_mixing"] = allow_race_mixing
    if options is not None:
        fleet["options"] = {k: bool(options.get(k)) for k in fleet_rules.FLEET_OPTION_KEYS}
    if notes is not None:
        fleet["notes"] = notes[:4000]
    if dummy_bogeys is not None:
        if dummy_bogeys < 0:
            return False, _("The number of dummy bogeys cannot be negative.")
        fleet["dummy_bogeys"] = min(dummy_bogeys, 1000)
    return True, _("Fleet updated.")


def add_squadron(fleet: dict, name: str) -> tuple[bool, str]:
    name = name.strip()[:60]
    if not name:
        return False, _("Enter a squadron name.")
    ids = {q["id"] for q in fleet["squadrons"]}
    n = len(ids) + 1
    while f"sq{n}" in ids:
        n += 1
    fleet["squadrons"].append({"id": f"sq{n}", "name": name})
    return True, _("Squadron added.")


def rename_squadron(fleet: dict, squadron_id: str, name: str) -> tuple[bool, str]:
    q = next((q for q in fleet["squadrons"] if q["id"] == squadron_id), None)
    if not q or not name.strip():
        return False, _("Squadron not found.") if not q else _("Enter a squadron name.")
    q["name"] = name.strip()[:60]
    return True, _("Squadron renamed.")


def move_squadron(fleet: dict, squadron_id: str, delta: int) -> tuple[bool, str]:
    sq = fleet["squadrons"]
    i = next((i for i, q in enumerate(sq) if q["id"] == squadron_id), None)
    if i is None:
        return False, _("Squadron not found.")
    j = max(0, min(len(sq) - 1, i + delta))
    sq.insert(j, sq.pop(i))
    return True, ""


def remove_squadron(fleet: dict, squadron_id: str) -> tuple[bool, str]:
    if len(fleet["squadrons"]) <= 1:
        return False, _("A fleet keeps at least one squadron.")
    if not any(q["id"] == squadron_id for q in fleet["squadrons"]):
        return False, _("Squadron not found.")
    fleet["squadrons"] = [q for q in fleet["squadrons"] if q["id"] != squadron_id]
    for s in fleet["ships"]:
        if s["squadron"] == squadron_id:
            s["squadron"] = fleet["squadrons"][0]["id"]
    return True, _("Squadron removed; its ships moved to {name}.", name=fleet["squadrons"][0]["name"])


def _table_id_taken(fleet: dict, table_id: str, except_uid: str = "") -> bool:
    """Table IDs name ships on the table, so they are unique within a fleet (case-insensitive)."""
    key = table_id.strip()[:16].lower()
    return any(s["table_id"].lower() == key for s in fleet["ships"] if s["uid"] != except_uid)


def suggest_table_id(fleet: dict, type_code: str) -> str:
    """CE-1, CE-2, ... from the design's type code (PLAN 9.3)."""
    code = type_code or "S"
    used = {s["table_id"] for s in fleet["ships"]}
    n = 1
    while f"{code}-{n}" in used:
        n += 1
    return f"{code}-{n}"


def add_ship(fleet: dict, design_id: str, name: str = "", table_id: str = "", squadron: str = "",
             loadout: dict | None = None) -> tuple[bool, str]:
    design = get_design(design_id)
    if not design:
        return False, _("Design not found.")
    if design["ruleset"] != fleet["ruleset"]:
        return False, _("That design belongs to another ruleset.")
    if table_id.strip() and _table_id_taken(fleet, table_id):
        return False, _("Another ship in this fleet already has the ID {id}.", id=table_id.strip()[:16])
    sq_ids = [q["id"] for q in fleet["squadrons"]]
    uids = {s["uid"] for s in fleet["ships"]}
    n = len(uids) + 1
    while f"sh{n}" in uids:
        n += 1
    fleet["ships"].append({
        "uid": f"sh{n}", "design_id": design_id,
        "name": name.strip()[:80] or design["name"],
        "table_id": table_id.strip()[:16] or suggest_table_id(fleet, design["type_code"]),
        "squadron": squadron if squadron in sq_ids else sq_ids[0],
        "status": "ready", "location": "", "loadout": _norm_loadout(loadout),
        "damage": {"hull": 0, "armour": 0, "systems_out": [], "drive_hits": 0,
                   "fighters_lost": {}, "salvos_spent": {}, "one_shot_used": []},
        "notes": "",
    })
    return True, _("{name} added.", name=fleet["ships"][-1]["name"])


def _ship(fleet: dict, uid: str) -> dict | None:
    return next((s for s in fleet["ships"] if s["uid"] == uid), None)


def remove_ship(fleet: dict, uid: str) -> tuple[bool, str]:
    if not _ship(fleet, uid):
        return False, _("Ship not found.")
    fleet["ships"] = [s for s in fleet["ships"] if s["uid"] != uid]
    return True, _("Ship removed.")


def update_ship(fleet: dict, uid: str, *, name: str | None = None, table_id: str | None = None,
                squadron: str | None = None, status: str | None = None, location: str | None = None,
                notes: str | None = None) -> tuple[bool, str]:
    ship = _ship(fleet, uid)
    if not ship:
        return False, _("Ship not found.")
    if table_id is not None and table_id.strip() and _table_id_taken(fleet, table_id, uid):
        return False, _("Another ship in this fleet already has the ID {id}.", id=table_id.strip()[:16])
    if status is not None:
        if status not in STATUSES:
            return False, _("Unknown status.")
        ship["status"] = status
    if squadron is not None:
        if squadron not in {q["id"] for q in fleet["squadrons"]}:
            return False, _("Squadron not found.")
        ship["squadron"] = squadron
    if name is not None and name.strip():
        ship["name"] = name.strip()[:80]
    if table_id is not None and table_id.strip():
        ship["table_id"] = table_id.strip()[:16]
    if location is not None:
        ship["location"] = location[:120]
    if notes is not None:
        ship["notes"] = notes[:2000]
    return True, _("Ship updated.")


def set_ship_loadout(fleet: dict, uid: str, loadout: dict | None) -> tuple[bool, str]:
    """None restores the design default."""
    ship = _ship(fleet, uid)
    if not ship:
        return False, _("Ship not found.")
    ship["loadout"] = _norm_loadout(loadout)
    return True, _("Loadout updated.")


def set_ship_damage(fleet: dict, uid: str, *, hull: int | None = None, armour: int | None = None,
                    drive_hits: int | None = None, systems_out: list[str] | None = None,
                    fighters_lost: dict | None = None, salvos_spent: dict | None = None,
                    one_shot_used: list[str] | None = None) -> tuple[bool, str]:
    """Campaign damage (PLAN 9.5). Clamped to what the design actually has."""
    ship = _ship(fleet, uid)
    if not ship:
        return False, _("Ship not found.")
    design = get_design(ship["design_id"])
    damage = ship["damage"]
    if hull is not None:
        damage["hull"] = max(0, min(int(hull), fleet_rules.hull_boxes(design) or int(hull)))
    if armour is not None:
        damage["armour"] = max(0, min(int(armour), (design or {}).get("armour", 0)))
    if drive_hits is not None:
        damage["drive_hits"] = max(0, min(2, int(drive_hits)))
    if systems_out is not None:
        known = {s["uid"] for s in (design or {}).get("systems", [])}
        damage["systems_out"] = [u for u in systems_out if u in known]
    if fighters_lost is not None:
        damage["fighters_lost"] = {k: max(0, int(v)) for k, v in fighters_lost.items()}
    if salvos_spent is not None:
        damage["salvos_spent"] = {k: max(0, int(v)) for k, v in salvos_spent.items()}
    if one_shot_used is not None:
        damage["one_shot_used"] = list(one_shot_used)
    return True, _("Damage recorded.")


def toggle_system_out(fleet: dict, uid: str, system_uid: str) -> tuple[bool, str]:
    """Clicking a system on the SSD knocks it out or brings it back."""
    ship = _ship(fleet, uid)
    if not ship:
        return False, _("Ship not found.")
    out = ship["damage"]["systems_out"]
    if system_uid in out:
        out.remove(system_uid)
        return True, _("System restored.")
    design = get_design(ship["design_id"])
    if system_uid not in {s["uid"] for s in (design or {}).get("systems", [])}:
        return False, _("System not found.")
    out.append(system_uid)
    return True, _("System knocked out.")


def repair_ship(fleet: dict, uid: str, plan: dict) -> tuple[bool, str]:
    """Apply a week of repairs computed by fleet_rules.repair_plan()."""
    ship = _ship(fleet, uid)
    if not ship:
        return False, _("Ship not found.")
    damage = ship["damage"]
    damage["hull"] = max(0, damage["hull"] - int(plan.get("hull") or 0))
    damage["drive_hits"] = max(0, damage["drive_hits"] - int(plan.get("drive_hits") or 0))
    fixed = set(plan.get("systems") or [])
    damage["systems_out"] = [u for u in damage["systems_out"] if u not in fixed]
    return True, _("{hull} damage points and {n} systems repaired.",
                   hull=int(plan.get("hull") or 0), n=len(fixed))


def replenish_ship(fleet: dict, uid: str) -> tuple[bool, str]:
    """A week at a base restocks fighters, salvos and one-shot systems in full (FT p.35)."""
    ship = _ship(fleet, uid)
    if not ship:
        return False, _("Ship not found.")
    ship["damage"].update(fighters_lost={}, salvos_spent={}, one_shot_used=[])
    return True, _("Ship replenished.")


def add_log_entry(fleet: dict, week: int, text: str) -> tuple[bool, str]:
    if not text.strip():
        return False, _("Enter a log entry.")
    fleet["log"].append({"week": max(0, week), "text": text.strip()[:1000]})
    return True, _("Log entry added.")


# ---- Settings -------------------------------------------------------------------------------------


def load_settings() -> dict:
    doc = migrations.upgrade("settings", _read_json(paths.user_data_dir() / "settings.json") or {})
    out = dict(DEFAULT_SETTINGS)
    if doc.get("paper") in ("A4", "Letter"):
        out["paper"] = doc["paper"]
    if doc.get("pdf_viewer") in ("app", "system"):
        out["pdf_viewer"] = doc["pdf_viewer"]
    if doc.get("theme") in THEMES:
        out["theme"] = doc["theme"]
    if isinstance(doc.get("language"), str):
        out["language"] = doc["language"]
    if isinstance(doc.get("last_backup"), str):
        out["last_backup"] = doc["last_backup"]
    for key in ("show_custom_factions", "show_other_race_factions"):
        if isinstance(doc.get(key), bool):
            out[key] = doc[key]
    return out


def save_settings(**changes) -> tuple[bool, str]:
    settings = load_settings()
    settings.update({k: v for k, v in changes.items() if k in DEFAULT_SETTINGS})
    paths.user_data_dir().mkdir(parents=True, exist_ok=True)
    _write_json(paths.user_data_dir() / "settings.json", {"schema_version": migrations.CURRENT, **settings})
    return True, _("Settings saved.")


# ---- Export / import (PLAN 5.6) --------------------------------------------------------------------


def _filename(name: str, ext: str) -> str:
    base = re.sub(r"[^A-Za-z0-9 ._-]+", "", name).strip().replace(" ", "_") or "export"
    return base[:60] + ext


def _factions_used(designs: list[dict], fleet: dict | None = None) -> list[dict]:
    wanted = {d["faction"] for d in designs} | ({fleet["faction"]} if fleet else set())
    return [f for f in custom_factions() if f["id"] in wanted]


def export_fleet(fleet_id: str) -> tuple[str, str] | None:
    """(filename, JSON text): the fleet, every non-catalog design it uses, its custom factions."""
    fleet = get_fleet(fleet_id)
    if not fleet:
        return None
    designs = [d for d in designs_for_fleet(fleet).values() if not is_catalog(d["id"])]
    doc = {"schema_version": migrations.CURRENT, "kind": "FTFleet", "fleet": fleet,
           "designs": designs, "factions": _factions_used(designs, fleet)}
    return _filename(fleet["name"], EXTENSIONS["fleet"]), json.dumps(doc, indent=1, ensure_ascii=False)


def export_design(design_id: str) -> tuple[str, str] | None:
    design = get_design(design_id)
    if not design:
        return None
    doc = {"schema_version": migrations.CURRENT, "kind": "FTDesign", "design": design,
           "factions": _factions_used([design])}
    return _filename(design["name"], EXTENSIONS["design"]), json.dumps(doc, indent=1, ensure_ascii=False)


def export_backup() -> tuple[str, bytes]:
    """A zip of the whole library; records the time for the web build's backup reminder."""
    buf = io.BytesIO()
    root = paths.user_data_dir()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for sub in ("designs", "fleets"):
            for p in sorted(_dir(sub).glob("*.json")):
                z.write(p, f"{sub}/{p.name}")
        for name in ("factions.json", "settings.json"):
            if (root / name).is_file():
                z.write(root / name, name)
    save_settings(last_backup=now())
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return f"FleetManager_backup_{stamp}{EXTENSIONS['backup']}", buf.getvalue()


def _newer(local: dict | None, incoming: dict) -> bool:
    """True if a local copy exists and is newer than the incoming one (ISO strings compare)."""
    return bool(local) and (local.get("modified") or "") > (incoming.get("modified") or "")


def import_file(filename: str, data: bytes, overwrite_newer: bool = False) -> tuple[bool, str, list[str]]:
    """Import an .FTFleet / .FTDesign / .FTBackup. Returns (ok, msg, conflicts): conflicts are
    names of items skipped because the local copy is newer; call again with overwrite_newer=True
    after the player confirms (PLAN 5.6)."""
    if data[:2] == b"PK":
        return _import_backup(data, overwrite_newer)
    try:
        doc = json.loads(data.decode("utf-8-sig"))
    except (UnicodeDecodeError, ValueError):
        return False, _("Not a Fleet Manager file."), []
    if not isinstance(doc, dict):
        return False, _("Not a Fleet Manager file."), []
    try:
        migrations.upgrade("fleet", {"schema_version": doc.get("schema_version")})
    except migrations.TooNewError:
        return False, _("This file comes from a newer version of the app."), []
    for f in doc.get("factions", []) if isinstance(doc.get("factions"), list) else []:
        if isinstance(f, dict) and _safe_id(f.get("id")) and isinstance(f.get("name"), str):
            if not any(c["id"] == f["id"] for c in custom_factions()):
                add_custom_faction(f["name"], f["id"], f.get("race"))
    kind = doc.get("kind")
    if kind == "FTDesign":
        design = normalize_design(doc.get("design"))
        if not design or is_catalog(design["id"]) or not _safe_id(design["id"]):
            return False, _("The file holds no usable design."), []
        return _import_designs([design], overwrite_newer)
    if kind == "FTFleet":
        fleet = normalize_fleet(doc.get("fleet"))
        if not fleet:
            return False, _("The file holds no usable fleet."), []
        raw = doc.get("designs") if isinstance(doc.get("designs"), list) else []
        designs = [d for d in (normalize_design(x) for x in raw) if d]
        designs = [d for d in designs if _safe_id(d["id"]) and not is_catalog(d["id"])]
        known = {d["id"] for d in designs} | set(_catalog()) | {d["id"] for d in list_designs()}
        missing = {s["design_id"] for s in fleet["ships"]} - known
        if missing:
            names = ", ".join(sorted(missing))
            return False, _("The fleet uses designs that are not in the file: {ids}.", ids=names), []
        if any(d["ruleset"] != fleet["ruleset"] for d in designs):
            return False, _("The file mixes designs of another ruleset into the fleet."), []
        ok, msg, conflicts = _import_designs(designs, overwrite_newer, quiet=True)
        local = get_fleet(fleet["id"])
        if _newer(local, fleet) and not overwrite_newer:
            conflicts.append(fleet["name"])
        else:
            _write_json(_fleet_path(fleet["id"]), fleet)
        if conflicts:
            return True, _("Imported; {n} newer local copies kept.", n=len(conflicts)), conflicts
        return True, _("Fleet {name} imported.", name=fleet["name"]), []
    return False, _("Not a Fleet Manager file."), []


def _import_designs(designs: list[dict], overwrite_newer: bool,
                    quiet: bool = False) -> tuple[bool, str, list[str]]:
    conflicts = []
    for d in designs:
        if _newer(get_design(d["id"]), d) and not overwrite_newer:
            conflicts.append(d["name"])
            continue
        _write_json(_design_path(d["id"]), d)
    if quiet or len(designs) != 1:
        return True, _("{n} designs imported.", n=len(designs) - len(conflicts)), conflicts
    if conflicts:
        return True, _("Kept the newer local copy of {name}.", name=conflicts[0]), conflicts
    return True, _("Design {name} imported.", name=designs[0]["name"]), []


def _import_backup(data: bytes, overwrite_newer: bool) -> tuple[bool, str, list[str]]:
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        return False, _("Not a Fleet Manager backup."), []
    conflicts: list[str] = []
    n = 0
    with z:
        names = z.namelist()
        if "factions.json" in names:
            doc = json.loads(z.read("factions.json").decode("utf-8"))
            for f in doc.get("factions", []) if isinstance(doc, dict) else []:
                if isinstance(f, dict) and _safe_id(f.get("id")) and isinstance(f.get("name"), str):
                    if not any(c["id"] == f["id"] for c in custom_factions()):
                        add_custom_faction(f["name"], f["id"], f.get("race"))
        for name in names:
            m = re.fullmatch(r"(designs|fleets)/([A-Za-z0-9_-]{1,64})\.json", name)
            if not m:
                continue
            try:
                raw = json.loads(z.read(name).decode("utf-8"))
            except ValueError:
                continue
            if m.group(1) == "designs":
                doc = normalize_design(raw)
                if not doc or is_catalog(doc["id"]):
                    continue
                local, path = get_design(doc["id"]), _design_path(doc["id"])
            else:
                doc = normalize_fleet(raw)
                if not doc:
                    continue
                local, path = get_fleet(doc["id"]), _fleet_path(doc["id"])
            if _newer(local, doc) and not overwrite_newer:
                conflicts.append(doc["name"])
                continue
            _write_json(path, doc)
            n += 1
    if n == 0 and not conflicts:
        return False, _("The backup is empty."), []
    return True, _("{n} items restored from the backup.", n=n), conflicts
