import re
import sys

import pytest

from maplelens import app
from maplelens.readers import glyphs, ocr


@pytest.fixture
def no_cache():
    glyphs.clear_cache()
    yield
    glyphs.clear_cache()


def test_self_check_passes_from_source(no_cache):
    if ocr.engine() is None:
        pytest.skip("no system OCR engine here")
    assert app.self_check() == 0


def test_self_check_fails_without_templates(tmp_path, monkeypatch, no_cache):
    monkeypatch.setattr(glyphs, "TEMPLATES", tmp_path)
    assert app.self_check() == 1


def test_self_check_fails_without_ocr(monkeypatch, no_cache):
    monkeypatch.setattr(ocr, "engine", lambda: None)
    assert app.self_check() == 1


def test_main_runs_self_check_before_any_window(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["maplelens", "--self-check"])
    monkeypatch.setattr(app, "self_check", lambda: 7)
    monkeypatch.setattr(app, "QApplication", None)  # building one would fail the test
    assert app.main() == 7


def test_self_check_fails_without_a_version(monkeypatch, no_cache):
    # a dist-info folder without METADATA gives None, not an error
    monkeypatch.setattr(app, "version", lambda name: None)
    assert app.self_check() == 1


GAME = (2, "MapleStory")
GUIDE = (1, "MapleStory Classic Thief Guide - Chrome")


@pytest.fixture
def windows(monkeypatch):
    """Fake open windows: set .list to the (handle, title) pairs on screen."""
    from maplelens.capture import pick_window

    class Windows:
        list: list = []  # noqa: RUF012

    monkeypatch.setattr(
        app.capture,
        "find_window",
        lambda title, exact=False: pick_window(Windows.list, title, exact),
    )
    return Windows


def test_unset_title_finds_the_game_and_saves_it(windows):
    windows.list = [GUIDE, GAME]
    settings, saves = {"window_title": None}, []
    assert app.find_game(settings, lambda: saves.append(1)) == 2
    assert settings["window_title"] == "MapleStory"
    assert saves == [1]


def test_unset_title_ignores_near_matches(windows):
    windows.list = [GUIDE]
    settings, saves = {"window_title": None}, []
    assert app.find_game(settings, lambda: saves.append(1)) is None
    assert settings["window_title"] is None
    assert saves == []


def test_saved_title_still_matches_by_substring(windows):
    windows.list = [GUIDE, GAME]
    settings, saves = {"window_title": "Thief Guide"}, []
    assert app.find_game(settings, lambda: saves.append(1)) == 1
    assert saves == []


def test_choosing_a_window_saves_its_title():
    settings, saves = {"window_title": None}, []
    app.choose_window(settings, lambda: saves.append(1), "Some Client")
    assert settings["window_title"] == "Some Client"
    assert saves == [1]


class _Raises:
    def update(self, *_):
        raise ValueError("bad frame")


class _Quiet:
    running = False

    def update(self, *_):
        pass


class _Box:
    def set_tab_dot(self, *_):
        pass


@pytest.fixture
def log(tmp_path, monkeypatch):
    path = tmp_path / "maplelens.log"
    path.write_text("from last run\n")
    app.start_log(path)
    yield path
    monkeypatch.setattr(app, "_log_path", None)


def test_start_log_empties_the_file(log):
    assert log.read_text() == ""


def test_a_tool_error_is_logged_once(log, monkeypatch):
    monkeypatch.setattr(sys, "stderr", None)  # a windowed exe has no console
    seen: set[str] = set()
    for _ in range(3):
        app.update_tools(_Box(), _Raises(), _Quiet(), None, None, 0.0, seen)
    text = log.read_text(encoding="utf-8")
    assert text.count("ValueError: bad frame") == 1
    assert "Traceback" in text


def test_picker_leaves_out_our_own_windows(monkeypatch):
    monkeypatch.setattr(app.capture, "window_titles", lambda: ["MapleLens", "MapleStory"])
    assert app.game_choices() == ["MapleStory"]


@pytest.mark.skipif(sys.platform != "win32", reason="named mutexes are a Windows thing")
def test_mark_running_holds_the_mutex_the_installer_checks(monkeypatch):
    import ctypes

    monkeypatch.setattr(app, "APP_MUTEX", "MapleLensTestMutex")
    kernel32 = ctypes.windll.kernel32
    kernel32.OpenMutexW.restype = ctypes.c_void_p
    synchronize = 0x00100000
    assert not kernel32.OpenMutexW(synchronize, False, "MapleLensTestMutex")
    assert app.mark_running()
    handle = kernel32.OpenMutexW(synchronize, False, "MapleLensTestMutex")
    assert handle
    kernel32.CloseHandle(ctypes.c_void_p(handle))


def test_installer_checks_the_apps_mutex():
    iss = (app.Path(__file__).parent.parent / "packaging" / "windows" / "maplelens.iss").read_text(
        encoding="utf-8"
    )
    assert f'#define AppMutexName "{app.APP_MUTEX}"' in iss
    # AppMutex only tells the player to close MapleLens; the [Code] section closes it
    assert "\nAppMutex=" not in iss


