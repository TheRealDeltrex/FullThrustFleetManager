"""The Design tab (PLAN 9.4): library, workbench edits, strict mode, refit-or-variant."""

from __future__ import annotations

import pytest

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
