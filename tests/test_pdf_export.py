"""The fleet PDF (PLAN 10.2/10.3). Page text is read back with pymupdf; the visual check is by
eye on rendered pages (see CLAUDE.md)."""

from __future__ import annotations

import re

import fitz  # pymupdf
import pytest

import pdf_export
import ssd_layout
import store
from rulesets import RULESETS

FB_SHIPS = ["fb:fb1:nac-furious", "fb:fb1:nac-vandenburg", "fb:fb1:nac-ark-royal"]


@pytest.fixture(autouse=True)
def library(tmp_path, monkeypatch):
    monkeypatch.setenv("FTFM_DATA_DIR", str(tmp_path))
    return tmp_path


def a_fleet(name="Home Fleet", ruleset="fb", ships=None, **extra) -> dict:
    fleet, _msg = store.create_fleet(ruleset, name, faction="NAC", points_limit=1500, **extra)
    for design_id in (ships if ships is not None else FB_SHIPS):
        store.add_ship(fleet, design_id)
    store.save_fleet(fleet)
    return fleet


def render(fleets, options=None) -> tuple[bytes, list[str]]:
    designs = [store.designs_for_fleet(f) for f in fleets]
    data = pdf_export.fleet_pdf(fleets, designs, options)
    with fitz.open("pdf", data) as doc:
        return data, [page.get_text() for page in doc]


def test_a_fleet_pack_has_every_section(client):
    fleet = a_fleet()
    _data, pages = render([fleet])
    text = "\n".join(pages)
    assert "Home Fleet" in pages[0] and "Furious" in pages[0]          # roster
    assert "Record sheets" in text
    assert "Orders chart" in text
    assert "Quick reference" in text
    assert "Fleet Book" in text or "FB1 p." in text                    # page references


def test_every_page_carries_the_ruleset_and_the_page_number():
    fleet = a_fleet()
    _data, pages = render([fleet])
    for number, page in enumerate(pages, start=1):
        assert "FB · Home Fleet" in page
        assert f"Page {number} / {len(pages)}" in page


def test_a_non_conforming_fleet_is_marked_on_every_page():
    """A fleet-level violation marks the pages; a violating ship is starred on the roster."""
    fleet = a_fleet()
    store.update_fleet_details(fleet, points_limit=10)
    store.save_fleet(fleet)
    _data, pages = render([fleet])
    assert all("non-conforming ships" in page for page in pages)
    assert "*" not in pages[0]       # the ships themselves are legal

    design, _msg = store.new_design("fb", name="Half-built")   # under its TMF
    store.save_design(dict(design, allow_rule_breaking=True), mode="refit")
    broken = a_fleet(name="Broken", ships=[design["id"]])
    _data, pages = render([broken])
    assert "*" in pages[0] and "non-conforming" in pages[0]


def test_a_conforming_fleet_is_not_marked():
    _data, pages = render([a_fleet()])
    assert not any("non-conforming ships" in page for page in pages)


def test_paper_sizes():
    fleet = a_fleet()
    for paper, width in (("A4", 210), ("Letter", 215.9)):
        data, _pages = render([fleet], pdf_export.PrintOptions(paper=paper))
        with fitz.open("pdf", data) as doc:
            assert round(doc[0].rect.width * 25.4 / 72) == round(width)


def test_sections_can_be_switched_off():
    fleet = a_fleet()
    options = pdf_export.PrintOptions(sheets=False, orders=False, tracker=False, quickref=False)
    _data, pages = render([fleet], options)
    assert len(pages) == 1 and "Home Fleet" in pages[0]


def test_docked_and_destroyed_ships_get_no_sheet_but_stay_on_the_roster():
    fleet = a_fleet()
    store.update_ship(fleet, fleet["ships"][0]["uid"], status="docked")
    store.save_fleet(fleet)
    _data, pages = render([fleet])
    text = "\n".join(pages)
    assert "Not printed:" in text and "CE-1 (docked)" in text
    assert "CE-1" in pages[0]

    _data, pages = render([fleet], pdf_export.PrintOptions(include_docked=True))
    assert "Not printed:" not in "\n".join(pages)


