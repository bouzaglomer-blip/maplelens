"""MapleLens entry point: watch the game window and run the tools."""

import os
import sys
import time
import traceback
from collections.abc import Callable
from importlib.metadata import version

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from maplelens import capture
from maplelens.overlay import Box, Layer
from maplelens.readers import glyphs, ocr, read_all
from maplelens.store import data_dir, load_settings, save_settings
from maplelens.tools.exp_meter.history import open_db
from maplelens.tools.exp_meter.ui import ExpMeterTool
from maplelens.tools.path_arrow import maps
from maplelens.tools.path_arrow.ui import PathArrowTool

_TICK_MS = 500
# The game client's window title. With no title saved, only a window with exactly this
# title counts, so a browser tab like "MapleStory wiki - Chrome" never does.
DEFAULT_TITLE = "MapleStory"


def build_box(settings: dict, save: Callable[[], None], tools: list) -> Box:
    """The one overlay box: a tab per tool, and Quit in the right-click menu."""
    box = Box("exp_meter", settings, save)
    for tool in tools:
        box.add_tab(tool.title, tool.tab)
    # quit() runs aboutToQuit, where main() saves through shutdown()
    box.add_menu_item("Quit MapleLens", QApplication.quit)
    box.show()
    return box


def find_game(settings: dict, save: Callable[[], None]) -> int | None:
    """The game window, or None.

    A saved title matches exactly, else as a substring. With none saved, a window titled
    exactly DEFAULT_TITLE counts, and its title is saved the first time one turns up.
    """
    if settings["window_title"]:
        return capture.find_window(settings["window_title"])
    found = capture.find_window(DEFAULT_TITLE, exact=True)
    if found is not None:
        settings["window_title"] = DEFAULT_TITLE
        save()
    return found


def report_once(e: Exception, seen: set[str]) -> None:
    """Print a traceback the first time each distinct error turns up."""
    key = f"{type(e).__name__}: {e}"
    if key not in seen:
        seen.add(key)
        traceback.print_exc()


def update_tools(  # noqa: PLR0913, PLR0917 - one per tool plus the frame; a bundle would hide them
    box: Box, exp, path, reading, rect, now: float, seen: set[str]
) -> None:
    """Feed both tools the same reading; the Path tab shows a dot while a trip runs.

    Each tool runs on its own: one raising doesn't stop the other.
    """
    try:
        exp.update(reading, rect, now)
    except Exception as e:
        report_once(e, seen)
    try:
        path.update(reading, rect, now)
    except Exception as e:
        report_once(e, seen)
        path.arrow.hide()  # never leave it pointing from a stale spot
    box.set_tab_dot(1, path.running)  # the Path tab's index in build_box's tools list


def self_check() -> int:
    """0 if everything MapleLens ships loads, else 1: the build's smoke test.

    Templates, maps.json, every minimap picture, the OCR engine and the version.
    The exit code is the answer: the frozen app is windowed, so it has no console.
    """
    try:
        glyphs.load_all()
        maps.load()
        pictures = sorted(maps.PICTURES.glob("*.png"))
        if not pictures or any(maps.picture(p.stem) is None for p in pictures):
            return 1
        if not version("maplelens"):  # None when its metadata file is missing
            return 1
    except Exception:
        return 1
    return 0 if ocr.engine() is not None else 1


def main() -> int:
    if "--self-check" in sys.argv[1:]:
        return self_check()
    if sys.platform == "darwin":  # Qt must never bring MapleLens to the front over the game
        os.environ.setdefault("QT_MAC_DISABLE_FOREGROUND_APPLICATION_TRANSFORM", "1")
        os.environ.setdefault("QT_MAC_SET_RAISE_PROCESS", "0")
    app = QApplication(sys.argv)
    if sys.platform == "darwin":
        from maplelens import overlay_mac

        overlay_mac.make_accessory()
        app.processEvents()  # finish launching first: a window shown before that activates us
    capture.set_dpi_aware()
    if not capture.ensure_access():
        return 1
    path = data_dir() / "settings.json"
    settings = load_settings(path)
    layer = Layer()

    def save() -> None:
        save_settings(path, settings)

    tool = ExpMeterTool(settings, open_db(data_dir() / "maplelens.db"))
    # the lambda defers the lookup: `box` is built from path_tool on the next line
    path_tool = PathArrowTool(settings, save, layer, lambda on: box.allow_typing(on))  # noqa: PLW0108
    box = build_box(settings, save, [tool, path_tool])
    hwnd = None
    seen: set[str] = set()  # error types/messages already printed

    def tick() -> None:
        nonlocal hwnd
        now = time.time()
        hwnd = hwnd or find_game(settings, save)
        rect = capture.client_rect(hwnd) if hwnd else None
        if rect is None:
            hwnd = None  # gone or minimized: look again next tick
            layer.hide()
            update_tools(box, tool, path_tool, None, None, now, seen)
            return
        layer.follow(rect)
        layer.show()
        try:
            reading = read_all(capture.grab(hwnd, rect), now)
        except Exception as e:  # a bad tick counts as no reading; the box still follows the game
            report_once(e, seen)
            reading = None
        update_tools(box, tool, path_tool, reading, rect, now, seen)
        box.place(rect)

    timer = QTimer()
    timer.timeout.connect(tick)
    timer.start(_TICK_MS)
    app.aboutToQuit.connect(lambda: tool.shutdown(time.time()))
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
