"""Persistence and every mutation (layer 3). Mutators return (ok: bool, msg: str).

User library under paths.user_data_dir(): designs/<id>.json, fleets/<id>.json,
campaigns/<id>.json, factions.json, settings.json (PLAN 5.7). Catalog designs come from the
bundled data/catalog/*.json, are never written, and are read-only: editing one makes a variant.

Untrusted input: library files and imports pass through normalize_design() / normalize_fleet(),
the single place types are enforced (Frostgrave lesson: a field that slips through imports fine
and then 500s every page that shows it). Every new field goes through them.
"""

from __future__ import annotations

import base64
import io
import json
import math
import random
import re
import uuid
import zipfile
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

import fleet_rules
import migrations
import paths
import portraits
import starmap
from i18n import _
from rulesets import RULESETS, presets

STATUSES = ("ready", "damaged", "docked", "hulk", "destroyed")
EXTENSIONS = {"fleet": ".FTFleet", "design": ".FTDesign", "campaign": ".FTCampaign",
              "starmap": ".FTStarmap", "backup": ".FTBackup"}
DEFAULT_SETTINGS = {"paper": "A4", "pdf_viewer": "app", "theme": "full-thrust", "language": "en",
                    # True once the player picks a look; see load_settings.
                    "theme_chosen": False,
                    "last_backup": None,
                    # The web build's backup reminder, put off for a while by "Later" (PLAN 5.7).
                    "backup_snoozed": None,
                    # The Design tab's faction pickers: the player's own factions are shown and
                    # other races' (Kra'Vak while designing a human ship) are not, until ticked.
                    "show_custom_factions": True, "show_other_race_factions": False}
# Appearance choices, keyed on <html data-theme> in static/style.css.
THEMES = ("admiralty", "lunar", "bridge", "carbon-armor", "night-sky", "nebula", "aurora", "asteroid",
          "orbital-foundry", "celestial-archive", "full-thrust")


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
        {"carrier": g["carrier"], **_norm_gunboats(g)}
        for g in v.get("gunboats", [])
        if isinstance(g, dict) and isinstance(g.get("carrier"), str) and isinstance(g.get("type"), str)
    ] if isinstance(v.get("gunboats"), list) else []
    out = {"fighters": fighters, "magazines": magazines, "pulsers": pulsers}
    if craft:
        out["craft"] = craft
    if gunboats:
        out["gunboats"] = gunboats
    return out


def _norm_gunboats(g: dict) -> dict:
    """One gunboat squadron (PC pp.79-82): its type, the six boats' types when it mixes them
    (p.79), the squadron's modifications and ECM level."""
    out: dict = {"type": g["type"][:20]}
    types = g.get("types")
    if (isinstance(types, list) and len(types) == 6 and all(isinstance(t, str) for t in types)
            and len(set(types)) > 1):
        out["types"] = [t[:20] for t in types]
    if _as_str_list(g.get("extras")):
        out["extras"] = [x[:20] for x in _as_str_list(g["extras"])]
    if isinstance(g.get("ecm"), int) and g["ecm"] > 0:
        out["ecm"] = _as_int(g["ecm"], 0, 0, 9)
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


def _norm_layout_hints(v: object) -> dict:
    """uid -> {"x", "y"}: a pinned system's place on the sheet, in points. Anything that is not
    a pair of finite numbers in a sane range is dropped, so a hint can never break a drawing."""
    out: dict = {}
    for uid, hint in (v.items() if isinstance(v, dict) else ()):
        if not isinstance(uid, str) or not isinstance(hint, dict):
            continue
        xy = [hint.get("x"), hint.get("y")]
        if all(isinstance(n, (int, float)) and not isinstance(n, bool) and math.isfinite(n)
               and -10000 <= n <= 10000 for n in xy):
            out[uid[:120]] = {"x": xy[0], "y": xy[1]}
    return out


# Carrier codes folded into CVA (CVE < CVL < CVA); designs saved earlier still carry them.
_RENAMED_CLASSES = {"CV": "CVA", "CVH": "CVA"}


def normalize_design(doc: object) -> dict | None:
    """A clean design dict, or None when the document is not a usable design at all."""
    if not isinstance(doc, dict):
        return None
    doc = migrations.upgrade("design", dict(doc))
    if (not isinstance(doc.get("ruleset"), str) or doc["ruleset"] not in RULESETS
            or not isinstance(doc.get("id"), str) or not doc["id"]):
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
        url = source.get("url")
        # A catalog design printed on a web page links to it; only plain https links are kept.
        if isinstance(url, str) and url.startswith("https://") and len(url) <= 200 and not any(
                c.isspace() or c in "\"'<>" for c in url):
            clean_source["url"] = url
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
        # Hull rows: Project Continuum's four, five or six (PC p.108), and the three to six the
        # Star Ranger catalog designs print under FB. Each ruleset reads only the counts it knows.
        "hull_rows": doc["hull_rows"] if doc.get("hull_rows") in (3, 5, 6) else 4,
        "stealth_hull": doc["stealth_hull"] if doc.get("stealth_hull") in (1, 2) else 0,
        # A PC monster ship section's whole-ship MASS, which its drives are sized for (PC p.116).
        "ship_mass": _as_int(doc.get("ship_mass"), 0, 0, 100000),
        "armour_regen": doc.get("armour_regen") is True,
        "streamlining": streamlining,
        "systems": systems,
        "default_loadout": _norm_loadout(doc.get("default_loadout"))
        or {"fighters": [], "magazines": [], "pulsers": []},
        "allow_rule_breaking": doc.get("allow_rule_breaking") is True,
        "layout_hints": _norm_layout_hints(doc.get("layout_hints")),
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
    if (not isinstance(doc.get("ruleset"), str) or doc["ruleset"] not in RULESETS
            or not _safe_id(doc.get("id"))):
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
        # FTL gunboat squadrons flying without a carrier (PC p.80).
        "gunboat_squadrons": [
            {"uid": g["uid"][:20], **_norm_gunboats(g)}
            for g in doc.get("gunboat_squadrons", [])
            if isinstance(g, dict) and isinstance(g.get("uid"), str) and isinstance(g.get("type"), str)
        ][:100] if isinstance(doc.get("gunboat_squadrons"), list) else [],
        "squadrons": squadrons,
        "ships": ships,
        # The campaign the fleet fights in and its side there (PLAN 11.3); one campaign at a time.
        "campaign_id": _as_opt_str(doc.get("campaign_id")),
        "campaign_side": (_as_opt_str(doc.get("campaign_side"))
                          if _as_opt_str(doc.get("campaign_id")) else None),
        "log": log,
        "notes": _as_str(doc.get("notes"), limit=4000),
        "modified": _as_str(doc.get("modified"), limit=40),
    }


