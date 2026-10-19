"""NPV gate (PLAN 8): every catalog design recomputes to its printed NPV and passes validation,
unless data/errata.json lists it with a real reason."""

from __future__ import annotations

import json

import pytest
from conftest import ROOT

from rulesets import get_ruleset

CATALOG = sorted((ROOT / "data" / "catalog").glob("*.json"))
DESIGNS = [d for path in CATALOG for d in json.loads(path.read_text(encoding="utf-8"))["designs"]]
ERRATA = {e["id"]: e for e in json.loads((ROOT / "data" / "errata.json").read_text(encoding="utf-8"))}


def _options(ruleset, design) -> dict:
    # A catalog design is judged with exactly the More Thrust options it needs switched on.
    return {opt: True for opt in ruleset.required_options(design, None)}


def test_catalog_files_present():
    assert {p.name for p in CATALOG} >= {"fb_fb1.json", "fb_starranger.json", "ft2_core.json", "ft2_mt.json"}


def test_ids_unique():
    ids = [d["id"] for d in DESIGNS]
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize("design", DESIGNS, ids=[d["id"] for d in DESIGNS])
def test_npv_gate(design):
    rs = get_ruleset(design["ruleset"])
    opts = _options(rs, design)
    b = rs.design_breakdown(design, opts)
    violations = [i.code for i in rs.validate_design(design, opts) if i.severity == "violation"]
    erratum = ERRATA.get(design["id"])
    if erratum:
        assert erratum["book_value"] == design["source"]["npv_book"]
        assert erratum["rules_value"] == b.points, "errata rules_value is stale"
        assert len(erratum["reason"]) > 20
        return
    # A Star Ranger variant often prints no NPV (0); it still has to be legal, bar the systems and
    # hull options the Fleet Books lack (such a design is listed only by Project Continuum).
    if design["source"]["npv_book"] or design["source"].get("book") != "SR":
        assert b.points == design["source"]["npv_book"]
    if design["source"].get("book") == "SR":
        violations = [v for v in violations if v != "not_in_books"]
    assert violations == []


def test_errata_entries_are_used():
    known = {d["id"] for d in DESIGNS} | {"ft2:ft:super-heavy-cruiser-example"}
    assert set(ERRATA) <= known
