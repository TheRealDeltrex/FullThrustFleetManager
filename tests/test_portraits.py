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


def test_every_original_design_has_art_and_adoptions_share_it():
    originals = []
    for file in (paths.bundle_dir() / "data/catalog").glob("*.json"):
        designs = json.loads(file.read_text(encoding="utf-8"))["designs"]
        # Original-book adoption coverage; the expanded source catalog is checked below.
        if file.name != "fb_starranger.json":
            originals.extend(designs)
    resolved = [portraits.resolve(d, {}) for d in originals]
    assert len(resolved) == len(originals) == 141
    assert all(a and a.get("file") for a in resolved)
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
            if art.get("columns", 4) > 1 or art.get("rows", 4) > 1:
                assert im.width == im.height
            assert im.width > 0 and im.height > 0
        assert 0 <= art["cell"] < art.get("columns", 4) * art.get("rows", 4)


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


def test_clicking_a_picture_opens_the_picture_changer(client):
    fleet, message = store.create_fleet("fb", "Click fleet", "human")
    store.add_ship(fleet, "fb:fb1:nac-harrison")
    store.save_fleet(fleet)
    ship = fleet["ships"][0]
    pages = {"/design/fb:fb1:nac-harrison": '/portrait/design/fb:fb1:nac-harrison"',
             f'/fleet/{fleet["id"]}': f'/portrait/ship/{fleet["id"]}/{ship["uid"]}"',
             "/campaign": f'/portrait/ship/{fleet["id"]}/{ship["uid"]}"'}
    for url, link in pages.items():
        page = client.get(url, follow_redirects=True).get_data(as_text=True)
        assert f'<a class="portrait-link" href="{link}' in page, url
        assert ">Change picture</a>" not in page, url


def test_expanded_source_catalog_has_art_and_explicit_reference_views():
    originals = [d for file in (paths.bundle_dir() / "data/catalog").glob("*.json")
                 for d in json.loads(file.read_text(encoding="utf-8"))["designs"]]
    resolved = [portraits.resolve(d, {}) for d in originals]
    assert len(originals) == len(resolved) == 482
    for art in resolved:
        assert art["view"] in {"source-photograph", "manufacturer-illustration", "faction-design",
                               "fleet-book-bow-lower-right", "port-bow-30deg-bow-lower-left"}
    # Shared class images are intentional, but cannot silently merge unrelated hulls.
    cells = {}
    for art in resolved:
        key = (art["file"], art["cell"])
        if key in cells:
            assert art.get("model") and art["model"] == cells[key].get("model")
        cells[key] = art
    assert all(a["basis"] in {"miniature", "miniature-variant", "invented-faction-design",
                             "fleet-book-restored", "fleet-book-style"}
               for a in resolved)
    for ruleset in RULESETS:
        for design in store.catalog_designs(ruleset):
            art = portraits.resolve(design, {})
            assert art["view"] in {"source-photograph", "manufacturer-illustration", "faction-design",
                                   "fleet-book-bow-lower-right", "port-bow-30deg-bow-lower-left"}


def test_versioned_defaults_preserve_existing_gallery_choices_and_uploads():
    design = {"id": "custom-test", "type_code": "SC"}
    legacy = "custom:SC:1"
    assert portraits.resolve(design, {})["file"] != portraits.manifest()["portraits"][legacy]["file"]
    portraits.save(portraits.design_target(design), art=legacy)
    assert portraits.resolve(design, portraits.load()) == portraits.manifest()["portraits"][legacy]
    portraits.save(portraits.design_target(design), data=png())
    assert "upload" in portraits.resolve(design, portraits.load())
    for code, default in portraits.manifest()["class_defaults"].items():
        assert default.startswith(f"custom:{code}:")
        assert default in portraits.manifest()["portraits"]
        assert f"custom:{code}:v2-1" in portraits.manifest()["portraits"]
        assert f"custom:{code}:v2-2" in portraits.manifest()["portraits"]


def test_phalon_photo_defaults_keep_originals_as_explicit_choices():
    for identity in ("fb2:ph-phyaa", "fb2:ph-vlath", "fb2:ph-draath"):
        art = portraits.resolve({"id": "fb:" + identity}, {})
        assert art["view"] == "source-photograph"
        assert art["basis"] == "miniature"
    for identity, cell in (("fb2:ph-phyaa", 0), ("fb2:ph-vlath", 1), ("fb2:ph-draath", 14)):
        legacy = portraits.manifest()["portraits"]["official:" + identity]
        assert (legacy["file"], legacy["cell"]) == ("ships/ph.webp", cell)
    for identity in ("sr:ph-silith", "sr:ph-greeth", "sr:ph-gruuss-b"):
        art = portraits.resolve({"id": "fb:" + identity}, {})
        assert art["view"] == "source-photograph"
        assert art["basis"] == "miniature"
    assert any(a["file"] == "ships/ph-fleetbook-extension-v3.webp"
               for a in portraits.manifest()["portraits"].values())


def test_portrait_renderer_uses_atlas_dimensions(client):
    from flask import render_template_string

    with client.application.test_request_context():
        page = render_template_string(
            '{% from "_portraits.html" import picture with context %}{{ picture(art, "Test") }}',
            art={"file": "ships/test.webp", "cell": 4, "columns": 3, "rows": 3},
            art_url=lambda file: "/static/" + file)
    assert "background-size:300% 300%" in page
    assert "background-position:50.0% 50.0%" in page

    # Individual images may retain their native portrait/landscape framing.
    # Contain them without stretching their hull geometry to a square.
    with client.application.test_request_context():
        page = render_template_string(
            '{% from "_portraits.html" import picture with context %}{{ picture(art, "Test") }}',
            art={"file": "ships/test.webp", "cell": 0, "columns": 1, "rows": 1},
            art_url=lambda file: "/static/" + file)
    assert "background-size:contain;background-position:center" in page


def test_photo_based_class_variants_share_images_and_preserve_legacy_choices(client):
    pairs = (("sr:rav-attacker", "sr:rav-attacker-missile"),
             ("sr:rav-raider", "sr:rav-raider-missile"),
             ("sr:rav-raider-type-ii", "sr:rav-raider-type-ii-needle"))
    for base, variant in pairs:
        design = {"id": "fb:" + base}
        art = portraits.resolve(design, {})
        assert art == portraits.resolve({"id": "fb:" + variant}, {})
        assert art["view"] == "source-photograph"
        assert art["columns"] == art["rows"] == 1
        assert len(art["references"]) == 2
        legacy = "miniature-v2:" + base
        portraits.save(portraits.design_target(design), art=legacy)
        assert portraits.resolve(design, portraits.load()) == portraits.manifest()["portraits"][legacy]
        portraits.save(portraits.design_target(design), data=png())
        assert "upload" in portraits.resolve(design, portraits.load())
        page = client.get("/design/ftpc:" + base).get_data(as_text=True)
        assert 'data:image/jpeg;base64,' in page


def test_individual_portraits_are_stored_small():
    # docs/SHIP-ARTWORK.md: a single-image portrait is shown at 256 px at most, so the repo and
    # the download carry it at 512 px on the long side, never the generator's full size.
    for art in portraits.manifest()["portraits"].values():
        if art.get("columns", 4) == 1 and art.get("rows", 4) == 1:
            with Image.open(paths.bundle_dir() / "static" / art["file"]) as im:
                assert max(im.size) <= 512, art["file"]
