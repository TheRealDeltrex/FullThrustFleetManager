"""Build clean, searchable, bookmarked copies of the Full Thrust rulebooks.

* Full Thrust (image-only scan): OCR with Tesseract, invisible text layer
  laid over the untouched page images.
* More Thrust, Fleet Book 1 & 2 (native text): fake-bold overprint copies
  are hidden from the text layer (see dedup_text.py); visuals unchanged.
* All four: bookmarks from the books' contents pages, pointing at the
  heading's position on the page; Fleet Books also get one bookmark per
  ship class.

Usage:  python tools/build_rulebooks.py [--src DIR] [--out DIR] [--only "Fleet Book 1" ...]
"""
import argparse
import io
import os
import re
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pymupdf
from pypdf import PdfReader, PdfWriter

from dedup_text import dedup_page
import tocs

ROOT = Path(__file__).resolve().parent.parent
# Where the bought PDFs live. Override with --src, or the FT_RULEBOOK_SRC env var.
DEFAULT_SRC = Path(os.environ.get("FT_RULEBOOK_SRC", "rulebook-sources"))
TESSERACT = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
OCR_DPI = 300

BOOKS = [
    # source file, output file, title, toc, printed->pdf page offset, ocr
    ("Full Thrust.pdf", "Full Thrust.pdf", "Full Thrust (2nd Edition)", tocs.FULL_THRUST, 1, True),
    ("More Thrust.pdf", "More Thrust.pdf", "More Thrust", tocs.MORE_THRUST, 0, False),
    ("Fleet Book 1Full.pdf", "Fleet Book 1.pdf", "Full Thrust Fleet Book 1", tocs.FLEET_BOOK_1, 0, False),
    ("Fleet Book 2Full.pdf", "Fleet Book 2.pdf", "Full Thrust Fleet Book 2", tocs.FLEET_BOOK_2, 0, False),
]


# --------------------------------------------------------------------- OCR
def _ocr_page(args):
    doc_path, pno, workdir = args
    doc = pymupdf.open(doc_path)
    png = Path(workdir) / f"p{pno:03d}.png"
    base = Path(workdir) / f"p{pno:03d}"
    doc[pno].get_pixmap(dpi=OCR_DPI, colorspace=pymupdf.csGRAY).save(png)
    env = dict(os.environ, OMP_THREAD_LIMIT="1")
    subprocess.run([str(TESSERACT), str(png), str(base), "-l", "eng", "--dpi", str(OCR_DPI),
                    "-c", "textonly_pdf=1", "pdf"],
                   check=True, capture_output=True, env=env)
    return pno, base.with_suffix(".pdf")


def add_ocr_layer(doc, src_path):
    with tempfile.TemporaryDirectory() as workdir:
        jobs = [(str(src_path), pno, workdir) for pno in range(doc.page_count)]
        with ThreadPoolExecutor(max_workers=max(1, (os.cpu_count() or 4) - 1)) as pool:
            for pno, ocr_pdf in pool.map(_ocr_page, jobs):
                # Load from memory: the grafted source stays referenced by
                # `doc`, which would keep the temp file locked on Windows.
                ocr = pymupdf.open("pdf", ocr_pdf.read_bytes())
                doc[pno].show_pdf_page(doc[pno].rect, ocr, 0, overlay=True)
                print(f"  OCR page {pno + 1}/{doc.page_count}", end="\r")
    print()


# ------------------------------------------------------------ text dedup
def dedup_document(src_path):
    # PyMuPDF round-trip first: Fleet Book 1 carries a malformed /Encrypt
    # entry that pypdf refuses to open.
    raw = pymupdf.open(src_path).tobytes()
    writer = PdfWriter(clone_from=PdfReader(io.BytesIO(raw)))
    hidden = sum(dedup_page(page, writer) for page in writer.pages)
    buf = io.BytesIO()
    writer.write(buf)
    print(f"  hid {hidden} overprinted text copies")
    return pymupdf.open("pdf", buf.getvalue())


