# Ship diagram (`ssd_layout.py`)

Read before changing `ssd_layout.py`, `static/ssddrag.js` or `templates/_ssd.html`.

- `layout(design, ruleset=None, damage=None, loadout=None, box="auto") -> Diagram(width, height,
  primitives)`. Pure. Primitives are frozen dataclasses (`Rect`, `Circle`, `Line`, `Path`,
  `Text`) in points with a top-left origin, so the screen and the paper use the same numbers:
  `to_svg()` renders them for the app, `pdf_export` renders the same tuple with fpdf2.
- Placement is arc-aware: `_side()` sorts each weapon into fore / port / starboard / aft /
  centre from its arcs, bigger classes first (`_weight`), then fore rows across the top, the
  side columns flanking a central block of all-round systems, aft weapons under it, the armour
  circles and damage track (stars on the crew-factor boxes), and a bottom row with FTL, the
  drive lozenge with its thrust, the FB core-systems box (beside the drive, no more than twice
  the FTL-to-drive gap away) and any holds or tug drives.
  Directly above the armour and hull boxes, bottom up: all fire controls in one row that never
  wraps (squeezed if needed), PDS after them when the row has room else in rows above, then
  hangars (`FIRE_CONTROLS` / `POINT_DEFENCE` / `HANGARS`).
- Master's packing rules: icons are packed by their real extent (`_icon_extent`, `_bbox`) with a
  small fixed gap, never spread across the band; the port and starboard columns hug the centre
  block. A weapon row is mirrored, smallest in the middle (two class-1 and two class-2 beams read
  2-1-1-2); larger-over-smaller only happens because rows wrap. Screens and other non-weapons
  get their own centre rows. Missiles and magazines (`MISSILES`) come last in the weapon space,
  magazines below launchers; a magazine wraps at 8 salvos a row. Every row of systems is centred
  (Master), the FTL/drive/core row too. Not systems, so not centred: the armour rows start on the
  left of the hit-point block (a centred block, rows left-aligned), and the Sa'Vasku thrust table
  and power box stay on the left.
- The sheet is cropped to what is drawn, evenly on both sides so the centre line stays central
  (`pdf_export._bounds` likewise, so rows sit mid-silhouette): `Diagram.left` is the crop's x
  offset (the SVG viewBox and `pdf_export` use it; anchors and hints stay in uncropped
  coordinates). `test_no_two_systems_overlap_on_any_catalog_sheet` guards overlaps.
  `layout_hints[uid] = {"x": .., "y": ..}` pins a system (the sheet grows to keep a pin on it).
- **Drag-to-arrange**: `Diagram.anchors` holds each icon's centre; `to_svg(..., draggable=True)`
  wraps each system in `<g class="sys" data-uid data-x data-y>`, `templates/_ssd.html`
  (`editable`) adds the hidden layout form and "Reset layout", `static/ssddrag.js` posts the drop
  through autosave to `POST /design/<id>/layout`. `store.set_layout_hint` saves at once (drawing,
  not rules): into a library design and its draft, or for catalog designs into `layouts.json`
  (merged by `get_design`, carried by backups). Used on the design tab and the Space Dock. On
  touch screens (`any-pointer: coarse`) a finger drags icons only while the diagram's "Arrange"
  toggle is on (client-side, kept across autosave swaps); otherwise it scrolls the page.
- Damage: a slash through each spent hull box and armour circle, a cross over dead systems and a
  damaged drive; black on paper. `damage=None` is a blank copy. Every primitive carries a `ref`
  (`hull:7`, `armour:2`, `system:s3`) that `to_svg()` emits as `data-ref` for the Campaign tab.
- Icons live in `ICON_SETS[<icon_set>]`, keyed by system type; a ruleset names its set per race
  (`icon_set_for(race)` -> `"fb"` / `"ft2"` / `"fb_kravak"` / `"fb_savasku"` / `"fb_phalon"`,
  falling back to the `icon_set` attribute) rather than drawing itself, because drawing is a
  consumer's job. A set may also supply `"main_drive"` and draw the drive itself, as `fb_kravak`
  does for the Advanced Grav Drive that FB2 p.9 says looks different and is written "4A".
- **Parts of a sheet that are not systems come from the ruleset's `derived`, never from a branch
  on the race**: `core_systems` (the B/L/P box; false for Sa'Vasku), `power_generators` (drawn
  at the damage-track row ends, over the rows the ship actually has, zeros omitted),
  `thrust_table` and `power` (the thrust table and the empty M/A/D/R box), `shell_layers` (one
  armour row per Phalon shell layer) and `pulser_modes` (the L/M/C letter in each pulser icon). A
  ruleset that derives none of them gets none of them, which is why FT2 and the human sheets did
  not change when they were added. `layout()` calls `design_breakdown()` once and also hands each
  icon its system's computed MASS, so an icon can print it (the Sa'Vasku screen node shows the
  power it needs). An unknown type falls back to a labelled box, so a new system never breaks a
  sheet. Boxed abbreviations take a callable so the label is translated at draw time.
- `box_size()` gives the sheet width band (small/medium/large/xlarge) the packed PDF sorts by.
- Portraits and theme art never replace record-sheet symbols; SSDs keep a light ground in every
  look.
- `tests/test_ssd_layout.py` covers placement, damage and the size bands, asserts every catalog
  design draws inside its own box, and holds SVG snapshots of 3 reference ships per ruleset in
  `tests/snapshots/`. Regenerate them with
  `.venv/Scripts/python.exe tests/test_ssd_layout.py --update` and read the diff: a changed
  snapshot means every record sheet changed.
