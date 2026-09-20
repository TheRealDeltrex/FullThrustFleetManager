"""Full Thrust Fleet Manager: Flask routes (layer 4, thin).

Parses requests, calls the layers above (rulesets -> fleet_rules -> store), renders templates.
No rules maths here (PLAN 2.7).
"""

from __future__ import annotations

import logging
import os
import sys
import threading
import webbrowser
from collections.abc import Callable
from logging.handlers import RotatingFileHandler

from flask import Flask, Response, abort, flash, redirect, render_template, request, session, url_for
from markupsafe import Markup

import fleet_rules
import i18n
import paths
import ssd_layout
import store
from i18n import _
from idle_watchdog import note_closing, note_heartbeat
from rulesets import RULESETS

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
    return {
        "BROWSER_MODE": BROWSER_MODE,
        "IS_FROZEN": paths.is_frozen(),
        "APP_VERSION": APP_VERSION,
        "LANG": i18n.get_language(),
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
    resp.headers.setdefault("X-Frame-Options", "DENY")
    resp.headers.setdefault("Referrer-Policy", "same-origin")
    resp.headers.setdefault("Content-Security-Policy", "frame-ancestors 'none'")
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
    if msg:
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
    if not fleet:
        return {"current_fleet": None, "all_fleets": store.list_fleets(), "fleet_points": 0}
    designs = store.designs_for_fleet(fleet)
    return {
        "current_fleet": fleet,
        "all_fleets": store.list_fleets(),
        "fleet_points": fleet_rules.fleet_points(fleet, designs),
        "fleet_badges": fleet_rules.badges(fleet, designs),
    }


def _fleet_context(fleet: dict, view: str) -> dict:
    designs = store.designs_for_fleet(fleet)
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
        "library": sorted(store.list_designs(fleet["ruleset"]) + store.catalog_designs(fleet["ruleset"]),
                          key=lambda d: d["name"].lower()),
        "factions": store.builtin_factions(fleet["ruleset"]) + store.custom_factions(),
        "option_keys": fleet_rules.FLEET_OPTION_KEYS,
    }


@app.route("/fleet")
def fleet_overview() -> str:
    fleet = current_fleet()
    if not fleet:
        return render_template("fleet.html", active_tab="fleet_overview", selected=None,
                               rulesets=list(RULESETS.values()))
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
        options={k: form.get("opt-" + k) == "on" for k in fleet_rules.FLEET_OPTION_KEYS},
        notes=form.get("notes", ""),
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
    for d in sorted(store.catalog_designs(), key=lambda d: (d["ruleset"], d["name"].lower())):
        if matches(d):
            catalog.setdefault(d["source"].get("book") or d["ruleset"], []).append(d)
    return {"mine": mine, "catalog": catalog, "query": query}


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
        "system_types": rs.system_types(design.get("race", "human"), options),
        "fighter_types": rs.fighter_types(options),
        "svg": Markup(ssd_layout.to_svg(ssd_layout.layout(design))),
        "npv_book": design["source"].get("npv_book") if design["source"].get("kind") == "catalog" else None,
    }


@app.route("/design")
def design() -> str:
    return render_template(
        "design.html", active_tab="design", library=_library(request.args.get("q", "")),
        rulesets=list(RULESETS.values()), selected=None,
    )


@app.route("/design/<design_id>")
def design_detail(design_id: str) -> str:
    working, dirty = store.working_design(design_id)
    if not working:
        abort(404)
    return render_template(
        "design.html", active_tab="design", library=_library(request.args.get("q", "")),
        rulesets=list(RULESETS.values()), selected=_design_context(working, dirty),
    )


@app.route("/design/new", methods=["POST"])
def design_new() -> Response:
    created, msg = store.new_design(
        request.form.get("ruleset", ""), request.form.get("race", "human"),
        request.form.get("faction") or None, request.form.get("name", ""),
    )
    flash(msg, "success" if created else "error")
    if not created:
        return redirect(url_for("design"))
    return redirect(url_for("design_detail", design_id=created["id"]))


def _apply_form(design: dict) -> dict:
    """The workbench posts the whole design; rules maths stays in the ruleset (PLAN 2.7)."""
    form = request.form
    design["name"] = form.get("name", design["name"]).strip()[:80] or design["name"]
    design["type_label"] = form.get("type_label", "").strip()[:60]
    design["type_code"] = form.get("type_code", "").strip()[:8]
    design["hull_kind"] = "merchant" if form.get("hull_kind") == "merchant" else "warship"
    design["faction"] = form.get("faction") or None
    for field in ("tmf", "hull_boxes", "armour", "thrust"):
        if form.get(field) is not None:
            design[field] = max(0, int(form.get(field) or 0))
    design["ftl"] = form.get("ftl") == "on"
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
            value = form.get(prefix + key)
            if value is None:
                continue
            system[key] = value if isinstance(system[key], str) and not value.isdigit() else int(value or 0)
    design["default_loadout"] = _read_loadout(design)
    return design


def _read_loadout(design: dict) -> dict:
    fighters = [
        {"hangar": system["uid"], "type": request.form.get(f"loadout-{system['uid']}", "standard")}
        for system in design["systems"] if system["type"] in ("hangar", "fighter_group")
    ]
    magazines = [
        {"magazine": system["uid"],
         "salvos": request.form.getlist(f"salvos-{system['uid']}")}
        for system in design["systems"] if system["type"] == "sm_magazine"
    ]
    return {"fighters": [f for f in fighters if f["type"]], "magazines": magazines}


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

    if action == "add_system":
        ok, msg = store.add_system(working, request.form.get("system_type", ""))
        flash(msg, "success" if ok else "error")
    elif action == "remove_system":
        ok, msg = store.remove_system(working, request.args.get("uid") or request.form.get("uid", ""))
        flash(msg, "success" if ok else "error")
    elif action in ("save", "refit", "variant"):
        ok, msg, saved_id = store.save_design(working, mode=action)
        flash(msg, "success" if ok else "error")
        if ok:
            return redirect(url_for("design_detail", design_id=saved_id))
    elif action != "apply":
        flash(_("Unknown action."), "error")
        return redirect(url_for("design_detail", design_id=design_id))

    store.save_draft(working)
    return redirect(url_for("design_detail", design_id=design_id))


@app.route("/campaign")
def campaign() -> str:
    return render_template("campaign.html", active_tab="campaign")


@app.route("/settings")
def settings() -> str:
    return render_template("settings.html", active_tab="settings", languages=i18n.LANGUAGES)


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
