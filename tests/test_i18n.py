"""Translation layer (PLAN 13)."""

from __future__ import annotations

import ast
import json
import re

from conftest import ROOT

import i18n

EN = ROOT / "translations" / "en.json"
# `_("...")` / `_('...')` in Jinja templates.
TEMPLATE_CALL = re.compile(r"""\b_\(\s*(["'])((?:\\.|(?!\1).)*)\1""")


def _python_strings() -> set[str]:
    found = set()
    for path in list(ROOT.glob("*.py")) + list((ROOT / "rulesets").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "_"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
            ):
                found.add(node.args[0].value)
    return found


def _template_strings() -> set[str]:
    found = set()
    for path in (ROOT / "templates").rglob("*.html"):
        for m in TEMPLATE_CALL.finditer(path.read_text(encoding="utf-8")):
            found.add(m.group(2))
    return found


def test_every_source_string_is_in_en_json():
    catalog = json.loads(EN.read_text(encoding="utf-8"))
    missing = sorted((_python_strings() | _template_strings()) - catalog.keys())
    assert missing == [], f"add to translations/en.json: {missing}"


def test_en_json_has_no_stale_entries():
    catalog = json.loads(EN.read_text(encoding="utf-8"))
    stale = sorted(catalog.keys() - (_python_strings() | _template_strings()))
    assert stale == [], f"remove from translations/en.json: {stale}"


def test_missing_key_falls_back_to_key():
    assert i18n.gettext("A string nobody translated") == "A string nobody translated"


def test_params_are_formatted_after_lookup():
    assert i18n.gettext("{n} ships", n=3) == "3 ships"


def test_broken_translation_falls_back_to_source(monkeypatch):
    monkeypatch.setattr(i18n, "_catalog", lambda lang: {"{n} ships": "{m} Schiffe"})
    assert i18n.gettext("{n} ships", n=2) == "2 ships"


def test_unknown_language_is_refused():
    assert i18n.set_language("xx") is False
    assert i18n.get_language() == "en"
