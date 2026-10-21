"""Build data/catalog/fb_starranger.json: the Fleet Book designs on the Star Ranger fleet pages
(fullthrust.star-ranger.com), "Authorized by GZG for use until Official stats are published."

The pages extend the four FB1 powers and add new ones (Islamic Federation, Imperial Japanese Star
Fleet, New Israel, Oceanic Union, Outer Rim Coalition, Scandinavian Federation, United Nations
Space Command, Free Cal-Tex, the Ravager pirates), plus more Kra'Vak, Sa'Vasku and Phalon
classes. Every stat block was read off the page text: TMF, NPV, hull boxes and their row split,
armour, thrust, then the systems, each count printed before its label ("1 Fire Control2 PDS"
is one fire control and two PDS). The site's own rules decide the rest:

- hull rows: three rows price a box at 3 points (thresholds 6 and 5), five at 1.5 and six at 1;
  a split printed with three places, "(1/1/)", is a three-row hull;
- "mass penalty for age N" / "N mass not used to show age" is MASS the ship carries unused;
- an EMP battery costs as the beam of its class and arcs; a graser follows the CD table at
  4 points a MASS (3 on the NAC's no-re-roll version); an anti-matter torpedo is MASS 2, 8 points.

A variant the page gives only as a change to its parent ("replace the B4 with 2 pulse torpedoes")
is built from the parent with that change. Where the page prints no NPV for it, the catalog
leaves the printed value at 0 and the app's own cost stands.

    python tools/extract_catalog_starranger.py
"""

from __future__ import annotations

import sys

from catalog_common import ROOT, design, write

sys.path.insert(0, str(ROOT))
from rulesets import common  # noqa: E402
from rulesets.fb import data as fb_data  # noqa: E402

BOOK = "SR"
SITE = "https://fullthrust.star-ranger.com/"
F3 = "FP,F,FS"
P = "AP,FP,F"
S = "F,FS,AS"
FP2 = "FP,F"
FS2 = "F,FS"
P5 = "AP,FP,F,FS,AS"

# Each fleet page: (faction, page file, [ships]).
# A ship: (name, type label, TMF, NPV, hull, armour, thrust, systems[, extras]).
# extras: rows (hull rows, default 4), ftl (False for none), note, kind, race, layers.
# fmt: off
NAC_FBR = [
    ("Miyazaki", "Frigate", 18, 61, 5, 0, 6, "B1*4 PDS FC", {"note": "Theoretical stats of an official class."}),
    ("Minerva/A", "Frigate", 18, 63, 5, 0, 6, "B1 ADFC PDS*2 FC", {"note": "Official variant of the FB1 Minerva."}),
    ("Tacoma/A", "Heavy Frigate", 24, 83, 7, 0, 6, f"B1 B2:{F3} ADFC PDS*2 FC", {"note": "Official variant of the FB1 Tacoma."}),
    ("Tacoma/T", "Heavy Frigate", 24, 81, 7, 0, 6, "B1*2 PT:F PDS FC", {"note": "Official variant of the FB1 Tacoma."}),
    ("Ticonderoga (pre-refit)", "Destroyer", 30, 94, 9, 0, 6, f"B1*3 B2:{F3} PDS FC AGE:2",
     {"note": "The FB1 Ticonderoga before its refit. The page's systems leave 2 MASS unused, carried here as lost to age."}),
    ("Hoshino", "Light Cruiser", 50, 164, 15, 0, 6, f"B1*2 B2:{F3} B2:all PDS*2 S1 FC*2 AGE:1"),
    ("Furious/M", "Escort Cruiser", 64, 217, 19, 3, 4, f"B1*2 B2:{P} B2:{S} SML:{F3} MAG:6 PDS*3 S1 FC*2", {"note": "Official variant of the FB1 Furious."}),
    ("Vandenburg/T", "Heavy Cruiser", 80, 269, 24, 5, 4, f"B1 B2:{P} B2:{S} B3:{F3} PT:F*2 PDS*2 S1 FC*2", {"note": "Official variant of the FB1 Vandenburg."}),
    ("Lion", "Battlecruiser", 100, 338, 30, 5, 4, f"B1 B2:all B3:{P} B3:{S} PT:F*2 PDS*3 S1 FC*3"),
    ("Repulse", "Battlecruiser", 96, 324, 29, 5, 4, f"B1*2 B2:{P} B2:{S} B3:{P} B3:{S} PT:F PDS*3 S1 FC*3"),
    ("Sioux", "Battlecruiser", 108, 356, 32, 4, 6, f"B1 B2:all B2:{P} B2:{S} B3:{F3} PT:F PDS*3 S1 FC*3"),
    ("Howe", "Battleship", 130, 439, 39, 8, 4, f"B1 B2:{P} B2:{S} B3:{P} B3:{S} SML:{F3} MAG:6 PDS*6 ADFC S1 FC*3"),
    ("Vanguard", "Battleship", 120, 403, 36, 8, 4, f"B1*2 B2:{P} B2:{S} B3:{F3} PT:F*4 PDS*3 S1 FC*3"),
    ("Avalon", "Battledreadnought", 126, 417, 38, 5, 4, f"B1*2 B2:all B3:{P} B3:{F3} PT:F PDS*3 S1 FC*3 HB AGE:3"),
    ("Eastwood", "Superdreadnought", 170, 558, 51, 5, 4, f"B1*2 B2:all*2 B2:{P} B2:{S} B3:{F3}*2 PDS*3 S1 FC*3 HB*2 AGE:6"),
    ("Valley Forge/S", "Superdreadnought", 190, 642, 57, 7, 4, f"B1*2 B2:all*2 B3:{P} B3:{S} B3:{F3} PT:F*2 SML:{F3} MAG:6 PDS*4 S1 FC*3 HB"),
    ("Valley Forge/M", "Superdreadnought", 190, 642, 57, 7, 4, f"B1*2 B2:all*2 B3:{P} B3:{S} B3:{F3} PT:F*2 SML:{F3}*2 MAG:12 PDS*4 S1 FC*3", {"note": "Richmond/Agincourt subclass."}),
    ("Saratoga", "Fleet Supercarrier", 190, 647, 38, 8, 4, "B1*2 B2:all PDS*3 S2 FC*2 HB*6 AGE:4"),
]

NAC_STATS = [
    ("Arrow", "Scout", 7, 26, 2, 0, 7, "B1 FC", {"rows": 3}),
    ("Gladius", "Lancer", 10, 37, 2, 0, 6, "B1 SM:F*2 FC", {"rows": 3}),
    ("Comanche", "Corvette", 14, 51, 3, 1, 6, f"B1 B2:{F3} PDS FC", {"rows": 3}),
    ("Troutbridge", "Frigate", 20, 67, 5, 1, 6, f"B1*2 B2:{F3} PDS FC"),
    ("Cambridge", "Torpedo Frigate", 23, 77, 6, 1, 6, "B1 PT:F PDS FC"),
    ("Achilles", "Heavy Frigate", 26, 87, 7, 0, 6, f"B1 B2:{F3} B2:all PDS FC"),
    ("Achilles/E", "Heavy Frigate", 26, 89, 7, 0, 6, "B1 ADFC PDS*4 FC"),
    ("Tallahachie", "Destroyer", 34, 113, 9, 2, 6, f"B1*2 B2:{F3} B2:all PDS*2 FC"),
    ("Tulsa", "Heavy Destroyer", 42, 139, 11, 2, 6, "B1*2 B2:all PT:F PDS*2 FC"),
    ("Lancaster", "Light Cruiser", 54, 180, 15, 2, 6, f"B1*2 B2:{P} B2:{S} B2:all PDS*2 S1 FC*2"),
    ("Lancaster/B", "Light Cruiser", 54, 180, 15, 2, 6, f"B1*2 B2:{P} B2:{S} B3:{F3} PDS*2 FC*2"),
    ("Suffolk", "Escort Cruiser", 64, 213, 18, 2, 6, f"B1*2 B2:{P} B2:{S} B3:{F3} PDS*2 S1 FC*2"),
    ("Suffolk/E", "Escort Cruiser", 64, 213, 18, 2, 6, f"B1*2 B2:{P} B2:{S} ADFC PDS*6 S1 FC*2"),
    ("Tiger", "Strike Cruiser", 70, 238, 20, 3, 4, f"B1 B2:{P} B2:{S} B2:all PT:{FP2} PT:{FS2} PDS*2 S1 FC*2"),
    ("Battleaxe", "Heavy Cruiser", 78, 262, 23, 5, 4, f"B1 B2:{F3} B2:all B3:{P} B3:{S} PDS*2 S1 FC*2"),
    ("Renown", "Battlecruiser", 100, 338, 30, 5, 4, f"B1 B2:{F3} B2:all B3:{P} B3:{S} PT:{F3} PDS*3 S1 FC*3"),
    ("Thunderer", "Battleship", 127, 429, 38, 6, 4, f"B1*2 B2:all B3:{F3} B3:{P} B3:{S} PT:{FP2} PT:{FS2} PDS*3 S1 FC*3"),
    ("Farragut", "Battledreadnought", 159, 535, 48, 8, 4, f"B1*2 B2:{F3} B2:all B3:{P} B3:{S} B4:{F3} PDS*4 S1 FC*3 HB"),
    ("Farragut/T", "Battledreadnought", 159, 0, 48, 8, 4, f"B1*2 B2:{F3} B2:all B3:{P} B3:{S} PT:{F3}*2 PDS*4 S1 FC*3 HB",
     {"note": "Pulse torpedo version: the class-4 battery becomes two torpedoes. The page prints no NPV."}),
    ("Farragut/G", "Battledreadnought", 159, 0, 48, 8, 4, f"B1*2 B2:{F3} B2:all B3:{P} B3:{S} G2:{FP2}:nr PDS*4 S1 FC*3 HB",
     {"note": "Graser version: the class-4 battery becomes a class-2 graser that may not re-roll (3 points a MASS). The page prints no NPV."}),
    ("Trafalgar", "Superdreadnought", 210, 711, 62, 8, 4, f"B1*2 B2:{F3} B2:all B3:{F3} B3:{P} B3:{S} B4:{F3}*2 PDS*4 S1 FC*4 HB"),
    ("Trafalgar/T", "Superdreadnought", 210, 0, 62, 8, 4, f"B1*2 B2:{F3} B2:all B3:{F3} B3:{P} B3:{S} PT:{F3}*4 PDS*4 S1 FC*4 HB",
     {"note": "Pulse torpedo version: the two class-4 batteries become four torpedoes. The page prints no NPV."}),
    ("Trafalgar/G", "Superdreadnought", 210, 0, 62, 8, 4, f"B1*2 B2:{F3} B2:all B3:{F3} B3:{P} B3:{S} G2:{FP2}:nr G2:{FS2}:nr PDS*4 S1 FC*4 HB",
     {"note": "Graser version: the two class-4 batteries become class-2 grasers that may not re-roll (3 points a MASS). The page prints no NPV."}),
    ("Fearless", "Escort Carrier", 80, 273, 20, 4, 4, f"B1*2 B2:{P} B2:{S} PDS*3 S1 FC HB*2"),
    ("Midway", "Light Carrier", 149, 505, 40, 8, 4, f"B1*2 B2:{F3} B2:all PDS*4 S1 FC*2 HB*4"),
    ("Nimitz", "Heavy Carrier", 240, 822, 60, 8, 4, f"B1*2 B2:{F3} B2:all*2 PDS*4 S1 FC*2 HB*8"),
    ("Albion", "Battle Carrier", 214, 727, 60, 8, 4, f"B1 B2:all B3:{P} B3:{S} B4:{F3} PDS*4 S1 FC*3 HB*4"),
    ("Albion/T", "Battle Carrier", 214, 0, 60, 8, 4, f"B1 B2:all B3:{P} B3:{S} PT:{F3}*2 PDS*4 S1 FC*3 HB*4",
     {"note": "Pulse torpedo version: the class-4 battery becomes two torpedoes. The page prints no NPV."}),
    ("Albion/G", "Battle Carrier", 214, 0, 60, 8, 4, f"B1 B2:all B3:{P} B3:{S} G2:{FS2}:nr PDS*4 S1 FC*3 HB*4",
     {"note": "Graser version: the class-4 battery becomes a class-2 graser that may not re-roll (3 points a MASS). The page prints no NPV."}),
    ("Galahad", "Assault Ship", 120, 337, 24, 0, 2, "B1 TB:20 T:32 PDS*2 S1 FC", {"note": "The FB1 p.42 Assault Transport as a named class."}),
]

