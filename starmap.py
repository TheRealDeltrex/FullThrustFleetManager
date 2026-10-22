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
MAX_STARS = 400
SPACINGS = (1, 2, 3, 4)
DEFAULT_SPACING = 2
# Exact counts per side (roadmap G1, Master 2026-10-22): settled worlds and outposts (home among
# them), naval bases (optional, home first) and whether settled worlds form a core; neutral
# systems belong to no side.
# `core`: settled worlds nearest home and outposts beyond them; off, the two are mixed.
DEFAULT_COUNTS = {"settled": 2, "outposts": 1, "bases": 1, "core": True}
# Neutral systems: none, on random free stars, or on the stars sides are most evenly near (a
# border region).
NEUTRAL_PLACES = ("none", "random", "border")
DEFAULT_NEUTRAL = {"settled": 2, "outposts": 2, "place": "none"}
MAX_GENERATED_SIDES = 5
NAME_STYLES = ("stars", "catalog")
# Survey catalogue prefixes, as FT p.37 names its minor stars (VN-459, HR-1306).
CATALOGS = ("BD", "GJ", "HD", "HR", "LHS", "VN")

# Real star names, for random maps and as the suggestion for a new system.
STAR_NAMES = (
    "Acamar", "Achernar", "Achird", "Acrux", "Adhafera", "Adhara", "Adhil", "Ain", "Aladfar",
    "Albaldah", "Albireo", "Alcor", "Alcyone", "Aldebaran", "Alderamin", "Aldhanab", "Aldulfin",
    "Alfirk", "Algedi", "Algenib", "Algieba", "Algol", "Algorab", "Alhena", "Alioth", "Aljanah",
    "Alkaid", "Alkalurops", "Alkes", "Almach", "Alnair", "Alnasl", "Alnilam", "Alnitak", "Alniyat",
    "Alphard", "Alphecca", "Alpheratz", "Alrescha", "Alsafi", "Alsephina", "Alshain", "Altair",
    "Altais", "Alterf", "Aludra", "Alula Australis", "Alula Borealis", "Alya", "Ancha",
    "Angetenar", "Ankaa", "Anser", "Antares", "Arcturus", "Arkab", "Arneb", "Ascella",
    "Asellus Australis", "Asellus Borealis", "Aspidiske", "Asterope", "Atik", "Atlas", "Atria",
    "Avior", "Azelfafage", "Azha", "Baham", "Barnard", "Baten Kaitos", "Beemim", "Bellatrix",
    "Betelgeuse", "Biham", "Botein", "Brachium", "Canopus", "Capella", "Caph", "Castor",
    "Cebalrai", "Celaeno", "Chara", "Chertan", "Cor Caroli", "Cursa", "Dabih", "Deneb",
    "Deneb Algedi", "Denebola", "Diadem", "Diphda", "Dschubba", "Dubhe", "Electra", "Elgafar",
    "Elkurud", "Elnath", "Eltanin", "Enif", "Errai", "Fafnir", "Fang", "Fawaris", "Fomalhaut",
    "Fulu", "Furud", "Gacrux", "Gianfar", "Gienah", "Ginan", "Gomeisa", "Grumium", "Hadar",
    "Hamal", "Hassaleh", "Heze", "Homam", "Imai", "Izar", "Jabbah", "Kaus Australis",
    "Kaus Borealis", "Kaus Media", "Keid", "Kitalpha", "Kochab", "Kornephoros", "Kraz", "Kurhah",
    "Lalande", "Larawag", "Lesath", "Lucida", "Luyten", "Maia", "Marfik", "Markab", "Matar",
    "Mebsuta", "Megrez", "Meissa", "Mekbuda", "Menkalinan", "Menkar", "Menkent", "Menkib", "Merak",
    "Merope", "Mesarthim", "Miaplacidus", "Mimosa", "Minelauva", "Mintaka", "Mira", "Mirach",
    "Mirfak", "Mirzam", "Mizar", "Mothallah", "Muphrid", "Muscida", "Naos", "Nashira", "Nekkar",
    "Nembus", "Nihal", "Nunki", "Nusakan", "Okab", "Peacock", "Phact", "Phecda", "Pherkad",
    "Pipirima", "Pleione", "Polaris", "Polis", "Pollux", "Porrima", "Procyon", "Propus", "Proxima",
    "Ran", "Rasalgethi", "Rasalhague", "Rastaban", "Regulus", "Revati", "Rigel", "Rigil Kentaurus",
    "Ross", "Rotanev", "Ruchbah", "Rukbat", "Sabik", "Sadachbia", "Sadalbari", "Sadalmelik",
    "Sadalsuud", "Sadr", "Saiph", "Sargas", "Sarin", "Sceptrum", "Scheat", "Schedar", "Seginus",
    "Shaula", "Sheliak", "Sheratan", "Sirius", "Situla", "Skat", "Spica", "Sualocin", "Suhail",
    "Sulafat", "Syrma", "Talitha", "Tania Australis", "Tania Borealis", "Tarazed", "Taygeta",
    "Tegmine", "Tejat", "Thuban", "Tiaki", "Titawin", "Toliman", "Tureis", "Unukalhai",
    "Unurgunite", "Vega", "Vindemiatrix", "Wasat", "Wezen", "Wolf", "Xamidimura", "Yed Posterior",
    "Yed Prior", "Yildun", "Zaniah", "Zaurak", "Zavijava", "Zosma", "Zubenelgenubi",
    "Zubenelhakrabi", "Zubeneschamali",
)
GREEK = ("Alpha", "Beta", "Gamma", "Delta", "Epsilon", "Zeta", "Eta", "Theta", "Iota", "Kappa",
         "Lambda", "Mu", "Nu", "Xi", "Omicron", "Pi", "Rho", "Sigma", "Tau", "Upsilon", "Phi",
         "Chi", "Psi", "Omega")
