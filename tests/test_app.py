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