ESU_FBR = [
    ("Nanuchka I", "Corvette", 13, 41, 4, 0, 6, "B1*2 FC AGE:1"),
    ("Riga", "Frigate", 20, 64, 6, 0, 6, f"B1 B2:{F3} PDS FC AGE:1"),
    ("Grisha", "Frigate", 22, 73, 7, 2, 4, "B1*2 B2:all PDS FC"),
    ("Krivak", "Destroyer", 26, 84, 10, 0, 4, f"B1*3 B2:{F3} PDS FC AGE:1"),
    ("Beijing/A", "Escort Cruiser", 60, 195, 22, 1, 4, f"B1*2 B2:{F3}*2 B2:{P} B2:{S} PDS*2 S1 FC*2 AGE:2",
     {"note": "The page's fire-control count is garbled; two fire controls close the MASS and the printed NPV."}),
    ("Beijing/E", "Escort Cruiser", 60, 203, 18, 5, 4, f"B1*2 B2:{P} B2:{S} ADFC PDS*6 S1 FC*2"),
    ("Slava", "Battlecruiser", 90, 293, 36, 0, 4, f"B1*2 B2:{P} B2:{S} B3:{FP2} B3:{FS2} PDS*2 S1 FC*2 AGE:2"),
    ("Sverdlov", "Battleship", 112, 364, 45, 0, 4, f"B1*3 B2:{F3} B2:{P} B2:{S} B3:{FP2} B3:{FS2} PDS*3 S1 FC*3 AGE:3"),
    ("Vostok", "Battledreadnought", 136, 453, 54, 0, 2, f"B1*2 B2:{P} B2:{S} B2:{F3} B3:{P} B3:{S} B4:F PDS*3 S1 FC*3 HB AGE:4"),
]

ESU_STATS = [
    ("Zheng He", "Scoutship", 8, 28, 1, 1, 8, "B1 FC", {"rows": 3}),
    ("Cossack", "Strikeboat", 14, 51, 1, 1, 6, f"B1 SMR:{F3}:er FC", {"rows": 3}),
    ("Poryshkin", "Corvette", 18, 61, 4, 1, 6, f"B2:{F3}*2 PDS FC"),
    ("Kunitsa", "Frigate", 24, 80, 7, 1, 6, f"B2:{F3} B2:all PDS FC"),
    ("Ural", "Destroyer", 34, 114, 9, 1, 6, f"B2:{F3}*3 B2:all PDS FC"),
    ("Ural (Fleet)", "Destroyer", 34, 116, 10, 1, 4, f"B2:{F3}*2 B2:all PDS*2 S1 FC", {"note": "Fleet variant of the Ural."}),
    ("Kunlun", "Heavy Destroyer", 48, 163, 11, 2, 6, f"B2:{F3} B2:{P} B2:{S} B2:all ADFC PDS*4 FC"),
    ("Kiang", "Light Cruiser", 54, 182, 17, 3, 4, f"B2:{F3}*2 B2:{P} B2:{S} B2:all PDS*2 S1 FC*2"),
    ("Oriskansky", "Escort Cruiser", 67, 227, 21, 4, 4, f"B2:{F3}*2 B2:{P} B2:{S} B2:all ADFC PDS*4 S1 FC*2"),
    ("Xinglong", "Heavy Cruiser", 89, 300, 26, 5, 4, f"B2:{P} B2:{S} B2:all*2 B3:{F3}*2 PDS*3 S1 FC*2"),
    ("Pobyeda", "Battlecruiser", 107, 364, 31, 5, 4, f"B2:{P}*2 B2:{S}*2 B2:all*2 B3:{F3}*2 ADFC PDS*4 S1 FC*2"),
    ("Khalinov", "Battleship", 140, 475, 42, 6, 4, f"B2:{P} B2:{S} B2:all*2 B3:{F3}*2 B3:{P} B3:{S} ADFC PDS*4 S1 FC*3"),
    ("Khalinov (Big Gun)", "Battleship", 140, 0, 42, 6, 4, f"B2:{P}*2 B2:{S}*2 B2:all*2 B4:{FP2} B4:{FS2} ADFC PDS*4 S1 FC*3",
     {"note": "Alternate big-gun fit: the four class-3 batteries become two class-4 (F/FP, F/FS) and two class-2 (F/FP/AP, F/FS/AS). The page prints no NPV."}),
    ("Morov", "Battledreadnought", 180, 609, 55, 7, 4, f"B2:{P} B2:{S} B2:all*3 B3:{F3}*2 B3:{P} B3:{S} ADFC PDS*4 S2 FC*3"),
    ("Morov (Big Gun)", "Battledreadnought", 180, 0, 55, 7, 4, f"B2:{P}*2 B2:{S}*2 B2:all*3 B4:{FP2} B4:{FS2} ADFC PDS*4 S2 FC*3",
     {"note": "Alternate big-gun fit: the four class-3 batteries become two class-4 (F/FP, F/FS) and two class-2 (F/FP/AP, F/FS/AS). The page prints no NPV."}),
    ("Zhukov", "Superdreadnought", 242, 818, 77, 7, 4, f"B2:{P} B2:{S} B2:all*3 B3:{F3} B3:{P}*2 B3:{S}*2 ADFC PDS*4 S2 FC*4 HB"),
    ("Zhukov (Big Gun)", "Superdreadnought", 242, 0, 77, 7, 4, f"B2:{P} B2:{S} B2:all*3 B3:{F3} B4:{P} B4:{S} ADFC PDS*4 S2 FC*4 HB",
     {"note": "Alternate big-gun fit: the four broadside class-3 batteries become two class-4 (F/FP/AP, F/FS/AS). The page prints no NPV."}),
    ("Nanjing", "Escort Carrier", 104, 359, 26, 4, 4, f"B2:{F3} B2:{P} B2:{S} B2:all*2 ADFC PDS*4 S1 FC*2 HB*2"),
    ("Changchun", "Light Carrier", 182, 618, 55, 5, 4, f"B2:{F3} B2:{P} B2:{S} B2:all*3 ADFC PDS*4 S1 FC*2 HB*4"),
    ("Shengfeng", "Heavy Carrier", 289, 1007, 77, 6, 3, f"B2:all*3 B3:{F3} B3:{P}*2 B3:{S}*2 ADFC PDS*6 S2 FC*4 HB*6"),
    ("Shengfeng (High Thrust)", "Heavy Carrier", 289, 992, 77, 6, 4, f"B2:all*3 B3:{F3} B3:{P}*2 B3:{S}*2 ADFC PDS*6 S1 FC*4 HB*6",
     {"note": "Alternate high-thrust fit: thrust 4 and level-1 screens."}),
    ("Shengfeng (Big Gun)", "Heavy Carrier", 289, 0, 77, 6, 3, f"B2:all*3 B3:{F3} B4:{P} B4:{S} ADFC PDS*6 S2 FC*4 HB*6",
     {"note": "Alternate big-gun fit: the four broadside class-3 batteries become two class-4 (F/FP/AP, F/FS/AS). The page prints no NPV."}),
]

