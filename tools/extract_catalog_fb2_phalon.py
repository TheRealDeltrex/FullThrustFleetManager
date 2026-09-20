"""Build data/catalog/fb_fb2_phalon.json: the Phalon classes of Fleet Book 2 (pp.38-45).

Hull integrity, shell layers, thrust and the system counts come from each ship's TECHNICAL
SPECIFICATIONS panel, which prints the shell layer by layer ("Shell Strength: Layer 1: 16,
Layer 2: 10, ..."); the run checks every TMF and NPV against the page text before writing.

Pulser arcs come off the vector SSDs. A pulser is a small hexagon ringed by six triangles, one
per arc, white where the battery bears and black where it does not, which tools/ssd_arcs.py
stars() reads. Plasma bolt launcher arcs cannot be read: the launcher icon is a cog with only
its class number in it, so they take the book's stated norm, "normally (but not always) mounted
to fire through the forward arcs of the ship (FP/F/FS)" (FB2 p.36).

Type codes are the FB1 p.12 class nearest the panel's "Human Class Equivalent"; the Huulth,
which the book calls only a "Medium Cruiser", carries none, because no book prints that class.

    python tools/extract_catalog_fb2_phalon.py
"""

from __future__ import annotations

import sys

import pymupdf
from catalog_common import ROOT, design, write

BOOK = "FB2"
FACTION = "PH"

# Pulser arc sets, named for readability (FB2 p.35: one, three or six arcs).
PORT = "AP,FP,F"
FORE = "FP,F,FS"
STBD = "F,FS,AS"
ALL = "all"

# (page, name, type label, code, TMF, NPV, hull, shell layers inner-first, thrust, systems)
# fmt: off
SHIPS = [
    (38, "Phyaa",   'Recon Scout',      'SC',   10,   39,  1, (1,),            6, "PU:F VS FC"),
    (38, "Vlath",   'Battle Scout',     'SC',   12,   51,  2, (1,),            4, f"PU:{ALL} VS FC"),
    (39, "Dorrth",  'Corvette',         'CT',   16,   60,  2, (2,),            6, f"PU:{FORE} VS FC"),
    (39, "Tyaph",   'Frigate',          'FF',   21,   84,  3, (2,),            6, f"PU:F PU:{ALL} VS FC"),
    (40, "Phuun",   'Frigate',          'FF',   24,   89,  3, (2,),            6,
     f"PU:{FORE} PBL1 VS FC"),
    (40, "Dinth",   'Heavy Destroyer',  'DH',   41,  150,  7, (4,),            6,
     f"PU:{ALL} PU:F PBL1 VS FC"),
    (41, "Tsaara",  'Light Cruiser',    'CL',   58,  225, 10, (3, 2),          4,
     f"PU:F PU:{ALL}*2 PBL2 VS FC*2"),
    (41, "Huulth",  'Medium Cruiser',   '',     70,  276, 12, (4, 3),          4,
     f"PU:{PORT} PU:{ALL}*2 PU:{STBD} PBL2 VS FC*2"),
    (42, "Tuuloth", 'Heavy Cruiser',    'CH',   80,  299, 16, (6, 3),          4,
     f"PU:{PORT} PU:{ALL} PU:{STBD} PBL3 VS FC*2"),
    (42, "Keraph",  'Battlecruiser',    'BC',  104,  398, 20, (8, 4),          4,
     f"PU:F PU:{PORT} PU:{ALL}*2 PU:{STBD} PBL3 VS FC*3 ADFC"),
    (43, "Ptath",   'Battleship',       'BB',  132,  522, 24, (8, 4, 4),       4,
     f"PU:{FORE}*3 PU:{PORT} PU:{ALL}*2 PU:{STBD} PBL4 VS FC*3"),
    (43, "Saath",   'Battledreadnought', 'BDN', 170,  658, 30, (9, 5, 4),      4,
     f"PU:{FORE}*2 PU:{PORT} PU:{ALL}*3 PU:{STBD} PBL5 PBL2 VS FC*3"),
    (44, "Voth",    'Superdreadnought', 'SDN', 250, 1041, 42, (16, 10, 8, 6),  2,
     f"PU:{ALL}*7 PU:{PORT}*2 PU:{STBD}*2 PBL6 PBL3*2 VS FC*5"),
    (44, "Taanis",  'Light Carrier',    'CVL', 170,  641, 30, (8, 4, 4),       4,
     f"PU:{PORT}*2 PU:{STBD}*2 PU:{ALL} PBL2 VS FC*2 HB*4"),
    (45, "Draath",  'Heavy Carrier',    'CVH', 250, 1002, 40, (12, 8, 6, 4),   2,
     f"PU:{PORT}*2 PU:{STBD}*2 PU:{ALL}*4 PBL3 VS FC*2 HB*8"),
]
# fmt: on


