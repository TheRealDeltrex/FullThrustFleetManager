"""The fleet PDF (PLAN 10.2/10.3). Page text is read back with pymupdf; the visual check is by
eye on rendered pages (see CLAUDE.md)."""

from __future__ import annotations

import fitz  # pymupdf
import pytest

import pdf_export
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
