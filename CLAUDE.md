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
`AGENTS.md` points Codex here and adds only the Codex/Claude PR workflow; keep it short.

## Current state

M1-M14 are done and released (versions are tagged on `devversion`). The app has the Layout C shell,
four rules engines (FB with the FB2 races, FT2 + More Thrust, FTCD, Cross Dimensions, and
FTPC, Project Continuum; the last two also field every Fleet Book ship), the catalog behind the NPV gate, the storage layer, the SSD
layout engine, the Design, Fleet overview, Campaign and Settings tabs, the fleet PDF, the
rulebook viewer, the signed Windows exe (M12) and the Pyodide build on GitHub Pages (M13).
Cross Dimensions is complete. Project Continuum is complete. Releases follow
`.claude/skills/shipping-a-release/SKILL.md`.

What exists:
- `app.py` — Flask app: tabs `/fleet` (home, `/` redirects), `/design`, `/campaign`,
  `/settings`; `/heartbeat` routes; `_reject_cross_site()` guard; `register_action` /
  `dispatch_action` carry the Fleet tab's state-changing forms; `main()` runs Werkzeug in dev,
  waitress + tray + idle watchdog when frozen.
- `templates/base.html` — Layout C top bar (brand, fleet selector, tabs, points meter, Print
  button, ruleset colour strip; sticky except below 520 px tall and in print), flashes,
  `<main class="work cols-N">` grid. One template per tab plus `error.html`, `print.html`,
  `rulebook.html` and `tournament_check.html`.
- `static/style.css` — the mockup's visual language, status and ruleset accent colours as CSS
  variables, panes stack below 1100 px. The Settings "Look" (`settings["theme"]`, one of
  `store.THEMES`: admiralty, lunar, bridge, carbon-armor, night-sky, nebula, aurora, asteroid,
  orbital-foundry, celestial-archive, full-thrust (default)) sets
  `<html data-theme>`; each look is a block at the end of the file that redefines the variables and
  restyles colour, type and borders only. The unscoped rules are their shared base, not a look
  (Classic was retired; a stored unknown value falls back to the default). `theme_chosen` marks
  a picked look: a stored `admiralty` without it is the old default and follows the new one. Ship diagrams keep a
  light ground in every look. Full Thrust matches the landing logo with navy panels,
  blue controls and crimson accents; its cover is `static/themes/full-thrust.webp`.
- `static/artwork.css` adds the two illustrated palettes and decorative covers for all eleven themes from
  `static/themes/`. `portraits.py`, `data/ship_art.json`, `static/ships/` and `_portraits.html`
  provide portraits in every theme. See `docs/SHIP-ARTWORK.md` for extension and storage rules.
  Versioned artwork covers the source catalog plus 46 custom choices;
  legacy records remain valid. Optional `class_defaults` selects refreshed class pictures.
  Per-portrait metadata records references, basis and view. Owner-corrected defaults use new
  IDs/files and remap only changed cells. Original Phalon art is restored and extended in its
  Fleet Book style/view in legacy records; legacy human factions use port-bow. New `photo-v6:`
  defaults use individual miniature-reference portraits with their native photo angles, clean
  aerospace materials and corrected casting bends. Ships sharing a miniature class share one
    portrait. `model` identifies that reference hull; `references` records source URLs. The 268
  individual portraits cover all 482 source catalog designs; 25 generic rules
  examples reuse matching miniature classes. Three no-miniature hulls are marked invented;
  older Kra’Vak/Sa’Vasku illustration-based reconstructions are explicitly identified.
    There are 38 refreshed miniature-based custom choices; special facilities retain earlier art.
  Optional `columns` and
  `rows` support atlases or individual images (1 by 1); omitted dimensions mean 4 by 4.
  Individual images are centered with `background-size:contain`, preserving native aspect
  ratios rather than distorting hull geometry.
  Eight `photo-v7:` material refinements supersede their `photo-v6:` defaults without
  changing the older records. Revisions retain model keys, source URLs and camera angles.
  `palette-v8:` defaults apply the owner-approved faction colours from
  `docs/SHIP-ARTWORK.md`, overriding miniature paint but retaining hull shapes and source
  viewing angles. Accents follow structural panels; no painted decorative motifs. NAC
  uses thinner flush plates and rebuilt lighting to reduce miniature shading.
  All prior IDs remain valid; explicit selections and uploads keep precedence.
  Portraits are separate from rules, SSD primitives and PDF output; do not replace meaningful
  record-sheet symbols with generated art. Design-level overrides use canonical catalog IDs
  across FB/CD/PC; fleet-instance overrides use fleet ID plus ship UID. `portraits.json` holds
  user choices/uploads separately from immutable catalog and design/fleet statistics.
- `static/fonts/` — IBM Plex Sans (owner's choice) Regular, Italic, SemiBold, Bold as TTF from the
  IBM/plex 1.1.0 release, with its OFL licence. The same files are for the PDF (M9). The web
  shell rewrites `url("fonts/` and `url("themes/` to `static/` paths when it inlines CSS;
  keep that spelling in CSS assets. Portrait HTML uses `art_url` for desktop/web paths.
- `i18n.py` + `translations/en.json` — see Translation below.
- `paths.py`, `tray.py`, `idle_watchdog.py`, `run_app.py`, `fleetmanager.spec` and
  `fleetmanager-linux.spec` — copied from Frostgrave and adapted (env prefix `FTFM_`).
- `scripts/build_browser_bundle.py` → `web/bundle.json` (gitignored), `web/index.html` (the
  Pyodide shell). `scripts/build_preview_pages.py` and
  `scripts/stamp_landing_page_versions.py` finish the Pages site; see Web build below.
- `rulesets/` — the `Ruleset` protocol, registry, FB, FT2 and FTCD engines; see Rulesets and
  FTCD ruleset below.
- `data/catalog/` — the read-only catalog; see Catalog below. `data/errata.json` — book values
  that disagree with the rules, with the reason (PLAN 8).
- `.github/workflows/tests.yml` (ruff + full pytest, and a web-build boot check, on push/PR), `deploy-pages.yml` and
  `build-linux.yml` (both manual, workflow_dispatch). `.githooks/pre-push` runs `ruff check .`
  before every push; `.claude/settings.json` enables it (`git config core.hooksPath .githooks`)
  when a session starts. Before pushing a PR branch, also run the tests for what you changed.
- Also: `docs/PLAN.md`, `docs/mockups/` (serve with
  `python -m http.server 8765 --directory docs/mockups`), `rulebooks/` and the `tools/` that
  rebuild them from the bought originals (source folder set in `tools/build_rulebooks.py`).

- `fleet_rules.py`, `store.py`, `migrations.py`, `data/factions.json` — see Storage below.

- `ssd_layout.py` — the record sheet; see Ship diagram below.
- The Ship Design tab (`/design`, `/design/<id>`) — see Ship Design tab below.

## Ship Design tab

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
- `store.add_system` re-sorts `systems` into the picker's order (stable, so one type keeps its
  add order); the Add-system picker remembers its last pick in `session["system_type"]`.
  The picker is one `<optgroup>` per ruleset group (`_system_groups`, ruleset order) with a filter
  box (`static/syspicker.js`: every typed word must appear in the option's `data-search`, Enter
  adds the first match, the text survives the autosave swap; hidden without script).
