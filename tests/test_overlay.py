import sys

import pytest

from maplelens import overlay
from maplelens.overlay import game_to_layer


def test_game_to_layer_125pct():
    assert game_to_layer(1250, 500, 1.25) == (1000.0, 400.0)


def _box(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from maplelens.overlay import Box

    QApplication.instance() or QApplication([])
    return Box("t", {}, lambda: None)


def test_box_tabs_switch(monkeypatch):
    from PySide6.QtWidgets import QLabel

    box = _box(monkeypatch)
    a, b = QLabel("a"), QLabel("b")
    assert box.add_tab("A", a) == 0
    assert box.add_tab("B", b) == 1
    assert a.isVisibleTo(box) and not b.isVisibleTo(box)
    box._tab_buttons[1].click()
    assert b.isVisibleTo(box) and not a.isVisibleTo(box)


def test_tab_dot(monkeypatch):
    from PySide6.QtWidgets import QLabel

    box = _box(monkeypatch)
    box.add_tab("A", QLabel())
    box.add_tab("B", QLabel())
    assert not box._tab_dots[1].isVisibleTo(box)
    box.set_tab_dot(1, True)
    assert box._tab_dots[1].isVisibleTo(box)
    box.set_tab_dot(1, False)
    assert not box._tab_dots[1].isVisibleTo(box)


def test_allow_typing_toggles_focus_flag(monkeypatch):
    from PySide6.QtCore import Qt

    box = _box(monkeypatch)
    box.show()
    assert box.windowFlags() & Qt.WindowDoesNotAcceptFocus
    box.allow_typing(True)
    assert not box.windowFlags() & Qt.WindowDoesNotAcceptFocus
    assert box.isVisible()
    box.allow_typing(False)
    assert box.windowFlags() & Qt.WindowDoesNotAcceptFocus
    assert box.isVisible()


def test_native_setup_offscreen_is_noop(monkeypatch):
    calls = []
    if sys.platform == "darwin":  # overlay_mac needs AppKit, which only the Mac has
        from maplelens import overlay_mac

        monkeypatch.setattr(overlay_mac, "make_panel", calls.append)
    box = _box(monkeypatch)
    box.show()
    assert calls == []


def test_font_per_platform():
    assert overlay.FONT == ("Helvetica Neue" if sys.platform == "darwin" else "Segoe UI")


@pytest.mark.skipif(sys.platform != "darwin", reason="overlay_mac needs AppKit")
def test_allow_typing_off_releases_keyboard_on_mac(monkeypatch):
    from maplelens import overlay_mac

    calls = []
    monkeypatch.setattr(overlay_mac, "release_keyboard", lambda: calls.append(1))
    box = _box(monkeypatch)
    box.show()
    box.allow_typing(True)
    assert calls == []
    box.allow_typing(False)
    assert calls == [1]


@pytest.mark.skipif(sys.platform != "darwin", reason="overlay_mac needs AppKit")
@pytest.mark.parametrize("active", [True, False])
def test_release_keyboard_deactivates_only_when_active(monkeypatch, active):
    from maplelens import overlay_mac

    calls = []

    class FakeApp:
        def isActive(self):
            return active

        def deactivate(self):
            calls.append(1)

    class FakeNSApplication:
        sharedApplication = staticmethod(FakeApp)

    monkeypatch.setattr(overlay_mac, "NSApplication", FakeNSApplication)
    overlay_mac.release_keyboard()
    assert calls == ([1] if active else [])