def test_a_blank_copy_leaves_the_campaign_state_off(monkeypatch):
    fleet = a_fleet()
    fleet["ships"][0]["damage"]["hull"] = 6
    store.save_fleet(fleet)
    marked, _p = render([fleet])
    blank, _p = render([fleet], pdf_export.PrintOptions(blank=True))
    undamaged, _p = render([fleet], pdf_export.PrintOptions(damage=False))
    assert len(blank) == len(undamaged)          # both drop the same marks
    assert len(marked) != len(blank)             # ... and the marked copy really has more ink


def test_the_tracker_only_appears_when_the_fleet_carries_fighters_or_ordnance():
    plain = a_fleet(ships=["fb:fb1:nac-vandenburg"])
    assert "Fighters and ordnance" not in "\n".join(render([plain])[1])
    carrier = a_fleet(name="Carrier Group", ships=["fb:fb1:nac-ark-royal"])
    assert "Fighters and ordnance" in "\n".join(render([carrier])[1])


def test_the_quick_reference_only_covers_the_systems_present():
    fleet = a_fleet(ships=["fb:fb1:nac-vandenburg"])       # beams, PDS, fire control, screens
    text = "\n".join(render([fleet])[1])
    assert "Beam batteries" in text
    assert "Salvo missile" not in text                      # this fleet carries none
    assert "Point defence systems" in text


def test_the_quick_reference_uses_the_book_wording_with_a_page_reference():
    entries = RULESETS["fb"].quickref({"beam"}, {})
    beam = next(e for e in entries if e.key == "beam")
    assert beam.book == "FB1" and beam.page > 0
    assert "Class 1" in beam.text                            # straight from the book


def test_a_battle_pack_holds_both_fleets_and_one_quick_reference():
    first = a_fleet()
    second = a_fleet(name="Task Force", ships=["fb:fb1:nsl-falke"])
    _data, pages = render([first, second])
    text = "\n".join(pages)
    assert text.count("Quick reference") == 1
    assert "Home Fleet" in text and "Task Force" in text
    assert text.count("Orders chart") == 2                   # one chart per fleet


def test_a_battle_pack_of_two_rulesets_is_refused():
    first = a_fleet()
    second = a_fleet(name="FT2 Fleet", ruleset="ft2", ships=["ft2:ft:courier"])
    assert pdf_export.battle_pack_error([first, second])
    assert pdf_export.battle_pack_error([first, a_fleet(name="Other")]) == ""
    assert pdf_export.battle_pack_error([first]) == ""


def test_an_ft2_fleet_renders_with_its_own_book_references():
    fleet = a_fleet(name="Task Force", ruleset="ft2",
                    ships=["ft2:ft:battleship", "ft2:ft:courier"])
    _data, pages = render([fleet])
    text = "\n".join(pages)
    assert "FT2 · Task Force" in text
    assert "FT p." in text


def test_a_fleet_with_no_ships_still_produces_a_roster():
    fleet = a_fleet(ships=[])
    _data, pages = render([fleet])
    assert "Home Fleet" in pages[0]


# ---- The print dialog (PLAN 10.3) ---------------------------------------------------------------


def test_the_dialog_needs_a_fleet(client):
    assert client.get("/print").status_code == 404


def test_the_dialog_offers_the_sections_and_a_second_fleet(client):
    a_fleet()
    a_fleet(name="Task Force", ships=[])
    page = client.get("/print").get_data(as_text=True)
    assert "Record sheets" in page and "Quick reference" in page
    assert "Blank copy" in page and "Task Force" in page


def test_posting_the_dialog_returns_a_pdf(client):
    a_fleet()
    response = client.post("/print", data={"roster": "on", "sheets": "on", "paper": "A4"})
    assert response.status_code == 200
    assert response.mimetype == "application/pdf"
    assert response.data[:4] == b"%PDF"
    assert "Home_Fleet.pdf" in response.headers["Content-Disposition"]


