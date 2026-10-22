"""Rulesets (layers 1+2): per-ruleset game data and pure rules behind one protocol (PLAN 6.1).

Each ruleset is a package here that exposes a `RULESET` object satisfying `Ruleset`, registered
in RULESETS below. Everything above this layer (fleet_rules, store, app, ssd_layout, pdf_export)
talks to a ruleset only through this protocol and never branches on a ruleset id.

Designs, loadouts and options are plain dicts in the shape of PLAN section 5; functions here are
pure and never mutate them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, runtime_checkable


@dataclass(frozen=True)
class BookRef:
    code: str  # "FB1"
    title: str
    file: str  # file name in rulebooks/
    page_offset: int  # PDF page = printed page + page_offset


@dataclass(frozen=True)
class Race:
    id: str
    name: str


@dataclass(frozen=True)
class ParamDef:
    """One editable parameter of a system, for the Design tab's Add-system picker and row
    editor. kind: "int" (min/max), "choice" (choices), "arcs" (arc picker; min/max = number of
    arcs), "uids" (other systems of the design, e.g. the launchers a magazine feeds)."""

    name: str
    kind: Literal["int", "choice", "arcs", "uids"]
    label: str
    default: Any = None
    min: int | None = None
    max: int | None = None
    choices: tuple[tuple[str, str], ...] = ()  # (value, label)


@dataclass(frozen=True)
class SystemDef:
    type: str
    label: str
    group: str  # picker grouping, e.g. "Weapons"
    params: tuple[ParamDef, ...] = ()
    book: str = ""
    page: int | None = None


@dataclass(frozen=True)
class BreakdownRow:
    key: str  # "hull", "main_drive", ... for fixed rows; the system type for system rows
    label: str
    mass: int
    points: int
    system_uid: str | None = None


@dataclass(frozen=True)
class Breakdown:
    rows: tuple[BreakdownRow, ...]
    mass_used: int
    points: int
    derived: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Issue:
    code: str
    severity: Literal["violation", "info"]
    message: str
    system_uid: str | None = None


@dataclass(frozen=True)
class QuickRefEntry:
    key: str
    title: str
    text: str  # original rulebook wording, trimmed (PLAN 2.5)
    book: str
    page: int
    url: str = ""  # where a web source (Star Ranger) prints it


@runtime_checkable
class Ruleset(Protocol):
    id: str
    name: str
    short_label: str
    accent_color: str  # CSS variable name, e.g. "--rs-fb"
    books: tuple[BookRef, ...]
    arcs: tuple[str, ...]  # fire arcs clockwise from fore: FB six, FT2 four (FT p.8)
    icon_set: Any  # the human icon table in ssd_layout.ICON_SETS; per race, icon_set_for()
    option_keys: tuple[str, ...]  # the fleet options this ruleset offers, in display order
    catalog_sources: tuple[str, ...]  # rulesets whose catalog designs this one adopts
    dummy_bogey_points: int  # points per dummy bogey a fleet may buy; 0 offers none
    hull_kinds: tuple[str, ...]  # what the Design tab's "Hull kind" offers, warship first

    def races(self) -> list[Race]: ...

    def system_types(self, race: str, options: dict) -> list[SystemDef]: ...

    def icon_set_for(self, race: str) -> str:
        """The ssd_layout.ICON_SETS id for a race, so each race's sheets look like its own part
        of the book (PLAN decision 10); `icon_set` is the human default."""
        ...

    def design_breakdown(self, design: dict, options: dict) -> Breakdown: ...

    def validate_design(self, design: dict, options: dict) -> list[Issue]: ...

    def loadout_points(self, design: dict, loadout: dict | None, options: dict) -> int:
        """Points of a loadout (fighters etc.), which design NPV excludes (PLAN 5.4)."""
        ...

    def fighter_types(self, options: dict, race: str = "human") -> list[str]:
        """Fighter group types a loadout may choose."""
        ...

    def required_options(self, design: dict, loadout: dict | None) -> set[str]:
        """Fleet options (e.g. "mt_systems") the design or loadout needs; fleet conformance
        flags the ones a fleet has switched off (PLAN 7). loadout=None: the default loadout."""
        ...

    def damage_track(self, design: dict) -> list[int]: ...

    def crew_factors(self, design: dict) -> int: ...

    def cf_positions(self, design: dict) -> list[int]: ...

    def threshold_numbers(self, design: dict) -> list[int]: ...

    def suggest_type(self, design: dict) -> tuple[str, str]: ...

    def quickref(self, systems_present: set[str], options: dict,
                 races: frozenset[str] = frozenset({"human"})) -> list[QuickRefEntry]: ...

    def fleet_issues(self, fleet: dict, ships: list[tuple[dict, dict]],
                     options: dict) -> list[Issue]:
        """Rules that judge the fleet as a whole rather than one design, given each ship with
        its design (ships whose design is missing are left out)."""
        ...

    def morale_mass(self, ships: list[tuple[dict, dict]]) -> tuple[int, int] | None:
        """(MASS destroyed, MASS lost at which the fleet withdraws) for a ruleset with a fleet
        morale rule, else None."""
        ...

    def scan_class(self, design: dict) -> str:
        """What a long-range scan reads the ship as: "escort", "cruiser" or "capital" (FT
        pp.21, 34)."""
        ...

    def adopt_design(self, design: dict) -> dict | None:
        """A catalog design of a `catalog_sources` ruleset as this ruleset's own: a new id and
        this ruleset id, changed where this ruleset's book says the design must change. The
        store calls it once per design at load time; None leaves the design out."""
        ...


RULESETS: dict[str, Ruleset] = {}


def register(ruleset: Ruleset) -> Ruleset:
    if ruleset.id in RULESETS:
        raise ValueError(f"duplicate ruleset: {ruleset.id}")
    RULESETS[ruleset.id] = ruleset
    return ruleset


def get_ruleset(ruleset_id: str) -> Ruleset:
    """KeyError for an unknown id; callers that read files guard for that."""
    return RULESETS[ruleset_id]


# Books the app ships to read but whose rules no ruleset implements yet. A ruleset's own `books`
# are its rules sources: the things a "FB1 p.16" link in the UI points into, and the things the
# quick reference quotes. These are neither, so they are kept apart rather than hung off a
# ruleset they do not belong to. The viewer and the Settings list show both (see app.books()).
# Cross Dimensions and Project Continuum both started here and moved to their rulesets' books;
# the list is empty until the app ships another book only to be read.
REFERENCE_BOOKS: tuple[BookRef, ...] = ()


# Book codes in publication order, for every list of rulebooks the player sees. A code missing
# here sorts after these, by code.
BOOK_ORDER: tuple[str, ...] = ("FT", "MT", "FB1", "FB2", "CD", "PC", "PCE")


def book_sort_key(code: str) -> tuple[int, str]:
    return (BOOK_ORDER.index(code) if code in BOOK_ORDER else len(BOOK_ORDER), code)


# Registration imports come last: the packages import the dataclasses above.
from rulesets import fb, ft2, ftcd, ftpc  # noqa: E402

# In publication order: FT2 with More Thrust (1992/1994), the Fleet Books (1998/2000), Cross
# Dimensions (2006), then Project Continuum (2014). Pickers list rulesets in this order and the
# New fleet form numbers them from it, so core Full Thrust is 1.
register(ft2.RULESET)
register(fb.RULESET)
register(ftcd.RULESET)
register(ftpc.RULESET)
