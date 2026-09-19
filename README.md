# Full Thrust Fleet Manager

Fleet management tool for the *Full Thrust* starship wargame (Ground Zero Games): design ships,
build fleets to a points limit, track campaign damage, and print a fleet PDF for the table.
Supports the FT2 and Fleet Book rulesets first; Cross Dimensions and Project Continuum later.

**Status:** planning done, build not started. See [docs/PLAN.md](docs/PLAN.md) for the full plan
and [docs/mockups/](docs/mockups/) for the UI mockups. Licensed GPL-3.0; GZG content notice in
[NOTICE.md](NOTICE.md).

## Step 1: Rulebook sources (`rulebooks/`)

Clean, searchable, bookmarked copies of the four core books, built from the
originals in `E:\RPG\Tabletop\Full Thurst`:

| Output | Source | Text layer |
|---|---|---|
| `Full Thrust.pdf` | `Full Thrust.pdf` (image-only scan) | Tesseract OCR, invisible layer over the untouched scans |
| `More Thrust.pdf` | `More Thrust.pdf` | Native text, fake-bold overprints removed from the text layer |
| `Fleet Book 1.pdf` | `Fleet Book 1Full.pdf` | Native text, overprints removed |
| `Fleet Book 2.pdf` | `Fleet Book 2Full.pdf` | Native text, overprints removed |

Every page renders identically to the original. Bookmarks follow each book's
contents page and jump to the heading on the page; the Fleet Books also have one
bookmark per ship class under each fleet's "Ship Designs" entry.

Rebuild (needs PyMuPDF, pypdf and Tesseract at `C:\Program Files\Tesseract-OCR`):

```bash
python tools/build_rulebooks.py
```

`--only "Fleet Book 1"` rebuilds a single book. The OCR of Full Thrust takes about 5 minutes.

- `tools/build_rulebooks.py`: the pipeline
- `tools/tocs.py`: bookmark lists (transcribed from the contents pages)
- `tools/dedup_text.py`: hides the 2-5x overprinted "bold" text copies via empty `/ActualText`