def test_a_battle_pack_of_two_rulesets_is_refused_in_the_dialog(client):
    a_fleet()
    other = a_fleet(name="FT2 Fleet", ruleset="ft2", ships=["ft2:ft:courier"])
    page = client.post("/print", data={"second_fleet": other["id"], "roster": "on"},
                       follow_redirects=True).get_data(as_text=True)
    assert "same ruleset" in page
    page = client.post("/print", data={"second_fleet": "nope"},
                       follow_redirects=True).get_data(as_text=True)
    assert "second fleet was not found" in page


# ---- Phalon pulser configuration on paper (FB2 p.35) ---------------------------------------------


def a_phalon_fleet() -> tuple[dict, str]:
    """A one-ship Phalon fleet whose pulsers are all configured to close range."""
    fleet, _msg = store.create_fleet("fb", "Grand Fleet", race="phalon", faction="PH")
    store.add_ship(fleet, "fb:fb2:ph-voth")
    design = store.get_design("fb:fb2:ph-voth")
    uid = next(s["uid"] for s in design["systems"] if s["type"] == "pulser")
    fleet["ships"][0]["loadout"] = {"fighters": [], "magazines": [],
                                    "pulsers": [{"pulser": uid, "mode": "C"}]}
    store.save_fleet(fleet)
    return fleet, uid


def test_a_configured_pulser_prints_its_letter():
    fleet, _uid = a_phalon_fleet()
    _data, pages = render([fleet], pdf_export.PrintOptions(quickref=False, roster=False))
    assert "C" in chr(10).join(pages)


def test_blank_pulsers_prints_the_icons_empty():
    """The print dialog's toggle drops the configuration so the player writes it on the sheet,
    which is how FB2 prints Phalon SSDs."""
    fleet, _uid = a_phalon_fleet()
    options = pdf_export.PrintOptions(quickref=False, blank_pulsers=True)
    design = store.get_design("fb:fb2:ph-voth")
    assert pdf_export._sheet_loadout(fleet["ships"][0], design, options)["pulsers"] == []
    # Without the toggle the sheet keeps what the ship recorded.
    kept = pdf_export._sheet_loadout(fleet["ships"][0], design, pdf_export.PrintOptions())
    assert len(kept["pulsers"]) == 1
    # A race with no pulsers is untouched either way.
    plain = {"uid": "x", "loadout": {"fighters": [], "magazines": [], "pulsers": []}}
    assert pdf_export._sheet_loadout(plain, {}, options) == plain["loadout"]


def test_a_cross_dimensions_fleet_prints_its_own_sheets_and_reference():
    design, _msg = store.new_design("ftcd", name="Lancer")
    design.update(tmf=40, hull_boxes=10, thrust=6, drive_advanced=True, systems=[
        {"uid": "g1", "type": "graser", "class": 1, "arcs": ["FP", "F", "FS"]},
        {"uid": "f1", "type": "fire_control"},
        {"uid": "s1", "type": "advanced_screen", "level": 1},
    ])
    ok, msg, _new_id = store.save_design(design, mode="refit")
    assert ok, msg
    fleet = a_fleet(name="Lancers", ruleset="ftcd", ships=[design["id"]])
    store.update_fleet_details(fleet, options={"cd_cpv": True})
    store.save_fleet(fleet)
    text = "\n".join(render([fleet])[1])
    assert "FTCD · Lancers" in text
    assert "Combat Points Value (CPV) hull cost" in text      # options by name, not by key
    assert "Grasers" in text and "Advanced screens" in text   # the quick reference, from CD
    assert "CD p." in text


def test_the_tracker_names_one_shot_systems():
    pages = render([a_fleet(ships=["fb:fb1:fse-athena"])])[1]
    tracker = next(p for p in pages if "Fighters and ordnance" in p)
    assert "Submunition" in tracker and "submunition" not in tracker


# ---- What the tracker and the quick reference read: the loadout carried -------------------------


def pc_design(systems, loadout) -> dict:
    return {"uid": "x", "systems": systems,
            "default_loadout": {"fighters": [], "magazines": [], **loadout}}


