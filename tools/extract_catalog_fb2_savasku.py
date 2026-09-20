"""Build data/catalog/fb_fb2_savasku.json: the Sa'Vasku constructs of Fleet Book 2 (pp.26-32).

Biomass, carapace, power generation and the node counts come from each ship's TECHNICAL
SPECIFICATIONS panel; the run checks every TMF and NPV against the page text before writing.

Arcs come off the vector SSDs, as FB1's did. Stinger nodes are drawn as the same six-segment
arc rings that human beam batteries use, so tools/ssd_arcs.py rings() reads them directly. Pod
launcher nodes are a cogged disc with an arrow beside it pointing along the launcher's single
arc, which ssd_arcs.py arrows() reads; all but the Vas'Sa'Rosh's three (F, FP, FS) bear fore.

Type codes are the FB1 p.12 class whose name the panel's "Human Class Equivalent" gives exactly;
the two ships the book calls only "Cruiser" carry no code, because inventing one would put a
classification in the catalog that no book prints.

    python tools/extract_catalog_fb2_savasku.py
"""

from __future__ import annotations

import sys

import pymupdf
from catalog_common import ROOT, design, write

BOOK = "FB2"
FACTION = "SV"

# Stinger arc sets, named for readability; each covers three contiguous arcs (FB2 p.22).
PORT = "AP,FP,F"
FORE = "FP,F,FS"
STBD = "F,FS,AS"
AFT = "AS,A,AP"

# (page, name, type label, code, TMF, NPV, biomass, carapace, systems)
# fmt: off
SHIPS = [
    (26, "Sa'An'Tha",    'Scoutship',                        'SC',  10,  34,  3,  0, f"PG:2 ST:{FORE} CX"),
    (26, "Sa'Kess'Tha",  'Scoutship',                        'SC',  11,  37,  2,  1, f"PG:3 ST:{FORE} CX"),
    (27, "Fo'Kiir'Tha",  'Corvette',                         'CT',  18,  59,  5,  1, f"PG:4 ST:{FORE} SP CX"),
    (27, "Fo'Sath'Aan",  'Frigate',                          'FF',  24,  77,  8,  2, f"PG:6 ST:{FORE} SP CX"),
    (28, "Fo'Vur'Ath",   'Heavy Destroyer',                  'DH',  40, 130, 12,  2,
     f"PG:9 ST:{PORT} ST:{STBD} PL:F SP CX"),
    (28, "Var'Arr'Sha",  'Light Cruiser',                    'CL',  52, 169, 16,  3,
     f"PG:12 ST:{PORT} ST:{STBD} PL:F SP*2 CX*2"),
    (29, "Var'Kiir'Sha", 'Cruiser',                          '',    64, 208, 18,  4,
     f"PG:16 ST:{PORT} ST:{FORE} ST:{STBD} PL:F SP*3 CX*2"),
    (29, "Var'Thee'Sha", 'Cruiser',                          '',    70, 226, 20,  6,
     f"PG:16 ST:{PORT} ST:{FORE} ST:{STBD} PL:F SP*3 CX*2"),
    (30, "Thy'Sa'Teth",  'Escort Carrier',                   'CVE', 94, 302, 36,  6,
     f"PG:16 ST:{FORE} SN SP*3 CX*2 DW*2"),
    (30, "Shyy'Tha'Var", 'Battlecruiser',                    'BC', 100, 326, 25,  8,
     f"PG:24 ST:{PORT} ST:{FORE} ST:{STBD} PL:F*2 SN SP*3 CX*3"),
    (31, "Ann'Var'Teth", 'Battleship',                       'BB', 120, 390, 30,  9,
     f"PG:30 ST:{PORT} ST:{STBD} ST:{PORT} ST:{STBD} PL:F*2 SN SP*4 CX*3"),
    (31, "Sla'Tha'Rosh", 'Battledreadnought/Heavy Battleship', 'BDN', 160, 527, 40, 12,
     f"PG:32 ST:{PORT} ST:{FORE} ST:{STBD} ST:{PORT} ST:{AFT} ST:{STBD} PL:F*2 SN*2 SP*4 CX*3 DW"),
    (32, "Vas'Sa'Rosh",  'Superdreadnought',                 'SDN', 220, 724, 60, 16,
     f"PG:40 ST:{PORT} ST:{FORE} ST:{FORE} ST:{STBD} ST:{PORT} ST:{AFT} ST:{AFT} ST:{STBD} "
     "PL:F PL:FP PL:FS SN*2 SP*6 CX*4 DW"),
    (32, "Vas'Sa'Teth",  'Heavy Fighter Carrier',            'CVH', 240, 779, 80, 12,
     f"PG:44 ST:{PORT} ST:{FORE} ST:{AFT} ST:{STBD} PL:F SN*2 SP*6 CX*3 DW*4"),
]
# fmt: on


