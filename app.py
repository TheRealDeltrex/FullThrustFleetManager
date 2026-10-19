"""Full Thrust Fleet Manager: Flask routes (layer 4, thin).

Parses requests, calls the layers above (rulesets -> fleet_rules -> store), renders templates.
No rules maths here (PLAN 2.7).
"""

from __future__ import annotations

import logging
import os
import re
import secrets
import sys
import threading
import webbrowser
from collections.abc import Callable
from logging.handlers import RotatingFileHandler

from flask import (
    Flask,
    Response,
    abort,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)
from markupsafe import Markup

import fleet_rules
import i18n
import paths
import pdf_export
import ssd_layout
import store
from i18n import _
from idle_watchdog import note_closing, note_heartbeat
from rulesets import REFERENCE_BOOKS, RULESETS, book_sort_key, common, presets
from rulesets.fb import data as fb_data

logger = logging.getLogger(__name__)


def _configure_logging() -> None:
    """The frozen exe has no console, so it logs to a small rotating file in the data dir.
    Everywhere else keeps Python's default stderr logging."""
    if not paths.is_frozen():
        return
    data_dir = paths.user_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(data_dir / "ftfm.log", maxBytes=512 * 1024, backupCount=2, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.addHandler(handler)
    root.setLevel(logging.INFO)


_configure_logging()

_BUNDLE_DIR = paths.bundle_dir()
app = Flask(
    __name__,
    template_folder=str(_BUNDLE_DIR / "templates"),
    static_folder=str(_BUNDLE_DIR / "static"),
)
app.secret_key = os.environ.get("SECRET_KEY") or paths.get_or_create_secret_key()
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

BROWSER_MODE = paths.is_browser()
APP_VERSION = paths.app_version()


@app.context_processor
def _inject_globals() -> dict:
    settings = store.load_settings()
    return {
        "BROWSER_MODE": BROWSER_MODE,
        "IS_FROZEN": paths.is_frozen(),
        "APP_VERSION": APP_VERSION,
        "LANG": i18n.get_language(),
        "THEME": settings["theme"],
        "SETTINGS": settings,
    }


app.jinja_env.globals["_"] = i18n.gettext


# ---- Local-only request guards --------------------------------------------------------------
# The app has no authentication; it relies on only listening on 127.0.0.1. Two holes remain
# that these guards close:
#  * Any website the user visits can POST a form at 127.0.0.1 (CSRF).
#  * A hostile DNS name pointed at 127.0.0.1 (DNS rebinding) makes a remote page same-origin
#    with us and able to read the library. Only the Host header tells that apart.

_ALLOWED_HOSTS = {"127.0.0.1", "localhost", "::1"}


def _host_is_local(host: str) -> bool:
    if not host:
        return False
    host = host.strip()
    if host.startswith("["):  # bracketed IPv6, e.g. "[::1]:5000"
        hostname = host[1:].partition("]")[0]
    else:
        hostname = host.partition(":")[0]
    return hostname.lower() in _ALLOWED_HOSTS


@app.before_request
def _reject_cross_site() -> Response | None:
    """Block DNS-rebinding reads and cross-site writes. The web build is exempt: it runs the app
    through a test client inside the page, with no network hop at all."""
    if BROWSER_MODE:
        return None
    if not _host_is_local(request.host):
        logger.warning("Rejected request with non-local Host header: %r", request.host)
        abort(403)
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return None
    # Origin comes with every cross-origin POST; Referer is the fallback for browsers that omit
    # Origin on same-origin posts. Neither present means a non-browser client (a test).
    source = request.headers.get("Origin") or request.headers.get("Referer")
    if source:
        from urllib.parse import urlparse

        if not _host_is_local(urlparse(source).netloc):
            logger.warning("Rejected cross-site %s %s from %r", request.method, request.path, source)
            abort(403)
    return None


@app.after_request
def _security_headers(resp: Response) -> Response:
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    # SAMEORIGIN, not DENY: the rulebook viewer frames our own vendored pdf.js page (PLAN 12).
    resp.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    resp.headers.setdefault("Referrer-Policy", "same-origin")
    resp.headers.setdefault("Content-Security-Policy", "frame-ancestors 'self'")
    return resp


# ---- Action dispatch --------------------------------------------------------------------------
# State-changing forms POST a hidden `action` field; handlers registered here take the target
# object (fleet or design dict), mutate it through store.py and return (ok, msg). The route
# flashes msg and saves iff ok. The fleet/design update routes arrive with the store (M5).

ActionHandler = Callable[[dict], tuple[bool, str]]
ACTION_HANDLERS: dict[str, ActionHandler] = {}


def register_action(name: str) -> Callable[[ActionHandler], ActionHandler]:
    def deco(fn: ActionHandler) -> ActionHandler:
        if name in ACTION_HANDLERS:
            raise ValueError(f"duplicate action handler: {name}")
        ACTION_HANDLERS[name] = fn
        return fn

    return deco


def dispatch_action(target: dict) -> bool:
    """Runs the handler named by request.form["action"] on target. Returns True iff the caller
    should save target."""
    handler = ACTION_HANDLERS.get(request.form.get("action") or "")
    if handler is None:
        flash(_("Unknown action."), "error")
        return False
    try:
        ok, msg = handler(target)
    except ValueError:
        flash(_("Please enter a valid number."), "error")
        return False
    # An edit saved as it is made (static/autosave.js) reports only what went wrong.
    if msg and not (ok and request.form.get("autosave")):
        flash(msg, "success" if ok else "error")
    return ok


# ---- Routes -----------------------------------------------------------------------------------


@app.route("/")
def home() -> Response:
    return redirect(url_for("fleet_overview"))


# ---- Fleet overview tab (PLAN 9.3) -------------------------------------------------------------

VIEWS = ("cards", "sheet", "roster")


def current_fleet() -> dict | None:
    """The fleet the top bar shows, remembered per browser session."""
    fleet_id = session.get("fleet_id")
    fleet = store.get_fleet(fleet_id) if fleet_id else None
    if not fleet:
        fleets = store.list_fleets()
        fleet = fleets[0] if fleets else None
        session["fleet_id"] = fleet["id"] if fleet else None
    return fleet


@app.context_processor
def _inject_current_fleet() -> dict:
    """The top bar carries the fleet selector, the points meter and the ruleset strip."""
    fleet = current_fleet()
    # The race pickers on both creation forms list every ruleset's races; which races exist is
    # the ruleset's to say (PLAN 6.1), so the template never hard-codes one.
    races = [(rs, rs.races()) for rs in RULESETS.values()]
    if not fleet:
        return {"current_fleet": None, "all_fleets": store.list_fleets(), "fleet_points": 0,
                "races_by_ruleset": races, "all_factions": store.faction_choices()}
    designs = store.designs_for_fleet(fleet)
    return {
        "current_fleet": fleet,
        "all_fleets": store.list_fleets(),
        "fleet_points": fleet_rules.fleet_points(fleet, designs),
        "fleet_badges": fleet_rules.badges(fleet, designs),
        "races_by_ruleset": races,
        "all_factions": store.faction_choices(),
    }


# The Add ship list shows the fleet's own faction, every faction, or the factions the player
# ticks; the choice is kept per fleet. Designs without a faction tick as this pseudo-faction.
NO_FACTION = "-"
SHIP_LIST_MODES = ("own", "all", "pick")


def _ship_list(fleet: dict) -> dict:
    """The fleet's Add ship filter: {"mode", "factions"}. A fleet without a faction has no
    "own" list, so it starts on all."""
    saved = (session.get("ship_lists") or {}).get(fleet["id"]) or {}
    mode = saved.get("mode")
    if mode not in SHIP_LIST_MODES or (mode == "own" and not fleet["faction"]):
        mode = "own" if fleet["faction"] else "all"
    if mode == "own":
        return {"mode": mode, "factions": [fleet["faction"]]}
    picked = saved.get("factions")
    if not isinstance(picked, list):
        picked = [fleet["faction"]] if fleet["faction"] else []
    return {"mode": mode, "factions": [f for f in picked if isinstance(f, str)]}


def _remember_ship_list(fleet: dict) -> None:
    args = request.args
    if "ships" in args:
        mode = args.get("ships")
    else:
        # The old Show all ships toggle: a hidden 0 before the checkbox's 1.
        mode = "all" if args.getlist("all_ships")[-1] == "1" else "own"
    if mode not in SHIP_LIST_MODES:
        return
    saved = dict((session.get("ship_lists") or {}).get(fleet["id"]) or {})
    saved["mode"] = mode
    if mode == "pick" and "factions_sent" in args:
        saved["factions"] = args.getlist("faction")[:100]
    lists = dict(session.get("ship_lists") or {})
    lists[fleet["id"]] = saved
    session["ship_lists"] = lists


def _faction_groups(designs: list[dict], factions: list[dict], keep: str | None = None) -> list[dict]:
    """Designs grouped by faction in the faction pickers' order (built-in, then custom), any
    other faction after them and factionless designs last; inside a group smallest class
    first, then points (the catalog order). ``keep`` adds that faction even with no designs."""
    order = {f["id"]: i for i, f in enumerate(factions)}
    by_faction: dict[str, list[dict]] = {}
    if keep:
        by_faction[keep] = []
    for d in designs:
        by_faction.setdefault(d["faction"] or NO_FACTION, []).append(d)

    def rank(fid: str) -> tuple:
        return (fid == NO_FACTION, order.get(fid, len(order)), fid)

    return [
        {"id": fid,
         "name": _("No faction") if fid == NO_FACTION else store.faction_name(fid),
         "designs": sorted(by_faction[fid], key=lambda d: (
             _class_rank(d), d.get("points", 0), d["name"].lower()))}
        for fid in sorted(by_faction, key=rank)
    ]


def _fleet_context(fleet: dict, view: str) -> dict:
    designs = store.designs_for_fleet(fleet)
    options = fleet_rules.fleet_options(fleet)
    every_design = store.list_designs(fleet["ruleset"]) + store.catalog_designs(fleet["ruleset"])
    for d in every_design:
        d["points"] = fleet_rules.design_points(d, options)
    factions = store.faction_choices(fleet["ruleset"], keep=fleet["faction"])
    ship_list = _ship_list(fleet)
    library = [d for d in every_design if ship_list["mode"] == "all"
               or (d["faction"] or NO_FACTION) in ship_list["factions"]]
    groups = _faction_groups(library, factions)
    report = fleet_rules.fleet_report(fleet, designs)
    sheets = {
        s["uid"]: Markup(ssd_layout.to_svg(ssd_layout.layout(
            designs[s["design_id"]], damage=s["damage"])))
        for s in fleet["ships"] if s["design_id"] in designs
    }
    return {
        "fleet": fleet,
        "designs": designs,
        "ruleset": RULESETS.get(fleet["ruleset"]),
        "view": view if view in VIEWS else "cards",
        "report": report,
        "badges": fleet_rules.badges(fleet, designs),
        "counts": fleet_rules.ship_counts(fleet),
        "sheets": sheets,
        "ship_points": {s["uid"]: fleet_rules.ship_points(s, designs.get(s["design_id"]),
                                                          fleet_rules.fleet_options(fleet))
                        for s in fleet["ships"]},
        "hull_damage": sum(s["damage"]["hull"] for s in fleet["ships"]),
        "dummy_bogeys": fleet_rules.dummy_bogeys(fleet),
        "morale": fleet_rules.morale(fleet, designs),
        "dummy_bogey_points": fleet_rules.dummy_bogey_points(fleet),
        "library": library,
        "library_groups": groups,
        "library_total": len(every_design),
        "ship_list": ship_list,
        # The factions the Pick list offers: those with a design in this ruleset, plus the fleet's.
        "library_factions": _faction_groups(every_design, factions, keep=fleet["faction"]),
        "faction_name": store.faction_name(fleet["faction"], fleet["ruleset"]),
        "factions": factions,
        # Only the options this fleet's ruleset offers, in its order, with readable names.
        "option_keys": fleet_rules.ruleset_option_keys(fleet["ruleset"]),
        "option_label": fleet_rules.option_label,
    }


@app.route("/fleet")
def fleet_overview() -> str:
    fleet = current_fleet()
    if not fleet:
        return render_template("fleet.html", active_tab="fleet_overview", selected=None,
                               rulesets=list(RULESETS.values()))
    if "ships" in request.args or "all_ships" in request.args:
        _remember_ship_list(fleet)
    return render_template("fleet.html", active_tab="fleet_overview",
                           selected=_fleet_context(fleet, request.args.get("view", "cards")),
                           rulesets=list(RULESETS.values()))


@app.route("/fleet/<fleet_id>")
def fleet_select(fleet_id: str) -> Response:
    if not store.get_fleet(fleet_id):
        abort(404)
    session["fleet_id"] = fleet_id
    return redirect(url_for("fleet_overview", view=request.args.get("view")))


@app.route("/fleet/new", methods=["POST"])
def fleet_new() -> Response:
    created, msg = store.create_fleet(
        request.form.get("ruleset", ""), request.form.get("name", ""),
        request.form.get("race", "human"), request.form.get("faction") or None,
        int(request.form.get("points_limit") or 0),
        request.form.get("allow_race_mixing") == "on",
        request.form.get("admiral", ""),
    )
    flash(msg, "success" if created else "error")
    if created:
        session["fleet_id"] = created["id"]
    return redirect(url_for("fleet_overview"))


@register_action("update_details")
def _update_details(fleet: dict) -> tuple[bool, str]:
    form = request.form
    return store.update_fleet_details(
        fleet, name=form.get("name"), admiral=form.get("admiral", ""),
        faction=form.get("faction") or None,
        points_limit=int(form.get("points_limit") or 0),
        allow_race_mixing=form.get("allow_race_mixing") == "on",
        # Options the ruleset does not offer are not on the form and stay as they were.
        options={**fleet["options"],
                 **{k: form.get("opt-" + k) == "on"
                    for k in fleet_rules.ruleset_option_keys(fleet["ruleset"])}},
        notes=form.get("notes", ""),
        dummy_bogeys=int(form.get("dummy_bogeys") or 0) if "dummy_bogeys" in form else None,
    )


@register_action("add_squadron")
def _add_squadron(fleet: dict) -> tuple[bool, str]:
    return store.add_squadron(fleet, request.form.get("name", ""))


@register_action("rename_squadron")
def _rename_squadron(fleet: dict) -> tuple[bool, str]:
    return store.rename_squadron(fleet, request.form.get("squadron", ""), request.form.get("name", ""))


@register_action("move_squadron")
def _move_squadron(fleet: dict) -> tuple[bool, str]:
    return store.move_squadron(fleet, request.form.get("squadron", ""),
                               int(request.form.get("delta") or 0))


@register_action("remove_squadron")
def _remove_squadron(fleet: dict) -> tuple[bool, str]:
    return store.remove_squadron(fleet, request.form.get("squadron", ""))


@register_action("add_ship")
def _add_ship(fleet: dict) -> tuple[bool, str]:
    return store.add_ship(fleet, request.form.get("design_id", ""), request.form.get("name", ""),
                          request.form.get("table_id", ""), request.form.get("squadron", ""))


@register_action("remove_ship")
def _remove_ship(fleet: dict) -> tuple[bool, str]:
    return store.remove_ship(fleet, request.form.get("uid", ""))


@register_action("update_ship")
def _update_ship(fleet: dict) -> tuple[bool, str]:
    form = request.form
    return store.update_ship(fleet, form.get("uid", ""), name=form.get("name"),
                             table_id=form.get("table_id"), squadron=form.get("squadron"),
                             status=form.get("status"), location=form.get("location"))


@app.route("/fleet/<fleet_id>/action", methods=["POST"])
def fleet_action(fleet_id: str) -> Response:
    fleet = store.get_fleet(fleet_id)
    if not fleet:
        abort(404)
    if request.form.get("action") == "delete_fleet":
        ok, msg = store.delete_fleet(fleet_id)
        flash(msg, "success" if ok else "error")
        session.pop("fleet_id", None)
        return redirect(url_for("fleet_overview"))
    if dispatch_action(fleet):
        store.save_fleet(fleet)
    return redirect(url_for("fleet_overview", view=request.args.get("view")))


@app.route("/fleet/<fleet_id>/check")
def fleet_check(fleet_id: str) -> str:
    """The tournament check (PLAN 7): every violation and info, grouped by ship. Blocks nothing."""
    fleet = store.get_fleet(fleet_id)
    if not fleet:
        abort(404)
    designs = store.designs_for_fleet(fleet)
    return render_template("tournament_check.html", active_tab="fleet_overview", fleet=fleet,
                           designs=designs, report=fleet_rules.fleet_report(fleet, designs),
                           ruleset=RULESETS.get(fleet["ruleset"]))


# ---- Design tab (PLAN 9.4) --------------------------------------------------------------------


def _catalog_group(design: dict) -> str:
    book = design["source"].get("book") or design["ruleset"]
    race = design.get("race") or "human"
    rs = RULESETS.get(design["ruleset"])
    group = book
    if race != "human":
        name = next((r.name for r in rs.races() if r.id == race), race) if rs else race
        group = f"{book} · {name}"
    # A ruleset may adopt another's book (Cross Dimensions takes the Fleet Book ships), so the
    # adopted copies get their own group, named for the ruleset they are costed under.
    if rs and book not in {b.code for b in rs.books}:
        group = f"{group} ({rs.short_label})"
    return group


# The catalog lists hulls smallest to largest: the FB1 p.12 size bands (SC up to SDN), with CD's
# CA beside CH, then carriers and merchants, which are roles rather than sizes.
_WARSHIP_ORDER = tuple(code for _, code, _, _ in fb_data.SHIP_CLASSES)
_AFTER_CH = _WARSHIP_ORDER.index("CH") + 1
_CLASS_ORDER = {code: i for i, code in enumerate(
    _WARSHIP_ORDER[:_AFTER_CH] + ("CA",) + _WARSHIP_ORDER[_AFTER_CH:]
    + ("CVE", "CVL", "CV", "CVH", "CVA", "M"))}


def _class_rank(design: dict) -> int:
    """Where a design's class sits in the catalog; an unknown code goes last."""
    return _CLASS_ORDER.get(design.get("type_code") or "", len(_CLASS_ORDER))


def _catalog_key(design: dict) -> tuple:
    """Book and race (the group), then faction (factionless last), class size, mass and name."""
    faction = design.get("faction") or ""
    return (design["ruleset"], design.get("race") or "human", not faction, faction,
            _class_rank(design), design.get("tmf", 0), design["name"].lower())


def _library(query: str = "") -> dict:
    """The left pane: my designs by ruleset, the catalog by book, both filtered by `query`."""
    def matches(d: dict) -> bool:
        if not query:
            return True
        haystack = " ".join(str(d.get(k) or "") for k in ("name", "type_label", "type_code", "faction"))
        return query.lower() in haystack.lower()

    mine: dict[str, list[dict]] = {}
    for d in store.list_designs():
        if matches(d):
            mine.setdefault(d["ruleset"], []).append(d)
    catalog: dict[str, list[dict]] = {}
    for d in sorted(store.catalog_designs(), key=_catalog_key):
        if matches(d):
            d["points"] = fleet_rules.design_points(d, {})
            # One book may hold several races (FB2 is a book of alien fleets), so the group is
            # book plus race; human designs keep the plain book heading.
            catalog.setdefault(_catalog_group(d), []).append(d)
    return {"mine": mine, "catalog": catalog, "query": query}


def _system_groups(definitions: list) -> list[tuple[str, list]]:
    """The Add-system picker's groups in the ruleset's order, each with its systems in order."""
    groups: dict[str, list] = {}
    for definition in definitions:
        groups.setdefault(definition.group, []).append(definition)
    return list(groups.items())


def _design_context(design: dict, dirty: bool) -> dict:
    """Everything the workbench shows about one design: breakdown, issues, SSD, usage."""
    rs = RULESETS[design["ruleset"]]
    options = {k: True for k in fleet_rules.FLEET_OPTION_KEYS}  # the picker offers everything
    breakdown = rs.design_breakdown(design, {})
    issues = fleet_rules.design_issues(design, {})
    violations = [i for i in issues if i.severity == "violation"]
    used_by = store.ships_using(design["id"])
    return {
        "design": design,
        "dirty": dirty,
        "ruleset": rs,
        "read_only": store.is_catalog(design["id"]),
        "breakdown": breakdown,
        "mass_limit": breakdown.derived.get("mass_limit") or design["tmf"],
        "issues": issues,
        "violations": violations,
        "can_save": not violations or design["allow_rule_breaking"],
        "used_by": used_by,
        "factions": store.faction_choices(design["ruleset"], keep=design["faction"]),
        "system_groups": _system_groups(rs.system_types(design.get("race", "human"), options)),
        "fighter_types": rs.fighter_types(options),
        "fighter_label": common.fighter_label,
        # Field names and choices for each system type's parameters, from the picker.
        "param_defs": {d.type: {p.name: p for p in d.params}
                       for d in rs.system_types(design.get("race", "human"), options)},
        "loadout_points": rs.loadout_points(design, None, {}),
        "max_stages": getattr(rs, "max_stages", 1),
        "svg": Markup(ssd_layout.to_svg(ssd_layout.layout(design))),
        "npv_book": design["source"].get("npv_book") if design["source"].get("kind") == "catalog" else None,
    }


def _class_presets() -> list[tuple]:
    """The New design form's class picker: each ruleset's presets with their form values."""
    return [(rs, [(presets.preset_key(rs.id, i), p) for i, p in enumerate(presets.class_presets(rs.id))])
            for rs in RULESETS.values()]


@app.route("/design")
def design() -> str:
    return render_template(
        "design.html", active_tab="design", library=_library(request.args.get("q", "")),
        rulesets=list(RULESETS.values()), selected=None, class_presets=_class_presets(),
    )


@app.route("/design/<design_id>")
def design_detail(design_id: str) -> str:
    working, dirty = store.working_design(design_id)
    if not working:
        abort(404)
    return render_template(
        "design.html", active_tab="design", library=_library(request.args.get("q", "")),
        rulesets=list(RULESETS.values()), selected=_design_context(working, dirty),
        class_presets=_class_presets(), last_system_type=session.get("system_type", ""),
    )


NEW_FACTION = "__new__"


def _chosen_faction(form, race: str) -> tuple[str | None, str]:
    """A faction picker's value. "New faction" names one in the box beside it, made on the spot
    for the design's race; with the box empty the choice stays NEW_FACTION and the caller says so."""
    faction = form.get("faction") or None
    if faction != NEW_FACTION:
        return faction, ""
    fid, msg = store.faction_for_name(form.get("new_faction", ""), race)
    return (fid, msg) if fid else (NEW_FACTION, msg)


@app.route("/design/new", methods=["POST"])
def design_new() -> Response:
    fleet = current_fleet()
    race = request.form.get("race") or (fleet or {}).get("race") or "human"
    faction, msg = _chosen_faction(request.form, race)
    if faction == NEW_FACTION:
        flash(msg, "error")
        return redirect(url_for("design"))
    created, msg = store.new_design(
        request.form.get("ruleset", ""), race, faction, request.form.get("name", ""),
        request.form.get("class_preset", ""),
    )
    flash(msg, "success" if created else "error")
    if not created:
        return redirect(url_for("design"))
    return redirect(url_for("design_detail", design_id=created["id"]))


def _apply_form(design: dict) -> dict:
    """The workbench posts the whole design; rules maths stays in the ruleset (PLAN 2.7)."""
    form = request.form
    old_tmf, old_code, old_label = design["tmf"], design["type_code"], design["type_label"]
    design["name"] = form.get("name", design["name"]).strip()[:80] or design["name"]
    design["type_label"] = form.get("type_label", "").strip()[:60]
    design["type_code"] = form.get("type_code", "").strip()[:8]
    kinds = getattr(RULESETS.get(design["ruleset"]), "hull_kinds", ("warship",))
    design["hull_kind"] = form.get("hull_kind") if form.get("hull_kind") in kinds else "warship"
    faction, _msg = _chosen_faction(form, design.get("race") or "human")
    if faction != NEW_FACTION:  # "New faction" with no name keeps the faction it had
        design["faction"] = faction
    for field in ("tmf", "hull_boxes", "armour", "thrust"):
        if form.get(field) is not None:
            design[field] = max(0, int(form.get(field) or 0))
    if design["type_code"] != old_code and design["type_label"] == old_label:
        # A known class code typed in names the type too, unless the type was edited as well.
        known = presets.class_for_code(design["ruleset"], design["type_code"], design["tmf"])
        if known:
            design["type_label"], design["type_code"] = known
    elif design["tmf"] != old_tmf and design["type_code"] == old_code:
        # MASS moved out of the class's band: the class follows, nothing else is re-preset.
        new_type = presets.reclass(design)
        if new_type:
            design["type_label"], design["type_code"] = new_type
    if form.get("armour_layers") is not None:
        # The Phalon shell, inner layer first, as "8, 4, 4" (FB2 p.35). Blank means one layer.
        design["armour_layers"] = [
            max(0, int(part)) for part in re.split(r"[,\s]+", form["armour_layers"].strip())
            if part.isdigit()
        ]
    design["ftl"] = form.get("ftl") == "on"
    if "advanced-present" in form:
        # Only a ruleset with tech levels draws these checkboxes; the marker keeps an unticked
        # box from reading as "the form did not say".
        for field in ("hull_advanced", "drive_advanced", "ftl_advanced"):
            design[field] = form.get(field) == "on"
    design["streamlining"] = form.get("streamlining", "none")
    design["allow_rule_breaking"] = form.get("allow_rule_breaking") == "on"
    design["notes"] = form.get("notes", "")[:4000]
    for system in design["systems"]:
        prefix = f"sys-{system['uid']}-"
        arcs = form.getlist(prefix + "arcs")
        if arcs or (prefix + "arcs-present") in form:
            system["arcs"] = arcs
        for key in list(system):
            if key in ("uid", "type", "arcs"):
                continue
            if isinstance(system[key], list):
                # A magazine's feeds: checkboxes, so an all-unchecked set needs the marker too.
                if (prefix + key + "-present") in form:
                    system[key] = form.getlist(prefix + key)
                continue
            value = form.get(prefix + key)
            if value == "more":
                # An open-ended setting's dropdown ends in "More" and a field to type the number.
                value = form.get(prefix + key + "-more", "").strip() or None
            if value is None:
                continue
            system[key] = value if isinstance(system[key], str) and not value.isdigit() else int(value or 0)
    design["default_loadout"] = _read_loadout(design)
    return design


def _read_loadout(design: dict) -> dict:
    form = request.form
    fighters: list[dict] = []
    craft: list[dict] = []
    magazines: list[dict] = []
    for system in design["systems"]:
        uid = system["uid"]
        if system["type"] in ("hangar", "fighter_group", "drone_womb"):
            if f"fighter-{uid}-0-type" in form:
                fighters += _read_fighter_groups(system)
                mass = _form_count(f"craft-{uid}")
                if mass:
                    craft.append({"hangar": uid, "mass": mass})
            else:
                fighters.append({"hangar": uid, "type": form.get(f"loadout-{uid}", "standard")})
        elif system["type"] == "sm_magazine":
            if f"salvos-{uid}-std" in form:
                # Counts and a stage count per magazine (CD p.25: never a mix of regular and
                # multi-stage loads in one magazine).
                entry = {"magazine": uid, "salvos": ["std"] * _form_count(f"salvos-{uid}-std")
                         + ["er"] * _form_count(f"salvos-{uid}-er")}
                stages = _form_count(f"stages-{uid}")
                if stages > 1:
                    entry["stages"] = stages
                magazines.append(entry)
            else:
                magazines.append({"magazine": uid, "salvos": form.getlist(f"salvos-{uid}")})
    # FB2 p.35: a Phalon pulser is configured L, M or C before a battle. "" leaves it blank,
    # which is what the book's own sheets print.
    pulsers = [
        {"pulser": system["uid"], "mode": form.get(f"pulser-{system['uid']}", "")}
        for system in design["systems"] if system["type"] == "pulser"
    ]
    loadout = {
        "fighters": [f for f in fighters if f["type"]],
        "magazines": magazines,
        "pulsers": [x for x in pulsers if x["mode"] in ("L", "M", "C")],
    }
    if craft:
        loadout["craft"] = craft
    return loadout


def _form_count(name: str) -> int:
    value = request.form.get(name, "")
    return min(999, int(value)) if value.isdigit() else 0


def _read_fighter_groups(hangar: dict) -> list[dict]:
    """One row per bay: the type ("" leaves the bay empty), FTL and kinetic capability, and the
    swing roles it may also launch as (Cross Dimensions, CD p.30)."""
    groups = []
    bays = hangar.get("bays") if isinstance(hangar.get("bays"), int) else 1
    for index in range(max(1, min(bays, 99))):
        prefix = f"fighter-{hangar['uid']}-{index}-"
        fighter_type = request.form.get(prefix + "type", "")
        if not fighter_type:
            continue
        entry = {"hangar": hangar["uid"], "type": fighter_type}
        extras = [x for x in ("ftl", "kinetic") if request.form.get(prefix + x) == "on"]
        swing = [t for t in request.form.getlist(prefix + "swing") if t != fighter_type]
        if extras:
            entry["extras"] = extras
        if swing:
            entry["swing"] = swing
        groups.append(entry)
    return groups


@app.route("/design/<design_id>", methods=["POST"])
def design_update(design_id: str) -> Response:
    working, _dirty = store.working_design(design_id)
    if not working:
        abort(404)
    action = request.form.get("action", "")

    if store.is_catalog(design_id) and action != "make_variant":
        flash(_("Catalog designs are read-only; make a variant."), "error")
        return redirect(url_for("design_detail", design_id=design_id))

    if action == "make_variant":
        variant, msg = store.make_variant(design_id)
        flash(msg, "success" if variant else "error")
        return redirect(url_for("design_detail", design_id=variant["id"] if variant else design_id))

    if action == "discard":
        ok, msg = store.discard_draft(design_id)
        flash(msg, "success" if ok else "error")
        return redirect(url_for("design_detail", design_id=design_id))

    if action == "delete":
        ok, msg = store.delete_design(design_id)
        flash(msg, "success" if ok else "error")
        return redirect(url_for("design_detail", design_id=design_id) if not ok else url_for("design"))

    try:
        working = _apply_form(working)
    except ValueError:
        flash(_("Please enter a valid number."), "error")
        return redirect(url_for("design_detail", design_id=design_id))

    # The Add-system picker stays on the last pick, so adding several of a kind is one click each.
    if request.form.get("system_type"):
        session["system_type"] = request.form["system_type"]

    if action == "add_system":
        ok, msg = store.add_system(working, request.form.get("system_type", ""))
        if not (ok and request.form.get("autosave")):
            flash(msg, "success" if ok else "error")
    elif action == "remove_system":
        ok, msg = store.remove_system(working, request.args.get("uid") or request.form.get("uid", ""))
        if not (ok and request.form.get("autosave")):
            flash(msg, "success" if ok else "error")
    elif action in ("save", "refit", "variant"):
        ok, msg, saved_id = store.save_design(working, mode=action)
        flash(msg, "success" if ok else "error")
        if ok:
            return redirect(url_for("design_detail", design_id=saved_id))
    elif action not in ("apply", "autosave"):
        flash(_("Unknown action."), "error")
        return redirect(url_for("design_detail", design_id=design_id))

    # Edits made in the page (static/autosave.js) are saved as they come, as long as no ship
    # uses the design and it keeps the rules; otherwise they wait in the draft for a refit, a
    # new variant or a fix. Either way the page says so, so there is no message here.
    if request.form.get("autosave") and store.save_design(working)[0]:
        return redirect(url_for("design_detail", design_id=design_id))
    store.save_draft(working)
    return redirect(url_for("design_detail", design_id=design_id))


# ---- Print dialog (PLAN 10.3) -------------------------------------------------------------------


@app.route("/print")
def print_dialog() -> str:
    fleet = current_fleet()
    if not fleet:
        abort(404)
    others = [f for f in store.list_fleets() if f["id"] != fleet["id"]]
    return render_template("print.html", active_tab="fleet_overview", fleet=fleet, others=others,
                           paper=store.load_settings()["paper"])


@app.route("/print", methods=["POST"])
def print_pdf() -> Response:
    fleet = current_fleet()
    if not fleet:
        abort(404)
    fleets = [fleet]
    second_id = request.form.get("second_fleet")
    if second_id:
        second = store.get_fleet(second_id)
        if not second:
            flash(_("The second fleet was not found."), "error")
            return redirect(url_for("print_dialog"))
        fleets.append(second)
    problem = pdf_export.battle_pack_error(fleets)
    if problem:
        flash(problem, "error")
        return redirect(url_for("print_dialog"))

    form = request.form
    options = pdf_export.PrintOptions(
        paper=form.get("paper", "A4"),
        roster=form.get("roster") == "on",
        sheets=form.get("sheets") == "on",
        orders=form.get("orders") == "on",
        tracker=form.get("tracker") == "on",
        quickref=form.get("quickref") == "on",
        damage=form.get("damage") == "on",
        include_docked=form.get("include_docked") == "on",
        blank=form.get("blank") == "on",
        blank_pulsers=form.get("blank_pulsers") == "on",
    )
    data = pdf_export.fleet_pdf(fleets, [store.designs_for_fleet(f) for f in fleets], options)
    name = "_".join(f["name"].replace(" ", "_") for f in fleets)[:60] or "fleet"
    return Response(data, mimetype="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{name}.pdf"'})


# ---- Campaign tab (PLAN 9.5, 11.1) ---------------------------------------------------------------


@app.route("/campaign")
def campaign() -> str:
    fleet = current_fleet()
    if not fleet:
        return render_template("campaign.html", active_tab="campaign", selected=None)
    designs = store.designs_for_fleet(fleet)
    ships = []
    for ship in fleet["ships"]:
        design = designs.get(ship["design_id"])
        left, total = fleet_rules.crew_factors_left(design, ship["damage"])
        ships.append({
            "ship": ship,
            "design": design,
            "svg": Markup(ssd_layout.to_svg(ssd_layout.layout(design, damage=ship["damage"])))
            if design else Markup(""),
            "hull_boxes": fleet_rules.hull_boxes(design),
            "crew_factors": left,
            "crew_factors_total": total,
            "crippled": fleet_rules.ship_is_crippled(design, ship["damage"]),
            "systems_out": fleet_rules.repairable_systems(design, ship["damage"]),
            "system_labels": fleet_rules.system_labels(design),
        })
    return render_template("campaign.html", active_tab="campaign", statuses=store.STATUSES,
                           selected={"fleet": fleet, "ships": ships,
                                     "ruleset": RULESETS.get(fleet["ruleset"])})


@register_action("set_damage")
def _set_damage(fleet: dict) -> tuple[bool, str]:
    form = request.form
    return store.set_ship_damage(
        fleet, form.get("uid", ""),
        hull=int(form.get("hull") or 0), armour=int(form.get("armour") or 0),
        drive_hits=int(form.get("drive_hits") or 0),
        systems_out=form.getlist("systems_out"),
    )


@register_action("click_ssd")
def _click_ssd(fleet: dict) -> tuple[bool, str]:
    """One click on the diagram: a hull box, an armour circle or a system (PLAN 9.5)."""
    uid = request.form.get("uid", "")
    kind, _sep, value = (request.form.get("ref") or "").partition(":")
    if kind == "system":
        return store.toggle_system_out(fleet, uid, value)
    if kind in ("hull", "armour"):
        # Clicking box N marks damage up to N; clicking the last marked box unmarks it.
        ship = next((s for s in fleet["ships"] if s["uid"] == uid), None)
        if not ship:
            return False, _("Ship not found.")
        number = int(value or 0)
        current = ship["damage"][kind]
        return store.set_ship_damage(fleet, uid, **{kind: number - 1 if current == number else number})
    return False, _("Nothing to change there.")


@register_action("repair")
def _repair(fleet: dict) -> tuple[bool, str]:
    form = request.form
    ship = next((s for s in fleet["ships"] if s["uid"] == form.get("uid")), None)
    if not ship:
        return False, _("Ship not found.")
    design = store.get_design(ship["design_id"])
    chosen = form.getlist("repair_system")
    successes = {uid: 1 for uid in form.getlist("repair_success")}
    successes["drive"] = int(form.get("drive_successes") or 0)
    plan = fleet_rules.repair_plan(design, ship["damage"], int(form.get("hull_repaired") or 0),
                                   chosen, successes)
    if plan["too_many"]:
        return False, _("Only {n} systems may be repaired in a week.",
                        n=fleet_rules.REPAIR_SYSTEMS_PER_WEEK)
    return store.repair_ship(fleet, ship["uid"], plan)


@register_action("replenish")
def _replenish(fleet: dict) -> tuple[bool, str]:
    return store.replenish_ship(fleet, request.form.get("uid", ""))


@register_action("add_log")
def _add_log(fleet: dict) -> tuple[bool, str]:
    return store.add_log_entry(fleet, int(request.form.get("week") or 0),
                               request.form.get("text", ""))


@app.route("/campaign/<fleet_id>/action", methods=["POST"])
def campaign_action(fleet_id: str) -> Response:
    fleet = store.get_fleet(fleet_id)
    if not fleet:
        abort(404)
    if dispatch_action(fleet):
        store.save_fleet(fleet)
    return redirect(url_for("campaign"))


@app.route("/dice/<int:sides>")
def dice(sides: int) -> Response:
    """Optional dice for the repair panel; results can always be typed in instead (PLAN 9.5)."""
    if sides not in (6,):
        abort(404)
    return Response(str(secrets.randbelow(sides) + 1), mimetype="text/plain")


# ---- Rulebooks (PLAN 12) --------------------------------------------------------------------------


def books() -> dict[str, object]:
    """Every book the app ships, by its code (FB1, FT, CD, ...).

    The rulesets' own books first, then the reference-only ones whose rules nothing implements
    yet; a ruleset book wins a code clash, since that is the one page links resolve against.
    """
    shipped = {b.code: b for b in REFERENCE_BOOKS}
    shipped.update({b.code: b for rs in RULESETS.values() for b in rs.books})
    return shipped


def books_in_order() -> list:
    """The shipped books in publication order (FT, MT, FB1, FB2, CD, PC, PCE)."""
    return sorted(books().values(), key=lambda b: book_sort_key(b.code))


def book_url(code: str, page: int | None = None) -> str:
    """The link behind every "FB1 p.16" in the UI."""
    return url_for("rulebook", code=code, page=page or 0)


app.jinja_env.globals["book_url"] = book_url


@app.route("/rulebook/<code>")
def rulebook(code: str) -> str | Response:
    book = books().get(code)
    if not book:
        abort(404)
    page = max(0, int(request.args.get("page") or 0))
    pdf_page = page + book.page_offset if page else 1
    if store.load_settings()["pdf_viewer"] == "system" and not BROWSER_MODE:
        # The player asked for their own PDF viewer: hand the file over and let the browser or
        # the OS open it (desktop only; the web build has nowhere to hand it to).
        return redirect(url_for("rulebook_file", code=code) + f"#page={pdf_page}")
    return render_template("rulebook.html", active_tab="settings", book=book, page=page,
                           pdf_page=pdf_page, books=books_in_order())


@app.route("/rulebook/<code>/file")
def rulebook_file(code: str) -> Response:
    book = books().get(code)
    if not book:
        abort(404)
    path = paths.bundle_dir() / "rulebooks" / book.file
    if not path.is_file():
        abort(404)
    return send_file(path, mimetype="application/pdf", download_name=book.file)


@app.route("/settings")
def settings() -> str:
    return render_template("settings.html", active_tab="settings", languages=i18n.LANGUAGES,
                           settings=store.load_settings(),
                           books=books_in_order())


@app.route("/settings", methods=["POST"])
def settings_save() -> Response:
    # Each Settings panel posts its own fields; a field a form leaves out keeps its value.
    fields = ("paper", "pdf_viewer", "theme")
    ok, msg = store.save_settings(**{k: request.form[k] for k in fields if k in request.form})
    if ok and request.form.get("autosave"):
        msg = ""
    # The top-bar look picker posts `next` and goes back to its page without a flash.
    nxt = request.form.get("next", "")
    if nxt.startswith("/") and not nxt.startswith(("//", "/\\")):
        if not ok:
            flash(msg, "error")
        return redirect(nxt)
    if msg:
        flash(msg, "success" if ok else "error")
    return redirect(url_for("settings"))


@app.route("/settings/factions", methods=["POST"])
def settings_factions() -> tuple[str, int]:
    """The faction pickers' show/hide toggles, posted in the background as they are ticked."""
    keys = ("show_custom_factions", "show_other_race_factions")
    store.save_settings(**{k: request.form[k] == "1" for k in keys if k in request.form})
    return "", 204


@app.route("/heartbeat", methods=["POST"])
def heartbeat() -> tuple[str, int]:
    """Pinged periodically by every open page; see idle_watchdog.py."""
    note_heartbeat()
    return ("", 204)


@app.route("/heartbeat/closing", methods=["POST"])
def heartbeat_closing() -> tuple[str, int]:
    """Pinged via sendBeacon when a page unloads; see idle_watchdog.py."""
    note_closing()
    return ("", 204)


@app.errorhandler(404)
def _not_found(_exc) -> tuple[str, int]:
    return render_template("error.html", message=_("Page not found.")), 404


def main() -> None:
    port = int(os.environ.get("PORT", 5000))
    if paths.is_frozen():
        url = f"http://127.0.0.1:{port}/"
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
        from waitress import serve

        threading.Thread(
            target=serve, args=(app,), kwargs={"host": "127.0.0.1", "port": port}, daemon=True
        ).start()

        import idle_watchdog

        # Windowless build: without these the server would outlive the browser tab invisibly.
        idle_watchdog.start()

        if sys.platform.startswith("win"):
            try:
                import tray

                tray.run(url)  # blocks until Quit
                return
            except Exception as exc:
                # Tray backends fail in ways we can't enumerate; idle_watchdog still exits us.
                logger.info("Tray icon unavailable, falling back to idle_watchdog: %s", exc)

        threading.Event().wait()
    else:
        # Reloader on; the Werkzeug debugger is an interactive console for anyone who reaches a
        # traceback, so it stays opt-in.
        debug = os.environ.get("FTFM_DEBUG") == "1"
        app.run(debug=debug, use_reloader=True, host="127.0.0.1", port=port)


if __name__ == "__main__":
    main()
