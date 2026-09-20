"""The fleet PDF (PLAN 10.2/10.3): roster, record sheets, orders chart, tracker, quick reference.

Pure consumer: it renders the same `ssd_layout` primitives the screen does, so screen = paper.
Black and white, photocopy-safe, IBM Plex Sans bundled under static/fonts (no system font).

`fleet_pdf(fleets, designs_by_fleet, options)` returns the PDF bytes. One fleet is a fleet pack;
two are a battle pack (PLAN 10.3): roster, sheets and tracker for each fleet, an orders chart
per fleet and one shared quick reference. Both fleets must share a ruleset; the caller checks.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fpdf import FPDF

import fleet_rules
import paths
import ssd_layout
from i18n import _
from rulesets import RULESETS

PAPER = {"A4": (210.0, 297.0), "Letter": (215.9, 279.4)}  # mm
MARGIN = 12.0
PT = 25.4 / 72.0  # a layout point in mm: the diagrams are drawn in points


@dataclass
class PrintOptions:
    """The print dialog of PLAN 10.3."""

    paper: str = "A4"
    roster: bool = True
    sheets: bool = True
    orders: bool = True
    tracker: bool = True
    quickref: bool = True
    damage: bool = True          # pre-mark campaign damage
    include_docked: bool = False
    blank: bool = False          # clean sheets, no campaign state at all
    turns: int = 10
    fields: dict = field(default_factory=dict)


FONT_DIR = "static/fonts"
FONTS = {
    "": "IBMPlexSans-Regular.ttf",
    "B": "IBMPlexSans-Bold.ttf",
    "I": "IBMPlexSans-Italic.ttf",
}


class FleetPDF(FPDF):
    """Every page carries the fleet name and ruleset label, and the non-conforming badge when it
    applies (PLAN 10.2)."""

    header_title = ""
    header_ruleset = ""
    non_conforming = False

    def header(self) -> None:
        self.set_font("plex", "B", 9)
        self.set_text_color(0, 0, 0)
        self.set_xy(MARGIN, 8)
        self.cell(0, 5, f"{self.header_ruleset} · {self.header_title}", align="L")
        if self.non_conforming:
            self.set_font("plex", "", 8)
            self.set_xy(MARGIN, 8)
            self.cell(self.w - 2 * MARGIN, 5,
                      _("Contains non-conforming ships, see roster"), align="R")
        self.set_draw_color(120, 120, 120)
        self.line(MARGIN, 14, self.w - MARGIN, 14)
        self.set_y(18)

    def footer(self) -> None:
        self.set_y(-12)
        self.set_font("plex", "", 7.5)
        self.cell(0, 5, _("Full Thrust Fleet Manager"), align="L")
        self.set_y(-12)
        self.cell(self.w - 2 * MARGIN, 5, _("Page {n} / {total}", n=self.page_no(),
                                            total="{nb}"), align="R")


def _new_pdf(paper: str) -> FleetPDF:
    width, height = PAPER.get(paper, PAPER["A4"])
    pdf = FleetPDF(orientation="P", unit="mm", format=(width, height))
    pdf.set_auto_page_break(True, margin=16)
    pdf.set_margins(MARGIN, 18, MARGIN)
    for style, filename in FONTS.items():
        pdf.add_font("plex", style, str(paths.bundle_dir() / FONT_DIR / filename))
    pdf.set_font("plex", "", 9)
    return pdf


# ---- Drawing the layout primitives -----------------------------------------------------------


def draw_diagram(pdf: FPDF, diagram: ssd_layout.Diagram, x: float, y: float, width: float) -> float:
    """Render a Diagram at (x, y) mm, scaled to `width` mm. Returns its height in mm."""
    scale = width / diagram.width if diagram.width else 1.0
    height = diagram.height * scale

    def px(value: float) -> float:
        return x + value * scale

    def py(value: float) -> float:
        return y + value * scale

    pdf.set_draw_color(0, 0, 0)
    pdf.set_text_color(0, 0, 0)
    for p in diagram.primitives:
        if isinstance(p, ssd_layout.Rect):
            pdf.set_line_width(max(0.1, p.stroke * scale * 0.5))
            style = "DF" if p.fill == "black" else ("D" if p.stroke else None)
            pdf.set_fill_color(0, 0, 0) if p.fill == "black" else pdf.set_fill_color(255, 255, 255)
            if p.fill in ("white", "black") and p.stroke:
                style = "DF"
            if style:
                pdf.rect(px(p.x), py(p.y), p.w * scale, p.h * scale, style=style)
        elif isinstance(p, ssd_layout.Circle):
            pdf.set_line_width(max(0.1, (p.stroke or 0.4) * scale * 0.5))
            pdf.set_fill_color(0, 0, 0) if p.fill == "black" else pdf.set_fill_color(255, 255, 255)
            style = "DF" if p.stroke else "F"
            # fpdf2 2.8.8 takes the CENTRE and the radius, whatever its docstring says.
            pdf.circle(px(p.cx), py(p.cy), p.r * scale, style=style)
        elif isinstance(p, ssd_layout.Line):
            pdf.set_line_width(max(0.1, p.stroke * scale * 0.5))
            pdf.line(px(p.x1), py(p.y1), px(p.x2), py(p.y2))
        elif isinstance(p, ssd_layout.Path):
            _draw_path(pdf, p, px, py, scale)
        elif isinstance(p, ssd_layout.Text):
            height = p.size * scale                      # the text's em height in mm
            pdf.set_font("plex", "B" if p.bold else "", max(3.0, height / PT))
            pdf.set_text_color(255, 255, 255) if p.fill == "white" else pdf.set_text_color(0, 0, 0)
            box = 30.0
            align = {"middle": "C", "start": "L", "end": "R"}[p.anchor]
            left = px(p.x) - (box / 2 if align == "C" else (box if align == "R" else 0))
            # p.y is the baseline; a cell centres its text, so lift it by ~3/4 of the em.
            pdf.set_xy(left, py(p.y) - height * 0.78)
            pdf.cell(box, height, p.text, align=align)
    pdf.set_text_color(0, 0, 0)
    return height


def _draw_path(pdf: FPDF, p: ssd_layout.Path, px, py, scale: float) -> None:
    """The primitives use only M / L / A / Z; arcs are drawn as their chord, which at icon size
    is a hair's difference and keeps the PDF dependency-free."""
    pdf.set_line_width(max(0.1, (p.stroke or 0.4) * scale * 0.5))
    points: list[tuple[float, float]] = []
    tokens = p.d.replace("M", " M ").replace("L", " L ").replace("A", " A ").replace("Z", " Z ").split()
    index = 0
    fill = p.fill == "black"
    polygon: list[tuple[float, float]] = []
    while index < len(tokens):
        token = tokens[index]
        if token in ("M", "L"):
            x, y = float(tokens[index + 1]), float(tokens[index + 2])
            point = (px(x), py(y))
            if token == "M":
                if len(points) > 1 and not fill:
                    _stroke(pdf, points)
                points = [point]
            else:
                points.append(point)
            polygon.append(point)
            index += 3
        elif token == "A":
            # "A rx ry rot large sweep x y": keep the end point, drop the curvature.
            x, y = float(tokens[index + 6]), float(tokens[index + 7])
            points.append((px(x), py(y)))
            polygon.append((px(x), py(y)))
            index += 8
        else:
            index += 1
    if fill and len(polygon) > 2:
        pdf.set_fill_color(0, 0, 0)
        with pdf.new_path() as path:
            path.style.fill_color = "#000000"
            path.style.stroke_color = "#000000"
            path.style.stroke_width = 0.1
            path.move_to(*polygon[0])
            for point in polygon[1:]:
                path.line_to(*point)
            path.close()
    elif len(points) > 1:
        _stroke(pdf, points)


