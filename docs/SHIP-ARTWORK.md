# Ship portraits and illustrated themes

Implemented 2026-10-19. No release or commit is implied by this working-tree implementation.

## What users can do

- Select **Orbital Foundry** or **Celestial Archive** in either existing theme picker.
- See ship portraits in Design, fleet cards and Campaign in all ten themes.
- Use **Change picture** on a design to set its shared picture, including a read-only catalog
  design. A fleet card's control changes only that particular ship in that fleet.
- Upload PNG, JPEG or WebP, choose a gallery picture, or reset to the inherited/default image.
- Download/restore a picture backup under Settings. The existing library export functions
  also include applicable portrait choices in design/fleet exports and full backups.

The version 2 set gives all 478 source designs distinct default portraits: 141 original
book designs and 337 Star Ranger designs. Ruleset adoptions share their source design's
picture. The 37 new 4 by 4 atlases also provide 46 refreshed custom choices, two per class
code. All 187 legacy portrait records and their atlas files remain available, so saved gallery
choices keep working. Uploaded pictures and explicit user choices retain priority.

The 23 custom class groups are SC, CT, FF, DD, DH, CL, CE, CH, CA, BC, BB, BDN, DN, SDN,
CVE, CVL, CVA, M, BASE, SECTION, JG, PT and GENERIC. `class_defaults` selects the versioned
first choice for each class; both new choices and legacy choices remain in the gallery.

## Provenance and limits

Images are generated interpretations, not official photographs or verified reconstructions
of every individual miniature. The faction directions use the ship illustrations in Fleet
Book 1 printed pages 13, 20, 27 and 34, and Fleet Book 2 pages 12, 26 and 38. These pages were
provided as visual references; record-sheet symbols and page layout were excluded from the
generation prompts. Civilian and generic FT2/MT art follows each ship's role. Paint schemes
are artistic choices, not rules or official faction specifications.

The publisher's [Full Thrust miniature range](https://shop.groundzerogames.co.uk/full-thrust-starships.html)
provided matched photograph references for 240 source designs, including interpreted variants.
The remaining 238 designs use invented faction-compatible hulls. Every new ship uses the approved
view 30 degrees above its port bow, bow toward lower-left and stern upper-right. Stations and
hull sections retain their appropriate geometry. These are generated interpretations, not exact
engineering reconstructions. Shop photographs are not bundled in the app.

Descriptively named original PNGs, generation prompts, per-cell source links and checksums are
saved in `E:\ClaudeOnlineFolder\Full Thrust Pictures\Miniature-Based-Uniform-View-v2`.
`Picture-Index.md` and `picture-map.json` there record the assignments. Original older pictures
and earlier drafts are preserved. `ARTWORK-PROMPTS.md` documents the original theme/portrait set;
the version 2 prompts accompany the new PNGs.

The SSD/PDF engine and catalog statistics were not changed. Portraits and theme banners do
not appear in the printed record sheets.

## Maintainable asset contract

- `data/ship_art.json` maps canonical design IDs to portrait IDs and defines each portrait's
  atlas file, zero-based cell, display metadata and class group. Catalog entries retain their
  existing IDs and data. No rule code depends on a portrait.
- Atlas files in `static/ships/` and banners in `static/themes/` are committed as WebP
  (quality 85), not PNG: the generated PNGs are about 3 MB each and would bloat the repo and
  the online build. Convert new art with Pillow before adding it.
- Atlas files in `static/ships/` have four equal columns and four equal rows. Cells are
  addressed by CSS, so there are no generated controls, captions or symbols. Assigned cells
  are unique; spare cells are not assigned as official ships. Do not rearrange a released
  atlas: existing IDs must keep their meaning. Add a new versioned file and update metadata
  when replacing artwork. A future catalog addition needs one mapping and an art cell, not
  a redesign of the screens.
- `_portraits.html` is the shared renderer. Theme-independent portrait layout lives at the
  start of `static/artwork.css`; the illustrated theme rules are scoped by `data-theme`.
  Theme banners are decorative HTML siblings of the working interface. Labels, tables,
  controls, validation and responsive layout remain normal HTML/CSS.
- Use `art_url` for bitmap paths: Flask uses `/static/`, the Pages iframe uses `static/`
  relative to its hosting project. `web/index.html` also rewrites relative theme CSS URLs.
- Portrait priority: fleet-instance override, design override, official default (including
  a direct official variant source), class default, generic default. A design reset restores
  its default; an instance reset restores its design picture. Official FB/CD/PC identities
  intentionally share design-level overrides.

## Uploads and persistence

User data is stored only under `paths.user_data_dir()/portraits.json`. It uses validated
target keys, a bundled portrait ID or a base64 JPEG, and a modification timestamp. Uploads
are decoded by Pillow, limited to 5 MB and 16 megapixels, oriented from EXIF, resized to fit
512 by 512, flattened against a dark ground and re-encoded without original metadata.
SVG and undecodable images are refused. Uploaded images are never inserted as executable
HTML. Filenames supplied by users are never used as disk paths.

Desktop persistence is an atomic JSON replacement. In the web build, the fleet snapshot
stays in localStorage, while portrait JSON is stored in IndexedDB `ftfm_artwork_v1`; a marker
in the fleet snapshot reconnects it on reload. A legacy inline portrait file migrates on
the next save. Failed IndexedDB restore blocks boot rather than silently overwriting the
saved collection. Browser storage is still device/browser-specific and subject to browser
eviction; Settings provides the portable picture backup. Picture backup restoration uses
the existing application request-size limit (16 MB).

Full backup and fleet/design import validate artwork and preserve newer local overrides by
default. Picture backups can explicitly replace newer pictures. Entries for removed ships
are retained in the artwork store; this permits restoring those ships from a backup.

## Validation

`tests/test_portraits.py` checks unique catalog coverage, two choices for every preset class,
asset existence, override precedence, upload rejection, catalog isolation, backup round trips,
explicit iframe form actions, and identical SSD SVG across all themes. `test_web_boot.py`
also checks IndexedDB gallery persistence when enabled. Manual automated-browser validation
exercised both illustrated themes, the existing Admiralty theme, gallery selection, upload,
reset and responsive layouts. A real Pyodide run verified uploaded-image persistence across
a full reload. Run targeted checks with isolated `FTFM_DATA_DIR`; never use a real library.
