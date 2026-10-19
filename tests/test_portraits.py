"""Portrait coverage, isolation, untrusted uploads and portable persistence."""
import io
import json

import pytest
from PIL import Image

import paths
import portraits
import store
from rulesets import RULESETS, presets


@pytest.fixture(autouse=True)
def library(tmp_path, monkeypatch):
    monkeypatch.setenv("FTFM_DATA_DIR", str(tmp_path))


def png():
    out = io.BytesIO()
    Image.new("RGBA", (800, 400), (50, 100, 150, 120)).save(out, "PNG")
    return out.getvalue()


def test_every_official_design_has_unique_art_and_adoptions_share_it():
    originals, not_yet_drawn = [], []
    for file in (paths.bundle_dir() / "data/catalog").glob("*.json"):
        designs = json.loads(file.read_text(encoding="utf-8"))["designs"]
        # Star Ranger designs have no art of their own yet and fall back to their class picture.
        (not_yet_drawn if file.name == "fb_starranger.json" else originals).extend(designs)
    resolved = [portraits.resolve(d, {}) for d in originals]
    assert len({(a["file"], a["cell"]) for a in resolved}) == len(originals) == 141
    assert all(portraits.resolve(d, {}) for d in not_yet_drawn)
    for d in originals:
        if d["ruleset"] == "fb":
            for rs in ("ftcd", "ftpc"):
                adopted = dict(d, id=rs + ":" + portraits.canonical(d["id"]))
                assert portraits.resolve(adopted, {}) == portraits.resolve(d, {})


def test_two_gallery_choices_per_supported_class_and_assets_exist():
    codes = {p.code for rs in RULESETS for p in presets.class_presets(rs)}
    codes.update(("BASE", "SECTION", "GENERIC"))
    for code in codes:
        assert len([a for a in portraits.gallery({"type_code": code}) if a["code"] == code]) >= 2
    for art in portraits.manifest()["portraits"].values():
        path = paths.bundle_dir() / "static" / art["file"]
        assert path.is_file(), path
        with Image.open(path) as im:
            assert im.width == im.height
        assert 0 <= art["cell"] < 16


def test_upload_does_not_mutate_catalog_and_reset_restores_default(client):
    identity = "fb:fb1:nac-harrison"
    before = store.get_design(identity)
    response = client.post("/portrait/design/" + identity, data={
        "action": "upload", "picture": (io.BytesIO(png()), "my-ship.png")}, follow_redirects=True)
    assert response.status_code == 200
    assert b"data:image/jpeg;base64," in response.data
    assert store.get_design(identity) == before
    art = portraits.resolve(before, portraits.load())
    assert "upload" in art
    client.post("/portrait/design/" + identity, data={"action": "reset"})
    assert portraits.resolve(before, portraits.load()) == portraits.resolve(before, {})


def test_per_ship_override_precedence_and_portable_fleet_backup(client):
    fleet, message = store.create_fleet("fb", "Art fleet", "human")
    store.add_ship(fleet, "fb:fb1:nac-harrison")
    store.save_fleet(fleet)
    ship = fleet["ships"][0]
    design = store.get_design(ship["design_id"])
    portraits.save(portraits.design_target(design), art="custom:SC:1")
    target = portraits.ship_target(fleet["id"], ship["uid"])
    portraits.save(target, art="custom:SC:2")
    assert portraits.resolve(design, portraits.load(), target)["variant"] == 2
    filename, data = store.export_fleet(fleet["id"])
    portraits.write({})
    assert store.import_file(filename, data.encode())[0]
    assert portraits.resolve(design, portraits.load(), target)["variant"] == 2
    filename, data = store.export_backup()
    portraits.write({})
    assert store.import_file(filename, data)[0]
    assert portraits.resolve(design, portraits.load(), target)["variant"] == 2
    assert client.get(f'/portrait/ship/{fleet["id"]}/{ship["uid"]}').status_code == 200
    portraits.save(target)
    assert portraits.resolve(design, portraits.load(), target)["variant"] == 1


@pytest.mark.parametrize("data", [b"<svg onload='alert(1)'/>", b"not an image",
                                  b"x" * (portraits.MAX_UPLOAD + 1)],
                         ids=["svg", "invalid", "oversize"])
def test_bad_upload_is_rejected_without_changing_choice(data):
    portraits.save("design:test", art="custom:SC:1")
    with pytest.raises(ValueError):
        portraits.save("design:test", data=data)
    assert portraits.load()["design:test"]["art"] == "custom:SC:1"


def test_unknown_target_or_art_cannot_be_saved():
    for target, art in (("../../outside", "custom:SC:1"), ("design:test", "../../evil")):
        with pytest.raises(ValueError):
            portraits.save(target, art=art)
    assert portraits.normalize({"design:test": {"upload": "javascript:alert(1)"}}) == {}


def test_picture_backup_routes_and_explicit_web_form_actions(client):
    portraits.save("design:fb1:nac-harrison", data=png())
    response = client.get("/portraits/backup")
    assert response.status_code == 200
    assert "attachment" in response.headers["Content-Disposition"]
    portraits.write({})
    response = client.post("/portraits/restore", data={
        "pictures": (io.BytesIO(response.data), "pictures.json")}, follow_redirects=True)
    assert response.status_code == 200
    assert "upload" in portraits.load()["design:fb1:nac-harrison"]
    page = client.get("/portrait/design/fb:fb1:nac-harrison").get_data(as_text=True)
    assert page.count('action="/portrait/design/fb:fb1:nac-harrison"') == 3


def test_portraits_and_new_themes_render_without_changing_ssd(client):
    identity = "fb:fb1:nac-harrison"
    baseline = None
    for theme in store.THEMES:
        store.save_settings(theme=theme)
        page = client.get("/design/" + identity).get_data(as_text=True)
        assert f'data-theme="{theme}"' in page
        assert "ship-portrait" in page
        svg = page[page.index("<svg"):page.index("</svg>") + 6]
        baseline = baseline or svg
        assert svg == baseline