- Actions: `apply` (recalculate), `add_system`, `remove_system`, `save` / `refit` / `variant`
  (`store.save_design` modes), `discard`, `delete`, `make_variant`. Everything but
  `make_variant` is refused on a catalog design.
- The right pane is computed per request in `_design_context()`: breakdown, MASS bar against
  `derived["mass_limit"]`, NPV against the book value for catalog designs, issue list, and the
  live SSD as inline SVG (`Markup`, from `ssd_layout`).
- New designs start from a class preset (`rulesets/presets.py`, built from each ruleset's
  class tables; applied by `store.new_design(class_preset=...)`). A later MASS change that
  leaves the class band only re-classes the design (`presets.reclass` in `_apply_form`).
- `tests/test_design_tab.py` uses the `client` fixture with a per-test `FTFM_DATA_DIR`.

## Fleet overview tab

- Routes: `GET /fleet` (the current fleet, `?view=cards|roster`), `GET /fleet/<id>`
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
  and the roster table. Both use the same `ssd_layout` diagrams the PDF does.
- A ship's name and table ID are editable on its card; table IDs are unique per fleet,
  case-insensitive (`store._table_id_taken`, checked on add and on edit).
- Add ship lists only the fleet's faction's designs when it has one; the "Show all ships" toggle
  is a GET form (`all_ships`, a hidden 0 before the checkbox's 1) remembered in
  `session["all_ships"]`, so it survives the redirect after adding a ship.
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
- Fonts are the bundled IBM Plex TTFs; no system font is used. `PrintOptions.style` is
  `mono` (default, ink-saving black and white) or `color` (blue dossier accents), selected
  independently of the screen theme in the print dialog. Both retain black-on-white SSDs.
  Shared page furniture, wrapping/repeating roster tables, framed packed ship sheets,
  orders grids with velocity columns, bounded tracker cards and two-column references
  use the same print-first layout on A4 and Letter. Rulebook text and SSD primitives stay
  unchanged. Running headers abbreviate long fleet names; body identities wrap in full.
- The tracker (`_tracker_rows`) and the quick reference read what a ship carries: its own
  loadout, else the design's default. Empty bays print nothing, a light wing is 8 fighters and
  4 endurance (PC p.75), a magazine shows its loaded salvos; with damage printed, lost fighters,
  spent salvos and used one-shots are struck out. Gunboats anywhere add the `gunboats` key.
- Quick reference: `data/quickref/<ruleset>.json`, generated by `tools/extract_quickref.py`
  from the rulebooks (heading table inside the tool; re-run after editing it). The text is the
  book's own wording with a **printed** page reference, which PLAN 2.5 requires: **never
  paraphrase it by hand.** FT and MT are OCR over two-column pages, so extraction picks up
  figure captions, spec panels and half sentences:  repairs hyphenation and stray page
  numbers, and  in the tool holds entries transcribed from the page image where the
  layout defeats it.  guards both the text and the page numbers. `Ruleset.quickref()` filters it to the systems present plus a few always-on
  entries, the fleet's optional rules and the races in the fleet. Some shared entries are
  race-dependent: FB1's crew and fire-control entries are dropped unless a crewed race is in the
  fleet, because a Sa'Vasku construct has neither. Race entries are key-prefixed (`kv_kgun`,
  `sv_stinger`, `ph_pulser`), so a mixed fleet still gets the FB1 entry for its human designs. **FB2 repeats
  FB1's headings once per race** and `body_after()` keeps the longest body wherever it is, so a
  Kra'Vak key can silently resolve to the Phalon section: pin such an entry to its printed pages
  in the tool's `PAGES` map, and check the page reference against the page image.
- `tests/test_pdf_export.py` reads the generated pages back with pymupdf. Render pages to PNG
  for a visual check when the layout changes.

## Campaign tab

- `GET /campaign` (the current fleet), `POST /campaign/<id>/action`, `GET /dice/6`.
- Campaign maths is pure and lives in `fleet_rules`: `hull_boxes`, `crew_factors_left`,
  `ship_is_crippled`, `repairable_systems`, `repair_plan` (FT p.35: 1D6 hull a week at a base,
  up to three systems on 3+, a disabled drive needs two successes; ruling: each drive roll takes
  one of the three places; attempts and successes are recorded separately). `store` applies it:
  `set_ship_damage` (clamped to what the design has), `toggle_system_out`, `repair_ship`,
  `replenish_ship` (fighters, salvos and one-shot systems in one week).
- **Clicking the diagram**: every primitive carries a `ref` (`hull:7`, `armour:2`,
  `system:s3`), `to_svg()` emits it as `data-ref`, and `static/campaign.js` posts the ref of the
  shape that was clicked. Clicking the last marked box unmarks it. The fields under the diagram
  do the same thing, so the tab works with scripting off; the dice buttons are optional too.
- `static/keepscroll.js` (every page) keeps the scroll position across the reload a click
  causes: it notes the scroll on click/change/submit and restores it when the next page has the
  same `<html data-path>` (the web frame has no path of its own).
- Hooks reserved for the later campaign module (PLAN 11.2) are in use but not repurposed:
  `ship.location`, `log[].week`, statuses `docked` and `hulk`.
- Campaigns (PLAN 11.3, roadmap step C1): `campaigns/<id>.json` holds name, ruleset, week,
  sides and a log; membership lives on the fleet (`campaign_id`, `campaign_side`), so a fleet is
  in one campaign at a time and every fleet in it shares the campaign's ruleset. The campaign bar
  on the Campaign tab posts fleet actions (`new_campaign`, `join_campaign`, `leave_campaign`) to
  `/campaign/<fleet>/action` and campaign actions to `/campaigns/<id>/action`. `.FTCampaign`
  exports the campaign with its fleets and their designs; backups carry `campaigns/`.
