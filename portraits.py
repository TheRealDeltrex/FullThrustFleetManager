"""Theme-independent artwork. Never read by rules, SSD layout or PDF rendering.

Bundled atlas metadata is immutable; user choices live in a separate UTF-8 JSON file,
including bounded, re-encoded uploads so the Pyodide snapshot can persist them too.
"""
from __future__ import annotations

import base64
import binascii
import io
import json
import re
import warnings
from datetime import datetime, timezone
from functools import lru_cache

import paths

MAX_UPLOAD = 5 * 1024 * 1024
MAX_ENCODED = 180_000
_TARGET = re.compile(r"^(?:design:[A-Za-z0-9:_-]{1,120}|ship:[A-Za-z0-9_-]{1,64}:[A-Za-z0-9_-]{1,64})$")


@lru_cache(maxsize=1)
def manifest() -> dict:
    return json.loads((paths.bundle_dir() / "data" / "ship_art.json").read_text(encoding="utf-8"))


def canonical(design_id: str) -> str:
    prefix, sep, rest = design_id.partition(":")
    return rest if sep and prefix in ("fb", "ft2", "ftcd", "ftpc") else design_id


def design_target(design: dict) -> str:
    return "design:" + canonical(design["id"])


def ship_target(fleet_id: str, uid: str) -> str:
    return f"ship:{fleet_id}:{uid}"


def encode_upload(data: bytes) -> str:
    """Decode real raster data, reject oversized images, remove metadata and active content."""
    if not data or len(data) > MAX_UPLOAD:
        raise ValueError("size")
    # Pillow is imported here, not at the top: the online version loads it as an optional
    # package, and a failed load must cost only uploads, not the whole app.
    try:
        from PIL import Image, ImageOps, UnidentifiedImageError
    except ImportError as exc:
        raise ValueError("image") from exc
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as source:
                if source.format not in ("JPEG", "PNG", "WEBP") or source.width * source.height > 16_000_000:
                    raise ValueError("format")
                source.load()
                pic = ImageOps.exif_transpose(source).convert("RGBA")
                pic.thumbnail((512, 512))
                canvas = Image.new("RGB", pic.size, "#121c26")
                canvas.paste(pic, mask=pic.getchannel("A"))
                output = io.BytesIO()
                canvas.save(output, "JPEG", quality=80, optimize=True)
                encoded = base64.b64encode(output.getvalue()).decode("ascii")
                if len(encoded) > MAX_ENCODED:
                    raise ValueError("size")
                return encoded
    except (OSError, UnidentifiedImageError, Image.DecompressionBombError,
            Image.DecompressionBombWarning) as exc:
        raise ValueError("image") from exc


@lru_cache(maxsize=128)
def _valid_encoded(value: str) -> bool:
    try:
        raw = base64.b64decode(value, validate=True)
    except (ValueError, binascii.Error):
        return False
    try:
        from PIL import Image
    except ImportError:  # cannot check without Pillow; keep the stored picture rather than drop it
        return raw[:3] == b"\xff\xd8\xff"
    try:
        with Image.open(io.BytesIO(raw)) as im:
            if im.format != "JPEG" or im.width > 512 or im.height > 512:
                return False
            im.verify()
        return True
    except (ValueError, OSError, binascii.Error):
        return False


def normalize(doc: object) -> dict:
    out = {}
    if not isinstance(doc, dict):
        return out
    for key, value in doc.items():
        if not isinstance(key, str) or not _TARGET.fullmatch(key) or not isinstance(value, dict):
            continue
        entry = {}
        art = value.get("art")
        upload = value.get("upload")
        if isinstance(art, str) and art in manifest()["portraits"]:
            entry["art"] = art
        elif isinstance(upload, str) and len(upload) <= MAX_ENCODED and _valid_encoded(upload):
            entry["upload"] = upload
        if entry:
            modified = value.get("modified")
            entry["modified"] = modified[:40] if isinstance(modified, str) else ""
            out[key] = entry
    return out


def load() -> dict:
    try:
        return normalize(json.loads((paths.user_data_dir() / "portraits.json").read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return {}


def write(doc: dict) -> None:
    root = paths.user_data_dir()
    root.mkdir(parents=True, exist_ok=True)
    tmp = root / "portraits.json.tmp"
    tmp.write_text(json.dumps(normalize(doc), ensure_ascii=False), encoding="utf-8")
    tmp.replace(root / "portraits.json")


def save(target: str, *, art: str = "", data: bytes | None = None) -> None:
    if not _TARGET.fullmatch(target):
        raise ValueError("target")
    doc = load()
    if data is not None:
        choice = {"upload": encode_upload(data)}
    elif art:
        if art not in manifest()["portraits"]:
            raise ValueError("art")
        choice = {"art": art}
    else:
        doc.pop(target, None)
        write(doc)
        return
    choice["modified"] = datetime.now(timezone.utc).isoformat()
    doc[target] = choice
    write(doc)


def merge(incoming: object, overwrite: bool = False) -> tuple[int, list[str]]:
    doc = load()
    count, conflicts = 0, []
    for key, value in normalize(incoming).items():
        if not overwrite and doc.get(key, {}).get("modified", "") > value["modified"]:
            conflicts.append(key)
        else:
            doc[key] = value
            count += 1
    if count:
        write(doc)
    return count, conflicts


def subset(designs: list[dict], fleet: dict | None = None, doc: dict | None = None) -> dict:
    """Portable choices, restricted to the objects included in an import/export."""
    wanted = {design_target(d) for d in designs}
    if fleet:
        wanted.update(ship_target(fleet["id"], s["uid"]) for s in fleet["ships"])
    return {k: v for k, v in (load() if doc is None else normalize(doc)).items() if k in wanted}


def class_code(design: dict) -> str:
    if design.get("hull_kind") == "starbase":
        return "BASE"
    if design.get("hull_kind") == "section":
        return "SECTION"
    return design.get("type_code") or "GENERIC"


def gallery(design: dict) -> list[dict]:
    code = class_code(design)
    doc = manifest()
    ids = doc.get("gallery_ids")
    if ids is None:
        ids = [k for k in doc["portraits"] if k.startswith("custom:")]
    choices = [dict(doc["portraits"][k], id=k) for k in ids if k in doc["portraits"]]
    order = {key: index for index, key in enumerate(ids)}
    return sorted(choices, key=lambda x: (x["code"] != code, x["code"], order[x["id"]]))


def resolve(design: dict | None, overrides: dict, target: str = "") -> dict | None:
    if not design:
        return None
    choice = overrides.get(target) or overrides.get(design_target(design))
    if choice and "upload" in choice:
        return {"upload": "data:image/jpeg;base64," + choice["upload"]}
    art = choice.get("art") if choice else None
    if not art:
        identity = canonical(design["id"])
        source_id = canonical(design.get("source", {}).get("of", ""))
        art = manifest()["official"].get(identity) or manifest()["official"].get(source_id)
    if not art:
        art = manifest().get("class_defaults", {}).get(class_code(design),
                                                        f"custom:{class_code(design)}:1")
    generic = manifest().get("class_defaults", {}).get("GENERIC", "custom:GENERIC:1")
    return manifest()["portraits"].get(art) or manifest()["portraits"][generic]