def _stroke(pdf: FPDF, points: list[tuple[float, float]]) -> None:
    for start, end in zip(points, points[1:]):
        pdf.line(start[0], start[1], end[0], end[1])


# ---- Sections -----------------------------------------------------------------------------------


def _ship_damage(ship: dict, options: PrintOptions) -> dict | None:
    if options.blank or not options.damage:
        return None
    return ship["damage"]


def _printable_ships(fleet: dict, options: PrintOptions) -> list[dict]:
    """Docked, hulk and destroyed ships stay on the roster but get no sheet (PLAN 10.2)."""
    skip = {"hulk", "destroyed"} if options.include_docked else {"docked", "hulk", "destroyed"}
    return [s for s in fleet["ships"] if s["status"] not in skip]


def roster_page(pdf: FleetPDF, fleet: dict, designs: dict, options: PrintOptions) -> None:
    rs = RULESETS.get(fleet["ruleset"])
    report = fleet_rules.fleet_report(fleet, designs)
    badges = fleet_rules.badges(fleet, designs)
    pdf.add_page()
    pdf.set_font("plex", "B", 15)
    pdf.cell(0, 8, fleet["name"], new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("plex", "", 9)
    limit = fleet["points_limit"] or _("no limit")
    lines = [
        f"{_('Ruleset')}: {rs.name if rs else fleet['ruleset']}",
        f"{_('Race')}: {fleet['race']} · {_('Faction')}: {fleet['faction'] or _('none')}",
        f"{_('Admiral')}: {fleet['admiral'] or '-'}",
        f"{_('Points')}: {report.points} / {limit}",
        f"{_('Ships')}: " + ", ".join(f"{k} {v}" for k, v in fleet_rules.ship_counts(fleet).items()),
    ]
    active = [k for k in fleet_rules.FLEET_OPTION_KEYS if fleet["options"].get(k)]
    if active:
        lines.append(f"{_('Options in force')}: " + ", ".join(active))
    marks = [name for name, on in badges.items() if on]
    if marks:
        lines.append(f"{_('Badges')}: " + ", ".join(marks))
    for line in lines:
        pdf.cell(0, 5, line, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    headers = [_("ID"), _("Name"), _("Class"), _("Type"), _("TMF"), _("Thrust"), _("FTL"),
               _("Status"), _("Source"), _("Points")]
    widths = [14, 38, 34, 16, 12, 14, 10, 22, 18, 16]
    pdf.set_font("plex", "B", 8)
    for header, width in zip(headers, widths):
        pdf.cell(width, 6, header, border="B")
    pdf.ln()
    pdf.set_font("plex", "", 8)
    conformance = {r.ship["uid"]: r.conforming for r in report.ships}
    for ship in fleet["ships"]:
        design = designs.get(ship["design_id"])
        status = ship["status"]
        if ship["damage"]["hull"]:
            status += f" ({ship['damage']['hull']})"
        name = ship["name"] + ("" if conformance.get(ship["uid"], True) else " *")
        row = [
            ship["table_id"], name,
            design["name"] if design else _("Missing design"),
            design["type_code"] if design else "-",
            str(design["tmf"]) if design else "-",
            str(design["thrust"]) if design else "-",
            (_("yes") if design["ftl"] else _("no")) if design else "-",
            status,
            design["source"]["kind"] if design else "-",
            str(fleet_rules.ship_points(ship, design, fleet_rules.fleet_options(fleet))),
        ]
        for value, width in zip(row, widths):
            pdf.cell(width, 5, value, border="B")
        pdf.ln()
    if any(not ok for ok in conformance.values()):
        pdf.ln(2)
        pdf.set_font("plex", "I", 8)
        pdf.cell(0, 5, _("* non-conforming; see the tournament check in the app."),
                 new_x="LMARGIN", new_y="NEXT")
    if fleet["notes"]:
        pdf.ln(3)
        pdf.set_font("plex", "", 8)
        pdf.multi_cell(0, 4, fleet["notes"])


def sheets_pages(pdf: FleetPDF, fleet: dict, designs: dict, options: PrintOptions) -> None:
    """Record sheets packed into rows, largest first (PLAN 10.2)."""
    ships = _printable_ships(fleet, options)
    if not ships:
        return
    pdf.add_page()
    pdf.set_font("plex", "B", 12)
    pdf.cell(0, 7, _("Record sheets"), new_x="LMARGIN", new_y="NEXT")

    usable = pdf.w - 2 * MARGIN
    ordered = sorted(
        ships,
        key=lambda s: -ssd_layout.BOX_WIDTHS[ssd_layout.box_size(designs[s["design_id"]])]
        if s["design_id"] in designs else 0,
    )
    x, y, row_height = MARGIN, pdf.get_y(), 0.0
    for ship in ordered:
        design = designs.get(ship["design_id"])
        if not design:
            continue
        diagram = ssd_layout.layout(design, damage=_ship_damage(ship, options),
                                    loadout=ship["loadout"])
        width = min(usable, diagram.width * PT * 1.35)
        height = diagram.height / diagram.width * width + 6
        if x + width > MARGIN + usable + 0.5:
            x, y, row_height = MARGIN, y + row_height + 4, 0.0
        if y + height > pdf.h - 18:
            pdf.add_page()
            x, y, row_height = MARGIN, pdf.get_y(), 0.0
        pdf.set_font("plex", "B", 8)
        pdf.set_xy(x, y)
        pdf.cell(width, 5, f"{ship['table_id']} · {ship['name']} · {design['name']} "
                           f"{_('MASS')} {design['tmf']}")
        draw_diagram(pdf, diagram, x, y + 5, width)
        row_height = max(row_height, height)
        x += width + 4
    left_off = [s for s in fleet["ships"] if s not in ships]
    if left_off:
        pdf.set_xy(MARGIN, min(y + row_height + 4, pdf.h - 24))
        pdf.set_font("plex", "I", 8)
        pdf.cell(0, 5, _("Not printed: {ships}",
                         ships=", ".join(f"{s['table_id']} ({s['status']})" for s in left_off)))


def orders_page(pdf: FleetPDF, fleet: dict, options: PrintOptions) -> None:
    """Ship ID x turns with a velocity column each (FB1 p.47 style)."""
    pdf.add_page()
    pdf.set_font("plex", "B", 12)
    pdf.cell(0, 7, _("Orders chart"), new_x="LMARGIN", new_y="NEXT")
    turns = max(1, options.turns)
    id_width = 26.0
    cell_width = (pdf.w - 2 * MARGIN - id_width) / turns
    pdf.set_font("plex", "B", 7.5)
    pdf.cell(id_width, 6, _("Ship"), border=1)
    for turn in range(1, turns + 1):
        pdf.cell(cell_width, 6, str(turn), border=1, align="C")
    pdf.ln()
    pdf.set_font("plex", "", 7)
    for ship in fleet["ships"]:
        if ship["status"] in ("destroyed", "hulk"):
            continue
        pdf.cell(id_width, 9, f"{ship['table_id']} {ship['name']}"[:22], border=1)
        for _turn in range(turns):
            pdf.cell(cell_width, 9, "", border=1)
        pdf.ln()


def tracker_page(pdf: FleetPDF, fleet: dict, designs: dict, options: PrintOptions) -> None:
    """Fighter and ordnance tracker; only printed when the fleet carries any (PLAN 10.2)."""
    rows: list[tuple[str, str, int, str]] = []  # (ship, label, boxes, kind)
    for ship in fleet["ships"]:
        design = designs.get(ship["design_id"])
        if not design or ship["status"] in ("destroyed", "hulk"):
            continue
        for system in design["systems"]:
            if system["type"] in ("hangar", "fighter_group"):
                rows.append((f"{ship['table_id']} {ship['name']}", _("Fighter group"), 6, "fighters"))
            elif system["type"] in ("sm_magazine", "sm_rack"):
                salvos = max(1, int(system.get("capacity", 2) or 2) // 2)
                rows.append((f"{ship['table_id']} {ship['name']}", _("Salvos"), salvos, "salvos"))
            elif system["type"] in ("submunition", "nova_cannon", "wave_gun", "mt_missile"):
                rows.append((f"{ship['table_id']} {ship['name']}", system["type"], 1, "one_shot"))
    if not rows:
        return
    pdf.add_page()
    pdf.set_font("plex", "B", 12)
    pdf.cell(0, 7, _("Fighters and ordnance"), new_x="LMARGIN", new_y="NEXT")
    for ship_label, label, boxes, kind in rows:
        pdf.set_font("plex", "", 8)
        pdf.cell(55, 7, ship_label[:32])
        pdf.cell(28, 7, label[:18])
        x, y = pdf.get_x(), pdf.get_y()
        for index in range(boxes):
            pdf.rect(x + index * 6, y + 1.5, 4.5, 4.5)
        if kind == "fighters":
            for index in range(6):
                pdf.circle(x + 46 + index * 6, y + 3.7, 2.2)
        pdf.ln(7)


def quickref_pages(pdf: FleetPDF, fleets: list[dict], designs_by_fleet: list[dict]) -> None:
    """Only the systems present, in the rulebook's own wording with a page reference."""
    ruleset = RULESETS.get(fleets[0]["ruleset"])
    if not ruleset:
        return
    present: set[str] = set()
    races: set[str] = set()
    options: dict = {}
    for fleet, designs in zip(fleets, designs_by_fleet):
        options.update({k: v for k, v in fleet_rules.fleet_options(fleet).items() if v})
        for ship in fleet["ships"]:
            design = designs.get(ship["design_id"])
            for system in design["systems"] if design else []:
                present.add(system["type"])
            if design and design["armour"]:
                present.add("armour")
            if design and design["streamlining"] != "none":
                present.add("streamlining")
            if design:
                races.add(design.get("race") or "human")
    # A race's own entries go on the sheet beside the shared ones (FB2 restates movement, crew
    # and the weapon summaries per race), so the ruleset needs to know which races are in play.
    entries = ruleset.quickref(present, options, frozenset(races or {"human"}))
    if not entries:
        return
    pdf.add_page()
    pdf.set_font("plex", "B", 12)
    pdf.cell(0, 7, _("Quick reference"), new_x="LMARGIN", new_y="NEXT")
    for entry in entries:
        pdf.set_font("plex", "B", 9)
        pdf.cell(0, 5.5, f"{entry.title}  ({entry.book} p.{entry.page})",
                 new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("plex", "", 8)
        pdf.multi_cell(0, 4, entry.text)
        pdf.ln(2)


# ---- The pack ------------------------------------------------------------------------------------


def fleet_pdf(fleets: list[dict], designs_by_fleet: list[dict],
              options: PrintOptions | None = None) -> bytes:
    options = options or PrintOptions()
    pdf = _new_pdf(options.paper)
    pdf.set_title(" / ".join(f["name"] for f in fleets))
    for fleet, designs in zip(fleets, designs_by_fleet):
        ruleset = RULESETS.get(fleet["ruleset"])
        pdf.header_title = fleet["name"]
        pdf.header_ruleset = ruleset.short_label if ruleset else fleet["ruleset"]
        pdf.non_conforming = not fleet_rules.fleet_conforming(fleet, designs)
        if options.roster:
            roster_page(pdf, fleet, designs, options)
        if options.sheets:
            sheets_pages(pdf, fleet, designs, options)
        if options.tracker:
            tracker_page(pdf, fleet, designs, options)
    for fleet in fleets if options.orders else []:
        ruleset = RULESETS.get(fleet["ruleset"])
        pdf.header_title = fleet["name"]
        pdf.header_ruleset = ruleset.short_label if ruleset else fleet["ruleset"]
        orders_page(pdf, fleet, options)
    if options.quickref:
        quickref_pages(pdf, fleets, designs_by_fleet)
    return bytes(pdf.output())


def battle_pack_error(fleets: list[dict]) -> str:
    """"" when the fleets may share a pack, else the reason (PLAN 10.3)."""
    if len(fleets) > 1 and len({f["ruleset"] for f in fleets}) > 1:
        return _("Both fleets must use the same ruleset.")
    return ""
