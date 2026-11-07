"""MapleLens entry point: watch the game window and run the tools."""

import contextlib
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import traceback
import urllib.request
from collections.abc import Callable
from importlib.metadata import version
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from maplelens import capture, update
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
# Held while MapleLens runs. The Windows installer and uninstaller look for it (AppMutex in
# packaging/windows/maplelens.iss) and ask the player to close MapleLens first.
APP_MUTEX = "MapleLensRunning"
# Tells Setup the app started it to update itself: Setup waits for MapleLens to exit instead
# of asking to close it, then starts the new version (IsUpdateRun in maplelens.iss).
UPDATE_FLAG = "/MAPLELENSUPDATE"


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
    text = "".join(traceback.format_exception(e))  # also for one raised on another thread
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


def mark_running() -> int | None:
    """Create APP_MUTEX on Windows; the handle stays open until MapleLens exits."""
    if sys.platform != "win32":
        return None
    import ctypes

    kernel32 = ctypes.windll.kernel32
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    return kernel32.CreateMutexW(None, False, APP_MUTEX)


def update_cmd(setup: Path) -> list[str]:
    """Setup's command line for an update: Inno's no-prompt flags plus UPDATE_FLAG."""
    return [str(setup), "/SILENT", "/SP-", "/SUPPRESSMSGBOXES", "/NOCANCEL", UPDATE_FLAG]


def install_update(setup: Path) -> None:
    """Hand over to `setup`: start it on its own, then quit the way Quit does.

    Quitting through Qt runs aboutToQuit, which saves the session in progress; Setup
    waits for MapleLens to exit before it replaces anything. If Setup can't start, the
    OSError propagates and MapleLens keeps running.
    """
    subprocess.Popen(
        update_cmd(setup),
        cwd=setup.parent,  # not {app}, the folder Setup replaces
        creationflags=getattr(subprocess, "DETACHED_PROCESS", 0)
        | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
    )
    QApplication.quit()


def update_notice(new: str) -> str:
    """The box's line for an update; it fits TAB_W up to version 10.10.10."""
    return f"Update to {new}: right-click"


def downloading_notice(new: str) -> str:
    return f"Downloading {new}…"


UPDATE_FAILED = "Update failed: right-click"  # the menu item tries again


def _user_agent() -> dict[str, str]:
    return {"User-Agent": f"MapleLens/{version('maplelens')}"}  # nothing about the player


def fetch_latest(repo: str = update.REPO) -> dict:
    """GitHub's latest release of `repo`, as JSON. Sends only MapleLens's version."""
    req = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/releases/latest",
        headers={**_user_agent(), "Accept": "application/vnd.github+json"},
    )
    with urllib.request.urlopen(req, timeout=10) as reply:
        return json.load(reply)


def download_file(url: str, dest: Path) -> None:
    """Save `url` to `dest`. The timeout is per read, so a 60 MB setup can take its time."""
    req = urllib.request.Request(url, headers=_user_agent())
    with urllib.request.urlopen(req, timeout=30) as reply, dest.open("wb") as f:
        shutil.copyfileobj(reply, f)


def clear_updates(folder: Path) -> None:
    """Delete setups left from earlier updates. One still running stays until next time."""
    for old in folder.glob("MapleLens-Setup-*"):
        with contextlib.suppress(OSError):
            old.unlink()


