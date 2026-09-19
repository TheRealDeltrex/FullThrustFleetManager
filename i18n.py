"""Translation layer (PLAN section 13).

`_("source string", **params)` looks the string up in translations/<lang>.json and falls back to
the source string itself. Params are applied with str.format after lookup, so translations can
reorder them: `_("{n} ships", n=3)`. app.py registers `gettext` as the Jinja global `_`.

English is the only language in v1; en.json lists every source string (identity mapping) so a
translator has the full set. tests/test_i18n.py fails when a `_("...")` literal in the code or
templates is missing from en.json.
"""

from __future__ import annotations

import json
from functools import lru_cache

import paths

DEFAULT_LANGUAGE = "en"
LANGUAGES = {"en": "English"}

_current = DEFAULT_LANGUAGE


@lru_cache(maxsize=None)
def _catalog(lang: str) -> dict[str, str]:
    path = paths.bundle_dir() / "translations" / f"{lang}.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return {k: v for k, v in data.items() if isinstance(k, str) and isinstance(v, str)}


def set_language(lang: str) -> bool:
    global _current
    if lang not in LANGUAGES:
        return False
    _current = lang
    return True


def get_language() -> str:
    return _current


def gettext(key: str, **params: object) -> str:
    text = _catalog(_current).get(key) or key
    if params:
        try:
            return text.format(**params)
        except (KeyError, IndexError, ValueError):
            # A broken translation must not take a page down; the source string is safe.
            return key.format(**params)
    return text


_ = gettext
