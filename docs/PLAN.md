# Full Thrust Fleet Manager: Build Plan

This is the single source of truth for building the app. It was written after a full design
interview with the owner (GitHub `TheRealDeltrex`), so every decision in here is settled. If
something turns out to be impossible or clearly wrong while building, stop and ask the owner;
do not silently re-decide.

- **Repo:** `TheRealDeltrex/FullThrustFleetManager` (public, GPL-3.0)
- **Branches:** work on `devversion`, releases on `main`
- **Milestones:** GitHub issues labelled `milestone`, one per section 16 entry
- **Agent manual:** `CLAUDE.md` at the repo root (keep it current as you build)
- **Mockups:** `docs/mockups/` (serve the folder over HTTP; the pages load `ssd.js`/`mockup.css`)
- **Sister project to copy infrastructure from:** `E:\ClaudeCodeFolder\FrostgraveWarbandKeeper`
  (public repo `TheRealDeltrex/FrostgraveWarbandKeeper`)

Book abbreviations: **FT** Full Thrust 2nd ed., **MT** More Thrust, **FB1/FB2** Fleet Book 1/2,
**FTCD** Full Thrust: Cross Dimensions, **FTPC** Full Thrust: Project Continuum. Page numbers
are **printed** page numbers unless stated otherwise (FT: PDF page = printed + 1; MT/FB1/FB2:
PDF page = printed).

---

## 1. What the app is

A tool for everything a Full Thrust player does **between** games: design ship classes, build
fleets to a points limit, carry damage and losses through a campaign, and **print a fleet PDF**
that is used at the table (roster, ship record sheets, orders chart, trackers, quick reference).

Target devices: **PC with a printer** (primary), **tablet** (fallback, responsive layout).
Phones are not a target.

Two builds of the same code:

| Build | What | Offline |
|---|---|---|
| **Desktop** | Windows exe (PyInstaller), local Flask server + browser window, tray icon | **Must work fully offline.** Everything bundled, including rulebook PDFs. |
| **Web** | Same Flask app run in the browser via Pyodide, hosted on GitHub Pages | May need a connection. Behaves as much like desktop as reasonably possible. |

---

## 2. Principles (apply to every milestone)

1. **Offline first on desktop.** No feature of the desktop build may need network access.
   No CDN fonts or scripts in templates; vendor everything under `static/`.
2. **Strict by default, bookkeeping on request.** Designs are validated against their ruleset
   and cannot be saved while they break rules, unless the per-design checkbox
   "Allow rule-breaking (calculation-only bookkeeping)" is ticked. Points and MASS are always
   calculated by the rules engine and are never hand-editable.
3. **Conformance is computed, never flagged.** Whether a design or fleet is "non-conforming" is
   the result of running the validators, not the state of a checkbox (section 7).
4. **The ruleset is always visible.** Every fleet, design, card, list row and printed page
   shows which ruleset it belongs to (section 9.2).
5. **Original rulebook wording.** Quick-reference text on printouts uses the rulebooks' own
   wording, trimmed only where needlessly wordy, with a page reference. GZG publishes the core
   books as free downloads and sells miniatures; a tool that makes their game easier to play is
   in their interest. Do not "fix" this into paraphrase.
6. **Screen = paper.** The ship diagram (SSD) is produced by one layout engine that emits
   drawing primitives; the browser renders them as SVG and the PDF renderer draws the same
   primitives. What the player sees in the app is what prints.
7. **Rules are data + pure functions.** No rules maths in routes or templates.
8. **Translation-ready.** English only in v1, but every user-facing string (UI and PDF) goes
   through the translation layer (section 13). Game terms (MASS, NPV, Thrust) stay as the books
   spell them.
9. **Targeted tests routinely, full suite before a release** (section 15). The rules engine is
   built test-first.

---

## 3. Decisions log (from the design interview)

| # | Topic | Decision |
|---|---|---|
| 1 | Platform | Local desktop app + Pyodide web build on GitHub Pages |
| 2 | Book content | Catalog designs and rules wording ship in the public repo and web build. GZG gives the books away free (shop.groundzerogames.co.uk/rules.html) |
| 3 | v1 races | Human only. Tech-module structure in place so each alien race is additive |
| 4 | Rulesets | Selectable **FT2, FB, FTCD, FTPC** |
| 5 | Ruleset scope | Per fleet, fixed at creation; designs belong to one ruleset; very visible everywhere |
| 6 | v1 rulesets | **FB + FT2**. FTCD and FTPC after v1 works |
| 7 | Stack | New repo; copy and adapt Frostgrave infrastructure; Frostgrave's 4-layer architecture |
| 8 | Design storage | Global library per ruleset; fleets reference designs; catalog designs read-only (editing makes a variant); editing a used design asks "refit all N ships" or "save as variant" |
| 9 | Campaign | v1 = fleet-level bookkeeping; data shaped to grow into a full optional campaign module (map, invented rules allowed, random campaign generator) |
| 10 | SSD style | Per-ruleset icon sets on one shared layout engine |
| 11 | Catalog | Agent-extracted (arcs read from page images); failing test gate: every catalog ship recomputes to its printed NPV or is listed in `errata.json` |
| 12 | UI | Layout C (mockup `layout-c-dockyard-fleet.html`), responsive stacking; PC primary, tablet fallback, phone not a target |
| 13 | Language | English, translation-ready |
| 14 | PDF | Roster, record sheets, orders, trackers, quick reference; A4/Letter; blank copy; **battle pack in v1** |
| 15 | Files | JSON content, extensions `.FTFleet`, `.FTDesign`, `.FTBackup`; `schema_version` + migrations; web build shows a backup reminder |
| 16 | Enforcement | Strict mode default, per-design bookkeeping checkbox, tournament check, non-conforming badge on printouts |
| 17 | Non-conformance | Per design and per fleet; computed from violations only |
| 18 | Race/faction | Fleet picks a race at creation; race mixing needs a per-fleet checkbox. Faction is a label; catalog filters are the player's choice |
| 19 | Badges | `mixed-faction`, `custom-ships`, `non-conforming` (section 7) |
| 20 | Rulebooks | Processed PDFs bundled; page links open them locally (web: served as static files) |
| 21 | Offline | Desktop fully offline; web as close as reasonable |
| 22 | Handoff | PLAN.md + starter CLAUDE.md + milestone issues |
| 23 | Repo | Public, GPL-3.0, `devversion`/`main` |
| 24 | FT2 scope | FT2 core + More Thrust as per-fleet toggles |
| 25 | Loadouts | Default loadout in the design, overridable per ship |
| 26 | SSD layout | Arc-aware automatic layout in v1; drag-to-arrange later |
| 27 | Hull types | v1: warships, merchants, non-FTL, tugs/tenders, FT2 superships (MT toggle). Installations later with the campaign module |

