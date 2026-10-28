# FTCD ruleset (`rulesets/ftcd/`): Cross Dimensions

- CD chapter 11, human tech. `data.py` (book, picker, CD p.42 classes), `rules.py` (costing,
  validation), `aliens.py` (FB2 races), `__init__.py`. Uses the shared helpers and missile check
  in `rulesets/common.py`, since CD is the Fleet Book design system gathered into one book; what
  CD changes is in `rules.py`'s docstring. Golden: the CD p.46 Heavy Cruiser is 294.
- Design fields `hull_advanced`, `drive_advanced`, `ftl_advanced` (normalised in `store`; other
  rulesets ignore them). An advanced hull has three rows (thresholds 6, 5) and is a standard
  hull below four boxes; an advanced drive turns its full thrust and its sheet icon is the "nA"
  hexagon, the advanced FTL a hexagon. Both come from `derived`, not a ruleset id.
- Broadside arcs are exactly `FS, AS, AP, FP`; they cost as three arcs (class-1/2 beams as six).
- Shell armour reuses `armour_layers` but costs 2, 4, 8 per box (doubling), not the Phalon
  2 x layer. MASS used may be under the total (CD p.42 "a maximum of"): a note, not a violation.
- **Fleet options drive points, so the Ship Design tab passes none**: the CPV hull cost and
  paying for advanced FTL apply to fleet totals only, and a system behind an option
  (`cd_optional_systems`, `cd_multistage`, `cd_super_weapons`) is an `option_needed` note there
  and an `option_off` violation only where a fleet has that option explicitly off.
- Quick reference: `CD_ENTRIES` in `tools/extract_quickref.py` (see `tools/CLAUDE.md`). Play
  rules with no system of their own are reached through keys `pdf_export` adds to the present set
  (`no_ftl`, `starbase`, `troop_hold`, `dummy_bogeys`) and `SHARED_ENTRIES` (in `__init__.py`)
  maps to entries; `fleet_morale` is on every sheet.
- Loadout extras (CD pp.25, 30, 47) live in the loadout, not the design, under optional keys
  `store._norm_loadout` keeps only when used: fighter `extras` / `swing`, magazine `stages`,
  top-level `craft` ({hangar, mass}). `derived["rich_loadout"]` makes the Ship Design tab draw
  one row per bay (`fighter-<uid>-<i>-type|ftl|kinetic|swing`), `craft-<uid>`, and per magazine
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
- Fleet-level rules (`rulesets/fleet_common.py`, shared with FTPC; the protocol's
  `fleet_issues`): a non-FTL ship is a battle rider (MASS 60 at most) and the fleet's live FTL
  ships must carry every rider, each in one tender bay or tug drive (an exact search, not
  first-fit; advanced-FTL tugs pool their transfer MASS, CD p.34). Over 60 it is a system defence
  ship and needs `cd_system_defence`, which also lifts the mothership check (CD p.35). Dummy
  bogeys (`fleet["dummy_bogeys"]`, CD p.37) cost 20, at most one per live ship, and need
  `cd_optional_systems`; the Fleet details form offers them as a dropdown.
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
  (FB and FT2 adopt nothing). `store._catalog()` calls it once per FB design: id
  `ftcd:<rest of the fb id>`. Every FB1 design costs its printed NPV unchanged. A design whose
  cost moves (the Kra'Vak, for their scatterguns) loses `npv_book` and says why in `notes`; the
  Si'Tek swaps one K-1 gun for an ADFC as p.21 says. The Ship Design tab groups the copies as
  "FB1 (FTCD)" etc., and the landing page's class count leaves them out.
