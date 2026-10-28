# Campaign tab and campaign module

Read before changing campaign code: `/campaign*` routes in `app.py`, the campaign half of
`store.py` and `fleet_rules.py`, `starmap.py`, `scenarios.py`, `forcegen.py`, `events.py`,
`static/campaign.js`. Step names (C1-C8, G1-G4) are PLAN 11's roadmap.

- `GET /campaign` (the current fleet), `POST /campaign/<id>/action`, `GET /dice/6`.
- Campaign maths is pure and lives in `fleet_rules`: `hull_boxes`, `crew_factors_left`,
  `ship_is_crippled`, `repairable_systems`, `repair_plan` (FT p.35: 1D6 hull a week at a base,
  up to three systems on 3+, a disabled drive needs two successes; ruling: each drive roll takes
  one of the three places; attempts and successes are recorded separately). `store` applies it:
  `set_ship_damage` (clamped to what the design has), `toggle_system_out`, `repair_ship`,
  `replenish_ship` (fighters, salvos and one-shot systems in one week).
- **Clicking the diagram**: every primitive carries a `ref` (`hull:7`, `armour:2`,
  `system:s3`), `to_svg()` emits it as `data-ref`, and `static/campaign.js` posts the ref of the
  shape that was clicked. Clicking the last marked box unmarks it. The fields under the diagram
  do the same thing, so the tab works with scripting off; the dice buttons are optional too.
- `static/keepscroll.js` (every page) keeps the scroll position across the reload a click
  causes: it notes the scroll on click/change/submit and restores it when the next page has the
  same `<html data-path>` (the web frame has no path of its own).
- Hooks reserved for the campaign module (PLAN 11.2) are in use but not repurposed:
  `ship.location`, `log[].week`, statuses `docked` and `hulk`.
- Campaigns (C1): `campaigns/<id>.json` holds name, ruleset, week, sides and a log; membership
  lives on the fleet (`campaign_id`, `campaign_side`), so a fleet is in one campaign at a time
  and every fleet in it shares the campaign's ruleset. The campaign bar posts fleet actions
  (`new_campaign`, `join_campaign`, `leave_campaign`) to `/campaign/<fleet>/action` and campaign
  actions to `/campaigns/<id>/action`. `.FTCampaign` exports the campaign with its fleets and
  their designs; backups carry `campaigns/`.
- Star maps (C2): `campaign["map"]` = {width, height, seed, systems [{q, r, name, kind
  settled|outpost|empty, owner side id or "", base}], draft}, normalised by
  `store.normalize_starmap`. `starmap.py` is pure: flat-topped hexes in odd-q offset coordinates
  (`hex_distance`, labels "0304" from 01), the seeded `generate()` (an app rule, G1: spacing,
  star names from a pool of 1200+ (proper names and Bayer designations) or catalogue numbers; up
  to 5 sides, each with exact counts of settled worlds, outposts and (optional) bases and a
  core-worlds toggle, plus neutral settled worlds and outposts placed none / random / border.
  **Counts are a hard rule** (Master 2026-10-22): `CountsError` when the stars can't hold them,
  never fewer. Homes at opposite ends, sides claim nearest stars in turn, then `claim_empty`
  gives bare stars inside a sphere to its side, front aside).
- `influence()` / `frontline()`: only settled worlds and outposts project; neutral clusters are
  `campaign["neutral_clusters"]`; hexes shaded when `map["frontline"]`. A side's sphere is the
  hexes within `campaign["front_reach"]` (default 4) of its systems, always outlined. Front
  hexes: ties between sides' nearest held systems, hexes beside another side's region, and a
  ring around neutral worlds' regions (their own hex, plus one more for a cluster within 3 hexes
  where every side is 2+ hexes further). In `to_svg()` every hex is an
  `<a href="/campaign?hex=q,r">`, so picking one needs no script. The map keeps a dark sky in
  every look.