# ---- Catalog ------------------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _catalog() -> dict[str, dict]:
    raw: dict[str, dict] = {}
    for path in sorted((paths.bundle_dir() / "data" / "catalog").glob("*.json")):
        doc = _read_json(path) or {}
        for d in doc.get("designs", []):
            clean = normalize_design(d)
            if clean:
                raw[clean["id"]] = clean
    # A design from outside its ruleset's books (the Star Ranger pages) is listed there only when
    # that ruleset's own rules make it legal; the rest still feed the adopting rulesets below.
    out = {i: d for i, d in raw.items()
           if d["ruleset"] in RULESETS and _adoptable(RULESETS[d["ruleset"]], RULESETS[d["ruleset"]], d)}
    # A ruleset with no designs of its own may adopt another's (Cross Dimensions takes the Fleet
    # Book ships, CD p.3), converted by the ruleset rather than kept as a second file.
    for rs in RULESETS.values():
        for source in rs.catalog_sources:
            for d in [d for d in raw.values() if d["ruleset"] == source]:
                clean = normalize_design(rs.adopt_design(json.loads(json.dumps(d))))
                if (clean and clean["ruleset"] == rs.id and clean["id"] not in out
                        and _adoptable(RULESETS[source], rs, clean)):
                    out[clean["id"]] = clean
    return out


def _adoptable(source, rs, design: dict) -> bool:
    """A rulebook design is always adopted. One from outside the source ruleset's books (the
    Star Ranger pages) only when it is legal unchanged, since it may use systems or rules the
    adopting ruleset lacks (the Fleet Books and Cross Dimensions are closed; owner's ruling)."""
    if design["source"].get("book") in {b.code for b in source.books}:
        return True
    opts = {o: True for o in rs.required_options(design, None)}
    return not any(i.severity == "violation" for i in rs.validate_design(design, opts))


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
    """Violations that block saving in strict mode (the design alone, without a fleet's options)."""
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
        "allow_race_mixing": allow_race_mixing,
        "options": fleet_rules.default_options(ruleset) if options is None else options,
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


def add_gunboat_squadron(fleet: dict, kind: str) -> tuple[bool, str]:
    """An FTL gunboat squadron the fleet fields without a carrier (PC p.80)."""
    rs = RULESETS.get(fleet["ruleset"])
    if kind not in dict(getattr(rs, "gunboat_types", ())):
        return False, _("Choose a gunboat type.")
    taken = {g["uid"] for g in fleet["gunboat_squadrons"]}
    uid = next(f"g{n}" for n in range(1, len(taken) + 2) if f"g{n}" not in taken)
    fleet["gunboat_squadrons"].append({"uid": uid, "type": kind})
    return True, _("Gunboat squadron added.")


def update_gunboat_squadrons(fleet: dict, squadrons: dict[str, dict]) -> tuple[bool, str]:
    """Replaces each listed squadron's type, boats, modifications and ECM, keyed by uid."""
    for i, old in enumerate(fleet["gunboat_squadrons"]):
        if old["uid"] in squadrons:
            fleet["gunboat_squadrons"][i] = {"uid": old["uid"], **_norm_gunboats(squadrons[old["uid"]])}
    return True, _("Gunboat squadrons updated.")


def remove_gunboat_squadron(fleet: dict, uid: str) -> tuple[bool, str]:
    before = len(fleet["gunboat_squadrons"])
    fleet["gunboat_squadrons"] = [g for g in fleet["gunboat_squadrons"] if g["uid"] != uid]
    if len(fleet["gunboat_squadrons"]) == before:
        return False, _("No such gunboat squadron.")
    return True, _("Gunboat squadron removed.")


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


def order_squadron(fleet: dict, squadron_id: str, uids: list[str]) -> tuple[bool, str]:
    """Puts the listed ships in this squadron in that order; a ship dragged in from another
    squadron joins it. Ships not listed keep their places."""
    if squadron_id not in {q["id"] for q in fleet["squadrons"]}:
        return False, _("Squadron not found.")
    by_uid = {s["uid"]: s for s in fleet["ships"]}
    picked = [by_uid[u] for u in dict.fromkeys(uids) if u in by_uid]
    if not picked:
        return False, _("Ship not found.")
    moved = {s["uid"] for s in picked}
    ships = fleet["ships"]
    # The squadron's block starts where its first ship (listed or not) stood.
    first = next(i for i, s in enumerate(ships) if s["uid"] in moved or s["squadron"] == squadron_id)
    rest = [s for s in ships if s["uid"] not in moved]
    at = sum(1 for s in ships[:first] if s["uid"] not in moved)
    for s in picked:
        s["squadron"] = squadron_id
    fleet["ships"] = rest[:at] + picked + rest[at:]
    return True, ""


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


# ---- Campaigns (PLAN 11.3) ------------------------------------------------------------------------
# A campaign groups fleets of one ruleset into sides and counts the weeks (FT p.35: a map turn is
# about a week). Membership lives on the fleet (campaign_id, campaign_side), so a fleet is in one
# campaign at a time and deleting a fleet needs no campaign edit.

MAX_SIDES = 8


def _default_sides() -> list[dict]:
    return [{"id": "blue", "name": _("Blue")}, {"id": "red", "name": _("Red")}]


def normalize_campaign(doc: object) -> dict | None:
    if not isinstance(doc, dict):
        return None
    doc = migrations.upgrade("campaign", dict(doc))
    if (not isinstance(doc.get("ruleset"), str) or doc["ruleset"] not in RULESETS
            or not _safe_id(doc.get("id"))):
        return None
    sides, seen = [], set()
    for side in doc.get("sides", []) if isinstance(doc.get("sides"), list) else []:
        if isinstance(side, dict) and _safe_id(side.get("id")) and side["id"] not in seen:
            seen.add(side["id"])
            sides.append({"id": side["id"], "name": _as_str(side.get("name"), side["id"], 40)})
    log = [
        {"week": _as_int(e.get("week"), 0, 0, 100000), "text": _as_str(e.get("text"), limit=1000)}
        for e in doc.get("log", []) if isinstance(e, dict)
    ] if isinstance(doc.get("log"), list) else []
    return {
        "schema_version": migrations.CURRENT,
        "id": doc["id"],
        "ruleset": doc["ruleset"],
        "name": _as_str(doc.get("name"), _("Unnamed campaign"), 80),
        "week": _as_int(doc.get("week"), 1, 1, 100000),
        "sides": sides[:MAX_SIDES] if len(sides) >= 2 else _default_sides(),
        "log": log,
        "map": (grid := normalize_starmap(doc.get("map"), {s["id"] for s in sides})),
        "forces": _norm_forces(doc.get("forces"), {s["id"] for s in sides}, grid),
        "contacts": _norm_contacts(doc.get("contacts"), {s["id"] for s in sides}, grid),
        "notes": _as_str(doc.get("notes"), limit=4000),
        "modified": _as_str(doc.get("modified"), limit=40),
    }


