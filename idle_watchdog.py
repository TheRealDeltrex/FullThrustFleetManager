"""Auto-shutdown for the frozen, windowless build.

The packaged exe has no window and no console (fleetmanager.spec, console=False), so closing the
browser tab alone would leave waitress serving invisibly. This tracks whether any page is still
open and exits the process once none is.

Two signals feed it (the /heartbeat routes in app.py and the matching JS in base.html):
- a periodic "still open" ping from every loaded page;
- an immediate "closing" signal (sendBeacon on pagehide). That also fires on ordinary in-app
  navigation, so it only shuts down if no fresh ping follows within a short grace period.

A generous no-heartbeat fallback covers the browser being killed outright.
"""

from __future__ import annotations

import os
import threading
import time

_HEARTBEAT_TIMEOUT = 180.0
_CLOSING_GRACE = 3.0
_POLL_INTERVAL = 1.0

_lock = threading.Lock()
_last_heartbeat = time.time()
_closing_at: float | None = None


def note_heartbeat() -> None:
    global _last_heartbeat, _closing_at
    with _lock:
        _last_heartbeat = time.time()
        _closing_at = None


def note_closing() -> None:
    global _closing_at
    with _lock:
        _closing_at = time.time()


def _should_shutdown() -> bool:
    with _lock:
        now = time.time()
        if _closing_at is not None and now - _closing_at > _CLOSING_GRACE:
            return True
        return now - _last_heartbeat > _HEARTBEAT_TIMEOUT


def start() -> None:
    def _loop():
        while True:
            time.sleep(_POLL_INTERVAL)
            if _should_shutdown():
                os._exit(0)

    threading.Thread(target=_loop, daemon=True).start()
