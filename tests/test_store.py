"""The library, mutations and import/export (PLAN 5). Every mutator returns (ok, msg)."""

from __future__ import annotations

import json

import pytest

import migrations
import store

CATALOG_FB = "fb:fb1:nac-harrison"


@pytest.fixture(autouse=True)
def library(tmp_path, monkeypatch):
    """A fresh library per test; the catalog is read from the bundle and shared."""
    monkeypatch.setenv("FTFM_DATA_DIR", str(tmp_path))
    return tmp_path


def a_design(**kw):
    """A saved library design. A blank new design is under its TMF, so it is saved in
    bookkeeping mode; conformance is fleet_rules' business, not the store's."""
    d, _msg = store.new_design("fb", faction="NAC", name="Test")
    d.update(allow_rule_breaking=True, **kw)
    ok, _m, _id = store.save_design(d, mode="refit")
    assert ok
    return d


def age(design_id, stamp="2000-01-01T00:00:00+00:00"):
    """Backdate a library design, so a later save is unambiguously newer (now() is per second)."""
    d = store.get_design(design_id)
    d["modified"] = stamp
    store._write_json(store._design_path(design_id), d)


def a_fleet(**kw):
    f, _msg = store.create_fleet("fb", "Home Fleet", faction="NAC", **kw)
    return f


# ---- Library ----------------------------------------------------------------------------------


def test_new_design_is_saved_and_listed():
    d, msg = store.new_design("fb", name="Scout")
    assert d and msg
    assert store.get_design(d["id"])["name"] == "Scout"
    assert [x["id"] for x in store.list_designs("fb")] == [d["id"]]
    assert store.list_designs("ft2") == []


def test_new_design_rejects_unknown_ruleset_and_race():
    assert store.new_design("nope")[0] is None
    assert store.new_design("fb", race="klingon")[0] is None


def test_catalog_designs_are_readable_and_read_only():
    d = store.get_design(CATALOG_FB)
    assert d and store.is_catalog(d["id"])
    ok, msg, _id = store.save_design(dict(d, name="Edited"))
    assert not ok and msg
    assert not store.delete_design(CATALOG_FB)[0]
    assert store.get_design(CATALOG_FB)["name"] == d["name"]
    # ... and the catalog never leaks into the user library
    assert store.list_designs() == []


def test_get_design_returns_a_copy_of_the_catalog_entry():
    store.get_design(CATALOG_FB)["systems"].clear()
    assert store.get_design(CATALOG_FB)["systems"]


def test_editing_a_catalog_design_means_making_a_variant():
    v, msg = store.make_variant(CATALOG_FB)
    assert v and msg
    assert v["source"] == {"kind": "variant", "of": CATALOG_FB}
    assert v["faction"] == store.get_design(CATALOG_FB)["faction"]  # variants keep the class faction
    assert not store.is_catalog(v["id"])
    ok, _m, saved = store.save_design(dict(v, name="Mine"))
    assert ok and saved == v["id"]


def test_make_variant_of_a_missing_design():
    assert store.make_variant("nope")[0] is None


def test_saving_a_design_ships_use_needs_refit_or_variant():
    d = a_design()
    f = a_fleet()
    store.add_ship(f, d["id"])
    store.save_fleet(f)

    ok, msg, _id = store.save_design(dict(d, name="Mark II"))
    assert not ok and msg  # blocked: ships use it

    ok, _m, new_id = store.save_design(dict(d, name="Mark II"), mode="variant")
    assert ok and new_id != d["id"]
    assert store.get_design(new_id)["source"] == {"kind": "variant", "of": d["id"]}
    assert store.get_design(d["id"])["name"] == d["name"]  # the ship's design is untouched

    ok, _m, same = store.save_design(dict(d, name="Mark II"), mode="refit")
    assert ok and same == d["id"]
    assert store.get_design(d["id"])["name"] == "Mark II"


def test_strict_mode_blocks_a_violating_design_unless_rule_breaking_is_allowed():
    d, _msg = store.new_design("fb", name="Blank")  # a blank hull is under its TMF
    assert not store.save_design(dict(d, allow_rule_breaking=False))[0]
    assert store.save_design(dict(d, allow_rule_breaking=True))[0]