FSE_FBR = [
    ("Ianesco", "Frigate", 18, 61, 5, 0, 6, f"B1 B2:{F3} SM:F PDS FC"),
    ("Flaubert", "Frigate", 21, 71, 6, 0, 6, f"B1*2 B2:{F3} SM:F PDS FC"),
    ("San Miguel/M", "Destroyer", 34, 112, 10, 2, 6, f"B1*2 SMR:{F3} PDS*2 FC"),
    ("Suffren/A", "Light Cruiser", 54, 181, 16, 0, 6, f"B2:{P} B2:{S} B1*2 SML:{F3} MAG:4 PDS*2 FC*2",
     {"note": "Variant of the FB1 Suffren: two reloads in the magazine and two class-1 batteries added."}),
    ("Suffren/B", "Light Cruiser", 54, 181, 16, 0, 6, f"B2:{P} B1*2 SML:{F3} MAG:6 PDS*2 FC*2",
     {"note": "Variant of the FB1 Suffren: one class-2 battery replaced by two class-1."}),
    ("Suffren/C", "Light Cruiser", 54, 181, 16, 0, 6, f"B2:{P} B2:{S} SMR:{F3}*2 B1 PDS*2 FC*2",
     {"note": "Variant of the FB1 Suffren: launcher and magazine replaced by two salvo missile racks and a class-1 battery."}),
    ("Ypres", "Battlecruiser", 96, 318, 29, 0, 6, f"B1*2 B2:{P} B2:{S} B2:all SML:F*2 MAG:8 PDS*3 FC*2"),
    ("Zara", "Battleship", 124, 413, 37, 0, 6, f"B1*2 B2:{P} B2:{S} B2:{F3} B2:all SML:{F3}*2 MAG:8 PDS*4 S1 FC*3"),
    ("Santiago", "Battleship", 120, 411, 36, 0, 4, f"B1*2 B2:{P}*2 B2:{S}*2 B2:all B3:{F3} SML:{F3}*2 MAG:10 PDS*4 S1 FC*3"),
    ("Garibaldi", "Battledreadnought", 132, 440, 40, 0, 4, f"B1*3 B2:{P} B2:{S} B2:all*2 SML:{F3} MAG:10 PDS*4 S1 FC*3 HB AGE:4"),
    ("Aragon", "Heavy Battleship", 140, 479, 42, 0, 4, f"B1*2 B2:{P} B2:{S} B2:all B3:{F3} SML:FP SML:FS MAG:12 PDS*4 S1 FC*3 HB"),
    ("Veneto", "Heavy Battleship", 140, 465, 42, 0, 6, f"B1 B2:{P} B2:{S} B2:all SML:F MAG:8 PDS*4 S1 FC*3 HB"),
    ("Chirac", "Superdreadnought", 204, 683, 61, 0, 4, f"B1*2 B2:{F3} B2:{P} B2:{S} B2:all*2 B3:{F3} SML:{P} SML:{S} MAG:14 PDS*5 S1 FC*4 HB*2 AGE:5"),
]

FSE_STATS = [
    ("Requin", "Strikeboat", 10, 36, 1, 1, 8, "SM:F*3 FC", {"rows": 3, "ftl": False}),
    ("Cygne", "Scoutship", 8, 29, 2, 0, 8, "B1 FC", {"rows": 3}),
    ("Daphne", "Corvette", 14, 48, 4, 0, 6, "B1 SM:F*2 PDS FC"),
    ("Lemnos", "Frigate", 20, 67, 6, 0, 6, f"B1 B2:{F3} SM:F PDS FC"),
    ("Esperance", "Heavy Frigate", 26, 86, 8, 0, 6, f"B1 B2:{F3} SM:F*2 PDS FC"),
    ("Hydra", "Destroyer", 31, 104, 9, 0, 6, f"B1*2 B2:{F3} SM:F*3 PDS*2 FC"),
    ("Hydra/C", "Destroyer", 31, 0, 9, 0, 6, f"B1*2 B2:{F3}*2 SM:F PDS*2 FC",
     {"note": "Epée variant: a second class-2 battery replaces two submunition packs. The page prints no NPV."}),
    ("Thetis", "Destroyer", 34, 114, 10, 0, 6, f"B1*2 B2:{F3} SMR:{F3} PDS*2 FC"),
    ("Galiano", "Heavy Destroyer", 40, 133, 12, 0, 6, f"B1 B2:{P} B2:{S} SMR:{F3} PDS*2 FC"),
    ("Ardennes", "Light Cruiser", 56, 186, 17, 0, 6, f"B1 B2:{P} B2:{S} B2:all SMR:{F3} PDS*2 FC*2"),
    ("Colbert", "Escort Cruiser", 68, 227, 20, 0, 6, f"B1*2 B2:{P} B2:{F3} B2:{S} SML:F MAG:6 PDS*2 FC*2"),
    ("Colbert/E", "Escort Cruiser", 68, 229, 20, 0, 6, f"B1*2 B2:{P} B2:{S} SML:F MAG:4 ADFC PDS*4 FC*2"),
    ("Tourville", "Heavy Cruiser", 84, 279, 26, 0, 6, f"B1*2 B2:{F3}*2 B2:all*2 SML:{F3} MAG:6 PDS*2 FC*2"),
    ("Duquesne", "Battlecruiser", 98, 326, 30, 0, 6, f"B1 B2:{P} B2:{S} B2:all B3:{F3} SML:{F3} MAG:6 PDS*3 FC*3"),
    ("Da Silva", "Battleship", 120, 407, 40, 0, 4, f"B1*2 B2:{F3} B2:all B2:{P}*2 B2:{S}*2 B3:{F3} SML:{P} SML:{S} MAG:10 PDS*4 FC*3"),
    ("Littorio", "Battledreadnought", 170, 580, 54, 0, 4, f"B1*2 B2:{P} B2:{S} B2:all*2 B3:{F3}*2 SML:{P} SML:{S} MAG:8 ADFC PDS*6 S1 FC*3 HB"),
    ("Charlemagne", "Superdreadnought", 260, 889, 80, 0, 4, f"B2:all*3 B2:{P} B2:{S} B3:{F3}*2 SML:{P} SML:{F3} SML:{S} MAG:24 ADFC PDS*6 S1 FC*5 HB*2"),
    ("Velasco", "Orbital Assault Ship", 92, 292, 27, 0, 4, "B1*2 ORTILLERY*3 TB:10 T:8 PDS*2 FC*2"),
    ("Centauro", "Escort Carrier", 90, 302, 24, 0, 6, f"B1*2 B2:{F3} B2:all PDS*3 FC*2 HB*2"),
    ("Stromboli", "Light Carrier", 140, 480, 40, 0, 4, f"B1*2 B2:{F3} B2:all SML:{F3} MAG:6 PDS*4 FC*2 HB*4"),
    ("Affondatore", "Strike Carrier", 180, 620, 48, 0, 4, f"B1*2 B2:{P} B2:{S} B2:all SML:{P} SML:{S} MAG:12 PDS*4 S1 FC*2 HB*4"),
    ("Affondatore/A", "Strike Carrier", 180, 620, 48, 0, 4, f"B1*2 B2:{P} B2:{S} B2:all PDS*4 S1 FC*2 HB*6"),
    ("Richelieu", "Heavy Carrier", 290, 998, 78, 0, 4, f"B2:{F3} B2:{P} B2:{S} B3:{F3}*2 SML:{F3} MAG:8 PDS*6 S1 FC*3 HB*8"),
    ("Richelieu/S", "Heavy Carrier", 290, 998, 78, 0, 4, f"B2:{F3} B2:{P} B2:{S} B3:{F3}*2 SML:{F3}*3 MAG:20 PDS*6 S1 FC*3 HB*6"),
]

NSL_FBR = [
    ("Falke/S", "Scoutship", 8, 60, 2, 0, 6, "B1 SM:F FC", {"rows": 3, "note": "Official strike variant of the FB1 Falke, armour removed."}),
    ("Nibelung (old)", "Frigate", 18, 60, 5, 2, 4, f"B1 B2:{F3} PDS FC", {"note": "The older frigate whose name passed to the FT-523 corvette."}),
    ("Kronprinz Wilhelm/E", "Light Cruiser", 48, 161, 14, 5, 4, f"B1*2 B2:{P} B2:{S} ADFC PDS*5 FC", {"note": "Official area-defence variant of the FB1 Kronprinz Wilhelm."}),
    ("Lutjens", "Heavy Cruiser", 88, 293, 26, 8, 4, f"B1*2 B2:{F3}*2 B2:{P} B2:{S} B3:{P} B3:{S} PDS*3 FC*2"),
    ("Prinz Eugen", "Heavy Cruiser", 77, 247, 23, 9, 4, f"B1*2 B2:{P}*2 B2:{S}*2 B3:{F3} PDS*2 FC*2 AGE:2"),
    ("Bayern", "Battlecruiser", 96, 318, 29, 10, 4, f"B1*3 B2:{F3}*2 B2:{P} B2:{S} B3:{P} B3:{S} PDS*3 FC*2"),
    ("Brocken", "Battleship", 134, 450, 54, 10, 2, f"B1*2 B2:{P} B2:{S} B3:{F3} B3:{P}*2 B3:{S}*2 PDS*4 FC*4"),
    ("Hapsburg", "Superdreadnought", 176, 568, 70, 16, 2, f"B1*4 B2:all*2 B2:{F3}*2 B3:{F3} B3:{P} B3:{S} PDS*3 FC*4 HB AGE:6"),
]

