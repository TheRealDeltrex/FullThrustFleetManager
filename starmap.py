"""Campaign star maps (PLAN 11.3, roadmap step C2): the hex grid, the random generator and the
SVG drawing. Pure: store keeps and normalises the map, app draws it.

FT p.35 suggests a hex map at 1 hex = 1 light year. Hexes are flat-topped in "odd-q" offset
coordinates: q is the column, r the row, and odd columns sit half a hex lower. A system is
{"q", "r", "name", "kind", "owner", "base"}: kind is settled, outpost or empty (FT pp.36-37:
settled worlds, small scientific or mining bases, bare stars), owner a side id or "", base a
naval base with a repair yard (FT p.36).
"""

from __future__ import annotations

import math
import random
from html import escape

KINDS = ("settled", "outpost", "empty")
MIN_SIZE, MAX_SIZE = 4, 30
DEFAULT_WIDTH, DEFAULT_HEIGHT, DEFAULT_STARS = 12, 10, 16

# Real star names, for random maps and as the suggestion for a new system.
STAR_NAMES = (
    "Achernar", "Acrux", "Adhara", "Albireo", "Alcor", "Aldebaran", "Alderamin", "Algenib",
    "Algol", "Alhena", "Alioth", "Alkaid", "Almach", "Alnair", "Alnilam", "Alphard",
    "Alphecca", "Alpheratz", "Altair", "Ankaa", "Antares", "Arcturus", "Arneb", "Atria",
    "Avior", "Barnard", "Bellatrix", "Betelgeuse", "Canopus", "Capella", "Caph", "Castor",
    "Cebalrai", "Deneb", "Denebola", "Diphda", "Dubhe", "Elnath", "Eltanin", "Enif",
    "Fomalhaut", "Gacrux", "Gienah", "Hadar", "Hamal", "Izar", "Kochab", "Kornephoros",
    "Lalande", "Lesath", "Luyten", "Markab", "Menkar", "Menkent", "Merak", "Miaplacidus",
    "Mintaka", "Mirach", "Mirfak", "Mirzam", "Mizar", "Naos", "Nunki", "Peacock",
    "Phecda", "Polaris", "Pollux", "Procyon", "Rasalhague", "Regulus", "Rigel", "Ross",
    "Ruchbah", "Sabik", "Sadr", "Saiph", "Scheat", "Schedar", "Shaula", "Sirius",
    "Spica", "Suhail", "Tarazed", "Thuban", "Unukalhai", "Vega", "Wezen", "Wolf",
    "Zaurak", "Zosma", "Zubenelgenubi", "Zubeneschamali",
)


def hex_distance(a: tuple[int, int], b: tuple[int, int]) -> int:
    """Hexes between two (q, r) positions; an FTL fleet moves 6 a week (FT p.35)."""
    def cube(q: int, r: int) -> tuple[int, int, int]:
        z = r - (q - (q & 1)) // 2
        return q, -q - z, z

    (x1, y1, z1), (x2, y2, z2) = cube(*a), cube(*b)
    return max(abs(x1 - x2), abs(y1 - y2), abs(z1 - z2))


def blank(width: int = DEFAULT_WIDTH, height: int = DEFAULT_HEIGHT) -> dict:
    return {"width": clamp_size(width), "height": clamp_size(height), "seed": None, "systems": []}


def clamp_size(n: int) -> int:
    return max(MIN_SIZE, min(MAX_SIZE, n))


def system_at(starmap: dict, q: int, r: int) -> dict | None:
    return next((s for s in starmap["systems"] if s["q"] == q and s["r"] == r), None)


def unused_name(starmap: dict, rng: random.Random | None = None) -> str:
    taken = {s["name"] for s in starmap["systems"]}
    free = [n for n in STAR_NAMES if n not in taken]
    if not free:
        return f"Star {len(taken) + 1}"
    return rng.choice(free) if rng else free[0]


