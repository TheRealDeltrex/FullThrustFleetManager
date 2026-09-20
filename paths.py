"""Filesystem paths for dev mode (`python app.py`), the PyInstaller-frozen exe and the Pyodide
web build.

- bundle_dir(): read-only resources shipped with the app (templates, static, data, translations,
  rulebooks). Resolves into PyInstaller's _MEIPASS when frozen.
- user_data_dir(): writable user library (designs, fleets, factions, settings). Never inside the
  bundle, which is a read-only temp extract when frozen.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "FullThrustFleetManager"


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def is_browser() -> bool:
    """True in the Pyodide web build (web/index.html sets FTFM_BROWSER=1)."""
    return os.environ.get("FTFM_BROWSER") == "1"


def bundle_dir() -> Path:
    if is_frozen():
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parent


def app_version() -> str:
    """Version from pyproject.toml, bundled into every build. "" if unreadable: it only feeds a
    UI label."""
    import tomllib

    try:
        data = tomllib.loads((bundle_dir() / "pyproject.toml").read_text(encoding="utf-8"))
        return str(data.get("project", {}).get("version", ""))
    except (OSError, tomllib.TOMLDecodeError):
        return ""


def default_user_data_dir() -> Path:
    # Running from source keeps data in the gitignored userdata/ next to the checkout, so a dev
    # session never touches a real install's library.
    if is_frozen():
        appdata = os.environ.get("APPDATA")
        base = Path(appdata) if appdata else Path.home() / ".config"
        return base / APP_NAME
    return bundle_dir() / "userdata"


def user_data_dir() -> Path:
    """FTFM_DATA_DIR env var (tests, the web build, scratch servers) > default."""
    env = os.environ.get("FTFM_DATA_DIR")
    if env:
        return Path(env)
    return default_user_data_dir()


def get_or_create_secret_key() -> str:
    """Flask session secret (flash messages only; no accounts). Per install, kept in
    user_data_dir() so FTFM_DATA_DIR sandboxing covers it too."""
    key_path = user_data_dir() / ".secret_key"
    if key_path.is_file():
        existing = key_path.read_text(encoding="utf-8").strip()
        if existing:
            return existing
    import secrets

    key = secrets.token_hex(32)
    key_path.parent.mkdir(parents=True, exist_ok=True)
    key_path.write_text(key, encoding="utf-8")
    return key