NSL_STATS = [
    ("Gepard", "Strikeboat", 11, 40, 3, 1, 6, "SM:F*2 FC", {"rows": 3}),
    ("Nymphe", "Scoutship", 10, 36, 3, 1, 6, "B1 FC", {"rows": 3}),
    ("Nibelung", "Corvette", 16, 54, 5, 1, 4, f"B2:{F3} B1 PDS FC"),
    ("Pola", "Frigate", 22, 74, 7, 2, 4, f"B2:{P} B2:{S} B1 PDS FC"),
    ("Huszar", "Heavy Frigate", 26, 87, 8, 2, 4, f"B2:{F3} B2:all B1 PDS FC"),
    ("Lützow", "Destroyer", 32, 107, 10, 3, 4, f"B2:{F3} B2:{P} B2:{S} B1 PDS*2 FC"),
    ("Rottweil", "Missile Destroyer", 34, 115, 10, 2, 4, f"B2:{F3} SMR:{F3}*2 PDS FC"),
    ("Sachsen", "Heavy Destroyer", 42, 141, 14, 3, 4, f"B2:{P} B2:{S} B2:all B1*2 PDS*2 FC*2"),
    ("Kiel", "Light Cruiser", 50, 167, 16, 4, 4, f"B2:{F3} B2:all*2 B1*2 PDS*3 FC*2"),
    ("Emden", "Light Cruiser", 50, 169, 16, 4, 4, f"B2:{F3} B2:all B1*2 ADFC PDS*4 FC*2"),
    ("Frankfurt", "Escort Cruiser", 68, 229, 20, 6, 4, f"B2:{F3} B2:{P}*2 B2:{S}*2 B1*2 ADFC PDS*5 FC*2"),
    ("Danzig", "Escort Cruiser", 70, 236, 21, 6, 4, f"B2:{F3} B2:{P} B2:{S} B3:{F3} B1*2 ADFC PDS*4 FC*2"),
    ("Rommel", "Attack Cruiser", 86, 285, 28, 7, 4, f"B2:{F3} B2:{P} B2:{S} B3:{F3}*2 B1*2 PDS*3 FC*2"),
    ("Helgoland", "Heavy Cruiser", 94, 313, 28, 9, 4, f"B2:{P} B2:{S} B3:{P} B3:{S} PT:{F3} B1*2 PDS*3 FC*2"),
    ("Von der Tann", "Battlecruiser", 107, 360, 32, 7, 4, f"B2:{P} B2:{S} B3:{F3} B3:{P} B3:{S} PT:{F3} B1*2 PDS*3 FC*3"),
    ("Graf Spee", "Battleship", 130, 448, 44, 8, 2, f"B2:{P} B2:{S} B3:{P}*2 B3:{S}*2 PT:{F3}*2 B1*2 ADFC PDS*4 FC*4"),
    ("Habsburg", "Heavy Battleship", 142, 486, 50, 8, 2, f"B2:{P} B2:{S} B3:{F3} B3:{P}*2 B3:{S}*2 PT:{F3}*2 B1*2 PDS*4 FC*4"),
    ("Maria Theresia", "Battledreadnought", 156, 525, 62, 9, 2, f"B2:{P} B2:{S} B3:{F3}*2 B3:{P} B3:{S} PT:{F3} HB B1*2 PDS*4 FC*4"),
    ("Erzherzog Ferdinand Max", "Superdreadnought", 190, 636, 76, 14, 2, f"B2:all*3 B3:{F3}*2 B3:{P} B3:{S} PT:{F3}*3 B1*2 PDS*5 FC*4"),
    ("Erzherzog Ferdinand Max-B", "Superdreadnought", 190, 636, 76, 14, 2, f"B2:all*3 B3:{F3}*2 B3:{P} B3:{S} B4:{F3} PT:{F3} B1*2 PDS*5 FC*4"),
    ("Erzherzog Ferdinand Max-C", "Superdreadnought", 190, 636, 76, 14, 2, f"B2:all*3 B3:{F3}*2 B3:{P} B3:{S} HB*2 B1*2 PDS*5 FC*4"),
    ("Prinz Heinrich", "Assault Transport", 120, 331, 30, 0, 2, "TB:20 T:32 B1 PDS*2 FC"),
    ("Prinzessin Hannah", "Escort Carrier", 92, 309, 28, 6, 4, f"B2:{F3} B2:{P} B2:{S} HB*2 B1*2 PDS*3 FC*2"),
    ("Kaiser Friedrich", "Light Carrier", 154, 517, 62, 10, 2, f"B2:{P} B2:{S} B3:{P} B3:{S} HB*3 B1*2 PDS*4 FC*3"),
    ("Wien", "Light Carrier", 140, 478, 50, 7, 2, f"B2:{P} B2:{S} B3:{F3} HB*4 B1*2 PDS*4 FC*3"),
    ("Donau", "Strike Carrier", 160, 548, 56, 8, 2, f"B2:{F3} B2:{P} B2:{S} B3:{P} B3:{S} HB*4 B1*2 PDS*4 FC*4"),
    ("Neu Salzburg", "Heavy Carrier", 212, 738, 62, 9, 2, f"B2:{P} B2:{S} B2:all*2 B3:{F3} HB*8 B1*2 PDS*6 FC*3"),
]

IJSF = [
    ("Ninja", "Scoutship", 10, 36, 2, 0, 8, "B1*2 FC", {"rows": 3}),
    ("Naginata", "Strikeboat", 10, 37, 1, 0, 6, f"B2:{P} B2:{S} FC", {"rows": 3}),
    ("Naginata/S", "Strikeboat", 10, 37, 1, 0, 6, "SM:F*4 FC", {"rows": 3}),
    ("Bakemono", "Strike Corvette", 16, 58, 3, 0, 6, f"B2:{F3} SM:F*2 PDS FC", {"rows": 3}),
    ("Ashigaru", "Patrol Frigate", 26, 86, 8, 0, 6, f"B1*2 B2:{F3} SM:F PDS FC"),
    ("Shoya", "Sensor Picket", 26, 108, 8, 0, 8, "B1 SSENS PDS FC"),
    ("Soyokaze", "Destroyer", 36, 123, 7, 0, 6, f"B1 B2:all SMR:{F3}*2 PDS FC"),
    ("Arashi", "Light Cruiser", 60, 203, 15, 0, 6, f"B1*2 B2:{P} B2:{S} B2:{F3} SM:F*4 SMR:{F3} PDS*3 FC*2"),
    ("Ronin", "Patrol Cruiser", 64, 217, 16, 0, 6, f"B1*2 B2:{P} B2:{S} B2:{F3} B3:{FP2} B3:{FS2} PDS*3 FC*2"),
    ("Samurai", "Heavy Cruiser", 83, 281, 20, 0, 6, f"B1*2 B2:{P} B2:{S} B3:{FP2} B3:{FS2} SM:F*5 SMR:{F3} PDS*3 FC*2"),
    ("Kesshi", "Battlecruiser", 110, 376, 28, 0, 5, f"B2:{F3} B3:{FP2} B3:{FS2} B3:{F3} SM:F*2 SMR:{F3}*2 PDS*3 FC*3 HB"),
    ("Yamato", "Battleship", 126, 437, 32, 0, 4, f"B1*3 B2:{P} B2:{S} B3:{FP2} B3:{FS2} B3:{F3} HDC1 SMR:{F3}:er*2 SM:F*4 PDS*3 FC*3 HB"),
    ("Musashi", "Super Battleship", 156, 541, 39, 0, 4, f"B1*2 B2:{F3} B3:{FP2} B3:{FS2} HDC2 SMR:{F3}:er*2 SM:F*4 PDS*4 FC*3 HB*2"),
    ("Shogun", "Command Dreadnought", 263, 930, 62, 0, 3, f"B1*3 B2:{P}*2 B2:{S}*2 B3:{FP2} B3:{FS2} B3:{P}*2 B3:{S}*2 HDC3 SMR:{F3}*4 SM:F*8 PDS*6 FC*5 HB*4"),
    ("Hiryu", "Light Carrier", 160, 564, 32, 0, 4, f"B1*2 B2:{P} B2:{S} B2:{F3}*2 ADFC PDS*4 S1 FC*2 HB*6"),
    ("Akagi", "Super Carrier", 269, 960, 54, 0, 3, f"B1*2 B2:{P}*2 B2:{S}*2 B2:{F3}*2 SMR:{F3}:er ADFC PDS*7 S2 FC*3 HB*10"),
]

