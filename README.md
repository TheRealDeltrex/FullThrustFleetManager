# Full Thrust Fleet Manager — dev version

[![Full Thrust Fleet Manager](https://raw.githubusercontent.com/TheRealDeltrex/FullThrustFleetManager/devversion/static/logo.jpg)](https://therealdeltrex.github.io/FullThrustFleetManager/)

This branch (`devversion`) holds the **full Python/Flask source code**. It exists so the app can
be run from source, read and altered: if you or your gaming group want a system, a house rule or
a ship class it doesn't already handle, this is the branch to work from.

If you just want to use the app and don't need to touch the code, you don't need this branch.
**Download a build** or play in your browser from the
[download page](https://therealdeltrex.github.io/FullThrustFleetManager/), or take the
[latest release](../../releases/latest) directly. The [`main` branch](../../tree/main) carries
the description, the licence and the workflow files, and nothing else.

A local fleet manager for the *Full Thrust* starship wargame (Ground Zero Games): design ships,
build fleets to a points limit, track campaign damage, and print a fleet PDF for the table.
Supports the Full Thrust 2nd edition and Fleet Book rulesets, including the Fleet Book 2 alien
races. Everything runs locally: no account, no server, plain JSON files you can back up and share.

Not affiliated with Ground Zero Games.

## What it does

- **Design ships** to the Fleet Book or Full Thrust 2nd edition rules, with live MASS and NPV,
  an arc picker and a rules check. Break the rules deliberately if you want to; the design is
  then marked non-conforming.
- **Build fleets** to a points limit, in squadrons, from your own designs or the ship classes of
  the books, with a tournament check that lists every violation.
- **Field the alien races**: Kra'Vak, Sa'Vasku and Phalon, each an additive tech module inside
  the Fleet Book ruleset with its own systems, record-sheet icons, validation and quick
  reference.
- **Track a campaign**: damage marked by clicking the ship diagram, crew factors, repairs and
  replenishment, a fleet log.
- **Print** a fleet pack or a two-fleet battle pack: roster, record sheets, orders chart,
  ordnance tracker and a quick reference in the rulebooks' own wording.
- **Read the rulebooks** in the app, with every page reference in the UI linking into them.

## Running from source

Needs Python 3.11 or newer.

```bash
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements-dev.txt
.venv/Scripts/python.exe app.py
```

Then open <http://127.0.0.1:5000/>. Data is kept in `userdata/` next to the checkout; set
`FTFM_DATA_DIR` to put it elsewhere.

**Start with [CLAUDE.md](CLAUDE.md)** before changing anything: it is the operating manual and
it is kept current. The build plan and every design decision behind the app are in
[docs/PLAN.md](docs/PLAN.md).

## Building

- **Windows desktop app:** `pyinstaller fleetmanager.spec`, output in `dist/`. Runs fully
  offline. Released builds are Authenticode-signed with a self-signed "Deltrex" certificate,
  which puts a publisher name on the SmartScreen prompt without silencing it.
- **Linux desktop app:** the "Build Linux" GitHub Action runs `fleetmanager-linux.spec`
  (onefile, no tray icon) and smoke-tests the binary. Nothing has been released for Linux yet;
  the workflow is there if it is ever wanted.
- **Web build:** `python scripts/build_browser_bundle.py` writes `web/bundle.json`; the
  "Deploy Pages" GitHub Action builds the site, renders the preview pages from the real app
  and publishes the lot.
- **Tests and lint:** `python -m pytest`, `ruff check .`.
- **Shipping a release:** the whole procedure, including signing, is in
  [.claude/skills/shipping-a-release/SKILL.md](.claude/skills/shipping-a-release/SKILL.md).
  Releases are tagged here on `devversion`; `main` is never merged into.

## Rulebooks (`rulebooks/`)

The app ships clean, searchable, bookmarked copies of the four core books, prepared from the
PDFs Ground Zero Games sells, so that every page reference in the app opens the right page.
Every page renders identically to the original; the work was on the text layer and the
bookmarks:

| Book | Text layer |
|---|---|
| `Full Thrust.pdf` | image-only scan, Tesseract OCR added as an invisible layer over the untouched pages |
| `More Thrust.pdf` | native text, fake-bold overprints hidden |
| `Fleet Book 1.pdf` | native text, overprints hidden |
| `Fleet Book 2.pdf` | native text, overprints hidden |

Bookmarks follow each book's contents page; the Fleet Books also have one bookmark per ship
class under each fleet's "Ship Designs" entry.

The pipeline that produces them is in `tools/` (`build_rulebooks.py`, with bookmark lists in
`tocs.py` and the overprint fix in `dedup_text.py`). It needs PyMuPDF, pypdf and Tesseract, and
reads the original PDFs from a local folder you set in the script.

## Credits

*Full Thrust*, *More Thrust* and the Fleet Books, their rules text, ship designs and diagrams
are © Jon Tuffley and Ground Zero Games. This is an unofficial fan project, not affiliated with
or endorsed by Ground Zero Games. Licensed GPL-3.0; see [NOTICE.md](NOTICE.md).