def test_delete_design_guards_ships_using_it():
    d = a_design()
    f = a_fleet()
    store.add_ship(f, d["id"])
    store.save_fleet(f)
    assert not store.delete_design(d["id"])[0]
    store.remove_ship(f, f["ships"][0]["uid"])
    store.save_fleet(f)
    assert store.delete_design(d["id"])[0]
    assert store.get_design(d["id"]) is None
    assert not store.delete_design(d["id"])[0]


def test_ships_using_lists_fleet_and_ship():
    d = a_design()
    f = a_fleet()
    store.add_ship(f, d["id"])
    store.save_fleet(f)
    assert store.ships_using(d["id"]) == [(f["id"], f["ships"][0]["uid"])]


# ---- Custom factions --------------------------------------------------------------------------


def test_custom_factions_round_trip():
    ok, _m, fid = store.add_custom_faction("Free Traders")
    assert ok and fid
    assert store.custom_factions() == [{"id": fid, "name": "Free Traders"}]
    assert store.faction_name(fid) == "Free Traders"
    assert not store.add_custom_faction("free traders")[0]  # no duplicates
    assert not store.add_custom_faction("   ")[0]


def test_builtin_factions_are_per_ruleset():
    assert {f["id"] for f in store.builtin_factions("fb")} >= {"NAC", "NSL", "FSE", "ESU"}
    assert store.builtin_factions("nope") == []
    assert store.faction_name("NAC", "fb") == "New Anglian Confederation"
    assert store.faction_name("unknown") == "unknown"
    assert store.faction_name(None) == ""


# ---- Fleets -----------------------------------------------------------------------------------


def test_create_and_list_fleets():
    f = a_fleet()
    assert store.get_fleet(f["id"])["name"] == "Home Fleet"
    assert [x["id"] for x in store.list_fleets()] == [f["id"]]
    assert store.delete_fleet(f["id"])[0]
    assert store.get_fleet(f["id"]) is None
    assert not store.delete_fleet(f["id"])[0]
    assert store.create_fleet("nope", "x")[0] is None


def test_squadrons():
    f = a_fleet()
    assert store.add_squadron(f, "Escort")[0]
    assert [q["name"] for q in f["squadrons"]] == ["Main body", "Escort"]
    assert store.rename_squadron(f, "sq2", "Screen")[0]
    assert not store.rename_squadron(f, "nope", "x")[0]
    assert store.move_squadron(f, "sq2", -1)[0]
    assert [q["id"] for q in f["squadrons"]] == ["sq2", "sq1"]
    d = a_design()
    store.add_ship(f, d["id"], squadron="sq2")
    assert store.remove_squadron(f, "sq2")[0]
    assert f["ships"][0]["squadron"] == "sq1"
    assert not store.remove_squadron(f, "sq1")[0]  # at least one squadron remains


def test_add_ship_names_and_numbers_by_type_code():
    d = a_design()
    f = a_fleet()
    assert store.add_ship(f, d["id"])[0]
    assert store.add_ship(f, d["id"])[0]
    code = store.get_design(d["id"])["type_code"] or "S"
    assert [s["table_id"] for s in f["ships"]] == [f"{code}-1", f"{code}-2"]
    assert [s["name"] for s in f["ships"]] == [d["name"], d["name"]]
    assert store.suggest_table_id(f, code) == f"{code}-3"
    assert not store.add_ship(f, "nope")[0]


def test_add_ship_rejects_another_ruleset():
    f = a_fleet()
    assert not store.add_ship(f, "ft2:ft:courier")[0]


def test_update_ship_and_loadout():
    d = a_design()
    f = a_fleet()
    store.add_ship(f, d["id"])
    uid = f["ships"][0]["uid"]
    assert store.update_ship(f, uid, name="Lion", status="damaged", location="Dock")[0]
    assert f["ships"][0]["name"] == "Lion" and f["ships"][0]["status"] == "damaged"
    assert not store.update_ship(f, uid, status="vaporised")[0]
    assert not store.update_ship(f, uid, squadron="nope")[0]
    assert not store.update_ship(f, "nope", name="x")[0]
    assert store.set_ship_loadout(f, uid, {"fighters": [{"hangar": "h", "type": "heavy"}]})[0]
    assert f["ships"][0]["loadout"]["fighters"] == [{"hangar": "h", "type": "heavy"}]
    assert store.set_ship_loadout(f, uid, None)[0]
    assert f["ships"][0]["loadout"] is None  # back to the design default
    assert not store.remove_ship(f, "nope")[0]
    assert store.remove_ship(f, uid)[0] and f["ships"] == []


