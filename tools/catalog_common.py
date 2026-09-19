"""Shared helpers for the catalog extractors (tools/extract_catalog_*.py).

Each extractor holds a curated ship list read from the rulebook pages: class, type and the
numbers from the text layer, systems and arcs read from the SSD (tools/ssd_arcs.py for rings,
the rendered page image for everything else). This module turns that list into design dicts
(PLAN 5.1) and writes data/catalog/<file>.json.

System notation, space separated, `*n` repeats a token:
  B<class>[:arcs]   beam; FB class 1 defaults to all arcs; FT2 classes are A/B/C
  PT:arcs           pulse torpedo          NB:arc   needle beam      SM[:arc]  submunition pack
  SML:arcs          SM launcher            MAG:<capacity>  magazine feeding every SML of the ship
  SMR:arcs[:er]     SM rack                PDS  FC  ADFC   PDAF  ADAF
  S<level>          screen                 HB   one fighter hangar bay (FB) / fighter group (FT2)
  H:<mass> P:<mass> T:<mass>  cargo / passenger / troop space      TB:<capacity>  tender bay
  NOVA:arc  WAVE:arc  AA:arc  MSL  ORTILLERY  MINELAYER  MINESWEEPER  TUG
Arcs are comma separated ("F,FS,FP") or "all".
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FB_ALL = ["F", "FS", "AS", "A", "AP", "FP"]


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _arcs(spec: str, ruleset: str) -> list[str]:
    if spec == "all":
        return list(FB_ALL)
    return spec.split(",")


def parse_systems(notation: str, ruleset: str) -> tuple[list[dict], dict]:
    """(systems, default_loadout) from the notation above."""
    tokens: list[str] = []
    for tok in notation.split():
        name, _, times = tok.partition("*")
        tokens += [name] * (int(times) if times else 1)
    systems: list[dict] = []
    launchers: list[str] = []
    magazines: list[dict] = []
    fighters: list[dict] = []

    def add(system: dict) -> dict:
        system = {"uid": f"s{len(systems) + 1}", **system}
        systems.append(system)
        return system

    for tok in tokens:
        head, _, rest = tok.partition(":")
        m = re.fullmatch(r"B([1-6ABC])", head)
        if m:
            cls = m.group(1)
            if ruleset == "fb":
                arcs = _arcs(rest, ruleset) if rest else list(FB_ALL)
                add({"type": "beam", "class": int(cls), "arcs": arcs})
            else:
                add({"type": "beam", "class": cls, "arcs": _arcs(rest, ruleset)})
        elif head == "PT":
            add({"type": "pulse_torpedo", "arcs": _arcs(rest, ruleset)})
        elif head == "NB":
            add({"type": "needle_beam", "arcs": _arcs(rest, ruleset)})
        elif head == "SM":
            add({"type": "submunition", **({"arcs": _arcs(rest, ruleset)} if rest else {})})
        elif head == "SML":
            launchers.append(add({"type": "sm_launcher", "arcs": _arcs(rest, ruleset)})["uid"])
        elif head == "MAG":
            magazines.append(add({"type": "sm_magazine", "capacity": int(rest), "feeds": []}))
        elif head == "SMR":
            arcs, _, load = rest.partition(":")
            add({"type": "sm_rack", "load": load or "std", "arcs": _arcs(arcs, ruleset)})
        elif head in (
            "PDS",
            "PDAF",
            "ADAF",
            "ADFC",
            "FC",
            "MSL",
            "ORTILLERY",
            "MINELAYER",
            "MINESWEEPER",
            "TUG",
        ):
            add(
                {
                    "type": {
                        "PDS": "pds",
                        "PDAF": "pdaf",
                        "ADAF": "adaf",
                        "ADFC": "adfc",
                        "FC": "fire_control",
                        "MSL": "mt_missile",
                        "ORTILLERY": "ortillery",
                        "MINELAYER": "minelayer",
                        "MINESWEEPER": "minesweeper",
                        "TUG": "tug_drive",
                    }[head]
                }
            )
        elif re.fullmatch(r"S[1-9]", head):
            add({"type": "screen", "level": int(head[1])})
        elif head == "HB":
            if ruleset == "fb":
                fighters.append({"hangar": add({"type": "hangar", "bays": 1})["uid"], "type": "standard"})
            else:
                fighters.append({"hangar": add({"type": "fighter_group"})["uid"], "type": "standard"})
        elif head in ("H", "P", "T"):
            add(
                {
                    "type": "hold",
                    "kind": {"H": "cargo", "P": "passenger", "T": "troop"}[head],
                    "mass": int(rest),
                }
            )
        elif head == "TB":
            add({"type": "tender_bay", "capacity": int(rest)})
        elif head in ("NOVA", "WAVE", "AA"):
            add(
                {
                    "type": {"NOVA": "nova_cannon", "WAVE": "wave_gun", "AA": "aa_battery"}[head],
                    "arcs": _arcs(rest, ruleset),
                }
            )
        else:
            raise ValueError(f"unknown system token: {tok}")
    if len(magazines) > 1:
        raise ValueError("one MAG per ship: it feeds every launcher")
    for mag in magazines:
        mag["feeds"] = list(launchers)
    loadout = {
        "fighters": fighters,
        "magazines": [{"magazine": m["uid"], "salvos": ["std"] * (m["capacity"] // 2)} for m in magazines],
    }
    return systems, loadout


def design(
    ruleset: str,
    book: str,
    page: int,
    faction: str | None,
    name: str,
    type_label: str,
    type_code: str,
    tmf: int,
    npv: int,
    systems: str,
    *,
    hull: int = 0,
    armour: int = 0,
    thrust: int = 0,
    ftl: bool = True,
    kind: str = "warship",
    notes: str = "",
) -> dict:
    ident = f"{ruleset}:{slug(book)}:{slug((faction or '') + ' ' + name)}"
    parsed, loadout = parse_systems(systems, ruleset)
    return {
        "schema_version": 1,
        "id": ident,
        "ruleset": ruleset,
        "race": "human",
        "faction": faction,
        "name": name,
        "type_label": type_label,
        "type_code": type_code,
        "hull_kind": kind,
        "tmf": tmf,
        "hull_boxes": hull,
        "armour": armour,
        "thrust": thrust,
        "ftl": ftl,
        "streamlining": "none",
        "systems": parsed,
        "default_loadout": loadout,
        "allow_rule_breaking": False,
        "layout_hints": {},
        "source": {"kind": "catalog", "book": book, "page": page, "npv_book": npv},
        "notes": notes,
    }


def write(filename: str, designs: list[dict]) -> Path:
    ids = [d["id"] for d in designs]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate catalog ids")
    out = ROOT / "data" / "catalog" / filename
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps({"schema_version": 1, "designs": designs}, indent=1, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return out