---

## 4. Repository layout

The existing folder `E:\ClaudeCodeFolder\FullThrustFleetManager` is the repo. It already holds
`tools/` (rulebook build), `rulebooks/` (the four processed PDFs) and `docs/`.

```
FullThrustFleetManager/
  CLAUDE.md                 agent operating manual (keep current)
  README.md                 user-facing: what it is, run, build
  LICENSE                   GPL-3.0
  NOTICE.md                 GZG content notice (rulebook text, designs, PDFs are GZG's)
  requirements.txt          flask, fpdf2, Pillow, waitress, pystray
  requirements-dev.txt      pytest, ruff, pymupdf + pypdf (tools only)
  run_app.py                entry point (as Frostgrave)
  paths.py                  bundle dir vs user data dir; dev vs frozen; FTFM_BROWSER mode
  tray.py, idle_watchdog.py desktop only (copied from Frostgrave)
  i18n.py                   translation layer (section 13)

  rulesets/                 LAYERS 1+2: game data + pure rules, one package per ruleset
    __init__.py             registry RULESETS = {"ft2": ..., "fb": ...}; Ruleset protocol
    common.py               shared maths (rounding, damage-track split, CF dots)
    fb/
      data.py               system definitions, hull table, fighter types, books/page offsets
      rules.py              cost / mass / validation for FB designs
      icons.py              FB icon set: icon id -> primitive builder
      quickref.py           quick-reference entries (original wording + page refs)
    ft2/
      data.py, rules.py, icons.py, quickref.py
      mt.py                 More Thrust additions, active only with the fleet toggles
  fleet_rules.py            LAYER 2: pure fleet logic (totals incl. loadouts, conformance,
                            badges, tournament check, campaign maths)
  store.py                  LAYER 3: persistence + every mutation, returns (ok, msg)
  migrations.py             schema_version upgrades, one function per step
  ssd_layout.py             pure: (design, ruleset, damage?) -> primitives
  pdf_export.py             fleet pack + battle pack, draws primitives with fpdf2
  app.py                    LAYER 4: Flask routes, thin

  data/
    catalog/fb_fb1.json     FB1 human classes, generated by tools/extract_catalog_fb1.py
    catalog/ft2_core.json   FT2 basic classes (FT pp.14-15)
    catalog/ft2_mt.json     MT new general designs (MT pp.22-23), human only
    errata.json             catalog entries whose book NPV does not match the rules, with reason
    factions.json           built-in factions per ruleset (NAC, NSL, FSE, ESU, ...)
  rulebooks/                processed PDFs (bundled, also served by the web build)
  templates/, static/       Jinja + vendored CSS/JS/fonts (no CDN)
  translations/en.json      source strings (German later)
  tools/                    build_rulebooks.py, tocs.py, dedup_text.py, extract_catalog_*.py
  scripts/                  build_browser_bundle.py (web), release helpers
  web/                      Pyodide shell (index.html), deployed to Pages by CI
  tests/
  docs/PLAN.md, docs/mockups/
  .github/workflows/        tests.yml, deploy-pages.yml (as Frostgrave)
```

**Layering (strict, from Frostgrave):** `rulesets/*` (data + pure rules) → `fleet_rules.py`
(pure) → `store.py` (persistence/mutation) → `app.py` (routes). Each layer imports only from
layers above it. `ssd_layout.py` and `pdf_export.py` are pure consumers of layers 1-2.

**Copy from Frostgrave and adapt** (read its `CLAUDE.md` first): `paths.py`, `tray.py`,
`idle_watchdog.py`, `run_app.py`, `frostgrave.spec` → `fleetmanager.spec`,
`scripts/build_browser_bundle.py`, `docs/app/index.html` → `web/index.html`,
`.github/workflows/deploy-pages.yml`, the `@register_action` dispatch pattern in `app.py`, and
the release skill at `E:\ClaudeCodeFolder\.claude\skills\shipping-a-release` (make a sibling
skill for this app there; it lives outside the repo on purpose because it holds code-signing
setup).

---

## 5. Data model

All files are UTF-8 JSON with a top-level `"schema_version": 1`. `migrations.py` upgrades older
files on load; write the migration and its test in the same commit as any schema change. IDs are
short random strings (`uuid4().hex[:12]`); catalog ids are readable (`fb:fb1:nac-furious`).

