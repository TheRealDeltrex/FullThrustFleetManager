# Full Thrust Fleet Manager

Fleet management tool for the *Full Thrust* starship wargame (Ground Zero Games): design ships,
build fleets to a points limit, track campaign damage, and print a fleet PDF for the table.
Supports the FT2 and Fleet Book rulesets first; Cross Dimensions and Project Continuum later.

![Full Thrust Fleet Manager](static/logo.jpg)

**Status:** v0.1.0, the first release. Both rulesets, the ship catalog, the design workbench,
fleets, campaign bookkeeping, the fleet PDF and the rulebook viewer are in. See
[docs/PLAN.md](docs/PLAN.md) for the full plan. Licensed GPL-3.0; GZG content notice in
[NOTICE.md](NOTICE.md).

## What it does

- **Design ships** to the Fleet Book or Full Thrust 2nd edition rules, with live MASS and NPV,
  an arc picker and a rules check. Break the rules deliberately if you want to; the design is
  then marked non-conforming.
- **Build fleets** to a points limit, in squadrons, from your own designs or the 96 ship classes
  of the books, with a tournament check that lists every violation.
- **Track a campaign**: damage marked by clicking the ship diagram, crew factors, repairs and
  replenishment, a fleet log.
- **Print** a fleet pack or a two-fleet battle pack: roster, record sheets, orders chart,
  ordnance tracker and a quick reference in the rulebooks' own wording.
- **Read the rulebooks** in the app, with every page reference in the UI linking into them.

Everything runs locally: no account, no server, plain JSON files you can back up and share.

## Running from source

Needs Python 3.11+.

```bash
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements-dev.txt
.venv/Scripts/python.exe app.py
```

Then open http://127.0.0.1:5000/. Data is kept in `userdata/` next to the checkout (set
`FTFM_DATA_DIR` to use another folder).

## Building

- **Windows desktop app:** `pyinstaller fleetmanager.spec` (output in
  `dist/FullThrustFleetManager/`). Runs fully offline; stores data in
  `%APPDATA%\FullThrustFleetManager`.
- **Web build:** `python scripts/build_browser_bundle.py` writes `web/bundle.json`; the
  "Deploy Pages" GitHub Action builds and publishes it.
- **Tests:** `python -m pytest`, lint with `ruff check .`.

## Rulebook sources (`rulebooks/`)

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
