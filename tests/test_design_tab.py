"""The Design tab (PLAN 9.4): library, workbench edits, strict mode, refit-or-variant."""

from __future__ import annotations

import re

import pytest

import app as app_module
import store

CATALOG = "fb:fb1:nac-furious"


@pytest.fixture(autouse=True)
def library(tmp_path, monkeypatch):
    monkeypatch.setenv("FTFM_DATA_DIR", str(tmp_path))
    return tmp_path


def make(client, name="Sentinel", ruleset="fb") -> str:
    client.post("/design/new", data={"ruleset": ruleset, "name": name})
    return next(d["id"] for d in store.list_designs() if d["name"] == name)


def fields(design: dict, **changes) -> dict:
    """The workbench posts the whole design, so every action carries the hull fields."""
    data = {
        "name": design["name"], "type_label": design["type_label"], "type_code": design["type_code"],
        "tmf": design["tmf"], "hull_boxes": design["hull_boxes"], "armour": design["armour"],
        "thrust": design["thrust"], "streamlining": design["streamlining"],
        "hull_kind": design["hull_kind"], "notes": design["notes"],
        "faction": design["faction"] or "",
    }
    if design["ftl"]:
        data["ftl"] = "on"
    if design["allow_rule_breaking"]:
        data["allow_rule_breaking"] = "on"
    data.update(changes)
    return data


# ---- Library and navigation --------------------------------------------------------------------


def test_the_tab_opens_with_the_catalog_and_no_selection(client):
    page = client.get("/design").get_data(as_text=True)
    assert "Pick a design from the library" in page
    assert "Furious" in page and "No designs yet" in page


def test_search_filters_the_library(client):
    page = client.get("/design?q=furious").get_data(as_text=True)
    assert "Furious" in page and "Vandenburg" not in page


def test_the_catalog_lists_by_faction_then_class_size_with_points(client):
    fb1 = app_module._library()["catalog"]["FB1"]
    factions = [d.get("faction") or "~" for d in fb1]
    assert factions == sorted(factions)  # factionless freighters last
    nac = [d["type_code"] for d in fb1 if d.get("faction") == "NAC"]
    assert nac.index("SC") < nac.index("DD") < nac.index("CH") < nac.index("BB") < nac.index("SDN")
    page = client.get("/design").get_data(as_text=True)
    furious = next(d for d in fb1 if d["id"] == CATALOG)
    assert f"{furious['type_code']} · {furious['points']} pts" in page
    assert "NAC" in page and "Civilian" in page


def test_every_catalog_design_has_a_class_code():
    """The FB2 hulls the book leaves unclassified take the class their MASS suggests, so the
    catalog can sort them by size."""
    assert all(d["type_code"] for d in store.catalog_designs())


def test_a_missing_design_is_a_404(client):
    assert client.get("/design/nope").status_code == 404


def test_creating_a_design_opens_it(client):
    page = client.post("/design/new", data={"ruleset": "fb", "name": "Sentinel"},
                       follow_redirects=True).get_data(as_text=True)
    assert "Sentinel" in page and "Design created." in page
    assert client.post("/design/new", data={"ruleset": "nope"},
                       follow_redirects=True).status_code == 200


# ---- Editing through drafts ---------------------------------------------------------------------


def test_edits_become_a_draft_and_do_not_touch_the_library_copy(client):
    design_id = make(client)
    saved = store.get_design(design_id)
    client.post(f"/design/{design_id}", data=fields(saved, thrust=6, action="apply"))
    assert store.get_design(design_id)["thrust"] == saved["thrust"]
    assert store.get_draft(design_id)["thrust"] == 6
    page = client.get(f"/design/{design_id}").get_data(as_text=True)
    assert "Unsaved changes" in page


def test_discarding_a_draft_restores_the_saved_design(client):
    design_id = make(client)
    client.post(f"/design/{design_id}", data=fields(store.get_design(design_id), thrust=6, action="apply"))
    client.post(f"/design/{design_id}", data={"action": "discard"})
    assert store.get_draft(design_id) is None
    assert "Unsaved changes" not in client.get(f"/design/{design_id}").get_data(as_text=True)


def test_adding_and_removing_systems(client):
    design_id = make(client)
    saved = store.get_design(design_id)
    client.post(f"/design/{design_id}", data=fields(saved, action="add_system", system_type="beam"))
    draft = store.get_draft(design_id)
    assert [s["type"] for s in draft["systems"]] == ["beam"]
    assert draft["systems"][0]["arcs"]  # a fresh weapon comes with a default arc

    uid = draft["systems"][0]["uid"]
    client.post(f"/design/{design_id}?uid={uid}", data=fields(draft, action="remove_system"))
    assert store.get_draft(design_id)["systems"] == []

    client.post(f"/design/{design_id}", data=fields(saved, action="add_system", system_type="nonsense"))
    assert "no such system" in client.get(f"/design/{design_id}").get_data(as_text=True)