### 5.1 Design (ship class)

```jsonc
{
  "schema_version": 1,
  "id": "a1b2c3d4e5f6",
  "ruleset": "fb",                    // "ft2" | "fb" | later "ftcd" | "ftpc"; fixed forever
  "race": "human",                    // tech module within the ruleset
  "faction": "NAC",                   // built-in id, custom faction id, or null
  "name": "Furious",
  "type_label": "Escort Cruiser",     // player's choice, app suggests from hull tables
  "type_code": "CE",
  "hull_kind": "warship",             // warship | merchant
  "tmf": 64,                          // total MASS
  "hull_boxes": 19,                   // FB; FT2 derives damage points from MASS
  "armour": 3,
  "thrust": 4,
  "ftl": true,
  "streamlining": "none",             // none | partial | full
  "systems": [                        // order = display order in lists
    {"uid": "s1", "type": "beam", "class": 3, "arcs": ["F"]},
    {"uid": "s2", "type": "beam", "class": 2, "arcs": ["F", "FP", "AP"]},
    {"uid": "s3", "type": "pds"},
    {"uid": "s4", "type": "screen", "level": 1},
    {"uid": "s5", "type": "hangar", "bays": 1},
    {"uid": "s6", "type": "sm_magazine", "capacity": 6, "feeds": ["s7"]},
    {"uid": "s7", "type": "sm_launcher", "arcs": ["FP", "F", "FS"]}
  ],
  "default_loadout": {                // section 5.4
    "fighters": [{"hangar": "s5", "type": "standard"}],
    "magazines": [{"magazine": "s6", "salvos": ["std", "std", "std"]}]
  },
  "allow_rule_breaking": false,       // bookkeeping checkbox; does NOT mean non-conforming
  "layout_hints": {},                 // optional icon positions (catalog; later drag layout)
  "source": {"kind": "catalog", "book": "FB1", "page": 16, "npv_book": 219},
                                      // or {"kind": "custom"} / {"kind": "variant", "of": "fb:fb1:nac-furious"}
  "notes": ""
}
```

FB arcs are six: `F, FS, AS, A, AP, FP` (fore, fore-starboard, aft-starboard, aft, aft-port,
fore-port). FT2 arcs are four 90-degree arcs, `F, S, A, P` (FT p.8), and no offensive weapon may
fire through `A` (owner decision after checking the page image; this line earlier said FT2 used the
six-arc model).

Catalog designs are loaded from `data/catalog/*.json`, never written, and are **read-only**.
Editing a catalog design creates a copy with `source.kind = "variant"`.

### 5.2 Fleet

```jsonc
{
  "schema_version": 1,
  "id": "f0e1d2c3b4a5",
  "ruleset": "fb",                    // fixed at creation
  "race": "human",                    // fixed at creation
  "allow_race_mixing": false,
  "faction": "NAC",                   // built-in id, custom faction id, or null
  "name": "7th Cruiser Squadron",
  "admiral": "R.Adm. A. Brigstone",
  "points_limit": 1500,
  "options": {                        // printed on the roster
    "core_systems": true, "rerolls": true, "fighter_endurance": true, "vector_movement": false,
    "mt_systems": false, "mt_superships": false, "mt_fighters": false   // FT2 only
  },
  "squadrons": [{"id": "sq1", "name": "Battle group"}, {"id": "sq2", "name": "Screen"}],
  "ships": [ /* 5.3 */ ],
  "campaign_id": null,                // reserved for the campaign module
  "log": [{"week": 4, "text": "Battle at Merril's; Vigil lost"}],
  "notes": ""
}
```

### 5.3 Ship (instance in a fleet)

```jsonc
{
  "uid": "sh1",
  "design_id": "fb:fb1:nac-furious",
  "name": "RNS Nashville",
  "table_id": "CE-1",
  "squadron": "sq1",
  "status": "damaged",                // ready | damaged | docked | hulk | destroyed
  "location": "",                     // free text now; campaign module later
  "loadout": null,                    // null = design default; else same shape as default_loadout
  "damage": {                         // persistent campaign state
    "hull": 6, "armour": 3,
    "systems_out": ["s3"],            // system uids knocked out
    "drive_hits": 0,                  // drives need two hits / two repairs
    "fighters_lost": {"s5": 2},       // per hangar
    "salvos_spent": {"s6": 1},
    "one_shot_used": []               // submunitions, SMRs, ...
  },
  "notes": ""
}
```

Crew factors lost are derived from `damage.hull` and the CF dot positions, never stored.

### 5.4 Loadout

A design's `default_loadout` sets fighter group types per hangar and salvo types per magazine or
rack. A ship's `loadout` overrides it wholesale (the UI copies the default when the player starts
editing). **Design NPV excludes loadout costs** (matches FB2 p.6 and the NPV gate); **ship and
fleet totals include them**. In FT2 the fighter group cost is part of the design (20 points incl.
bay, FT p.31); the loadout choice there is only the MT specialised fighter type (extra cost, MT
toggle).

### 5.5 Custom factions

```jsonc
{"schema_version": 1, "id": "cf1", "name": "Free Traders of Kappa-9"}
```
Stored in the user library; selectable as fleet faction and design faction.

### 5.6 File formats

| Extension | Content |
|---|---|
| `.FTFleet` | one fleet + every custom/variant design it uses (catalog designs by id) + the custom factions it uses. Self-contained for sharing and battle packs |
| `.FTDesign` | one design (+ its custom faction) |
| `.FTBackup` | zip of the whole user library (designs, fleets, factions, settings) |