CONSTELLATIONS = (
    "Andromedae", "Antliae", "Apodis", "Aquarii", "Aquilae", "Arae", "Arietis", "Aurigae",
    "Bootis", "Caeli", "Camelopardalis", "Cancri", "Canum Venaticorum", "Canis Majoris",
    "Canis Minoris", "Capricorni", "Carinae", "Cassiopeiae", "Centauri", "Cephei", "Ceti",
    "Chamaeleontis", "Circini", "Columbae", "Comae Berenices", "Coronae Australis",
    "Coronae Borealis", "Corvi", "Crateris", "Crucis", "Cygni", "Delphini", "Doradus",
    "Draconis", "Equulei", "Eridani", "Fornacis", "Geminorum", "Gruis", "Herculis", "Horologii",
    "Hydrae", "Hydri", "Indi", "Lacertae", "Leonis", "Leonis Minoris", "Leporis", "Librae",
    "Lupi", "Lyncis", "Lyrae", "Mensae", "Microscopii", "Monocerotis", "Muscae", "Normae",
    "Octantis", "Ophiuchi", "Orionis", "Pavonis", "Pegasi", "Persei", "Phoenicis", "Pictoris",
    "Piscium", "Piscis Austrini", "Puppis", "Pyxidis", "Reticuli", "Sagittae", "Sagittarii",
    "Scorpii", "Sculptoris", "Scuti", "Serpentis", "Sextantis", "Tauri", "Telescopii",
    "Trianguli", "Trianguli Australis", "Tucanae", "Ursae Majoris", "Ursae Minoris", "Velorum",
    "Virginis", "Volantis", "Vulpeculae",
)
# Proper names plus Bayer designations ("Tau Ceti"), so large maps rarely repeat (Master asked
# for at least 1200).
NAME_POOL = STAR_NAMES + tuple(f"{g} {c}" for c in CONSTELLATIONS for g in GREEK)


def hex_distance(a: tuple[int, int], b: tuple[int, int]) -> int:
    """Hexes between two (q, r) positions; an FTL fleet moves 6 a week (FT p.35)."""
    def cube(q: int, r: int) -> tuple[int, int, int]:
        z = r - (q - (q & 1)) // 2
        return q, -q - z, z

    (x1, y1, z1), (x2, y2, z2) = cube(*a), cube(*b)
    return max(abs(x1 - x2), abs(y1 - y2), abs(z1 - z2))