ISS = app.Path(__file__).parent.parent / "packaging" / "windows" / "maplelens.iss"


def test_update_cmd_runs_setup_silently_in_update_mode():
    setup = app.Path("C:/Users/דניאל/AppData/Roaming/MapleLens/updates/MapleLens-Setup-0.2.0.exe")
    assert app.update_cmd(setup) == [
        str(setup),
        "/SILENT",
        "/SP-",
        "/SUPPRESSMSGBOXES",
        "/NOCANCEL",
        app.UPDATE_FLAG,
    ]


@pytest.fixture
def handoff(monkeypatch):
    """Fake process start and Qt quit; .calls records them in order."""

    class Handoff:
        calls: list = []  # noqa: RUF012
        fail: Exception | None = None

    Handoff.calls = []

    def popen(cmd, **kw):
        if Handoff.fail:
            raise Handoff.fail
        Handoff.calls.append(("start", cmd, kw))

    class FakeQApplication:
        @staticmethod
        def quit():
            Handoff.calls.append(("quit",))

    def no_exit(*a):
        raise AssertionError("install_update must quit through QApplication.quit")

    monkeypatch.setattr(app.subprocess, "Popen", popen)
    monkeypatch.setattr(app, "QApplication", FakeQApplication)
    monkeypatch.setattr(app.sys, "exit", no_exit)
    return Handoff


def test_install_update_starts_setup_then_quits_through_qt(handoff, tmp_path):
    setup = tmp_path / "MapleLens-Setup-0.2.0.exe"
    app.install_update(setup)
    (start, cmd, kw), quit_ = handoff.calls
    assert start == "start"
    assert cmd == app.update_cmd(setup)
    assert kw["cwd"] == setup.parent  # never inside the folder Setup replaces
    assert quit_ == ("quit",)


def test_install_update_keeps_running_when_setup_wont_start(handoff, tmp_path):
    handoff.fail = OSError("blocked")
    with pytest.raises(OSError):
        app.install_update(tmp_path / "MapleLens-Setup-0.2.0.exe")
    assert handoff.calls == []  # no quit: the old version keeps running


def test_installer_knows_the_update_flag():
    iss = ISS.read_text(encoding="utf-8")
    assert f"'{app.UPDATE_FLAG}'" in iss
    # an update run relaunches MapleLens; skipifsilent keeps the hand-run entry from doing so
    assert re.search(r'^Filename: "\{app\}\\MapleLens\.exe";.*Check: IsUpdateRun', iss, re.M)


# --- the update check ---------------------------------------------------------------


def _latest(v):
    """A releases/latest reply for version `v`."""
    return {
        "tag_name": f"v{v}",
        "assets": [
            {
                "name": f"MapleLens-Setup-{v}.exe",
                "browser_download_url": f"https://example.invalid/MapleLens-Setup-{v}.exe",
                "digest": "sha256:" + "0" * 64,
            }
        ],
    }


NEWER = _latest("0.2.0")  # the running version is 0.1.0 throughout


