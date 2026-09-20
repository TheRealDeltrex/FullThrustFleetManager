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
    ("fb", "hangar", "Fighter movement", "FB1", "FIGHTER MOVEMENT"),
    ("fb", "hold", "Cargo holds and passengers", "FB1", "CARGO HOLDS AND PASSENGER ACCOMMODATIONS"),
    ("fb", "tug_drive", "Tugs and tenders", "FB1", "TUGS AND TENDERS:"),
    ("fb", "arcs", "Arcs of fire", "FB1", "ARCS OF FIRE"),
    ("fb", "vector_movement", "Vector movement", "FB1", "MOVING SHIPS UNDER THE VECTOR SYSTEM"),
    ("fb", "rerolls", "Rerolls (penetrating damage)", "FB1", "REROLLS (PENETRATING DAMAGE)"),

    # Kra'Vak (FB2 pp.9-10). Keys are prefixed kv_ so a Kra'Vak entry never displaces the FB1
    # one for the same system on a mixed-race fleet's sheet.
    ("fb", "kv_thrust", "Kra'Vak thrust and manoeuvre", "FB2", "KRA’VAK THRUST AND MANOEUVRE"),
    ("fb", "kv_kgun", "Kinetic guns (K-guns)", "FB2", "KINETIC GUNS (K-GUNS)"),
    ("fb", "kv_mkp", "Multiple kinetic penetrator packs", "FB2", "MULTIPLE KINETIC PENETRATOR (MKP) PACKS"),
    ("fb", "kv_scattergun", "Scatterguns", "FB2", "SCATTERGUNS:"),
    ("fb", "kv_fire_control", "Kra'Vak fire control", "FB2", "FIRE CONTROL SYSTEMS"),
    ("fb", "kv_crew", "Kra'Vak crew factors and damage control", "FB2", "CREW FACTORS AND DAMAGE CONTROL"),
    ("fb", "kv_hangar", "Kra'Vak fighters", "FB2", "FIGHTERS"),

    # Sa'Vasku (FB2 pp.22-25). The weapon and defence entries come from the book's own summary
    # panel on p.25, the rest from the rules pages.
    ("fb", "sv_power", "Allocating power", "FB2", "ALLOCATING POWER"),
    ("fb", "sv_thrust", "Sa'Vasku thrust and manoeuvre", "FB2", "SA'VASKU THRUST AND MANOEUVRE"),
    ("fb", "sv_biomass", "Biomass boxes", "FB2", "BIOMASS BOXES"),
    ("fb", "sv_power_generator", "Power generators", "FB2", "POWER GENERATORS"),
    ("fb", "sv_stinger", "Stinger nodes", "FB2", "STINGER NODES"),
    ("fb", "sv_pod_launcher", "Pod launcher nodes", "FB2", "POD LAUNCHER NODES"),
    ("fb", "sv_screen_node", "Screen nodes", "FB2", "SCREEN NODES"),
    ("fb", "sv_spicule", "Spicules", "FB2", "SPICULES"),
    ("fb", "sv_cortex", "Cortex nodes", "FB2", "CORTEX NODES"),
    ("fb", "sv_drone_womb", "Drone wombs", "FB2", "DRONE WOMBS"),
    ("fb", "sv_repair", "Sa'Vasku damage control", "FB2", "DAMAGE CONTROL"),

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

