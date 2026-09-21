"""System tray icon for the frozen build.

The packaged exe runs windowless (fleetmanager.spec, console=False), so once the browser tab is
closed there is no sign the app is running. The tray icon gives an explicit Quit and a way to
reopen the browser.
"""

from __future__ import annotations

import os
import webbrowser

from PIL import Image

import i18n
import paths


def _icon_image() -> Image.Image:
    """The app logo (static/favicon.png), shipped with the build."""
    return Image.open(paths.bundle_dir() / "static" / "favicon.png").convert("RGBA")


def run(url: str) -> None:
    """Blocks on the tray icon's event loop until Quit. Call from the main thread."""
    import pystray

    def _open(_icon=None, _item=None) -> None:
        webbrowser.open(url)

    def _quit(icon, _item) -> None:
        icon.stop()
        os._exit(0)

    _ = i18n.gettext
    icon = pystray.Icon(
        "FullThrustFleetManager",
        _icon_image(),
        _("Full Thrust Fleet Manager"),
        menu=pystray.Menu(
            pystray.MenuItem(_("Open Fleet Manager"), _open, default=True),
            pystray.MenuItem(_("Quit"), _quit),
        ),
    )
    icon.run()