def normalize_starmap(doc: object, side_ids: set[str]) -> dict | None:
    """A campaign's star map (starmap.py), or None. Systems off the grid or on a taken hex are
    dropped; an owner that is not a side of this campaign reads as unowned."""
    if not isinstance(doc, dict):
        return None
    out = starmap.blank(_as_int(doc.get("width"), starmap.DEFAULT_WIDTH),
                        _as_int(doc.get("height"), starmap.DEFAULT_HEIGHT))
    seed = doc.get("seed")
    whole = isinstance(seed, int) and not isinstance(seed, bool)
    out["seed"] = _as_int(seed, 0, 0, 2**31 - 1) if whole else None
    taken = set()
    for s in doc.get("systems", []) if isinstance(doc.get("systems"), list) else []:
        if not isinstance(s, dict):
            continue
        q, r = _as_int(s.get("q"), -1), _as_int(s.get("r"), -1)
        if not (0 <= q < out["width"] and 0 <= r < out["height"]) or (q, r) in taken:
            continue
        taken.add((q, r))
        out["systems"].append({
            "q": q, "r": r,
            "name": _as_str(s.get("name"), starmap.hex_label(q, r), 40),
            "kind": s.get("kind") if s.get("kind") in starmap.KINDS else "settled",
            "owner": s.get("owner") if s.get("owner") in side_ids else "",
            "base": s.get("base") is True,
        })
    out["systems"].sort(key=lambda s: (s["q"], s["r"]))
    return out


MAX_FORCES = 200


def _norm_forces(raw: object, side_ids: set[str], grid: dict | None) -> list[dict]:
    """Task forces (step C3): a side's ships travelling together, sitting on a hex of the map,
    with this week's order (a hex to jump to, or None). A ship is in one force at most; a force
    needs a map, and one off the map or of an unknown side is dropped."""
    if not grid or not isinstance(raw, list):
        return []
    out, seen_ids, seen_ships = [], set(), set()
    for f in raw[:MAX_FORCES]:
        if not isinstance(f, dict) or not _safe_id(f.get("id")) or f["id"] in seen_ids:
            continue
        q, r = _as_int(f.get("q"), -1), _as_int(f.get("r"), -1)
        if f.get("side") not in side_ids or not (0 <= q < grid["width"] and 0 <= r < grid["height"]):
            continue
        order = f.get("order")
        if (isinstance(order, list) and len(order) == 2
                and 0 <= _as_int(order[0], -1) < grid["width"]
                and 0 <= _as_int(order[1], -1) < grid["height"]):
            order = [_as_int(order[0]), _as_int(order[1])]
        else:
            order = None
        ships = []
        for ref in f.get("ships", []) if isinstance(f.get("ships"), list) else []:
            if isinstance(ref, dict) and _safe_id(ref.get("fleet")) and _safe_id(ref.get("uid")):
                key = (ref["fleet"], ref["uid"])
                if key not in seen_ships:
                    seen_ships.add(key)
                    ships.append({"fleet": ref["fleet"], "uid": ref["uid"]})
        seen_ids.add(f["id"])
        out.append({"id": f["id"], "side": f["side"], "name": _as_str(f.get("name"), f["id"], 40),
                    "q": q, "r": r, "order": order, "ships": ships})
    return out


MAX_CONTACTS = 500
CONTACT_OUTCOMES = ("", "battle", "standoff", "leave", "escaped")


def _norm_contacts(raw: object, side_ids: set[str], grid: dict | None) -> list[dict]:
    """Contacts (step C4): sides meeting in a system at the end of a week (FT pp.34-35). Each
    side's scan report as the others see it, its choice, the catch roll, the outcome with the
    sides that must leave, and a battle's result (a side id, or "drawn")."""
    if not grid or not isinstance(raw, list):
        return []
    out, seen = [], set()
    for c in raw[-MAX_CONTACTS:]:
        if not isinstance(c, dict) or not _safe_id(c.get("id")) or c["id"] in seen:
            continue
        q, r = _as_int(c.get("q"), -1), _as_int(c.get("r"), -1)
        sides = [s for s in c.get("sides", []) if s in side_ids] if isinstance(c.get("sides"), list) else []
        if len(set(sides)) < 2 or not (0 <= q < grid["width"] and 0 <= r < grid["height"]):
            continue
        sides = list(dict.fromkeys(sides))
        reports = c.get("reports") if isinstance(c.get("reports"), dict) else {}
        choices = c.get("choices") if isinstance(c.get("choices"), dict) else {}
        leaving = c.get("leaving") if isinstance(c.get("leaving"), list) else []
        roll = c.get("roll")
        outcome = c.get("outcome") if c.get("outcome") in CONTACT_OUTCOMES else ""
        result = c.get("result") if c.get("result") in (*sides, "drawn") else ""
        before = c.get("owner_before") if isinstance(c.get("owner_before"), str) else None
        seen.add(c["id"])
        out.append({
            "id": c["id"], "week": _as_int(c.get("week"), 1, 1, 100000), "q": q, "r": r,
            "sides": sides,
            "reports": {s: {k: _as_int((reports.get(s) or {}).get(k) if isinstance(reports.get(s), dict)
                                       else 0, 0, 0, 999) for k in fleet_rules.SCAN_CLASSES}
                        for s in sides},
            "choices": {s: choices.get(s) if choices.get(s) in fleet_rules.CONTACT_CHOICES else ""
                        for s in sides},
            "roll": _as_int(roll, 0, 1, 6) if isinstance(roll, int) and not isinstance(roll, bool) else None,
            "outcome": outcome, "leaving": [s for s in sides if s in leaving] if outcome else [],
            "result": result if outcome == "battle" else "",
            "owner_before": before if before in (*side_ids, "") else None,
            "notes": _as_str(c.get("notes"), limit=2000),
        })
    return out


def _campaign_path(campaign_id: str) -> Path | None:
    sid = _safe_id(campaign_id)
    return _dir("campaigns") / f"{sid}.json" if sid else None


def get_campaign(campaign_id: str | None) -> dict | None:
    path = _campaign_path(campaign_id) if campaign_id else None
    return normalize_campaign(_read_json(path)) if path and path.is_file() else None


def list_campaigns(ruleset: str | None = None) -> list[dict]:
    out = [c for c in (normalize_campaign(_read_json(p)) for p in sorted(_dir("campaigns").glob("*.json")))
           if c and (ruleset is None or c["ruleset"] == ruleset)]
    return sorted(out, key=lambda c: c["name"].lower())


def save_campaign(campaign: dict) -> tuple[bool, str]:
    clean = normalize_campaign(campaign)
    if not clean:
        return False, _("Not a valid campaign.")
    clean["modified"] = now()
    _write_json(_campaign_path(clean["id"]), clean)
    campaign.clear()
    campaign.update(clean)
    return True, ""


def campaign_fleets(campaign_id: str) -> list[dict]:
    return [f for f in list_fleets() if f["campaign_id"] == campaign_id]


def create_campaign(fleet: dict, name: str) -> tuple[dict | None, str]:
    """A new campaign in the fleet's ruleset, with the fleet on its first side."""
    campaign = normalize_campaign({"id": new_id(), "ruleset": fleet["ruleset"],
                                   "name": name.strip() or _("New campaign")})
    save_campaign(campaign)
    fleet["campaign_id"], fleet["campaign_side"] = campaign["id"], campaign["sides"][0]["id"]
    return campaign, _("Campaign created.")


