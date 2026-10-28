# Full Thrust Fleet Manager — agent operating manual

Read this before working on this project. It is the single source of truth for **how work is
done** here; `docs/PLAN.md` is the single source of truth for **what is built** (decisions,
data model, rules, UI, milestones). Read the relevant PLAN section before starting work.

A local Flask app (no login, no server, plain-file JSON storage) for designing Full Thrust
ships, building fleets, tracking campaign damage, and printing a fleet PDF for the table. Same
code also runs in the browser via Pyodide on GitHub Pages. Rulesets: FB (Fleet Books 1 and 2
with the FB2 races), FT2 + More Thrust, FTCD (Cross Dimensions) and FTPC (Project Continuum).

## Where the detail lives

Topic notes sit next to their code (nested `CLAUDE.md`, loaded automatically when you work
there) or in `docs/` (read the file **before** changing that area).

| Area | File |
|---|---|
| Ruleset protocol, races, `common.py` | `rulesets/CLAUDE.md` |
| FB / FT2 / FTCD / FTPC specifics | `rulesets/<id>/CLAUDE.md` |
| Catalog, quick-reference extraction, NPV gate | `tools/CLAUDE.md` |
| Ship diagram (`ssd_layout.py`) | `docs/ssd-layout.md` |
| Fleet PDF (`pdf_export.py`) | `docs/pdf-export.md` |
| Campaign tab, star map, forces, contacts | `docs/campaign.md` |
| Storage, import/export, migrations, factions | `docs/storage.md` |
| Ship Design / Fleet tabs, rulebook viewer, looks, tablets and phones | `docs/ui-tabs.md` |
| Web (Pyodide/Pages) and desktop builds | `docs/builds.md` |
| Ship portraits and theme art | `docs/SHIP-ARTWORK.md` |
| Releasing | `.claude/skills/shipping-a-release/SKILL.md` (only when shipping) |

## Maintaining this file

Update it (or the topic file above) in the same commit as any change that makes it wrong, or
that adds a pattern or gotcha a future session would re-derive. **Current state only**, not a
changelog: no release notes, version histories or "M9 done" lines; git has those. Edit affected
lines in place; delete anything that stops being true. Keep this root file to cross-cutting
rules; topic detail goes in the matching nested `CLAUDE.md` or `docs/` file, with a row in the
table above. `AGENTS.md` points Codex here and adds only the Codex/Claude PR workflow; keep it
short.

## Non-negotiable principles

Full list in PLAN section 2. The ones most likely to be broken by accident:

