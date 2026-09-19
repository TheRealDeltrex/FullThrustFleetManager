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

from flask import Flask, Response, abort, flash, redirect, render_template, request, url_for

import i18n
import paths
from i18n import _
from idle_watchdog import note_closing, note_heartbeat

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


@app.route("/fleet")
def fleet_overview() -> str:
    return render_template("fleet.html", active_tab="fleet_overview")


@app.route("/design")
def design() -> str:
    return render_template("design.html", active_tab="design")


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
