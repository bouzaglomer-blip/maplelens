"""MapleLens entry point: watch the game window and run the tools."""

import os
import sys
import time
import traceback
from collections.abc import Callable
from importlib.metadata import version
from pathlib import Path

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
APP_NAME = "MapleLens"  # also the title of our own windows, which the picker leaves out
# The game client's window title. With no title saved, only a window with exactly this
# title counts, so a browser tab like "MapleStory wiki - Chrome" never does.
DEFAULT_TITLE = "MapleStory"
_log_path: Path | None = None  # where report_once also writes; set by start_log
LOOKING = f"Looking for {DEFAULT_TITLE}… right-click to pick the game window"


def build_box(
    settings: dict,
    save: Callable[[], None],
    tools: list,
    pick: Callable[[str], None] | None = None,
) -> Box:
    """The one overlay box: a tab per tool; the window picker and Quit on right-click."""
    box = Box("exp_meter", settings, save)
    for tool in tools:
        box.add_tab(tool.title, tool.tab)
    if pick:
        box.add_submenu("Pick game window…", game_choices, pick)
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


def game_choices() -> list[str]:
    """Window titles to offer in the picker: every window but MapleLens's own."""
    return [t for t in capture.window_titles() if t != APP_NAME]


def choose_window(settings: dict, save: Callable[[], None], title: str) -> None:
    """Make `title` the game window's title from now on."""
    settings["window_title"] = title
    save()


def start_log(path: Path) -> None:
    """Send report_once to `path` too, emptied now so it holds this run only."""
    global _log_path  # noqa: PLW0603 - one log per process, set once at startup
    path.write_text("", encoding="utf-8")
    _log_path = path


def report_once(e: Exception, seen: set[str]) -> None:
    """Log a traceback the first time each distinct error turns up.

    To the log file, and to stderr when there is one (a windowed exe has none).
    """
    key = f"{type(e).__name__}: {e}"
    if key in seen:
        return
    seen.add(key)
    text = traceback.format_exc()
    if sys.stderr is not None:
        sys.stderr.write(text)
    if _log_path is not None:
        with _log_path.open("a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {text}")


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
    app.setApplicationName(APP_NAME)
    if sys.platform == "darwin":
        from maplelens import overlay_mac

        overlay_mac.make_accessory()
        app.processEvents()  # finish launching first: a window shown before that activates us
    capture.set_dpi_aware()
    if not capture.ensure_access():
        return 1
    start_log(data_dir() / "maplelens.log")
    path = data_dir() / "settings.json"
    settings = load_settings(path)
    layer = Layer()

    def save() -> None:
        save_settings(path, settings)

    tool = ExpMeterTool(settings, open_db(data_dir() / "maplelens.db"))
    # the lambda defers the lookup: `box` is built from path_tool on the next line
    path_tool = PathArrowTool(settings, save, layer, lambda on: box.allow_typing(on))  # noqa: PLW0108
    hwnd = None
    seen: set[str] = set()  # error types/messages already logged

    def pick(title: str) -> None:
        nonlocal hwnd
        choose_window(settings, save, title)
        hwnd = None  # the next tick finds the chosen window

    box = build_box(settings, save, [tool, path_tool], pick)

    def tick() -> None:
        nonlocal hwnd
        now = time.time()
        hwnd = hwnd or find_game(settings, save)
        box.set_status(None if hwnd else LOOKING)  # a minimized game isn't "looking"
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
