"""The web bundle carries everything the app reads at runtime, and nothing desktop-only."""

from __future__ import annotations

import importlib.util

from conftest import ROOT


def _collect() -> dict[str, str]:
    spec = importlib.util.spec_from_file_location("bbb", ROOT / "scripts" / "build_browser_bundle.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.collect()


def test_bundle_contents():
    files = _collect()
    for rel in (
        "app.py",
        "paths.py",
        "i18n.py",
        "idle_watchdog.py",
        "pyproject.toml",
        "translations/en.json",
        "static/style.css",
        "rulesets/__init__.py",
    ):
        assert rel in files
    for tpl in (ROOT / "templates").glob("*.html"):
        assert f"templates/{tpl.name}" in files
    assert "tray.py" not in files and "run_app.py" not in files
