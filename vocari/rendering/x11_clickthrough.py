"""Makes a top-level window truly click-through on X11.

Qt's WA_TransparentForMouseEvents is documented to be platform-dependent,
and in practice (PySide6 6.x on X11/xfwm4, at least) it does *not* give a
standalone top-level window a real X input shape - the window still
swallows every click/button event landing on its rectangle at the X
protocol level, Qt's attribute only affects whether Qt's own event
dispatch reacts to it internally. Confirmed by reading the window's actual
Shape-extension INPUT region back from the X server: it covered 100% of
the window's rect despite the attribute being set well before the window
was ever mapped.

The real fix is the same mechanism window managers themselves use for
rounded corners etc: the X Shape extension's INPUT region (as opposed to
its BOUNDING region, which affects what's drawn/visible and is left alone
here - only the input routing changes). Setting it to an empty rectangle
list makes the X server itself pass every click straight through to
whatever is behind the window, for good, independent of window size or
future resizes (an empty region stays empty regardless of geometry).
"""
from __future__ import annotations

from vocari.logging_setup import get_logger

logger = get_logger("overlay.x11")


def make_click_through(win_id: int) -> bool:
    """Best-effort: punches a permanent, empty input-shape hole in the X11
    window `win_id` (as returned by QWidget.winId()). Returns False (and
    logs why) instead of raising if python-xlib isn't installed or the X
    server has no Shape extension - callers should keep whatever fallback
    behavior they already had for that case."""
    try:
        from Xlib import display
        from Xlib.ext import shape
    except ImportError:
        logger.warning("python-xlib недоступен — click-through оверлея на X11 не гарантирован")
        return False

    try:
        d = display.Display()
        if not d.has_extension("SHAPE"):
            logger.warning("X-сервер не поддерживает расширение SHAPE — click-through оверлея не гарантирован")
            return False
        window = d.create_resource_object("window", win_id)
        # Unsorted (0): we're not claiming any particular rectangle order,
        # there simply are none.
        window.shape_rectangles(shape.SO.Set, shape.SK.Input, 0, 0, 0, [])
        d.sync()
        return True
    except Exception:
        logger.exception("Не удалось выставить пустой input-shape для оверлея")
        return False
