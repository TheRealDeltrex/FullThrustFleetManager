"""Class presets for a new design: pick a class and the hull starts with plausible stats.

MASS is the middle of the class's band (FB1 p.12, CD p.42) or the class's own MASS where the book
prints one figure (FT p.14). Hull, armour and thrust sit at the lower end of what the published
ships of that class carry, so a player builds up rather than strips down:

- hull boxes: the lowest "Average" hull of the book's descriptor table, rounded down (FB2 p.3
  25%, CD p.43 30%);
- armour: the least armour any armoured Fleet Book ship of the class has (FB1, FB2);
- thrust: 4, the lowest rating most published warships of every class use; 2 for superdreadnoughts,
  heavy carriers and merchants, where the books' slow hulls are the norm.

Fire controls follow the owner's rule of thumb rather than a book: 1 for escorts, 2 from the
light cruiser up, 3 for battlecruisers and battleships, 4 for the dreadnoughts (BDN, DN, SDN),
2 for carriers and none for merchants; carriers also start with two hangar bays. Every preset is
FTL-capable. Races without fire control or hangars (Sa'Vasku) get neither.
Everything is a starting point only; the workbench edits every value afterwards.
"""

from __future__ import annotations

from dataclasses import dataclass

from rulesets import RULESETS
from rulesets.fb import data as fb_data
from rulesets.ft2 import data as ft2_data
from rulesets.ftcd import data as ftcd_data


@dataclass(frozen=True)
class ClassPreset:
    code: str
    label: str
    tmf: int
    hull_boxes: int
    armour: int
    thrust: int
    fire_controls: int
    hull_kind: str = "warship"


# Lowest non-zero armour among the Fleet Book ships of each class (catalog data, FB1/FB2).
ARMOUR = {
    "SC": 1, "CT": 1, "FF": 2, "DD": 2, "DH": 2, "CL": 3, "CE": 3, "CH": 5, "CA": 5,
    "BC": 5, "BB": 5, "BDN": 7, "DN": 7, "SDN": 7, "CVE": 6, "CVL": 9, "CV": 9, "CVH": 12,
}
SLOW = {"SDN", "CVH", "CV"}
CARRIER_BAYS = 2  # hangar bays a carrier preset starts with, one fighter group each
# A band with no top ("160+", FB1 p.12) is treated as this wide, so its middle stays sensible.
OPEN_BAND_WIDTH = 80


def fire_controls(code: str, hull_kind: str = "warship") -> int:
    if hull_kind == "merchant":
        return 0
    if code.startswith("CV"):
        return 2
    if code in ("BDN", "DN", "SDN"):
        return 4
    if code in ("BC", "BB"):
        return 3
    if code in ("CL", "CE", "CH", "CA"):
        return 2
    return 1


def _banded(classes: tuple, hull_share: int, label_of) -> list[ClassPreset]:
    out = []
    for label, code, low, high in classes:
        tmf = (low + (high if high is not None else low + OPEN_BAND_WIDTH)) // 2
        out.append(ClassPreset(
            code, label_of(label), tmf, tmf * hull_share // 100, ARMOUR.get(code, 0),
            2 if code in SLOW else 4, fire_controls(code),
        ))
    return out


def _average_hull(descriptors: tuple) -> int:
    return next(pct for pct, name in descriptors if name == "Average")


def _merchant(label_of, tmf: int, hull_share: int) -> ClassPreset:
    return ClassPreset("M", label_of("Merchant"), tmf, tmf * hull_share // 100, 0, 2, 0,
                       "merchant")


def class_presets(ruleset_id: str) -> list[ClassPreset]:
    """The classes a new design of this ruleset may start from, smallest first."""
    if ruleset_id in ("fb", "ftcd"):
        data = fb_data if ruleset_id == "fb" else ftcd_data
        share = _average_hull(data.HULL_DESCRIPTORS)
        label_of = fb_data.translated_class_label
        return (_banded(data.SHIP_CLASSES, share, label_of)
                + _banded(data.CARRIER_CLASSES, share, label_of)
                + [_merchant(label_of, 50, share)])
    if ruleset_id == "ft2":
        # FT2 derives hull and armour from MASS, so only MASS, thrust and fire control apply.
        out = []
        for kind in ("escort", "cruiser", "capital", "carrier", "merchant"):
            for label, code, tmf in ft2_data.BASIC_CLASSES[kind]:
                hull_kind = "merchant" if kind == "merchant" else "warship"
                out.append(ClassPreset(
                    code, ft2_data.class_label(label), tmf, 0, 0,
                    2 if hull_kind == "merchant" or code in SLOW else 4,
                    fire_controls(code, hull_kind), hull_kind,
                ))
        return out
    return []


