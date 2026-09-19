# Full Thrust Fleet Manager — agent operating manual

Read this before working on this project. It is the single source of truth for **how work is
done** here; `docs/PLAN.md` is the single source of truth for **what is built** (decisions,
data model, rules, UI, milestones). Read the relevant PLAN section before starting a milestone.

A local Flask app (no login, no server, plain-file JSON storage) for designing Full Thrust
ships, building fleets, tracking campaign damage, and printing a fleet PDF for the table. Same
code also runs in the browser via Pyodide on GitHub Pages.

## Maintaining this file

Update it in the same commit as any change that makes it wrong, or that adds a pattern or
gotcha a future session would re-derive. **Current state only**, not a changelog. Edit affected
lines in place; delete anything that stops being true. When a milestone lands, move its
"planned" notes below into real descriptions of the code.

## Current state

M1 (Scaffold) is done: an empty Layout C shell that runs on desktop and is ready for the web
build. No rules engine, storage or fleets yet; next is **M2** (ruleset framework + FB engine).

What exists:
- `app.py` — Flask app: tabs `/fleet` (home, `/` redirects), `/design`, `/campaign`,
  `/settings`; `/heartbeat` routes; `_reject_cross_site()` guard; `register_action` /
  `dispatch_action` (no update routes use them yet, they arrive with the store in M5); `main()`
  runs Werkzeug in dev, waitress + tray + idle watchdog when frozen.
- `templates/base.html` — Layout C top bar (brand, fleet selector, tabs, points meter, Print
  button, ruleset colour strip), flashes, `<main class="work cols-N">` grid. One template per
  tab plus `error.html`; tab bodies are placeholders.
- `static/style.css` — the mockup's visual language, status and ruleset accent colours as CSS
  variables, panes stack below 1100 px. System font stack, no web fonts.
- `i18n.py` + `translations/en.json` — see Translation below.
- `paths.py`, `tray.py`, `idle_watchdog.py`, `run_app.py`, `fleetmanager.spec` — copied from
  Frostgrave and adapted (env prefix `FTFM_`).
- `scripts/build_browser_bundle.py` → `web/bundle.json` (gitignored), `web/index.html` (the
  Pyodide shell).
- `rulesets/__init__.py` — empty `RULESETS` registry placeholder for M2.
- `.github/workflows/tests.yml` (ruff + full pytest on push/PR), `deploy-pages.yml` (manual).
- Also: `docs/PLAN.md`, `docs/mockups/` (serve with
  `python -m http.server 8765 --directory docs/mockups`), `rulebooks/` and the `tools/` that
  rebuild them from `E:\RPG\Tabletop\Full Thurst\`.

Modules of PLAN section 4 not listed here (`fleet_rules.py`, `store.py`, `migrations.py`,
`ssd_layout.py`, `pdf_export.py`, `data/`) are created by the milestone that needs them.

## Non-negotiable principles

Full list in PLAN section 2. The ones most likely to be broken by accident:

- **Desktop works fully offline.** No CDN links in templates, no network calls. Vendor all JS,
  CSS and fonts under `static/`.
- **Points and MASS come only from the rules engine.** Never hand-editable, never computed in
  routes or templates.
- **Non-conformance is computed from violations**, never from the `allow_rule_breaking`
  checkbox. The checkbox only permits saving a violating design.
- **The ruleset is visible everywhere** a fleet or design appears, including every PDF page.
- **Quick-reference text uses the original rulebook wording** (trimmed where needlessly wordy)
  with page references. This is a deliberate owner decision (PLAN 2.5); do not paraphrase it.
- **Every user-facing string goes through `_()`** (UI and PDF), even though only English exists.
- **Catalog designs are read-only.** Editing one creates a variant.

## Architecture (PLAN section 4; layers 1-3 arrive in M2-M5)

Four layers, strictly ordered — each may import only from layers above it:

1. **`rulesets/<id>/`** — per-ruleset data and pure rules (costing, validation, damage track,
   icon set, quick reference) behind the `Ruleset` protocol in `rulesets/__init__.py`.
   v1: `fb` and `ft2` (+ `ft2/mt.py` for the More Thrust toggles).
2. **`fleet_rules.py`** — pure fleet logic: totals incl. loadouts, conformance, badges,
   tournament check, campaign maths. Never branches on a ruleset id; calls the protocol.
3. **`store.py`** — persistence and every mutation, returning `(ok: bool, msg: str)`.
4. **`app.py`** — Flask routes, thin. State-changing forms use the `@register_action` dispatch
   pattern copied from Frostgrave.

Pure consumers: `ssd_layout.py` (design → drawing primitives) and `pdf_export.py` (primitives →
PDF via fpdf2). The browser renders the same primitives as SVG: screen = paper.

## Sister project

`E:\ClaudeCodeFolder\FrostgraveWarbandKeeper` uses the same stack. Copy and adapt (never import)
its infrastructure: `paths.py`, `tray.py`, `idle_watchdog.py`, `run_app.py`, the PyInstaller spec,
`scripts/build_browser_bundle.py`, the Pyodide shell, `.github/workflows/deploy-pages.yml`. Read
its `CLAUDE.md` for the reasoning behind those pieces before copying them.

## Translation

`from i18n import _` in Python, `{{ _("...") }}` in Jinja (registered as a global). Params go in
as keywords and are formatted after lookup: `_("{n} ships", n=3)`. Missing keys fall back to the
source string. `translations/en.json` is an identity map of every source string, and
`tests/test_i18n.py` fails on any `_("literal")` missing from it **and** on stale entries, so
add or remove the en.json line with the string. Only literals are found: never pass a variable
to `_()` for a string that is not in en.json. Game terms (MASS, NPV, Thrust) stay as the books
spell them. The one exception is `web/index.html`'s loading screen, which runs before Python.

## Offline and the web build

- `tests/test_shell.py` fails on any `http(s)://` or `//host` URL in `templates/` or `static/`.
  The web shell loads Pyodide from jsdelivr; that is allowed (PLAN 1) and it is outside those
  folders.