def test_tracker_rows_follow_the_loadout():
    hangar = [{"uid": "h", "type": "hangar"}]
    # An empty bay carries nothing to track.
    assert pdf_export._tracker_rows({"loadout": None}, pc_design(hangar, {})) == []
    # A light wing is eight fighters with four endurance (PC p.75).
    light = {"fighters": [{"hangar": "h", "type": "standard", "extras": ["light"]}]}
    assert [r[1:3] for r in pdf_export._tracker_rows({"loadout": None}, pc_design(hangar, light))] == [(8, 4)]
    # A ship's own loadout wins over the design's.
    standard = {"fighters": [{"hangar": "h", "type": "standard"}], "magazines": []}
    own = pdf_export._tracker_rows({"loadout": standard}, pc_design(hangar, light))
    assert [r[1:3] for r in own] == [(6, 6)]
    # A magazine shows the salvos it holds: two ER salvos in 6 MASS are two boxes, not three.
    magazine = [{"uid": "m", "type": "sm_magazine", "capacity": 6, "feeds": []}]
    er = {"magazines": [{"magazine": "m", "salvos": ["er", "er"]}]}
    assert [r[1] for r in pdf_export._tracker_rows({"loadout": None}, pc_design(magazine, er))] == [2]


def test_gunboats_in_a_boat_bay_get_the_gunboat_reference():
    """PC p.80: a boat bay carries gunboats too; the gunboat entry must come with them."""
    pc = RULESETS["ftpc"]
    design, _msg = store.new_design("ftpc", name="Boat carrier")
    design.update(tmf=100, systems=[{"uid": "b", "type": "boat_bay", "mass": 24}],
                  default_loadout={"fighters": [], "magazines": [],
                                   "gunboats": [{"carrier": "b", "type": "standard"}]})
    design["allow_rule_breaking"] = True
    ok, msg, design_id = store.save_design(design)
    assert ok, msg
    fleet = a_fleet(ruleset="ftpc", ships=[design_id])
    pages = render([fleet])[1]
    reference = "".join(p for p in pages if "Quick reference" in p)
    gunboat = next(e for e in pc.quickref({"gunboat_rack"}, {}) if e.key == "gunboat_rack")
    assert gunboat.title in reference


# ---- Print design and pagination ---------------------------------------------------------------


def _assert_page_bounds(doc):
    """Body text, headers and footers must stay on the printable page."""
    for page in doc:
        for word in page.get_text("words"):
            x0, y0, x1, y1 = word[:4]
            assert x0 >= 11 * 72 / 25.4, word
            assert x1 <= page.rect.width - 11 * 72 / 25.4, word
            assert y0 >= 5 * 72 / 25.4, word
            assert y1 <= page.rect.height - 6 * 72 / 25.4, word


@pytest.mark.parametrize("paper", ["A4", "Letter"])
@pytest.mark.parametrize("style", ["mono", "color"])
def test_print_styles_wrap_long_names_and_repeat_roster_headings(paper, style):
    fleet = a_fleet(name="Northern Expeditionary Fleet - Outer Approach", ships=[])
    for n in range(36):
        store.add_ship(fleet, FB_SHIPS[n % len(FB_SHIPS)])
        fleet["ships"][-1]["name"] = f"Vessel {n + 1}: The Long Road to the Distant Northern Frontier"
    options = pdf_export.PrintOptions(paper=paper, style=style, sheets=False, orders=False,
                                      tracker=False, quickref=False)
    data, pages = render([fleet], options)
    assert len(pages) > 1
    assert "Vessel 36:" in "\n".join(pages)
    # Every continuation containing ship rows repeats the column labels.
    for page in pages:
        if "Vessel" in page:
            assert "Thrust" in page and "Source" in page
    with fitz.open("pdf", data) as doc:
        _assert_page_bounds(doc)
        pixels = doc[0].get_pixmap(colorspace=fitz.csRGB, matrix=fitz.Matrix(.5, .5)).samples
        # MuPDF's RGB rasterisation can round a neutral channel by one level.
        has_colour = any(max(rgb) - min(rgb) > 2
                         for rgb in zip(pixels[::3], pixels[1::3], pixels[2::3]))
        assert has_colour == (style == "color")
        if style == "mono":
            for drawing in doc[0].get_drawings():
                for colour in (drawing["color"], drawing["fill"]):
                    assert colour is None or max(colour) - min(colour) < .001


