"""Export, import and backup through the app (PLAN 5.6, 5.7, 9.6), not just the store."""

from __future__ import annotations

import io
from datetime import datetime, timedelta, timezone

import pytest

import app as app_module
import store

FURIOUS = "fb:fb1:nac-furious"


@pytest.fixture(autouse=True)
def library(tmp_path, monkeypatch):
    monkeypatch.setenv("FTFM_DATA_DIR", str(tmp_path))
    return tmp_path


def a_fleet() -> dict:
    fleet, _msg = store.create_fleet("fb", "Home Fleet", faction="NAC", points_limit=1500)
    store.add_ship(fleet, FURIOUS)
    store.save_fleet(fleet)
    return fleet


def a_design() -> dict:
    design, _msg = store.new_design("fb", name="Sentinel")
    design["allow_rule_breaking"] = True
    ok, msg, design_id = store.save_design(design)
    assert ok, msg
    return store.get_design(design_id)


def upload(client, name: str, data: bytes):
    return client.post("/import", data={"file": (io.BytesIO(data), name)},
                       content_type="multipart/form-data", follow_redirects=True)


def attachment(resp) -> str:
    assert resp.status_code == 200
    disposition = resp.headers["Content-Disposition"]
    assert disposition.startswith("attachment;")
    return disposition


def test_the_settings_tab_offers_backup_and_import(client):
    page = client.get("/settings").get_data(as_text=True)
    assert 'action="/backup"' in page and 'action="/import"' in page and 'type="file"' in page


def test_a_backup_round_trips_through_the_app(client):
    fleet, design = a_fleet(), a_design()
    resp = client.post("/backup")
    assert ".FTBackup" in attachment(resp)
    store.delete_fleet(fleet["id"])
    store.delete_design(design["id"])
    page = upload(client, "lib.FTBackup", resp.data).get_data(as_text=True)
    assert "restored from the backup" in page
    assert store.get_fleet(fleet["id"]) and store.get_design(design["id"])
    assert "Last backup" in client.get("/settings").get_data(as_text=True)


def test_a_fleet_and_a_design_export_from_their_tabs(client):
    fleet, design = a_fleet(), a_design()
    client.get(f"/fleet/{fleet['id']}")
    assert f"/export/fleet/{fleet['id']}" in client.get("/fleet").get_data(as_text=True)
    assert ".FTFleet" in attachment(client.get(f"/export/fleet/{fleet['id']}"))
    assert f"/export/design/{design['id']}" in client.get(f"/design/{design['id']}").get_data(as_text=True)
    assert ".FTDesign" in attachment(client.get(f"/export/design/{design['id']}"))
    # Catalog designs are the app's own and stay out of files.
    assert "/export/design/" not in client.get(f"/design/{FURIOUS}").get_data(as_text=True)
    assert client.get(f"/export/design/{FURIOUS}").status_code == 404
    assert client.get("/export/fleet/nope").status_code == 404


def test_a_newer_local_copy_waits_for_the_players_answer(client):
    design = a_design()
    blob = client.get(f"/export/design/{design['id']}").data
    store.save_design(dict(design, name="Newer here"))
    # The file is made older than the library copy.
    old = blob.replace(design["modified"].encode(), b"2000-01-01T00:00:00+00:00")
    page = upload(client, "x.FTDesign", old).get_data(as_text=True)
    assert "Newer copies kept here: Sentinel." in page
    assert store.get_design(design["id"])["name"] == "Newer here"
    resp = client.post("/import/held", data={"action": "replace"}, follow_redirects=True)
    page = resp.get_data(as_text=True)
    assert store.get_design(design["id"])["name"] == "Sentinel"
    assert "Newer copies kept here" not in page


def test_keeping_mine_drops_the_held_import(client):
    design = a_design()
    old = client.get(f"/export/design/{design['id']}").data.replace(
        design["modified"].encode(), b"2000-01-01T00:00:00+00:00")
    store.save_design(dict(design, name="Newer here"))
    upload(client, "x.FTDesign", old)
    client.post("/import/held", data={"action": "keep"})
    assert store.held_import() is None
    assert store.get_design(design["id"])["name"] == "Newer here"


def test_a_bad_file_is_refused_with_a_message(client):
    page = upload(client, "x.FTDesign", b"not json").get_data(as_text=True)
    assert "Not a Fleet Manager file." in page
    page = client.post("/import", data={}, follow_redirects=True).get_data(as_text=True)
    assert "Choose a file to import." in page


def test_the_online_version_reminds_to_back_up(client, monkeypatch):
    monkeypatch.setattr(app_module, "BROWSER_MODE", True)
    assert "backup-due" not in client.get("/settings").get_data(as_text=True)  # empty library
    a_fleet()
    assert "backup-due" in client.get("/settings").get_data(as_text=True)
    client.post("/backup/later", data={"next": "/settings"})
    assert "backup-due" not in client.get("/settings").get_data(as_text=True)
    weeks_ago = (datetime.now(timezone.utc) - timedelta(days=15)).replace(microsecond=0).isoformat()
    store.save_settings(backup_snoozed=weeks_ago)
    assert "backup-due" in client.get("/settings").get_data(as_text=True)
    client.post("/backup")
    assert "backup-due" not in client.get("/settings").get_data(as_text=True)


def test_the_desktop_shows_no_reminder(client):
    a_fleet()
    assert "backup-due" not in client.get("/settings").get_data(as_text=True)