def check_against_text() -> None:
    """Every curated TMF, NPV and shell layer must appear on its page's text layer."""
    doc = pymupdf.open(ROOT / "rulebooks" / "Fleet Book 2.pdf")
    problems = []
    for page, name, _label, _code, tmf, npv, _hull, layers, *_ in SHIPS:
        text = " ".join(doc[page - 1].get_text().split())
        if f"TMF: {tmf}" not in text or f"NPV: {npv}" not in text or name not in text:
            problems.append(f"p{page} {name}: TMF {tmf} / NPV {npv} not on the page")
        printed = ", ".join(f"Layer {i + 1}: {n}" for i, n in enumerate(layers))
        if printed not in text:
            problems.append(f"p{page} {name}: shell '{printed}' not on the page")
    if problems:
        sys.exit("\n".join(problems))


def check_pulser_arcs() -> None:
    """The pulser arcs curated above must be the ones drawn on the SSDs.

    ssd_arcs.stars() reads every pulser on a page but cannot say which ship it belongs to, so
    the check is per page: the multiset of arc sets we claim for a page's ships must be the one
    the page draws. Page 45 also carries the weapons summary box, whose three example icons are
    not on any ship, so they are allowed as extras there.
    """
    sys.path.insert(0, str(ROOT / "tools"))
    import ssd_arcs

    doc = pymupdf.open(ROOT / "rulebooks" / "Fleet Book 2.pdf")
    problems = []
    by_page: dict[int, list[str]] = {}
    for page, _name, _label, _code, _tmf, _npv, _hull, _layers, _thrust, systems in SHIPS:
        for token in systems.split():
            head, _, rest = token.partition(":")
            if head != "PU":
                continue
            spec, _, times = rest.partition("*")
            arcs = ssd_arcs.ARC_ANGLES if spec == "all" else spec.split(",")
            key = ",".join(a for a in ssd_arcs.ARC_ANGLES if a in arcs)
            by_page.setdefault(page, []).extend([key] * (int(times) if times else 1))
    for page, ours in sorted(by_page.items()):
        drawn = [",".join(f["arcs"]) for f in ssd_arcs.stars(doc[page - 1])]
        extra = sorted(drawn)
        for key in ours:
            if key in extra:
                extra.remove(key)
            else:
                problems.append(f"p{page}: no pulser drawn with arcs {key}")
        # p.45's summary box shows three example pulsers that belong to no ship.
        if extra and not (page == 45 and len(extra) == 3):
            problems.append(f"p{page}: pulsers drawn that no ship claims: {extra}")
    if problems:
        sys.exit("\n".join(problems))


def build() -> list[dict]:
    return [
        design("fb", BOOK, page, FACTION, name, label, code, tmf, npv, systems,
               hull=hull, armour_layers=layers, thrust=thrust, race="phalon")
        for page, name, label, code, tmf, npv, hull, layers, thrust, systems in SHIPS
    ]


def main() -> None:
    check_against_text()
    check_pulser_arcs()
    out = write("fb_fb2_phalon.json", build())
    print(f"Wrote {out} ({len(SHIPS)} Phalon classes; pulser arcs match the SSDs)")


if __name__ == "__main__":
    main()
