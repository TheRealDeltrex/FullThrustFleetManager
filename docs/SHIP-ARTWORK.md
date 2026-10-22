# Ship portraits and illustrated themes

Current artwork contract, updated 2026-10-22.

## What users can do

- Select any of the eleven themes in either existing theme picker; every theme has its own cover.
- See ship portraits in Design, fleet cards and Campaign in all eleven themes.
- Use **Change picture** on a design to set its shared picture, including a read-only catalog
  design. A fleet card's control changes only that particular ship in that fleet.
- Upload PNG, JPEG or WebP, choose a gallery picture, or reset to the inherited/default image.
- Download/restore a picture backup under Settings. The existing library export functions
  also include applicable portrait choices in design/fleet exports and full backups.

Source catalog designs have default portraits. Ruleset adoptions share their source
design's picture. New miniature-class defaults intentionally share images across variants.
The photo-v6 defaults cover all 482 source catalog designs using 268 individual portraits.
Variants sharing a miniature hull intentionally share a picture. Faction-neutral FT2/MT
examples use an actual miniature of the matching hull class. There are two current choices
per custom class group: 38 refreshed miniature-based choices plus the eight retained special
facility/section/jump-gate/platform choices. All earlier gallery records remain available.
Explicit user choices and uploads retain priority over refreshed defaults.

The earlier arrow-corrected atlases and original Fleet Book Phalon set remain valid legacy
choices. New Phalon defaults use photographs of the actual miniatures; the older Fleet Book
set is not deleted or reinterpreted. No released atlas or portrait ID changes meaning.

The 23 custom class groups are SC, CT, FF, DD, DH, CL, CE, CH, CA, BC, BB, BDN, DN, SDN,
CVE, CVL, CVA, M, BASE, SECTION, JG, PT and GENERIC. `class_defaults` selects the current
first choice. Existing class gallery pictures remain available for old selections.

## Provenance and limits

The `photo-v6:` rollout replaces older interpretations with individual miniature-reference
portraits. Miniatures dictate hull architecture and proportions; their native camera angle
is retained rather than forcing a uniform direction. Slight casting bends are corrected using
longitudinal bow/stern alignment and transverse structural edges, accounting for perspective.
NSL geometry must remain crisp, straight and square; fixed nose guns align with the hull.
Miniature paint shading and tabletop lighting are discarded: surfaces are realized as clean
painted armour, bare metal, carbon composite and selective plating under sunlight. Any ageing
is subtle fading, without atmospheric grime or rust. Some fine detail is reconstructed from
small photographs; the images are not engineering-verified replicas.

Named miniature classes and their variants reuse the same image. If there is no named-model
photo, an available miniature from the same faction and hull class is preferred to invention.
Invented hulls are permitted only where that class has no miniature. `model` and `references`
record the chosen hull and sources. Three older Kra’Vak hulls (Lu’Dak, Do’San and Sha’Ken) use
manufacturer/Fleet Book
illustrations because usable model photographs were not located. Thirteen older Sa’Vasku
hulls use the manufacturer illustration to identify geometry in a fleet photograph; their
metadata declares the illustration view rather than claiming an exact photo angle. Existing IDs,
user choices and uploads
remain valid. The owner's later rendering feedback allows a further materials/lighting pass
where remaining miniature-like shading needs improvement.

Images are generated interpretations, not official photographs or engineering-verified
replicas. The publisher's [miniature range](https://shop.groundzerogames.co.uk/full-thrust-starships.html),
[Star Ranger](https://fullthrust.star-ranger.com/), and linked miniature galleries supply
shape references. Each portrait records its actual source URLs and model key. Fleet Book
illustrations are used only as explicitly identified geometry references, never as record
sheet decoration. Source-photo crops isolate a model from group photographs without
changing its geometry. Paint schemes are visual choices, not rules.

Only three new portraits are invented: the IF Remora scout and the unreleased OUDF
Jervis Bay/Brisbane hulls. Remora variants share their image. The OUDF source documents
that its master miniature was never released. Ettin reuses the FT1210 hull pictured as Ogre;
it is not a newly invented carrier. Three older Kra’Vak hulls are illustration reconstructions,
not invented replacements. Special custom facilities retain their earlier artwork.

Stands, mounting posts, bases, sprues, loose kit components and neighbouring models must
not become ship parts. Assembled photographs were found for KEYSTONE and KEROSENE;
their new portraits use those photographs rather than the unassembled-parts listings.

All generated PNGs, including discarded drafts, are preserved under
`E:\ClaudeOnlineFolder\Full Thrust Pictures`, organized by faction. A faction root holds
current portraits; `Discarded/` holds rejected and superseded versions. `References/`
holds source images, and `Prompts/` holds generation prompts. `Index.html` links per-faction
current and archive galleries. `Picture-Inventory.json` records checksums for every stored
PNG. Earlier review indexes are retained under `Documentation/Previous-Indexes/`.

The SSD/PDF engine and catalog statistics were not changed. Portraits and theme banners do
not appear in the printed record sheets.

## Maintainable asset contract

- `data/ship_art.json` maps canonical design IDs to portrait IDs and defines each portrait's
  atlas file, zero-based cell, display metadata and class group. Catalog entries retain their
  existing IDs and data. No rule code depends on a portrait.
- Atlas files in `static/ships/` and banners in `static/themes/` are committed as WebP
  (quality 85–90), not PNG: the generated PNGs are about 3 MB each and would bloat the repo and
  the online build. Convert new art with Pillow before adding it.
- Individual portraits are committed at most 512 pixels on the long side (WebP quality 85).
  The app shows them at 256 pixels or less, and the full-size generator output (about 250 KB
  each, 66 MB for 268) belongs in the picture library, not in the repo or the download.
- Atlas files normally have four equal columns and rows. Optional per-portrait `columns`
  and `rows` metadata supports other grids or a single image (1 by 1). Individual
  images use `background-size:contain` and centered positioning so a portrait/landscape
  canvas never stretches the ship to a square. The Valhalla legacy repair atlas is 3 by 3.
  `_portraits.html` computes background size and position from those dimensions, defaulting
    to 4 by 4 for every legacy record. Cells are addressed by CSS, so there are no generated
  controls, captions or symbols. Shared cells must identify the same
  `model`; spare cells are not assigned as official ships. Do not rearrange a released
  atlas: existing IDs must keep their meaning. Add a new versioned file and update metadata
  when replacing artwork. A future catalog addition needs one mapping and an art cell, not
  a redesign of the screens.
- `_portraits.html` is the shared renderer. Theme-independent portrait layout lives at the
  start of `static/artwork.css`; the illustrated theme rules are scoped by `data-theme`.
  Theme banners are decorative HTML siblings of the working interface. Labels, tables,
  controls, validation and responsive layout remain normal HTML/CSS. All eleven covers use
  the same responsive banner rule and a per-theme `--theme-cover` URL. Add or replace
  a cover without redesigning screens. Preserve the `url("themes/` spelling so the
  browser shell can rewrite it. Covers are hidden in print and excluded from SSDs/PDFs.
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

`tests/test_portraits.py` checks catalog coverage and intentional class sharing, two choices for
every preset class,
asset existence, override precedence, upload rejection, catalog isolation, backup round trips,
explicit iframe form actions, and identical SSD SVG across all themes. `test_web_boot.py`
also checks IndexedDB gallery persistence when enabled. Manual automated-browser validation
exercised both illustrated themes, the existing Admiralty theme, gallery selection, upload,
reset and responsive layouts. A real Pyodide run verified uploaded-image persistence across
a full reload. Run targeted checks with isolated `FTFM_DATA_DIR`; never use a real library.
