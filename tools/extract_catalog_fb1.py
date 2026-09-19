"""Build data/catalog/fb_fb1.json: the human classes of Fleet Book 1 (NAC, NSL, FSE, ESU, pp.13-41)
and the merchant and support vessels (p.42).

Hull integrity, armour grade, thrust, weapon counts, hangar bays and magazine capacity come from
each ship's TECHNICAL SPECIFICATIONS panel. Beam arcs come from tools/ssd_arcs.py rings(), launcher
and rack arcs from pies(); torpedo, submunition and merchant details were read off the rendered
SSD images (p.42 has no spec panels). The run checks every TMF and NPV against the page text
before writing, so a transcription slip fails here rather than in the NPV gate.

    python tools/extract_catalog_fb1.py
"""

from __future__ import annotations

import re
import sys

import pymupdf
from catalog_common import ROOT, design, write

BOOK = "FB1"
FP_F_FS = "F,FS,FP"
PORT = "F,AP,FP"
STBD = "F,FS,AS"

# (page, faction, name, type label, code, TMF, NPV, hull, armour, thrust, systems)
# fmt: off
WARSHIPS = [
    # NAC
    (13, 'NAC', 'Harrison', 'Scoutship', 'SC', 6, 21, 2, 0, 4, "B1 FC"),
    (13, 'NAC', 'Arapaho', 'Corvette', 'CT', 12, 41, 2, 1, 6, "B1*2 PDS FC"),
    (14, 'NAC', 'Minerva', 'Frigate', 'FF', 18, 61, 5, 0, 6, f"B1*2 B2:{FP_F_FS} PDS FC"),
    (14, 'NAC', 'Tacoma', 'Heavy Frigate', 'FF', 24, 81, 7, 0, 6, f"B1*2 B2:{PORT} B2:{STBD} PDS FC"),
    (15, 'NAC', 'Ticonderoga', 'Destroyer', 'DD', 30, 100, 9, 0, 6, f"B1*2 B2:{PORT} B2:{STBD} PDS*2 FC"),
    (15, 'NAC', 'Huron', 'Light Cruiser', 'CL', 50, 167, 15, 0, 6,
     f"B1*2 B2:{FP_F_FS} B2:{PORT} B2:{STBD} PDS*2 S1 FC*2"),
    (16, 'NAC', 'Furious', 'Escort Cruiser', 'CE', 64, 219, 19, 3, 4,
     f"B3:F B2:{PORT} B2:{STBD} B1 PT:F PDS*3 FC*2 ADFC S1"),
    (16, 'NAC', 'Vandenburg', 'Heavy Cruiser', 'CH', 80, 261, 24, 5, 6,
     f"B3:{FP_F_FS} B2:{PORT} B2:{STBD} B1 PDS*2 FC*2 S1"),
    (17, 'NAC', 'Majestic', 'Battlecruiser', 'BC', 106, 358, 32, 5, 4,
     f"B1*2 B3:{PORT} B3:{STBD} B2:all SML:{FP_F_FS} MAG:6 PDS*3 S1 FC*3"),
    (17, 'NAC', 'Victoria', 'Battleship', 'BB', 120, 406, 36, 5, 4,
     f"B2:all B1*2 B3:{PORT} B3:{FP_F_FS} B3:{STBD} PT:F*2 PDS*3 S1 FC*3"),
    (18, 'NAC', 'Excalibur', 'Battledreadnought', 'BDN', 140, 472, 42, 7, 4,
     f"B1*2 B3:{PORT} B3:{FP_F_FS} B3:{STBD} B2:all PT:F PDS*3 S1 FC*3 HB"),
    (18, 'NAC', 'Valley Forge', 'Superdreadnought', 'SDN', 190, 642, 57, 7, 4,
     f"B3:{FP_F_FS} B1*2 B3:{PORT} B2:all*2 B3:{STBD} PT:F*2 PDS*4 S1 FC*3 HB*2"),
    (19, 'NAC', 'Inflexible', 'Light Fleet Carrier', 'CVL', 140, 483, 28, 9, 4,
     "B1*2 B2:all PDS*4 S2 FC*2 HB*4"),
    (19, 'NAC', 'Ark Royal', 'Fleet Supercarrier', 'CVH', 200, 690, 40, 12, 4,
     "B1*2 B2:all*2 PDS*4 S2 FC*2 HB*6"),
    # NSL
    (20, 'NSL', 'Falke', 'Scoutship', 'SC', 8, 27, 2, 1, 6, "B1 FC"),
    (20, 'NSL', 'Stroschen', 'Corvette', 'CT', 14, 47, 4, 2, 4, f"B2:{FP_F_FS} PDS FC"),
    (21, 'NSL', 'Ehrenhold', 'Frigate', 'FF', 20, 67, 6, 2, 4, f"B2:{PORT} B2:{STBD} PDS FC"),
    (21, 'NSL', 'Waldburg', 'Destroyer', 'DD', 30, 100, 9, 3, 4, f"B1*2 B2:{PORT} B2:{STBD} PDS*2 FC"),
    (22, 'NSL', 'Waldburg/M', 'Missile Destroyer', 'DD', 30, 101, 9, 2, 4, f"B1 SML:{FP_F_FS} MAG:4 PDS FC"),
    (22, 'NSL', 'Kronprinz Wilhelm', 'Light Cruiser', 'CL', 48, 161, 14, 5, 4,
     f"B1*2 B2:{FP_F_FS} B2:{PORT} B2:{STBD} PDS*3 FC ADFC"),
    (23, 'NSL', 'Radetzky', 'Escort Cruiser', 'CE', 58, 195, 17, 6, 4,
     f"B2:{FP_F_FS}*2 B1*2 B2:{PORT} B2:{STBD} PDS*3 FC*2 ADFC"),
    (23, 'NSL', 'Markgraf', 'Heavy Cruiser', 'CH', 82, 271, 25, 10, 4,
     f"B1*2 B3:{FP_F_FS}*2 B2:{PORT} B2:{STBD} PDS*3 FC*2"),
    (24, 'NSL', 'Maximilian', 'Battlecruiser', 'BC', 100, 333, 30, 10, 4,
     f"B3:{FP_F_FS} B1*2 B3:{PORT} B3:{STBD} B2:{PORT} B2:{STBD} PDS*3 FC*3"),
    (24, 'NSL', 'Richthofen', 'Battlecruiser', 'BC', 104, 351, 31, 6, 4,
     f"B3:{FP_F_FS}*2 B1*2 B2:{PORT} B3:{PORT} B3:{STBD} B2:{STBD} PDS*3 FC*3"),
    (25, 'NSL', 'Maria Von Burgund', 'Battleship', 'BB', 120, 414, 36, 10, 2,
     f"B1*2 B3:{PORT} B3:{STBD} B2:{PORT} B2:{STBD} B3:{FP_F_FS} B3:{PORT} B3:{STBD} PT:{FP_F_FS} PDS*4 FC*4"),
    (25, 'NSL', 'Szent Istvan', 'Battledreadnought', 'BDN', 150, 500, 60, 14, 2,
     f"B1 B2:{PORT} B2:{STBD} B3:{FP_F_FS}*2 B3:{PORT} B3:{STBD} PDS*4 FC*4 HB"),
    (26, 'NSL', 'Von Tegetthoff', 'Superdreadnought', 'SDN', 200, 670, 80, 14, 2,
     f"B1*2 B3:{FP_F_FS}*2 B2:all*4 B3:{PORT} B3:{STBD} SML:{FP_F_FS} MAG:8 PDS*4 FC*4 HB"),
    (26, 'NSL', 'Der Theuerdank', 'Fighter Carrier', 'CV', 220, 737, 88, 14, 2,
     f"B1*2 B2:all*3 B3:{PORT} B3:{STBD} B3:{FP_F_FS} PDS*6 FC*3 HB*4"),
    # FSE
    (27, 'FSE', 'Mistral', 'Scoutship', 'SC', 8, 28, 2, 0, 6, "B1*2 FC"),
    (27, 'FSE', 'Athena', 'Corvette', 'CT', 14, 48, 4, 0, 6, "B1*2 SM:F PDS FC"),
    (28, 'FSE', 'Ibiza', 'Frigate', 'FF', 18, 61, 5, 0, 6, "B1*2 SM:F*2 PDS FC"),
    (28, 'FSE', 'San Miguel', 'Destroyer', 'DD', 34, 112, 10, 2, 6, f"B1*2 B2:{PORT} B2:{STBD} PDS*2 FC"),
    (29, 'FSE', 'Trieste', 'Super Destroyer', 'DH', 42, 139, 13, 0, 6,
     f"B1 B2:{FP_F_FS} SML:{FP_F_FS} MAG:4 PDS FC"),
    (29, 'FSE', 'Suffren', 'Light Cruiser', 'CL', 54, 181, 16, 0, 6,
     f"B2:{PORT} B2:{STBD} SML:{FP_F_FS} MAG:6 PDS*2 FC*2"),
    (30, 'FSE', 'Milan', 'Escort Cruiser', 'CE', 62, 206, 19, 0, 6,
     f"B1 B2:{PORT} B2:{STBD} SML:{FP_F_FS} MAG:6 PDS*2 FC*2"),
    (30, 'FSE', 'Jerez', 'Heavy Cruiser', 'CH', 88, 293, 26, 0, 6,
     f"B1*2 B2:{PORT} B2:all B2:{STBD} SML:{FP_F_FS}*2 MAG:8 PDS*2 FC*2"),
    (31, 'FSE', 'Ypres', 'Battlecruiser', 'BC', 96, 318, 29, 0, 6,
     f"B1*2 B2:{PORT} B2:{STBD} B2:all SML:{FP_F_FS} MAG:6 PDS*3 S1 FC*2"),
    (31, 'FSE', 'Roma', 'Battleship', 'BB', 110, 377, 33, 0, 4,
     f"B1*2 B2:{PORT} B2:{STBD} B2:all B2:{PORT} B2:{STBD} SML:{PORT} SML:{STBD} MAG:12 PDS*4 S1 FC*3"),
    (32, 'FSE', 'Bonaparte', 'Battledreadnought', 'BDN', 160, 531, 48, 0, 6,
     f"B1*2 B2:{PORT} B2:{STBD} B3:F B2:all SML:{FP_F_FS} MAG:8 PDS*4 S1 FC*3 HB"),
    (32, 'FSE', 'Foch', 'Superdreadnought', 'SDN', 250, 855, 75, 0, 4,
     f"B2:all B3:{FP_F_FS}*2 B2:all B2:{PORT} B2:{STBD} SML:{PORT} SML:{FP_F_FS} SML:{STBD} "
     f"MAG:18 PDS*6 S1 FC*5 HB*3"),
    (33, 'FSE', 'Bologna', 'Light Carrier', 'CVL', 170, 580, 51, 0, 4,
     f"B1*2 B2:all*2 SML:{FP_F_FS} MAG:6 PDS*4 S1 FC*2 HB*4"),
    (33, 'FSE', "Jeanne D'Arc", 'Fleet Carrier', 'CVH', 280, 955, 84, 0, 4,
     f"B2:all B3:{FP_F_FS} B2:{FP_F_FS} B3:{FP_F_FS} SML:{FP_F_FS} MAG:6 PDS*6 S1 FC*3 HB*7"),
    # ESU
    (34, 'ESU', 'Lenov', 'Scoutship', 'SC', 6, 21, 1, 0, 8, "B1 FC"),
    (34, 'ESU', 'Nanuchka II', 'Corvette', 'CT', 14, 48, 4, 0, 6, f"B1 B2:{FP_F_FS} PDS FC"),
    (35, 'ESU', 'Novgorod', 'Frigate', 'FF', 22, 73, 7, 0, 6, f"B1*2 B2:{FP_F_FS} PDS FC"),
    (35, 'ESU', 'Warsaw', 'Destroyer', 'DD', 28, 93, 8, 3, 4, f"B1*2 B2:{PORT} B2:{STBD} PDS FC"),
    (36, 'ESU', 'Volga', 'Super Destroyer', 'DH', 34, 115, 10, 2, 4,
     f"B1*2 B2:all B2:{PORT} B2:{STBD} PDS*2 FC"),
    (36, 'ESU', 'Tibet', 'Light Cruiser', 'CL', 48, 162, 14, 3, 4,
     f"B2:all B1*2 B2:{PORT} B2:{STBD} PDS*2 S1 FC*2"),
    (37, 'ESU', 'Beijing/B', 'Escort Cruiser', 'CE', 60, 201, 18, 5, 4,
     f"B1*2 B3:{FP_F_FS} B2:{PORT} B2:{STBD} PDS*2 S1 FC*2"),
    (37, 'ESU', 'Gorshkov', 'Heavy Cruiser', 'CH', 70, 240, 21, 0, 4,
     f"B1*2 B2:{PORT} B2:{STBD} B3:{FP_F_FS} SMR:{FP_F_FS}*2 PDS*2 S1 FC*2"),
    (38, 'ESU', 'Voroshilev', 'Heavy Cruiser', 'CH', 78, 262, 23, 5, 4,
     f"B3:{FP_F_FS}*2 B1*2 B2:{PORT} B2:{STBD} PDS*2 S1 FC*2"),
    (38, 'ESU', 'Manchuria', 'Battlecruiser', 'BC', 94, 312, 38, 0, 4,
     f"B1 B3:{FP_F_FS}*2 B2:{FP_F_FS} B2:{PORT} B2:{STBD} PDS*2 S1 FC*2"),
    (39, 'ESU', 'Petrograd', 'Battleship', 'BB', 116, 386, 46, 0, 4,
     f"B3:{FP_F_FS} B1 B3:{FP_F_FS} B2:{FP_F_FS}*2 B1*2 B2:{PORT} B2:{STBD} PDS*3 S1 FC*3"),
    (39, 'ESU', 'Rostov', 'Battledreadnought', 'BDN', 138, 458, 55, 0, 4,
     f"B1 B2:{PORT} B2:{STBD} B2:{FP_F_FS} B3:{PORT} B3:{STBD} PDS*3 S1 FC*3 HB"),
    (40, 'ESU', 'Tsiolkovsky', 'Light Carrier', 'CVL', 150, 512, 45, 0, 4,
     f"B1*2 B2:{FP_F_FS}*2 B2:{PORT} B2:{STBD} PDS*4 S1 FC*2 HB*4"),
    (40, 'ESU', 'Komarov', 'Superdreadnought', 'SDN', 220, 751, 88, 0, 2,
     f"B1*2 B2:{PORT} B2:{STBD} B3:{FP_F_FS}*2 B3:{PORT} B3:{STBD} B4:F,FP B4:F,FS PDS*4 S2 FC*3 HB"),
    (41, 'ESU', 'Konstantin', 'Attack Carrier', 'CVA', 240, 842, 72, 0, 2,
     f"B1*2 B2:{PORT}*2 B3:{FP_F_FS}*2 B3:{PORT} B3:{STBD} B2:{STBD}*2 PDS*6 S2 FC*2 HB*6"),
]
# fmt: on