class UpdateCheck:
    """Asks for the latest release a few seconds after start, then once a day, and
    updates on a click of "Update to X.Y.Z…".

    Requests and the download each run on a thread of their own and only fill a slot;
    poll(), called from the tick on the Qt thread, starts them and acts on what they
    left. A slow or hanging request never delays a tick, and the next one waits for it.
    """

    FIRST_S = 5
    EVERY_S = 24 * 3600

    def __init__(  # noqa: PLR0913, PLR0917 - the box, settings and the parts tests swap
        self,
        box: Box,
        settings: dict,
        save: Callable[[], None],
        fetch: Callable[[], dict],
        running: str,
        seen: set[str],
        now: float,
        *,
        folder: Path,
        download: Callable[[str, Path], None] = download_file,
        install: Callable[[Path], None] = install_update,
    ):
        self._box, self._settings, self._save = box, settings, save
        self._fetch, self._running, self._seen = fetch, running, seen
        self._folder, self._download, self._install = folder, download, install
        self._due = now + self.FIRST_S
        self._thread: threading.Thread | None = None
        self._result: tuple[dict | None, Exception | None] = (None, None)
        self._download_thread: threading.Thread | None = None
        self._got: tuple[Path | None, Exception | None] = (None, None)
        self._item = None  # the "Update to X.Y.Z…" menu item, once an update is known
        self.release: update.Release | None = None

    def poll(self, now: float) -> None:
        if self._download_thread is not None and not self._download_thread.is_alive():
            self._download_thread = None
            self._hand_over(*self._got)
        if self._thread is not None and not self._thread.is_alive():
            self._thread = None
            reply, error = self._result
            if error is not None:
                report_once(error, self._seen)
            else:
                self._found(update.parse_latest(reply))
        if self._thread is None and now >= self._due:
            self._due = now + self.EVERY_S
            self._thread = threading.Thread(target=self._ask, daemon=True)
            self._thread.start()

    def _ask(self) -> None:  # on the check's own thread: no Qt here
        try:
            self._result = (self._fetch(), None)
        except Exception as e:
            self._result = (None, e)

    def _found(self, release: update.Release | None) -> None:
        if release is None or not update.is_newer(release, self._running):
            return
        self.release = release
        label = f"Update to {release.version}…"
        if self._item is None:
            self._item = self._box.add_menu_item(label, self._update, first=True)
        else:
            self._item.setText(label)
        downloading = self._download_thread is not None  # its line stays until it ends
        if not downloading and self._settings.get("update_dismissed") != release.version:
            self._box.set_notice(
                update_notice(release.version), lambda: self._dismiss(release.version)
            )

    def _dismiss(self, new: str) -> None:
        self._settings["update_dismissed"] = new
        self._save()

    def _update(self) -> None:
        """The menu item's click: download the setup; poll() hands over once it's checked."""
        if self.release is None or self._download_thread is not None:
            return  # a second click while downloading does nothing
        self._box.set_notice(downloading_notice(self.release.version))
        self._got = (None, None)
        self._download_thread = threading.Thread(
            target=self._get, args=(self.release,), daemon=True
        )
        self._download_thread.start()

    def _get(self, release: update.Release) -> None:  # on the download's own thread: no Qt
        setup = self._folder / f"MapleLens-Setup-{release.version}.exe"
        part = setup.with_name(setup.name + ".part")  # renamed only once its digest matches
        try:
            if release.digest is None:
                raise ValueError(f"GitHub gave no digest for {setup.name}: it can't be checked")
            self._folder.mkdir(parents=True, exist_ok=True)
            self._download(release.url, part)
            if not update.digest_ok(part, release.digest):
                raise ValueError(f"{setup.name} doesn't match GitHub's digest {release.digest}")
            part.replace(setup)
            self._got = (setup, None)
        except Exception as e:
            with contextlib.suppress(OSError):
                part.unlink(missing_ok=True)
            self._got = (None, e)

    def _hand_over(self, setup: Path | None, error: Exception | None) -> None:
        if setup is not None:
            try:
                self._install(setup)  # quits MapleLens: Setup takes it from here
                return
            except Exception as e:  # Setup didn't start; this version keeps running
                error = e
                with contextlib.suppress(OSError):
                    setup.unlink(missing_ok=True)
        if error is not None:
            report_once(error, self._seen)
        self._box.set_notice(UPDATE_FAILED)


def update_check(  # noqa: PLR0913, PLR0917 - main's parts, plus the fetch tests swap
    box: Box,
    settings: dict,
    save: Callable[[], None],
    seen: set[str],
    now: float,
    fetch: Callable[[], dict] = fetch_latest,
) -> UpdateCheck | None:
    """An UpdateCheck for the installed Windows app with the toggle on, else None.

    Clears the setups earlier updates left in the data folder's `updates`.
    """
    if not update.should_check(getattr(sys, "frozen", False), sys.platform, settings):
        return None
    folder = data_dir() / "updates"
    clear_updates(folder)
    return UpdateCheck(box, settings, save, fetch, version("maplelens"), seen, now, folder=folder)


def _prepare_process() -> None:
    """Process-wide setup that must happen before Qt starts."""
    mark_running()
    if sys.platform == "darwin":  # Qt must never bring MapleLens to the front over the game
        os.environ.setdefault("QT_MAC_DISABLE_FOREGROUND_APPLICATION_TRANSFORM", "1")
        os.environ.setdefault("QT_MAC_SET_RAISE_PROCESS", "0")


def main() -> int:  # noqa: PLR0915 - the entry point wires every part together
    if "--self-check" in sys.argv[1:]:
        return self_check()
    _prepare_process()
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
    updates = update_check(box, settings, save, seen, time.time())

    def tick() -> None:
        nonlocal hwnd
        now = time.time()
        if updates:  # before the game lookup: updates show with no game open too
            updates.poll(now)
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
