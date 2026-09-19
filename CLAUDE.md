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

Nothing of the app exists yet. The repo holds:
- `docs/PLAN.md` — the build plan (milestones M1-M14 are GitHub issues labelled `milestone`)
- `docs/mockups/` — UI mockups (Layout C is the chosen UI) and the print mockup;
  serve with `python -m http.server 8765 --directory docs/mockups`
- `rulebooks/` — processed rulebook PDFs (text layer + bookmarks), bundled with the app
- `tools/build_rulebooks.py` (+ `tocs.py`, `dedup_text.py`) — rebuilds `rulebooks/` from the
  original PDFs in `E:\RPG\Tabletop\Full Thurst\`

Start with **M1 (Scaffold)**.

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

## Architecture (planned, PLAN section 4)

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
- Lint with ruff.

## Asking the owner

PLAN.md records settled decisions. If a decision there turns out to be impossible or clearly
wrong, stop and ask instead of re-deciding. Facts (costs, page contents, file layouts) are looked
up, not asked.