def blank(width: int = DEFAULT_WIDTH, height: int = DEFAULT_HEIGHT) -> dict:
    """An empty map. `draft` holds a generated map's settings until it is finalised; while it
    does, changing them generates the map again."""
    return {"width": clamp_size(width), "height": clamp_size(height), "seed": None, "systems": [],
            "draft": None, "frontline": False}


def clamp_size(n: int) -> int:
    return max(MIN_SIZE, min(MAX_SIZE, n))


def system_at(starmap: dict, q: int, r: int) -> dict | None:
    return next((s for s in starmap["systems"] if s["q"] == q and s["r"] == r), None)


def unused_name(starmap: dict, rng: random.Random | None = None) -> str:
    """A pool name no system on the map has: a proper star name about half the time while any
    are left, otherwise a Bayer designation."""
    taken = {s["name"] for s in starmap["systems"]}
    proper = [n for n in STAR_NAMES if n not in taken]
    if not rng:
        free = proper or [n for n in NAME_POOL if n not in taken]
        return free[0] if free else f"Star {len(taken) + 1}"
    if proper and rng.random() < 0.5:
        return rng.choice(proper)
    for _try in range(50):
        name = rng.choice(NAME_POOL)
        if name not in taken:
            return name
    free = [n for n in NAME_POOL if n not in taken]
    return rng.choice(free) if free else f"Star {len(taken) + 1}"


def catalog_name(starmap: dict, rng: random.Random) -> str:
    taken = {s["name"] for s in starmap["systems"]}
    while True:
        name = f"{rng.choice(CATALOGS)}-{rng.randrange(100, 10000)}"
        if name not in taken:
            return name


class CountsError(ValueError):
    """The counts ask for more systems than the map holds: `needed` against `placed` stars."""

    def __init__(self, needed: int, placed: int):
        super().__init__(f"{needed} systems needed, {placed} stars placed")
        self.needed, self.placed = needed, placed


def settings(width: int, height: int, stars: int, side_ids: list[str], *,
             spacing: int = DEFAULT_SPACING, counts: dict | None = None,
             neutral: dict | None = None, names: str = "stars") -> dict:
    """The generator's inputs as kept on a draft map, with defaults filled in."""
    counts = counts or {}
    return {
        "width": clamp_size(width), "height": clamp_size(height),
        "stars": max(1, min(MAX_STARS, stars)), "spacing": spacing, "names": names,
        "sides": {side: dict(DEFAULT_COUNTS, **counts.get(side, {})) for side in side_ids},
        "neutral": dict(DEFAULT_NEUTRAL, **(neutral or {})),
    }


def needed(draft: dict) -> int:
    """Systems the counts take: every side's settled worlds and outposts, and the neutral ones."""
    neutral = draft["neutral"]
    return (sum(c["settled"] + c["outposts"] for c in draft["sides"].values())
            + (neutral["settled"] + neutral["outposts"] if neutral["place"] != "none" else 0))


