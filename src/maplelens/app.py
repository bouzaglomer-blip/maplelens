"""MapleLens entry point: watch the game window and run the tools."""

import sys
import time
import traceback
from collections.abc import Callable

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from maplelens.capture import client_rect, find_window, grab, set_dpi_aware
from maplelens.overlay import Box, Layer
from maplelens.readers import read_all
from maplelens.store import data_dir, load_settings, save_settings
from maplelens.tools.exp_meter.history import open_db
from maplelens.tools.exp_meter.ui import ExpMeterTool

_TICK_MS = 500


def build_box(settings: dict, save: Callable[[], None], tools: list) -> Box:
    """The one overlay box: a tab per tool, and Quit in the right-click menu."""
    box = Box("exp_meter", settings, save)
    for tool in tools:
        box.add_tab(tool.title, tool.tab)
    # quit() runs aboutToQuit, where main() saves through shutdown()
    box.add_menu_item("Quit MapleLens", QApplication.quit)
    box.show()
    return box


def main() -> int:
    app = QApplication(sys.argv)
    set_dpi_aware()
    path = data_dir() / "settings.json"
    settings = load_settings(path)
    title = settings["window_title"]
    if not title:
        print("Run: uv run python scripts/grab.py --title <game title> --label first")
        return 1

    layer = Layer()

    def save() -> None:
        save_settings(path, settings)

    tool = ExpMeterTool(settings, open_db(data_dir() / "maplelens.db"), save)
    box = build_box(settings, save, [tool])
    hwnd = None
    seen: set[str] = set()  # error types/messages already printed

    def tick() -> None:
        nonlocal hwnd
        now = time.time()
        hwnd = hwnd or find_window(title)
        rect = client_rect(hwnd) if hwnd else None
        if rect is None:
            hwnd = None  # gone or minimized: look again next tick
            layer.hide()
            tool.update(None, None, now)
            return
        layer.follow(rect)
        layer.show()
        try:
            reading = read_all(grab(rect), now)
        except Exception as e:  # a bad tick counts as no reading; the box still follows the game
            key = f"{type(e).__name__}: {e}"
            if key not in seen:
                seen.add(key)
                traceback.print_exc()
            reading = None
        tool.update(reading, rect, now)
        box.place(rect)

    timer = QTimer()
    timer.timeout.connect(tick)
    timer.start(_TICK_MS)
    app.aboutToQuit.connect(lambda: tool.shutdown(time.time()))
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