def join_campaign(fleet: dict, campaign_id: str, side_id: str) -> tuple[bool, str]:
    campaign = get_campaign(campaign_id)
    if not campaign:
        return False, _("Campaign not found.")
    if campaign["ruleset"] != fleet["ruleset"]:
        return False, _("That campaign uses another ruleset.")
    if side_id not in {s["id"] for s in campaign["sides"]}:
        return False, _("Side not found.")
    fleet["campaign_id"], fleet["campaign_side"] = campaign_id, side_id
    return True, _("Fleet joined {name}.", name=campaign["name"])


def leave_campaign(fleet: dict) -> tuple[bool, str]:
    if not fleet.get("campaign_id"):
        return False, _("The fleet is in no campaign.")
    fleet["campaign_id"] = fleet["campaign_side"] = None
    return True, _("Fleet left the campaign.")


def update_campaign(campaign: dict, *, name: str | None = None, week: int | None = None,
                    notes: str | None = None, sides: dict[str, str] | None = None) -> tuple[bool, str]:
    if name is not None:
        campaign["name"] = name.strip()[:80] or campaign["name"]
    if week is not None:
        campaign["week"] = max(1, week)
    if notes is not None:
        campaign["notes"] = notes[:4000]
    for side in campaign["sides"]:
        if sides and (sides.get(side["id"]) or "").strip():
            side["name"] = sides[side["id"]].strip()[:40]
    return True, _("Campaign updated.")


def _force(campaign: dict, force_id: str) -> dict | None:
    return next((f for f in campaign["forces"] if f["id"] == force_id), None)


def force_ships(campaign: dict, force: dict,
                fleets: dict[str, dict] | None = None) -> list[tuple[dict, dict, dict | None]]:
    """(fleet, ship, design) for each ship of the force that still exists in a campaign fleet."""
    if fleets is None:
        fleets = {f["id"]: f for f in campaign_fleets(campaign["id"])}
    out = []
    for ref in force["ships"]:
        fleet = fleets.get(ref["fleet"])
        ship = _ship(fleet, ref["uid"]) if fleet else None
        if ship:
            out.append((fleet, ship, get_design(ship["design_id"])))
    return out


def add_force(campaign: dict, side: str, name: str, q: int, r: int) -> tuple[dict | None, str]:
    grid = campaign.get("map")
    if not grid or not starmap.system_at(grid, q, r):
        return None, _("Pick a star system for the task force.")
    if side not in {s["id"] for s in campaign["sides"]}:
        return None, _("Side not found.")
    if len(campaign["forces"]) >= MAX_FORCES:
        return None, _("A campaign has at most {n} task forces.", n=MAX_FORCES)
    taken = {f["id"] for f in campaign["forces"]}
    n = len(taken) + 1
    while f"tf{n}" in taken:
        n += 1
    force = {"id": f"tf{n}", "side": side, "name": name.strip()[:40] or _("Task force {n}", n=n),
             "q": q, "r": r, "order": None, "ships": []}
    campaign["forces"].append(force)
    return force, _("Task force added.")


def rename_force(campaign: dict, force_id: str, name: str) -> tuple[bool, str]:
    force = _force(campaign, force_id)
    if not force:
        return False, _("Task force not found.")
    force["name"] = name.strip()[:40] or force["name"]
    return True, _("Task force renamed.")


def remove_force(campaign: dict, force_id: str) -> tuple[bool, str]:
    force = _force(campaign, force_id)
    if not force:
        return False, _("Task force not found.")
    campaign["forces"].remove(force)
    return True, _("Task force disbanded.")


def assign_ships(campaign: dict, force_id: str, fleet: dict, uids: list[str]) -> tuple[bool, str]:
    """Moves the fleet's chosen ships into the force, out of any other. Only a fleet of the
    force's side may join it, and a ship joins where the force is."""
    force = _force(campaign, force_id)
    if not force:
        return False, _("Task force not found.")
    if fleet.get("campaign_id") != campaign["id"] or fleet.get("campaign_side") != force["side"]:
        return False, _("Only ships of the force's side can join it.")
    picked = [uid for uid in uids if _ship(fleet, uid)]
    if not picked:
        return False, _("Tick the ships to add.")
    for other in campaign["forces"]:
        other["ships"] = [x for x in other["ships"] if not (x["fleet"] == fleet["id"] and x["uid"] in picked)]
    force["ships"] += [{"fleet": fleet["id"], "uid": uid} for uid in picked]
    return True, _("{n} ships joined {name}.", n=len(picked), name=force["name"])


def unassign_ship(campaign: dict, force_id: str, fleet_id: str, uid: str) -> tuple[bool, str]:
    force = _force(campaign, force_id)
    if not force:
        return False, _("Task force not found.")
    before = len(force["ships"])
    force["ships"] = [x for x in force["ships"] if not (x["fleet"] == fleet_id and x["uid"] == uid)]
    return len(force["ships"]) < before, _("Ship left the task force.")


def reachable_systems(campaign: dict, force: dict) -> tuple[list[tuple[dict, int]], str]:
    """(systems the force can jump to this week with their distance, why none)."""
    reach, why = fleet_rules.force_reach(
        [(ship, design) for _f, ship, design in force_ships(campaign, force)])
    here = (force["q"], force["r"])
    systems = [(s, starmap.hex_distance(here, (s["q"], s["r"]))) for s in campaign["map"]["systems"]]
    return sorted([(s, d) for s, d in systems if 0 < d <= reach], key=lambda x: (x[1], x[0]["name"])), why


def set_force_order(campaign: dict, force_id: str, dest: tuple[int, int] | None) -> tuple[bool, str]:
    force = _force(campaign, force_id)
    if not force:
        return False, _("Task force not found.")
    if dest is None or dest == (force["q"], force["r"]):
        force["order"] = None
        return True, _("{name} holds position.", name=force["name"])
    options, why = reachable_systems(campaign, force)
    target = next((s for s, _d in options if (s["q"], s["r"]) == tuple(dest)), None)
    if not target:
        return False, why or _("Out of reach: a task force jumps up to {n} hexes a week.",
                               n=fleet_rules.FTL_HEXES_PER_WEEK)
    force["order"] = [target["q"], target["r"]]
    return True, _("{name} jumps to {dest}.", name=force["name"], dest=target["name"])


def meetings(campaign: dict) -> list[tuple[dict, list[dict]]]:
    """Systems where forces of two or more sides sit, with those forces (FT p.35)."""
    grid = campaign.get("map")
    out = []
    for system in grid["systems"] if grid else []:
        here = [f for f in campaign["forces"]
                if (f["q"], f["r"]) == (system["q"], system["r"]) and f["ships"]]
        if len({f["side"] for f in here}) > 1:
            out.append((system, here))
    return out


def this_weeks_contacts(campaign: dict) -> list[dict]:
    return [c for c in campaign["contacts"] if c["week"] == campaign["week"]]


def _contact(campaign: dict, contact_id: str) -> dict | None:
    return next((c for c in this_weeks_contacts(campaign) if c["id"] == contact_id), None)


def _contact_system(campaign: dict, contact: dict) -> dict | None:
    return starmap.system_at(campaign["map"], contact["q"], contact["r"]) if campaign["map"] else None