@pytest.fixture
def qt_box(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from maplelens.overlay import Box

    QApplication.instance() or QApplication([])
    box = Box("t", {}, lambda: None)
    box.add_menu_item("Quit MapleLens", lambda: None)
    return box


class _Fetch:
    """A fake fetch: returns .reply (or raises .error); counts its calls."""

    def __init__(self, reply=None, error=None):
        self.reply, self.error, self.calls = reply, error, 0

    def __call__(self):
        self.calls += 1
        if self.error:
            raise self.error
        return self.reply


def _check(box, fetch, settings=None, save=lambda: None):
    settings = {"update_dismissed": None} if settings is None else settings
    return app.UpdateCheck(box, settings, save, fetch, "0.1.0", set(), now=0.0)


def _run(check, now):
    """A tick at `now`, a wait for any check it started, then the tick that collects it."""
    check.poll(now)
    if check._thread is not None:
        check._thread.join(5)
    check.poll(now)


def _menu(box):
    return [a.text() for a in box.actions()]


def test_first_check_waits_a_few_seconds(qt_box):
    fetch = _Fetch(NEWER)
    check = _check(qt_box, fetch)
    _run(check, app.UpdateCheck.FIRST_S - 1)
    assert fetch.calls == 0
    _run(check, app.UpdateCheck.FIRST_S)
    assert fetch.calls == 1


def test_a_newer_release_shows_the_line_and_the_menu_item(qt_box):
    check = _check(qt_box, _Fetch(NEWER))
    _run(check, 10.0)
    assert qt_box._notice.isVisibleTo(qt_box)
    assert qt_box._notice_text.text() == app.update_notice("0.2.0")
    assert _menu(qt_box) == ["Update to 0.2.0…", "Quit MapleLens"]


def test_the_same_version_shows_nothing(qt_box):
    check = _check(qt_box, _Fetch(_latest("0.1.0")))
    _run(check, 10.0)
    assert not qt_box._notice.isVisibleTo(qt_box)
    assert _menu(qt_box) == ["Quit MapleLens"]


def test_dismissing_saves_the_version(qt_box):
    settings, saves = {"update_dismissed": None}, []
    check = _check(qt_box, _Fetch(NEWER), settings, lambda: saves.append(1))
    _run(check, 10.0)
    qt_box._notice_close.click()
    assert settings["update_dismissed"] == "0.2.0"
    assert saves == [1]


def test_a_dismissed_version_keeps_the_menu_item_but_no_line(qt_box):
    check = _check(qt_box, _Fetch(NEWER), {"update_dismissed": "0.2.0"})
    _run(check, 10.0)
    assert not qt_box._notice.isVisibleTo(qt_box)
    assert _menu(qt_box) == ["Update to 0.2.0…", "Quit MapleLens"]


def test_a_later_version_brings_the_line_back_and_relabels_the_item(qt_box):
    fetch = _Fetch(NEWER)
    check = _check(qt_box, fetch, {"update_dismissed": "0.2.0"})
    _run(check, 10.0)
    fetch.reply = _latest("0.3.0")
    _run(check, 10.0 + app.UpdateCheck.EVERY_S)
    assert fetch.calls == 2
    assert qt_box._notice.isVisibleTo(qt_box)
    assert qt_box._notice_text.text() == app.update_notice("0.3.0")
    assert _menu(qt_box) == ["Update to 0.3.0…", "Quit MapleLens"]


def test_checks_again_only_after_a_day(qt_box):
    fetch = _Fetch(NEWER)
    check = _check(qt_box, fetch)
    _run(check, 10.0)
    _run(check, 10.0 + app.UpdateCheck.EVERY_S - 1)
    assert fetch.calls == 1
    _run(check, 10.0 + app.UpdateCheck.EVERY_S)
    assert fetch.calls == 2


def test_a_failing_check_is_logged_once_and_shows_nothing(qt_box, log, monkeypatch):
    monkeypatch.setattr(sys, "stderr", None)
    fetch = _Fetch(error=OSError("offline"))
    check = _check(qt_box, fetch)
    _run(check, 10.0)
    _run(check, 10.0 + app.UpdateCheck.EVERY_S)
    assert fetch.calls == 2  # the next scheduled check tries again
    assert not qt_box._notice.isVisibleTo(qt_box)
    assert _menu(qt_box) == ["Quit MapleLens"]
    text = log.read_text(encoding="utf-8")
    assert text.count("OSError: offline") == 1
    assert "Traceback" in text


def test_a_hanging_check_never_blocks_a_tick(qt_box, log, monkeypatch):
    import threading

    monkeypatch.setattr(sys, "stderr", None)
    let_go, calls = threading.Event(), []

    def hangs():
        calls.append(1)
        let_go.wait(5)
        raise TimeoutError("timed out")

    check = _check(qt_box, hangs)
    for day in range(5):  # ticks go on while the request hangs, and start no second one
        check.poll(10.0 + day * app.UpdateCheck.EVERY_S)
    assert calls == [1]
    assert not qt_box._notice.isVisibleTo(qt_box)
    let_go.set()
    check._thread.join(5)
    check.poll(10.0 + 4 * app.UpdateCheck.EVERY_S)
    assert log.read_text(encoding="utf-8").count("TimeoutError: timed out") == 1
    assert not qt_box._notice.isVisibleTo(qt_box)


def test_from_source_there_is_no_update_check(qt_box, monkeypatch):
    monkeypatch.delattr(sys, "frozen", raising=False)
    fetch = _Fetch(NEWER)
    assert app.update_check(qt_box, {"update_check": True}, lambda: None, set(), 0.0, fetch) is None
    assert fetch.calls == 0


def test_toggle_off_there_is_no_update_check(qt_box, monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "platform", "win32")
    fetch = _Fetch(NEWER)
    settings = {"update_check": False}
    assert app.update_check(qt_box, settings, lambda: None, set(), 0.0, fetch) is None
    assert fetch.calls == 0


def test_the_installed_windows_app_gets_an_update_check(qt_box, monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "platform", "win32")
    settings = {"update_check": True, "update_dismissed": None}
    check = app.update_check(qt_box, settings, lambda: None, set(), 0.0, _Fetch(NEWER))
    assert isinstance(check, app.UpdateCheck)


def test_settings_default_to_checking():
    from maplelens.store import DEFAULTS

    assert DEFAULTS["update_check"] is True
    assert DEFAULTS["update_dismissed"] is None


def test_fetch_asks_github_with_only_the_version(monkeypatch):
    import io
    import json

    seen = {}

    def urlopen(req, timeout):
        seen["url"], seen["headers"], seen["timeout"] = req.full_url, dict(req.headers), timeout
        return io.BytesIO(json.dumps(NEWER).encode())

    monkeypatch.setattr(app.urllib.request, "urlopen", urlopen)
    assert app.fetch_latest("someone/maplelens") == NEWER
    assert seen["url"] == "https://api.github.com/repos/someone/maplelens/releases/latest"
    assert seen["headers"]["User-agent"] == f"MapleLens/{app.version('maplelens')}"
    assert seen["timeout"] <= 15
