"""The schema_version framework (PLAN 5). Add a test per step in the commit that adds the step."""

from __future__ import annotations

import pytest

import migrations


def test_current_document_passes_through():
    doc = migrations.upgrade("design", {"schema_version": migrations.CURRENT, "id": "x"})
    assert doc["schema_version"] == migrations.CURRENT and doc["id"] == "x"


@pytest.mark.parametrize("value", [None, "1", 0, -3, True, 1.5, {}])
def test_missing_or_bad_version_counts_as_one(value):
    assert migrations.upgrade("fleet", {"schema_version": value})["schema_version"] == migrations.CURRENT


def test_newer_files_are_refused_not_guessed_at():
    with pytest.raises(migrations.TooNewError):
        migrations.upgrade("fleet", {"schema_version": migrations.CURRENT + 1})


def test_every_kind_has_a_step_for_every_version_below_current():
    for kind in migrations.KINDS:
        assert set(migrations.STEPS[kind]) == set(range(1, migrations.CURRENT))


def test_a_registered_step_runs(monkeypatch):
    monkeypatch.setattr(migrations, "CURRENT", 2)
    monkeypatch.setitem(migrations.STEPS["design"], 1, lambda d: dict(d, added=True))
    out = migrations.upgrade("design", {"schema_version": 1})
    assert out == {"schema_version": 2, "added": True}


# ---- v1 -> v2: the Phalon multi-layered shell (FB2 p.35) -----------------------------------------


def test_a_v1_design_gains_empty_shell_layers():
    """`armour` keeps its meaning (the total box count), so a v1 design needs no conversion:
    an empty armour_layers means the single layer every other race has."""
    doc = migrations.upgrade("design", {"schema_version": 1, "armour": 5,
                                        "default_loadout": {"fighters": [], "magazines": []}})
    assert doc["schema_version"] == 2
    assert doc["armour_layers"] == []
    assert doc["armour"] == 5
    assert doc["default_loadout"]["pulsers"] == []


def test_a_v2_design_keeps_the_layers_it_has():
    doc = migrations.upgrade("design", {"schema_version": 2, "armour": 40,
                                        "armour_layers": [16, 10, 8, 6]})
    assert doc["armour_layers"] == [16, 10, 8, 6]


def test_a_v1_fleets_ship_loadouts_gain_pulsers():
    doc = migrations.upgrade("fleet", {
        "schema_version": 1,
        "ships": [{"uid": "s1", "loadout": {"fighters": [], "magazines": []}},
                  {"uid": "s2", "loadout": None}],
    })
    assert doc["schema_version"] == 2
    assert doc["ships"][0]["loadout"]["pulsers"] == []


def test_a_v3_file_is_still_refused():
    with pytest.raises(migrations.TooNewError):
        migrations.upgrade("design", {"schema_version": 3})
