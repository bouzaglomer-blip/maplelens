"""MapleLens's own windows: a click-through layer over the game and small draggable boxes."""

import sys
from collections.abc import Callable

from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QAction, QColor, QFont, QGuiApplication, QPainter
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLayout,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

_INSET = 40  # px from the game's top-right corner for a box with no saved position

# The box's look (mockup 1), shared by every tab: grey labels, larger bold values.
FONT = "Helvetica Neue" if sys.platform == "darwin" else "Segoe UI"
LABEL_PT, LABEL_COLOR = 9, "#9fb0c8"
VALUE_PT, VALUE_COLOR = 12, "#ffffff"
ACCENT = "#ffcc33"
TAB_W = 186  # every tab's width: the box is 210 px wide, less its 12 px side margins


def text_label(text: str, pt: int, color: str, *, bold: bool = False) -> QLabel:
    label = QLabel(text)
    label.setFont(QFont(FONT, pt, QFont.Bold if bold else QFont.Normal))
    label.setStyleSheet(f"color: {color};")
    return label


def game_to_layer(px: float, py: float, dpr: float) -> tuple[float, float]:
    """Game-client physical pixels to layer-local Qt logical coordinates."""
    return px / dpr, py / dpr


def native_setup(widget: QWidget) -> None:
    """Platform setup for one of MapleLens's own windows, run each time it's shown.

    Mac: a panel that stays visible over the game and leaves it the keyboard. Nothing on
    Windows: capture grabs the game window alone, so the readers never see these windows,
    and streams and screenshots do.
    """
    if sys.platform == "darwin" and QGuiApplication.platformName() == "cocoa":
        from maplelens import overlay_mac  # AppKit only exists on the Mac

        overlay_mac.make_panel(widget)


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
        native_setup(self)
        super().showEvent(event)


class Box(QWidget):
    """A small dark box with a tab strip; drag it, its spot is saved per game window."""

    def __init__(self, name: str, settings: dict, on_moved: Callable[[], None]):
        super().__init__(None, _OVERLAY)
        self._name, self._settings, self._on_moved = name, settings, on_moved
        self._origin: QPoint | None = None  # game client top-left, logical px
        self._game_w = 0
        self._drag_from: QPoint | None = None
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self._tab_buttons: list[QPushButton] = []
        self._tab_dots: list[QLabel] = []
        self._strip_row = QWidget()  # holds the strip, so it hides as one
        self._strip = QHBoxLayout(self._strip_row)
        self._strip.setContentsMargins(0, 0, 0, 0)
        self._strip.setSpacing(14)
        self._strip.addStretch()
        self._pages = QStackedWidget()
        self._status = QLabel()
        self._status.setFont(QFont(FONT, 10))
        self._status.setStyleSheet(f"color: {VALUE_COLOR};")
        self._status.hide()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 10)
        layout.setSizeConstraint(QLayout.SetFixedSize)  # the box hugs the current tab
        layout.addWidget(self._strip_row)
        layout.addWidget(self._pages)
        layout.addWidget(self._status)

    def add_tab(self, title: str, widget: QWidget) -> int:
        """Add a tab; the first one added is shown. Returns its index."""
        i = self._pages.addWidget(widget)
        button = QPushButton(title)
        button.setFlat(True)
        button.setFocusPolicy(Qt.NoFocus)
        button.setCursor(Qt.PointingHandCursor)
        button.setFont(QFont(FONT, 10, QFont.Bold))
        button.clicked.connect(lambda: self._select(i))
        dot = QLabel()
        dot.setFixedSize(6, 6)
        dot.setStyleSheet(f"background: {ACCENT}; border-radius: 3px;")
        dot.hide()
        self._tab_buttons.append(button)
        self._tab_dots.append(dot)
        at = self._strip.count() - 1  # before the trailing stretch
        self._strip.insertWidget(at, button)
        self._strip.insertWidget(at + 1, dot, 0, Qt.AlignVCenter)
        self._select(self._pages.currentIndex())
        return i

    def _select(self, index: int) -> None:
        self._pages.setCurrentIndex(index)
        for j, b in enumerate(self._tab_buttons):
            color, line = (VALUE_COLOR, ACCENT) if j == index else (LABEL_COLOR, "transparent")
            b.setStyleSheet(
                f"QPushButton {{ color: {color}; border: 0; border-bottom: 2px solid {line};"
                " padding: 2px 0; }"
            )
        for j in range(self._pages.count()):  # only the current page sizes the box
            policy = QSizePolicy.Preferred if j == index else QSizePolicy.Ignored
            self._pages.widget(j).setSizePolicy(policy, policy)

    def set_status(self, text: str | None) -> None:
        """Show one line of `text` in place of the tabs; None brings the tabs back."""
        self._status.setText(text or "")
        self._status.setVisible(text is not None)
        self._strip_row.setVisible(text is None)
        self._pages.setVisible(text is None)

    def set_tab_dot(self, index: int, on: bool) -> None:
        self._tab_dots[index].setVisible(on)

    def allow_typing(self, on: bool) -> None:
        """Let the box take keyboard focus (only while a text field needs it)."""
        self.setWindowFlag(Qt.WindowDoesNotAcceptFocus, not on)
        self.show()  # changing a window flag hides a shown window
        if not on and sys.platform == "darwin":
            from maplelens import overlay_mac

            overlay_mac.release_keyboard()

    def add_menu_item(self, label: str, callback: Callable[[], None]) -> None:
        """An item in the box's right-click menu."""
        action = QAction(label, self)
        action.triggered.connect(callback)
        self.addAction(action)
        self.setContextMenuPolicy(Qt.ActionsContextMenu)

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
        native_setup(self)
        super().showEvent(event)

    def paintEvent(self, _event):
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