def test_the_add_system_picker_keeps_the_last_pick(client):
    design_id = make(client)
    client.post(f"/design/{design_id}",
                data=fields(store.get_design(design_id), action="add_system", system_type="sm_rack"))
    page = client.get(f"/design/{design_id}").get_data(as_text=True)
    assert re.search(r'<option value="sm_rack"\s+selected>', page)
    assert not re.search(r'<option value="beam"\s+selected>', page)


def test_arcs_are_edited_as_checkboxes(client):
    design_id = make(client)
    client.post(f"/design/{design_id}",
                data=fields(store.get_design(design_id), action="add_system", system_type="beam"))
    draft = store.get_draft(design_id)
    uid = draft["systems"][0]["uid"]
    data = fields(draft, action="apply")
    data[f"sys-{uid}-arcs-present"] = "1"
    data[f"sys-{uid}-arcs"] = ["F", "FS"]
    client.post(f"/design/{design_id}", data=data)
    assert store.get_draft(design_id)["systems"][0]["arcs"] == ["F", "FS"]


@pytest.mark.parametrize("ruleset, system_type, value", [
    ("ftcd", "beam", "3"), ("ftcd", "graser", "2"), ("fb", "beam", "2"), ("ft2", "beam", "C"),
])
def test_a_weapons_class_is_edited_beside_its_arcs(client, ruleset, system_type, value):
    design_id = make(client, ruleset=ruleset)
    client.post(f"/design/{design_id}",
                data=fields(store.get_design(design_id), action="add_system", system_type=system_type))
    draft = store.get_draft(design_id)
    uid = draft["systems"][0]["uid"]
    page = client.get(f"/design/{design_id}").get_data(as_text=True)
    assert f'<select class="input sm" name="sys-{uid}-class">' in page   # always a dropdown
    assert f'name="sys-{uid}-arcs"' in page
    client.post(f"/design/{design_id}", data=fields(draft, action="apply", **{f"sys-{uid}-class": value}))
    assert str(store.get_draft(design_id)["systems"][0]["class"]) == value


def test_a_racks_load_and_stages_show_beside_its_arcs(client):
    design_id = make(client, ruleset="ftcd")
    client.post(f"/design/{design_id}",
                data=fields(store.get_design(design_id), action="add_system", system_type="sm_rack"))
    uid = store.get_draft(design_id)["systems"][0]["uid"]
    page = client.get(f"/design/{design_id}").get_data(as_text=True)
    assert f'name="sys-{uid}-load"' in page
    assert f'<select class="input sm" name="sys-{uid}-stages">' in page


def test_a_class_outside_the_list_stays_selected(client):
    design_id = make(client)
    client.post(f"/design/{design_id}",
                data=fields(store.get_design(design_id), action="add_system", system_type="beam"))
    draft = store.get_draft(design_id)
    uid = draft["systems"][0]["uid"]
    client.post(f"/design/{design_id}", data=fields(draft, action="apply", **{f"sys-{uid}-class": "8"}))
    page = client.get(f"/design/{design_id}").get_data(as_text=True)
    assert '<option value="8" selected>8</option>' in page


def test_an_open_ended_setting_lists_up_to_11_then_more(client):
    design_id = make(client)
    client.post(f"/design/{design_id}",
                data=fields(store.get_design(design_id), action="add_system", system_type="sm_magazine"))
    draft = store.get_draft(design_id)
    uid = draft["systems"][0]["uid"]
    key = f"sys-{uid}-capacity"
    page = client.get(f"/design/{design_id}").get_data(as_text=True)
    assert f'<select class="input sm" name="{key}">' in page
    assert '<option value="11" >11</option>' in page and '<option value="12"' not in page
    assert '<option value="more" >More</option>' in page and f'name="{key}-more" value=""' in page

    client.post(f"/design/{design_id}", data=fields(
        draft, action="apply", **{key: "more", f"{key}-more": "14"}))
    assert store.get_draft(design_id)["systems"][0]["capacity"] == 14
    page = client.get(f"/design/{design_id}").get_data(as_text=True)
    assert '<option value="more" selected>More</option>' in page
    assert f'name="{key}-more" value="14"' in page

    client.post(f"/design/{design_id}",
                data=fields(draft, action="apply", **{key: "more", f"{key}-more": ""}))
    assert store.get_draft(design_id)["systems"][0]["capacity"] == 14   # an empty field changes nothing
    client.post(f"/design/{design_id}", data=fields(draft, action="apply", **{key: "4"}))
    assert store.get_draft(design_id)["systems"][0]["capacity"] == 4