# -------------------------------------------------------------- bookmarks
def _find_heading(page, title):
    """Top-left point of `title` on the page, or None."""
    if title.startswith("SECTION"):
        title = title.split(":", 1)[1]
    # Quotes/apostrophes differ between the TOC text and the page (curly vs
    # straight, OCR), so search quote-free fragments, longest first.
    probes = []
    for chunk in sorted(re.split(r"[\"'“”‘’]", title), key=len, reverse=True):
        words = chunk.split()
        probes += [" ".join(words[:n]) for n in (len(words), 4, 3, 2)]
    for probe in dict.fromkeys(probes):
        if len(probe) < 4:
            continue
        # Headings are set in capitals; skip matches in running body text.
        hits = [r for r in page.search_for(probe)
                if any(c.isalpha() for c in page.get_textbox(r))
                and page.get_textbox(r).upper() == page.get_textbox(r)]
        if hits:
            r = min(hits, key=lambda r: (r.y0, r.x0))
            return pymupdf.Point(0, max(r.y0 - 12, 0))
    return None


def find_ships(page):
    """Ship-class headings: 13pt Faktos spans, possibly wrapped over 2 lines."""
    spans = []
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            for s in line["spans"]:
                if "Faktos" in s["font"] and 12.5 <= s["size"] <= 13.5 and s["text"].strip():
                    spans.append((pymupdf.Rect(s["bbox"]), s["text"].strip()))
    spans.sort(key=lambda t: (t[0].y0, t[0].x0))
    groups = []
    for rect, text in spans:
        g = groups[-1] if groups else None
        if g and 0 <= rect.y0 - g[0].y1 < 12 and rect.x0 < g[0].x1 and rect.x1 > g[0].x0:
            g[0] |= rect
            g[1].append(text)
        else:
            groups.append([rect, [text]])
    ships = []
    for rect, parts in groups:
        name = re.sub(r"\s+", " ", " ".join(parts)).strip()
        if " class" in name.lower():
            ships.append((name, rect))
    return ships


def build_toc(doc, entries, offset, with_ships):
    pages = [p + offset for _, _, p in entries]
    toc = []
    for i, (level, title, printed) in enumerate(entries):
        pno = printed + offset                     # 1-based PDF page
        dest = {"kind": pymupdf.LINK_GOTO, "page": pno - 1, "to": pymupdf.Point(0, 0), "zoom": 0}
        # Fleet "Ship Designs" chapters open on a fresh page whose banner
        # doesn't repeat the TOC wording, so they keep the page top.
        chapter_start = printed == 0 or "Ship Designs" in title
        pt = None if chapter_start else _find_heading(doc[pno - 1], title)
        if pt:
            dest["to"] = pt
        toc.append([level, title, pno, dest])
        if with_ships and ("Ship Designs" in title or "Merchant" in title):
            end = next((p for p in pages[i + 1:] if p > pno), doc.page_count + 1)
            for sp in range(pno, end):
                for name, rect in find_ships(doc[sp - 1]):
                    toc.append([level + 1, name, sp,
                                {"kind": pymupdf.LINK_GOTO, "page": sp - 1,
                                 "to": pymupdf.Point(0, max(rect.y0 - 12, 0)), "zoom": 0}])
    return toc


# ------------------------------------------------------------------ main
def build(src_dir, out_dir, only=None):
    out_dir.mkdir(parents=True, exist_ok=True)
    for src_name, out_name, title, entries, offset, ocr in BOOKS:
        if only and not any(o.lower() in out_name.lower() for o in only):
            continue
        src = src_dir / src_name
        print(f"{src_name} -> {out_name}")
        if ocr:
            doc = pymupdf.open(src)
            add_ocr_layer(doc, src)
        else:
            doc = dedup_document(src)
        toc = build_toc(doc, entries, offset, with_ships="Fleet Book" in title)
        doc.set_toc(toc)
        doc.set_metadata({"title": title, "author": "Jon Tuffley / Ground Zero Games",
                          "subject": "Full Thrust starship combat rules",
                          "producer": "FullThrustFleetManager build_rulebooks.py"})
        doc.set_pagemode("UseOutlines")
        doc.save(out_dir / out_name, garbage=3, deflate=True)
        print(f"  {len(toc)} bookmarks")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", type=Path, default=DEFAULT_SRC)
    ap.add_argument("--out", type=Path, default=ROOT / "rulebooks")
    ap.add_argument("--only", nargs="+", help="build only books whose output name contains one of these")
    a = ap.parse_args()
    build(a.src, a.out, a.only)
