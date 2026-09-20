"""The rulebook viewer (PLAN 12): bundled PDFs, vendored pdf.js, page links, viewer setting."""

from __future__ import annotations

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


def test_the_viewer_may_be_framed_by_its_own_page(client):
    """X-Frame-Options DENY would break the viewer; same-origin framing has to stay allowed."""
    headers = client.get("/rulebook/FB1").headers
    assert headers["X-Frame-Options"] == "SAMEORIGIN"
    assert "frame-ancestors 'self'" in headers["Content-Security-Policy"]
