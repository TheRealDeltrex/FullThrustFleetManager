"""The fleet PDF (PLAN 10.2/10.3): roster, record sheets, orders chart, tracker, quick reference.

Pure consumer: it renders the same `ssd_layout` primitives the screen does, so screen = paper.
Print-first dossier layout, with monochrome and colour styles; bundled IBM Plex Sans fonts.

`fleet_pdf(fleets, designs_by_fleet, options)` returns the PDF bytes. One fleet is a fleet pack;
two are a battle pack (PLAN 10.3): roster, sheets and tracker for each fleet, an orders chart
per fleet and one shared quick reference. Both fleets must share a ruleset; the caller checks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from math import ceil

from fpdf import FPDF
from fpdf.fonts import FontFace

import fleet_rules
import paths
import ssd_layout
from i18n import _
from rulesets import RULESETS, common

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
    blank_pulsers: bool = False  # Phalon: print the pulser icons empty to write L/M/C in
    turns: int = 10
    fields: dict = field(default_factory=dict)
    style: str = "mono"          # mono remains the ink-saving default; colour is optional


FONT_DIR = "static/fonts"
FONTS = {
    "": "IBMPlexSans-Regular.ttf",
    "B": "IBMPlexSans-Bold.ttf",
    "I": "IBMPlexSans-Italic.ttf",
}


class FleetPDF(FPDF):
    """Print furniture is independent of the screen theme and the SSD renderer."""

    header_title = ""
    header_ruleset = ""
    non_conforming = False
    print_style = "mono"

    @property
    def accent(self) -> tuple[int, int, int]:
        return (28, 68, 95) if self.print_style == "color" else (25, 25, 25)

    @property
    def tint(self) -> tuple[int, int, int]:
        return (237, 243, 247) if self.print_style == "color" else (246, 246, 246)

    def header(self) -> None:
        self.set_text_color(*self.accent)
        self.set_font("plex", "B", 9)
        self.set_xy(MARGIN, 8)
        title = f"{self.header_ruleset} · {self.header_title}"
        self.cell(0, 5, _fit(self, title, self.epw))
        self.set_draw_color(*self.accent)
        self.set_line_width(.65)
        self.line(MARGIN, 15, self.w - MARGIN, 15)
        if self.non_conforming:
            self.set_font("plex", "", 7.5)
            self.set_text_color(50)
            self.set_xy(MARGIN, 17)
            self.cell(0, 4, _("Contains non-conforming ships, see roster"))
        self.set_y(24)
        self.set_text_color(25)

    def footer(self) -> None:
        self.set_draw_color(175)
        self.set_line_width(.2)
        self.line(MARGIN, self.h - 15, self.w - MARGIN, self.h - 15)
        self.set_font("plex", "", 7)
        self.set_text_color(80)
        self.set_xy(MARGIN, self.h - 12)
        self.cell(0, 5, _("Full Thrust Fleet Manager") + "  /  " + date.today().isoformat())
        self.set_xy(MARGIN, self.h - 12)
        self.cell(self.epw, 5, _("Page {n} / {total}", n=self.page_no(), total="{nb}"), align="R")


def _new_pdf(paper: str, style: str = "mono") -> FleetPDF:
    width, height = PAPER.get(paper, PAPER["A4"])
    pdf = FleetPDF(orientation="P", unit="mm", format=(width, height))
    pdf.print_style = style if style in ("mono", "color") else "mono"
    pdf.set_auto_page_break(True, margin=19)
    pdf.set_margins(MARGIN, 24, MARGIN)
    for style, filename in FONTS.items():
        pdf.add_font("plex", style, str(paths.bundle_dir() / FONT_DIR / filename))
    pdf.set_font("plex", "", 9)
    return pdf


def _fit(pdf: FPDF, text: str, width: float) -> str:
    """Only running headers are abbreviated; body content wraps without truncation."""
    if pdf.get_string_width(text) <= width - 2:
        return text
    while text and pdf.get_string_width(text + "...") > width - 2:
        text = text[:-1]
    return text + "..."


def _lines(pdf: FPDF, text: str, width: float) -> list[str]:
    return pdf.multi_cell(width, 4, text, dry_run=True, output="LINES", align="L")


def _section(pdf: FleetPDF, title: str, eyebrow: str = "") -> None:
    pdf.add_page()
    if eyebrow:
        pdf.set_font("plex", "B", 8)
        pdf.set_text_color(*pdf.accent)
        pdf.cell(0, 5, eyebrow.upper(), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("plex", "B", 18)
    pdf.set_text_color(*pdf.accent)
    pdf.multi_cell(0, 8, title, new_x="LMARGIN", new_y="NEXT", align="L")
    pdf.ln(5)
    pdf.set_text_color(25)


def _room(pdf: FleetPDF, height: float) -> None:
    if pdf.get_y() + height > pdf.h - 19:
        pdf.add_page()


def _table(pdf: FleetPDF, headers: list[str], rows: list[list[str]], widths: list[float],
           *, grid: bool = False, size: float = 7.5, row_height: float = 8) -> None:
    """Full-width wrapping tables; fpdf repeats headings on continuation pages."""
    pdf.set_font("plex", "", size)
    pdf.set_text_color(25)
    pdf.set_draw_color(180)
    pdf.set_fill_color(255)
    pdf.set_line_width(.15)
    with pdf.table(col_widths=widths, width=pdf.epw, line_height=3.8,
                   text_align="LEFT", padding=(1.8, 1.2), min_row_height=row_height,
                   borders_layout="ALL" if grid else "HORIZONTAL_LINES",
                   headings_style=FontFace(emphasis="B", color=pdf.accent, fill_color=pdf.tint),
                   cell_fill_color=pdf.tint, cell_fill_mode="ROWS") as table:
        for values in [headers, *rows]:
            row = table.row()
            for value in values:
                row.cell(value)
    pdf.set_x(MARGIN)


# ---- Drawing the layout primitives -----------------------------------------------------------


def draw_diagram(pdf: FPDF, diagram: ssd_layout.Diagram, x: float, y: float, width: float) -> float:
    """Render a Diagram at (x, y) mm, scaled to `width` mm. Returns its height in mm."""
    scale = width / diagram.width if diagram.width else 1.0
    height = diagram.height * scale

    def px(value: float) -> float:
        return x + (value - diagram.left) * scale

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


def _sheet_loadout(ship: dict, design: dict, options: PrintOptions) -> dict | None:
    """The loadout a record sheet is drawn with.

    FB2 p.35 prints Phalon pulser icons blank so the player can write L, M or C into them before
    each battle, and the print dialog offers that: with `blank_pulsers` the sheet drops whatever
    configuration is recorded and prints the blanks the book does.
    """
    loadout = ship["loadout"]
    if not options.blank_pulsers:
        return loadout
    effective = loadout if loadout is not None else design.get("default_loadout")
    if not isinstance(effective, dict) or not effective.get("pulsers"):
        return loadout
    return {**effective, "pulsers": []}


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
    _section(pdf, fleet["name"], _("Fleet roster"))
    limit = fleet["points_limit"] or _("no limit")
    metrics = [(_("Points"), f"{report.points} / {limit}"),
               (_("Ships"), str(len(fleet["ships"]))),
               (_("Ruleset"), rs.short_label if rs else fleet["ruleset"])]
    x, y = MARGIN, pdf.get_y()
    width = (pdf.epw - 8) / 3
    for label, value in metrics:
        pdf.set_fill_color(*pdf.tint)
        pdf.rect(x, y, width, 21, style="F")
        pdf.set_xy(x + 3, y + 2)
        pdf.set_font("plex", "B", 7.5)
        pdf.set_text_color(*pdf.accent)
        pdf.cell(width - 6, 5, label.upper())
        pdf.set_xy(x + 3, y + 8)
        pdf.set_font("plex", "B", 14)
        pdf.cell(width - 6, 9, value)
        x += width + 4
    pdf.set_xy(MARGIN, y + 26)
    pdf.set_font("plex", "", 9)
    pdf.set_text_color(25)
    lines = [
        f"{_('Ruleset')}: {rs.name if rs else fleet['ruleset']}",
        f"{_('Race')}: {fleet['race']} · {_('Faction')}: {fleet['faction'] or _('none')}",
        f"{_('Admiral')}: {fleet['admiral'] or '-'}",
        *([_("Dummy bogeys: {n} ({p} points)", n=fleet_rules.dummy_bogeys(fleet),
             p=fleet_rules.dummy_bogey_points(fleet))] if fleet_rules.dummy_bogeys(fleet) else []),
        f"{_('Ships')}: " + ", ".join(f"{k} {v}" for k, v in fleet_rules.ship_counts(fleet).items()),
        # FTL gunboat squadrons flying without a carrier (PC p.80).
        *(_("FTL gunboat squadron: {label} ({p} points)", label=rs.gunboat_squadron_label(g),
            p=rs.gunboat_squadron_points(g)) for g in fleet_rules.gunboat_squadrons(fleet)),
    ]
    morale = fleet_rules.morale(fleet, designs)
    if morale:
        lines.append(_("Fleet morale: withdraws when {n} MASS is destroyed (half its MASS).",
                       n=morale[1]))
    active = [fleet_rules.option_label(k) for k in fleet_rules.ruleset_option_keys(fleet["ruleset"])
              if fleet["options"].get(k)]
    if active:
        lines.append(f"{_('Options in force')}: " + ", ".join(active))
    marks = [fleet_rules.badge_label(name) for name, on in badges.items() if on]
    if marks:
        lines.append(f"{_('Badges')}: " + ", ".join(marks))
    for line in lines:
        pdf.multi_cell(0, 4.8, line, new_x="LMARGIN", new_y="NEXT", align="L")
    pdf.ln(3)

    headers = [_("ID"), _("Name"), _("Class"), _("Type"), _("TMF"), _("Thrust"), _("FTL"),
               _("Status"), _("Source"), _("Points")]
    widths = [14, 33, 29, 11, 10, 13, 9, 22, 17, 14]
    rows = []
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
        rows.append(row)
    _table(pdf, headers, rows, widths)
    if any(not ok for ok in conformance.values()):
        pdf.ln(2)
        pdf.set_font("plex", "I", 8)
        pdf.multi_cell(0, 4, _("* non-conforming; see the tournament check in the app."),
                       new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)
    _room(pdf, 20)
    pdf.set_font("plex", "B", 10)
    pdf.set_text_color(*pdf.accent)
    pdf.cell(0, 6, _("Notes"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("plex", "", 9)
    pdf.set_text_color(25)
    if fleet["notes"]:
        pdf.multi_cell(0, 4.8, fleet["notes"], new_x="LMARGIN", new_y="NEXT", align="L")
    pdf.set_draw_color(195)
    pdf.set_line_width(.15)
    for _line in range(4):
        if pdf.get_y() + 8 > pdf.h - 20:
            break
        pdf.ln(8)
        pdf.line(MARGIN, pdf.get_y(), pdf.w - MARGIN, pdf.get_y())



def sheets_pages(pdf: FleetPDF, fleet: dict, designs: dict, options: PrintOptions) -> None:
    """Record sheets packed into rows, largest first (PLAN 10.2)."""
    ships = _printable_ships(fleet, options)
    if not ships:
        return
    _section(pdf, _("Record sheets"))
    usable = pdf.epw
    ordered = sorted(ships, key=lambda s: -ssd_layout.BOX_WIDTHS[
        ssd_layout.box_size(designs[s["design_id"]])] if s["design_id"] in designs else 0)
    x, y, row_height = MARGIN, pdf.get_y(), 0.0
    for ship in ordered:
        design = designs.get(ship["design_id"])
        if not design:
            continue
        diagram = ssd_layout.layout(design, damage=_ship_damage(ship, options),
                                    loadout=_sheet_loadout(ship, design, options))
        # A tall SSD must fit a fresh page as well as the available row width.
        inner = min(usable - 6, diagram.width * PT * 1.35,
                    (pdf.h - 19 - 24 - 28) * diagram.width / diagram.height)
        width = inner + 6
        pdf.set_font("plex", "B", 9)
        title_lines = _lines(pdf, f"{ship['table_id']} · {ship['name']}", width - 6)
        pdf.set_font("plex", "", 8)
        meta_lines = _lines(pdf, f"{design['name']} · {_('MASS')} {design['tmf']}", width - 6)
        band = 5 + 4 * (len(title_lines) + len(meta_lines))
        # Account for wrapped identities before the final height constraint.
        inner = min(inner, (pdf.h - 19 - 24 - band - 4) * diagram.width / diagram.height)
        height = band + diagram.height / diagram.width * inner + 4
        if x + width > MARGIN + usable + .1:
            x, y, row_height = MARGIN, y + row_height + 4, 0.0
        if y + height > pdf.h - 19:
            pdf.add_page()
            x, y, row_height = MARGIN, pdf.get_y(), 0.0
        pdf.set_line_width(.25)
        pdf.set_draw_color(160)
        pdf.set_fill_color(255)
        pdf.rect(x, y, width, height, style="DF")
        pdf.set_fill_color(*pdf.tint)
        pdf.rect(x, y, width, band, style="F")
        pdf.set_xy(x + 3, y + 2)
        pdf.set_text_color(*pdf.accent)
        pdf.set_font("plex", "B", 9)
        pdf.multi_cell(width - 6, 4, chr(10).join(title_lines), new_x="LEFT", new_y="NEXT", align="L")
        pdf.set_font("plex", "", 8)
        pdf.set_text_color(35)
        pdf.multi_cell(width - 6, 4, chr(10).join(meta_lines), align="L")
        draw_diagram(pdf, diagram, x + (width - inner) / 2, y + band + 1, inner)
        row_height = max(row_height, height)
        x += width + 4
    left_off = [s for s in fleet["ships"] if s not in ships]
    if left_off:
        pdf.set_xy(MARGIN, y + row_height + 5)
        pdf.set_font("plex", "I", 8)
        pdf.multi_cell(0, 4, _("Not printed: {ships}",
            ships=", ".join(f"{s['table_id']} ({s['status']})" for s in left_off)), align="L")



def orders_page(pdf: FleetPDF, fleet: dict, options: PrintOptions) -> None:
    """Ship ID x turns with a velocity column each (FB1 p.47 style)."""
    turns = max(1, options.turns)
    for first in range(1, turns + 1, 10):
        chart_turns = range(first, min(first + 10, turns + 1))
        _section(pdf, _("Orders chart"))
        pdf.set_font("plex", "", 8)
        pdf.multi_cell(0, 4.5, _("V = velocity. Write movement orders beside it for each turn."),
                       new_x="LMARGIN", new_y="NEXT")
        pdf.ln(3)
        pdf.set_font("plex", "", 7)
        pdf.set_draw_color(155)
        pdf.set_fill_color(255)
        pdf.set_line_width(.15)
        with pdf.table(width=pdf.epw, col_widths=[34, *([4.5, 10.7] * len(chart_turns))],
                       line_height=3.7, min_row_height=12, padding=(1.5, .8), text_align="LEFT",
                       num_heading_rows=2, headings_style=FontFace(emphasis="B", color=pdf.accent,
                       fill_color=pdf.tint)) as table:
            heading = table.row()
            heading.cell(_("Ship"))
            for turn in chart_turns:
                heading.cell(str(turn), colspan=2, align="CENTER")
            labels = table.row()
            labels.cell(_("ID") + " / " + _("Name"))
            for _turn in chart_turns:
                labels.cell(_("V"))
                labels.cell(_("Orders"))
            for ship in fleet["ships"]:
                if ship["status"] in ("destroyed", "hulk"):
                    continue
                row = table.row()
                row.cell(f"{ship['table_id']} {ship['name']}")
                for _turn in chart_turns:
                    row.cell("")
                    row.cell("")


def _tracker_rows(ship: dict, design: dict) -> list[tuple[str, int, int, str]]:
    """(label, boxes, endurance circles, uid) for what the ship actually carries: its own loadout
    or the design's default. A wing is six fighters with six endurance, a light wing eight with
    four (PC p.75); a magazine shows the salvos loaded in it, a rack its one salvo."""
    loadout = ship.get("loadout")
    if loadout is None:
        loadout = design.get("default_loadout") or {}
    by_uid = {s["uid"]: s for s in design["systems"]}
    labels = fleet_rules.system_labels(design)
    rows: list[tuple[str, int, int, str]] = []
    wings = [f for f in common.loadout_entries(loadout, "fighters")
             if by_uid.get(f.get("hangar"), {}).get("type") in common.FIGHTER_BAY_TYPES]
    for system in design["systems"]:
        uid = system["uid"]
        if system["type"] in common.FIGHTER_BAY_TYPES:
            groups = [f for f in wings if f.get("hangar") == uid]
            if not groups and system["type"] == "fighter_group":
                groups = [{}]  # FT2 pays for the group in the design itself (FT p.31)
            for group in groups:
                light = "light" in (group.get("extras") or [])
                rows.append((_("Fighter group"), 8 if light else 6, 4 if light else 6, uid))
        elif system["type"] in common.GUNBOAT_CARRIER_TYPES:
            # PC p.79: six gunboats, six points of combat endurance.
            for _squadron in (g for g in common.loadout_entries(loadout, "gunboats")
                              if g.get("carrier") == uid):
                rows.append((_("Gunboat squadron"), 6, 6, uid))
        elif system["type"] == "sm_magazine":
            salvos = sum(len(m.get("salvos") or []) for m in common.loadout_entries(loadout, "magazines")
                         if m.get("magazine") == uid)
            if salvos:
                rows.append((_("Salvos"), salvos, 0, uid))
        elif system["type"] == "sm_rack":
            rows.append((_("Salvos"), 1, 0, uid))
        elif system["type"] in ("submunition", "nova_cannon", "wave_gun", "mt_missile"):
            rows.append((labels.get(uid, system["type"]), 1, 0, uid))
    return rows


def tracker_page(pdf: FleetPDF, fleet: dict, designs: dict, options: PrintOptions) -> None:
    """Fighter and ordnance tracker; only printed when the fleet carries any (PLAN 10.2). With
    campaign damage printed, lost fighters and spent salvos and one-shot systems are struck out."""
    rows: list[tuple[str, str, int, int, int]] = []  # (ship, label, boxes, endurance, spent)
    for ship in fleet["ships"]:
        design = designs.get(ship["design_id"])
        if not design or ship["status"] in ("destroyed", "hulk"):
            continue
        damage = _ship_damage(ship, options) or {}
        lost = dict(damage.get("fighters_lost") or {})
        lost.update(damage.get("salvos_spent") or {})
        used = set(damage.get("one_shot_used") or [])
        for label, boxes, endurance, uid in _tracker_rows(ship, design):
            spent = min(boxes, 1 if uid in used else int(lost.pop(uid, 0)))
            rows.append((f"{ship['table_id']} {ship['name']}", label, boxes, endurance, spent))
    rs = RULESETS.get(fleet["ruleset"])
    for squadron in fleet_rules.gunboat_squadrons(fleet):
        # PC p.79: six gunboats, six points of combat endurance.
        rows.append((rs.gunboat_squadron_label(squadron), _("Gunboat squadron"), 6, 6, 0))
    if not rows:
        return
    _section(pdf, _("Fighters and ordnance"))
    # Separate writing areas for units/salvos and combat endurance. Long tracks continue
    # in another card rather than running through the endurance circles or page margin.
    box_capacity = int((pdf.epw * .55 - 8) // 6)
    circle_capacity = int((pdf.epw * .45 - 8) // 6)
    for number, (ship_label, label, boxes, endurance, spent) in enumerate(rows, start=1):
        for chunk in range(max(ceil(boxes / box_capacity), ceil(endurance / circle_capacity), 1)):
            pdf.set_font("plex", "B", 9)
            heading = _lines(pdf, ship_label + " · " + label + " · " + _("Track {n}", n=number),
                             pdf.epw - 6)
            band = len(heading) * 4 + 4
            height = band + 17
            _room(pdf, height + 4)
            x, y = MARGIN, pdf.get_y()
            pdf.set_draw_color(170)
            pdf.set_line_width(.2)
            pdf.rect(x, y, pdf.epw, height)
            pdf.set_fill_color(*pdf.tint)
            pdf.rect(x, y, pdf.epw, band, style="F")
            pdf.set_text_color(*pdf.accent)
            pdf.set_xy(x + 3, y + 2)
            pdf.multi_cell(pdf.epw - 6, 4, chr(10).join(heading), align="L")
            pdf.set_font("plex", "", 7.5)
            pdf.set_text_color(30)
            pdf.set_xy(x + 3, y + band + 1)
            pdf.cell(pdf.epw * .55 - 6, 4, _("Units / salvos"))
            if endurance:
                pdf.cell(0, 4, _("Combat endurance"))
            pdf.set_draw_color(0)
            pdf.set_line_width(.25)
            top = y + band + 7
            for index in range(chunk * box_capacity, min(boxes, (chunk + 1) * box_capacity)):
                left = x + 3 + (index % box_capacity) * 6
                pdf.rect(left, top, 4.5, 4.5)
                if index < spent:
                    pdf.line(left, top + 4.5, left + 4.5, top)
            for index in range(chunk * circle_capacity,
                               min(endurance, (chunk + 1) * circle_capacity)):
                pdf.circle(x + pdf.epw * .55 + (index % circle_capacity) * 6 + 2.2,
                           top + 2.2, 2.2)
            pdf.set_xy(MARGIN, y + height + 4)



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
        if fleet_rules.dummy_bogeys(fleet):
            present.add("dummy_bogeys")
        if fleet_rules.gunboat_squadrons(fleet):
            present.add("gunboats")
        for ship in fleet["ships"]:
            design = designs.get(ship["design_id"])
            for system in design["systems"] if design else []:
                present.add(system["type"])
            if design and design["armour"]:
                present.add("armour")
            if design and sum(1 for n in design.get("armour_layers", []) if n) > 1:
                present.add("shell_armour")  # layered armour has its own entry (CD p.20)
            if design and design.get("armour_regen"):
                present.add("armour_regen")  # PC p.57
            if design and design.get("stealth_hull"):
                present.add("stealth_hull")  # PC p.56
            if design and design.get("hull_rows") == 3 and design.get("hull_boxes", 0) > 3:
                present.add("sr_hull_rows")  # Star Ranger's three-row hulls
            if design and design["streamlining"] != "none":
                present.add("streamlining")
            # Rules a ship brings without a system (the FTCD quick reference reads these).
            stationary = design and (design.get("hull_kind") == "starbase" or any(
                s["type"] in ("jump_gate", "portal") for s in design["systems"]))
            if design and not design.get("ftl") and not stationary:
                present.add("no_ftl")
            if design and design.get("hull_kind") == "starbase":
                present.add("starbase")
            loadout = ship.get("loadout") if ship.get("loadout") is not None else (design or {}).get(
                "default_loadout")
            if common.loadout_entries(loadout, "gunboats"):
                present.add("gunboats")  # carried in a boat bay too, not only on a rack (PC p.80)
            if design and any(s.get("kind") == "troop" for s in design["systems"]):
                present.add("troop_hold")
            if design:
                races.add(design.get("race") or "human")
    # A race's own entries go on the sheet beside the shared ones (FB2 restates movement, crew
    # and the weapon summaries per race), so the ruleset needs to know which races are in play.
    entries = ruleset.quickref(present, options, frozenset(races or {"human"}))
    if not entries:
        return
    # The shared reference names both fleets rather than inheriting whichever
    # orders chart happened to print last.
    pdf.header_title = " / ".join(f["name"] for f in fleets)
    pdf.non_conforming = any(not fleet_rules.fleet_conforming(f, d)
                             for f, d in zip(fleets, designs_by_fleet))
    _section(pdf, _("Quick reference"))
    column = 0
    top = pdf.get_y()
    y = top
    width = (pdf.epw - 9) / 2

    def advance() -> None:
        nonlocal column, y, top
        if column == 0:
            column = 1
        else:
            pdf.add_page()
            column = 0
            top = pdf.get_y()
        y = top

    for entry in entries:
        where = entry.url or f"{entry.book} p.{entry.page}"
        pdf.set_font("plex", "B", 9.5)
        title = _lines(pdf, entry.title, width)
        pdf.set_font("plex", "", 7.5)
        source = _lines(pdf, where, width)
        pdf.set_font("plex", "", 8.5)
        body = _lines(pdf, entry.text, width)
        heading_height = 4.5 * len(title) + 3.6 * len(source) + 2
        entry_height = heading_height + 4.2 * len(body)
        if (y + heading_height + 12 > pdf.h - 19
                or entry_height <= pdf.h - 19 - top and y + entry_height > pdf.h - 19):
            advance()
        # Keep heading and the opening lines together; continuations repeat the
        # source heading, never alter or summarise the original rulebook wording.
        index = 0
        while index < len(body):
            x = MARGIN + column * (width + 9)
            pdf.set_xy(x, y)
            pdf.set_font("plex", "B", 9.5)
            pdf.set_text_color(*pdf.accent)
            pdf.multi_cell(width, 4.5, chr(10).join(title), new_x="LEFT", new_y="NEXT", align="L")
            pdf.set_font("plex", "", 7.5)
            pdf.set_text_color(75)
            pdf.multi_cell(width, 3.6, chr(10).join(source), new_x="LEFT", new_y="NEXT", align="L")
            y = pdf.get_y() + 2
            pdf.set_font("plex", "", 8.5)
            pdf.set_text_color(25)
            while index < len(body) and y + 4.2 <= pdf.h - 19:
                pdf.set_xy(x, y)
                pdf.cell(width, 4.2, body[index])
                y += 4.2
                index += 1
            if index < len(body):
                advance()
        y += 5

# ---- The pack ------------------------------------------------------------------------------------


def fleet_pdf(fleets: list[dict], designs_by_fleet: list[dict],
              options: PrintOptions | None = None) -> bytes:
    options = options or PrintOptions()
    pdf = _new_pdf(options.paper, options.style)
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
    for fleet, designs in zip(fleets, designs_by_fleet) if options.orders else []:
        ruleset = RULESETS.get(fleet["ruleset"])
        pdf.header_title = fleet["name"]
        pdf.header_ruleset = ruleset.short_label if ruleset else fleet["ruleset"]
        pdf.non_conforming = not fleet_rules.fleet_conforming(fleet, designs)
        orders_page(pdf, fleet, options)
    if options.quickref:
        quickref_pages(pdf, fleets, designs_by_fleet)
    return bytes(pdf.output())


def battle_pack_error(fleets: list[dict]) -> str:
    """"" when the fleets may share a pack, else the reason (PLAN 10.3)."""
    if len(fleets) > 1 and len({f["ruleset"] for f in fleets}) > 1:
        return _("Both fleets must use the same ruleset.")
    return ""
