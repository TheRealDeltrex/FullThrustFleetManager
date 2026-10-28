# FTPC ruleset (`rulesets/ftpc/`): Project Continuum

- PC section 13 (summary pp.118-124), human tech, errata (PCE) folded in. `data.py` (books,
  picker of ~80 systems in groups, fighter points, class table p.106), `rules.py` (`SYSTEM_RULES`
  type -> (mass_fn(s, design), points_fn(s, mass, design), label_fn)), `techbase.py`,
  `__init__.py`. Golden: the PC pp.113-114 heavy cruiser is 294. The FB2 races dispatch to their
  FB2 tech modules unchanged (errata: PC invalidates nothing in FB1/FB2), except that the CPV
  option reprices their basic hull as it does a human one (PC p.140).
- A holofield and a cloaking device each stand alone among `SCREENS_AND_FIELDS` (PC pp.60, 62);
  ECM is not in that set. A PC bay is one bay: `bays` is ignored in cost and capacity alike.
- Star Ranger systems PC lacks are in its picker as a "Star Ranger" group (`book="SR"`),
  `compact_superior_sensors` (2/30, beside PC's 4/16 superior sensors; owner's call) among them:
  `rocket_cannon` (as a beam), `amt` (2/8), `hdc` ((class x 8) - 4, x3, one arc), `age_penalty`;
  hull rows also offer 3 (x3; a hull of 3 boxes or fewer costs 2 a box). Adopted Star Ranger
  designs swap `lrpt` for the long-range torpedo, `mt_missile` for a heavy missile and superior
  sensors for the compact kind; their grasers become heavy grasers (high intensity unless the
  source disables rerolls), retaining the Star Ranger MASS and points table
  (`common.convert_star_ranger`; CD gets a class-2 torpedo). Their rules text is
  `data/quickref/sr.json` (hand-kept from the site, `url` per entry, `QuickRefEntry.url`): FB
  and PC quick references add it (`star_ranger_quickref`), `/rules/star-ranger` shows it all, and
  the Ship Design tab links a system to it.
- Design fields `hull_rows` (3/4/5/6: hull boxes x3/x2/x1.5/x1; an advanced hull is three rows
  at x3 and ignores it), `stealth_hull` (0-2, +2/+4 a hull and armour box), `armour_regen` (+2 a
  box). Normalised in `store`; the Ship Design tab draws them when `derived["pc_hull_options"]`.
  Rows past the third threshold on 4+.
- Shell armour costs 2 x layer as Phalon; screens are 5% a level with **no minimum**, which is
  why the FB1 Tibet costs 159 here. Broadside pairs (gatling/meson/pulser/TPA, SR K-1) are
  priced per pair (`_paired`); arcs need not be contiguous (p.45).
- Hangars: a `hangar_bay` (6 MASS) needs a `launch_tube`; the combined `hangar` (9) still
  exists. `common.FIGHTER_BAY_TYPES` lists every fighter-holding type for the loadout editor,
  the loadout reader and the PDF tracker. A ruleset's `fighter_extras` property names the
  per-group extras the loadout editor offers (FTCD ftl/kinetic, FTPC ftl/fast/long_range/heavy).
- A `turret` {arcs 2-6, mounts [weapon uids]} costs by the MASS it holds (`turret_mass`, PC
  p.46), edited as checkboxes like a magazine's feeds (`derived["turret_weapons"]`); removing a
  system drops it from every `feeds` and `mounts` list. A `fighter_rack` holds one wing that must
  carry the `robot` extra; `light` is an extra too (eight for the price of six, some types only).
- Gunboats (PC pp.79-82) are a loadout key `gunboats`: [{carrier, type, extras, ecm}], one
  squadron of six per `gunboat_rack` or `boat_bay` (`common.GUNBOAT_CARRIER_TYPES`); the
  `gunboat_types` / `gunboat_extras` properties drive the editor. Ruling: a squadron in a boat
  bay takes 24 craft MASS (MASS 4 a boat, p.80). A squadron may mix types (p.79): `types` lists
  all six boats (absent when uniform; `rules.boat_types()` reads both) and the per-squadron
  modifications cover all six. The editor is the `templates/_gunboats.html` macro, shared by the
  Ship Design tab's loadout and the Fleet tab.
- FTL gunboat squadrons need no carrier (p.80): `fleet["gunboat_squadrons"]` [{uid, type, ...}],
  FTL implied and paid (`rules.independent_squadron`). `fleet_rules.gunboat_squadron_points`
  adds them through the ruleset's `gunboat_squadron_points`, gated on `gunboat_types` like the
  loadout editor; `fleet_issues` validates them and counts them in the tech base. They are not
  ships: no card, no morale MASS, no dummy-bogey allowance; the PDF lists them on the roster and
  the tracker.
- The Imperial tech base (`techbase.py`, PC pp.125-127) is the fleet option `pc_tech_base`:
  `design_techs()` maps systems, hull options and loadouts to technologies,
  `with_prerequisites()` closes them, and `fleet_issues` reports the choices as an info and over
  `LIMIT` (10, the book's recommendation) or gunboats beside fighters as violations.
- A monster ship section is `hull_kind` "section" with `ship_mass` (the whole ship): its drives
  and FTL are sized on that (`drive_basis`, p.116), and fleet rules don't treat it as a rider.
- Options: `pc_optional_systems` (catapults, flawed design), `pc_adfc_no_mass`,
  `pc_hangar_criticals`, `pc_overload_torpedoes`, plus CD's. Fleet rules are CD's through
  `fleet_common.fleet_issues()`, except dummy bogeys need no option. The catalog is FB's adopted
  as `ftpc:` ids.
- Quick reference: `PC_ENTRIES` in `tools/extract_quickref.py` (see `tools/CLAUDE.md`).
  `SHARED_ENTRIES` in `__init__.py` maps systems described together; `pdf_export` adds
  `armour_regen` and `stealth_hull` for those hull options.