- **Desktop works fully offline.** No CDN links in templates, no network calls. Vendor all JS,
  CSS and fonts under `static/`. `tests/test_shell.py` fails on any `http(s)://` or `//host` URL
  in `templates/` or `static/` (the web shell's Pyodide from jsdelivr is allowed, PLAN 1).
- **Points and MASS come only from the rules engine.** Never hand-editable, never computed in
  routes or templates.
- **Non-conformance is computed from violations**, never from the `allow_rule_breaking`
  checkbox. The checkbox only permits saving a violating design.
- **The ruleset is visible everywhere** a fleet or design appears, including every PDF page.
- **Quick-reference text uses the original rulebook wording** (trimmed where needlessly wordy)
  with page references. Deliberate owner decision (PLAN 2.5); do not paraphrase it.
- **Every user-facing string goes through `_()`** (UI and PDF), even though only English exists.
- **Catalog designs are read-only.** Editing one creates a variant. Catalog JSON is generated.
- **Normalisation is the trust boundary**: every new design/fleet field is added to
  `store.normalize_design()` / `normalize_fleet()` in the same commit.
- **Screen = paper**: the app's SVG and the PDF draw the same `ssd_layout` primitives.
- Owner rulings in the topic files (marked "Master", "owner's ruling") are settled; do not
  "fix" them.

## Architecture (PLAN section 4)

Four layers, strictly ordered; each may import only from layers above it:

1. **`rulesets/<id>/`** — per-ruleset data and pure rules (costing, validation, damage track,
   icon set, quick reference) behind the `Ruleset` protocol in `rulesets/__init__.py`: `fb`,
   `ft2` (+ `ft2/mt.py`), `ftcd`, `ftpc`; shared pieces in `common.py` and `fleet_common.py`.
2. **`fleet_rules.py`** — pure fleet logic: totals incl. loadouts, conformance, badges,
   tournament check, campaign maths. Never branches on a ruleset id; calls the protocol.
3. **`store.py`** — persistence and every mutation, returning `(ok: bool, msg: str)`.
4. **`app.py`** — Flask routes, thin. State-changing forms use the `@register_action` /
   `dispatch_action` pattern copied from Frostgrave; the route saves iff ok.

Pure consumers: `ssd_layout.py` (design -> drawing primitives) and `pdf_export.py` (primitives
-> PDF via fpdf2). Pure campaign helpers: `starmap.py`, `scenarios.py`, `forcegen.py`,
`events.py`.

Other files: tabs `/fleet` (home), `/design`, `/campaign`, `/settings`; one template per tab in
`templates/` around `base.html`. `static/style.css` (looks as CSS-variable blocks),
`static/artwork.css` + `portraits.py` + `data/ship_art.json` (portraits), `static/fonts/` (IBM
Plex TTFs with OFL, also used by the PDF). `data/catalog/`, `data/quickref/`, `data/errata.json`
(book values that disagree with the rules, with the reason, PLAN 8), `data/factions.json`.
`paths.py`, `tray.py`, `idle_watchdog.py`, `run_app.py` and the specs come from Frostgrave (env
prefix `FTFM_`). `app.main()` runs Werkzeug in dev, waitress + tray + idle watchdog when frozen;
`_reject_cross_site()` guards forms. `docs/mockups/` (serve with
`python -m http.server 8765 --directory docs/mockups`). `rulebooks/` holds the processed PDFs,
rebuilt by `tools/build_rulebooks.py` from the bought originals.

## Translation

`from i18n import _` in Python, `{{ _("...") }}` in Jinja (registered as a global). Params go in
as keywords and are formatted after lookup: `_("{n} ships", n=3)`. Missing keys fall back to the
source string. `translations/en.json` is an identity map of every source string, and
`tests/test_i18n.py` fails on any `_("literal")` missing from it **and** on stale entries, so
add or remove the en.json line with the string. Only literals are found: never pass a variable
to `_()` for a string that is not in en.json. Game terms (MASS, NPV, Thrust) stay as the books
spell them. The one exception is `web/index.html`'s loading screen, which runs before Python.

## Rules sources

Page numbers in code, data and PLAN are **printed** page numbers. PDF page = printed + 1 for
`Full Thrust.pdf` and `Full Thrust Cross Dimensions.pdf`, = printed for the others. The FT2
book's text layer is OCR: verify numbers against the page image (`page.get_pixmap(dpi=200)`).

- A ruleset's `books` are its **rules sources**: what a `book_url()` link points into and what
  the quick reference quotes. Books shipped only to be read go in `REFERENCE_BOOKS`
  (`rulesets/__init__.py`), so a code can never resolve a page reference into a book whose rules
  nothing implements. It holds Full Thrust Light (`FTL`, GZG's free 2008 intro game, shipped
  unchanged; Master: no FTL mechanics in the app). CD and PC (errata `PCE`) are free
  non-commercial publications distributed with GZG's agreement, credited in `NOTICE.md`.
  `app.books()` merges the two, rulesets winning a clash.
- A new PDF needs no spec or workflow change (both take the whole `rulebooks/` folder). Verify
  its `page_offset` against a printed folio rather than assuming 0; `tests/test_rulebooks.py`
  checks the reference books' against pages 20 and 30.

## Running locally

`.venv` (Python 3.14 here; CI uses 3.12): `pip install -r requirements-dev.txt`.

`paths.user_data_dir()` is `FTFM_DATA_DIR` if set, else `userdata/` (gitignored) when running
from source, `%APPDATA%\FullThrustFleetManager` when frozen. For a scratch server set
`FTFM_DATA_DIR` to a temp dir and `PORT` to something other than 5000 (the owner may run a real
instance there); stop it by PID from the port, never by process name. The session preview config
`ftfm-dev-scratch` (in the parent folder's `.claude/launch.json`, outside the repo) does this on
port 5123. Reach the server as `127.0.0.1`/`localhost`; other Host headers get 403.
`FTFM_DEBUG=1` enables the Werkzeug debugger. `Start-Dev-Version.bat` is the owner's
double-click launcher: it runs `app.py` on `PORT` (default 5000) and opens the browser unless
`FTFM_NO_BROWSER` is set.

## Git and GitHub

- Work on `devversion`. **It is the only branch with source.** `main` carries just `README.md`,
  `LICENSE`, `NOTICE.md`, `.gitignore` and `.github/workflows/`, because GitHub only offers a
  `workflow_dispatch` workflow that exists on the default branch, and `main` is the default
  branch. Releases are tagged on `devversion`; nothing is merged into `main`. Never push to
  `main` without the owner.
- Because nothing is merged into `main`, a change under `.github/workflows/` has to be copied to
  `main` deliberately, or the dispatchable copy goes stale. The checkout step takes its `ref` as
  an input defaulting to `devversion`, so a stale copy runs against good source and simply skips
  whatever steps it is missing.
- CI: `.github/workflows/tests.yml` (ruff + full pytest, and a web-build boot check, on
  push/PR); `deploy-pages.yml` and `build-linux.yml` are manual. `.githooks/pre-push` runs
  `ruff check .` before every push; `.claude/settings.json` enables it
  (`git config core.hooksPath .githooks`) when a session starts. Before pushing a PR branch,
  also run the tests for what you changed.
- Commit per coherent step; commit messages end with the attribution line the harness provides.
- **A PR is not left waiting unwatched.** Master's standing rule is to merge once CI is green, so
  the session that opened a PR drives it to merged:
  - Whenever the turn ends with CI pending, make sure something will bring you back (the app's
    PR monitor/Auto-fix, or a scheduled check-in): a lost event must not stall the thread.
  - A job that failed before any test ran (checkout, `pip install`, `playwright install`, runner
    lost, a network error) is infrastructure: re-run the failed jobs once without asking. A
    second identical failure, or any failing test or lint, is real: fix it and push.
  - Green: merge `devversion` in if it moved, wait for that run, merge. Then say so.
  - Still stuck after two check-ins with no change: tell Master what it waits on, once.
- **Shipping** has its own procedure in `.claude/skills/shipping-a-release/SKILL.md`; read it
  only when shipping. Two things in it are easy to get wrong from memory: deploy Pages **last**,
  after the zip is attached, or the Windows badge stamps the previous version; and dispatch the
  workflow with `--ref devversion` as well as `-f ref=devversion`, or GitHub runs `main`'s copy.

## Testing

- Rules engines are built **test-first**, golden tests from PLAN 6.2/6.3 first.
- `tests/test_catalog_gate.py` must stay green (see `tools/CLAUDE.md`).
- **Routine work: run only the tests for what you changed.** Full suite before a release and in
  CI. Do not run the whole suite as routine verification.
- Lint with ruff (`ruff check .`, config in `pyproject.toml`). The three rulebook pipeline files
  in `tools/` are excluded: they predate the app and are run by hand. Pass only `.py` files.
- `tests/conftest.py` sets `FTFM_DATA_DIR` to a temp dir before anything imports `app`; the
  `client` fixture is a Flask test client.

```bash
.venv/Scripts/python.exe -m pytest tests/test_<thing>.py -q
.venv/Scripts/python.exe -m ruff check <files.py>
```

## Sister project and asking the owner

The `FrostgraveWarbandKeeper` checkout beside this one uses the same stack. Copy and adapt
(never import) its infrastructure: `paths.py`, `tray.py`, `idle_watchdog.py`, `run_app.py`, the
PyInstaller spec, `scripts/build_browser_bundle.py`, the Pyodide shell,
`.github/workflows/deploy-pages.yml`. Read its `CLAUDE.md` for the reasoning before copying.

PLAN.md records settled decisions. If a decision there turns out to be impossible or clearly
wrong, stop and ask instead of re-deciding. Facts (costs, page contents, file layouts) are
looked up, not asked.
