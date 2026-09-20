"""Build data/catalog/fb_fb2_kravak.json: the Kra'Vak classes of Fleet Book 2 (pp.12-19).

Hull integrity, thrust, K-gun classes and counts, scattergun and fire-control counts, hangar
bays and hold/lab space all come from each ship's TECHNICAL SPECIFICATIONS panel, which FB2
prints in full; the run checks every TMF and NPV against the page text before writing.

Arcs are NOT read from the SSDs here, and tools/ssd_arcs.py finds nothing on these pages: the
Kra'Vak icon is a plain numbered hexagon with no arc pointer (see the key on FB2 p.11). Filled
means one-arc and outline means all-arc, which the class already determines — FB2 p.9 gives
class-1 K-guns all six arcs and limits every larger class to a single arc. That arc is the fore
arc: FB2 p.11 ("their main offensive power in a small number of large K-guns bearing in the Fore
arc"), confirmed per ship on p.13 ("two forward-firing K-2 guns") and p.15 ("a deadly fore-arc
armament of twin K-4 guns"). MKP packs likewise fire "through 1 arc only (usually the Fore
arc)" (FB2 p.9).

    python tools/extract_catalog_fb2_kravak.py
"""

from __future__ import annotations

import sys

import pymupdf
from catalog_common import ROOT, design, write

BOOK = "FB2"
FACTION = "KV"

# (page, name, type label, code, TMF, NPV, hull, thrust, systems)
# fmt: off
WARSHIPS = [
    (12, "Lu'Dak",  'Scoutship',                'SC',  11,  44,  3, 6, "K1 MKP FC"),
    (12, "Ka'Tak",  'Striker or Corvette',      'CT',  20,  79,  6, 6, "K1 MKP*2 SG FC"),
    (13, "Da'Kak",  'Heavy Frigate',            'FF',  30, 119,  9, 6, "K2*2 SG*2 FC"),
    (13, "Di'Tok",  'Heavy Destroyer',          'DH',  40, 159, 12, 6, "K2*2 K1 SG*3 FC"),
    (14, "Vo'Bok",  'Light Cruiser',            'CL',  60, 238, 18, 6, "K3*2 K1 SG*4 FC*2"),
    (14, "Si'Tek",  'Patrol or Escort Cruiser', 'CE',  70, 278, 21, 6, "K3*2 K1*2 SG*5 FC*2"),
    (15, "Ko'Tek",  'Strike Cruiser',           'CE',  70, 275, 21, 6, "K3*3 K1 SG*2 FC*2"),
    (15, "Va'Dok",  'Heavy Cruiser',            'CH',  84, 329, 27, 6, "K4*2 K1 SG*4 FC*2"),
    (16, "Ti'Dak",  'Battlecruiser',            'BC', 100, 393, 36, 4, "K5*2 K1*2 SG*5 FC*3"),
    (16, "Ko'Vol",  'Battleship',               'BB', 121, 467, 48, 4, "K5*2 K1*3 SG*6 FC*3"),
    (17, "Lo'Vok",  'Battledreadnought',        'BDN',160, 626, 54, 4, "K5*2 K3*2 K1*3 SG*7 FC*4 HB"),
    (17, "Yu'Kas",  'Superdreadnought',         'SDN',220, 883, 72, 3, "K6*4 K1*5 SG*13 FC*5 HB"),
    (18, "Do'San",  'Tactical (Light) Carrier', 'CVL',180, 671, 54, 4, "K3*4 K1*3 SG*7 FC*3 HB*4"),
    (18, "Ko'San",  'Heavy Carrier',            'CVH',240, 917, 72, 4, "K3*4 K1*4 SG*11 FC*3 HB*6"),
    (19, "To'Rok",  'Explorer or Recon Ship',   '',    60, 196, 18, 4, "K2 K1 SG*2 FC S:10 TB:4"),
]
# The Sha'Ken is the one Kra'Vak merchant hull: crew factor 1 at MASS 40 ("[Crew Factor: 1
# (Merchant)]", FB2 p.19), so it is costed with the merchant crew rule.
MERCHANTS = [
    (19, "Sha'Ken", 'Light Freighter or Fleet Tender', 'M', 40, 97, 10, 2, "K1 SG FC H:18"),
]
# fmt: on

NOTES = {
    "To'Rok": "Shuttle bay holds 2 x MASS-2 interface shuttles (4 points each, not in the NPV).",
}


def check_against_text() -> None:
    """Every curated TMF/NPV must appear on its page's text layer."""
    doc = pymupdf.open(ROOT / "rulebooks" / "Fleet Book 2.pdf")
    problems = []
    for page, name, _label, _code, tmf, npv, *_ in WARSHIPS + MERCHANTS:
        text = " ".join(doc[page - 1].get_text().split())
        if f"TMF: {tmf}" not in text or f"NPV: {npv}" not in text or name not in text:
            problems.append(f"p{page} {name}: TMF {tmf} / NPV {npv} not on the page")
    if problems:
        sys.exit("\n".join(problems))


def build() -> list[dict]:
    return [
        design("fb", BOOK, page, FACTION, name, label, code, tmf, npv, systems,
               hull=hull, thrust=thrust, race="kravak", kind=kind, notes=NOTES.get(name, ""))
        for kind, rows in (("warship", WARSHIPS), ("merchant", MERCHANTS))
        for page, name, label, code, tmf, npv, hull, thrust, systems in rows
    ]


def main() -> None:
    check_against_text()
    designs = build()
    out = write("fb_fb2_kravak.json", designs)
    print(f"Wrote {out} ({len(designs)} Kra'Vak classes)")


if __name__ == "__main__":
    main()