@pytest.mark.parametrize("ruleset", ["fb", "ftcd"])
def test_a_hangar_bay_holds_one_fighter_group(client, ruleset):
    """FB1 p.10, CD p.46: 9 MASS of bay per group of six, so a second group is a second bay."""
    design_id = make(client, ruleset=ruleset)
    for _ in range(2):
        design = store.get_draft(design_id) or store.get_design(design_id)
        client.post(f"/design/{design_id}", data=fields(design, action="add_system", system_type="hangar"))
    hangars = store.get_draft(design_id)["systems"]
    assert [s["type"] for s in hangars] == ["hangar", "hangar"] and not any("bays" in s for s in hangars)
    page = client.get(f"/design/{design_id}").get_data(as_text=True)
    assert page.count("Hangar bay (1 fighter group)") == 2 and f"sys-{hangars[0]['uid']}-bays" not in page


def test_a_bad_number_is_reported_not_raised(client):
    design_id = make(client)
    page = client.post(f"/design/{design_id}",
                       data=fields(store.get_design(design_id), tmf="lots", action="apply"),
                       follow_redirects=True).get_data(as_text=True)
    assert "valid number" in page


# ---- Strict mode ---------------------------------------------------------------------------------


def test_save_is_blocked_while_the_design_breaks_the_rules(client):
    design_id = make(client)
    saved = store.get_design(design_id)          # a blank hull is under its TMF
    page = client.get(f"/design/{design_id}").get_data(as_text=True)
    assert 'value="save"' in page and "disabled" in page

    page = client.post(f"/design/{design_id}", data=fields(saved, action="save"),
                       follow_redirects=True).get_data(as_text=True)
    assert "breaks the rules" in page


def test_bookkeeping_mode_allows_the_save_and_warns(client):
    design_id = make(client)
    data = fields(store.get_design(design_id), action="save", allow_rule_breaking="on")
    page = client.post(f"/design/{design_id}", data=data, follow_redirects=True).get_data(as_text=True)
    assert "Design saved." in page
    assert "non-conforming for as long as" in page
    assert store.get_design(design_id)["allow_rule_breaking"] is True
    assert store.get_draft(design_id) is None    # saving clears the draft


# ---- Catalog, variants and refit -------------------------------------------------------------------


def test_a_catalog_design_is_read_only_and_offers_a_variant(client):
    page = client.get(f"/design/{CATALOG}").get_data(as_text=True)
    assert "cannot be edited" in page and "Make a variant" in page

    blocked = client.post(f"/design/{CATALOG}", data={"action": "apply", "tmf": 5},
                          follow_redirects=True).get_data(as_text=True)
    assert "read-only" in blocked
    assert store.get_draft(CATALOG) is None

    page = client.post(f"/design/{CATALOG}", data={"action": "make_variant"},
                       follow_redirects=True).get_data(as_text=True)
    assert "Variant created." in page
    variant = next(d for d in store.list_designs())
    assert variant["source"] == {"kind": "variant", "of": CATALOG}


def test_saving_a_design_ships_use_offers_refit_or_variant(client):
    design_id = make(client)
    data = fields(store.get_design(design_id), action="save", allow_rule_breaking="on")
    client.post(f"/design/{design_id}", data=data)

    fleet, _msg = store.create_fleet("fb", "Home Fleet")
    store.add_ship(fleet, design_id)
    store.save_fleet(fleet)

    page = client.get(f"/design/{design_id}").get_data(as_text=True)
    assert "Used by 1 ships" in page and "Refit all 1 ships" in page and 'value="variant"' in page

    saved = store.get_design(design_id)
    client.post(f"/design/{design_id}", data=fields(saved, action="variant", thrust=6,
                                                    allow_rule_breaking="on"))
    assert len(store.list_designs()) == 2
    assert store.get_design(design_id)["thrust"] == saved["thrust"]

    client.post(f"/design/{design_id}", data=fields(saved, action="refit", thrust=6,
                                                    allow_rule_breaking="on"))
    assert store.get_design(design_id)["thrust"] == 6


def test_deleting_a_design(client):
    design_id = make(client)
    page = client.post(f"/design/{design_id}", data={"action": "delete"},
                       follow_redirects=True).get_data(as_text=True)
    assert "Design deleted." in page
    assert store.get_design(design_id) is None