# Entries the page layout defeats: a two-column page with a figure caption or a spec panel in
# the middle gives the reader's line order, not the sentence order, and a section that breaks
# across a column ends mid-sentence. These were transcribed from the page images by hand, in
# the book's own words (PLAN 2.5), trimmed the same way the rest are. Everything else comes
# straight out of the page text. Check the page image before editing one.
# fmt: off
OVERRIDES = {
    ("ft2", "turn_sequence"):
        "The game is played as a series of GAME TURNS, each Turn consisting of both (or all) "
        "players having the opportunity to move and fire their ships. Each Game Turn starts with "
        "both players simultaneously (and secretly) writing the MOVEMENT ORDERS for all the ships "
        "they own, using the spaces on the lower portion of the Ship Record Sheets. Once all "
        "orders for that Turn have been completed, any Asteroids or similar objects (such as "
        "Installations or Starbases) that may be in play are moved if necessary, in accordance "
        "with the rules given for such objects. Now each player must move all of his ships, in "
        "strict accordance with the orders he has written for them.",
    ("ft2", "arcs"):
        "The 360 degree space around each ship is divided into four equal (90 degree) ARCS, "
        "labelled FORE, AFT, PORT and STARBOARD. IMPORTANT NOTE! NO ship may fire OFFENSIVE "
        "WEAPONRY through its AFT arc; this is due to the spatial distortions of the ship's Drive "
        "fields, which make it impossible to accurately track a distant target through the rear "
        "90° of the ship's arcs. These Fire Arcs determine which of a ship's weapon batteries "
        "may be brought to bear on a particular target ship, as some Batteries will be unable to "
        "fire through certain arcs.",
    ("ft2", "fighter_group"):
        "Each Fighter is armed with a single weapon, similar to a shorter-ranged 'C' Battery in "
        "effect. The RANGE of Fighter weaponry is 6\", and a Group may ONLY fire at targets in the "
        "Fighters' FORE arc. All Fighters in the Group must engage the SAME target ship. ROLL 1D6 "
        "PER FIGHTER IN THE GROUP: Hits and damage are scored per die, using the same results as "
        "Beam Battery Fire. Screens protect as normal against Fighter weapon fire. Fighters "
        "operate in GROUPS of 1 to 6 craft, with each Group moving and firing as a single unit.",
    ("ft2", "nova_cannon"):
        "The NOVA CANNON is a massive weapon that can only be mounted in the spinal core of a "
        "Capital ship, and fires only DIRECTLY FORWARD - not just through the Fore arc, but "
        "actually on the centreline of the ship only. In other words, the weapon fires in whatever "
        "direction the ship's bow is pointing. Firing a Nova Cannon draws a massive amount of "
        "power from the ship's Power Plant; on the Turn it is to be fired the player must note "
        "this in his movement orders for that ship, and the ship may not expend ANY other power at "
        "all for that Turn, ie: it may not apply any Thrust (to accelerate or manoeuvre), may not "
        "fire ANY other weapons, and even its Screens may not function for that Turn!",
    ("ft2", "wave_gun"):
        "The Wave Gun is a smaller and slightly less over-the-top variant on the Nova Cannon given "
        "in the Full Thrust rulebook. The system fires a Plasma charge that expands as it travels "
        "along its line of flight, causing damage to any vessels in its path. As with the Nova "
        "Cannon, the Wave Gun may fire only along the main axis of the carrying ship, ie: in a "
        "straight line bearing directly forward along the ship's current course. The ship may not "
        "fire ANY other weaponry in the turn that it fires the Wave Gun, and also counts as "
        "UNSHIELDED through its entire frontal arc while the weapon is being fired.",
    ("ft2", "ortillery"):
        "This is a system used for ground support fire from orbiting Starships or Monitors. It has "
        "no function in Space Combat, and cannot be used as an anti-ship weapon. The use of this "
        "system is fully described in the section on Ortillery Fire in the \"DIRTSIDE II\" "
        "INTERFACE rules; if you are using FULL THRUST with a different Ground Combat rules system "
        "then the rules given should allow you to relate this weapon to your chosen game with a "
        "little thought.",
    ("ft2", "mt_missile"):
        "When a ship ENDS its plotted movement within 6\" of an active enemy missile, the missile "
        "may attack the ship. This is carried out at the same point in the turn as Fighter group "
        "attacks. Before the missile attacks, the ship has a chance to try and intercept it using "
        "any PDAF systems it has, in a similar way to firing on fighter groups; as missiles are "
        "smaller and more agile than fighters, however, it needs a roll of 6 by the PDAF to kill "
        "the missile. Each PDAF (or ADAF, using the same proximity rules as for fighter defence) "
        "can attempt to kill only one missile per turn. \"NORMAL\" MISSILES are assumed to carry "
        "nuclear detonation warheads, and roll 2 dice when attacking – the total score rolled "
        "is the number of damage points inflicted on the target, and is NOT reduced by screens.",
    ("ft2", "streamlining"):
        "The great majority of Starships are not built to ever enter a planetary atmosphere or "
        "attempt to land. Such ships are characterised by their totally unstreamlined structure "
        "and often square, blocky or fragile-looking designs. Some ships, on the other hand, ARE "
        "built to operate in atmosphere as well as in deep space, to varying degrees of "
        "efficiency; a vessel that is FULLY STREAMLINED is completely atmosphere-capable, and can "
        "\"fly\" like an Aerospace craft. Other ships may be classed as PARTIALLY STREAMLINED, "
        "which gives them some capability of atmospheric operations and landing, usually by sheer "
        "brute thrust from their Drives rather than any kind of aerodynamic lift.",
    # FB2 p.11's summary panel. Both are the panel's own words, cut where the next thing on the
    # page is not rules text: the K-gun entry ends before its "ICONS (examples):" caption, and
    # the MKP entry before the SCATTERGUNS panel beside it, which the extractor runs on into
    # because the MKP body is too short to end the section.
    ("fb", "kv_kgun"):
        "Range 0 - 6 mu: 2+ to hit Range 6 - 12 mu: 3+ to hit Range 12 - 18 mu: 4+ to hit "
        "Range 18 - 24 mu: 5+ to hit Range 24 - 30 mu: 6 to hit If hit scored, roll again; roll "
        "GREATER than K-gun class = DP equal to class, roll LESS THAN OR EQUAL to class = DP "
        "equal to class x 2. Natural roll of 6 is always class x 1 DP, even for K-6 and larger. "
        "First DP of hit taken on armour, remainder penetrates. Class-1 K-guns ONLY can fire in "
        "limited point-defence mode: 1 fighter/missile kill is scored on a roll of 5 or 6; no "
        "rerolls.",
    ("fb", "kv_mkp"):
        "One-shot system, range 12 mu. 1 die rolled: 1-3 = no hits, 4 or 5 = 1 hit, 6 = 2 hits "
        "(no rerolls). Each hit does 4 damage points, one to armour (if any) and remainder on "
        "hull.",
}
# fmt: on