- `.FTStarmap` files carry the map and the sides; loading one maps owners onto this campaign's
  sides by position. Settings > Import refuses them and points to the Star map panel. A
  generated map is a draft (`map["draft"]` holds its settings) that its inputs regenerate live
  with the same seed until Finalize (`finalize_starmap`; Master's exception to no-Save/Apply);
  `app.NEEDS_FINAL_MAP` actions refuse while it is a draft.
- Task forces (C3): `campaign["forces"]` [{id tf1.., side, name, q, r, order [q, r] or null,
  ships [{fleet, uid}]}], normalised by `store._norm_forces` (on a map, a known side, a ship in
  one force only). A force sits on a star system and jumps up to `FTL_HEXES_PER_WEEK` (6, FT
  p.35); `fleet_rules.force_reach` refuses a docked ship, a starbase or gate
  (`fleet_common.jump_blockers`), or ships without working FTL that the force's tender bays and
  tugs cannot carry. `store.next_week` carries out every order, sets each ship's `location` to
  the system name and logs a contact where sides meet (`store.meetings`); replacing the map
  clears the forces. Pennants and dashed order lines: `starmap.to_svg(forces=)`.
- Contacts (C4): `campaign["contacts"]` [{id k1.., week, q, r, sides, reports {side: {escort,
  cruiser, capital}}, choices {side: fight|withdraw|standoff|""}, roll, outcome
  battle|standoff|leave|escaped, leaving [sides], result side|"drawn", owner_before, notes}],
  normalised by `store._norm_contacts`. `next_week` opens one per meeting with each side's real
  scan (`fleet_rules.scan_counts`, the protocol's `scan_class`), which that side may change
  (decoys, weasel boats). Pure rules: `fleet_rules.contact_outcome` / `catch_roll_needed` (FT
  p.35). The last choice settles it; a won battle or a fleet that got away gives the system to
  the side left there (`store._claim`, an app rule, undone by `reopen_contact`). Next week
  refuses while a contact this week is unsettled, a battle is unrecorded, or a force that must
  leave has no order and can move. Only the current fleet's side sees its own choice before all
  are in.
- Bases and reinforcements (C5): with a star map, `store.yard_block` allows repairs and
  replenishment only for a docked ship in a task force at its side's naval base, and
  `repair_ship` once per campaign week (`ship["repaired_week"]`); without a map nothing is
  checked. `campaign["reinforcements"]` [{id rf1.., side, name, week, q, r, ships}] become task
  forces in `next_week` (`store._arrivals`) before contacts are found.
- Hidden movement (C6): `campaign["hidden"]`. The tab looks through `_campaign_view()`: the
  current fleet's side, behind a hand-over screen whenever that side changes
  (`session["campaign_seen"]`), or the umpire (`session["campaign_umpire"]`), switched by
  `POST /campaigns/<id>/view`. A side sees its own forces and those it is in contact with
  (`store.sees_force`), others' orders and reinforcements only without hidden movement, and log
  entries whose optional `sides` include it (`store.sees_log`). Other sides' ship lists are never
  shown. A force with `dummy` has no ships, jumps 6 and is removed with a log entry when it ends
  a week beside an enemy force (`store._exposed_dummies`).
- Objectives (C7): `campaign["objectives"]` {side: {count, include, draw [up to 2 tiers]}} (hold
  `count` settled systems with `include` among them, `starmap.holds`), `end_week` and `result`
  {winner side|"draw", week, text}. `next_week` judges the week just ended (`store._verdict`)
  before moving anything: an objective met wins; after `end_week` a draw tier draws, else the
  sides without objectives (the defenders) win. A result stops Next week until
  `reopen_campaign`. `store.lafayette_campaign()` sets up FT pp.36-38 from `LAFAYETTE` (map
  positions read off FT p.37); its force budgets go in the notes.
- Scenarios (G2): `scenarios.py` is pure; `build(kind, map, sides, attacker)` turns `invasion` /
  `raid` / `border_war` (all app rules) into owners, objectives, a last week and a note, and
  `store.apply_scenario` applies it in week 1 before any contact. `scenarios.home` is a side's
  first naval base, else settled world, else outpost. Objectives only measure holdings, so a
  template is a holding.
- Force generator (G3): `forcegen.pick` (pure) buys catalog designs for a budget, each pick in
  the least-used scan class that keeps every class at half the ships or less (FT p.37).
  `store.generate_forces` makes a new fleet for a side from `force_candidates` (the faction's FTL
  catalog warships), joins it to the campaign, forms a "Main fleet" force at the side's home and,
  with a garrison budget, one force per settled world it holds. The books print no non-FTL
  warships, so garrisons are FTL ships too.
- Weekly events (G4, app rules): with `campaign["events"]`, `next_week` rolls 2D6 per side on
  `events.py`'s table (`store._weekly_events`, before reinforcements arrive): unrest and pirates
  take an unguarded settled world or outpost, supply trouble closes the side's yards and a leak
  exposes its forces for that week (`campaign["effects"]`, read by `yard_block` and
  `sees_force`), late or early moves its next reinforcement. War weariness: a battle lost by a
  side with an objective takes a week off `end_week` (`contact["shortened"]`, undone by
  `reopen_contact`).
- Installations (C8) are ordinary fleet ships whose design `fleet_common.installation()`
  accepts: a starbase, a gate, or a design with neither FTL nor thrust (FT p.27; a PC monster
  ship `section` is not one). Placed in a task force on a system they never move and cannot be
  carried (PC p.116), the side cannot withdraw from a contact there, and a standing one is a
  repair yard for its side's docked ships there, itself included (`store.installations_at`,
  `yard_block`; an app rule beside FT p.35's naval bases).
