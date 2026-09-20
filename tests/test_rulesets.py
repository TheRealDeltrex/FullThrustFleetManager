"""Every registered ruleset satisfies the Ruleset protocol (PLAN 6.1)."""

from __future__ import annotations

import pytest

from rulesets import RULESETS, Ruleset


def test_v1_rulesets_registered():
    assert set(RULESETS) == {"fb", "ft2"}


@pytest.mark.parametrize("rid", sorted(RULESETS))
def test_protocol(rid):
    rs = RULESETS[rid]
    assert isinstance(rs, Ruleset)
    assert rs.id == rid and rs.short_label and rs.name and rs.accent_color.startswith("--rs-")
    assert rs.arcs and rs.books and rs.races()
    assert rs.system_types("human", {}) and rs.fighter_types({})
    # Every race the ruleset offers must be a complete tech module, not just a name in a list.
    for race in rs.races():
        assert rs.system_types(race.id, {}), race.id
        assert rs.fighter_types({}, race.id), race.id
        assert rs.icon_set_for(race.id), race.id