def test_an_unknown_action_is_refused(client):
    design_id = make(client)
    page = client.post(f"/design/{design_id}", data=fields(store.get_design(design_id), action="dance"),
                       follow_redirects=True).get_data(as_text=True)
    assert "Unknown action." in page


# ---- The right-hand pane ----------------------------------------------------------------------------


def test_the_workbench_shows_the_ssd_budget_and_issues(client):
    page = client.get(f"/design/{CATALOG}").get_data(as_text=True)
    assert "<svg viewBox=" in page                      # live SSD
    assert "NPV" in page and "MASS" in page             # budget
    assert "Book NPV 219" in page                       # the printed value for the Furious
    assert "No issues: this design is legal." in page


def test_the_ruleset_badge_is_on_the_design_header(client):
    assert 'badge rs-fb' in client.get(f"/design/{CATALOG}").get_data(as_text=True)
    ft2 = client.get("/design/ft2:ft:courier").get_data(as_text=True)
    assert 'badge rs-ft2' in ft2


# ---- Races (FB2 alien tech modules) ------------------------------------------------------------


def test_new_design_form_offers_every_race_grouped_by_ruleset(client):
    body = client.get("/design").get_data(as_text=True)
    assert 'name="race"' in body
    assert "Kra&#39;Vak" in body or "Kra'Vak" in body


def test_a_new_design_inherits_the_current_fleets_race(client):
    client.post("/fleet/new", data={"ruleset": "fb", "name": "Clan raid", "race": "kravak"},
                follow_redirects=True)
    resp = client.post("/design/new", data={"ruleset": "fb", "name": "Test hull"},
                       follow_redirects=True)
    assert resp.status_code == 200
    design = next(d for d in store.list_designs() if d["name"] == "Test hull")
    assert design["race"] == "kravak"


def test_a_new_design_defaults_to_the_current_fleets_faction(client):
    client.post("/fleet/new", data={"ruleset": "ftcd", "name": "Rim patrol", "faction": "NSL"})
    body = client.get("/design").get_data(as_text=True)
    assert '<option value="NSL" selected' in body
    client.post("/design/new", data={"ruleset": "ftcd", "name": "Picket", "faction": "NSL"})
    assert next(d for d in store.list_designs() if d["name"] == "Picket")["faction"] == "NSL"


def test_the_workbench_sets_the_faction_and_saving_keeps_it(client):
    design_id = make(client, ruleset="ftcd")
    assert 'name="faction"' in client.get(f"/design/{design_id}").get_data(as_text=True)
    client.post(f"/design/{design_id}", data=fields(store.get_design(design_id), action="save",
                                                    faction="ESU", allow_rule_breaking="on"))
    assert store.get_design(design_id)["faction"] == "ESU"


def test_saving_a_catalog_variant_keeps_the_class_faction(client):
    """The workbench used to have no faction field, so every save cleared it."""
    variant, _msg = store.make_variant(CATALOG)
    client.post(f"/design/{variant['id']}", data=fields(variant, action="save",
                                                        allow_rule_breaking="on"))
    assert store.get_design(variant["id"])["faction"] == "NAC"


def test_the_add_system_picker_follows_the_designs_race(client):
    created, _msg = store.new_design("fb", "kravak", "KV", "Hunter")
    body = client.get(f"/design/{created['id']}").get_data(as_text=True)
    assert "K-gun" in body and "Scattergun" in body
    assert "Salvo missile launcher" not in body  # human tech, not offered here


def test_a_kravak_catalog_design_is_listed_under_its_race(client):
    body = client.get("/design").get_data(as_text=True)
    assert "Lo&#39;Vok" in body or "Lo'Vok" in body
    assert "FB2" in body


def test_the_picker_offers_savasku_nodes_for_a_savasku_design(client):
    created, _msg = store.new_design("fb", "savasku", "SV", "Construct")
    body = client.get(f"/design/{created['id']}").get_data(as_text=True)
    assert "Stinger node" in body and "Power generators" in body
    assert "K-gun" not in body and "Beam battery" not in body


def test_a_savasku_design_shows_power_instead_of_a_thrust_field(client):
    """A construct has no thrust rating to edit; it buys thrust with power each turn (FB2 p.22),
    so the workbench shows what it generates and posts a fixed 0."""
    body = client.get("/design/fb:fb2:sv-vas-sa-rosh").get_data(as_text=True)
    assert 'name="thrust" value="0"' in body and 'type="hidden" name="thrust"' in body
    assert "power per turn: 40" in body


