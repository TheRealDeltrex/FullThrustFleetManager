"""Build data/quickref/<ruleset>.json: the rulebook wording for each system, with a page ref.

PLAN 2.5: the quick reference on the fleet PDF uses the original rulebook wording, trimmed
where needlessly wordy, never a paraphrase. This tool pulls the text that follows a heading in
the book and trims it to whole sentences; fix an entry by editing the table here and re-running:

    .venv/Scripts/python.exe tools/extract_quickref.py

Page numbers printed in the output are PRINTED page numbers (PDF page - page_offset).
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import fitz  # pymupdf

ROOT = Path(__file__).resolve().parent.parent
BOOKS = {
    # code: (file, page_offset: PDF page index = printed page + offset, first content page index)
    "FT": ("Full Thrust.pdf", 1, 2),
    "MT": ("More Thrust.pdf", 0, 2),
    "FB1": ("Fleet Book 1.pdf", 0, 1),
    "FB2": ("Fleet Book 2.pdf", 0, 1),
}

# (ruleset, key, title, book, heading). `key` is the system type, or a rule the sheet needs.
# fmt: off
ENTRIES = [
    ("fb", "turn_sequence", "Turn sequence", "FB1", "TURN SEQUENCE"),
    ("fb", "beam", "Beam batteries", "FB1", "NEW BEAM BATTERY DESIGNATIONS"),
    ("fb", "beam_pd", "Class-1 beams as point defence", "FB1", "CLASS-1 BEAM BATTERIES AS POINT-DEFENCE"),
    ("fb", "pulse_torpedo", "Pulse torpedoes", "FB1", "ENHANCED PULSE TORPEDOES"),
    ("fb", "needle_beam", "Needle beams", "FB1", "ENHANCED NEEDLE BEAMS"),
    ("fb", "pds", "Point defence systems", "FB1", "POINT DEFENCE SYSTEMS"),
    ("fb", "adfc", "Area-defence fire control", "FB1", "AREA-DEFENCE FIRE CONTROL (ADFC)"),
    ("fb", "armour", "Hull armour", "FB1", "HULL ARMOUR"),
    ("fb", "fire_control", "Fire control systems", "FB1", "FIRE CONTROL SYSTEMS"),
    ("fb", "hull_track", "Hull damage track", "FB1", "HULL DAMAGE TRACK"),
    ("fb", "threshold", "Applying damage", "FB1", "APPLYING DAMAGE"),
    ("fb", "core_systems", "Core systems", "FB1", "CORE SYSTEMS (OPTIONAL RULE)"),
    ("fb", "crew", "Crew casualties", "FB1", "CREW CASUALTIES"),
    ("fb", "sm_launcher", "Salvo missile systems", "FB1", "SALVO MISSILE MOUNTINGS AND MAGAZINES:"),
    ("fb", "sm_magazine", "Magazine capacities", "FB1", "MAGAZINE CAPACITIES"),
    ("fb", "hangar", "Fighter movement", "FB1", "FIGHTER MOVE SEQUENCE"),
    ("fb", "hold", "Cargo holds and passengers", "FB1", "CARGO HOLDS AND PASSENGER ACCOMMODATIONS"),
    ("fb", "tug_drive", "Tugs and tenders", "FB1", "TUGS AND TENDERS:"),
    ("fb", "arcs", "Arcs of fire", "FB1", "ARCS OF FIRE"),
    ("fb", "vector_movement", "Vector movement", "FB1", "MOVING SHIPS UNDER THE VECTOR SYSTEM"),
    ("fb", "rerolls", "Rerolls (penetrating damage)", "FB1", "REROLLS (PENETRATING DAMAGE)"),

    ("ft2", "turn_sequence", "Sequence of play", "FT", "SEQUENCE OF PLAY:"),
    ("ft2", "beam", "Beam weapon batteries", "FT", "BEAM WEAPON BATTERIES:"),
    ("ft2", "arcs", "Fire arcs", "FT", "FIRE ARCS:"),
    ("ft2", "fire_control", "Fire control systems", "FT", "FIRE CONTROL SYSTEMS:"),
    ("ft2", "screen", "Defensive screens", "FT", "DEFENSIVE SCREENS:"),
    ("ft2", "pulse_torpedo", "Pulse torpedoes", "FT", "PULSE TORPEDOES:"),
    ("ft2", "needle_beam", "Needle beams", "FT", "NEEDLE BEAMS:"),
    ("ft2", "submunition", "Submunition packs", "FT", "SUBMUNITION PACKS:"),
    ("ft2", "nova_cannon", "Spinal-mount nova cannon", "FT", "SPINAL-MOUNT NOVA CANNON:"),
    ("ft2", "fighter_group", "Fighter attacks", "FT", "FIGHTER ATTACKS:"),
    ("ft2", "pdaf", "Anti-fighter defences", "FT", "ANTI-FIGHTER DEFENCES:"),
    ("ft2", "ftl", "FTL drives", "FT", "FASTER-THAN-LIGHT (FTL) DRIVES:"),
    ("ft2", "tug_drive", "FTL tugs and tenders", "FT", "FTL TUGS AND TENDERS:"),
    ("ft2", "wave_gun", "Wave gun", "MT", "WAVE GUN:"),
    ("ft2", "ortillery", "Planetary bombardment (ortillery)", "MT", "(ORTILLERY):"),
    ("ft2", "reflex_field", "Reflex field", "MT", "REFLEX FIELD:"),
    ("ft2", "cloak", "Cloaking field", "MT", "FIELD:"),
    ("ft2", "mt_missile", "Missiles", "MT", "MISSILE ATTACKS:"),
    ("ft2", "streamlining", "Atmospheric streamlining", "MT", "ATMOSPHERIC STREAMLINING:"),
]
# fmt: on

LIMIT = 700  # trimmed where needlessly wordy (PLAN 2.5)
HEADING = re.compile(r"^[A-Z][A-Z \-/()&.,0-9’'\"]{6,60}:?$")


def clean(text: str) -> str:
    text = text.replace("�", "'").replace("’", "'").replace("“", '"').replace("”", '"')
    text = re.sub(r"-\n(?=[a-z])", "", text)      # hyphenation across a line break
    text = re.sub(r"\s+", " ", text).strip()
    return text


def trim(text: str) -> str:
    """Whole sentences up to LIMIT characters."""
    if len(text) <= LIMIT:
        return text
    cut = text[:LIMIT]
    end = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
    return cut[:end + 1].strip() if end > 200 else cut.rstrip() + "..."


def body_after(pages: list[str], heading: str, first: int = 0) -> tuple[str, int] | None:
    """The best match for `heading`: the contents page repeats every heading with no body under
    it, so the longest body wins."""
    # Contents and introduction pages repeat every heading with the wrong text under it.
    matches = [m for m in _matches(pages, heading) if m and m[1] >= first]
    return max(matches, key=lambda m: len(m[0])) if matches else None


def _matches(pages: list[str], heading: str):
    for index, page in enumerate(pages):
        lines = page.splitlines()
        for line_no, line in enumerate(lines):
            if line.strip().rstrip(":") != heading.rstrip(":"):
                continue
            body: list[str] = []
            for follow in lines[line_no + 1:]:
                # A sub-heading right under the heading ("IMPORTANT NOTE:") is part of the entry;
                # only a heading after real text ends it.
                if (HEADING.fullmatch(follow.strip()) and len(follow.split()) >= 2
                        and len("".join(body).strip()) >= 200):
                    break
                body.append(follow)
            if len("".join(body).strip()) < 80 and index + 1 < len(pages):
                body += pages[index + 1].splitlines()[:25]
            yield clean("\n".join(body)), index


def main() -> int:
    texts = {
        code: ([page.get_text() for page in fitz.open(ROOT / "rulebooks" / file)], offset, first)
        for code, (file, offset, first) in BOOKS.items()
    }
    out: dict[str, list[dict]] = {}
    missing = []
    for ruleset, key, title, book, heading in ENTRIES:
        pages, offset, first = texts[book]
        found = body_after(pages, heading, first)
        if not found or len(found[0]) < 60:
            missing.append(f"{ruleset}/{key} ({book}: {heading})")
            continue
        body, index = found
        out.setdefault(ruleset, []).append({
            "key": key, "title": title, "text": trim(body), "book": book, "page": index - offset,
        })
    target = ROOT / "data" / "quickref"
    target.mkdir(parents=True, exist_ok=True)
    for ruleset, entries in out.items():
        path = target / f"{ruleset}.json"
        path.write_text(json.dumps({"schema_version": 1, "entries": entries}, indent=1,
                                   ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"{path.name}: {len(entries)} entries")
    for item in missing:
        print("MISSING:", item)
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
