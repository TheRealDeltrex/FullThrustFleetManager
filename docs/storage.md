# Storage: `fleet_rules.py`, `store.py`, `migrations.py`, factions, files

Read before changing fleet maths, persistence, import/export or the schema.

- `fleet_rules.py` (pure): `fleet_options()`, `default_options(ruleset)` (what `create_fleet`
  starts with: gear and mechanics on, selection limits and alternative core rules off),
  `design_points()` / `ship_points()` (NPV plus the ship's loadout, its own or the design
  default) / `fleet_points()` (skips destroyed ships), `design_issues()`, `fleet_report()` (the
  tournament check: fleet issues + a `ShipReport` each), `badges()` (`non_conforming`,
  `no_faction`, `mixed_faction`, `custom_ships`; names from `badge_label()`), `ship_counts()`.
  Conformance is "no violation": campaign damage, ship status and `allow_rule_breaking` never
  enter into it. A ship also violates on `missing_design`, `wrong_ruleset`, `race_mixing`,
  `mt_toggle_off`; a fleet on `over_points` (a limit of 0 means no limit).
- `store.py`: everything that touches disk, plus every mutation. Mutators take the fleet dict,
  change it in place and return `(ok, msg)`; the route saves iff ok. `save_design(design, mode)`
  is the refit-or-variant decision: `save` refuses when ships use the design, `refit` rewrites it
  under them, `variant` writes a new id. Catalog designs are never written: their ids contain `:`
  so `_safe_id()` rejects them as file names too. Strict mode blocks saving a design with
  violations unless `allow_rule_breaking`; a blank `new_design()` is under its TMF, so tests that
  save one set that flag.
- **Normalisation is the trust boundary.** Everything read from the library or an import goes
  through `normalize_design()` / `normalize_fleet()`, which clamp types and drop junk and are the
  only place new fields are accepted. Add every new field there in the same commit.
- Export/import (PLAN 5.6): `.FTCampaign` (campaign + its fleets + their designs), `.FTFleet`
  (fleet + its non-catalog designs + custom factions), `.FTDesign`, `.FTBackup` (a zip of the
  library). `import_file()` returns `(ok, msg, conflicts)`; a *newer local copy* is kept and
  named in `conflicts`, and the caller re-calls with `overwrite_newer=True` after the player
  confirms. `modified` is an ISO string at second resolution, so tests that need "strictly
  newer" backdate the local copy. The whole file is read and checked (`_read_document` /
  `_read_backup`, raising `_Refused` or `TooNewError`) before anything is written; a backup entry
  that is not a usable design or fleet is skipped and counted.
- In the app: Settings > Files (`POST /backup`, `POST /import`), and an Export button on the
  Fleet tab and on a saved custom design (`/export/fleet/<id>`, `/export/design/<id>`). An import
  with conflicts is held in `pending_import.json` (`store.hold_import`) until the player answers
  Replace / Keep mine (`POST /import/held`). Downloads are plain `attachment` responses and links
  without a `download` attribute, so the web shell intercepts them. The web build shows a backup
  reminder (`BACKUP_DUE`, `store.backup_due()`: 14 days since the last backup or "Later").
- `migrations.py`: `CURRENT`, `STEPS[kind][from_version]`, `upgrade()`. A missing or malformed
  `schema_version` counts as 1; anything above `CURRENT` raises `TooNewError` and is refused
  rather than guessed at. Write the step and its test in the commit that bumps `CURRENT`.
- `data/factions.json` holds the built-in factions per ruleset, each with its race; custom
  factions (with the race they were made for) live in the user library and travel with exports.
  The Ship Design tab's faction pickers (`templates/_factions.html`, `static/factions.js`) offer
  "New faction" (`store.faction_for_name`), list a custom faction only once a saved design
  carries it (`store.faction_choices`), and hide custom and other races' factions by two toggles
  saved as the `show_custom_factions` / `show_other_race_factions` settings
  (`POST /settings/factions`).
- Settings: `settings["theme"]` is one of `store.THEMES` (default `full-thrust`; an unknown
  stored value falls back to it). `theme_chosen` marks a picked look: a stored `admiralty`
  without it is the old default and follows the new one. Portrait choices and uploads live in
  `portraits.json`, apart from catalog and design/fleet statistics (`docs/SHIP-ARTWORK.md`).