def test_other_races_keep_the_thrust_field(client):
    body = client.get("/design/fb:fb2:kv-lo-vok").get_data(as_text=True)
    assert 'type="number" min="0" name="thrust"' in body


def test_the_picker_offers_phalon_systems_for_a_phalon_design(client):
    created, _msg = store.new_design("fb", "phalon", "PH", "Warrior")
    body = client.get(f"/design/{created['id']}").get_data(as_text=True)
    assert "Pulser battery" in body and "Plasma bolt launcher" in body
    assert "K-gun" not in body and "Stinger node" not in body


def test_a_pulser_can_be_configured_in_the_loadout(client):
    """FB2 p.35: L, M or C, chosen before a battle; the design holds the default."""
    created, _msg = store.new_design("fb", "phalon", "PH", "Warrior")
    client.post(f"/design/{created['id']}", data={"action": "add_system", "system_type": "pulser"},
                follow_redirects=True)
    draft, _dirty = store.working_design(created["id"])
    uid = next(s["uid"] for s in draft["systems"] if s["type"] == "pulser")

    client.post(f"/design/{created['id']}", data={
        "action": "apply", "name": "Warrior", "tmf": "100", "hull_boxes": "20", "armour": "12",
        "armour_layers": "8, 4", "thrust": "4", "ftl": "on", "streamlining": "none",
        "hull_kind": "warship", "type_label": "", "type_code": "", "notes": "",
        f"pulser-{uid}": "C", f"sys-{uid}-arcs-present": "1", f"sys-{uid}-arcs": "F",
    }, follow_redirects=True)

    draft, _dirty = store.working_design(created["id"])
    assert draft["default_loadout"]["pulsers"] == [{"pulser": uid, "mode": "C"}]
    assert draft["armour_layers"] == [8, 4]


def test_the_shell_layer_field_is_only_shown_to_races_that_stack_armour(client):
    phalon = client.get("/design/fb:fb2:ph-voth").get_data(as_text=True)
    human = client.get("/design/fb:fb1:nac-furious").get_data(as_text=True)
    assert 'name="armour_layers"' in phalon and "16, 10, 8, 6" in phalon
    assert 'name="armour_layers"' not in human


def test_cross_dimensions_tech_levels_are_edited_on_the_workbench(client):
    design_id = make(client, "Lancer", ruleset="ftcd")
    design = store.get_draft(design_id) or store.get_design(design_id)
    page = client.get(f"/design/{design_id}").get_data(as_text=True)
    assert 'name="drive_advanced"' in page
    client.post(f"/design/{design_id}", data=fields(
        design, action="apply", **{"advanced-present": "1", "drive_advanced": "on", "hull_advanced": "on"}))
    working = store.get_draft(design_id)
    assert working["drive_advanced"] is True and working["hull_advanced"] is True
    assert working["ftl_advanced"] is False
    plain = client.get(f"/design/{make(client, 'Plain')}").get_data(as_text=True)
    assert 'name="drive_advanced"' not in plain                    # FB has no tech levels


def test_cross_dimensions_loadout_editor(client):
    """CD pp.25, 30, 47: one row per fighter group with its extras and swing roles, light vessels
    per hangar, and salvo counts with a stage count per magazine."""
    design_id = make(client, "Ark", ruleset="ftcd")
    for system_type in ("hangar", "sm_magazine"):
        design = store.get_draft(design_id) or store.get_design(design_id)
        client.post(f"/design/{design_id}", data=fields(design, action="add_system", system_type=system_type))
    design = store.get_draft(design_id)
    hangar = next(s["uid"] for s in design["systems"] if s["type"] == "hangar")
    magazine = next(s["uid"] for s in design["systems"] if s["type"] == "sm_magazine")

    page = client.get(f"/design/{design_id}").get_data(as_text=True)
    assert f'name="fighter-{hangar}-0-type"' in page and f'name="craft-{hangar}"' in page
    assert f'name="stages-{magazine}"' in page and "Long range" in page

    client.post(f"/design/{design_id}", data=fields(design, action="apply", **{
        f"fighter-{hangar}-0-type": "attack", f"fighter-{hangar}-0-ftl": "on",
        f"fighter-{hangar}-0-swing": ["standard", "interceptor"],
        f"fighter-{hangar}-1-type": "", f"craft-{hangar}": "4",
        f"salvos-{magazine}-std": "3", f"salvos-{magazine}-er": "0", f"stages-{magazine}": "2",
    }))
    loadout = store.get_draft(design_id)["default_loadout"]
    assert loadout["fighters"] == [{"hangar": hangar, "type": "attack", "extras": ["ftl"],
                                    "swing": ["standard", "interceptor"]}]
    assert loadout["craft"] == [{"hangar": hangar, "mass": 4}]
    assert loadout["magazines"] == [{"magazine": magazine, "salvos": ["std"] * 3, "stages": 2}]

    page = client.get(f"/design/{design_id}").get_data(as_text=True)
    assert f'name="fighter-{hangar}-1-type"' not in page             # one bay, one group
    assert "Loadout: 56 points" in page                              # 24 + 9 + 9 + 6, shuttles 8