def test_fleet_details_and_log():
    f = a_fleet()
    assert not store.update_fleet_details(f, name="  ")[0]
    assert not store.update_fleet_details(f, points_limit=-1)[0]
    assert store.update_fleet_details(f, name="Task Force", points_limit=1500,
                                      options={"mt_systems": True, "bogus": True})[0]
    assert f["name"] == "Task Force" and f["points_limit"] == 1500
    assert f["options"]["mt_systems"] is True and "bogus" not in f["options"]
    assert store.add_log_entry(f, 2, "Raided Alpha")[0]
    assert not store.add_log_entry(f, 2, "  ")[0]
    assert f["log"] == [{"week": 2, "text": "Raided Alpha"}]


def test_designs_for_fleet_covers_every_referenced_design():
    d = a_design()
    f = a_fleet()
    store.add_ship(f, d["id"])
    store.add_ship(f, d["id"])
    assert set(store.designs_for_fleet(f)) == {d["id"]}


# ---- Normalisation of untrusted files ----------------------------------------------------------


def test_normalize_design_rejects_nonsense_and_clamps_fields():
    assert store.normalize_design(None) is None
    assert store.normalize_design({"id": "x"}) is None  # no ruleset
    assert store.normalize_design({"ruleset": "fb"}) is None  # no id
    d = store.normalize_design({
        "id": "x", "ruleset": "fb", "tmf": "lots", "thrust": 99, "armour": -5, "ftl": "yes",
        "streamlining": "shiny", "hull_kind": "banana", "notes": 5,
        "systems": ["nope", {"type": "beam"}, {"uid": "s1", "type": "beam", "class": 77, "arcs": ["F", 3]}],
        "source": {"kind": "wat"}, "layout_hints": "no",
    })
    assert d["tmf"] == 10 and d["thrust"] == 20 and d["armour"] == 0
    assert d["ftl"] is False and d["streamlining"] == "none" and d["hull_kind"] == "warship"
    assert d["notes"] == "" and d["layout_hints"] == {}
    assert d["source"] == {"kind": "custom"}
    assert d["systems"] == [{"uid": "s1", "type": "beam", "class": 9, "arcs": ["F"]}]
    assert d["schema_version"] == migrations.CURRENT


def test_normalize_fleet_repairs_squadrons_ships_and_options():
    f = store.normalize_fleet({
        "id": "f1", "ruleset": "fb", "squadrons": "no",
        "options": {"mt_systems": True, "core_systems": 1, "evil": True},
        "ships": ["nope", {"uid": "s1", "design_id": "d1", "squadron": "gone", "status": "melted",
                           "damage": {"drive_hits": 9, "systems_out": ["a", 2]}}],
        "log": [{"week": -1, "text": "x"}, "nope"], "points_limit": None,
    })
    assert [q["id"] for q in f["squadrons"]] == ["sq1"]
    assert f["ships"][0]["squadron"] == "sq1" and f["ships"][0]["status"] == "ready"
    assert f["ships"][0]["damage"]["drive_hits"] == 2
    assert f["ships"][0]["damage"]["systems_out"] == ["a"]
    assert f["options"] == {k: k == "mt_systems" for k in f["options"]}
    assert f["log"] == [{"week": 0, "text": "x"}]
    assert f["points_limit"] == 0
    assert store.normalize_fleet({"id": "../../etc", "ruleset": "fb"}) is None


def test_a_design_id_can_never_escape_the_library(library):
    assert store._design_path("../evil") is None
    assert store.get_design("../evil") is None
    assert not store.delete_design("../evil")[0]
    assert list(library.glob("**/*evil*")) == []


# ---- Export / import --------------------------------------------------------------------------


def test_export_and_import_a_design():
    d = a_design()
    name, text = store.export_design(d["id"])
    assert name.endswith(store.EXTENSIONS["design"])
    store.delete_design(d["id"])
    ok, msg, conflicts = store.import_file(name, text.encode("utf-8"))
    assert ok and msg and conflicts == []
    assert store.get_design(d["id"])["name"] == d["name"]
    assert store.export_design("nope") is None


def test_exported_design_carries_its_custom_faction():
    _ok, _m, fid = store.add_custom_faction("Free Traders")
    d = a_design()
    assert store.save_design(dict(d, faction=fid), mode="refit")[0]
    _name, text = store.export_design(d["id"])
    assert json.loads(text)["factions"] == [{"id": fid, "name": "Free Traders"}]


