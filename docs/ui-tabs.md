# UI: Ship Design, Fleet overview, rulebook viewer, layout and looks

Read before changing those routes in `app.py`, their templates, or `static/style.css`.

## Ship Design tab

- Routes: `GET /design` (library, no selection), `GET /design/<id>` (workbench),
  `POST /design/new`, `POST /design/<id>` with an `action` field. Catalog ids contain `:` and
  travel in the path unescaped, which Flask handles.
- **Edits go to a draft, not the library.** Strict mode refuses to save a violating design, so
  the workbench holds changes that are not saveable yet: `store.save_draft()` / `get_draft()` /
  `discard_draft()` under `drafts/`, and `working_design(id)` returns `(design, dirty)`. Saving,
  refitting, saving as a variant and deleting all clear the draft.
- The whole design posts with every action (`_apply_form`), so an edit is never lost by clicking
  Add system. Per-system inputs are named `sys-<uid>-<param>`; arcs are checkboxes plus a hidden
  `sys-<uid>-arcs-present` marker, because an all-unchecked arc set posts nothing. Remove buttons
  carry the uid in their `formaction` query, so the table needs no script.
- `store.add_system` re-sorts `systems` into the picker's order (stable, so one type keeps its
  add order); the picker remembers its last pick in `session["system_type"]`. It is one
  `<optgroup>` per ruleset group (`_system_groups`, ruleset order) with a filter box
  (`static/syspicker.js`: every typed word must appear in the option's `data-search`, Enter adds
  the first match, the text survives the autosave swap; hidden without script).
- Actions: `apply` (recalculate), `add_system`, `remove_system`, `save` / `refit` / `variant`
  (`store.save_design` modes), `discard`, `delete`, `make_variant`. Everything but
  `make_variant` is refused on a catalog design.
- The right pane is computed per request in `_design_context()`: breakdown, MASS bar against
  `derived["mass_limit"]`, NPV against the book value for catalog designs, issue list, and the
  live SSD as inline SVG (`Markup`, from `ssd_layout`).
- New designs start from a class preset (`rulesets/presets.py`, applied by
  `store.new_design(class_preset=...)`). A later MASS change that leaves the class band only
  re-classes the design (`presets.reclass` in `_apply_form`).
- `tests/test_design_tab.py` uses the `client` fixture with a per-test `FTFM_DATA_DIR`.

## Fleet overview tab

- Routes: `GET /fleet` (the current fleet, `?view=cards|roster|dock`), `GET /fleet/<id>` (select
  and redirect), `POST /fleet/new`, `POST /fleet/<id>/action`, `GET /fleet/<id>/check` (the
  tournament check of PLAN 7, which blocks nothing).
- **The current fleet lives in the Flask session** (`session["fleet_id"]`, falling back to the
  first fleet). `_inject_current_fleet()` is a context processor, so the top bar's selector,
  points meter, ruleset strip and non-conforming chip work on every tab.
- Fleet mutations go through `@register_action` handlers and `dispatch_action(fleet)`: the
  handler mutates the fleet dict via `store`, the route saves iff ok. That is the pattern for
  every state-changing form. `delete_fleet` is handled before dispatch because it has no fleet
  left to save.
- Views: cards per squadron (mini SSD with the ship's damage, status and squadron selectors),
  the roster table, and the Space Dock (`?view=dock&ship=<uid>`, the pick remembered per fleet in
  `session["dock_ship"]`): one ship's draggable diagram beside its design breakdown, a Refit
  select (`refit_ship` -> `store.refit_ship`, drops damage/loadout entries the new design lacks),
  "Refit as variant" (`store.refit_as_variant`, then opens the variant in Ship Design) and "Edit
  design". All use the same `ssd_layout` diagrams the PDF does.
- A ship's name and table ID are editable on its card; table IDs are unique per fleet,
  case-insensitive (`store._table_id_taken`, checked on add and on edit).
- Add ship lists only the fleet's faction's designs when it has one; the "Show all ships" toggle
  is a GET form (`all_ships`, a hidden 0 before the checkbox's 1) remembered in
  `session["all_ships"]`, so it survives the redirect after adding a ship.
- `tests/test_fleet_tab.py` covers the routes, the views, every badge row and the check page.

## Rulebook viewer

- `GET /rulebook/<code>?page=N` (the viewer page) and `/rulebook/<code>/file` (the bundled PDF).
  `book_url()` is a Jinja global, so every "FB1 p.16" in the UI is a link; page numbers are
  **printed** ones and the route adds the book's `page_offset`.
- pdf.js 4.6.82 (legacy build) is vendored under `static/pdfjs/`, Apache-2.0, licence alongside.
  Trimmed: no source maps, no locale, no cmaps, no debugger. It is excluded from the web bundle
  (served as plain files) and from `test_shell.py`'s remote-URL scan, because it is third-party
  code with URLs in comments that fetches nothing at runtime.
- The viewer is framed, so the security headers are `X-Frame-Options: SAMEORIGIN` and
  `frame-ancestors 'self'`; do not tighten them back to DENY without replacing the frame.
- The Settings tab writes `pdf_viewer` (`app` / `system`) and `paper`; with `system`, a page
  reference redirects to the file itself so the browser or the OS opens it.

## Layout, looks, tablets and phones

- `templates/base.html`: Layout C top bar (brand, fleet selector, tabs, points meter, Print
  button, ruleset colour strip; sticky except below 520 px tall and in print), flashes,
  `<main class="work cols-N">` grid.
- Looks: `<html data-theme>` from `settings["theme"]` (`store.THEMES`). Each look is a block at
  the end of `static/style.css` that redefines the variables and restyles colour, type and
  borders only; the unscoped rules are their shared base, not a look. Ship diagrams keep a light
  ground and the star map a dark sky in every look. `static/artwork.css` adds the illustrated
  palettes and theme covers from `static/themes/`; portraits are in `docs/SHIP-ARTWORK.md`.
- Widths: desktop (> 1100 px, panes side by side), tablet portrait (761-1100: Fleet overview
  keeps a 210 px left pane; Ship Design stacks with the library's books and New design form in
  columns and the diagram beside budget/issues under the workbench) and phones (<= 760: one
  column, Fleet overview's left pane last, static top bar, look picker hidden as it is in
  Settings). Hover effects go in `@media (hover: hover)`. Squadron drag reorder
  (`static/reorder.js`) uses HTML drag and drop for a mouse and its own pointer drag for
  touch/pen. Inline scripts in `base.html` and `web/index.html` add `maximum-scale=1` on iOS
  only, which stops focus zoom on small fields and still allows pinch zoom.
- Check layout changes at 820x1180, 1180x820 and 390x844 with touch emulation;
  `document.documentElement.scrollWidth` must equal the viewport.