def test_fb_keeps_its_one_select_per_hangar(client):
    design_id = make(client, "Plain carrier")
    design = store.get_draft(design_id) or store.get_design(design_id)
    client.post(f"/design/{design_id}", data=fields(design, action="add_system", system_type="hangar"))
    page = client.get(f"/design/{design_id}").get_data(as_text=True)
    hangar = next(s["uid"] for s in store.get_draft(design_id)["systems"] if s["type"] == "hangar")
    assert f'name="loadout-{hangar}"' in page and "-0-type" not in page


def test_a_magazine_feeds_its_launchers_from_checkboxes(client):
    """The feeds list used to post as the text "[]", and every recalculation then failed."""
    design_id = make(client, "Feeder", ruleset="ftcd")
    for system_type in ("sm_launcher", "sm_magazine"):
        design = store.get_draft(design_id) or store.get_design(design_id)
        client.post(f"/design/{design_id}", data=fields(design, action="add_system", system_type=system_type))
    design = store.get_draft(design_id)
    launcher = next(s["uid"] for s in design["systems"] if s["type"] == "sm_launcher")
    magazine = next(s["uid"] for s in design["systems"] if s["type"] == "sm_magazine")
    page = client.get(f"/design/{design_id}").get_data(as_text=True)
    assert f'name="sys-{magazine}-feeds" value="{launcher}"' in page

    client.post(f"/design/{design_id}", data=fields(design, action="apply", **{
        f"sys-{magazine}-feeds-present": "1", f"sys-{magazine}-feeds": launcher}))
    def feeds() -> list:
        return next(s for s in store.get_draft(design_id)["systems"] if s["uid"] == magazine)["feeds"]

    assert feeds() == [launcher]
    client.post(f"/design/{design_id}", data=fields(design, action="apply",
                                                     **{f"sys-{magazine}-feeds-present": "1"}))
    assert feeds() == []


def test_fighter_types_and_system_fields_carry_names_not_keys(client):
    design_id = make(client, "Named carrier")
    for system_type in ("hangar", "hold"):
        design = store.get_draft(design_id) or store.get_design(design_id)
        client.post(f"/design/{design_id}", data=fields(design, action="add_system", system_type=system_type))
    page = client.get(f"/design/{design_id}").get_data(as_text=True)
    assert ">Long range</option>" in page and ">long_range<" not in page
    assert ">bays" not in page
    hold = next(s["uid"] for s in store.get_draft(design_id)["systems"] if s["type"] == "hold")
    assert f'<select class="input sm" name="sys-{hold}-kind"' in page and ">Cargo (H)</option>" in page


# ---- Class presets ------------------------------------------------------------------------------


def _preset_index(ruleset: str, code: str) -> str:
    from rulesets import presets
    return presets.preset_key(ruleset, next(i for i, p in enumerate(presets.class_presets(ruleset))
                                            if p.code == code))


def _new(client, ruleset: str, code: str, race: str = "human") -> dict:
    client.post("/design/new", data={"ruleset": ruleset, "race": race, "name": code,
                                     "class_preset": _preset_index(ruleset, code)})
    return next(d for d in store.list_designs() if d["name"] == code)


def _count(design: dict, system_type: str) -> int:
    return sum(1 for s in design["systems"] if s["type"] == system_type)


def test_a_class_preset_fills_the_hull_from_the_class(client):
    cl = _new(client, "ftcd", "CL")  # CD p.42: 40-60
    assert (cl["type_code"], cl["tmf"], cl["hull_boxes"], cl["armour"], cl["thrust"]) == ("CL", 50, 15, 3, 4)
    assert cl["ftl"] and _count(cl, "fire_control") == 2 and _count(cl, "hangar") == 0


@pytest.mark.parametrize("code, fcs", [("FF", 1), ("CE", 2), ("CA", 2), ("BC", 3), ("BB", 3),
                                       ("BDN", 4), ("DN", 4), ("SDN", 4), ("CVL", 2)])
def test_fire_controls_grow_with_the_class(client, code, fcs):
    assert _count(_new(client, "ftcd", code), "fire_control") == fcs


