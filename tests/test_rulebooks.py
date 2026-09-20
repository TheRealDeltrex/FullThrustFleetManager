"""The rulebook viewer (PLAN 12): bundled PDFs, vendored pdf.js, page links, viewer setting."""

from __future__ import annotations

import re

import pytest

import paths
import store
from rulesets import RULESETS

PDFJS = paths.bundle_dir() / "static" / "pdfjs"


@pytest.fixture(autouse=True)
def library(tmp_path, monkeypatch):
    monkeypatch.setenv("FTFM_DATA_DIR", str(tmp_path))
    return tmp_path


def text(response) -> str:
    return response.get_data(as_text=True)


def test_every_book_a_ruleset_names_is_bundled():
    for ruleset in RULESETS.values():
        for book in ruleset.books:
            assert (paths.bundle_dir() / "rulebooks" / book.file).is_file(), book.file


def test_pdfjs_is_vendored_not_linked():
    assert (PDFJS / "web" / "viewer.html").is_file()
    assert (PDFJS / "build" / "pdf.mjs").is_file()
    assert (PDFJS / "build" / "pdf.worker.mjs").is_file()
    assert (PDFJS / "LICENSE").is_file()


def test_the_viewer_page_frames_the_bundled_file(client):
    page = text(client.get("/rulebook/FB1?page=16"))
    assert "pdfjs/web/viewer.html" in page
    assert "rulebook/FB1/file" in page
    assert "#page=16" in page          # FB1 prints its own page numbers (offset 0)
    assert "Page 16" in page


def test_the_page_offset_is_applied(client):
    """FT's printed page 15 is PDF page 16 (its BOOKS entry says +1)."""
    assert "#page=16" in text(client.get("/rulebook/FT?page=15"))
    assert "#page=15" in text(client.get("/rulebook/FB1?page=15"))


def test_the_viewer_opens_at_page_one_without_a_page(client):
    assert "#page=1" in text(client.get("/rulebook/FB1"))


def test_the_file_route_serves_the_pdf(client):
    response = client.get("/rulebook/FB1/file")
    assert response.status_code == 200 and response.mimetype == "application/pdf"
    assert response.data[:4] == b"%PDF"


def test_unknown_books_are_404(client):
    assert client.get("/rulebook/NOPE").status_code == 404
    assert client.get("/rulebook/NOPE/file").status_code == 404


def test_the_setting_switches_to_the_system_viewer(client):
    client.post("/settings", data={"pdf_viewer": "system", "paper": "A4"})
    assert store.load_settings()["pdf_viewer"] == "system"
    response = client.get("/rulebook/FT?page=15")
    assert response.status_code == 302
    assert response.headers["Location"] == "/rulebook/FT/file#page=16"

    client.post("/settings", data={"pdf_viewer": "app", "paper": "Letter"})
    assert client.get("/rulebook/FT?page=15").status_code == 200
    assert store.load_settings()["paper"] == "Letter"


def test_the_settings_tab_offers_the_books_and_the_viewer_choice(client):
    page = text(client.get("/settings"))
    assert "Rulebooks" in page and "My own PDF viewer" in page
    assert "/rulebook/FB1" in page and "/rulebook/FT" in page


def test_a_catalog_design_links_to_its_page(client):
    page = text(client.get("/design/fb:fb1:nac-furious"))
    design = store.get_design("fb:fb1:nac-furious")
    assert f"/rulebook/FB1?page={design['source']['page']}" in page


# ---- Quick reference text (PLAN 2.5) -------------------------------------------------------------
#
# The FT and MT text layers are OCR, and both books are two-column pages with figure captions and
# spec panels in them, so extraction used to pull in page numbers, captions and half sentences.
# These guard the result; entries the layout defeats are hand-transcribed in the extractor.


def quickref_entries():
    for ruleset in RULESETS.values():
        for entry in ruleset.quickref(set(), {}) or []:
            yield ruleset.id, entry
        # quickref() filters by the systems present, so ask for everything the books cover too.
        for entry in ruleset.quickref({"beam", "pulse_torpedo", "needle_beam", "submunition",
                                       "nova_cannon", "wave_gun", "hangar", "fighter_group",
                                       "sm_launcher", "sm_magazine", "pds", "pdaf", "adfc",
                                       "screen", "armour", "hold", "tug_drive", "ortillery",
                                       "cloak", "reflex_field", "mt_missile", "streamlining",
                                       "ftl", "crew", "hull_track"},
                                      {"core_systems": True, "rerolls": True,
                                       "vector_movement": True}):
            yield ruleset.id, entry
        # Each race brings its own entries, from its own pages (FB2's Kra'Vak section repeats
        # FB1's headings, so a wrong page reference here is a real risk).
        for race in {r.id for r in ruleset.races()} - {"human"}:
            for entry in ruleset.quickref({"kgun", "mkp", "scattergun", "fire_control", "hangar",
                                           "stinger", "pod_launcher", "spicule", "cortex",
                                           "screen_node", "drone_womb", "power_generator",
                                           "pulser", "plasma_bolt_launcher", "vapour_shroud"},
                                          {}, frozenset({race})):
                yield ruleset.id, entry


def test_every_quickref_entry_is_readable():
    seen = 0
    for ruleset_id, entry in quickref_entries():
        seen += 1
        where = f"{ruleset_id}/{entry.key}"
        assert "�" not in entry.text, where          # OCR could not read a character
        assert not re.search(r"[a-z]- [a-z]", entry.text), where   # "danger- ous"
        assert not re.search(r"\s[.,;:]", entry.text), where       # " ." from a line break
        assert entry.text.rstrip()[-1] in ".!?", where             # never cut mid-sentence
        assert not re.search(r"\b(MASS|POINTS COST|SYMBOL):", entry.text), where  # spec panel
        assert not re.search(r"\bFIG(URE)? \d", entry.text), where  # figure caption
        assert len(entry.text) > 100, where
        assert entry.title and entry.book
    assert seen > 30


def test_quickref_pages_point_at_the_right_page():
    """The page reference is the PRINTED page; the viewer adds each book's offset."""
    import fitz  # pymupdf

    books = {b.code: b for rs in RULESETS.values() for b in rs.books}
    checked = 0
    for ruleset_id, entry in quickref_entries():
        book = books[entry.book]
        with fitz.open(paths.bundle_dir() / "rulebooks" / book.file) as doc:
            page = doc[entry.page + book.page_offset - 1]        # printed -> 0-based PDF index
            words = {w.lower().strip(".,:;()") for w in page.get_text().split()}
        sample = [w.lower().strip('.,:;()"\'') for w in entry.text.split()[:12] if len(w) > 4]
        assert any(w in words for w in sample), f"{ruleset_id}/{entry.key} is not on p.{entry.page}"
        checked += 1
    assert checked > 30


def test_the_viewer_may_be_framed_by_its_own_page(client):
    """X-Frame-Options DENY would break the viewer; same-origin framing has to stay allowed."""
    headers = client.get("/rulebook/FB1").headers
    assert headers["X-Frame-Options"] == "SAMEORIGIN"
    assert "frame-ancestors 'self'" in headers["Content-Security-Policy"]