# FB1 p.42 (no spec panels; read from the SSDs): (name, TMF, NPV, hull, thrust, systems)
# fmt: off
MERCHANTS = [
    ('Heavy Freighter', 120, 195, 12, 2, 'PDS H:83'),
    ('Medium Freighter', 80, 131, 8, 2, 'PDS H:55'),
    ('Light Freighter', 40, 67, 4, 2, 'PDS H:27'),
    ('Free Trader', 20, 47, 4, 4, 'B1 FC H:8'),
    ('Fleet Auxiliary', 100, 193, 20, 2, 'B1 FC PDS*2 H:56'),
    ('Assault Transport', 120, 337, 24, 2, 'B1 S1 PDS*2 FC TB:20 T:32'),
    ('Bulk Carrier', 200, 303, 20, 1, 'PDS H:149'),
    ('Starliner', 120, 205, 12, 2, 'B1 FC PDS*2 P:80'),
]
# fmt: on
NOTES = {
    "Assault Transport": "Carries four MASS 5 assault dropships in its tender bay: +40 points (FB1 p.42).",
}


def check_against_text() -> None:
    """Every curated TMF/NPV must appear on its page's text layer."""
    doc = pymupdf.open(ROOT / "rulebooks" / "Fleet Book 1.pdf")
    problems = []
    for page, _f, name, _l, _c, tmf, npv, *_ in WARSHIPS:
        text = " ".join(doc[page - 1].get_text().split())
        if f"TMF: {tmf}" not in text or f"NPV: {npv}" not in text or name not in text:
            problems.append(f"p{page} {name}: TMF {tmf} / NPV {npv} not on the page")
    text = " ".join(doc[41].get_text().split())
    for name, tmf, npv, *_ in MERCHANTS:
        if not re.search(rf"{name.upper()} Mass {tmf} \W {npv}\*? Points", text):
            problems.append(f"p42 {name}: Mass {tmf} / {npv} Points not on the page")
    if problems:
        sys.exit("\n".join(problems))


def build() -> list[dict]:
    designs = [
        design(
            "fb",
            BOOK,
            page,
            faction,
            name,
            label,
            code,
            tmf,
            npv,
            systems,
            hull=hull,
            armour=armour,
            thrust=thrust,
        )
        for page, faction, name, label, code, tmf, npv, hull, armour, thrust, systems in WARSHIPS
    ]
    designs += [
        design(
            "fb",
            BOOK,
            42,
            None,
            name,
            name,
            "M",
            tmf,
            npv,
            systems,
            hull=hull,
            thrust=thrust,
            kind="merchant",
            notes=NOTES.get(name, ""),
        )
        for name, tmf, npv, hull, thrust, systems in MERCHANTS
    ]
    return designs


def main() -> None:
    check_against_text()
    out = write("fb_fb1.json", build())
    print(f"Wrote {out} ({len(WARSHIPS)} warships, {len(MERCHANTS)} merchant and support vessels)")


if __name__ == "__main__":
    main()