def _contact_place(campaign: dict, contact: dict) -> str:
    system = _contact_system(campaign, contact)
    return system["name"] if system else starmap.hex_label(contact["q"], contact["r"])


def _side_name(campaign: dict, side: str) -> str:
    return next((s["name"] for s in campaign["sides"] if s["id"] == side), side)


def contact_forces(campaign: dict, contact: dict) -> list[dict]:
    """The task forces of the contact's sides in its system now."""
    return [f for f in campaign["forces"]
            if (f["q"], f["r"]) == (contact["q"], contact["r"]) and f["side"] in contact["sides"]]


def _open_contact(campaign: dict, system: dict, forces: list[dict], fleets: dict[str, dict]) -> dict:
    """A new contact for this week, each side's report starting as what its scan really shows."""
    taken = {c["id"] for c in campaign["contacts"]}
    n = len(taken) + 1
    while f"k{n}" in taken:
        n += 1
    sides = list(dict.fromkeys(f["side"] for f in forces))
    reports = {side: fleet_rules.scan_counts(
        [(ship, design) for force in forces if force["side"] == side
         for _f, ship, design in force_ships(campaign, force, fleets)]) for side in sides}
    contact = {"id": f"k{n}", "week": campaign["week"], "q": system["q"], "r": system["r"],
               "sides": sides, "reports": reports, "choices": dict.fromkeys(sides, ""), "roll": None,
               "outcome": "", "leaving": [], "result": "", "owner_before": None, "notes": ""}
    campaign["contacts"] = (campaign["contacts"] + [contact])[-MAX_CONTACTS:]
    return contact


def set_contact_report(campaign: dict, contact_id: str, side: str,
                       counts: dict[str, int]) -> tuple[bool, str]:
    """What a side's scan shows the others: the real count by default, changed by decoy drones
    and weasel boats (FT pp.21-22, 34)."""
    contact = _contact(campaign, contact_id)
    if not contact or side not in contact["sides"]:
        return False, _("Contact not found.")
    if contact["outcome"]:
        return False, _("The sides have already chosen.")
    contact["reports"][side] = {k: max(0, min(999, int(counts.get(k) or 0)))
                                for k in fleet_rules.SCAN_CLASSES}
    return True, _("Scan report updated.")


def _claim(campaign: dict, contact: dict, side: str) -> str:
    """The system goes to the side left holding it (an app rule; FT p.36 calls it superiority).
    A bare star has nothing to hold. Returns the text for the log."""
    system = _contact_system(campaign, contact)
    if not system or system["kind"] == "empty" or system["owner"] == side:
        return ""
    contact["owner_before"] = system["owner"]
    system["owner"] = side
    return " " + _("{system} is now held by {side}.", system=system["name"], side=_side_name(campaign, side))


def set_contact_choice(campaign: dict, contact_id: str, side: str, choice: str,
                       roll: int | None = None) -> tuple[bool, str]:
    """A side's choice (FT p.35). The last one in reveals them all and settles the contact,
    rolling the catch roll unless the players rolled it themselves (`roll`)."""
    contact = _contact(campaign, contact_id)
    if not contact or side not in contact["sides"]:
        return False, _("Contact not found.")
    if contact["outcome"]:
        return False, _("The sides have already chosen.")
    if choice not in fleet_rules.CONTACT_CHOICES:
        return False, _("Choose fight, withdraw or stand off.")
    contact["choices"][side] = choice
    if not all(contact["choices"].values()):
        return True, _("Choice made.")
    if fleet_rules.catch_roll_needed(contact["choices"]):
        contact["roll"] = roll if roll in range(1, 7) else random.randint(1, 6)
    outcome, leaving = fleet_rules.contact_outcome(contact["choices"], contact["roll"])
    contact["outcome"], contact["leaving"] = outcome, leaving
    where = _contact_place(campaign, contact)
    if outcome == "standoff":
        text = _("{system}: stand off.", system=where)
    elif outcome == "leave":
        text = _("{system}: no battle, every side leaves.", system=where)
    elif outcome == "escaped":
        stays = next(s for s in contact["sides"] if s not in leaving)
        text = _("{system}: {sides} got away (catch roll {roll}).", system=where, roll=contact["roll"],
                 sides=", ".join(_side_name(campaign, s) for s in leaving))
        text += _claim(campaign, contact, stays)
    elif contact["roll"]:
        text = _("{system}: battle (catch roll {roll}).", system=where, roll=contact["roll"])
    else:
        text = _("{system}: battle.", system=where)
    campaign["log"].append({"week": campaign["week"], "text": text})
    return True, text


def set_battle_result(campaign: dict, contact_id: str, result: str, notes: str = "") -> tuple[bool, str]:
    """The winning side holds the system and the others must leave it (an app rule), or "drawn":
    the battle was broken off and nobody claims the system (FT p.35)."""
    contact = _contact(campaign, contact_id)
    if not contact or contact["outcome"] != "battle":
        return False, _("Contact not found.")
    if contact["result"]:
        return False, _("The battle is already recorded.")
    if result not in (*contact["sides"], "drawn"):
        return False, _("Choose who won.")
    contact["result"], contact["notes"] = result, notes.strip()[:2000]
    where = _contact_place(campaign, contact)
    if result == "drawn":
        text = _("{system}: battle broken off.", system=where)
    else:
        contact["leaving"] = [s for s in contact["sides"] if s != result]
        text = _("{system}: battle won by {side}.", system=where, side=_side_name(campaign, result))
        text += _claim(campaign, contact, result)
    campaign["log"].append({"week": campaign["week"], "text": text})
    return True, text


def reopen_contact(campaign: dict, contact_id: str) -> tuple[bool, str]:
    """Clears this week's choices and result, and gives the system back."""
    contact = _contact(campaign, contact_id)
    if not contact:
        return False, _("Contact not found.")
    system = _contact_system(campaign, contact)
    if system and contact["owner_before"] is not None:
        system["owner"] = contact["owner_before"]
    contact.update(choices=dict.fromkeys(contact["sides"], ""), roll=None, outcome="", leaving=[],
                   result="", owner_before=None)
    return True, _("Contact reopened.")


