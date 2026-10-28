# FT2 ruleset (`rulesets/ft2/`): Full Thrust 2 + More Thrust

- `data.py` (books FT +1 / MT 0, arcs `F S A P`, FT p.31 table, FT p.14 basic classes),
  `rules.py`, `mt.py` (MT systems, supership rows/fire controls, fighter surcharges),
  `__init__.py` (`RULESET`, the picker; MT systems offered only with `mt_systems`).
- System dicts: `beam` {class A|B|C, arcs}, `needle_beam`/`pulse_torpedo`/`nova_cannon`/
  `aa_battery`/`wave_gun` {arcs, one arc}, `submunition` {arcs optional}, `screen` {level 1-3},
  `fire_control` (the first N per class are free, then 3 MASS/10 points), `fighter_group` (one
  group incl. bay; loadout `hangar` points at its uid), `tug_drive` (merchant, FTL x3); no params:
  `pdaf`, `adaf`, `minelayer`, `minesweeper`, `mt_missile`, `ortillery`, `reflex_field`, `cloak`.
  `hull_boxes`, `armour` and `streamlining` are FB fields; FT2 derives damage from MASS and flags
  armour or streamlining.
- Facts from the page images (the FT text layer is OCR): 4 arcs, no offensive fire aft (FT
  p.8); extra damage boxes go on the LOWER rows (FT p.12); merchants have 1 free fire control and
  4 rows at their size (FT p.15); non-FTL warships carry 75% (FT p.25); tugs pay FTL x3 (FT
  p.26); turn thrust rounds up (FT p.5). Odd fractions round up (owner: damage points; the rest
  follow, and the FT p.15 Survey Cruiser confirms it for merchant capacity).
