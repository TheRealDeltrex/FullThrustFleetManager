"""System tray icon for the frozen build.

The packaged exe runs windowless (fleetmanager.spec, console=False), so once the browser tab is
closed there is no sign the app is running. The tray icon gives an explicit Quit and a way to
reopen the browser.
"""

from __future__ import annotations

import os
import webbrowser

from PIL import Image, ImageDraw

import i18n

_BG = (16, 24, 38, 255)
_FG = (79, 155, 232, 255)


def _icon_image() -> Image.Image:
    """A simple arrowhead ship silhouette on a dark disc."""
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse((2, 2, 62, 62), fill=_BG, outline=_FG, width=3)
    draw.polygon([(32, 10), (48, 50), (32, 42), (16, 50)], fill=_FG)
    return img


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