def next_week(campaign: dict) -> tuple[bool, str]:
    """Every force carries out its order, the week advances, ships' locations follow their force,
    and each system where sides meet goes into the campaign log."""
    fleets = {f["id"]: f for f in campaign_fleets(campaign["id"])}
    for contact in this_weeks_contacts(campaign):
        where = _contact_place(campaign, contact)
        if not contact["outcome"]:
            return False, _("Settle the contact at {system} first.", system=where)
        if contact["outcome"] == "battle" and not contact["result"]:
            return False, _("Record the battle at {system} first.", system=where)
        for force in campaign["forces"]:
            if (force in contact_forces(campaign, contact) and force["side"] in contact["leaving"]
                    and not force["order"] and reachable_systems(campaign, force)[0]):
                return False, _("{name} must leave {system} this week.", name=force["name"], system=where)
    moved = False
    for force in campaign["forces"]:
        if force["order"]:
            force["q"], force["r"] = force["order"]
            force["order"] = None
            moved = True
    campaign["week"] += 1
    touched = set()
    for force in campaign["forces"]:
        system = starmap.system_at(campaign["map"], force["q"], force["r"]) if campaign["map"] else None
        where = system["name"] if system else starmap.hex_label(force["q"], force["r"])
        for fleet, ship, _design in force_ships(campaign, force, fleets):
            if ship["location"] != where:
                ship["location"] = where
                touched.add(fleet["id"])
    for fleet_id in touched:
        save_fleet(fleets[fleet_id])
    names = {s["id"]: s["name"] for s in campaign["sides"]}
    found = meetings(campaign)
    for system, forces in found:
        text = _("Contact at {system}: {forces}.", system=system["name"],
                 forces=", ".join(f"{f['name']} ({names[f['side']]})" for f in forces))
        campaign["log"].append({"week": campaign["week"], "text": text})
        _open_contact(campaign, system, forces, fleets)
    if found:
        return True, _("Week {n}: contact at {systems}.", n=campaign["week"],
                       systems=", ".join(system["name"] for system, _f in found))
    return True, _("Week {n}.", n=campaign["week"]) if not moved else _("Week {n}: task forces moved.",
                                                                          n=campaign["week"])


def add_side(campaign: dict, name: str) -> tuple[bool, str]:
    if len(campaign["sides"]) >= MAX_SIDES:
        return False, _("A campaign has at most {n} sides.", n=MAX_SIDES)
    taken = {s["id"] for s in campaign["sides"]}
    n = len(taken) + 1
    while f"side{n}" in taken:
        n += 1
    campaign["sides"].append({"id": f"side{n}", "name": name.strip()[:40] or _("Side {n}", n=n)})
    return True, _("Side added.")


def remove_side(campaign: dict, side_id: str) -> tuple[bool, str]:
    if side_id not in {s["id"] for s in campaign["sides"]}:
        return False, _("Side not found.")
    if len(campaign["sides"]) <= 2:
        return False, _("A campaign needs two sides.")
    if any(f["campaign_side"] == side_id for f in campaign_fleets(campaign["id"])):
        return False, _("Move that side's fleets first.")
    campaign["sides"] = [s for s in campaign["sides"] if s["id"] != side_id]
    return True, _("Side removed.")


def add_campaign_log(campaign: dict, week: int, text: str) -> tuple[bool, str]:
    return add_log_entry(campaign, week, text)


def new_starmap(campaign: dict, width: int, height: int) -> tuple[bool, str]:
    campaign["map"] = starmap.blank(width, height)
    campaign["forces"] = []
    campaign["contacts"] = []
    return True, _("Blank star map ready: click a hex to add a system.")


def random_starmap(campaign: dict, width: int, height: int, stars: int,
                   seed: int | None = None) -> tuple[bool, str]:
    if seed is None:
        seed = random.randrange(1, 1_000_000)
    campaign["map"] = starmap.generate(width, height, max(1, min(stars, 400)),
                                       [s["id"] for s in campaign["sides"]], seed)
    campaign["forces"] = []
    campaign["contacts"] = []
    placed = len(campaign["map"]["systems"])
    if placed < stars:
        return True, _("Only {n} stars fit on a map this size (seed {seed}).", n=placed, seed=seed)
    return True, _("Random star map, seed {seed}.", seed=seed)


def set_star_system(campaign: dict, q: int, r: int, *, name: str, kind: str, owner: str,
                    base: bool) -> tuple[bool, str]:
    """Adds the system on hex (q, r) or changes the one there."""
    grid = campaign.get("map")
    if not grid or not (0 <= q < grid["width"] and 0 <= r < grid["height"]):
        return False, _("That hex is not on the map.")
    system = starmap.system_at(grid, q, r)
    added = system is None
    if added:
        system = {"q": q, "r": r}
        grid["systems"].append(system)
    system.update(name=name.strip()[:40] or starmap.unused_name(grid), base=base,
                  kind=kind if kind in starmap.KINDS else "settled",
                  owner=owner if owner in {s["id"] for s in campaign["sides"]} else "")
    return True, _("System added.") if added else _("System updated.")


def remove_star_system(campaign: dict, q: int, r: int) -> tuple[bool, str]:
    grid = campaign.get("map")
    system = starmap.system_at(grid, q, r) if grid else None
    if not system:
        return False, _("No system on that hex.")
    if any((f["q"], f["r"]) == (q, r) for f in campaign["forces"]):
        return False, _("Move the task forces there first.")
    grid["systems"].remove(system)
    return True, _("System removed.")


def export_starmap(campaign_id: str) -> tuple[str, str] | None:
    campaign = get_campaign(campaign_id)
    if not campaign or not campaign["map"]:
        return None
    doc = {"schema_version": migrations.CURRENT, "kind": "FTStarmap", "map": campaign["map"],
           "sides": campaign["sides"]}
    name = _filename(campaign["name"] + " map", EXTENSIONS["starmap"])
    return name, json.dumps(doc, indent=1, ensure_ascii=False)


def import_starmap(campaign: dict, data: bytes) -> tuple[bool, str]:
    """Replaces the campaign's map with an .FTStarmap. Owners follow the file's sides by
    position, so a map shared from another campaign keeps who holds what."""
    try:
        doc = json.loads(data.decode("utf-8-sig"))
    except (UnicodeDecodeError, ValueError):
        doc = None
    if not isinstance(doc, dict) or doc.get("kind") != "FTStarmap":
        return False, _("Not a star map file.")
    try:
        migrations.upgrade("campaign", {"schema_version": doc.get("schema_version")})
    except migrations.TooNewError:
        return False, _("This file comes from a newer version of the app.")
    theirs = [s.get("id") for s in doc.get("sides", []) if isinstance(s, dict)] \
        if isinstance(doc.get("sides"), list) else []
    ours = [s["id"] for s in campaign["sides"]]
    rename = dict(zip(theirs, ours))
    raw = doc.get("map")
    if isinstance(raw, dict) and isinstance(raw.get("systems"), list):
        raw = dict(raw, systems=[dict(s, owner=rename.get(s.get("owner"), "")) if isinstance(s, dict) else s
                                 for s in raw["systems"]])
    grid = normalize_starmap(raw, set(ours))
    if not grid:
        return False, _("Not a star map file.")
    campaign["map"] = grid
    campaign["forces"] = []
    campaign["contacts"] = []
    return True, _("Star map loaded: {n} systems.", n=len(grid["systems"]))


def delete_campaign(campaign_id: str) -> tuple[bool, str]:
    """The fleets stay, out of any campaign."""
    path = _campaign_path(campaign_id)
    if not path or not path.is_file():
        return False, _("Campaign not found.")
    for fleet in campaign_fleets(campaign_id):
        leave_campaign(fleet)
        save_fleet(fleet)
    path.unlink()
    return True, _("Campaign deleted.")


# ---- Settings -------------------------------------------------------------------------------------