def test_export_and_import_a_fleet_with_its_designs():
    d = a_design()
    f = a_fleet()
    store.add_ship(f, d["id"])
    store.add_ship(f, CATALOG_FB)
    store.save_fleet(f)
    name, text = store.export_fleet(f["id"])
    assert name.endswith(store.EXTENSIONS["fleet"])
    doc = json.loads(text)
    assert [x["id"] for x in doc["designs"]] == [d["id"]]  # catalog ships are not copied

    store.delete_fleet(f["id"])
    store.delete_design(d["id"])
    ok, _m, conflicts = store.import_file(name, text.encode("utf-8"))
    assert ok and conflicts == []
    assert len(store.get_fleet(f["id"])["ships"]) == 2
    assert store.get_design(d["id"])
    assert store.export_fleet("nope") is None


def test_importing_a_fleet_whose_designs_are_missing_fails():
    d = a_design()
    f = a_fleet()
    store.add_ship(f, d["id"])
    store.save_fleet(f)
    _name, text = store.export_fleet(f["id"])
    doc = json.loads(text)
    doc["designs"] = []
    store.delete_fleet(f["id"])
    store.delete_design(d["id"])
    ok, msg, _c = store.import_file("x.FTFleet", json.dumps(doc).encode("utf-8"))
    assert not ok and d["id"] in msg


def test_a_newer_local_copy_is_kept_until_the_player_confirms():
    d = a_design()
    age(d["id"])
    _name, text = store.export_design(d["id"])
    assert store.save_design(dict(d, name="Newer here"), mode="refit")[0]
    ok, _m, conflicts = store.import_file("x.FTDesign", text.encode("utf-8"))
    assert ok and conflicts == [d["name"]]
    assert store.get_design(d["id"])["name"] == "Newer here"
    ok, _m, conflicts = store.import_file("x.FTDesign", text.encode("utf-8"), overwrite_newer=True)
    assert ok and conflicts == []
    assert store.get_design(d["id"])["name"] == d["name"]


def test_import_rejects_junk_and_files_from_a_newer_app():
    assert not store.import_file("x.FTDesign", b"not json")[0]
    assert not store.import_file("x.FTDesign", json.dumps([1, 2]).encode())[0]
    assert not store.import_file("x.FTDesign", json.dumps({"kind": "FTDesign"}).encode())[0]
    assert not store.import_file("x.FTFleet", json.dumps({"kind": "FTFleet"}).encode())[0]
    assert not store.import_file("x.FTDesign", json.dumps({"kind": "Other"}).encode())[0]
    newer = json.dumps({"schema_version": 99, "kind": "FTDesign"}).encode()
    ok, msg, _c = store.import_file("x.FTDesign", newer)
    assert not ok and msg


def test_backup_round_trip():
    d = a_design()
    f = a_fleet()
    store.add_ship(f, d["id"])
    store.save_fleet(f)
    store.add_custom_faction("Free Traders")
    name, blob = store.export_backup()
    assert name.endswith(store.EXTENSIONS["backup"])
    assert store.load_settings()["last_backup"]

    store.delete_fleet(f["id"])
    store.delete_design(d["id"])
    ok, msg, conflicts = store.import_file(name, blob)
    assert ok and msg and conflicts == []
    assert store.get_fleet(f["id"]) and store.get_design(d["id"])
    assert [x["name"] for x in store.custom_factions()] == ["Free Traders"]
    assert not store.import_file("x.FTBackup", b"PK\x03\x04 garbage")[0]


def test_backup_import_keeps_newer_local_copies():
    d = a_design()
    age(d["id"])
    _name, blob = store.export_backup()
    assert store.save_design(dict(d, name="Newer here"), mode="refit")[0]
    ok, _m, conflicts = store.import_file("b.FTBackup", blob)
    assert ok and conflicts == [d["name"]]
    assert store.get_design(d["id"])["name"] == "Newer here"


# ---- Settings ---------------------------------------------------------------------------------


def test_settings_defaults_and_validation():
    assert store.load_settings() == store.DEFAULT_SETTINGS
    store.save_settings(paper="Letter", pdf_viewer="nonsense", nothing_like_this=1)
    s = store.load_settings()
    assert s["paper"] == "Letter" and s["pdf_viewer"] == "app"
    assert "nothing_like_this" not in s
