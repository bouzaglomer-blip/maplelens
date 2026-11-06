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
