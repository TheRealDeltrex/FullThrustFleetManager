"""Read fire arcs off the vector SSDs in the processed Fleet Book PDFs.

Every arc-capable icon (beam battery, pulse torpedo, SM launcher, ...) is drawn as a disc split
into six segments by a divider path (six straight lines round a circle). The disc is filled dark
grey and each covered arc is a white wedge drawn over it; an all-white disc covers all six arcs.
Fore is up. This reads those paths instead of eyeballing pixels; the catalog author checks the
output against the rendered page (PLAN 8 step 2) and the NPV gate checks the costs.

    python tools/ssd_arcs.py "Fleet Book 1.pdf" 16 17
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parent.parent
# Angle of each arc's centre in page coordinates (y grows downward), clockwise from fore.
ARC_ANGLES = {"F": -90, "FS": -30, "AS": 30, "A": 90, "AP": 150, "FP": -150}


def _is_white(fill) -> bool:
    return fill is not None and all(c > 0.9 for c in fill)


def _polygon(drawing: dict) -> list[tuple[float, float]]:
    """The path as a polygon, sampling each Bezier segment."""
    pts: list[tuple[float, float]] = []
    for it in drawing["items"]:
        if it[0] == "l":
            pts += [(it[1].x, it[1].y), (it[2].x, it[2].y)]
        elif it[0] == "c":
            p0, p1, p2, p3 = it[1:5]
            for i in range(9):
                t = i / 8
                u = 1 - t
                pts.append(
                    (
                        u**3 * p0.x + 3 * u * u * t * p1.x + 3 * u * t * t * p2.x + t**3 * p3.x,
                        u**3 * p0.y + 3 * u * u * t * p1.y + 3 * u * t * t * p2.y + t**3 * p3.y,
                    )
                )
    return pts


def _inside(pt: tuple[float, float], poly: list[tuple[float, float]]) -> bool:
    x, y = pt
    inside = False
    for (x0, y0), (x1, y1) in zip(poly, poly[1:] + poly[:1]):
        if (y0 > y) != (y1 > y) and x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
            inside = not inside
    return inside


def rings(page: pymupdf.Page) -> list[dict]:
    """[{x, y, arcs, label}] for every arc ring on the page, sorted top-to-bottom, left-to-right.
    label is any text inside the disc (the beam class digit), else ""."""
    drawings = page.get_drawings()
    dividers = [
        d
        for d in drawings
        if d.get("fill") is None
        and sum(1 for it in d["items"] if it[0] == "l") == 6
        and 8 < d["rect"].width < 30
    ]
    words = page.get_text("words")
    found = []
    for div in dividers:
        dc = ((div["rect"].x0 + div["rect"].x1) / 2, (div["rect"].y0 + div["rect"].y1) / 2)
        discs = [
            d
            for d in drawings
            if d.get("fill") is not None
            and len(d["items"]) == 4
            and all(it[0] == "c" for it in d["items"])
            and div["rect"].width - 1 < d["rect"].width < div["rect"].width + 5
            and abs((d["rect"].x0 + d["rect"].x1) / 2 - dc[0]) < 1.5
            and abs((d["rect"].y0 + d["rect"].y1) / 2 - dc[1]) < 1.5
        ]
        if not discs:
            continue
        discs.sort(key=lambda d: -d["rect"].width)  # the outer ring, not the number disc
        r = discs[0]["rect"]
        cx, cy, radius = (r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2, r.width / 2
        if _is_white(discs[0]["fill"]):
            arcs = set(ARC_ANGLES)
        else:
            wedges = [
                _polygon(d)
                for d in drawings
                if d is not discs[0]
                and _is_white(d.get("fill"))
                and d["rect"].intersects(r)
                and d["rect"].width <= r.width + 0.5
                and d["rect"].height <= r.height + 0.5
            ]
            arcs = set()
            for arc, deg in ARC_ANGLES.items():
                pt = (
                    cx + 0.85 * radius * math.cos(math.radians(deg)),
                    cy + 0.85 * radius * math.sin(math.radians(deg)),
                )
                if any(_inside(pt, w) for w in wedges):
                    arcs.add(arc)
        label = " ".join(w[4] for w in words if r.contains(pymupdf.Rect(w[:4])))
        found.append(
            {
                "x": round(cx, 1),
                "y": round(cy, 1),
                "arcs": [a for a in ARC_ANGLES if a in arcs],
                "label": label,
            }
        )
    return sorted(found, key=lambda f: (round(f["y"] / 6), f["x"]))


def pies(page: pymupdf.Page) -> list[dict]:
    """[{x, y, arcs}] for every partial-ring icon: SM launchers and racks, and pulse torpedoes
    that traverse more than one arc. The covered arcs are one white ring segment (line, curves,
    line) around a small white inner disc; an arc is covered when the point midway between the
    inner disc and the outer edge, in that arc's direction, lies inside the segment."""
    drawings = page.get_drawings()
    inner_discs = [
        d
        for d in drawings
        if _is_white(d.get("fill"))
        and len(d["items"]) == 4
        and all(it[0] == "c" for it in d["items"])
        and 6 < d["rect"].width < 14
    ]
    found = []
    for d in drawings:
        items = d["items"]
        if not (
            _is_white(d.get("fill"))
            and len(items) >= 3
            and items[0][0] == "l"
            and items[-1][0] == "l"
            and all(it[0] == "c" for it in items[1:-1])
        ):
            continue
        discs = [c for c in inner_discs if c["rect"].intersects(d["rect"])]
        if not discs:
            continue
        r = discs[0]["rect"]
        cx, cy, r_in = (r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2, r.width / 2
        poly = _polygon(d)
        r_out = max(math.hypot(x - cx, y - cy) for x, y in poly)
        mid = (r_in + r_out) / 2
        arcs = [
            arc
            for arc, deg in ARC_ANGLES.items()
            if _inside((cx + mid * math.cos(math.radians(deg)), cy + mid * math.sin(math.radians(deg))), poly)
        ]
        found.append({"x": round(cx, 1), "y": round(cy, 1), "arcs": arcs})
    return sorted(found, key=lambda f: (round(f["y"] / 6), f["x"]))


def arrows(page: pymupdf.Page) -> list[dict]:
    """[{x, y, arc}] for every Sa'Vasku Pod Launcher Node (FB2 pp.26-32).

    A pod launcher is drawn as a cogged disc with an arrow beside it pointing along its single
    fire arc; the arrow is two black paths, a quad shaft and a triangular head. Stinger nodes and
    power generators use the same cogged disc with no arrow, so the arrowhead is what identifies
    a launcher, and the direction from the disc's centre to the head gives the arc.
    """
    drawings = page.get_drawings()
    discs = [
        d for d in drawings
        if d.get("fill") is not None and not _is_white(d["fill"])
        and len(d["items"]) == 12 and all(it[0] == "c" for it in d["items"])
    ]
    heads = [
        d for d in drawings
        if d.get("fill") is not None and not _is_white(d["fill"])
        and sum(1 for it in d["items"] if it[0] == "l") == 3
        and all(it[0] == "l" for it in d["items"])
    ]
    found = []
    for disc in discs:
        r = disc["rect"]
        cx, cy = (r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2
        near = [
            h for h in heads
            if math.hypot((h["rect"].x0 + h["rect"].x1) / 2 - cx,
                          (h["rect"].y0 + h["rect"].y1) / 2 - cy) < r.width * 1.4
        ]
        if not near:
            continue
        head = min(near, key=lambda h: math.hypot((h["rect"].x0 + h["rect"].x1) / 2 - cx,
                                                  (h["rect"].y0 + h["rect"].y1) / 2 - cy))
        hx = (head["rect"].x0 + head["rect"].x1) / 2
        hy = (head["rect"].y0 + head["rect"].y1) / 2
        degrees = math.degrees(math.atan2(hy - cy, hx - cx))
        arc = min(ARC_ANGLES, key=lambda a: abs((degrees - ARC_ANGLES[a] + 180) % 360 - 180))
        found.append({"x": round(cx, 1), "y": round(cy, 1), "arc": arc})
    return sorted(found, key=lambda f: (round(f["y"] / 6), f["x"]))


def stars(page: pymupdf.Page) -> list[dict]:
    """[{x, y, arcs}] for every Phalon Pulser Battery (FB2 pp.38-45).

    A pulser is drawn as a small hexagon (the blank the player writes L, M or C into) ringed by
    six triangles, one per arc: a white triangle is an arc the battery covers, a black one an arc
    it does not. So a one-arc pulser shows one white point and five black, and an all-arc battery
    six white ones.
    """
    drawings = page.get_drawings()
    bodies = [
        d for d in drawings
        if _is_white(d.get("fill")) and len(d["items"]) == 6
        and all(it[0] == "l" for it in d["items"]) and 8 < d["rect"].width < 14
    ]
    points = [
        d for d in drawings
        if d.get("fill") is not None and len(d["items"]) == 3
        and all(it[0] == "l" for it in d["items"]) and 3 < d["rect"].width < 8
    ]
    found = []
    for body in bodies:
        r = body["rect"]
        cx, cy = (r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2
        arcs = []
        for arc, degrees in ARC_ANGLES.items():
            want = (cx + 6.9 * math.cos(math.radians(degrees)),
                    cy + 6.9 * math.sin(math.radians(degrees)))
            near = [
                d for d in points
                if math.hypot((d["rect"].x0 + d["rect"].x1) / 2 - want[0],
                              (d["rect"].y0 + d["rect"].y1) / 2 - want[1]) < 3.0
            ]
            if near and _is_white(near[0]["fill"]):
                arcs.append(arc)
        if arcs:
            found.append({"x": round(cx, 1), "y": round(cy, 1),
                          "arcs": [a for a in ARC_ANGLES if a in arcs]})
    return sorted(found, key=lambda f: (round(f["y"] / 6), f["x"]))


def main() -> None:
    doc = pymupdf.open(ROOT / "rulebooks" / sys.argv[1])
    for p in map(int, sys.argv[2:]):
        for f in rings(doc[p - 1]):
            arcs = "all" if len(f["arcs"]) == 6 else ",".join(f["arcs"])
            print(f"p{p} ({f['x']:6.1f},{f['y']:6.1f}) [{f['label']:>2}] {arcs}")
        for f in pies(doc[p - 1]):
            print(f"p{p} ({f['x']:6.1f},{f['y']:6.1f}) pie {','.join(f['arcs'])}")
        for f in arrows(doc[p - 1]):
            print(f"p{p} ({f['x']:6.1f},{f['y']:6.1f}) arrow {f['arc']}")
        for f in stars(doc[p - 1]):
            arcs = "all" if len(f["arcs"]) == 6 else ",".join(f["arcs"])
            print(f"p{p} ({f['x']:6.1f},{f['y']:6.1f}) pulser {arcs}")


if __name__ == "__main__":
    main()