def check_against_text() -> None:
    """Every curated TMF/NPV must appear on its page's text layer."""
    doc = pymupdf.open(ROOT / "rulebooks" / "Fleet Book 2.pdf")
    problems = []
    for page, name, _label, _code, tmf, npv, *_ in SHIPS:
        text = " ".join(doc[page - 1].get_text().split())
        if f"TMF: {tmf}" not in text or f"NPV: {npv}" not in text or name not in text:
            problems.append(f"p{page} {name}: TMF {tmf} / NPV {npv} not on the page")
    if problems:
        sys.exit("\n".join(problems))


# The one printed table cell that the rules do not produce. FB2 p.28's Fo'Vur'Ath (MASS 40,
# 9 power) ends its 6-power band at thrust 7, but 2% x 8 x 40 = 6.4 also rounds to 6, so the
# band runs to thrust 8. Eleven of the other thirteen tables match to the cell, so the rule is
# right and this row is a slip; it is recorded rather than rounded around.
TABLE_SLIPS = {"Fo'Vur'Ath": "6-power band printed as ending at thrust 7; 8 also costs 6"}


def check_thrust_tables() -> None:
    """Every thrust table printed on an SSD must be one the engine reproduces.

    The tables are the only place the power rules are written down as numbers, so they are the
    real test of `savasku.thrust_power()`; a change to the rounding shows up here first. Two of
    the fourteen (the Shyy'Tha'Var and the Sla'Tha'Rosh) are not in the book's text layer at all,
    so the check runs the other way round: each table that CAN be read must match some ship on
    its page, rather than each ship needing a readable table.
    """
    import re

    sys.path.insert(0, str(ROOT))
    from rulesets.fb import savasku

    doc = pymupdf.open(ROOT / "rulebooks" / "Fleet Book 2.pdf")
    by_page: dict[int, list[tuple]] = {}
    for page, name, _label, _code, tmf, _npv, _bio, _car, systems in SHIPS:
        power = int(re.search(r"PG:(\d+)", systems).group(1))
        by_page.setdefault(page, []).append((name, savasku.thrust_table(tmf, power)))
    problems = []
    for page, ships in sorted(by_page.items()):
        text = " ".join(doc[page - 1].get_text().split()) + " "
        for table in re.findall(r"((?:\d+ \d+/(?:\d+|-) ){3,})", text):
            printed = [(int(a), int(b), None if c == "-" else int(c))
                       for a, b, c in re.findall(r"(\d+) (\d+)/(\d+|-)", table)]
            if any(printed == ours for _name, ours in ships):
                continue
            # Allow a table that differs only where TABLE_SLIPS records a slip for that ship.
            excused = False
            for name, ours in ships:
                if name in TABLE_SLIPS and len(printed) == len(ours) and sum(
                    1 for a, b in zip(printed, ours) if a != b
                ) == 1:
                    excused = True
            if not excused:
                problems.append(f"p{page}: printed table matches no ship: {printed}")
    if problems:
        sys.exit("\n".join(problems))


def build() -> list[dict]:
    return [
        design("fb", BOOK, page, FACTION, name, label, code, tmf, npv, systems,
               hull=biomass, armour=carapace, thrust=0, race="savasku")
        for page, name, label, code, tmf, npv, biomass, carapace, systems in SHIPS
    ]


def main() -> None:
    check_against_text()
    check_thrust_tables()
    out = write("fb_fb2_savasku.json", build())
    print(f"Wrote {out} ({len(SHIPS)} Sa'Vasku constructs; thrust tables match the printed ones)")


if __name__ == "__main__":
    main()