All are JSON (the backup is a zip of JSON files). Import de-duplicates by id and asks before
overwriting a newer local copy.

### 5.7 Storage

- **Desktop:** user data dir from `paths.py` (e.g. `%APPDATA%\FullThrustFleetManager`):
  `designs/<id>.json`, `fleets/<id>.json`, `factions.json`, `settings.json`.
- **Web:** same files in Pyodide's in-memory filesystem, snapshotted to localStorage after each
  mutating request and restored at boot (Frostgrave's mechanism). A dismissable banner reminds
  the player to export a `.FTBackup`; it reappears after changes when no backup was exported in
  the last 14 days.

---

## 6. Rulesets

### 6.1 Ruleset interface

Each ruleset package exposes the same functions (a `Protocol` in `rulesets/__init__.py`):

```python
id: str; name: str; short_label: str; accent_color: str; books: list[BookRef]
races() -> list[Race]                              # v1: human only
system_types(race, options) -> list[SystemDef]     # what the Add-system picker offers
design_breakdown(design, options) -> Breakdown     # rows (label, mass, points), totals, derived values
validate_design(design, options) -> list[Issue]    # Issue(code, severity "violation"|"info", message, system_uid)
damage_track(design) -> list[int]                  # boxes per row
crew_factors(design) -> int; cf_positions(design) -> list[int]
threshold_numbers(design) -> list[int]
suggest_type(design) -> tuple[str, str]            # (label, code)
icon_set: IconSet; quickref(systems_present, options) -> list[QuickRefEntry]
```

`fleet_rules.py` never branches on a ruleset id; it calls the interface. Adding FTCD later means
adding a package and registering it.

### 6.2 FB ruleset (FB1 + FB2 amendments), human tech

Design procedure FB1 pp.10-11; hull boxes per FB2 p.3.

| Item | MASS | Points |
|---|---|---|
| Basic hull | TMF | TMF x 1 |
| Hull integrity | any number of boxes, min 10% of TMF (FB2 p.3); descriptor Fragile <15%, Weak 15-24, Average 25-34, Strong 35-44, Super 45+ | boxes x 2 |
| Armour | 1 per box | x 2 |
| Main drive | 5% TMF per thrust point | x 2 |
| FTL drive | 10% TMF (optional) | x 2 |
| Streamlining | partial 10% / full 20% | x 2 |
| Beam class 1 | 1, all 6 arcs | 3 |
| Beam class 2 | 2 for 3 adjacent arcs; 3 for 6 arcs | x 3 |
| Beam class N ≥ 3 | 2^(N-1) for 1 arc, +25% of that base per extra arc | x 3 |
| Pulse torpedo | 4 (1 arc), +1 per extra arc, max 3 arcs | x 3 |
| Needle beam | 2 (1 arc) | 6 |
| Submunition pack | 1 | 3 |
| SM launcher (SML) | 3 | 9 |
| SM magazine | 2 per standard salvo, 3 per ER salvo; each launcher fed by exactly one magazine | x 3 |
| SM rack (SMR) | 4 (standard) / 5 (ER) | 12 / 15 |
| PDS / FireCon / ADFC | 1 / 1 / 2 | 3 / 4 / 8 |
| Screen L1 / L2 | 5% / 10% TMF, min 3 / 6; extra generators 5% each, backups only | x 3 |
| Hangar bay | 1.5 x MASS carried; one fighter group bay = 9 | x 3 (+ craft) |
| Fighters (loadout, per group of 6) | | standard/interceptor 18, fast/attack/long-range 24, heavy 30, torpedo 36 (FB1 p.11, rules FB2 p.4) |
| Cargo / passengers / troops / labs | 1 per space | 0 |
| Nova cannon / Wave gun / MT missile / Ortillery | 20 / 12 / 2 / 3 | 60 / 36 / 6 / 9 |
| Minelayer / Minesweeper | 2 + 1 per mine / 5 | 6 + 2 per mine / 15 |
| Reflex field / Cloak | greater of 10 or 10% / greater of 2 or 10% | x 6 / x 10 |
| Tug FTL | 10% own TMF + 20% of towable MASS | x 2 |
| Tender bay | 1.5 x MASS carried | x 3 |

Derived rules:
- **Rounding** (FB1 p.10): percentages round .5 up, below .5 down; no system rounds to 0 MASS.
- **Damage track:** 4 rows, extra boxes in the upper rows (FB1 p.5).
- **Thresholds:** 6, 5, 4 at the end of rows 1-3; core systems roll at +1.
- **Crew factors** (FB1 pp.7-8): warship 1 per 20 TMF or part, merchant 1 per 50; DCP = CF. CF
  dots: step = ceil(boxes / CF), a dot every step boxes, the last dot in the last box.
- **Holds:** cargo/passenger/troop MASS split into 4 spaces, larger first.
- **Turn thrust:** floor(thrust / 2); thrust 1 may always turn 1.
- **Type suggestion:** FB1 p.12 table (SC 4-10 ... SDN 160+, carriers CVE/CVL/CVH/CVA).
- **Core systems** box is always drawn on FB SSDs; the fleet option decides whether it is used.

Violations (FB): MASS used ≠ TMF (over or under); hull boxes < 10% TMF; C1 not all-arc; C2 with
other than 3 adjacent or 6 arcs; arcs not adjacent where required; pulse torpedo > 3 arcs;
magazine not linked or launcher fed by two magazines; salvo load exceeding magazine space;
fighter loadout without a hangar. Infos (not violations): no fire control; no FTL ("system
defence ship"); screen generators beyond level 2 (backups only).

**Golden tests (must pass before anything else is built on FB):**
- FB1 pp.10-11 Heavy Cruiser example: TMF 85 → MASS 85, **290 points**.
- Furious (FB1 p.16): TMF 64, hull 19, armour 3, thrust 4, FTL, C3 (F), 2x C2 (3 arcs), C1,
  pulse torpedo (F), 3 PDS, 2 FC, ADFC, L1 screen → **219**.
- Vandenburg (FB1 p.16): TMF 80, hull 24, armour 5, thrust 6, FTL, C3 (3 arcs), 2x C2 (3 arcs),
  C1, 2 PDS, 2 FC, L1 screen → **261**.
- Damage track 19 → 5/5/5/4; 15 → 4/4/4/3; CF dots for 27 boxes / 5 CF → boxes 6, 12, 18, 24, 27.

`docs/mockups/ssd.js` contains a working JavaScript version of this costing that reproduces
219 and 261; use it as a cross-check, not as the source of truth.

### 6.3 FT2 ruleset (FT core + More Thrust toggles), human tech

Design procedure FT pp.29-31 (printed). Read those pages from `rulebooks/Full Thrust.pdf`; its
text layer is OCR, so verify every number against the page image.

| Item | Rule |
|---|---|
| Hull | "standard" (FT p.14 table) or "special" MASS up to 100 (above 100 only with the MT superships toggle) |
| Class | warship: escort ≤18, cruiser 19-36, capital 37-100; merchants one class |
| Hull cost | warship 2 x MASS, merchant 1.5 x MASS |
| Damage points | warship MASS / 2, merchant MASS / 4; odd results round **up** (owner decision; the book is silent) |
| System capacity | warship MASS / 2, merchant MASS / 10 (merchants: only C batteries, PDAF, L1 screens, submunitions; minimum 1 MASS of weaponry) |
| FTL | cost = MASS (uses no MASS) |
| Drives | points only, no MASS: escort 1 x MASS per 4 thrust, cruiser per 2, capital/merchant per 1; max thrust 8 |
| Beam A / B / C | MASS 3 / 2 / 1; points 4 / 3 / 2 **plus 3 / 2 / 1 per arc covered, including the first** |
| PDAF / ADAF | 1 / 3 MASS; 3 / 10 points |
| Screens | 3 MASS and 25 points per level (levels 1-3) |
| Fighter group incl. bay | 6 MASS, 20 points; carriers and dreadnoughts only |
| Needle beam / Pulse torpedo | 2 MASS 6 pts / 5 MASS 15 pts |
| Nova cannon | 16 MASS, 50 points, capital only |
| Submunition pack / Minelayer (3 mines) / Minesweeper | 1/3; 3/10; 5/20 |
| Fire controls | 1 escort, 2 cruiser, 3 capital, 1 merchant (FT p.15) included; extras 3 MASS, 10 points (FT p.31) |
| Damage track | escort 2 rows, cruiser 3, capital 4 (FT pp.10-12), extra boxes on the **lower** rows (FT p.12); thresholds 6, 5+, 4+ |

**More Thrust toggles** (fleet options; each enables system types and is printed on the roster):
- `mt_systems`: MT missiles, AA batteries (capital only), wave gun, ortillery, reflex field,
  cloaking field (MT pp.3-4). Take every cost from the page.
- `mt_superships`: MASS > 100, drives 2 x MASS per thrust, one extra fire control per full 50
  MASS over 100, one extra damage row per 50 MASS, thresholds stay 4+ from row 3 (MT p.22).
- `mt_fighters`: fast, heavy, interceptor, attack, long-range, torpedo fighters with MT's
  surcharges on top of the 20-point group (MT p.12). Take every value from the page.
- MT *play* rules (damage control, boarding, morale, etc.) appear in the quick reference only.

**Golden tests (FT2):**
- FT p.31 "Super Heavy Cruiser": special hull MASS 36, damage 18, FTL, thrust 4, L1 screen,
  3 PDAF, 2 A batteries (3 arcs), 3 B batteries (3 arcs) → **267 points**. The book's table
  total says 276, but the line items and the text both give 267; the table is a misprint. Put
  it in `errata.json` and test for 267.
- The FT pp.14-15 basic classes (courier 15 ... fleet carrier 687, merchants) are the FT2
  catalog gate. Some OCR'd values look inconsistent (battleship 447 vs battledreadnought 431);
  check each against the page image and record genuine book errors in `errata.json`.

### 6.4 Later rulesets (not in v1)

**FTCD** (`Full Thrust Cross Dimensions.pdf`, 64 pages, text layer present) and **FTPC**
(`project-continuum-full-thrust-version-1-1-4-april-20171.pdf`, 156 pages, plus the 8-page
errata of 26 April 2017; text layers present). Both need the rulebook treatment first
(bookmarks via `tools/tocs.py`, overprint check), and the errata folded into the FTPC ruleset.
Source folder: `E:\RPG\Tabletop\Full Thurst\`.

---

## 7. Conformance, badges and the tournament check

Computed by `fleet_rules.py` on demand; never stored.

**A design is non-conforming** if and only if `validate_design()` returns at least one
`violation`. `allow_rule_breaking` only permits *saving* such a design; a design saved in
bookkeeping mode that passes every check is conforming.

**A fleet is non-conforming** if any ship's design is non-conforming, **or** a fleet-level
violation exists:
- points total (NPV + loadouts, destroyed ships excluded) > `points_limit`
- a design of another race while `allow_race_mixing` is false
- a design of another ruleset (impossible through the UI; guard on import)
- More Thrust content while the matching FT2 toggle is off

Campaign damage and ship status never affect conformance.

**Badges** (fleet header, fleet list row, ship cards where relevant, PDF page headers, battle
pack):

| Badge | Shown when |
|---|---|
| **ruleset** (always) | e.g. `FB · Fleet Books` or `FT2 · Full Thrust 2nd ed.`, in the ruleset accent colour |
| **non-conforming** | the fleet is non-conforming. PDF: top-right corner of **every page** of that fleet: "⚠ Contains non-conforming ships, see roster"; offending ships marked on the roster |
| **mixed-faction** | the fleet has **no faction**, **or** any ship's design faction differs from the fleet faction (a custom design without a faction counts as different) |
| **custom-ships** | any ship uses a custom design or a variant of a catalog design |

Variants inherit the faction of the catalog class they came from. A custom-faction fleet built
only from custom designs assigned to that same custom faction shows `custom-ships` but not
`mixed-faction`.

**Tournament check:** a button on the fleet overview that lists every violation and info of the
fleet and each design, grouped by ship, with a link into the Design tab. It blocks nothing.

---

## 8. Catalog extraction and the NPV gate

v1 catalog: FB1 human classes (NAC, NSL, FSE, ESU, 57 warships; plus merchant and support
vessels from FB1 p.42 as far as they are specified), FT2 basic classes (FT pp.14-15) and MT's
new general designs (MT pp.22-23).

Process (one-off per book, scripts kept in `tools/` so it can be re-run):
1. Text extraction from the processed PDFs in `rulebooks/`: class name + type (13pt Faktos spans,
   see `find_ships()` in `tools/build_rulebooks.py`), the TMF/NPV box, and the TECHNICAL
   SPECIFICATIONS panel (hull integrity, armour, armament counts per class, defences, sensors,
   drives, hangars, crew factor).
2. **Arcs and anything only visible in the SSD** (arcs, magazine links, which battery is which)
   are read by the agent from rendered page images (`page.get_pixmap(dpi=200)`, cropped to the
   SSD box). There is no arc-entry screen in the app.
3. Book icon positions may be stored as `layout_hints` while looking at the images.
4. `tests/test_catalog_gate.py`: for every catalog design, `design_breakdown().points` equals
   `source.npv_book` and MASS used equals TMF, **unless** the id is listed in `data/errata.json`
   as `{"id", "book_value", "rules_value", "reason"}`. This test fails the build. An errata entry
   needs a real reason (book misprint, known erratum), never "could not make it match".

---

## 9. UI (Layout C)

Reference: `docs/mockups/layout-c-dockyard-fleet.html` (serve with
`python -m http.server 8765 --directory docs/mockups`). Visual language from Layout A: dark top
bar, light panels, blue accent, status colours (ready green, damaged amber, docked blue, lost
grey, violation red).

### 9.1 Shell

Top bar: app name, fleet selector, tabs **Fleet overview · Design · Campaign · Settings**, fleet
points meter (`used / limit`), **Print** button (opens the print dialog, 10.3).

### 9.2 Ruleset visibility

Each ruleset has a short label and an accent colour (FT2 amber, FB blue; later FTCD green, FTPC
purple). The fleet header shows a large ruleset badge; the fleet selector and fleet list prefix
every fleet with its badge; the Design tab header shows the design's ruleset badge; the top bar
carries a thin strip in the current fleet's ruleset colour. Every PDF page header carries the
ruleset label.

### 9.3 Fleet overview tab (home)

- Left pane: fleets list grouped by ruleset; squadrons of the current fleet (add, rename,
  reorder, move ships between squadrons).
- Header: fleet name, ruleset badge, race, faction, admiral, option chips, badges (section 7),
  **view switch Cards / Record sheet / Roster**, "+ Add ship", "Tournament check".
- Stat tiles: points (with bar), ships by status, hull damage awaiting repair, fighters/ordnance.
- **Cards:** per squadron, one card per ship (table id, status chip, name, class, mini SSD with
  damage, TMF / thrust / points). Destroyed ships greyed.
- **Record sheet:** the fleet exactly as PDF page 2 renders it (same layout engine), with ships
  that are not printed listed underneath.
- **Roster:** the PDF page 1 table.
- Clicking a ship anywhere opens its design in the Design tab, with that ship's damage selectable
  in the SSD preview.
- "+ Add ship": choose a design from the library or catalog (faction/type filters are the
  player's choice; none are applied automatically), name, table id (suggested from the type
  code: `CE-1`, `CE-2`...), squadron, loadout.

### 9.4 Design tab (Layout A workbench)

- Left: library tree (my designs by ruleset/faction; catalog by book/faction; search; opt-in
  filters).
- Centre: header (name, type, ruleset badge, source link like "FB1 p.16" that opens the rulebook
  at the page, "used by N ships", Save / Save as variant), hull & drives fields, systems table
  (system, arc picker, MASS, points, remove), "Add system" picker offering only what the
  ruleset, race and fleet toggles allow, loadout editor, notes.
- Right: live SSD preview (toggle: clean / each fleet ship using this design, with damage),
  budget (MASS used vs TMF bar, points, match against the book NPV for catalog designs), issues
  list (violations red, infos blue).
- **Strict mode:** Save is disabled while violations exist, unless "Allow rule-breaking
  (calculation-only bookkeeping)" is ticked. Ticking it shows a notice that the design counts as
  non-conforming for as long as it has violations.
- Saving a design used by ships asks: "Refit all N ships" or "Save as new variant".
- Catalog designs open read-only with a "Make a variant" button.
- New design: ruleset (preselected from the current fleet), race, faction (optional).

### 9.5 Campaign tab (v1)

- Per ship: status selector; damage entry by clicking the SSD (hull boxes, armour circles,
  systems, fighters, salvos); derived crew factors.
- Repair & resupply panel with an "at base" toggle and FT p.35 helpers: 1D6 hull per week; up
  to 3 systems per week on 3+; fully disabled drives need two successes; full replenishment in
  one week. Dice buttons are optional; results can always be typed in.
- Fleet log: entries with week number and text.

### 9.6 Settings

Default paper size (A4/Letter), rulebook viewer (in-app viewer vs the system PDF viewer, desktop
only), export / import, backup, language (English only for now), about / licence / GZG notice.

### 9.7 Responsive

Below about 1100 px width the panes stack: the left pane becomes a drawer, the right pane moves
under the centre. Targets: PC and tablet landscape. No phone-specific work.

---

## 10. Ship diagram (SSD) and the PDF

### 10.1 Layout engine (`ssd_layout.py`)

Pure function `layout(design, ruleset, damage=None, loadout=None, box="auto") ->
Diagram(width, height, primitives)`. Primitives: `rect, circle, line, path, text, icon(id, x, y,
state)`. Icon drawing comes from the ruleset's `icon_set`, so FT2 and FB sheets each look like
their own book (FT p.14 key and the FT p.48 record sheet; FB1 p.12 key and the FB1 p.47 record
sheet).

Arc-aware automatic placement (v1):
- fore-only or fore-centred weapons top centre; port-covering batteries in a left column,
  starboard-covering in a right column; aft-only at the bottom; all-round systems (C1, PDS,
  fire controls) in a central row; larger classes nearer the top;
- damage track below (FB: armour circle row, 4 rows with CF stars; FT2: 2/3/4 rows by class);
- bottom row: FTL, main drive with thrust, core systems box (FB), holds;
- damage state draws crosses on boxes, circles and systems (black in the PDF).

`layout_hints` in a design override positions (catalog may ship them; drag-to-arrange later).
The web page renders primitives to SVG; `pdf_export.py` renders the same primitives with fpdf2.
`docs/mockups/ssd.js` shows a working prototype of an FB-style diagram.

### 10.2 Fleet PDF contents

Reference: `docs/mockups/print-fleet-sheet.html`.

1. **Roster:** fleet name, ruleset badge, race, faction, admiral, points `used / limit`, ship
   counts, options in force (incl. MT toggles), badges; table of ID, name, class, type, TMF,
   thrust, FTL, status (+damage), source, points (NPV + loadout); non-conforming ships marked;
   notes.
2. **Record sheets:** boxes sized by damage-track width (small / medium / large, full width for
   very large ships), packed in rows, largest first; box header "ID · name · class TMF";
   campaign damage pre-marked. Docked, hulk and destroyed ships are left off (they stay on the
   roster).
3. **Orders chart:** ship ID x turns 1-10 with velocity columns (FB1 p.47 style).
4. **Fighter/ordnance tracker** (only if the fleet carries any): per fighter group 6 fighter
   boxes + CEF circles (6, or 9 for long-range), per magazine salvo boxes, one-shot systems.
5. **Quick reference:** only the systems present in the fleet, in the original rulebook wording
   (trimmed), with a page reference per entry; plus the ruleset's turn sequence.

Every page: header with fleet name and ruleset label; footer with app name, date, page x / y;
the non-conforming badge top right when applicable.

### 10.3 Print dialog

Sections on/off, paper A4 (default) / Letter, damage pre-marked on/off, include docked ships
on/off, **blank copy** (clean SSDs, no campaign state), **battle pack**: pick a second fleet
(own or an imported `.FTFleet`); both fleets must share a ruleset (warn otherwise); output =
roster + sheets + trackers for fleet 1, the same for fleet 2, one orders chart per fleet and one
shared quick reference.

Black and white, photocopy-safe, fonts bundled (no system-font dependency).

---

## 11. Campaign

### 11.1 v1 (bookkeeping)

Ship status, persistent damage, loadout usage, fleet log with week numbers, repair/resupply
helpers (9.5). Destroyed ships stay in the fleet (greyed, excluded from points) until deleted.

### 11.2 Hooks reserved now for the campaign module

`fleet.campaign_id`, `ship.location`, `log[].week`, statuses `docked` and `hulk`. Do not reuse
them for anything else.

### 11.3 Campaign module (after v1, optional for users)

A campaign object grouping fleets (own and opponents'), a star map (hex; FT p.34: 1 hex = 1 LY,
6 hexes per week), fleet movement, hidden movement / umpire mode, naval bases, repairs tied to
bases, reinforcements, **installations and segmented stations** (MT p.22), and a **random
campaign generator** (map, objectives, starting forces) for groups without a campaign of their
own. Rules beyond FT's outline may be invented; label them in the UI as "app rules".

---

## 12. Rulebooks in the app

- `rulebooks/*.pdf` (processed text layer + bookmarks, built by `tools/build_rulebooks.py` from
  the originals in `E:\RPG\Tabletop\Full Thurst\`) are part of the repo and bundled with the
  desktop build.
- Page links ("FB1 p.16") open the bundled PDF at that page. Desktop: an in-app viewer page
  (pdf.js vendored under `static/`, no CDN), with a setting to use the system PDF viewer
  instead. Web: the same viewer page; PDFs are served as static files next to the app on Pages
  (not inside `bundle.json`).
- Printed-to-PDF page offsets live in each ruleset's `BOOKS` (FT +1, the others 0).

---

## 13. Translation layer

`i18n.py` provides `_("...")` for Python and a Jinja global `_`; `translations/en.json` holds the
source strings; missing keys fall back to the key. Templates, flash messages, validation issue
messages and PDF labels all use it. No German in v1.

---

## 14. Web build

Copy Frostgrave's approach (`scripts/build_browser_bundle.py`): bundle Python modules,
templates, `data/` and `translations/` into `web/bundle.json`; `web/index.html` loads Pyodide,
installs Flask + fpdf2, unpacks the bundle, sets `FTFM_BROWSER=1`, drives the real Flask app
through its test client, and snapshots data to localStorage. CI (`deploy-pages.yml`) builds from
`devversion` and deploys `web/` plus `rulebooks/` and `static/` to Pages. PDF download works via a
Blob. Backup banner per 5.7. Read the browser-build section of Frostgrave's `CLAUDE.md` and its
bundle script docstring first (it documents a past bug where two copies of the shell diverged).

---

## 15. Testing

- **Rules engines test-first** (`tests/test_rules_fb.py`, `tests/test_rules_ft2.py`): the golden
  tests of 6.2/6.3 first, then one test per costing rule and per validator.
- **Catalog gate** (section 8), failing.
- **Conformance and badges** (`tests/test_fleet_rules.py`): every row of section 7, including the
  faction edge cases.
- **Migrations:** one test per migration step.
- **SSD layout snapshots:** primitives for 3 reference ships per ruleset stored as JSON; changes
  must be reviewed.
- **PDF smoke:** a fleet pack and a battle pack render; page count; the non-conforming badge
  appears exactly when expected; one visual check by rendering the pages to PNG and looking at
  them.
- **Web:** the bundle boots in headless Chromium and saves a fleet.
- **Routine work:** run only the tests for what changed. Full suite before a release and in CI.
- Lint with ruff.

---

## 16. Milestones (one GitHub issue each)

Each milestone ends with its tests green, `CLAUDE.md` updated, and the work committed on
`devversion`.

| # | Milestone | Done when |
|---|---|---|
| M1 | **Scaffold** | Repo layout of section 4; Frostgrave infrastructure copied and adapted (paths, run_app, tray, watchdog, spec); Flask shell with the Layout C top bar and empty tabs; i18n layer; vendored static assets; CI running tests + ruff |
| M2 | **Ruleset framework + FB rules engine** | `Ruleset` protocol + registry; `rulesets/fb` complete for human tech per 6.2; FB golden tests green |
| M3 | **FT2 + More Thrust rules engine** | `rulesets/ft2` + `mt.py` per 6.3 with toggles; FT2 golden test (267) green; costs verified against page images |
| M4 | **Catalog + NPV gate** | FB1 human classes, FT2 basic classes, MT general designs extracted; `test_catalog_gate.py` green with a justified `errata.json` |
| M5 | **Storage, library, import/export** | Data model of section 5; store mutations returning `(ok, msg)`; `.FTFleet` / `.FTDesign` / `.FTBackup` export and import; migrations framework; custom factions |
| M6 | **SSD layout engine + icon sets** | `ssd_layout.py` with arc-aware layout; FB and FT2 icon sets; SVG rendering in the app; snapshot tests |
| M7 | **Design tab** | Workbench per 9.4 incl. strict mode, bookkeeping checkbox, issues list, arc picker, loadout editor, refit/variant prompt, read-only catalog, source links (to the viewer from M11) |
| M8 | **Fleet overview tab** | Per 9.3: fleets with ruleset/race/faction, squadrons, three views, stat tiles, badges, tournament check, add ship |
| M9 | **PDF: fleet pack + battle pack** | Per 10.2/10.3; A4/Letter; blank copy; badges; quick reference in original wording for all v1 systems; visual check done |
| M10 | **Campaign bookkeeping** | Per 9.5 / 11.1; damage entry on the SSD; repair/resupply helpers; log; damaged SSDs print correctly |
| M11 | **Rulebook viewer** | Bundled PDFs, in-app viewer (vendored pdf.js), page links everywhere, setting for the system viewer |
| M12 | **Desktop packaging** | PyInstaller exe with tray; **verified fully offline** (network disabled: create a fleet, design a ship, print a PDF, open a rulebook page) |
| M13 | **Web build** | Pyodide build on Pages from `devversion`; localStorage persistence; backup banner; PDF download; rulebooks served statically |
| M14 | **v1.0 release** | Full test suite green; README; release per the adapted release skill; merge to `main`; tag `v1.0.0` |

---

## 17. After v1 (roadmap, rough order)

1. FTCD ruleset (rulebook processing, rules engine, catalog if the book has designs)
2. FTPC ruleset (incl. the 2017 errata)
3. Alien races per ruleset: FB Kra'Vak (FB2 pp.7-20), Phalon (pp.34-46), Sa'Vasku (pp.21-33);
   golden test: the FB2 p.11 Kra'Vak example = 384
4. Campaign module (11.3) with installations and the random campaign generator
5. Drag-to-arrange SSD layout
6. Tablet play mode (interactive SSDs instead of paper)
7. Guided (stepper) design mode for new players (see `layout-b-hangar-deck.html`, screen B2)
8. German translation