NI3 = {"rows": 3}
NI = [
    ("Sheir", "Scout Ship", 8, 29, 2, 0, 8, "B1 FC", NI3),
    ("Sa'ar", "Corvette", 14, 51, 4, 1, 6, "B2:all PDS FC", NI3),
    ("Nitznutz", "Spyship", 14, 70, 2, 0, 13, "SSENS", NI3),
    ("Ra'am", "Battle Frigate", 24, 86, 6, 2, 6, f"B1 B2:{P} B2:{S} PDS FC", NI3),
    ("Barad", "Escort Frigate", 24, 89, 6, 1, 6, "B1*2 ADFC PDS*3 FC", NI3),
    ("Tzayad", "Destroyer", 33, 119, 8, 1, 6, f"B2:{P} B2:{S} PT:F PDS*2 FC", NI3),
    ("Tzayad-B", "Destroyer", 33, 0, 8, 1, 6, f"B2:{P}*2 B2:{S}*2 PDS*2 FC",
     {"rows": 3, "note": "Variant: two class-2 batteries replace the pulse torpedo. The page prints no NPV."}),
    ("Tzayad-S", "Stealth Destroyer", 33, 155, 8, 1, 6, f"B2:{F3} B2:all*2 PDS*2 FC", {"rows": 3, "stealth": 2}),
    ("Kashat", "Light Cruiser", 53, 190, 13, 3, 6, f"B2:{P} B2:{F3} B2:{S} PT:{F3} PDS*2 FC*2", NI3),
    ("Kashat-E", "Escort Cruiser", 53, 192, 14, 3, 6, f"B1*2 B2:{P} B2:{S} ADFC PDS*5 FC*2", NI3),
    ("Kashat-L", "Light Cruiser", 53, 0, 13, 3, 6, f"B2:{P} B2:{S} LRPT:F PDS*2 FC*2",
     {"rows": 3, "note": "Refit: an F-arc long-range pulse torpedo replaces the pulse torpedo and the forward class-2 battery. The page prints no NPV."}),
    ("Maccabee", "Escort Cruiser", 64, 229, 17, 4, 6, f"B2:{P}*2 B2:{S}*2 PT:{F3} PDS*2 FC*2", NI3),
    ("Maccabee-K", "Escort Cruiser", 64, 0, 17, 4, 6, f"B2:{P}*2 B2:{S}*2 B3:{F3} PDS*2 FC*2",
     {"rows": 3, "note": "Refit: a class-3 battery (FP/F/FS) replaces the pulse torpedo. The page prints no NPV."}),
    ("Maccabee-E", "Super Escort", 64, 232, 17, 4, 6, f"B1 B2:{P} B2:{S} ADFC*2 PDS*8 FC", NI3),
    ("Maccabee-S", "Stealth Cruiser", 64, 316, 17, 5, 6, f"B2:{P} B2:{S} B2:all*3 PDS*2 FC*2", {"rows": 3, "stealth": 2}),
    ("Yerushalayim", "Heavy Cruiser", 84, 300, 25, 5, 6, f"B2:{P}*2 B2:{F3} B2:{S}*2 PT:{F3} PDS*3 FC*2", NI3),
    ("Yerushalayim-K", "Heavy Cruiser", 84, 0, 25, 5, 6, f"B2:{P}*2 B2:{F3} B2:{S}*2 B3:{F3} PDS*3 FC*2",
     {"rows": 3, "note": "Refit: a class-3 battery replaces the pulse torpedo. The page prints no NPV."}),
    ("Yerushalayim-L", "Heavy Cruiser", 84, 0, 25, 5, 6, f"B2:{P}*2 B2:{S}*2 LRPT:F PDS*3 FC*2",
     {"rows": 3, "note": "Refit: an F-arc long-range pulse torpedo replaces the pulse torpedo and the forward class-2 battery. The page prints no NPV."}),
    ("Yerushalayim-G", "Heavy Cruiser", 84, 309, 25, 5, 6, f"B2:{P} B2:{S} B2:all G2:F PDS*3 FC*2", NI3),
    ("Barak", "Battlecruiser", 107, 381, 31, 6, 6, f"B2:{P}*2 B2:{F3} B2:{S}*2 LRPT:{F3} PDS*3 FC*2", NI3),
    ("Sabra", "Battleship", 130, 480, 40, 6, 4, f"B2:{P} B2:{F3} B2:{S} B2:all*2 LRPT:{P} LRPT:{S} ADFC PDS*4 FC*3", NI3),
    ("Sabra-G", "Battleship", 130, 503, 40, 6, 4, f"B2:{P} B2:{F3} B2:{S} B2:all*2 G3:F ADFC PDS*5 FC*2", NI3),
    ("Sabra-S", "Stealth Battleship", 130, 664, 40, 6, 4, f"B2:{P}*4 B2:{F3}*2 B2:{S}*4 B2:all*5 ADFC PDS*5 FC*3", {"rows": 3, "stealth": 2}),
    ("Chalutz Chalal", "Heavy Battleship", 170, 627, 50, 5, 4, f"B2:{P}*2 B2:{F3}*2 B2:{S}*2 B2:all LRPT:{P} LRPT:{S} PDS*4 FC*3 HB*2", NI3),
    ("Chalutz Chalal-G", "Heavy Battleship", 170, 642, 50, 5, 4, f"B2:{P}*2 B2:{S}*2 B2:all*2 PT:{FP2} PT:{FS2} G2:{F3} PDS*4 FC*3 HB*2", NI3),
    ("Chayal Cochavim*", "Heavy Battleship", 170, 615, 50, 5, 4, f"B2:{P}*2 B2:{S}*2 B2:all*3 LRPT:{P} LRPT:{S} LRPT:{F3} PDS*4 FC*3",
     {**NI3, "note": "* Adjusted: the page's third long-range torpedo on five arcs is trimmed to three, the limit for a torpedo; the page prints NPV 627."}),
    ("Ben Gurion", "Superdreadnought", 240, 883, 73, 11, 4, f"B2:{P}*4 B2:{F3}*3 B2:{S}*4 B2:all LRPT:{P}*2 LRPT:{S}*2 ADFC PDS*5 FC*4", NI3),
    ("Ben Gurion-G", "Superdreadnought", 240, 918, 74, 11, 4, f"B2:{P}*4 B2:{F3}*4 B2:{S}*4 B2:all*2 PT:{F3} G3:{F3} ADFC PDS*5 FC*4", NI3),
    ("Kineret", "Light Carrier", 150, 550, 42, 7, 4, f"B2:{P}*2 B2:{S}*2 PT:{F3} PDS*4 FC*2 HB*4", NI3),
    ("Tzion", "Supercarrier", 280, 1028, 84, 10, 4, f"B1*2 B2:{P}*2 B2:{S}*2 B2:all*2 PT:{F3} PDS*6 FC*2 HB*8", NI3),
]

U3 = {"rows": 3}
UNSC = [
    ("Hermes", "Diplomatic Courier", 9, 30, 2, 0, 7, "B1 P:1 FC", U3),
    ("Hermes SC", "Courier", 9, 33, 2, 0, 7, "B1*2 FC", {"rows": 3, "note": "Militarized Hermes: a second class-1 battery replaces the passenger space."}),
    ("Warrior", "Strike Corvette", 16, 64, 4, 0, 4, "B1 AMT*2 PDS FC", U3),
    ("Hunter", "Frigate", 24, 94, 6, 0, 6, f"B1 G1:{P} G1:{S} PDS FC", U3),
    ("Lawkeeper", "Patrol Frigate", 20, 76, 6, 0, 6, f"B1 G1:{F3} PDS FC", U3),
    ("Lake", "Destroyer", 34, 130, 9, 0, 6, f"B1 B2:{F3} AMT*3 PDS*2 FC", U3),
    ("Lake Mk II", "Destroyer", 34, 124, 9, 0, 6, f"B1 B2:{F3} PT:{F3} PDS*2 FC", {"rows": 3, "note": "A pulse torpedo replaces the anti-matter torpedoes."}),
    ("Lake Mk III", "Destroyer", 34, 130, 9, 0, 6, f"B1 B2:{F3} G1:{P} G1:{S} PDS*2 FC", {"rows": 3, "note": "Two class-1 grasers replace the anti-matter torpedoes."}),
    ("Mountain", "Light Cruiser", 50, 187, 15, 0, 4, f"B1*2 B2:{P} B2:{S} B2:all PT:{F3} PDS*3 FC*2", U3),
    ("Storm", "Strike Cruiser", 56, 209, 17, 0, 6, f"B1 B2:{P} B2:{S} AMT*3 PDS*3 FC*2", U3),
    ("Bay", "Escort Cruiser", 70, 256, 21, 0, 6, f"B1 B2:{P} B2:{S} PT:{F3} ADFC PDS*6 FC*2", U3),
    ("Bay II", "Escort Cruiser", 77, 281, 23, 0, 6, f"B1 B2:{P} B2:{S} B2:all PT:{F3} ADFC PDS*5 FC*2", U3),
    ("Storm II", "Fast Strike Cruiser", 80, 288, 24, 0, 8, f"B1 B2:{P} B2:{S} AMT*3 PDS*3 FC*2", U3),
    ("River", "Heavy Cruiser", 87, 328, 27, 0, 5, f"B1 B2:{P}*2 B2:{S}*2 PT:{F3} G2:F PDS*3 FC*2", U3),
    ("Point", "Battlecruiser", 109, 415, 33, 0, 4, f"B1*2 B2:{P}*2 B2:{S}*2 PT:{F3}*2 G2:F PDS*4 S1 FC*3", U3),
    ("Luna", "Battleship", 137, 531, 39, 0, 4, f"B1*2 B2:{P}*2 B2:{S}*2 PT:{F3}*2 G2:F AMT*6 PDS*4 S1 FC*3", U3),
    ("Luna Mk II", "Battleship", 137, 531, 39, 0, 4, f"B1*2 B2:{P}*2 B2:{S}*2 PT:{F3}*2 G2:{F3} G1:{P} G1:{S} PDS*4 S1 FC*3",
     {"rows": 3, "note": "The graser covers three arcs (the page leaves which open; FP/F/FS here) and two class-1 grasers replace the anti-matter torpedoes."}),
    ("Sea", "Battledreadnought", 160, 616, 45, 0, 4, f"B1*2 B2:{P}*2 B2:{S}*2 PT:{F3}*2 G2:F AMT*6 PDS*4 S1 FC*3 HB", U3),
    ("Sea Mk II", "Battledreadnought", 160, 616, 45, 0, 4, f"B1*2 B2:{P}*2 B2:{S}*2 PT:{F3}*2 G2:{F3} G1:{P} G1:{S} PDS*4 S1 FC*3 HB",
     {"rows": 3, "note": "The graser covers three arcs (the page leaves which open; FP/F/FS here) and two class-1 grasers replace the anti-matter torpedoes."}),
    ("Gaia", "Superdreadnought", 187, 726, 57, 0, 4, f"B1*2 B2:{P} B2:{S} B2:all*2 PT:{F3} G3:F G1:{P} G1:{S} PDS*4 S1 FC*4 HB", U3),
    ("Sol", "Extended Range Superdreadnought", 259, 949, 72, 0, 5, f"B1*2 B2:{P} B2:{S} B2:all*2 PT:{F3} G3:F AMT*6 PDS*4 S1 FC*4 HB H:4*3", U3),
    ("Asteroid", "Escort Carrier", 87, 326, 24, 0, 4, f"B1*2 B2:{P} B2:{S} B2:all ADFC PDS*6 FC*2 HB*2", U3),
    ("Star", "Light Carrier", 152, 565, 45, 0, 4, f"B1*2 B2:{P} B2:{S} PT:{F3} PDS*4 S1 FC*2 HB*4", U3),
    ("Constellation", "Heavy Carrier", 269, 997, 78, 0, 4, f"B1*2 B2:{P} B2:{S} PT:{F3}*2 PDS*5 S1 FC*2 HB*8", U3),
    ("Visionary", "Deep-Range Explorer", 108, 334, 33, 0, 3, f"B1*2 B2:{P} B2:{S} TB:6 H:4*3 S:4*3 PDS*3 S1 FC",
     {"rows": 3, "note": "The 12 MASS of long-range sensors (three 4-MASS systems, no combat value) are carried as science space."}),
    ("Fleet Replenishment Tender", "Replenishment Tender", 94, 241, 24, 0, 4, "B1*3 H:12*3 PDS*2 FC", U3),
]