def generate(width: int, height: int, stars: int, side_ids: list[str], seed: int, *,
             spacing: int = DEFAULT_SPACING, counts: dict | None = None,
             neutral: dict | None = None, names: str = "stars") -> dict:
    """A random map (an app rule, roadmap G1): stars at least `spacing` hexes apart. `counts`
    gives each side exactly its settled worlds and outposts (its home among them) and naval bases
    (side id -> {"settled", "outposts", "bases", "core"}, DEFAULT_COUNTS where missing);
    `neutral` the settled worlds and outposts nobody holds and their `place` (NEUTRAL_PLACES:
    none, random free stars, or a border region where the sides' systems are most evenly near);
    the rest are bare stars. Homes: the first two sides at opposite ends, any others as far from those as the
    map allows; a home is settled unless the side has only outposts. Sides then take turns
    claiming the free star nearest their home until their counts are met. With `core` its
    settled worlds are the nearest and its outposts lie beyond, otherwise the two are mixed.
    Bases go on home, then on the side's settled worlds furthest from it, then its outposts.
    Raises CountsError when the stars placed cannot hold the counts. Names are real stars or
    survey catalogue numbers. The same seed and settings give the same map, which comes back as
    a draft holding those settings."""
    draft = settings(width, height, stars, side_ids, spacing=spacing, counts=counts,
                     neutral=neutral, names=names)
    rng = random.Random(seed)
    starmap = blank(width, height)
    starmap["seed"] = seed
    cells = [(q, r) for q in range(starmap["width"]) for r in range(starmap["height"])]
    rng.shuffle(cells)
    placed: list[tuple[int, int]] = []
    for cell in cells:
        if len(placed) >= draft["stars"]:
            break
        if all(hex_distance(cell, p) >= spacing for p in placed):
            placed.append(cell)
    if needed(draft) > len(placed):
        raise CountsError(needed(draft), len(placed))
    for q, r in placed:
        name = catalog_name(starmap, rng) if names == "catalog" else unused_name(starmap, rng)
        starmap["systems"].append({"q": q, "r": r, "name": name, "kind": "empty", "owner": "", "base": False})
    systems = starmap["systems"]
    mid = starmap["height"] // 2
    homes: list[tuple[dict, str]] = []
    for side in side_ids:
        if not homes:
            home = min(systems, key=lambda s: (s["q"], abs(s["r"] - mid)))
        elif len(homes) == 1:
            home = max((s for s in systems if s is not homes[0][0]),
                       key=lambda s: (s["q"], -abs(s["r"] - mid)))
        else:
            free = [s for s in systems if all(s is not h for h, _side in homes)]
            home = max(free, key=lambda s: min(_apart(s, h) for h, _side in homes))
        home.update(kind="settled" if draft["sides"][side]["settled"] else "outpost", owner=side)
        homes.append((home, side))
    # Each side's claims, nearest first; a side drops out once it has what its counts ask for.
    wants = {side: draft["sides"][side]["settled"] + draft["sides"][side]["outposts"] - 1
             for side in side_ids}
    claims: dict[str, list[dict]] = {side: [] for side in side_ids}
    while any(len(claims[side]) < wants[side] for side in side_ids):
        for home, side in homes:
            if len(claims[side]) >= wants[side]:
                continue
            free = [s for s in systems if not s["owner"]]
            pick = min(free, key=lambda s: (_apart(s, home), rng.random()))
            pick["owner"] = side
            claims[side].append(pick)
    for home, side in homes:
        c = draft["sides"][side]
        settled = c["settled"] - (home["kind"] == "settled")
        kinds = ["settled"] * settled + ["outpost"] * (len(claims[side]) - settled)
        if not c["core"]:
            rng.shuffle(kinds)
        for system, kind in zip(claims[side], kinds):
            system["kind"] = kind
        rest = sorted(claims[side], key=lambda s: (s["kind"] != "settled", -_apart(s, home)))
        for system in ([home] + rest)[:c["bases"]]:
            system["base"] = True
    neutral = draft["neutral"]
    free = [s for s in systems if not s["owner"]]
    rng.shuffle(free)
    if neutral["place"] == "border":
        held = {side: [s for s in systems if s["owner"] == side] for side in side_ids}

        def unevenness(s: dict) -> int:
            near = sorted(min(_apart(s, h) for h in own) for own in held.values() if own)
            return near[1] - near[0] if len(near) > 1 else 0
        free.sort(key=unevenness)                            # stable: ties stay shuffled
    if neutral["place"] != "none":
        for i, system in enumerate(free[:neutral["settled"] + neutral["outposts"]]):
            system["kind"] = "settled" if i < neutral["settled"] else "outpost"
    systems.sort(key=lambda s: (s["q"], s["r"]))
    starmap["draft"] = draft
    return starmap


def _apart(a: dict, b: dict) -> int:
    return hex_distance((a["q"], a["r"]), (b["q"], b["r"]))


def holds(starmap: dict, side: str, count: int, include: str = "") -> bool:
    """Whether the side holds at least `count` settled systems, `include` (a system name) among
    them when given: the shape of FT p.36's victory conditions."""
    held = [s for s in starmap["systems"] if s["owner"] == side and s["kind"] == "settled"]
    return len(held) >= count and (not include or any(s["name"] == include for s in held))