def test_both_styles_use_identical_ssd_primitives(monkeypatch):
    fleet = a_fleet()
    diagrams = []
    original = pdf_export.draw_diagram

    def capture(pdf, diagram, *args):
        diagrams.append(diagram)
        return original(pdf, diagram, *args)

    monkeypatch.setattr(pdf_export, "draw_diagram", capture)
    for style in ("mono", "color"):
        render([fleet], pdf_export.PrintOptions(style=style))
    count = len(fleet["ships"])
    assert len(diagrams) == count * 2
    assert diagrams[:count] == diagrams[count:]


def test_orders_and_long_tracker_rows_stay_inside_letter_page(monkeypatch):
    fleet = a_fleet(ships=["fb:fb1:nac-ark-royal"])
    fleet["ships"][0]["name"] = "Carrier with a deliberately long ship name for the orders grid"
    monkeypatch.setattr(pdf_export, "_tracker_rows", lambda ship, design: [
        ("Long reserve magazine", 48, 9, "test-magazine")])
    data, pages = render([fleet], pdf_export.PrintOptions(paper="Letter", roster=False,
                                                         sheets=False, quickref=False))
    assert "Track 1" in "\n".join(pages)
    with fitz.open("pdf", data) as doc:
        _assert_page_bounds(doc)
        # The capacity is retained across cards, rather than truncated to fit.
        squares = [item for p in doc for drawing in p.get_drawings() for item in drawing["items"]
                   if item[0] == "re" and abs(item[1].width - 4.5 * 72 / 25.4) < .05
                   and abs(item[1].height - 4.5 * 72 / 25.4) < .05]
        assert len(squares) == 48


def test_print_dialog_offers_and_applies_styles(client):
    a_fleet()
    page = client.get("/print").get_data(as_text=True)
    assert 'name="print_style"' in page
    assert "Black and white (ink-saving)" in page and "Fleet dossier (colour)" in page
    for style in ("mono", "color", "invalid"):
        response = client.post("/print", data={"roster": "on", "print_style": style})
        assert response.mimetype == "application/pdf"
        with fitz.open("pdf", response.data) as doc:
            colour = doc[0].get_text("dict")["blocks"][0]["lines"][0]["spans"][0]["color"]
            assert colour == (0x1C445F if style == "color" else 0x191919)


def test_battle_pack_orders_keep_each_fleets_warning():
    first = a_fleet(name="Over Limit")
    store.update_fleet_details(first, points_limit=10)
    second = a_fleet(name="Legal Fleet")
    _data, pages = render([first, second])
    orders = [page for page in pages if "Orders chart" in page]
    assert len(orders) == 2
    assert "non-conforming ships" in orders[0]
    assert "non-conforming ships" not in orders[1]


def test_long_orders_charts_keep_every_turn_at_a_writable_width():
    fleet = a_fleet(ships=[FB_SHIPS[0]])
    data, pages = render([fleet], pdf_export.PrintOptions(roster=False, sheets=False,
        tracker=False, quickref=False, turns=12))
    assert len(pages) == 2
    assert "11" in pages[1] and "12" in pages[1]
    assert all("Orders chart" in page and "Furious" in page for page in pages)
    with fitz.open("pdf", data) as doc:
        _assert_page_bounds(doc)


# ---- Record sheets after the FT Light layout -----------------------------------------------------

NAC_MIXED = [f"fb:fb1:nac-{s}" for s in (
    "harrison", "minerva", "minerva", "tacoma", "ticonderoga", "ticonderoga", "huron", "furious",
    "vandenburg", "majestic", "victoria", "excalibur", "valley-forge", "ark-royal")]
ESCORTS = [f"fb:fb1:nac-{s}" for s in ("harrison", "minerva", "tacoma", "ticonderoga", "ticonderoga")]


def _sheet_pages(data):
    with fitz.open("pdf", data) as doc:
        return [(page.rect.width > page.rect.height, page.get_text()) for page in doc
                if "Record sheets" in page.get_text()]