ORC = [
    ("Gremlin", "Frigate", 18, 60, 6, 0, 6, "B2:all PDS FC"),
    ("Goblin", "Destroyer", 27, 90, 10, 1, 4, f"B2:all B2:{F3} PDS*2 FC"),
    ("Hobgoblin", "Destroyer", 27, 90, 10, 1, 4, f"B2:all EMP2:{F3} PDS*2 FC", {"note": "Goblin variant: the three-arc class-2 battery becomes a class-2 EMP battery."}),
    ("Gargoyle", "Light Cruiser", 44, 148, 15, 2, 4, f"B2:all*2 EMP2:{P} EMP2:{S} PDS*2 FC*2"),
    ("Fomor", "Heavy Cruiser", 77, 256, 27, 4, 4, f"B2:all*2 B3:{P5} EMP2:{P} EMP2:{S} PDS*3 FC*2"),
    ("Bugbear", "Heavy Escort Cruiser", 84, 282, 29, 4, 4, f"B2:all*4 EMP2:{P} EMP2:{S} ADFC PDS*6 FC*2"),
    ("Troll", "Heavy Cruiser", 87, 290, 30, 4, 4, f"B2:all*2 B3:{P} B3:{S} EMP2:{P} EMP2:{S} PDS*3 FC*2"),
    ("Ogre", "Battleship", 130, 434, 46, 4, 4, f"B2:all*4 B3:{P5}*2 EMP3:{F3} PDS*4 FC*3"),
    ("Ettin", "Light Carrier", 130, 433, 46, 4, 4, f"B2:all*2 EMP2:{F3} PDS*4 FC*2 HB*3"),
]

SCANFED = [
    ("Thorson", "Scoutship", 8, 30, 3, 0, 6, "B1 FC", {"rows": 3}),
    ("Ariander", "Corvette", 14, 47, 5, 0, 6, "B1 SM:F PDS FC"),
    ("Hrafn", "Frigate", 20, 66, 7, 0, 6, "B1*2 SM:F PDS FC"),
    ("Tjeld", "Patrol Frigate", 22, 74, 8, 1, 4, "B1 B2:all SM:F PDS FC"),
    ("Freja", "Destroyer", 32, 107, 12, 1, 4, f"B1 B2:{P} B2:{F3} B2:{S} SM:F PDS FC"),
    ("Mjolnir", "Heavy Destroyer", 44, 147, 16, 2, 4, f"B1 B2:{F3} B2:all PT:F PDS FC*2"),
    ("Trondheim", "Light Cruiser", 56, 186, 20, 3, 4, f"B1 B2:{P} B2:{S} B2:all PT:F PDS*2 FC*2"),
    ("Saint Olaf", "Escort Cruiser", 66, 218, 24, 4, 4, f"B1 B2:{P} B2:{F3}*2 B2:{S} PT:F PDS*3 FC*2"),
    ("Saint Olaf-E", "Escort Cruiser", 66, 220, 24, 4, 4, "B1 B2:all*2 PT:F ADFC PDS*5 FC*2"),
    ("Hardrada", "Heavy Cruiser", 88, 289, 32, 6, 4, f"B1*2 B2:{P} B2:{F3} B2:{S} B3:{F3} PT:F PDS*3 FC*2"),
    ("Peder Skram", "Battlecruiser", 100, 331, 36, 6, 4, f"B1*2 B2:{P} B2:{S} B3:{F3}*2 PT:F PDS*3 FC*3"),
    ("Ericsson", "Heavy Battleship", 144, 478, 52, 7, 4, f"B1*2 B2:{P} B2:{S} B3:{F3}*2 B3:{P} B3:{S} PT:F PDS*4 FC*4"),
    ("Valhalla", "Superdreadnought", 201, 669, 72, 8, 4, f"B1*2 B2:{F3}*2 B3:{P}*2 B3:{S}*2 PT:{F3}*2 PDS*5 FC*5 HB"),
    ("Sleipnir", "Strike Carrier", 184, 623, 56, 6, 4, f"B1*2 B2:{P} B2:{F3}*2 B2:{S} B3:{P} B3:{S} PDS*5 FC*4 HB*4"),
]

FCT = [
    ("Austin", "Destroyer", 30, 96, 9, 0, 6, f"B1*2 B2:{F3}*2 PDS*2 FC",
     {"rows": 5, "note": "The page prints NPV 95.5 / CPV 74.5: a five-row hull's half points. The app rounds .5 up."}),
]

R6 = {"rows": 6}
RAVAGERS = [
    ("Attacker", "Attacker", 12, 44, 3, 0, 6, f"B1 EMP2:{F3} FC", {"rows": 3}),
    ("Attacker (Missile)", "Attacker", 12, 44, 3, 0, 6, "B1 SM:F*2 FC", {"rows": 3, "note": "Missile pack variant: two submunition packs replace the EMP battery."}),
    ("Raider", "Raider", 28, 86, 8, 0, 6, f"B1 B2:{F3} EMP2:{P} EMP2:{S} PDS FC", R6),
    ("Raider (Missile)", "Raider", 28, 86, 8, 0, 6, f"B1 EMP2:{F3} SMR:{F3} PDS FC", {"rows": 6, "note": "Missile variant."}),
    ("Raider Type II", "Raider", 30, 93, 8, 0, 6, f"B1 B2:{P} B2:{S} EMP1 EMP2:{F3} PDS FC", R6),
    ("Raider Type II (Needle)", "Raider", 30, 93, 8, 0, 6, f"B1 B2:all EMP2:{F3} NB:F PDS FC", {"rows": 6, "note": "Needle beam variant."}),
    ("Cruiser", "Cruiser", 72, 203, 20, 0, 6, f"B1 B2:{F3} B2:{P} B2:{S} EMP2:{P} EMP2:{S} NB:F H:6 PDS*2 FC*2", R6),
    ("Carrier", "Carrier", 90, 259, 26, 0, 4, f"B1*2 B2:{F3} EMP2:{F3} H:8 PDS*3 FC*2 HB*2", R6),
]

KV = {"race": "kravak"}
KV_WAVE1 = [
    ("Kedge", "Heavy Striker", 24, 96, 7, 0, 6, "K1 SG MKP*4 FC", KV),
    ("To'Ki", "Destroyer", 31, 124, 9, 0, 6, "K1 K3 SG*2 FC", {"race": "kravak", "note": "NAC reporting name KICK."}),
    ("Ki'Rek", "Light Attack Cruiser", 60, 237, 18, 0, 6, "K1*2 K3 SG*3 MKP*4 FC*2", {"race": "kravak", "note": "NAC reporting name KILROY."}),
    ("De'Rek", "Light Attack Cruiser", 60, 235, 22, 0, 4, f"K1 K2:{FP2} K2:{FS2} K3 SG*3 FC*2", {"race": "kravak", "note": "NAC reporting name KOORBASH."}),
    ("Ka'Ton", "Heavy Attack Cruiser", 82, 322, 30, 0, 4, "K1*3 K3*2 SG*4 MKP*6 FC*2", {"race": "kravak", "note": "NAC reporting name KIDNEY."}),
    ("Lu'Ton", "Heavy Attack Cruiser", 82, 322, 30, 0, 4, f"K1*2 K2:{FP2} K2:{FS2} K3*2 SG*4 FC*2", {"race": "kravak", "note": "NAC reporting name KINKY."}),
    ("Kia'Kyu", "Heavy Battleship", 130, 512, 46, 0, 4, "K1*4 K5*2 SG*6 MKP*6 FC*3", {"race": "kravak", "note": "NAC reporting name KARATE."}),
    ("Kia'Kas", "Heavy Battleship", 130, 512, 46, 0, 4, f"K1*3 K2:{FP2} K2:{FS2} K5*2 SG*6 FC*3", {"race": "kravak", "note": "NAC reporting name KOHOLA."}),
]