- The web build runs the real app through Flask's test client in an iframe `srcdoc`, so
  absolute `/static/...` URLs don't resolve there: `web/index.html`'s `renderPage()` inlines
  every `static/*.css` / `*.js` by file name. Only text passes through `bundle.json`; binary
  assets and the rulebooks are copied next to `index.html` by `deploy-pages.yml`.
- `build_browser_bundle.py` globs modules, templates, `data/`, `translations/` and static text
  files; `fleetmanager.spec` adds whole folders. Neither keeps a hand list (Frostgrave's drifted
  and shipped broken). New top-level desktop-only modules go in `EXCLUDED_MODULES`.
- The shell stamps a content hash into its `bundle.json?v=` URL on each build; commit it with
  the `__BUNDLE_VERSION__` placeholder, not a hash.
- `FTFM_BROWSER=1` turns off the local-host guard (no network hop in the page).

## Running locally

`.venv` (Python 3.14 here; CI uses 3.12): `pip install -r requirements-dev.txt`.

`paths.user_data_dir()` is `FTFM_DATA_DIR` if set, else `userdata/` (gitignored) when running
from source, `%APPDATA%\FullThrustFleetManager` when frozen. For a scratch server set
`FTFM_DATA_DIR` to a temp dir and `PORT` to something other than 5000 (the owner may run a real
instance there); stop it by PID from the port, never by process name. The session preview config
`ftfm-dev-scratch` (in `E:\ClaudeCodeFolder\.claude\launch.json`, outside the repo) does this
on port 5123. Reach the server as `127.0.0.1`/`localhost`; other Host headers get 403.
`FTFM_DEBUG=1` enables the Werkzeug debugger.

## Rules sources

`rulebooks/` holds the processed PDFs. Page numbers in code, data and PLAN are **printed** page
numbers. PDF page = printed + 1 for `Full Thrust.pdf`, = printed for the others. The FT2 book's
text layer is OCR: verify numbers against the page image (`page.get_pixmap(dpi=200)`).

## Git and GitHub

- Work on `devversion`; `main` is for releases only. Never push to `main` without the owner.
- Commit per coherent step; each milestone issue is closed by the commit/PR that completes it.
- Commit messages end with the attribution line the harness provides.

## Testing

- Rules engines are built **test-first**, golden tests from PLAN 6.2/6.3 first.
- `tests/test_catalog_gate.py` must stay green: every catalog ship's recomputed points equal its
  printed NPV, or it is listed in `data/errata.json` with a real reason.
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

## Asking the owner

PLAN.md records settled decisions. If a decision there turns out to be impossible or clearly
wrong, stop and ask instead of re-deciding. Facts (costs, page contents, file layouts) are looked
up, not asked.