def test_carriers_start_with_two_hangar_bays_and_merchants_with_no_fire_control(client):
    cvh = _new(client, "fb", "CVH")
    assert _count(cvh, "hangar") == 2 and _count(cvh, "fire_control") == 2
    merchant = _new(client, "fb", "M")
    assert merchant["hull_kind"] == "merchant" and _count(merchant, "fire_control") == 0
    assert _count(_new(client, "ft2", "CVL"), "fighter_group") == 2


def test_races_without_fire_control_get_none(client):
    assert _new(client, "ftcd", "BB", race="savasku")["systems"] == []


def test_no_preset_starts_blank_as_before(client):
    design = store.get_design(make(client))
    assert design["systems"] == [] and design["type_code"] == ""


def test_leaving_the_class_band_reclasses_without_touching_the_rest(client):
    cl = _new(client, "ftcd", "CL")
    client.post(f"/design/{cl['id']}", data=fields(cl, tmf=58, action="apply"))
    assert store.get_draft(cl["id"])["type_code"] == "CL"  # still inside 40-60
    client.post(f"/design/{cl['id']}", data=fields(cl, tmf=85, action="apply"))
    draft = store.get_draft(cl["id"])
    assert draft["type_code"] == "CA" and draft["hull_boxes"] == cl["hull_boxes"]
    assert _count(draft, "fire_control") == 2


def test_a_carrier_stays_a_carrier_and_a_typed_code_wins(client):
    cve = _new(client, "fb", "CVE")
    client.post(f"/design/{cve['id']}", data=fields(cve, tmf=145, action="apply"))
    assert store.get_draft(cve["id"])["type_code"] == "CVL"
    cl = _new(client, "fb", "CL")
    client.post(f"/design/{cl['id']}", data=fields(cl, tmf=120, type_code="XX", action="apply"))
    assert store.get_draft(cl["id"])["type_code"] == "XX"


def test_the_form_offers_the_class_picker(client):
    page = client.get("/design").get_data(as_text=True)
    assert 'name="class_preset"' in page and "CL · Light Cruiser · MASS 50" in page


def test_a_class_of_another_ruleset_is_ignored(client):
    client.post("/design/new", data={"ruleset": "fb", "name": "Odd",
                                     "class_preset": _preset_index("ftcd", "CA")})
    assert next(d for d in store.list_designs() if d["name"] == "Odd")["type_code"] == ""


def test_new_faction_from_the_new_design_form_makes_the_faction_and_its_first_ship(client):
    client.post("/design/new", data={"ruleset": "ftcd", "name": "Raider", "race": "human",
                                     "faction": "__new__", "new_faction": "Rim Pirates"})
    design = next(d for d in store.list_designs() if d["name"] == "Raider")
    faction = next(f for f in store.custom_factions() if f["name"] == "Rim Pirates")
    assert design["faction"] == faction["id"] and faction["race"] == "human"
    # It has a ship now, so the pickers list it; the same name again reuses it.
    assert ">Rim Pirates</option>" in client.get("/design").get_data(as_text=True)
    client.post("/design/new", data={"ruleset": "ftcd", "name": "Corsair", "race": "human",
                                     "faction": "__new__", "new_faction": "rim pirates"})
    assert len(store.custom_factions()) == 1
    assert next(d for d in store.list_designs() if d["name"] == "Corsair")["faction"] == faction["id"]


def test_new_faction_without_a_name_makes_no_design(client):
    client.post("/design/new", data={"ruleset": "ftcd", "name": "Ghost", "faction": "__new__"})
    assert not store.list_designs() and not store.custom_factions()


def test_a_custom_faction_shows_in_the_pickers_only_once_it_has_a_ship(client):
    _ok, _m, fid = store.add_custom_faction("Free Traders")
    assert fid not in {f["id"] for f in store.faction_choices()}
    design_id = make(client, ruleset="ftcd")
    client.post(f"/design/{design_id}", data=fields(store.get_design(design_id), action="save",
                                                    faction=fid, allow_rule_breaking="on"))
    choice = next(f for f in store.faction_choices() if f["id"] == fid)
    assert choice["custom"] and choice["races"] == ["human"]


def test_the_workbench_names_a_new_faction(client):
    design_id = make(client, ruleset="ftcd")
    client.post(f"/design/{design_id}", data=fields(store.get_design(design_id), action="save",
                                                    faction="__new__", new_faction="Belt Union",
                                                    allow_rule_breaking="on"))
    assert store.faction_name(store.get_design(design_id)["faction"]) == "Belt Union"
    # "New faction" with the name box left empty keeps the faction the design had.
    client.post(f"/design/{design_id}", data=fields(store.get_design(design_id), action="save",
                                                    faction="__new__", allow_rule_breaking="on"))
    assert store.faction_name(store.get_design(design_id)["faction"]) == "Belt Union"