def load_settings() -> dict:
    doc = migrations.upgrade("settings", _read_json(paths.user_data_dir() / "settings.json") or {})
    out = dict(DEFAULT_SETTINGS)
    if doc.get("paper") in ("A4", "Letter"):
        out["paper"] = doc["paper"]
    if doc.get("pdf_viewer") in ("app", "system"):
        out["pdf_viewer"] = doc["pdf_viewer"]
    # Admiralty was the default before Full Thrust, and every save wrote the whole settings
    # file, so a stored "admiralty" without theme_chosen is the old default, not a choice.
    if isinstance(doc.get("theme_chosen"), bool):
        out["theme_chosen"] = doc["theme_chosen"]
    if doc.get("theme") in THEMES and (doc["theme"] != "admiralty" or out["theme_chosen"]):
        out["theme"] = doc["theme"]
    if isinstance(doc.get("language"), str):
        out["language"] = doc["language"]
    for key in ("last_backup", "backup_snoozed"):
        if isinstance(doc.get(key), str):
            out[key] = doc[key]
    for key in ("show_custom_factions", "show_other_race_factions"):
        if isinstance(doc.get(key), bool):
            out[key] = doc[key]
    return out


def save_settings(**changes) -> tuple[bool, str]:
    settings = load_settings()
    if "theme" in changes:
        changes["theme_chosen"] = True
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
           "designs": designs, "factions": _factions_used(designs, fleet),
           "portraits": portraits.subset(list(designs_for_fleet(fleet).values()), fleet)}
    return _filename(fleet["name"], EXTENSIONS["fleet"]), json.dumps(doc, indent=1, ensure_ascii=False)


def export_campaign(campaign_id: str) -> tuple[str, str] | None:
    """(filename, JSON text): the campaign, every fleet in it and what those fleets need."""
    campaign = get_campaign(campaign_id)
    if not campaign:
        return None
    fleets = campaign_fleets(campaign_id)
    used: dict[str, dict] = {}
    for fleet in fleets:
        used.update(designs_for_fleet(fleet))
    designs = [d for d in used.values() if not is_catalog(d["id"])]
    art: dict = {}
    for fleet in fleets:
        art.update(portraits.subset(list(designs_for_fleet(fleet).values()), fleet))
    wanted = {d["faction"] for d in designs} | {f["faction"] for f in fleets}
    doc = {"schema_version": migrations.CURRENT, "kind": "FTCampaign", "campaign": campaign,
           "fleets": fleets, "designs": designs,
           "factions": [f for f in custom_factions() if f["id"] in wanted], "portraits": art}
    return _filename(campaign["name"], EXTENSIONS["campaign"]), json.dumps(doc, indent=1, ensure_ascii=False)


def export_design(design_id: str) -> tuple[str, str] | None:
    design = get_design(design_id)
    if not design:
        return None
    doc = {"schema_version": migrations.CURRENT, "kind": "FTDesign", "design": design,
           "factions": _factions_used([design]), "portraits": portraits.subset([design])}
    return _filename(design["name"], EXTENSIONS["design"]), json.dumps(doc, indent=1, ensure_ascii=False)


def export_backup() -> tuple[str, bytes]:
    """A zip of the whole library; records the time for the web build's backup reminder."""
    buf = io.BytesIO()
    root = paths.user_data_dir()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for sub in ("designs", "fleets", "campaigns"):
            for p in sorted(_dir(sub).glob("*.json")):
                z.write(p, f"{sub}/{p.name}")
        for name in ("factions.json", "settings.json", "portraits.json"):
            if (root / name).is_file():
                z.write(root / name, name)
    save_settings(last_backup=now())
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return f"FleetManager_backup_{stamp}{EXTENSIONS['backup']}", buf.getvalue()


def _newer(local: dict | None, incoming: dict) -> bool:
    """True if a local copy exists and is newer than the incoming one (ISO strings compare)."""
    return bool(local) and (local.get("modified") or "") > (incoming.get("modified") or "")


BACKUP_REMINDER_DAYS = 14  # PLAN 5.7


def backup_due() -> bool:
    """The web build's reminder: the library holds something and neither a backup nor a "Later"
    happened in the last two weeks."""
    if not any(any(_dir(sub).glob("*.json")) for sub in ("designs", "fleets", "campaigns")):
        return False
    settings = load_settings()
    stamps = [settings[k] for k in ("last_backup", "backup_snoozed") if settings[k]]
    if not stamps:
        return True
    try:
        latest = max(datetime.fromisoformat(t) for t in stamps)
        return (datetime.now(timezone.utc) - latest).days >= BACKUP_REMINDER_DAYS
    except (ValueError, TypeError):  # not an ISO time with a zone: remind
        return True


# An import that found newer local copies waits here for the player's answer (PLAN 5.6). It is
# JSON (the file as base64) because the web build snapshots the data folder as text.
def _pending_path() -> Path:
    return paths.user_data_dir() / "pending_import.json"


def hold_import(filename: str, data: bytes, conflicts: list[str]) -> None:
    paths.user_data_dir().mkdir(parents=True, exist_ok=True)
    _write_json(_pending_path(), {"filename": filename[:200], "conflicts": conflicts[:200],
                                  "data": base64.b64encode(data).decode("ascii")})


def held_import() -> dict | None:
    """{"filename", "conflicts", "data": bytes} of the import waiting for an answer, or None."""
    doc = _read_json(_pending_path()) if _pending_path().is_file() else None
    if not isinstance(doc, dict) or not isinstance(doc.get("data"), str):
        return None
    try:
        data = base64.b64decode(doc["data"], validate=True)
    except ValueError:
        return None
    conflicts = [c for c in doc.get("conflicts", []) if isinstance(c, str)] \
        if isinstance(doc.get("conflicts"), list) else []
    return {"filename": _as_str(doc.get("filename"), limit=200), "conflicts": conflicts, "data": data}


def drop_held_import() -> None:
    _pending_path().unlink(missing_ok=True)


# A backup is a few hundred KB of JSON; anything far bigger unpacked is not one of ours.
MAX_BACKUP_BYTES = 64 * 1024 * 1024


class _Refused(Exception):
    """An import that writes nothing; the message says why."""


def _import_factions(raw: object) -> list[dict]:
    out = []
    for f in raw if isinstance(raw, list) else []:
        if isinstance(f, dict) and _safe_id(f.get("id")) and isinstance(f.get("name"), str):
            out.append(f)
    return out


def _import_design(raw: object) -> dict | None:
    design = normalize_design(raw)
    if not design or is_catalog(design["id"]) or not _safe_id(design["id"]):
        return None
    return design