def preset_key(ruleset_id: str, index: int) -> str:
    """The form value for a preset: ruleset and index in `class_presets` (FT2 repeats codes)."""
    return f"{ruleset_id}:{index}"


def find_preset(ruleset_id: str, key: str) -> ClassPreset | None:
    """The preset a form value names, or None (blank, or a class of another ruleset)."""
    rid, _sep, index = key.partition(":")
    presets = class_presets(ruleset_id)
    if rid != ruleset_id or not index.isdigit() or int(index) >= len(presets):
        return None
    return presets[int(index)]


def preset_systems(ruleset_id: str, race: str, preset: ClassPreset) -> list[str]:
    """System types the preset starts with: its fire controls and, for a carrier, two hangar bays
    of one fighter group each (FT2: two fighter groups); only those the race can mount."""
    types = {s.type for s in RULESETS[ruleset_id].system_types(race, {})}
    wanted = ["fire_control"] * preset.fire_controls
    if preset.code.startswith("CV"):
        wanted += [("fighter_group" if ruleset_id == "ft2" else "hangar")] * CARRIER_BAYS
    return [t for t in wanted if t in types]


def apply_preset(design: dict, preset: ClassPreset) -> dict:
    """Fill a fresh design's hull from the preset. Every preset starts FTL-capable."""
    design.update(
        type_label=preset.label, type_code=preset.code, hull_kind=preset.hull_kind,
        tmf=preset.tmf, hull_boxes=preset.hull_boxes, armour=preset.armour, thrust=preset.thrust,
        ftl=True,
    )
    return design


# ---- Re-classing after a MASS change ------------------------------------------------------------


def _tables(ruleset_id: str) -> tuple:
    if ruleset_id == "fb":
        return fb_data.SHIP_CLASSES, fb_data.CARRIER_CLASSES
    if ruleset_id == "ftcd":
        return ftcd_data.SHIP_CLASSES, ftcd_data.CARRIER_CLASSES
    return ()


def reclass(design: dict) -> tuple[str, str] | None:
    """A new (label, code) when the design's MASS has left the band of its class, else None.

    Only a design whose type code is one of the ruleset's classes is touched; a band list is
    kept (a carrier stays a carrier). FT2 prints one MASS per class, so there the class is the
    nearest of the same kind, as its type suggestion picks."""
    code, tmf, rid = design.get("type_code"), design.get("tmf", 0), design.get("ruleset")
    if rid == "ft2":
        for table in ft2_data.BASIC_CLASSES.values():
            if any(c == code for _l, c, _m in table):
                label, new_code, _m = min(table, key=lambda c: (abs(c[2] - tmf), c[2]))
                if new_code == code:
                    return None
                return ft2_data.class_label(label), new_code
        return None
    for table in _tables(rid):
        band = next((c for c in table if c[1] == code), None)
        if band is None:
            continue
        _label, _code, low, high = band
        if low <= tmf and (high is None or tmf <= high):
            return None
        return _nearest_band(tmf, table)
    return None


def class_for_code(ruleset_id: str, code: str, tmf: int = 0) -> tuple[str, str] | None:
    """(label, code) of the ruleset's class with this code, any case, or None. FT2 repeats SC
    (courier boat, scoutship), so there the one nearest the MASS wins."""
    code = code.strip().upper()
    if ruleset_id == "ft2":
        matches = [c for table in ft2_data.BASIC_CLASSES.values() for c in table if c[1] == code]
        if not matches:
            return None
        label, found, _m = min(matches, key=lambda c: (abs(c[2] - tmf), c[2]))
        return ft2_data.class_label(label), found
    for table in _tables(ruleset_id):
        band = next((c for c in table if c[1] == code), None)
        if band:
            return fb_data.translated_class_label(band[0]), band[1]
    return None


def _nearest_band(tmf: int, table: tuple) -> tuple[str, str]:
    """The band holding tmf whose centre is nearest (ties to the smaller), as the type
    suggestion picks; past either end of the table, the end class."""
    inside = [c for c in table if c[2] <= tmf and (c[3] is None or tmf <= c[3])]
    if not inside:
        label, code = (table[0] if tmf < table[0][2] else table[-1])[:2]
    else:
        label, code, _low, _high = min(
            inside, key=lambda c: abs(tmf - (c[2] if c[3] is None else (c[2] + c[3]) / 2)))
    return fb_data.translated_class_label(label), code