# Printed-page window for an entry whose heading is not unique in its book. FB2 repeats
# "FIRE CONTROL SYSTEMS", "HULL INTEGRITY" and "FIGHTERS" once per race, and body_after() keeps
# the longest body, so without a window a Kra'Vak key can pick up the Phalon section's text.
# The window also aims the weapon entries at the book's own summary panel (FB2 p.11) rather
# than at the long rules pages.
PAGES = {
    ("fb", "kv_kgun"): (11, 11),
    ("fb", "kv_mkp"): (11, 11),
    ("fb", "kv_scattergun"): (11, 11),
    ("fb", "kv_thrust"): (9, 9),
    ("fb", "kv_fire_control"): (10, 10),
    ("fb", "kv_crew"): (10, 10),
    ("fb", "kv_hangar"): (10, 10),
    ("fb", "sv_power"): (22, 22),
    ("fb", "sv_thrust"): (22, 22),
    ("fb", "sv_biomass"): (22, 22),
    ("fb", "sv_power_generator"): (22, 22),
    ("fb", "sv_stinger"): (22, 22),
    ("fb", "sv_pod_launcher"): (22, 22),
    ("fb", "sv_screen_node"): (23, 23),
    ("fb", "sv_spicule"): (23, 23),
    ("fb", "sv_cortex"): (24, 24),
    ("fb", "sv_drone_womb"): (23, 23),
    ("fb", "sv_repair"): (24, 24),
}

LIMIT = 700  # trimmed where needlessly wordy (PLAN 2.5)
HEADING = re.compile(r"^[A-Z][A-Z \-/()&.,0-9’'\"]{6,60}:?$")


def clean(text: str) -> str:
    text = (text.replace("�", "'").replace("‘", "'").replace("’", "'")
                .replace("“", '"').replace("”", '"'))
    # Hyphenation across a line break: "danger-\nous" is one word, "Anti-\nAircraft" keeps its
    # hyphen. Both reach us as "danger- ous" once the page text is read line by line.
    text = re.sub(r"(?<=[a-z])-\s*\n\s*(?=[a-z])", "", text)
    text = re.sub(r"(?<=[A-Za-z])-\s*\n\s*(?=[A-Z])", "-", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"(?<=[a-z])-\s+(?=[a-z])", "", text)
    text = re.sub(r"(?<=[A-Za-z])-\s+(?=[A-Z])", "-", text)
    text = re.sub(r"\s+[0-9]{1,3}$", "", text)    # a page number swept up with the last line
    text = re.sub(r"\s+([.,;:])", r"", text)     # the line break left a space before it
    for wrong, right in LOST_HYPHENS.items():
        text = text.replace(wrong, right)
    return text.strip()


# Words whose hyphen the book's own text layer drops (the overprinted "bold" copies confuse it).
LOST_HYPHENS = {
    "pointdefence": "point-defence",
    "antifighter/antimissile": "anti-fighter/anti-missile",
    "fragilelooking": "fragile-looking",
    "atmospherecapable": "atmosphere-capable",
}


def trim(text: str) -> str:
    """Whole sentences up to LIMIT characters."""
    if len(text) <= LIMIT:
        return text
    cut = text[:LIMIT]
    end = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
    return cut[:end + 1].strip() if end > 200 else cut.rstrip() + "..."


def body_after(pages: list[str], heading: str, first: int = 0,
               window: tuple[int, int] | None = None) -> tuple[str, int] | None:
    """The best match for `heading`: the contents page repeats every heading with no body under
    it, so the longest body wins. `window` is an inclusive range of 0-based page indices, for a
    heading that appears more than once in the book."""
    # Contents and introduction pages repeat every heading with the wrong text under it.
    matches = [m for m in _matches(pages, heading) if m and m[1] >= first]
    if window:
        matches = [m for m in matches if window[0] <= m[1] <= window[1]]
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
        printed = PAGES.get((ruleset, key))
        # PAGES is in printed pages; page index = printed + offset - 1 (see the comment below).
        window = (printed[0] + offset - 1, printed[1] + offset - 1) if printed else None
        found = body_after(pages, heading, first, window)
        if not found or len(found[0]) < 60:
            missing.append(f"{ruleset}/{key} ({book}: {heading})")
            continue
        body, index = found
        text = OVERRIDES.get((ruleset, key)) or trim(body)
        # `index` is 0-based, so the PDF's own page number is index + 1 and the printed number
        # is that minus the book's offset (FT prints 1 on its second PDF page).
        out.setdefault(ruleset, []).append({
            "key": key, "title": title, "text": text, "book": book, "page": index + 1 - offset,
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
