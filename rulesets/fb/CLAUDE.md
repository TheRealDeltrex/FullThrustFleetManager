# FB ruleset (`rulesets/fb/`): Fleet Books 1 and 2

- `data.py` (books, `system_defs()` for the picker, fighter points, FB1 p.12 classes, hull
  descriptors), `rules.py` (human tech: `SYSTEM_RULES` type -> (mass, points, label), breakdown,
  validation, derived values), `kravak.py` (FB2 pp.9-11), `savasku.py` (FB2 pp.21-25),
  `phalon.py` (FB2 pp.35-37), `tech.py` (the race -> module table), `__init__.py` (`RULESET`).
- A tech module declares `CREWED`: Sa'Vasku alone are False, and that decides whether FB1's
  crew and fire-control quick-reference entries belong on a sheet.

## System dicts

The design `systems` list; `uid` + `type` always: `beam` {class, arcs},
`pulse_torpedo`/`needle_beam`/`sm_launcher`/`nova_cannon`/`wave_gun` {arcs}, `submunition`
{arcs optional}, `sm_magazine` {capacity (MASS), feeds [launcher uids]}, `sm_rack` {load
std|er, arcs}, `screen` {level; >2 = backup generators}, `hangar` (one bay = one fighter group,
FB1 p.10; the picker offers no count, an older design's `bays` > 1 still costs 9 MASS a bay),
`tender_bay` {capacity = MASS carried}, `minelayer` {mines}, `tug_drive` {tow_mass}, `hold`
{kind cargo|passenger|troop|lab, mass}; no params: `pds`, `fire_control`, `adfc`, `mt_missile`,
`ortillery`, `minesweeper`, `reflex_field`, `cloak`.

Types only the Star Ranger catalog uses (not in the picker; `rules.SYSTEM_RULES`): `emp` and
`rocket_cannon` {class, arcs} cost as a beam; `graser` {class, arcs, no_reroll} (CD mass table,
x4, x3 without reroll); `hdc` {class, one arc}; `lrpt` {arcs}; `amt`, `superior_sensors`,
`enhanced_sensors` (2/8 as CD and PC); `age_penalty` {mass} is MASS lost to age at 0 points. FB
designs may also carry `hull_rows` 3/4/5/6 (boxes x3/x2/x1.5/x1; a hull of 3 boxes or fewer
always costs 2 a box) and `stealth_hull` 1-2 (+2/+4 a hull and armour box).
**The Fleet Books are closed (owner's ruling; CD too, only PC takes additions):** these are
costed only so the gate can check the Star Ranger pages, and `FBRuleset.validate_design` flags
each as `not_in_books`, a violation.

## Judgment calls (also in code comments)

The hull minimum is the *rounded* 10% (FB2 says FB1's Fragile designs stay legal); pulse
torpedo arcs must be adjacent ("traverse"), class 3+ beam arcs need not be; type suggestion
picks the FB1 p.12 band whose centre is nearest (ties to the smaller class), carriers from 2
fighter bays and MASS 80, never CVA; merchants suggest "Merchant" / "M" (no book code exists).

## Kra'Vak (`kravak.py`)

Hull, damage track, crew factors, thresholds, holds and tender bays are the human rules (FB2 p.9
says so), imported from `rules.py` rather than restated. What differs: the Advanced Grav Drive
costs 3 points per MASS (FB2 p.9, the one rule that makes the race); `kgun` {class, arcs} on the
FB2 p.9 MASS table (class 1 all six arcs, class 2 one or two adjacent, class 3+ exactly one, +3
MASS per class above 6) at 4 points per MASS; one-shot `mkp` {arcs, one} at 1/4 and
`scattergun` at 1/5; fire control 1/4; no screens (FB2 p.8), no ADFC (scatterguns area-defend
themselves, FB2 p.10), no salvo missiles, no beams. `turn_thrust` is the full thrust rating, not
half (FB2 p.9). Anything else raises `race_system`.

**FB2 prints "9 MASS and costs 18 points" for an alien fighter bay twice (pp.10 and 36) and is
wrong both times**: every design in the book prices a bay at the human 27 (Kra'Vak Lo'Vok 626,
Yu'Kas 883, Ko'San 917; Phalon Taanis 641, Draath 1002). The printed 18 is a fighter group's own
cost from the same page. Do not "fix" it back.

## Sa'Vasku (`savasku.py`)

Needed **no new schema**, and that is the point: biomass IS `hull_boxes` (1 MASS, 2 points,
four-row track, threshold at each row end), carapace IS `armour`, the FTL node is the ordinary
10% one. The main drive node is always 10% of MASS with no rating, so `thrust` is 0 and a
non-zero thrust is a violation; power generation is a system (`power_generator` {capacity})
carrying the total. Nodes: `stinger` {arcs, 3 contiguous}, `pod_launcher` {arcs, one},
`spicule`, `cortex`, `screen_node` (5% of MASS, min 3), `drone_womb`. A construct has **no crew
factors** (`crew_factors` is 0, no CF stars) and no core systems box.

- **The M/A/D/R power pools are not in the data model and must not be added.** They are
  rewritten every turn and do not carry over (FB2 p.22), so they are play state like movement
  orders: the sheet prints an empty box to write in. Drones are grown from biomass in play, so a
  drone group costs 0 points.
- The **thrust table** is derived (`derived["thrust_table"]`), not stored. FB2 p.21 says the
  power cost is "rounded up" and shows 9.6 -> 10, but it is **round-half-up with a floor of 1**:
  the Sa'Kess'Tha needs 1 PP at thrust 6 (1.32) and 2 at thrust 7 (1.54). Each row is the
  *highest* thrust its power pair buys. `extract_catalog_fb2_savasku.py` checks the derived table
  against every table printed in the book; twelve of the fourteen match to the cell.

## Phalon (`phalon.py`)

Closest to human: hull, drives, FTL, fire control, ADFC, hangars, tender bays and crew factors
come from `rules.py`. Own systems: `pulser` {arcs, 1/3/6 for 2/3/4 MASS, 5 points per MASS},
`plasma_bolt_launcher` {class, arcs (3 adjacent); 5 MASS per class, 3 points per MASS} and
`vapour_shroud` (5% of MASS, min 1, 3 points per MASS). No separate PDS: pulsers do that job
(FB2 p.35).

- **The shell is the one thing that needed schema.** Armour stacked in layers; a box costs
  `2 x layer number`, so a fourth-layer box costs 8 (FB2 p.35). `armour` keeps its meaning as
  the **total** box count (what the campaign damage clamp and the damage track use), and
  `armour_layers` holds the split, **inner layer first**. A design with no layers has the single
  layer every other race has. The sheet draws one row per layer with the outermost on top, which
  is also the order damage removes them, so shell box 1 is the first box of the top row.
- **The pulser L/M/C setting is a loadout entry, not design data** (FB2 p.35: chosen before each
  battle, never changed during one) and costs nothing: PLAN decision 25's default-in-design,
  overridable-per-ship pattern. The print dialog's `blank_pulsers` prints the icons empty, the
  way the book does.