KV3 = {"race": "kravak", "rows": 3, "note": "NAC reporting name; the Kra'Vak name is unknown."}
KV_WAVE2 = [
    ("KELT-ALPHA", "Strikeboat", 10, 42, 3, 0, 6, "MKP*2 FC", KV3),
    ("KELT-BETA", "Strikeboat", 10, 42, 3, 0, 6, "K1 FC", KV3),
    ("KELT-CHARLIE", "Strikeboat", 10, 44, 3, 0, 6, "SG*2 FC", KV3),
    ("KATA", "Striker Corvette", 18, 75, 5, 0, 6, "SG K1 MKP*2 FC", KV3),
    ("KEEL", "MKP Frigate", 23, 99, 6, 0, 6, "SG K1 MKP*4 FC", KV3),
    ("KYRA", "Frigate", 28, 120, 8, 0, 6, "SG*2 K2*2 FC", KV3),
    ("KRILL", "MKP Destroyer", 33, 142, 9, 0, 6, "SG*2 K1 MKP*6 FC", KV3),
    ("KEIRA", "Destroyer", 34, 144, 12, 0, 6, "SG*2 K2*2 FC", KV3),
    ("KAZOO", "Heavy Destroyer", 48, 204, 14, 0, 6, f"SG*2 K1 K2:{FP2} K2:{FS2} MKP*2 FC", KV3),
    ("KRAIT", "Light Cruiser", 61, 258, 20, 0, 6, "SG*3 K3*2 K1 FC*2", KV3),
    ("KRAIT-F", "Fast Light Cruiser", 61, 266, 16, 0, 8, "SG*3 K3*2 FC*2", KV3),
    ("KIRIN", "Escort Cruiser", 68, 293, 21, 0, 6, "SG*8 K3*2 FC*2", KV3),
    ("KORMA", "Patrol Cruiser", 73, 309, 24, 0, 6, f"SG*3 K2:{FP2} K2:{FS2} K1*3 FC*2", KV3),
    ("KANJI", "Heavy Cruiser", 81, 342, 25, 0, 6, "SG*2 K3*2 K1*5 FC*2", KV3),
    ("KAYAK", "Tri-Gun Heavy Cruiser", 81, 345, 25, 0, 6, "SG*5 K3*3 K1 FC*2", KV3),
    ("KAPOK", "Quad-Gun Heavy Cruiser", 81, 343, 25, 0, 6, f"SG*3 K2:{FP2}*2 K2:{FS2}*2 K1 FC*3", KV3),
    ("KAPOK-F", "Fast Quad-Gun Heavy Cruiser", 81, 334, 25, 0, 8, "SG*2 K2*4 FC*2", KV3),
    ("KETONE-ALPHA", "Battlecruiser", 94, 395, 32, 0, 6, "SG*3 K4*2 K1*2 FC*2", KV3),
    ("KETONE-BETA", "Battlecruiser", 94, 399, 33, 0, 6, "SG*4 K4*3 K1*2 FC*2", KV3),
    ("KASBAH", "Battleship", 124, 522, 42, 0, 6, "SG*5 K5*2 K1*2 FC*2", KV3),
    ("KLAXON", "Superheavy Battleship", 149, 631, 52, 0, 5, "SG*5 K4*4 K1*2 FC*4", KV3),
    ("KODIAK", "Mega-Battleship", 173, 737, 56, 0, 5, "SG*5 K5*4 K1*2 FC*4", KV3),
    ("KEYSTONE", "Superdreadnought", 244, 1036, 84, 0, 5, "SG*9 K6*4 K1*3 FC*4", KV3),
    ("KEROSENE", "Heavy Carrier", 264, 1075, 80, 0, 5, "SG*7 K3*4 K1*4 FC*3 HB*6", KV3),
]

SV = {"race": "savasku"}
SAVASKU = [
    ("Fo'Vann'Ath", "Destroyer", 32, 103, 10, 2, 0, f"PG:8 ST:{P} ST:{S} SP CX", {"race": "savasku", "note": "NAC reporting name Swat."}),
    ("Var'Konn'Sha", "Light Cruiser", 58, 185, 22, 3, 0, f"PG:12 ST:{F3} PL:F SP*2 CX*2",
     {"race": "savasku", "note": "NAC reporting name Sneaker. Extra biomass feeds more pod launcher shots."}),
    ("Var'Tuur'Sha", "Attack Cruiser", 78, 251, 24, 4, 0, f"PG:19 ST:{P} ST:{S} PL:F*2 SP*3 CX*2", {"race": "savasku", "note": "NAC reporting name Sword."}),
    ("Vas'Kaan'Rosh", "Superdreadnought", 200, 657, 56, 15, 0, f"PG:36 ST:{F3}*2 ST:{P}*2 ST:{S}*2 ST:AP,A,AS PL:F*2 SP*6 SN*2 CX*4 DW",
     {"race": "savasku", "note": "NAC reporting name Shade."}),
]

PHALON = [
    ("Silith", "Fast Destroyer", 28, 104, 6, 0, 8, f"PU:{F3}*2 FC", {"race": "phalon", "layers": (1,)}),
    ("Greeth", "Heavy Destroyer", 33, 128, 7, 0, 6, f"PU:{F3} PU:{S} PU:{P} FC", {"race": "phalon", "layers": (3,)}),
    ("Gruuss", "Attack Cruiser", 90, 342, 18, 0, 4, f"PU:F*2 PU:{P} PU:{S} PU:all PBL3 VS FC*2", {"race": "phalon", "layers": (6, 3)}),
    ("Gruuss-B", "Attack Cruiser", 97, 371, 21, 0, 4, f"PU:{P}*2 PU:{S}*2 PU:all PBL2:{F3} PBL2:{S} FC*2", {"race": "phalon", "layers": (5, 4)}),
    ("Viiyaan", "Medium Podship", 80, 175, 8, 0, 2, "PU:all PBL1 H:43 FC", {"race": "phalon", "layers": (2, 1)}),
    ("Tuuyaan", "Small Podship", 48, 121, 5, 0, 2, "PU:all PBL1 H:21 FC", {"race": "phalon", "layers": (2,)}),
]

CRUSTY = [
    ("Ch'Ka'Tk", "Scout Boat", 8, 28, 1, 1, 8, "RC1 FC", {"rows": 3, "note": "NAC reporting name CLUE."}),
    ("Sss'Tk'vk", "Strike Boat", 9, 32, 1, 1, 7, "SM:F*2 FC", {"rows": 3, "note": "NAC reporting name CRUM."}),
    ("K'Knn'TK", "Attack Craft", 16, 55, 2, 2, 8, "RC1 SM:F*2 FC", {"rows": 3, "note": "NAC reporting name CATFISH."}),
    ("Sk'Ka'Kss", "Frigate", 20, 67, 4, 2, 6, f"RC2:{F3} SM:F*2 PDS FC", {"note": "NAC reporting name CROW."}),
    ("Tkk'vk'Ka", "Destroyer", 30, 100, 6, 3, 6, f"RC2:{P} RC2:{S} SM:F*2 PDS*2 FC", {"note": "NAC reporting name CACTUS."}),
    ("Tk'Vkk'Ch", "Heavy Destroyer", 40, 133, 8, 4, 6, f"RC2:{P} RC2:{S} SMR:{F3} PDS*3 FC", {"note": "NAC reporting name COMET."}),
    ("Sss'Ka'Tk'Tk", "Light Cruiser", 50, 167, 10, 5, 6, f"RC2:{P} RC2:{F3} RC2:{S} SMR:{F3} PDS*3 FC*2", {"note": "NAC reporting name CRAKE."}),
    ("Ch'Tkk'ch'K", "Strike Cruiser", 80, 266, 16, 8, 6, f"RC2:{P}*2 RC2:{F3} RC2:{S}*2 SMR:{F3}*2 PDS*4 FC*2", {"note": "NAC reporting name CROSSBOW."}),
    ("Tk'ch'ch'Ksss", "Heavy Cruiser", 80, 266, 16, 8, 6, f"RC2:{P} RC2:{S} RC3:{FP2} RC3:{FS2} SMR:{F3} PDS*4 FC*2", {"note": "NAC reporting name CUTLASS."}),
    ("Ka'Tk'chh'Vs", "Battlecruiser", 100, 338, 20, 10, 5, f"RC2:{P} RC2:{F3} RC2:{S} RC3:{P} RC3:{F3} RC3:{S} SMR:{F3} PDS*4 FC*3", {"note": "NAC reporting name COBALT."}),
    ("Vk'ca'tk'Knn", "Heavy Battleship", 140, 473, 28, 14, 5, f"RC2:{P}*2 RC2:{S}*2 RC3:{P} RC3:{F3}*2 RC3:{S} SMR:{F3}*2 PDS*5 FC*4", {"note": "NAC reporting name CROWBAR."}),
    ("Vn'Ks'Ks'Vkk", "Dreadnought", 160, 540, 32, 16, 5, f"RC2:{P} RC2:{F3}*2 RC2:{S} RC3:{P}*2 RC3:{F3} RC3:{S}*2 SMR:{F3}*2 PDS*6 FC*4", {"note": "NAC reporting name CASTLE."}),
    ("Tr'Skk'ka'Ch", "Light Carrier", 140, 478, 28, 14, 4, f"RC2:{P}*2 RC2:{S}*2 RC3:{F3} PDS*4 FC*2 HB*4", {"note": "NAC reporting name CONDOR."}),
]