def import_file(filename: str, data: bytes, overwrite_newer: bool = False) -> tuple[bool, str, list[str]]:
    """Import an .FTFleet / .FTDesign / .FTCampaign / .FTBackup. Returns (ok, msg, conflicts): conflicts are
    names of items skipped because the local copy is newer; call again with overwrite_newer=True
    after the player confirms (PLAN 5.6). The whole file is read and checked before anything is
    written, so a refused file leaves the library as it was."""
    try:
        if data[:2] == b"PK":
            factions, designs, fleets, campaigns, art, skipped = _read_backup(data)
        else:
            factions, designs, fleets, campaigns, art = _read_document(data)
            skipped = 0
    except _Refused as refusal:
        return False, str(refusal), []
    except migrations.TooNewError:
        return False, _("This file comes from a newer version of the app."), []

    for f in factions:
        if not any(c["id"] == f["id"] for c in custom_factions()):
            add_custom_faction(f["name"], f["id"], f.get("race"))
    conflicts: list[str] = []
    written = 0
    for doc, local, path in ([(d, get_design(d["id"]), _design_path(d["id"])) for d in designs]
                             + [(f, get_fleet(f["id"]), _fleet_path(f["id"])) for f in fleets]
                             + [(c, get_campaign(c["id"]), _campaign_path(c["id"])) for c in campaigns]):
        if _newer(local, doc) and not overwrite_newer:
            conflicts.append(doc["name"])
            continue
        _write_json(path, doc)
        written += 1
    art_written, art_conflicts = portraits.merge(art, overwrite_newer)
    conflicts.extend(art_conflicts)

    if data[:2] == b"PK":
        written += art_written
        msg = _("{n} items restored from the backup.", n=written)
        if skipped:
            msg += " " + _("{n} unreadable entries skipped.", n=skipped)
        return True, msg, conflicts
    if campaigns:
        if conflicts:
            return True, _("Imported; {n} newer local copies kept.", n=len(conflicts)), conflicts
        return True, _("Campaign {name} imported.", name=campaigns[0]["name"]), []
    if fleets:
        if conflicts:
            return True, _("Imported; {n} newer local copies kept.", n=len(conflicts)), conflicts
        return True, _("Fleet {name} imported.", name=fleets[0]["name"]), []
    if conflicts:
        return True, _("Kept the newer local copy of {name}.", name=conflicts[0]), conflicts
    return True, _("Design {name} imported.", name=designs[0]["name"]), []


def _fleets_need_only(fleets: list[dict], designs: list[dict], ruleset: str) -> None:
    """Refuses fleets whose designs are neither in the file nor known here, or of another ruleset."""
    known = {d["id"] for d in designs} | set(_catalog()) | {d["id"] for d in list_designs()}
    missing = {s["design_id"] for f in fleets for s in f["ships"]} - known
    if missing:
        names = ", ".join(sorted(missing))
        raise _Refused(_("The fleet uses designs that are not in the file: {ids}.", ids=names))
    if any(d["ruleset"] != ruleset for d in designs):
        raise _Refused(_("The file mixes designs of another ruleset into the fleet."))


def _read_document(data: bytes) -> tuple[list[dict], list[dict], list[dict], list[dict], dict]:
    """(factions, designs, fleets, campaigns, ship pictures) of an .FTDesign, .FTFleet or
    .FTCampaign, all checked; raises _Refused. Pictures are kept only for the designs and ships
    the file carries."""
    try:
        doc = json.loads(data.decode("utf-8-sig"))
    except (UnicodeDecodeError, ValueError):
        raise _Refused(_("Not a Fleet Manager file.")) from None
    if not isinstance(doc, dict):
        raise _Refused(_("Not a Fleet Manager file."))
    migrations.upgrade("fleet", {"schema_version": doc.get("schema_version")})
    factions = _import_factions(doc.get("factions"))
    kind = doc.get("kind")
    if kind == "FTDesign":
        design = _import_design(doc.get("design"))
        if not design:
            raise _Refused(_("The file holds no usable design."))
        return factions, [design], [], [], portraits.subset([design], doc=doc.get("portraits"))
    if kind == "FTFleet":
        fleet = normalize_fleet(doc.get("fleet"))
        if not fleet:
            raise _Refused(_("The file holds no usable fleet."))
        raw = doc.get("designs") if isinstance(doc.get("designs"), list) else []
        designs = [d for d in (_import_design(x) for x in raw) if d]
        _fleets_need_only([fleet], designs, fleet["ruleset"])
        used = designs + [{"id": s["design_id"]} for s in fleet["ships"]]
        return factions, designs, [fleet], [], portraits.subset(used, fleet, doc.get("portraits"))
    if kind == "FTCampaign":
        campaign = normalize_campaign(doc.get("campaign"))
        if not campaign:
            raise _Refused(_("The file holds no usable campaign."))
        raw = doc.get("designs") if isinstance(doc.get("designs"), list) else []
        designs = [d for d in (_import_design(x) for x in raw) if d]
        raw = doc.get("fleets") if isinstance(doc.get("fleets"), list) else []
        fleets = [f for f in (normalize_fleet(x) for x in raw) if f]
        if any(f["ruleset"] != campaign["ruleset"] or f["campaign_id"] != campaign["id"] for f in fleets):
            raise _Refused(_("The file holds fleets that are not in its campaign."))
        _fleets_need_only(fleets, designs, campaign["ruleset"])
        art: dict = {}
        for fleet in fleets:
            used = designs + [{"id": s["design_id"]} for s in fleet["ships"]]
            art.update(portraits.subset(used, fleet, doc.get("portraits")))
        return factions, designs, fleets, [campaign], art
    if kind == "FTStarmap":
        raise _Refused(_("Load a star map on a campaign's Star map panel."))
    raise _Refused(_("Not a Fleet Manager file."))


def _read_backup(data: bytes) -> tuple[list[dict], list[dict], list[dict], list[dict], dict, int]:
    """(factions, designs, fleets, campaigns, ship pictures, entries skipped) of an .FTBackup; raises
    _Refused. An entry
    that cannot be read as a design or fleet of this app is skipped and counted, not guessed at;
    one from a newer app refuses the whole backup."""
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise _Refused(_("Not a Fleet Manager backup.")) from None
    designs: list[dict] = []
    fleets: list[dict] = []
    campaigns: list[dict] = []
    factions: list[dict] = []
    art: dict = {}
    skipped = 0
    with z:
        if sum(info.file_size for info in z.infolist()) > MAX_BACKUP_BYTES:
            raise _Refused(_("Not a Fleet Manager backup."))
        names = z.namelist()
        try:
            if "factions.json" in names:
                doc = json.loads(z.read("factions.json").decode("utf-8"))
                factions = _import_factions(doc.get("factions") if isinstance(doc, dict) else None)
            if "portraits.json" in names:
                art = portraits.normalize(json.loads(z.read("portraits.json").decode("utf-8")))
            for name in names:
                m = re.fullmatch(r"(designs|fleets|campaigns)/([A-Za-z0-9_-]{1,64})\.json", name)
                if not m:
                    continue
                try:
                    raw = json.loads(z.read(name).decode("utf-8"))
                except (UnicodeDecodeError, ValueError):
                    skipped += 1
                    continue
                kind = m.group(1)
                doc = {"designs": _import_design, "fleets": normalize_fleet,
                       "campaigns": normalize_campaign}[kind](raw)
                if not doc:
                    skipped += 1
                    continue
                {"designs": designs, "fleets": fleets, "campaigns": campaigns}[kind].append(doc)
        except (zipfile.BadZipFile, OSError, RuntimeError, ValueError) as error:
            if isinstance(error, migrations.TooNewError):
                raise
            raise _Refused(_("Not a Fleet Manager backup.")) from None
    if not designs and not fleets and not campaigns:
        raise _Refused(_("The backup is empty."))
    return factions, designs, fleets, campaigns, art, skipped