- Star maps (step C2): `campaign["map"]` = {width, height, seed, systems [{q, r, name, kind
  settled|outpost|empty, owner side id or "", base}], draft}, normalised by `store.normalize_starmap`.
  `starmap.py` is pure: flat-topped hexes in odd-q offset coordinates (`hex_distance`, labels
  "0304" from 01), the seeded `generate()` (an app rule, step G1: spacing, star names from a pool
  of 1200+ (proper names and Bayer designations) or catalogue numbers; up to 5 sides, each with
  exact counts of settled worlds, outposts and (optional) bases and a core-worlds toggle, plus
  neutral settled worlds and outposts placed none / random / border. Counts are a hard rule
  (Master 2026-10-22): `CountsError` when the stars can't hold them, never fewer. Homes at
  opposite ends, sides claim nearest stars in turn, then `claim_empty` gives bare stars inside a
  sphere to its side, front aside), `influence()` / `frontline()` (only settled worlds and
  outposts project; neutral clusters are `campaign["neutral_clusters"]`; hexes shaded when
  `map["frontline"]`: a side's sphere is the hexes within `campaign["front_reach"]` (default 4)
  of its systems, always outlined; ties between sides' nearest held systems, hexes beside another side's
  region, and a ring around neutral worlds' regions: their own hex, plus one more for a cluster within 3 hexes where every side is 2+ hexes further) and `to_svg()`, where every hex is an `<a href="/campaign?hex=q,r">`
  so picking one needs no script. `scenarios.home` is a side's first base, else settled world,
  else outpost. The map keeps a dark sky in every look. `.FTStarmap` files
  carry the map and the sides; loading one maps owners onto this campaign's sides by position.
  Settings > Import refuses them and points to the Star map panel. A generated map is a draft
  (`map["draft"]` holds its settings) that its inputs regenerate live with the same seed until
  Finalize (`finalize_starmap`; Master's exception to no-Save/Apply); `app.NEEDS_FINAL_MAP`
  actions refuse while it is a draft.
- Task forces (step C3): `campaign["forces"]` [{id tf1.., side, name, q, r, order [q, r] or
  null, ships [{fleet, uid}]}], normalised by `store._norm_forces` (on a map, a known side, a ship
  in one force only). A force sits on a star system and jumps up to `FTL_HEXES_PER_WEEK` (6, FT
  p.35) to another; `fleet_rules.force_reach` refuses a docked ship, a starbase or gate
  (`fleet_common.jump_blockers`), or ships without working FTL that the force's tender bays and
  tugs cannot carry. `store.next_week` carries out every order, sets each ship's `location` to
  the system name and logs a contact where sides meet (`store.meetings`); replacing the map
  clears the forces. Pennants and dashed order lines are drawn by `starmap.to_svg(forces=)`.
- Contacts (step C4): `campaign["contacts"]` [{id k1.., week, q, r, sides, reports {side:
  {escort, cruiser, capital}}, choices {side: fight|withdraw|standoff|""}, roll, outcome
  battle|standoff|leave|escaped, leaving [sides], result side|"drawn", owner_before, notes}],
  normalised by `store._norm_contacts`. `next_week` opens one per meeting with each side's real
  scan (`fleet_rules.scan_counts`, the protocol's `scan_class`), which that side may change
  (decoys, weasel boats). The pure rules are `fleet_rules.contact_outcome` /
  `catch_roll_needed` (FT p.35). The last choice settles it; a won battle or a fleet that got
  away gives the system to the side left there (`store._claim`, an app rule, undone by
  `reopen_contact`). Next week refuses while a contact this week is unsettled, a battle is
  unrecorded, or a force that must leave has no order and can move. Only the current fleet's
  side sees its own choice before all are in.
- Bases and reinforcements (step C5): with a star map, `store.yard_block` allows repairs and
  replenishment only for a docked ship in a task force at its side's naval base, and
  `repair_ship` once per campaign week (`ship["repaired_week"]`); without a map nothing is
  checked. `campaign["reinforcements"]` [{id rf1.., side, name, week, q, r, ships}] become task
  forces in `next_week` (`store._arrivals`) before contacts are found.
- Hidden movement (step C6): `campaign["hidden"]`. The tab looks through `_campaign_view()`: the
  current fleet's side, behind a hand-over screen whenever that side changes
  (`session["campaign_seen"]`), or the umpire (`session["campaign_umpire"]`), switched by
  `POST /campaigns/<id>/view`. A side sees its own forces and those it is in contact with
  (`store.sees_force`), others' orders and reinforcements only without hidden movement, and log
  entries whose optional `sides` include it (`store.sees_log`). Other sides' ship lists are never
  shown. A force with `dummy` has no ships, jumps 6 and is removed with a log entry when it ends
  a week beside an enemy force (`store._exposed_dummies`).
- Objectives (step C7): `campaign["objectives"]` {side: {count, include, draw [up to 2 tiers]}}
  (hold `count` settled systems with `include` among them, `starmap.holds`), `end_week` and
  `result` {winner side|"draw", week, text}. `next_week` judges the week just ended
  (`store._verdict`) before moving anything: an objective met wins; after `end_week` a draw tier
  draws, else the sides without objectives (the defenders) win. A result stops Next week until
  `reopen_campaign`. `store.lafayette_campaign()` sets up FT pp.36-38 from `LAFAYETTE` (map
  positions read off FT p.37); its force budgets go in the notes.
- Scenarios (step G2): `scenarios.py` is pure; `build(kind, map, sides, attacker)` turns
  `invasion` / `raid` / `border_war` (all app rules) into owners, objectives, a last week and a
  note, and `store.apply_scenario` applies it in week 1 before any contact. A side's home is its
  first naval base on the map. Objectives only measure holdings, so a template is a holding.
- Force generator (step G3): `forcegen.pick` (pure) buys catalog designs for a budget, each
  pick in the least-used scan class that keeps every class at half the ships or less (FT p.37).
  `store.generate_forces` makes a new fleet for a side from `force_candidates` (the faction's
  FTL catalog warships), joins it to the campaign, forms a "Main fleet" force at the side's home
  and, with a garrison budget, one force per settled world it holds. The books print no non-FTL
  warships, so garrisons are FTL ships too.
- Weekly events (step G4, app rules): with `campaign["events"]`, `next_week` rolls 2D6 per
  side on `events.py`'s table (`store._weekly_events`, before reinforcements arrive): unrest and
  pirates take an unguarded settled world or outpost, supply trouble closes the side's yards
  and a leak exposes its forces for that week (`campaign["effects"]`, read by `yard_block` and
  `sees_force`), late or early moves its next reinforcement. War weariness: a battle lost by a
  side with an objective takes a week off `end_week` (`contact["shortened"]`, undone by
  `reopen_contact`).
- Installations (step C8) are ordinary fleet ships whose design `fleet_common.installation()`
  accepts: a starbase, a gate, or a design with neither FTL nor thrust (FT p.27; a PC monster
  ship `section` is not one). Placed in a task force on a system they never move and cannot
  be carried (PC p.116), the side cannot withdraw from a contact there, and a standing one is
  a repair yard for its side's docked ships there, itself included (`store.installations_at`,
  `yard_block`; an app rule beside FT p.35's naval bases).

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
  (`icon_set_for(race)` -> `"fb"` / `"ft2"` / `"fb_kravak"` / `"fb_savasku"` / `"fb_phalon"`,
  falling back to the `icon_set`
  attribute) rather than drawing itself, because drawing is a consumer's job. A set may also
  supply `"main_drive"` and draw the drive itself, as `fb_kravak` does for the Advanced Grav
  Drive that FB2 p.9 says looks different and is written "4A".
- **Parts of a sheet that are not systems come from the ruleset's `derived`, never from a branch
  on the race**: `core_systems` (the B/L/P box; false for Sa'Vasku), `power_generators` (drawn at
  the damage-track row ends, over the rows the ship actually has, zeros omitted), `thrust_table`
  and `power` (the thrust table and the empty M/A/D/R box), `shell_layers` (one armour row per
  Phalon shell layer) and `pulser_modes` (the L/M/C letter in each pulser icon). A ruleset that derives none of them
  gets none of them, which is why FT2 and the human sheets did not change when they were added.
  `layout()` calls `design_breakdown()` once and also hands each icon its system's computed MASS,
  so an icon can print it (the Sa'Vasku screen node shows the power it needs).
  An unknown type falls back to a labelled box, so a new system never breaks a sheet. Boxed
  abbreviations take a callable so the label is translated at draw time.
- `box_size()` gives the sheet width band (small/medium/large/xlarge) the packed PDF sorts by.
- `tests/test_ssd_layout.py` covers placement, damage and the size bands, asserts every catalog
  design draws inside its own box, and holds SVG snapshots of 3 reference ships per ruleset in
  `tests/snapshots/`. Regenerate them with
  `.venv/Scripts/python.exe tests/test_ssd_layout.py --update` and read the diff: a changed
  snapshot means every record sheet changed.

## Storage (layers 2-3)

- `fleet_rules.py` (pure): `fleet_options()`, `default_options(ruleset)` (what `create_fleet`
  starts with: gear and mechanics on, selection limits and alternative core rules off), `design_points()` / `ship_points()` (NPV plus the
  ship's loadout, its own or the design default) / `fleet_points()` (skips destroyed ships),
  `design_issues()`, `fleet_report()` (the tournament check: fleet issues + a `ShipReport` each),
  `badges()` (`non_conforming`, `no_faction`, `mixed_faction`, `custom_ships`; names from
  `badge_label()`), `ship_counts()`. Conformance is
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
- Export/import (PLAN 5.6): `.FTCampaign` (campaign + its fleets + their designs),
  `.FTFleet` (fleet + its non-catalog designs + custom factions),
  `.FTDesign`, `.FTBackup` (a zip of the library). `import_file()` returns
  `(ok, msg, conflicts)`; a *newer local copy* is kept and named in `conflicts`, and the caller
  re-calls with `overwrite_newer=True` after the player confirms. `modified` is an ISO string at
  second resolution, so tests that need "strictly newer" backdate the local copy. The whole file
  is read and checked (`_read_document` / `_read_backup`, raising `_Refused` or `TooNewError`)
  before anything is written; a backup entry that is not a usable design or fleet is skipped
  and counted.
- In the app: Settings > Files (`POST /backup`, `POST /import`), and an Export button on the
  Fleet tab and on a saved custom design (`/export/fleet/<id>`, `/export/design/<id>`). An
  import with conflicts is held in `pending_import.json` (`store.hold_import`) until the player
  answers Replace / Keep mine (`POST /import/held`). Downloads are plain `attachment` responses
  and links without a `download` attribute, so the web shell intercepts them. The web build
  shows a backup reminder (`BACKUP_DUE`, `store.backup_due()`: 14 days since the last backup
  or "Later").
- `migrations.py`: `CURRENT`, `STEPS[kind][from_version]`, `upgrade()`. A missing or malformed
  `schema_version` counts as 1; anything above `CURRENT` raises `TooNewError` and is refused
  rather than guessed at. Write the step and its test in the commit that bumps `CURRENT`.
- `data/factions.json` holds the built-in factions per ruleset, each with its race; custom
  factions (with the race they were made for) live in the user library and travel with exports.
  The Ship Design tab's faction pickers (`templates/_factions.html`, `static/factions.js`) offer
  "New faction" (`store.faction_for_name`), list a custom faction only once a saved design carries
  it (`store.faction_choices`), and hide custom and other races' factions by two toggles saved as
  the `show_custom_factions` / `show_other_race_factions` settings (`POST /settings/factions`).

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

## Architecture (PLAN section 4)

Four layers, strictly ordered — each may import only from layers above it:

1. **`rulesets/<id>/`** — per-ruleset data and pure rules (costing, validation, damage track,
   icon set, quick reference) behind the `Ruleset` protocol in `rulesets/__init__.py`.
   `fb`, `ft2` (+ `ft2/mt.py` for the More Thrust toggles) and `ftcd`.
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
- The protocol is PLAN 6.1 plus: `arcs` (the ruleset's arc names), `option_keys` (the fleet
  options it offers, in display order; `fleet_rules.option_label()` names them, and the fleet
  form, chips and PDF show only those), `loadout_points()` (fleet
  totals include loadouts, PLAN 5.4), `fighter_types(options, race)` (loadout editor),
  `required_options(design, loadout)` (the MT toggles a design needs), `icon_set_for(race)`,
  `quickref(systems_present, options, races)`, `fleet_issues(fleet, [(ship, design)], options)`
  (rules that judge the whole fleet; `fleet_report` adds them to `fleet_issues`) and
  `hull_kinds` (the Ship Design tab's "Hull kind" choices) and `dummy_bogey_points` (0 offers none; `fleet_rules.fleet_points` adds the fleet's
  `dummy_bogeys` at that price). `loadout=None` means the design's default loadout.
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
  fleet's options. As with FTCD's options, a key absent from `options` (a design alone, as the
  Ship Design tab and `save_design` judge it) is only an `option_needed` info; `False` is the violation.
- The tournament check validates the ship's own loadout when it has one (`ship["loadout"]` in
  place of `default_loadout`), since that is what it carries and costs.
- `rulesets/common.py`: what more than one ruleset needs. Integer rounding (`round_half_up`,
  `pct_mass`: .5 up, never 0 MASS), arcs (`ARCS`, `arcs_valid`, `arcs_contiguous`),
  `split_rows`, `cf_positions`, the semi-untrusted readers (`as_int`, `systems_of`, `arcs_of`,
  `loadout_entries`), `half_turn_thrust`, labels (`hangar_label`, `hold_label`, `class_label`,
  `hull_descriptor`), `pick_class` and the salvo-missile check `validate_missiles`. **A ruleset
  imports shared pieces from here, never from another ruleset's `rules.py`**; only a race module
  reused across rulesets (FTCD's FB2 races) crosses packages. The FB modules keep their old
  underscore names as aliases. Never compute percentages with floats: 85 x 30% must be 25.5
  exactly to round to 26.
- `rulesets/fb/`: `data.py` (books, `system_defs()` for the picker, fighter points, FB1 p.12
  classes, hull descriptors), `rules.py` (human tech: `SYSTEM_RULES` type -> (mass, points,
  label), breakdown, validation, derived values), `kravak.py` (Kra'Vak tech, FB2 pp.9-11),
  `savasku.py` (Sa'Vasku tech, FB2 pp.21-25), `phalon.py` (Phalon tech, FB2 pp.35-37),
  `tech.py` (the race -> module table), `__init__.py` (`RULESET`).
- A tech module also declares `CREWED`: Sa'Vasku alone are False, and that is what decides
  whether FB1's crew and fire-control quick-reference entries belong on a sheet.
- Kra'Vak tech (`kravak.py`): hull, damage track, crew factors, thresholds, holds and tender bays
  are the human rules, which FB2 p.9 says outright, so they are imported from `rules.py` rather
  than restated. What differs: the Advanced Grav Drive costs 3 points per MASS (FB2 p.9, and it
  is the one rule that makes the race); `kgun` {class, arcs} on the FB2 p.9 MASS table (class 1
  all six arcs, class 2 one or two adjacent, class 3+ exactly one, +3 MASS per class above 6) at
  4 points per MASS; one-shot `mkp` {arcs, one} at 1/4 and `scattergun` at 1/5; fire control
  1/4; no screens (FB2 p.8), no ADFC (scatterguns area-defend themselves, FB2 p.10), no salvo
  missiles, no beams. `turn_thrust` is the full thrust rating, not half (FB2 p.9). Anything else
  raises `race_system`.
- **FB2 prints "9 MASS and costs 18 points" for an alien fighter bay twice (pp.10 and 36) and is
  wrong both times**: every design in the book prices a bay at the human 27 (Kra'Vak Lo'Vok 626,
  Yu'Kas 883, Ko'San 917; Phalon Taanis 641, Draath 1002). The printed 18 is a fighter group's
  own cost from the same page. Do not "fix" it back.
- Sa'Vasku tech (`savasku.py`) needed **no new schema**, and that is the point: biomass IS
  `hull_boxes` (1 MASS, 2 points, four-row track, threshold at each row end), carapace IS
  `armour`, the FTL node is the ordinary 10% one. The main drive node is always 10% of MASS with
  no rating, so `thrust` is 0 and a non-zero thrust is a violation; power generation is a system
  (`power_generator` {capacity}) carrying the total. Nodes: `stinger` {arcs, 3 contiguous},
  `pod_launcher` {arcs, one}, `spicule`, `cortex`, `screen_node` (5% of MASS, min 3), `drone_womb`.
  A construct has **no crew factors** (`crew_factors` is 0, no CF stars) and no core systems box.
- **The M/A/D/R power pools are not in the data model and must not be added.** They are rewritten
  every turn and explicitly do not carry over (FB2 p.22), so they are play state like movement
  orders: the sheet prints an empty box to write in. Drones are grown from biomass in play, so a
  drone group costs 0 points.
- Phalon tech (`phalon.py`) is the closest of the three to human: hull, drives, FTL, fire
  control, ADFC, hangars, tender bays and crew factors are the human rules and come from
  `rules.py`. Its own systems are `pulser` {arcs, 1/3/6 for 2/3/4 MASS, 5 points per MASS},
  `plasma_bolt_launcher` {class, arcs (3 adjacent); 5 MASS per class, 3 points per MASS} and
  `vapour_shroud` (5% of MASS, min 1, 3 points per MASS). There is no separate PDS: pulsers do
  that job (FB2 p.35).
- **The Phalon shell is the one thing that needed schema.** It is armour stacked in layers and
  a box costs `2 x layer number`, so a fourth-layer box costs 8 (FB2 p.35). `armour` keeps its
  meaning as the **total** box count, which is what the campaign damage clamp and the damage
  track use, and `armour_layers` holds the split, **inner layer first**. A design with no
  layers has the single layer every other race has. The sheet draws one row per layer with the
  outermost on top, which is also the order damage removes them, so shell box 1 is the first
  box of the top row.
- **The Phalon pulser L/M/C setting is a loadout entry, not design data** (FB2 p.35: chosen
  before each battle, never changed during one) and costs nothing. It is PLAN decision 25's
  default-in-design, overridable-per-ship pattern. The print dialog's `blank_pulsers` prints
  the icons empty, the way the book does, so the player writes the letters on the sheet.
- The Sa'Vasku **thrust table** is derived (`derived["thrust_table"]`), not stored. FB2 p.21 says
  the power cost is "rounded up" and shows 9.6 -> 10, but it is **round-half-up with a floor of
  1**: the Sa'Kess'Tha needs 1 PP at thrust 6 (1.32) and 2 at thrust 7 (1.54). Each row is the
  *highest* thrust its power pair buys. `extract_catalog_fb2_savasku.py` checks the derived table
  against every table printed in the book; twelve of the fourteen match to the cell.
- System dicts per type (the design `systems` list; `uid` + `type` always): `beam` {class,
  arcs}, `pulse_torpedo`/`needle_beam`/`sm_launcher`/`nova_cannon`/`wave_gun` {arcs},
  `submunition` {arcs optional}, `sm_magazine` {capacity (MASS), feeds [launcher uids]},
  `sm_rack` {load std|er, arcs}, `screen` {level; >2 = backup generators}, `hangar` (one bay = one fighter group, FB1 p.10; the
  picker offers no count, an older design's `bays` > 1 still costs 9 MASS a bay),
  `tender_bay` {capacity = MASS carried}, `minelayer` {mines}, `tug_drive` {tow_mass}, `hold`
  {kind cargo|passenger|troop|lab, mass}; no params: `pds`, `fire_control`, `adfc`,
  `mt_missile`, `ortillery`, `minesweeper`, `reflex_field`, `cloak`.
- FB types only the Star Ranger catalog uses (not in the picker; `rules.SYSTEM_RULES`): `emp` and
  `rocket_cannon` {class, arcs} cost as a beam; `graser` {class, arcs, no_reroll} (CD mass table,
  x4, x3 without reroll); `hdc` {class, one arc}; `lrpt` {arcs}; `amt`, `superior_sensors`,
  `enhanced_sensors` (2/8 as CD and PC);
  `age_penalty` {mass} is MASS lost to age at 0 points. FB designs may also carry `hull_rows`
  3/4/5/6 (boxes x3/x2/x1.5/x1; Star Ranger; a hull of 3 boxes or fewer always costs 2 a box) and `stealth_hull` 1-2 (+2/+4 a hull and armour box).
  **The Fleet Books are closed (owner's ruling; CD too, only PC takes additions):** these are
  costed only so the gate can check the Star Ranger pages, and `FBRuleset.validate_design`
  flags each as `not_in_books`, a violation.
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

## FTCD ruleset (`rulesets/ftcd/`)

- Cross Dimensions chapter 11, human tech. `data.py` (book, picker, CD p.42 classes),
  `rules.py` (costing, validation), `__init__.py`. It uses the shared helpers and missile check in
  `rulesets/common.py`, since CD is the Fleet Book design system gathered into one book; what
  CD changes is in `rules.py`'s docstring. Golden: the CD p.46 Heavy Cruiser is 294.
- New design fields `hull_advanced`, `drive_advanced`, `ftl_advanced` (normalised in `store`;
  other rulesets ignore them). An advanced hull has three rows (thresholds 6, 5) and is a
  standard hull below four boxes; an advanced drive turns its full thrust and its sheet icon
  is the "nA" hexagon, the advanced FTL a hexagon. Both come from `derived`, not a ruleset id.
- Broadside arcs are exactly `FS, AS, AP, FP`; they cost as three arcs (class-1/2 beams as six).
- Shell armour reuses `armour_layers` but costs 2, 4, 8 per box (doubling), not the Phalon
  2 x layer. MASS used may be under the total (CD p.42 "a maximum of"): a note, not a violation.
- **Fleet options drive points, so the Ship Design tab passes none**: the CPV hull cost and paying for
  advanced FTL apply to fleet totals only, and a system behind an option (`cd_optional_systems`,
  `cd_multistage`, `cd_super_weapons`) is an `option_needed` note there and an `option_off`
  violation only where a fleet has that option explicitly off.
- Quick reference: `CD_ENTRIES` in `tools/extract_quickref.py`. CD's headings are mixed case, so
  each entry names the next heading and a printed-page window instead; `gap_text()` restores the
  word spaces the justified text layer drops (glyph gap > 0.1 x font size) and skips the
  all-italic lines, which are the book's worked examples. That cleanup runs for CD only, so the
  FB and FT2 output does not move. Play rules with no system of their own are reached through
  keys `pdf_export` adds to the present set (`no_ftl`, `starbase`, `troop_hold`,
  `dummy_bogeys`) and `SHARED_ENTRIES` maps to entries; `fleet_morale` is on every sheet.
- Loadout extras (CD pp.25, 30, 47) live in the loadout, not the design, under optional keys
  `store._norm_loadout` keeps only when used: fighter `extras` / `swing`, magazine `stages`,
  top-level `craft` ({hangar, mass}). `derived["rich_loadout"]` makes the Ship Design tab draw one
  row per bay (`fighter-<uid>-<i>-type|ftl|kinetic|swing`), `craft-<uid>`, and per magazine
  `stages-<uid>` with `salvos-<uid>-std|er` counts; `_read_loadout` falls back to the single
  `loadout-<uid>` select for the other rulesets. Multi-stage loads are paid in `loadout_points`
  beyond the magazine space (two stages cost nothing extra, three 6 a salvo); FB's
  `_validate_missiles` takes FTCD's `salvo_space` for the bigger loads.
- A magazine's `feeds` list is edited as launcher checkboxes with a `-feeds-present` marker,
  like arcs; any list-valued system field is skipped by `_apply_form`'s int parsing.
- The FB2 races (`aliens.py`, CD p.21 section 5.12): each race's FB2 tech module with CD's
  design changes on top. Kra'Vak scatterguns cost 4 (not 5), Kra'Vak may mount an ADFC (2 MASS,
  8), Kra'Vak fighter groups pay +6 for kinetic weapons; the CPV option reaches every hull.
  Sa'Vasku and Phalon cost as in FB2. The rest of p.21 is play (screens, penetration) and is in
  the quick reference as `cd_kravak`, `cd_savasku`, `cd_phalon` beside the race's FB2 entries;
  `kv_scattergun` is left out because CD's scattergun rules replace it.
- Fleet-level rules (`rulesets/fleet_common.py`, shared with FTPC; the protocol's `fleet_issues`): a non-FTL ship is a battle
  rider (MASS 60 at most) and the fleet's live FTL ships must carry every rider, each in one
  tender bay or tug drive (an exact search, not first-fit; advanced-FTL tugs pool their transfer
  MASS, CD p.34). Over 60 it is a system defence ship and needs `cd_system_defence`, which also
  lifts the mothership check (CD p.35). Dummy bogeys (`fleet["dummy_bogeys"]`, CD p.37) cost 20,
  at most one per live ship, and need `cd_optional_systems`; the Fleet details form offers them
  as a dropdown.
- CD p.57's composition limits are fleet options: `cd_patrol_battle` (no capitals, at most half
  the points on cruisers) and `cd_capital_limit` (at most half on capitals); a ship's points
  include its loadout ("including their fighters"). Classes come from `rules.ship_class`.
- Fleet morale (CD p.40) is the protocol's `morale_mass()`: (MASS destroyed, half the fleet's
  MASS rounded up), shown as a Fleet tab tile and a PDF roster line; None in FB and FT2.
- Gates and starbases (CD pp.35, 51) need no new design field. A gate is a design carrying a
  `jump_gate` or `portal` system {transfer_mass}: the drive is 1 MASS per 10 transfer (a portal
  1 per 1), paid as FTL at 2 a MASS; hull boxes at least 10% of the transfer MASS; one kind per
  gate. A starbase section is `hull_kind` "starbase" (FTCD's `hull_kinds` alone offers it; other
  rulesets read it as a warship). Both are `rules.stationary()`: thrust must be 0, no "no FTL"
  note, and the fleet's battle-rider check skips them. The sheet draws "GATE n" / "PORT n".
- Catalog: CD prints no designs ("all of the ships in fleet book 1 can be used unchanged", p.3),
  so it adopts the FB catalog at load time: `catalog_sources = ("fb",)` and `adopt_design()`
  (Ruleset protocol; FB and FT2 adopt nothing). `store._catalog()` calls it once per FB design:
  id `ftcd:<rest of the fb id>`. Every FB1 design costs its printed NPV unchanged. A design whose
  cost moves (the Kra'Vak, for their scatterguns) loses `npv_book` and says why in `notes`; the
  Si'Tek swaps one K-1 gun for an ADFC as p.21 says. The Ship Design tab groups the copies as
  "FB1 (FTCD)" etc., and the landing page's class count leaves them out.

## FTPC ruleset (`rulesets/ftpc/`)

- Project Continuum section 13 (summary pp.118-124), human tech, errata (PCE) folded in.
  `data.py` (books, picker of ~80 systems in groups, fighter points, class table p.106),
  `rules.py` (`SYSTEM_RULES` type -> (mass_fn(s, design), points_fn(s, mass, design), label_fn)),
  `__init__.py`. Golden: the PC pp.113-114 heavy cruiser is 294. The FB2 races dispatch to their
  FB2 tech modules unchanged (errata: PC invalidates nothing in FB1/FB2), except that the CPV
  option reprices their basic hull as it does a human one (PC p.140).
- A holofield and a cloaking device each stand alone among `SCREENS_AND_FIELDS` (PC pp.60, 62);
  ECM is not in that set. A PC bay is one bay: `bays` is ignored in cost and capacity alike.
- Star Ranger systems PC lacks are in its picker as a "Star Ranger" group (`book="SR"`),
  `compact_superior_sensors` (2/30, beside PC's 4/16 superior sensors; owner's call) among them:
  `rocket_cannon` (as a beam), `amt` (2/8), `hdc` ((class x 8) - 4, x3, one arc), `age_penalty`;
  hull rows also offer 3 (x3; a hull of 3 boxes or fewer costs 2 a box). Adopted Star Ranger
  designs swap `lrpt` for the long-range torpedo, `mt_missile` for a heavy missile and superior
  sensors for the compact kind; their grasers become heavy grasers (high intensity unless
  the source disables rerolls), retaining the Star Ranger MASS and points table
  (`common.convert_star_ranger`; CD gets a class-2 torpedo). Their rules text is
  `data/quickref/sr.json` (hand-kept from the site, `url` per entry, `QuickRefEntry.url`): FB and
  PC quick references add it (`star_ranger_quickref`), `/rules/star-ranger` shows it all, and the
  Ship Design tab links a system to it.
- New design fields `hull_rows` (3/4/5/6: hull boxes x3/x2/x1.5/x1; an advanced hull is three rows
  at x3 and ignores it), `stealth_hull` (0-2, +2/+4 a hull and armour box), `armour_regen`
  (+2 a box). Normalised in `store`; the Ship Design tab draws them when `derived["pc_hull_options"]`.
  Rows past the third threshold on 4+.
- Shell armour costs 2 x layer as Phalon; screens are 5% a level with **no minimum**, which is
  why the FB1 Tibet costs 159 here. Broadside pairs (gatling/meson/pulser/TPA, SR K-1) are
  priced per pair (`_paired`); arcs need not be contiguous (p.45).
- PC hangars: a `hangar_bay` (6 MASS) needs a `launch_tube`; the combined `hangar` (9) still
  exists. `common.FIGHTER_BAY_TYPES` lists every fighter-holding type for the loadout editor,
  the loadout reader and the PDF tracker. A ruleset's `fighter_extras` property names the
  per-group extras the loadout editor offers (FTCD ftl/kinetic, FTPC ftl/fast/long_range/heavy).
- A `turret` {arcs 2-6, mounts [weapon uids]} costs by the MASS it holds (`turret_mass`, PC p.46),
  edited as checkboxes like a magazine's feeds (`derived["turret_weapons"]`); removing a system
  drops it from every `feeds` and `mounts` list. A `fighter_rack` holds one wing that must carry
  the `robot` extra; `light` is an extra too (eight for the price of six, some types only).
- Gunboats (PC pp.79-82) are a loadout key `gunboats`: [{carrier, type, extras, ecm}], one
  squadron of six per `gunboat_rack` or `boat_bay` (`common.GUNBOAT_CARRIER_TYPES`); a ruleset's
  `gunboat_types` / `gunboat_extras` properties drive the editor. Ruling: a squadron in a boat bay
  takes 24 craft MASS (MASS 4 a boat, p.80). A squadron may mix types (p.79): `types` lists all
  six boats (absent when uniform; `rules.boat_types()` reads both) and the per-squadron
  modifications cover all six. The editor is the `templates/_gunboats.html` macro, shared by the
  Ship Design tab's loadout and the Fleet tab.
- FTL gunboat squadrons need no carrier (p.80): `fleet["gunboat_squadrons"]` [{uid, type, ...}],
  FTL implied and paid (`rules.independent_squadron`). `fleet_rules.gunboat_squadron_points`
  adds them to the total through the ruleset's `gunboat_squadron_points`, gated on
  `gunboat_types` like the loadout editor; `fleet_issues` validates them and counts them in the
  tech base. They are not ships: no card, no morale MASS, no dummy-bogey allowance; the PDF lists
  them on the roster and the tracker.
- The Imperial tech base (`techbase.py`, PC pp.125-127) is the fleet option `pc_tech_base`:
  `design_techs()` maps systems, hull options and loadouts to technologies,
  `with_prerequisites()` closes them, and `fleet_issues` reports the choices as an info and over
  `LIMIT` (10, the book's recommendation) or gunboats beside fighters as violations.
- A monster ship section is `hull_kind` "section" with `ship_mass` (the whole ship): its drives
  and FTL are sized on that (`drive_basis`, p.116), and fleet rules don't treat it as a rider.
- Options: `pc_optional_systems` (catapults, flawed design), `pc_adfc_no_mass`,
  `pc_hangar_criticals`, `pc_overload_torpedoes`, plus CD's. Fleet rules are CD's through
  `fleet_common.fleet_issues()`, except dummy bogeys need no option. The catalog is FB's adopted
  as `ftpc:` ids.
- Quick reference: `PC_ENTRIES` in `tools/extract_quickref.py` name a PC **bookmark**; the text
  runs to the next bookmark, on the pages the two point at (`PC_SPLIT_HEADINGS` for headings the
  page breaks over two lines). `SHARED_ENTRIES` in `rulesets/ftpc/__init__.py` maps systems
  described together; `pdf_export` adds `armour_regen` and `stealth_hull` for those hull options.

## Catalog

- `data/catalog/fb_fb1.json` (FB1 pp.13-42: 57 NAC/NSL/FSE/ESU warships, 8 merchant and support
  vessels), `fb_fb2_kravak.json` (FB2 pp.12-19, 15 Kra'Vak warships and 1 merchant),
  `fb_fb2_savasku.json` (FB2 pp.26-32, 14 Sa'Vasku constructs),
  `fb_fb2_phalon.json` (FB2 pp.38-45, 15 Phalon classes),
  `ft2_core.json` (FT pp.14-15, 17 basic classes), `ft2_mt.json` (MT p.23, 14 designs),
  `fb_starranger.json` (341 designs from fullthrust.star-ranger.com, GZG-sanctioned interim
  stats: the FB1/FB2 powers plus ten human factions IJSF to OUDF; book "SR", page 0,
  `source.url` the page; `npv_book` 0 where the page prints none, then the gate checks only
  legality). Written by `tools/extract_catalog_starranger.py`, whose tables put counts first as
  the pages do. FB lists, and CD and PC adopt, a Star Ranger design only where it is legal
  unchanged under that ruleset (`store._adoptable`; FB 178, CD 239, PC 336 of 341). A name ending in `*` marks a design
  adjusted to fit the rules (owner's ruling: torpedo arcs trimmed to three, the IF Remora
  enlarged for 2-MASS enhanced sensors); its `npv_book` is the adjusted cost and its note says
  what the page printed (`common.printed_npv` words the adopted copies' notes); the Ship Design tab groups them as "Star Ranger" and links the NPV chip to the
  page (`common.WEB_SOURCES`).
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
  139 of the 141 book designs match their printed NPV; the two errata entries are the FT p.31
  design example and the FB2 p.18 Do'San. 52 Star Ranger designs are in errata too: 28 small
  hulls the pages price at 3 a box, five adjusted (`*`) designs left with unused MASS (legal in
  CD and PC only), the rest page misprints or systems the page leaves out.
- **Sa'Vasku and Phalon arcs come off the vector SSDs**, unlike Kra'Vak's. `ssd_arcs.py` has one
  reader per icon shape: `rings()` (human beams and Sa'Vasku stinger nodes), `pies()` (SM
  launchers and racks), `arrows()` (a Sa'Vasku pod launcher's arrowhead beside its cogged disc)
  and `stars()` (a Phalon pulser: a hexagon ringed by six triangles, white where the battery
  bears). What no icon shows cannot be read: Kra'Vak K-guns and Phalon plasma bolt launchers
  carry only a class number, so both take the arc the book's prose names (fore, and FP/F/FS).
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
`Start-Dev-Version.bat` is the owner's double-click launcher: it runs `app.py` on `PORT` (default
5000) and opens the browser unless `FTFM_NO_BROWSER` is set.

## Rules sources

`rulebooks/` holds the processed PDFs. Page numbers in code, data and PLAN are **printed** page
numbers. PDF page = printed + 1 for `Full Thrust.pdf` and `Full Thrust Cross Dimensions.pdf`,
= printed for the others. The FT2 book's text layer is OCR: verify numbers against the page
image (`page.get_pixmap(dpi=200)`).

- A ruleset's `books` are its **rules sources**: what a `book_url()` link points into and what
  the quick reference quotes. Books the app ships only to be read go in `REFERENCE_BOOKS`
  (`rulesets/__init__.py`) instead, so a code can never resolve a page reference into a book
  whose rules nothing implements. It is empty now: Cross Dimensions (`CD`) and Project
  Continuum (`PC`, errata `PCE`) were there until their rulesets made them rules sources. Both are free
  non-commercial publications distributed with GZG's agreement, credited in `NOTICE.md`.
  `app.books()` merges the two, rulesets winning a clash.
- A new PDF needs no spec or workflow change: `fleetmanager.spec` and `deploy-pages.yml` both
  take the whole `rulebooks/` folder. Verify its `page_offset` against a printed folio rather
  than assuming 0; `tests/test_rulebooks.py` checks the reference books' against pages 20
  and 30.

## Git and GitHub

- Work on `devversion`. **It is the only branch with source.** `main` carries just
  `README.md`, `LICENSE`, `NOTICE.md`, `.gitignore` and `.github/workflows/`, because GitHub
  only offers a `workflow_dispatch` workflow that exists on the default branch, and `main`
  is the default branch. Releases are tagged on `devversion`; nothing is merged into `main`.
  Never push to `main` without the owner.
- Because nothing is merged into `main`, a change to a file under `.github/workflows/` has
  to be copied to `main` deliberately, or the dispatchable copy goes stale. The checkout
  step takes its `ref` as an input defaulting to `devversion`, so a stale copy runs against
  good source and simply skips whatever steps it is missing.
- Commit per coherent step; each milestone issue is closed by the commit/PR that completes it.
- Commit messages end with the attribution line the harness provides.
- **A PR is not left waiting unwatched.** Master's standing rule is to merge once CI is green,
  so the session that opened a PR drives it to merged:
  - Subscribe to the PR, and whenever the turn ends with CI pending, also schedule a check-in
    (`send_later`, about 15 minutes, then longer). Never end a turn with your PR unmerged and
    nothing scheduled: a lost event must not stall the thread.
  - A job that failed before any test ran (checkout, `pip install`, `playwright install`,
    runner lost, a network error) is infrastructure: re-run the failed jobs once
    (`rerun_failed_jobs`) without asking. A second identical failure, or any failing test or
    lint, is real: fix it and push.
  - Green: merge `devversion` in if it moved, wait for that run, merge. Then say so.
  - Still stuck after two check-ins with no change: tell Master what it waits on, once.
- **Shipping** (version bump, exe, release, Pages deploy) has its own procedure in
  `.claude/skills/shipping-a-release/SKILL.md`. Read it when actually shipping and not
  before. Two things in it are easy to get wrong from memory: deploy Pages **last**, after
  the zip is attached, or the Windows badge stamps the previous version; and dispatch the
  workflow with `--ref devversion` as well as `-f ref=devversion`, or GitHub runs `main`'s
  copy of the workflow file.

## Testing

- Rules engines are built **test-first**, golden tests from PLAN 6.2/6.3 first.
- `tests/test_catalog_gate.py` must stay green: every catalog ship's recomputed points equal its
  printed NPV, or it is listed in `data/errata.json` with a real reason. Errata entries still check
  violations against their explicit `expected_violations` list (empty by default).
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

`fleetmanager-linux.spec` is the same build for Linux, made by `build-linux.yml` rather than
by hand: **onefile**, because one file to `chmod +x` is the easiest thing to hand a
non-technical user, and with `tray` excluded, since `main()` only reaches the tray icon on
win32 and pystray would drag in GTK/X11 backends the build cannot assume. Keep the two specs'
`datas` in step; the Linux workflow's smoke test is what catches a folder one of them forgot.
Dispatch it with a release tag to attach the tarball, or without one for a bare artifact.

Verifying a build: run the exe with `PORT` and `FTFM_DATA_DIR` pointed at a scratch dir, then
exercise it over HTTP. **It opens a browser tab on launch**, and that tab's heartbeat keeps the
idle watchdog from exiting, so stop a test instance by PID from the port (never by process
name), not by waiting for the watchdog.

## Web build (M13)

`python scripts/build_browser_bundle.py`, then serve a copy of what `deploy-pages.yml`
assembles: `web/index.html`, `web/bundle.json`, `static/`, `rulebooks/` in one folder
(`python -m http.server`). The deployed site has two levels: `web/landing.html` becomes the site
root (`index.html`) and the Pyodide app sits under `app/` with its `static/` and `rulebooks/`.
The landing page reads its logo and fonts from `app/static/`, so the site carries one copy.

Two steps finish the landing page and both run on every deploy:

- `scripts/build_preview_pages.py _site` writes `preview-design.html` and
  `preview-fleet.html`, the “See it in action” snapshots. They are **rendered from the real
  app through its test client**, so a preview cannot drift from the templates or the rules
  engine; the record sheet on them is the SVG `ssd_layout` actually draws. Sanitising rewrites
  `/static/` to `app/static/` and injects a script that inerts every form and internal link.
- `scripts/stamp_landing_page_versions.py _site/index.html` fills the version badges and the
  download links from the newest release carrying each platform's asset (`-win64.zip`,
  `-linux-x64.tar.gz`). The asset name carries the version, so the link is never hard-coded,
  and a platform with no release at all **loses its whole card** rather than publishing a vDEV
  badge over a dead button. An unreachable API changes nothing.

`tests/test_web_boot.py` boots the built site in headless Chromium and saves a fleet. It needs
Playwright and the network, so it is skipped unless `FTFM_WEB_BOOT=1`; the Tests workflow's
`web-build` job sets that.

Keep the `data-version-badge` / `data-download` / `data-platform-card` markers in
`landing.html`: `tests/test_landing_page.py` holds that contract, since a broken marker is
invisible until a deploy. Two web-only facts the desktop build hides:

- `bundle.json` is **text only**. Binary files the Python side opens (the PDF's TTFs) are
  fetched by the shell and written into the Pyodide filesystem under `/app`
  (`BINARY_ASSETS` / `copyBinaryAssets` in the shell). Add to that list when the app starts
  reading another binary file.
- Flask routes do not exist for anything outside the page: pdf.js must be pointed at
  `/rulebooks/<file>.pdf` in `BROWSER_MODE`, not at `/rulebook/<code>/file`.
- An inline binary response (the fleet PDF) is opened from a blob in a new tab; an attachment
  is downloaded.

Deployment is manual (`deploy-pages.yml`, workflow_dispatch) and belongs to the owner.
