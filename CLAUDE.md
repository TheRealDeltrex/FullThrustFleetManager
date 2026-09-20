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

M1-M11 are done: the whole v1 feature set — the Layout C shell, the FB and FT2 (+ More Thrust)
rules engines, the 96-design catalog behind the NPV gate, the storage layer, the SSD layout
engine, the Design, Fleet overview, Campaign and Settings tabs, the fleet PDF and the rulebook
viewer. What remains is packaging: **M12** (desktop exe), **M13** (web build) and M14 (release,
the owner's).

What exists:
- `app.py` — Flask app: tabs `/fleet` (home, `/` redirects), `/design`, `/campaign`,
  `/settings`; `/heartbeat` routes; `_reject_cross_site()` guard; `register_action` /
  `dispatch_action` (no update routes use them yet, they arrive with the store in M5); `main()`
  runs Werkzeug in dev, waitress + tray + idle watchdog when frozen.
- `templates/base.html` — Layout C top bar (brand, fleet selector, tabs, points meter, Print
  button, ruleset colour strip), flashes, `<main class="work cols-N">` grid. One template per
  tab plus `error.html`; tab bodies are placeholders.
- `static/style.css` — the mockup's visual language, status and ruleset accent colours as CSS
  variables, panes stack below 1100 px.
- `static/fonts/` — IBM Plex Sans (owner's choice) Regular, Italic, SemiBold, Bold as TTF from the
  IBM/plex 1.1.0 release, with its OFL licence. The same files are for the PDF (M9). The web
  shell rewrites `url("fonts/` to `url("static/fonts/` when it inlines the CSS; keep that exact
  spelling in `@font-face`.
- `i18n.py` + `translations/en.json` — see Translation below.
- `paths.py`, `tray.py`, `idle_watchdog.py`, `run_app.py`, `fleetmanager.spec` — copied from
  Frostgrave and adapted (env prefix `FTFM_`).
- `scripts/build_browser_bundle.py` → `web/bundle.json` (gitignored), `web/index.html` (the
  Pyodide shell).
- `rulesets/` — the `Ruleset` protocol, registry, FB and FT2 engines; see Rulesets below.
- `data/catalog/` — the read-only catalog; see Catalog below. `data/errata.json` — book values
  that disagree with the rules, with the reason (PLAN 8).
- `.github/workflows/tests.yml` (ruff + full pytest on push/PR), `deploy-pages.yml` (manual).
- Also: `docs/PLAN.md`, `docs/mockups/` (serve with
  `python -m http.server 8765 --directory docs/mockups`), `rulebooks/` and the `tools/` that
  rebuild them from the bought originals (source folder set in `tools/build_rulebooks.py`).

- `fleet_rules.py`, `store.py`, `migrations.py`, `data/factions.json` — see Storage below.

- `ssd_layout.py` — the record sheet; see Ship diagram below.
- The Design tab (`/design`, `/design/<id>`) — see Design tab below.

## Design tab

- Routes: `GET /design` (library, no selection), `GET /design/<id>` (workbench),
  `POST /design/new`, `POST /design/<id>` with an `action` field. Catalog ids contain `:` and
  travel in the path unescaped, which Flask handles.
- **Edits go to a draft, not the library.** Strict mode refuses to save a violating design, so
  the workbench has to hold changes that are not saveable yet: `store.save_draft()` /
  `get_draft()` / `discard_draft()` under `drafts/`, and `working_design(id)` returns
  `(design, dirty)`. Saving, refitting, saving as a variant and deleting all clear the draft.
- The whole design posts with every action (`_apply_form`), so an edit is never lost by
  clicking Add system. Per-system inputs are named `sys-<uid>-<param>`; arcs are checkboxes
  plus a hidden `sys-<uid>-arcs-present` marker, because an all-unchecked arc set posts nothing.
  Remove buttons carry the uid in their `formaction` query, so the table needs no script.
- Actions: `apply` (recalculate), `add_system`, `remove_system`, `save` / `refit` / `variant`
  (`store.save_design` modes), `discard`, `delete`, `make_variant`. Everything but
  `make_variant` is refused on a catalog design.
- The right pane is computed per request in `_design_context()`: breakdown, MASS bar against
  `derived["mass_limit"]`, NPV against the book value for catalog designs, issue list, and the
  live SSD as inline SVG (`Markup`, from `ssd_layout`).
- `tests/test_design_tab.py` uses the `client` fixture with a per-test `FTFM_DATA_DIR`.

## Fleet overview tab

- Routes: `GET /fleet` (the current fleet, `?view=cards|sheet|roster`), `GET /fleet/<id>`
  (select and redirect), `POST /fleet/new`, `POST /fleet/<id>/action`, `GET /fleet/<id>/check`
  (the tournament check of PLAN 7, which blocks nothing).
- **The current fleet lives in the Flask session** (`session["fleet_id"]`, falling back to the
  first fleet). `_inject_current_fleet()` is a context processor, so the top bar's selector,
  points meter, ruleset strip and non-conforming chip work on every tab.
- Fleet mutations go through `@register_action` handlers and `dispatch_action(fleet)`: the
  handler mutates the fleet dict via `store`, the route saves iff ok. That is the pattern for
  every state-changing form from here on. `delete_fleet` is handled before dispatch because it
  has no fleet left to save.
- Views: cards per squadron (mini SSD with the ship's damage, status and squadron selectors),
  record sheets (docked, hulk and destroyed ships are listed but not drawn, PLAN 10.2) and the
  roster table. All three use the same `ssd_layout` diagrams the PDF will.
- `tests/test_fleet_tab.py` covers the routes, the views, every badge row and the check page.

## Fleet PDF (`pdf_export.py`)

- `fleet_pdf(fleets, designs_by_fleet, options) -> bytes`, with `PrintOptions` mirroring the
  print dialog (PLAN 10.3). One fleet is a fleet pack; two are a battle pack (both rosters,
  sheets and trackers, an orders chart each, one shared quick reference).
  `battle_pack_error()` rejects two rulesets; `/print` GET is the dialog, POST returns the PDF.
- `draw_diagram()` renders the **same `ssd_layout` primitives** the screen does, so screen =
  paper. Two fpdf2 traps: `circle()` takes the centre and the radius (its docstring says
  bounding box) and a filled path needs colour strings, not tuples. Arc rings are sampled into
  polylines in `ssd_layout`, so both renderers draw the identical points.
- Fonts are the bundled IBM Plex TTFs; no system font is used. Output is black and white.
- Quick reference: `data/quickref/<ruleset>.json`, generated by `tools/extract_quickref.py`
  from the rulebooks (heading table inside the tool; re-run after editing it). The text is the
  book's own wording with a **printed** page reference, which PLAN 2.5 requires: **never
  paraphrase it by hand.** FT and MT are OCR over two-column pages, so extraction picks up
  figure captions, spec panels and half sentences:  repairs hyphenation and stray page
  numbers, and  in the tool holds entries transcribed from the page image where the
  layout defeats it.  guards both the text and the page numbers. `Ruleset.quickref()` filters it to the systems present plus a few always-on
  entries, the fleet's optional rules and the races in the fleet. Race entries are key-prefixed
  (`kv_kgun`), so a mixed fleet still gets the FB1 entry for its human designs. **FB2 repeats
  FB1's headings once per race** and `body_after()` keeps the longest body wherever it is, so a
  Kra'Vak key can silently resolve to the Phalon section: pin such an entry to its printed pages
  in the tool's `PAGES` map, and check the page reference against the page image.
- `tests/test_pdf_export.py` reads the generated pages back with pymupdf. Render pages to PNG
  for a visual check when the layout changes.

## Campaign tab

- `GET /campaign` (the current fleet), `POST /campaign/<id>/action`, `GET /dice/6`.
- Campaign maths is pure and lives in `fleet_rules`: `hull_boxes`, `crew_factors_left`,
  `ship_is_crippled`, `repairable_systems`, `repair_plan` (FT p.35: 1D6 hull a week at a base,
  up to three systems on 3+, a disabled drive needs two successes). `store` applies it:
  `set_ship_damage` (clamped to what the design has), `toggle_system_out`, `repair_ship`,
  `replenish_ship` (fighters, salvos and one-shot systems in one week).
- **Clicking the diagram**: every primitive carries a `ref` (`hull:7`, `armour:2`,
  `system:s3`), `to_svg()` emits it as `data-ref`, and `static/campaign.js` posts the ref of the
  shape that was clicked. Clicking the last marked box unmarks it. The fields under the diagram
  do the same thing, so the tab works with scripting off; the dice buttons are optional too.
- Hooks reserved for the later campaign module (PLAN 11.2) are in use but not repurposed:
  `ship.location`, `log[].week`, statuses `docked` and `hulk`, `fleet.campaign_id` (unused).

## Rulebook viewer

- `GET /rulebook/<code>?page=N` (the viewer page) and `/rulebook/<code>/file` (the bundled PDF).
  `book_url()` is a Jinja global, so every "FB1 p.16" in the UI is a link; page numbers are
  **printed** ones and the route adds the book's `page_offset`.
- pdf.js 4.6.82 (legacy build) is vendored under `static/pdfjs/`, Apache-2.0, licence
  alongside. Trimmed: no source maps, no locale, no cmaps, no debugger. It is excluded from the
  web bundle (served as plain files) and from `test_shell.py`'s remote-URL scan, because it is
  third-party code with URLs in comments that fetches nothing at runtime.
- The viewer is framed, so the security headers are `X-Frame-Options: SAMEORIGIN` and
  `frame-ancestors 'self'` — do not tighten them back to DENY without replacing the frame.
- The Settings tab writes `pdf_viewer` (`app` / `system`) and `paper`; with `system`, a page
  reference redirects to the file itself so the browser or the OS opens it.

`pdf_export.py` (PLAN section 4) arrives with M9.

## Ship diagram (`ssd_layout.py`)

- `layout(design, ruleset=None, damage=None, loadout=None, box="auto") -> Diagram(width, height,
  primitives)`. Pure. Primitives are frozen dataclasses (`Rect`, `Circle`, `Line`, `Path`,
  `Text`) in points with a top-left origin, so the screen and the paper use the same numbers:
  `to_svg()` renders them for the app, `pdf_export` (M9) renders the same tuple with fpdf2.
- Placement is arc-aware: `_side()` sorts each weapon into fore / port / starboard / aft /
  centre from its arcs, bigger classes first (`_weight`), then fore rows across the top, the
  side columns flanking a central block of all-round systems, aft weapons under it, the armour
  circles and damage track (stars on the crew-factor boxes), and a bottom row with FTL, the
  drive lozenge with its thrust, the FB core-systems box and any holds or tug drives.
  `layout_hints[uid] = {"x": .., "y": ..}` pins a system; drag-to-arrange can write them later.
- Damage: a slash through each spent hull box and armour circle, a cross over dead systems and
  a damaged drive; black on paper. `damage=None` is a blank copy.
- Icons live in `ICON_SETS[<icon_set>]`, keyed by system type; a ruleset names its set per race
  (`icon_set_for(race)` -> `"fb"` / `"ft2"` / `"fb_kravak"`, falling back to the `icon_set`
  attribute) rather than drawing itself, because drawing is a consumer's job. A set may also
  supply `"main_drive"` and draw the drive itself, as `fb_kravak` does for the Advanced Grav
  Drive that FB2 p.9 says looks different and is written "4A".
  An unknown type falls back to a labelled box, so a new system never breaks a sheet. Boxed
  abbreviations take a callable so the label is translated at draw time.
- `box_size()` gives the sheet width band (small/medium/large/xlarge) the packed PDF sorts by.
- `tests/test_ssd_layout.py` covers placement, damage and the size bands, asserts every catalog
  design draws inside its own box, and holds SVG snapshots of 3 reference ships per ruleset in
  `tests/snapshots/`. Regenerate them with
  `.venv/Scripts/python.exe tests/test_ssd_layout.py --update` and read the diff: a changed
  snapshot means every record sheet changed.

## Storage (layers 2-3)

- `fleet_rules.py` (pure): `fleet_options()`, `design_points()` / `ship_points()` (NPV plus the
  ship's loadout, its own or the design default) / `fleet_points()` (skips destroyed ships),
  `design_issues()`, `fleet_report()` (the tournament check: fleet issues + a `ShipReport` each),
  `badges()` (`non_conforming`, `mixed_faction`, `custom_ships`), `ship_counts()`. Conformance is
  "no violation": campaign damage, ship status and `allow_rule_breaking` never enter into it. A
  ship also violates on `missing_design`, `wrong_ruleset`, `race_mixing`, `mt_toggle_off`; a
  fleet on `over_points` (a limit of 0 means no limit).
- `store.py`: everything that touches disk, plus every mutation. Mutators take the fleet dict,
  change it in place and return `(ok, msg)`; the route saves iff ok. `save_design(design, mode)`
  is the refit-or-variant decision: `save` refuses when ships use the design, `refit` rewrites
  it under them, `variant` writes a new id. Catalog designs are never written: their ids contain
  `:` so `_safe_id()` rejects them as file names too. Strict mode blocks saving a design with
  violations unless `allow_rule_breaking` — note a blank `new_design()` is under its TMF, so
  tests that save one set that flag.
- **Normalisation is the trust boundary.** Everything read from the library or an import goes
  through `normalize_design()` / `normalize_fleet()`, which clamp types and drop junk and are the
  only place new fields are accepted. Add every new field there in the same commit.
- Export/import (PLAN 5.6): `.FTFleet` (fleet + its non-catalog designs + custom factions),
  `.FTDesign`, `.FTBackup` (a zip of the library). `import_file()` returns
  `(ok, msg, conflicts)`; a *newer local copy* is kept and named in `conflicts`, and the caller
  re-calls with `overwrite_newer=True` after the player confirms. `modified` is an ISO string at
  second resolution, so tests that need "strictly newer" backdate the local copy.
- `migrations.py`: `CURRENT`, `STEPS[kind][from_version]`, `upgrade()`. A missing or malformed
  `schema_version` counts as 1; anything above `CURRENT` raises `TooNewError` and is refused
  rather than guessed at. Write the step and its test in the commit that bumps `CURRENT`.
- `data/factions.json` holds the built-in factions per ruleset; custom factions live in the
  user library and travel with exports.

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

## Architecture (PLAN section 4; layer 1 exists, layers 2-3 arrive with M5-M8)

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

## Rulesets

- `rulesets/__init__.py`: dataclasses (`BookRef`, `Race`, `ParamDef`, `SystemDef`,
  `BreakdownRow`, `Breakdown`, `Issue`, `QuickRefEntry`), the `Ruleset` protocol, `RULESETS`,
  `register()`, `get_ruleset()`. Rulesets register at the bottom of that file (they import the
  dataclasses, so the import has to come last).
- The protocol is PLAN 6.1 plus: `arcs` (the ruleset's arc names), `loadout_points()` (fleet
  totals include loadouts, PLAN 5.4), `fighter_types(options, race)` (loadout editor),
  `required_options(design, loadout)` (the MT toggles a design needs), `icon_set_for(race)` and
  `quickref(systems_present, options, races)`. `loadout=None` means the design's default loadout.
- **Races are additive modules inside a ruleset, never new rulesets** (PLAN 3 decision 3). A tech
  module is a plain module exposing the per-design half of the protocol (`system_defs()`,
  `design_breakdown`, `validate_design`, `loadout_points`, `damage_track`, `crew_factors`,
  `cf_positions`, `threshold_numbers`, `suggest_type`, `ICON_SET`, `FIGHTER_POINTS`);
  `rulesets/fb/tech.py` maps race id -> module and `FBRuleset` dispatches every per-design call
  on `design["race"]`. An unknown race falls back to human rather than raising. Adding a race is:
  write the module, add it to `_TECH`, add its icon set to `ssd_layout`, add its catalog
  extractor and its quick-reference rows. Nothing above the ruleset layer knows races exist
  beyond passing one along.
- `design_breakdown().derived["mass_limit"]` is the MASS budget for the UI bar: FB must use
  exactly TMF, FT2 at most the system capacity (hull and drives take no MASS in FT2).
- `validate_design(design, options)` also flags More Thrust content whose fleet toggle is off in
  `options` (`mt_toggle_off`, `mass_over_100`), so fleet conformance is just validation with the
  fleet's options.
- `rulesets/common.py`: integer rounding (`round_half_up`, `pct_mass`: .5 up, never 0 MASS),
  arcs (`ARCS`, `arcs_valid`, `arcs_contiguous`), `split_rows`, `cf_positions`. Never compute
  percentages with floats: 85 x 30% must be 25.5 exactly to round to 26.
- `rulesets/fb/`: `data.py` (books, `system_defs()` for the picker, fighter points, FB1 p.12
  classes, hull descriptors), `rules.py` (human tech: `SYSTEM_RULES` type -> (mass, points,
  label), breakdown, validation, derived values), `kravak.py` (Kra'Vak tech, FB2 pp.9-11),
  `tech.py` (the race -> module table), `__init__.py` (`RULESET`).
- Kra'Vak tech (`kravak.py`): hull, damage track, crew factors, thresholds, holds and tender bays
  are the human rules, which FB2 p.9 says outright, so they are imported from `rules.py` rather
  than restated. What differs: the Advanced Grav Drive costs 3 points per MASS (FB2 p.9, and it
  is the one rule that makes the race); `kgun` {class, arcs} on the FB2 p.9 MASS table (class 1
  all six arcs, class 2 one or two adjacent, class 3+ exactly one, +3 MASS per class above 6) at
  4 points per MASS; one-shot `mkp` {arcs, one} at 1/4 and `scattergun` at 1/5; fire control
  1/4; no screens (FB2 p.8), no ADFC (scatterguns area-defend themselves, FB2 p.10), no salvo
  missiles, no beams. `turn_thrust` is the full thrust rating, not half (FB2 p.9). Anything else
  raises `race_system`.
- **FB2 p.10 prints "9 MASS and costs 18 points" for a Kra'Vak fighter bay and that is wrong**:
  every design in the book (Lo'Vok 626, Yu'Kas 883, Ko'San 917) prices a bay at the human 27, and
  the printed 18 is the Ra'San group's own cost from the same page. Do not "fix" it back.
- System dicts per type (the design `systems` list; `uid` + `type` always): `beam` {class,
  arcs}, `pulse_torpedo`/`needle_beam`/`sm_launcher`/`nova_cannon`/`wave_gun` {arcs},
  `submunition` {arcs optional}, `sm_magazine` {capacity (MASS), feeds [launcher uids]},
  `sm_rack` {load std|er, arcs}, `screen` {level; >2 = backup generators}, `hangar` {bays},
  `tender_bay` {capacity = MASS carried}, `minelayer` {mines}, `tug_drive` {tow_mass}, `hold`
  {kind cargo|passenger|troop|lab, mass}; no params: `pds`, `fire_control`, `adfc`,
  `mt_missile`, `ortillery`, `minesweeper`, `reflex_field`, `cloak`.
- Rules code treats designs as semi-untrusted: bad numbers read as defaults (`_int`), unknown
  types cost nothing and raise a violation. Nothing in a ruleset raises on a malformed design.
- Labels and issue messages are translated at call time (`system_defs()` is a function for that
  reason). Breakdown `derived` holds `hull_descriptor`, `turn_thrust`, `damage_track`,
  `crew_factors`, `cf_positions`, `thresholds`, `holds`, `ftl_mass`, `drive_mass`.
- FB judgment calls, recorded in the code comments: the hull minimum is the *rounded* 10% (FB2
  says FB1's Fragile designs stay legal); pulse torpedo arcs must be adjacent ("traverse"), class
  3+ beam arcs need not be; type suggestion picks the FB1 p.12 band whose centre is nearest (ties
  to the smaller class), carriers from 2 fighter bays and MASS 80, never CVA; merchants suggest
  "Merchant" / "M" (no book code exists).
- `rulesets/ft2/`: `data.py` (books FT +1 / MT 0, arcs `F S A P`, FT p.31 table, FT p.14 basic
  classes), `rules.py`, `mt.py` (MT systems, supership rows/fire controls, fighter surcharges),
  `__init__.py` (`RULESET`, the picker; MT systems offered only with `mt_systems`).
- FT2 system dicts: `beam` {class A|B|C, arcs}, `needle_beam`/`pulse_torpedo`/`nova_cannon`/
  `aa_battery`/`wave_gun` {arcs, one arc}, `submunition` {arcs optional}, `screen` {level 1-3},
  `fire_control` (the first N per class are free, then 3 MASS/10 points), `fighter_group` (one
  group incl. bay; loadout `hangar` points at its uid), `tug_drive` (merchant, FTL x3); no params:
  `pdaf`, `adaf`, `minelayer`, `minesweeper`, `mt_missile`, `ortillery`, `reflex_field`, `cloak`.
  `hull_boxes`, `armour` and `streamlining` are FB fields; FT2 derives damage from MASS and flags
  armour or streamlining.
- FT2 facts from the page images: 4 arcs, no offensive fire aft (FT p.8); extra damage boxes go
  on the LOWER rows (FT p.12); merchants have 1 free fire control and 4 rows at their size (FT
  p.15); non-FTL warships carry 75% (FT p.25); tugs pay FTL x3 (FT p.26); turn thrust rounds up
  (FT p.5). Odd fractions round up (owner: damage points; the rest follow, and the FT p.15
  Survey Cruiser confirms it for merchant capacity).
- Tests: `tests/test_rules_fb.py`, `tests/test_rules_ft2.py` (golden designs, one test per costing
  rule and validator), `tests/test_rulesets.py` (protocol conformance).
  `docs/mockups/ssd.js` has a JS costing that agrees on 219 and 261; it is not the reference.

## Catalog

- `data/catalog/fb_fb1.json` (FB1 pp.13-42: 57 NAC/NSL/FSE/ESU warships, 8 merchant and support
  vessels), `fb_fb2_kravak.json` (FB2 pp.12-19, 15 Kra'Vak warships and 1 merchant),
  `ft2_core.json` (FT pp.14-15, 17 basic classes), `ft2_mt.json` (MT p.23, 14 designs).
  Files are `{"schema_version": 1, "designs": [...]}`; ids `<ruleset>:<book>:<faction->name>`.
- **Generated, never hand-edited:** `tools/extract_catalog_fb1.py` and `extract_catalog_ft2.py`
  hold the curated ship tables and write the JSON; fix a ship there and re-run. The notation is
  documented in `tools/catalog_common.py`. Default loadouts: standard fighters per bay/group,
  all-standard salvos; each ship's single magazine feeds all its launchers.
- How the tables were read: spec panels from the text layer (the FB1 script checks every TMF/NPV
  against the page); arcs from the vector SSDs by `tools/ssd_arcs.py` (`rings()` = beam rings,
  white segments are covered arcs; `pies()` = launcher/rack ring segments); the rest (torpedo
  facing, submunitions, merchants, all of FT and MT) from rendered page images. FT2 beam pointers:
  up F, left P, right S; the FT capital classes' side A batteries cover two arcs, not three.
- `tests/test_catalog_gate.py` (PLAN 8) judges each design with exactly the MT options it needs.
  110 of the 112 match their printed NPV; the two errata entries are the FT p.31 design example
  and the FB2 p.18 Do'San.
- **Kra'Vak arcs need no image pass.** `ssd_arcs.py` finds nothing on FB2 pp.12-19: the Kra'Vak
  icon is a plain numbered hexagon with no arc pointer (the key is on FB2 p.11), filled for a
  one-arc gun and outline for an all-arc one. The class already fixes that, and the book's prose
  names the arc as fore (FB2 pp.11, 13, 15).
- tools/ scripts need `pymupdf` (requirements-dev) and run from the repo root; the three rulebook
  pipeline files are excluded from ruff, the extractors only from E501 (one row per ship).

## Sister project

The `FrostgraveWarbandKeeper` checkout beside this one uses the same stack. Copy and adapt (never import)
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
`ftfm-dev-scratch` (in the parent folder's `.claude/launch.json`, outside the repo) does this
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

## Desktop build (M12)

`.venv/Scripts/python.exe -m PyInstaller --noconfirm fleetmanager.spec` produces a onedir build
at `dist/FullThrustFleetManager/` (~63 MB; the rulebooks and pdf.js are most of it). The spec
adds whole folders, so new static or data files need no edit there.

Verifying a build: run the exe with `PORT` and `FTFM_DATA_DIR` pointed at a scratch dir, then
exercise it over HTTP. **It opens a browser tab on launch**, and that tab's heartbeat keeps the
idle watchdog from exiting, so stop a test instance by PID from the port (never by process
name), not by waiting for the watchdog.

## Web build (M13)

`python scripts/build_browser_bundle.py`, then serve a copy of what `deploy-pages.yml`
assembles: `web/index.html`, `web/bundle.json`, `static/`, `rulebooks/` in one folder
(`python -m http.server`). The deployed site has two levels: `web/landing.html` becomes the site
root (`index.html`: play online + Windows download, no preview pages) and the Pyodide app sits
under `app/` with its `static/` and `rulebooks/`. The landing page reads its logo and fonts from
`app/static/`. `scripts/stamp_landing_page_versions.py _site/index.html` fills the version badges
and the Windows link from the newest release with a `-win64.zip` asset (the asset name carries the
version, so the link cannot be hard-coded); keep the `data-version-badge` / `data-download`
markers in `landing.html`. Two web-only facts the desktop build hides:

- `bundle.json` is **text only**. Binary files the Python side opens (the PDF's TTFs) are
  fetched by the shell and written into the Pyodide filesystem under `/app`
  (`BINARY_ASSETS` / `copyBinaryAssets` in the shell). Add to that list when the app starts
  reading another binary file.
- Flask routes do not exist for anything outside the page: pdf.js must be pointed at
  `/rulebooks/<file>.pdf` in `BROWSER_MODE`, not at `/rulebook/<code>/file`.
- An inline binary response (the fleet PDF) is opened from a blob in a new tab; an attachment
  is downloaded.

Deployment is manual (`deploy-pages.yml`, workflow_dispatch) and belongs to the owner.