def test_built_in_factions_carry_their_race_for_the_other_races_toggle(client):
    races = {f["id"]: f["races"] for f in store.faction_choices("ftcd")}
    assert races["NAC"] == ["human"] and races["KV"] == ["kravak"] and races["PH"] == ["phalon"]
    body = client.get("/design").get_data(as_text=True)
    assert 'data-races="kravak"' in body and 'value="__new__"' in body


def test_the_faction_toggles_are_saved_settings(client):
    assert store.load_settings()["show_custom_factions"] is True
    assert store.load_settings()["show_other_race_factions"] is False
    assert client.post("/settings/factions", data={"show_other_race_factions": "1"}).status_code == 204
    client.post("/settings/factions", data={"show_custom_factions": "0"})
    settings = store.load_settings()
    assert settings["show_other_race_factions"] is True and settings["show_custom_factions"] is False
    body = client.get("/design").get_data(as_text=True)
    assert re.search(r'data-toggle="show_other_race_factions"\s+checked', body)


# ---- Edits save as they are made (static/autosave.js) ----------------------------------------------


def test_an_autosaved_edit_goes_straight_to_the_library_without_a_message(client):
    design_id = make(client)
    data = fields(store.get_design(design_id), thrust=6, allow_rule_breaking="on",
                  action="autosave", autosave="1")
    page = client.post(f"/design/{design_id}", data=data, follow_redirects=True).get_data(as_text=True)
    assert store.get_design(design_id)["thrust"] == 6
    assert store.get_draft(design_id) is None
    assert "Design saved." not in page and "Unsaved changes" not in page
    assert 'data-autosave="autosave"' in page


def test_an_autosaved_system_added_is_saved_too(client):
    design_id = make(client)
    data = fields(store.get_design(design_id), allow_rule_breaking="on",
                  action="add_system", system_type="beam", autosave="1")
    page = client.post(f"/design/{design_id}", data=data, follow_redirects=True).get_data(as_text=True)
    assert [s["type"] for s in store.get_design(design_id)["systems"]] == ["beam"]
    assert "System added" not in page


def test_an_autosaved_edit_to_a_design_ships_use_waits_for_refit_or_variant(client):
    design_id = make(client)
    client.post(f"/design/{design_id}",
                data=fields(store.get_design(design_id), action="save", allow_rule_breaking="on"))
    fleet, _msg = store.create_fleet("fb", "Home Fleet")
    store.add_ship(fleet, design_id)
    store.save_fleet(fleet)
    saved = store.get_design(design_id)
    page = client.post(f"/design/{design_id}", data=fields(saved, thrust=6, allow_rule_breaking="on",
                                                          action="autosave", autosave="1"),
                       follow_redirects=True).get_data(as_text=True)
    assert store.get_design(design_id)["thrust"] == saved["thrust"]
    assert store.get_draft(design_id)["thrust"] == 6
    assert "Unsaved changes" in page and "Refit all 1 ships" in page


def test_six_arcs_read_fore_then_aft_with_a_gap(client):
    design_id = make(client)
    client.post(f"/design/{design_id}",
                data=fields(store.get_design(design_id), action="add_system", system_type="beam"))
    page = client.get(f"/design/{design_id}").get_data(as_text=True)
    arcs = re.findall(r'name="sys-[^"]+-arcs" value="(\w+)"', page)
    assert arcs == ["F", "FP", "FS", "A", "AP", "AS"]
    assert re.search(r'<label class="arc aft"><input type="checkbox" name="sys-[^"]+-arcs" value="A"', page)


def test_a_class_code_typed_in_fills_the_type(client):
    design_id = make(client)
    client.post(f"/design/{design_id}", data=fields(store.get_design(design_id), type_code="cl",
                                                    action="apply"))
    draft = store.get_draft(design_id)
    assert (draft["type_label"], draft["type_code"]) == ("Light Cruiser", "CL")
    # A type edited together with the code is kept, and an unknown code leaves the type alone.
    client.post(f"/design/{design_id}", data=fields(draft, type_code="DD", type_label="Picket",
                                                    action="apply"))
    assert store.get_draft(design_id)["type_label"] == "Picket"
    client.post(f"/design/{design_id}", data=fields(store.get_draft(design_id), type_code="ZZ",
                                                    action="apply"))
    assert store.get_draft(design_id)["type_label"] == "Picket"
