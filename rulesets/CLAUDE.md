# Rulesets layer (`rulesets/`)

Loaded when you work under `rulesets/`. Per-ruleset detail is in `fb/`, `ft2/`, `ftcd/` and
`ftpc/` `CLAUDE.md`. Engines are built **test-first**, golden tests from PLAN 6.2/6.3 first.

- `rulesets/__init__.py`: dataclasses (`BookRef`, `Race`, `ParamDef`, `SystemDef`,
  `BreakdownRow`, `Breakdown`, `Issue`, `QuickRefEntry`), the `Ruleset` protocol, `RULESETS`,
  `register()`, `get_ruleset()`, `REFERENCE_BOOKS`. Rulesets register at the bottom of that file
  (they import the dataclasses, so the import has to come last).
- The protocol is PLAN 6.1 plus: `arcs` (the ruleset's arc names), `option_keys` (the fleet
  options it offers, in display order; `fleet_rules.option_label()` names them, and the fleet
  form, chips and PDF show only those), `loadout_points()` (fleet totals include loadouts, PLAN
  5.4), `fighter_types(options, race)` (loadout editor), `required_options(design, loadout)` (the
  MT toggles a design needs), `icon_set_for(race)`, `quickref(systems_present, options, races)`,
  `fleet_issues(fleet, [(ship, design)], options)` (rules that judge the whole fleet;
  `fleet_report` adds them to `fleet_issues`), `hull_kinds` (the Ship Design tab's "Hull kind"
  choices), `dummy_bogey_points` (0 offers none; `fleet_rules.fleet_points` adds the fleet's
  `dummy_bogeys` at that price), `morale_mass()`, `catalog_sources` / `adopt_design()`,
  `fighter_extras`, `gunboat_types` / `gunboat_extras`. `loadout=None` means the design's default
  loadout.
- **Races are additive modules inside a ruleset, never new rulesets** (PLAN 3 decision 3). A tech
  module is a plain module exposing the per-design half of the protocol (`system_defs()`,
  `design_breakdown`, `validate_design`, `loadout_points`, `damage_track`, `crew_factors`,
  `cf_positions`, `threshold_numbers`, `suggest_type`, `ICON_SET`, `FIGHTER_POINTS`, `CREWED`);
  `rulesets/fb/tech.py` maps race id -> module and `FBRuleset` dispatches every per-design call
  on `design["race"]`. An unknown race falls back to human rather than raising. Adding a race is:
  write the module, add it to `_TECH`, add its icon set to `ssd_layout`, add its catalog
  extractor and its quick-reference rows. Nothing above the ruleset layer knows races exist
  beyond passing one along.
- `design_breakdown().derived["mass_limit"]` is the MASS budget for the UI bar: FB must use
  exactly TMF, FT2 at most the system capacity (hull and drives take no MASS in FT2).
- `validate_design(design, options)` also flags More Thrust content whose fleet toggle is off in
  `options` (`mt_toggle_off`, `mass_over_100`), so fleet conformance is just validation with the
  fleet's options. A key absent from `options` (a design alone, as the Ship Design tab and
  `save_design` judge it) is only an `option_needed` info; `False` is the violation.
- The tournament check validates the ship's own loadout when it has one (`ship["loadout"]` in
  place of `default_loadout`), since that is what it carries and costs.
- `rulesets/common.py`: what more than one ruleset needs. Integer rounding (`round_half_up`,
  `pct_mass`: .5 up, never 0 MASS), arcs (`ARCS`, `arcs_valid`, `arcs_contiguous`),
  `split_rows`, `cf_positions`, the semi-untrusted readers (`as_int`, `systems_of`, `arcs_of`,
  `loadout_entries`), `half_turn_thrust`, labels (`hangar_label`, `hold_label`, `class_label`,
  `hull_descriptor`), `pick_class`, the salvo-missile check `validate_missiles`,
  `FIGHTER_BAY_TYPES`, `GUNBOAT_CARRIER_TYPES`, `convert_star_ranger`, `printed_npv`,
  `WEB_SOURCES`. **A ruleset imports shared pieces from here, never from another ruleset's
  `rules.py`**; only a race module reused across rulesets (FTCD's FB2 races) crosses packages.
  The FB modules keep their old underscore names as aliases. **Never compute percentages with
  floats**: 85 x 30% must be 25.5 exactly to round to 26.
- `rulesets/fleet_common.py`: fleet-level rules shared by FTCD and FTPC (riders, gates,
  `jump_blockers`, `installation()`, `fleet_issues()`); see `ftcd/CLAUDE.md`.
- `rulesets/presets.py`: class presets for new designs, built from each ruleset's class tables;
  `presets.reclass` re-classes a design whose MASS leaves its band.
- Rules code treats designs as semi-untrusted: bad numbers read as defaults (`_int`), unknown
  types cost nothing and raise a violation. Nothing in a ruleset raises on a malformed design.
- Labels and issue messages are translated at call time (`system_defs()` is a function for that
  reason). Breakdown `derived` holds `hull_descriptor`, `turn_thrust`, `damage_track`,
  `crew_factors`, `cf_positions`, `thresholds`, `holds`, `ftl_mass`, `drive_mass`, plus the
  sheet parts listed in `docs/ssd-layout.md`.
- Tests: `tests/test_rules_<ruleset>[_<race>].py` (golden designs, one test per costing rule
  and validator), `tests/test_rulesets.py` (protocol conformance), `tests/test_catalog_gate.py`.
  `docs/mockups/ssd.js` has a JS costing that agrees on 219 and 261; it is not the reference.