def generate(width: int, height: int, stars: int, side_ids: list[str], seed: int) -> dict:
    """A random map (an app rule): stars at least two hexes apart, about 40% settled, 30%
    outposts and 30% bare stars. The first two sides get a home naval base at opposite ends,
    and a settled world or outpost belongs to the home clearly nearer to it; the rest is
    contested. The same seed and settings give the same map."""
    rng = random.Random(seed)
    starmap = blank(width, height)
    starmap["seed"] = seed
    cells = [(q, r) for q in range(starmap["width"]) for r in range(starmap["height"])]
    rng.shuffle(cells)
    placed: list[tuple[int, int]] = []
    for cell in cells:
        if len(placed) >= stars:
            break
        if all(hex_distance(cell, p) >= 2 for p in placed):
            placed.append(cell)
    for q, r in placed:
        roll = rng.random()
        kind = "settled" if roll < 0.4 else "outpost" if roll < 0.7 else "empty"
        starmap["systems"].append({"q": q, "r": r, "name": unused_name(starmap, rng),
                                   "kind": kind, "owner": "", "base": False})
    homes = []
    if len(side_ids) >= 2 and len(placed) >= 2:
        west = min(starmap["systems"], key=lambda s: (s["q"], abs(s["r"] - starmap["height"] // 2)))
        east = max(starmap["systems"], key=lambda s: (s["q"], -abs(s["r"] - starmap["height"] // 2)))
        homes = [(west, side_ids[0]), (east, side_ids[1])]
        for home, side in homes:
            home.update(kind="settled", owner=side, base=True)
    for system in starmap["systems"]:
        if system["owner"] or system["kind"] == "empty" or not homes:
            continue
        (h1, s1), (h2, s2) = homes
        d1 = hex_distance((system["q"], system["r"]), (h1["q"], h1["r"]))
        d2 = hex_distance((system["q"], system["r"]), (h2["q"], h2["r"]))
        if abs(d1 - d2) > 2:
            system["owner"] = s1 if d1 < d2 else s2
    starmap["systems"].sort(key=lambda s: (s["q"], s["r"]))
    return starmap


def holds(starmap: dict, side: str, count: int, include: str = "") -> bool:
    """Whether the side holds at least `count` settled systems, `include` (a system name) among
    them when given: the shape of FT p.36's victory conditions."""
    held = [s for s in starmap["systems"] if s["owner"] == side and s["kind"] == "settled"]
    return len(held) >= count and (not include or any(s["name"] == include for s in held))


def hex_label(q: int, r: int) -> str:
    """The printed hex number, column then row from 01 ("0304")."""
    return f"{q + 1:02d}{r + 1:02d}"


# ---- Drawing --------------------------------------------------------------------------------------

SIZE = 20                                  # hex radius in SVG units
_H = SIZE * math.sqrt(3)


def _centre(q: int, r: int) -> tuple[float, float]:
    return SIZE * 1.5 * q + SIZE + 2, _H * (r + 0.5 * (q & 1)) + _H / 2 + 2


def _corners(x: float, y: float) -> str:
    return " ".join(f"{x + SIZE * math.cos(math.radians(60 * i)):.1f},"
                    f"{y + SIZE * math.sin(math.radians(60 * i)):.1f}" for i in range(6))


def to_svg(starmap: dict, sides: list[dict], href: str = "", selected: tuple[int, int] | None = None,
           label: str = "", forces: list[dict] | None = None) -> str:
    """The map as inline SVG. With href ("/campaign?hex="), every hex links to href + "q,r", which
    selects it without any script. Side colours are side-0 ... side-7 classes in style.css."""
    width = SIZE * (1.5 * starmap["width"] + 0.5) + 4
    height = _H * (starmap["height"] + 0.5) + 4
    colour = {s["id"]: f"side-{i}" for i, s in enumerate(sides)}
    out = [f'<svg class="starmap" viewBox="0 0 {width:.0f} {height:.0f}" role="img" '
           f'aria-label="{escape(label)}">']
    for q in range(starmap["width"]):
        for r in range(starmap["height"]):
            x, y = _centre(q, r)
            cls = "hex sel" if selected == (q, r) else "hex"
            poly = (f'<polygon class="{cls}" points="{_corners(x, y)}">'
                    f'<title>{hex_label(q, r)}</title></polygon>')
            out.append(f'<a href="{escape(href)}{q},{r}">{poly}</a>' if href else poly)
    if selected:
        # Drawn again on top, so the neighbours' outlines do not cover the highlight.
        out.append(f'<polygon class="hex-ring" points="{_corners(*_centre(*selected))}"/>')
    for s in starmap["systems"]:
        x, y = _centre(s["q"], s["r"])
        side = colour.get(s["owner"], "unowned")
        tag = f'<a href="{escape(href)}{s["q"]},{s["r"]}">' if href else "<g>"
        out.append(tag)
        if s["base"]:
            out.append(f'<circle class="base {side}" cx="{x:.1f}" cy="{y - 3:.1f}" r="8.5"/>')
        radius = {"settled": 5.5, "outpost": 3.5, "empty": 2.2}[s["kind"]]
        out.append(f'<circle class="star {s["kind"]} {side}" cx="{x:.1f}" cy="{y - 3:.1f}" r="{radius}"/>')
        out.append(f'<text class="star-name" x="{x:.1f}" y="{y + 12:.1f}">{escape(s["name"])}</text>')
        out.append("</a>" if href else "</g>")
    # Task forces: a pennant per side present on a hex, its orders as a dashed line.
    for f in forces or []:
        if f.get("order"):
            (x1, y1), (x2, y2) = _centre(f["q"], f["r"]), _centre(*f["order"])
            out.append(f'<line class="order {colour.get(f["side"], "unowned")}" x1="{x1:.1f}" y1="{y1:.1f}" '
                       f'x2="{x2:.1f}" y2="{y2:.1f}"/>')
    placed: dict[tuple[int, int], list[str]] = {}
    for f in forces or []:
        sides_here = placed.setdefault((f["q"], f["r"]), [])
        if f["side"] in sides_here:
            continue
        sides_here.append(f["side"])
        x, y = _centre(f["q"], f["r"])
        x, y = x - 11 + 7 * (len(sides_here) - 1), y - 13
        out.append(f'<path class="pennant {colour.get(f["side"], "unowned")}" '
                   f'd="M{x:.1f} {y:.1f}v9M{x:.1f} {y:.1f}l6 2.5l-6 2.5z">'
                   f'<title>{escape(f["name"])}</title></path>')
    out.append("</svg>")
    return "".join(out)