def neighbours(q: int, r: int) -> list[tuple[int, int]]:
    """The six hexes around (q, r) in odd-q coordinates, on or off the map."""
    down = q & 1
    return [(q, r - 1), (q, r + 1), (q - 1, r - 1 + down), (q - 1, r + down),
            (q + 1, r - 1 + down), (q + 1, r + down)]


NEUTRAL, OPEN = "~", "-"                    # frontline() regions: neutral worlds', nobody's
CLUSTER = 3                                 # neutral worlds this near each other form a cluster
DEFAULT_FRONT_REACH = 4                     # how far a side's systems project its front


def frontline(starmap: dict, reach: int = DEFAULT_FRONT_REACH) -> set[tuple[int, int]]:
    """The hexes on the front (an app rule, Master 2026-10-22). Each hex within `reach` of a
    side's held system belongs to the side whose system is strictly nearest; beyond that is open
    space. The front is every hex two sides are equally near, every hex beside one held by
    another side (so an odd gap gives a front two hexes wide and two opposing systems side by
    side are both on it) and every side's hex beside open space, so a side's sphere is always
    outlined. Neutral worlds (unowned
    settled worlds and outposts) hold their own hex, and one in a cluster (another within
    CLUSTER hexes) the hexes around it too, wherever no side's system is nearer. A side's hex
    beside that region is front, so a lone neutral world inside a side's reach is ringed by it
    and a cluster pushes it two hexes out. A neutral hex beside a side's system is front too."""
    held: dict[str, list[tuple[int, int]]] = {}
    neutral: list[tuple[int, int]] = []
    for s in starmap["systems"]:
        if s["owner"]:
            held.setdefault(s["owner"], []).append((s["q"], s["r"]))
        elif s["kind"] != "empty":
            neutral.append((s["q"], s["r"]))
    if not held:
        return set()
    radius = {w: int(any(o != w and hex_distance(w, o) <= CLUSTER for o in neutral)) for w in neutral}
    systems = {p: side for side, cells in held.items() for p in cells}
    owner: dict[tuple[int, int], str] = {}
    for q in range(starmap["width"]):
        for r in range(starmap["height"]):
            near = sorted((min(hex_distance((q, r), p) for p in cells), side)
                          for side, cells in held.items())
            if any(hex_distance((q, r), w) <= radius[w] and hex_distance((q, r), w) < near[0][0]
                   for w in neutral):
                owner[q, r] = NEUTRAL
            elif near[0][0] > reach:
                owner[q, r] = OPEN
            else:
                owner[q, r] = "" if len(near) > 1 and near[0][0] == near[1][0] else near[0][1]
    front = set()
    for cell, side in owner.items():
        around = [owner[n] for n in neighbours(*cell) if n in owner]
        if side == NEUTRAL:
            if any(n in systems for n in neighbours(*cell)):
                front.add(cell)
        elif side != OPEN and (not side or NEUTRAL in around or OPEN in around
                               or any(o not in (side, "", NEUTRAL) for o in around)):
            front.add(cell)
    return front


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
           label: str = "", forces: list[dict] | None = None,
           reach: int = DEFAULT_FRONT_REACH) -> str:
    """The map as inline SVG. With href ("/campaign?hex="), every hex links to href + "q,r", which
    selects it without any script. Side colours are side-0 ... side-7 classes in style.css."""
    width = SIZE * (1.5 * starmap["width"] + 0.5) + 4
    height = _H * (starmap["height"] + 0.5) + 4
    colour = {s["id"]: f"side-{i}" for i, s in enumerate(sides)}
    front = frontline(starmap, reach) if starmap.get("frontline") else set()
    out = [f'<svg class="starmap" viewBox="0 0 {width:.0f} {height:.0f}" role="img" '
           f'aria-label="{escape(label)}">']
    for q in range(starmap["width"]):
        for r in range(starmap["height"]):
            x, y = _centre(q, r)
            cls = "hex sel" if selected == (q, r) else "hex front" if (q, r) in front else "hex"
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
