"""MapleLens's own windows: a click-through layer over the game and small draggable boxes."""

import ctypes
from collections.abc import Callable
from ctypes import wintypes

from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

_WDA_EXCLUDEFROMCAPTURE = 0x11
_INSET = 40  # px from the game's top-right corner for a box with no saved position


def game_to_layer(px: float, py: float, dpr: float) -> tuple[float, float]:
    """Game-client physical pixels to layer-local Qt logical coordinates."""
    return px / dpr, py / dpr


def exclude_from_capture(widget: QWidget) -> None:
    """Keep one of MapleLens's own windows out of screen grabs, so readers never see it."""
    set_affinity = ctypes.windll.user32.SetWindowDisplayAffinity
    set_affinity.argtypes = [wintypes.HWND, wintypes.DWORD]
    set_affinity(int(widget.winId()), _WDA_EXCLUDEFROMCAPTURE)  # returns 0 on old Windows: ignore


_OVERLAY = Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.WindowDoesNotAcceptFocus


class Layer(QWidget):
    """Empty see-through window over the game's client area; tools draw on it later."""

    def __init__(self):
        super().__init__(None, _OVERLAY | Qt.WindowTransparentForInput)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)

    def follow(self, rect: tuple[int, int, int, int]) -> None:
        left, top, w, h = rect  # physical pixels
        dpr = self.devicePixelRatioF()
        x, y = game_to_layer(left, top, dpr)
        pw, ph = game_to_layer(w, h, dpr)
        self.setGeometry(round(x), round(y), round(pw), round(ph))

    def showEvent(self, event):
        exclude_from_capture(self)
        super().showEvent(event)


class Box(QWidget):
    """A small dark text box with optional buttons; drag it, its spot is saved per game window."""

    def __init__(self, name: str, settings: dict, on_moved: Callable[[], None]):
        super().__init__(None, _OVERLAY)
        self._name, self._settings, self._on_moved = name, settings, on_moved
        self._origin: QPoint | None = None  # game client top-left, logical px
        self._game_w = 0
        self._drag_from: QPoint | None = None
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        font = QFont("Consolas", 10)
        font.setStyleHint(QFont.Monospace)
        self._label = QLabel()
        self._label.setFont(font)
        self._label.setStyleSheet("color: #e8e8e8;")
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(12, 8, 12, 8)
        self._layout.addWidget(self._label)

    def set_text(self, text: str) -> None:
        self._label.setText(text)
        self.adjustSize()

    def add_button(self, label: str, callback: Callable[[], None]) -> None:
        button = QPushButton(label)
        button.setFocusPolicy(Qt.NoFocus)
        button.clicked.connect(callback)
        self._layout.addWidget(button)
        self.adjustSize()

    def place(self, game_rect: tuple[int, int, int, int]) -> None:
        if self._drag_from is not None:
            return  # don't fight the user's drag
        left, top, w, _ = game_rect  # physical pixels
        dpr = self.devicePixelRatioF()
        x, y = game_to_layer(left, top, dpr)
        self._origin = QPoint(round(x), round(y))
        self._game_w = round(w / dpr)
        saved = self._settings.get("boxes", {}).get(self._name)
        if saved:
            target = self._origin + QPoint(*saved)
        else:
            target = self._origin + QPoint(self._game_w - self.width() - _INSET, _INSET)
        if target != self.pos():
            self.move(target)

    def showEvent(self, event):
        exclude_from_capture(self)
        super().showEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(20, 20, 24, 200))
        p.drawRoundedRect(QRect(0, 0, self.width(), self.height()), 8, 8)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_from = event.globalPosition().toPoint() - self.pos()

    def mouseMoveEvent(self, event):
        if self._drag_from is not None:
            self.move(event.globalPosition().toPoint() - self._drag_from)

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.LeftButton or self._drag_from is None:
            return
        self._drag_from = None
        if self._origin is not None:
            off = self.pos() - self._origin
            self._settings.setdefault("boxes", {})[self._name] = [off.x(), off.y()]
            self._on_moved()
