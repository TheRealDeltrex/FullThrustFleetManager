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