def test_record_sheets_are_landscape_with_at_least_six_ships_a_page():
    fleet = a_fleet(ships=NAC_MIXED)
    data, _pages = render([fleet], pdf_export.PrintOptions(roster=False, tracker=False,
                                                          quickref=False, orders=False))
    sheets = _sheet_pages(data)
    assert all(landscape for landscape, _text in sheets)
    counts = [len(set(re.findall(r"\b[A-Z]{2,4}-\d+\b", text))) for _l, text in sheets]
    assert sum(counts) == len(NAC_MIXED)
    assert len(sheets) == 2 and min(counts) >= 6


def test_one_scale_per_page_and_legible(monkeypatch):
    """Every SSD on a sheet page is drawn at the same scale, never below MIN_SCALE when a
    span can avoid it."""
    fleet = a_fleet(ships=NAC_MIXED + ["fb:fb2:sv-shyy-tha-var"])
    designs = store.designs_for_fleet(fleet)
    scales = []
    original = pdf_export._ship_card

    def capture(pdf, card, x, y, w, h, scale, points):
        scales.append((pdf.page_no(), round(scale, 4)))
        return original(pdf, card, x, y, w, h, scale, points)

    monkeypatch.setattr(pdf_export, "_ship_card", capture)
    pdf_export.fleet_pdf([fleet], [designs], pdf_export.PrintOptions(roster=False))
    assert len(scales) == len(fleet["ships"])
    for page in {p for p, _s in scales}:
        assert len({s for p, s in scales if p == page}) == 1
    assert min(s for _p, s in scales) >= pdf_export.MIN_SCALE


def test_a_ship_too_tall_for_a_slot_spans_two():
    fleet = a_fleet(ships=["fb:fb2:sv-sa-kess-tha", *ESCORTS])
    designs = store.designs_for_fleet(fleet)
    pdf = pdf_export._new_pdf("A4")
    pdf.add_page(orientation="L")
    cards = [pdf_export._Card(s, designs[s["design_id"]], d := ssd_layout.layout(designs[s["design_id"]]),
                              pdf_export._bounds(d)) for s in fleet["ships"]]
    pages = pdf_export._pages(pdf, cards)
    assert len(pages) == 1
    assert cards[0].span != (1, 1)
    occupied = [(c.slot[0] + dc, c.slot[1] + dr) for c in cards
                for dc in range(c.span[0]) for dr in range(c.span[1])]
    assert len(occupied) == len(set(occupied))                # no two cards overlap


def test_the_orders_plot_always_has_pages_of_its_own():
    """Master: even a fleet small enough to leave room under its cards."""
    for ships in (ESCORTS, NAC_MIXED):
        fleet = a_fleet(ships=ships)
        _data, pages = render([fleet], pdf_export.PrintOptions(roster=False, quickref=False))
        plotted = [p for p in pages if "Orders chart" in p]
        assert plotted and all("Record sheets" not in p for p in plotted)
        assert all(ship["table_id"] in plotted[0] for ship in fleet["ships"])
        assert "Turn 10" in plotted[0] and "Start V" in plotted[0]


@pytest.mark.parametrize("paper", ["A4", "Letter"])
@pytest.mark.parametrize("style", ["mono", "color"])
def test_record_sheets_and_plot_stay_on_the_page(paper, style):
    fleet = a_fleet(ships=NAC_MIXED[:5])
    for ship in fleet["ships"]:
        ship["name"] = "A Deliberately Long Ship Name That Will Not Fit The Card Band"
    data, _pages = render([fleet], pdf_export.PrintOptions(paper=paper, style=style, roster=False,
                                                          quickref=False))
    with fitz.open("pdf", data) as doc:
        _assert_page_bounds(doc)


@pytest.mark.parametrize("style", ["mono", "color"])
def test_ship_cards_draw_a_hull_silhouette_in_both_styles(style):
    data, _pages = render([a_fleet(ships=NAC_MIXED)],
                          pdf_export.PrintOptions(style=style, roster=False, quickref=False))
    with fitz.open("pdf", data) as doc:
        silhouettes = [d for page in doc for d in page.get_drawings()
                       if len(d["items"]) == 9 and all(i[0] == "l" for i in d["items"])]
    assert len(silhouettes) >= len(NAC_MIXED)
