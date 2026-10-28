# tools/: catalog and quick-reference extraction

Scripts need `pymupdf` (requirements-dev) and run from the repo root. The three rulebook
pipeline files (`build_rulebooks.py` and friends, source folder set there) are excluded from
ruff and run by hand; the extractors only from E501 (one row per ship).

## Catalog (`data/catalog/`)

- `fb_fb1.json` (FB1 pp.13-42: 57 NAC/NSL/FSE/ESU warships, 8 merchant and support vessels),
  `fb_fb2_kravak.json` (FB2 pp.12-19, 15 Kra'Vak warships and 1 merchant),
  `fb_fb2_savasku.json` (FB2 pp.26-32, 14 Sa'Vasku constructs), `fb_fb2_phalon.json` (FB2
  pp.38-45, 15 Phalon classes), `ft2_core.json` (FT pp.14-15, 17 basic classes), `ft2_mt.json`
  (MT p.23, 14 designs), `fb_starranger.json` (341 designs from fullthrust.star-ranger.com,
  GZG-sanctioned interim stats: the FB1/FB2 powers plus ten human factions IJSF to OUDF; book
  "SR", page 0, `source.url` the page; `npv_book` 0 where the page prints none, then the gate
  checks only legality). Files are `{"schema_version": 1, "designs": [...]}`; ids
  `<ruleset>:<book>:<faction->name>`.
- **Generated, never hand-edited:** `extract_catalog_*.py` hold the curated ship tables and
  write the JSON; fix a ship there and re-run. The notation is documented in
  `catalog_common.py`. Default loadouts: standard fighters per bay/group, all-standard salvos;
  each ship's single magazine feeds all its launchers.
- Star Ranger (`extract_catalog_starranger.py`, tables put counts first as the pages do): FB
  lists, and CD and PC adopt, a design only where it is legal unchanged under that ruleset
  (`store._adoptable`; FB 178, CD 239, PC 336 of 341). A name ending in `*` marks a design
  adjusted to fit the rules (owner's ruling: torpedo arcs trimmed to three, the IF Remora
  enlarged for 2-MASS enhanced sensors); its `npv_book` is the adjusted cost and its note says
  what the page printed (`common.printed_npv` words the adopted copies' notes); the Ship Design
  tab groups them as "Star Ranger" and links the NPV chip to the page (`common.WEB_SOURCES`).
- How the tables were read: spec panels from the text layer (the FB1 script checks every
  TMF/NPV against the page); arcs from the vector SSDs by `ssd_arcs.py`; the rest (torpedo
  facing, submunitions, merchants, all of FT and MT) from rendered page images. FT2 beam
  pointers: up F, left P, right S; the FT capital classes' side A batteries cover two arcs, not
  three.
- `ssd_arcs.py` has one reader per icon shape: `rings()` (human beams and Sa'Vasku stinger
  nodes; white segments are covered arcs), `pies()` (SM launchers and racks), `arrows()` (a
  Sa'Vasku pod launcher's arrowhead beside its cogged disc) and `stars()` (a Phalon pulser: a
  hexagon ringed by six triangles, white where the battery bears). What no icon shows cannot be
  read: Kra'Vak K-guns and Phalon plasma bolt launchers carry only a class number, so both take
  the arc the book's prose names (fore, and FP/F/FS). **Kra'Vak arcs need no image pass**: the
  icon is a plain numbered hexagon (key on FB2 p.11), filled for a one-arc gun and outline for an
  all-arc one; the class fixes that and the prose names the arc as fore (FB2 pp.11, 13, 15).
- `tests/test_catalog_gate.py` (PLAN 8) judges each design with exactly the MT options it needs
  and must stay green: every ship's recomputed points equal its printed NPV, or it is in
  `data/errata.json` with a real reason (errata entries still check their explicit
  `expected_violations`, empty by default). 139 of the 141 book designs match; the two errata
  entries are the FT p.31 design example and the FB2 p.18 Do'San. 52 Star Ranger designs are in
  errata too: 28 small hulls the pages price at 3 a box, five adjusted (`*`) designs left with
  unused MASS (legal in CD and PC only), the rest page misprints or systems the page leaves out.

## Quick reference (`extract_quickref.py` -> `data/quickref/<ruleset>.json`)

- The heading table is inside the tool; re-run after editing it. The text is the book's own
  wording with a **printed** page reference (PLAN 2.5): **never paraphrase it by hand.**
- FT and MT are OCR over two-column pages, so extraction picks up figure captions, spec panels
  and half sentences: `clean()` repairs hyphenation (`LOST_HYPHENS`) and stray page numbers, and
  `OVERRIDES` holds entries transcribed from the page image where the layout defeats it.
  `tests/test_rulebooks.py` guards both the text and the page numbers.
- **FB2 repeats FB1's headings once per race** and `body_after()` keeps the longest body
  wherever it is, so a Kra'Vak key can silently resolve to the Phalon section: pin such an entry
  to its printed pages in the `PAGES` map, and check the page reference against the page image.
  Race entries are key-prefixed (`kv_kgun`, `sv_stinger`, `ph_pulser`).
- `CD_ENTRIES`: CD's headings are mixed case, so each entry names the next heading and a
  printed-page window instead; `gap_text()` restores the word spaces the justified text layer
  drops (glyph gap > 0.1 x font size) and skips the all-italic lines (the book's worked
  examples). That cleanup runs for CD only, so FB and FT2 output does not move.
- `PC_ENTRIES` name a PC **bookmark**; the text runs to the next bookmark, on the pages the two
  point at (`PC_SPLIT_HEADINGS` for headings the page breaks over two lines).
- `Ruleset.quickref()` filters the file to the systems present plus a few always-on entries, the
  fleet's optional rules and the races in the fleet. FB1's crew and fire-control entries are
  dropped unless a crewed race is in the fleet (a Sa'Vasku construct has neither); a mixed fleet
  still gets the FB1 entry for its human designs.
