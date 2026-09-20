"""Build data/catalog/ft2_core.json (FT pp.14-15 basic classes) and ft2_mt.json (MT p.23 new
general designs).

FT is an image-only scan, so every design was read off the page image (FT2 beam pointers: up =
F, left = P, right = S). The side A batteries of the capital classes point Fore plus their own
side only, which is what makes the Battleship (447) dearer than the Battledreadnought (431)
despite the smaller hull. MT has a native text layer; its MASS and POINTS lines are checked
against the page before writing. Type codes come from the ruleset's suggest_type().

    python tools/extract_catalog_ft2.py
"""

from __future__ import annotations

import re
import sys

import pymupdf
from catalog_common import ROOT, design, write

sys.path.insert(0, str(ROOT))
from rulesets import get_ruleset  # noqa: E402

# (name, type label, MASS, points, thrust, systems[, kind, ftl])
# fmt: off
FT_CORE = [
    ('Courier', 'Courier Boat', 2, 15, 8, 'BC:P,F,S FC'),
    ('Scout Ship', 'Scoutship', 4, 28, 8, 'BC:P,F,S PDAF FC'),
    ('Corvette', 'Corvette', 6, 43, 8, 'PDAF BC:P,F,S*2 FC'),
    ('Frigate', 'Frigate', 10, 65, 6, 'BC:P,F,S BB:P,F,S PDAF*2 FC'),
    ('Destroyer', 'Destroyer', 14, 92, 6, 'BC:P,F,S BB:P,F,S*2 PDAF*2 FC'),
    ('Light Cruiser', 'Light Cruiser', 22, 190, 6, 'BB:P,F,S*3 S1 PDAF*2 FC*2'),
    ('Escort Cruiser', 'Escort Cruiser', 26, 195, 4, 'BB:P,F,S*3 S1 ADAF PDAF FC*2'),
    ('Heavy Cruiser', 'Heavy Cruiser', 32, 238, 4, 'BA:P,F,S BB:P,F,S*3 S1 ADAF PDAF FC*2'),
    ('Battlecruiser', 'Battlecruiser', 40, 381, 4, 'BA:P,F,S BA:F,P BA:F,S BB:P,F,S PDAF*3 S2 FC*3'),
    ('Battleship', 'Battleship', 48, 447, 4, 'BB:P,F,S BA:F,P BA:F,S BA:F,P BA:F,S PDAF*4 S2 FC*3'),
    ('Battledreadnought', 'Battledreadnought', 60, 431, 2, 'BB:P,F,S BA:F,P BA:F,S BA:F,P BA:F,S PDAF*4 S2 HB FC*3'),
    ('Superdreadnought', 'Superdreadnought', 80, 580, 2, 'BA:P,F,S BA:F,P BA:F,S BA:F,P BA:F,S PDAF*4 S3 HB*2 FC*3'),
    ('Light Carrier', 'Light Carrier', 70, 499, 2, 'BC:P,F,S*2 PDAF*3 S2 HB*4 FC*3'),
    ('Fleet Carrier', 'Fleet Carrier', 98, 687, 2, 'BB:P,F,S*2 PDAF*3 S2 HB*6 FC*3'),
    ('Bulk Tanker', 'Bulk Tanker', 100, 502, 2, 'BC:P,F,S*3 PDAF*4 S1 FC', 'merchant'),
    ('Heavy Freighter', 'Heavy Freighter', 60, 306, 2, 'BC:P,F,S PDAF*2 S1 FC', 'merchant'),
    ('Survey Cruiser', 'Exploration Cruiser', 48, 333, 4, 'BC:P,F,S*3 PDAF*2 FC', 'merchant'),
]
# fmt: on

# fmt: off
MT_DESIGNS = [
    ('Strikeboat', 'Strikeboat', 4, 26, 8, 'SM:F PDAF FC'),
    ('Lancer', 'Lancer', 6, 39, 8, 'PDAF SM:F*2 FC'),
    ('Torpedo Destroyer', 'Torpedo Destroyer', 14, 86, 6, 'PT:F BC:P,F,S PDAF FC'),
    ('Super Destroyer', 'Super Destroyer', 16, 105, 6, 'BB:P,F,S*3 PDAF*2 FC'),
    ('Privateer', 'Privateer', 18, 137, 8, 'NB:F BA:P,F,S PDAF S1 FC'),
    ('Needle Cruiser', 'Needle Cruiser', 22, 187, 6, 'NB:F BB:P,F,S*2 S1 PDAF*2 FC*2'),
    ('Strike Cruiser', 'Strike Cruiser', 28, 198, 4, 'PDAF PT:F*2 S1 FC*2'),
    ('Missile Cruiser', 'Missile Cruiser', 26, 187, 4, 'BC:P,F,S MSL*4 S1 PDAF FC*2'),
    ('Planetary Bombardment Monitor', 'Monitor', 32, 198, 2, 'BB:P,F,S ORTILLERY*3 S1 PDAF*2 FC*2'),
    ('System Defence Cruiser', 'System Defence Cruiser', 32, 252, 4, 'BA:P,F,S*5 PDAF*3 S2 FC*2', 'warship', False),
    ('Escort/Patrol Carrier', 'Escort Carrier', 40, 286, 2, 'BC:P,F,S*3 HB*2 PDAF*2 S1 FC*3'),
    ('Free Trader', 'Free Trader', 10, 50, 2, 'BC:P,F,S FC', 'merchant'),
    ('Medium Tug', 'Tug', 32, 224, 2, 'BC:P,F,S*2 PDAF*2 FC TUG', 'merchant'),
    ('Armed Merchantman', 'Armed Merchantman', 36, 178, 2, 'BC:P,F,S*2 PDAF*2 FC', 'merchant'),
]
# fmt: on


def _build(rows: list, book: str, page: int) -> list[dict]:
    ft2 = get_ruleset("ft2")
    out = []
    for row in rows:
        name, label, mass, points, thrust, systems, *rest = row
        kind = rest[0] if rest else "warship"
        ftl = rest[1] if len(rest) > 1 else True
        d = design(
            "ft2", book, page, None, name, label, "", mass, points, systems, thrust=thrust, ftl=ftl, kind=kind
        )
        d["type_code"] = ft2.suggest_type(d)[1]
        out.append(d)
    return out


def check_mt_text() -> None:
    doc = pymupdf.open(ROOT / "rulebooks" / "More Thrust.pdf")
    text = " ".join(doc[22].get_text().split())
    missing = [
        name
        for name, _l, mass, points, *_ in MT_DESIGNS
        if not re.search(rf"{re.escape(name.upper())} MASS {mass} {points} POINTS", text)
    ]
    if missing:
        sys.exit(f"MT p.23 text does not match: {missing}")


def main() -> None:
    check_mt_text()
    core = _build(FT_CORE, "FT", 14)
    for d in core:  # FT p.14 table, diagrams on pp.14-15
        if d["tmf"] >= 40 or d["hull_kind"] == "merchant":
            d["source"]["page"] = 15
    print("Wrote", write("ft2_core.json", core))
    print("Wrote", write("ft2_mt.json", _build(MT_DESIGNS, "MT", 23)))


if __name__ == "__main__":
    main()