P4 = "AP,FP,F,FS"
# * marks a design adjusted here to fit the rules (owner's ruling 2026-10-21); the note says how.
JIBRAIL = "* Adjusted: the page's two torpedoes on five arcs are trimmed to three (FB1 p.7); the page prints NPV 527. "
ARABIYA = "* Adjusted: the page's two torpedoes on four arcs are trimmed to three (FB1 p.7); the page prints NPV 694. "
REMORA = "* Adjusted: the page prints TMF 3, NPV 10. "
IF_NOTE = "The page lets each bracketed weapon block be swapped at build (4 HMR, 2 SMR, 4 class-2 on 3 arcs, or 2 six-arc and 1 three-arc class-2); this is its listed fit."
IF = [
    ("al Shaulah", "Strikeship", 10, 37, 1, 0, 6, "MSL*2 FC", {"rows": 3, "note": "Alternative fits: 1 SMR or 2 needle beams. Its only defence is luck."}),
    ("Khabar", "Corvette", 14, 50, 2, 0, 9, f"SMR:{F3} FC", {"rows": 3, "note": "Alternative fits: 2 heavy missiles or a class-3 battery (F)."}),
    ("al Hawar", "Frigate", 24, 81, 5, 2, 6, "B2:all*2 PDS FC", {"note": "Alternative fit: a three-arc class-2 battery and 1 SMR."}),
    ("Saladin", "Destroyer", 34, 114, 7, 3, 6, f"B2:{P} B2:{S} MSL*2 PDS*2 FC", {"note": IF_NOTE}),
    ("Saladin (Heavy)", "Heavy Destroyer", 44, 148, 10, 2, 6, f"MSL*2 B2:all*2 B2:{F3} PDS*2 FC", {"note": IF_NOTE}),
    ("Ashraf", "Light Cruiser", 54, 179, 14, 4, 6, "MSL*4 B2:all PDS*2 FC*2", {"note": IF_NOTE}),
    ("Sahaabah", "Patrol Cruiser", 64, 217, 17, 5, 4, f"B2:all MSL*4 B2:all*2 B2:{F3} PDS*2 FC*2", {"note": IF_NOTE}),
    ("Hattin", "Heavy Cruiser", 84, 287, 22, 6, 4, f"B3:{P5} B2:all*2 B2:{F3} B2:all ADFC PDS*4 S1 FC*2", {"note": IF_NOTE}),
    ("Khartoum", "Attack Cruiser", 90, 306, 23, 6, 4, f"B3:{P5} B2:all*2 B2:{F3} MSL*4 PDS*3 S1 FC*2", {"note": IF_NOTE}),
    ("Saif ed Din", "Battleship", 124, 424, 31, 9, 4, f"B3:{P5}*2 B2:all*4 B2:{F3}*2 ADFC PDS*4 S1 FC*3", {"note": "Sword of Islam. " + IF_NOTE}),
    ("Jibrail*", "Heavy Battleship", 154, 515, 39, 10, 4, f"PT:{F3}*2 B3:{P5} B2:all*4 B2:{F3}*2 ADFC PDS*5 S1 FC*4", {"note": JIBRAIL + IF_NOTE}),
    ("Jibrail (Sensors)*", "Heavy Battleship", 154, 519, 39, 10, 4, f"PT:{F3}*2 B3:{P5} B2:all*4 B2:{F3}*2 ADFC PDS*5 S1 FC*3 ESENS", {"note": JIBRAIL + "Variant: one fire control becomes enhanced sensors (2 MASS, 8 points)."}),
    ("Arabiya*", "Dreadnought", 204, 688, 54, 12, 4, f"B3:{P4}*2 B3:{F3}*2 PT:{F3}*2 B2:all*2 B2:{F3}*4 ADFC PDS*6 S1 FC*4 TUG:6", {"note": ARABIYA + "Carries Remora scouts and can tow 6 MASS through FTL."}),
    ("Arabiya (Flagship)*", "Dreadnought", 204, 690, 54, 12, 4, f"B3:{P4}*2 B3:{F3}*2 PT:{F3}*2 B2:all*2 B2:{F3}*3 ADFC PDS*6 S1 FC*4 TUG:6 ESENS P:1", {"note": ARABIYA + "Variant: one three-arc class-2 battery becomes enhanced sensors (2 MASS, 8 points) and 1 MASS of passenger space for an admiral's staff."}),
    ("Remora*", "Scout", 7, 25, 1, 1, 9, "ESENS", {"ftl": False, "note": REMORA + "Enhanced sensors take 2 MASS, so the hull grows from TMF 3 to 7 to carry them at thrust 9."}),
    ("Remora (Recon)*", "Scout", 5, 19, 1, 0, 9, "ESENS", {"ftl": False, "note": REMORA + "Recon variant: armour removed; at TMF 5 (printed 3) it carries the enhanced sensors at thrust 9."}),
    ("Madinah", "Battle Carrier", 184, 633, 42, 10, 4, f"B3:{P5} B2:all*4 B2:{F3}*2 ADFC PDS*4 S1 FC*2 HB*4", {"note": IF_NOTE}),
    ("Madinah (CVH)", "Heavy Carrier", 184, 632, 42, 10, 4, "B2:all*2 ADFC PDS*5 S1 FC HB*6", {"note": "Six-bay heavy carrier option."}),
]

def _modules(n: int) -> str:
    return " ".join(["H:8"] * n)


OU_NOTE = ("The page prices the hull without its 8-MASS payload module{s}; each well holds the zero-cost "
           "Cargo module here. Swap in a Gunpack (3 class-2, 1 class-1, 1 PDS) or Standard (2 class-2, "
           "2 class-1, 2 PDS) module for 24 points, a Defence module (2 class-1, 4 PDS, ADFC) for 26, or "
           "a Torpedo module (class-2, pulse torpedo, fire control, PDS) for 25.")
OUDF = [
    ("Snake", "Heavy Frigate", 24, 79, 7, 1, 7, f"B2:{F3} B1*2 PDS FC"),
    ("Spider", "Torpedo Boat", 24, 79, 7, 1, 7, "PT:F PDS FC"),
    ("Freemantle", "Patrol Vessel", 32, 99, 16, 2, 5, "B1 FC", {"note": "The only Oceanic Union design that can operate without a payload module."}),
    ("River", "Destroyer", 40, 107, 16, 2, 4, f"B1 FC {_modules(1)}", {"note": OU_NOTE.format(s="")}),
    ("Numbat", "Light Cruiser", 62, 184, 19, 2, 4, f"B2:{F3} B1 PDS S1 FC*2 {_modules(1)}", {"note": OU_NOTE.format(s="")}),
    ("Tuvalu Block I", "Heavy Cruiser", 81, 227, 24, 3, 4, f"B2:{P} B2:{S} B1 PDS*2 S1 FC*2 {_modules(2)}", {"note": OU_NOTE.format(s="s")}),
    ("Tuvalu Block II", "Heavy Cruiser", 81, 246, 32, 3, 4, f"B2:{P} B2:{S} B1 PDS*2 S1 FC*2 {_modules(1)}", {"note": OU_NOTE.format(s="")}),
    ("Waikato", "Escort Carrier", 102, 322, 31, 3, 4, f"B2:{F3} B1 PDS S1 FC*2 HB*2 {_modules(1)}", {"note": OU_NOTE.format(s="")}),
    ("Dunedin", "Battlecruiser", 111, 319, 33, 3, 6, f"B2:all B1 PDS*2 S1 FC*3 {_modules(2)}", {"note": OU_NOTE.format(s="s")}),
    ("Cooma", "Battleship", 124, 347, 37, 6, 4, f"B2:all B1 PDS S2 FC*3 {_modules(3)}", {"note": OU_NOTE.format(s="s")}),
    ("Auckland", "Carrier", 128, 411, 37, 3, 4, f"B2:all B1 PDS*2 S1 FC*2 HB*3 {_modules(1)}", {"note": OU_NOTE.format(s="")}),
    ("Jervis Bay", "Modular Fleet Auxiliary", 144, 280, 29, 0, 2, f"B2:{F3} B1*2 PDS*2 FC {_modules(10)}", {"note": OU_NOTE.format(s="s")}),
    ("Brisbane", "Heavy Battleship", 144, 392, 43, 5, 4, f"B2:{F3} B2:{P} B2:{S} B1*2 PDS*2 S1 FC*3 {_modules(4)}",
     {"note": "Conjectural: the master miniature was never released. " + OU_NOTE.format(s="s")}),
]
# fmt: on

PAGES = [
    ("NAC", "NACfbr.htm", NAC_FBR),
    ("NAC", "NACstats.htm", NAC_STATS),
    ("ESU", "ESUfbr.htm", ESU_FBR),
    ("ESU", "ESUstats.htm", ESU_STATS),
    ("FSE", "FSEfbr.htm", FSE_FBR),
    ("FSE", "FSEstats.htm", FSE_STATS),
    ("NSL", "NSLfbr.htm", NSL_FBR),
    ("NSL", "NSLstats.htm", NSL_STATS),
    ("IJSF", "IJSFstats.htm", IJSF),
    ("NI", "NIstats.htm", NI),
    ("UNSC", "UNSCstats.htm", UNSC),
    ("ORC", "ORCstats.htm", ORC),
    ("ScanFed", "ScanFedstats.htm", SCANFED),
    ("FCT", "MISCstats.htm", FCT),
    ("RAV", "MISCstats.htm", RAVAGERS),
    ("KV", "KVstats.htm", KV_WAVE1),
    ("KV", "KVstatsWave2.htm", KV_WAVE2),
    ("SV", "SVstats.htm", SAVASKU),
    ("PH", "SVstats.htm", PHALON),
    ("CR", "CRstats.htm", CRUSTY),
    ("IF", "IFstats.htm", IF),
    ("OUDF", "OUDFstats.htm", OUDF),
]

KEYWORD_CODES = (
    ("Superdreadnought", "SDN"), ("Battledreadnought", "BDN"), ("Heavy Battleship", "BDN"),
    ("Dreadnought", "DN"), ("Battleship", "BB"), ("Battlecruiser", "BC"), ("Heavy Cruiser", "CH"),
    ("Escort Cruiser", "CE"), ("Patrol Cruiser", "CE"), ("Light Cruiser", "CL"),
    ("Heavy Destroyer", "DH"), ("Destroyer", "DD"), ("Frigate", "FF"), ("Corvette", "CT"),
    ("Scout", "SC"), ("Courier", "SC"),
)
MERCHANTS = {"Galahad", "Prinz Heinrich", "Visionary", "Fleet Replenishment Tender", "Jervis Bay",
             "Viiyaan", "Tuuyaan"}


def type_code(name: str, label: str, tmf: int) -> str:
    """The class code the label names, else the class whose MASS range holds the ship."""
    if name in MERCHANTS:
        return "M"
    low = label.lower()
    if "carrier" in low:
        if "escort" in low or "light" in low:
            return "CVE" if "escort" in low else "CVL"
        if any(w in low for w in ("heavy", "strike", "battle", "super", "fleet", "attack")):
            return "CVA"
        return common.pick_class(tmf, fb_data.CARRIER_CLASSES)[1]
    for word, code in KEYWORD_CODES:
        if word.lower() in low:
            return code
    return common.pick_class(tmf, fb_data.SHIP_CLASSES)[1]


def build() -> list[dict]:
    designs = []
    for faction, page, ships in PAGES:
        for ship in ships:
            name, label, tmf, npv, hull, armour, thrust, systems, *rest = ship
            extra = rest[0] if rest else {}
            designs.append(design(
                "fb", BOOK, 0, faction, name, label, type_code(name, label, tmf), tmf, npv,
                systems, hull=hull, armour=armour, thrust=thrust, ftl=extra.get("ftl", True),
                kind="merchant" if name in MERCHANTS else "warship", race=extra.get("race", "human"),
                armour_layers=extra.get("layers", ()), notes=extra.get("note", ""),
                hull_rows=extra.get("rows", 4), stealth=extra.get("stealth", 0), url=SITE + page,
            ))
    return designs


def main() -> None:
    designs = build()
    out = write("fb_starranger.json", designs)
    print(f"Wrote {out} ({len(designs)} designs)")


if __name__ == "__main__":
    main()
