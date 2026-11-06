"""The EXP meter tool: a tab with live numbers and a History window."""

import sqlite3
import sys
import time

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from maplelens.overlay import (
    LABEL_COLOR,
    LABEL_PT,
    TAB_W,
    VALUE_COLOR,
    VALUE_PT,
    native_setup,
    text_label,
)
from maplelens.readers import Reading
from maplelens.tools.exp_meter.history import history, save_segment
from maplelens.tools.exp_meter.meter import ExpMeter
from maplelens.tools.exp_meter.text import box_lines, format_duration, format_last

_FLUSH_S = 60
_COLUMNS = ["Map", "Class", "Lvl", "Avg EXP/h", "Avg %/h", "Active time", "Last there"]


class _Item(QTableWidgetItem):
    """A cell that sorts by a value instead of by its text."""

    def __init__(self, text: str, key):
        super().__init__(text)
        self.key = key

    def __lt__(self, other):
        return self.key < other.key


class HistoryWindow(QTableWidget):
    def __init__(self, conn: sqlite3.Connection):
        super().__init__(0, len(_COLUMNS))
        self._conn = conn
        self.setWindowTitle("MapleLens — EXP history")
        self.setHorizontalHeaderLabels(_COLUMNS)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.verticalHeader().hide()
        self.setSortingEnabled(True)
        self.setAttribute(Qt.WA_QuitOnClose, False)  # closing it must not end the app
        if sys.platform == "darwin":  # native_setup makes it a panel that leaves the game active
            self.setWindowFlag(Qt.Tool)
            self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.resize(760, 360)

    def refresh(self) -> None:
        now = time.time()
        self.setSortingEnabled(False)  # otherwise rows reshuffle while being filled
        rows = history(self._conn)
        self.setRowCount(len(rows))
        for i, r in enumerate(rows):
            cells = [
                (r.map_name, r.map_name),
                (r.job, r.job),
                (str(r.level), r.level),
                (f"{r.exp_per_min * 60:,.0f}", r.exp_per_min),
                (f"{r.pct_per_min * 60:.2f}%", r.pct_per_min),
                (format_duration(r.active_s / 60), r.active_s),
                (format_last(r.last, now), r.last),
            ]
            for col, (text, key) in enumerate(cells):
                self.setItem(i, col, _Item(text, key))
        self.setSortingEnabled(True)
        self.sortItems(len(_COLUMNS) - 1, Qt.DescendingOrder)

    def showEvent(self, event):
        native_setup(self)
        super().showEvent(event)


class ExpMeterTool:
    def __init__(self, settings: dict, conn: sqlite3.Connection):
        self._conn = conn
        self._meter = ExpMeter(settings["idle_cutoff_s"], settings["jump_factor"])
        self._last_flush: float | None = None
        self._history = HistoryWindow(conn)
        self.title = "EXP"
        self.tab = QWidget()
        self.tab.setFixedWidth(TAB_W)  # same box width as the other tabs
        self._lines = QVBoxLayout(self.tab)
        self._lines.setContentsMargins(0, 4, 0, 0)
        self._lines.setSpacing(0)
        button = QPushButton("History")
        button.setFocusPolicy(Qt.NoFocus)
        button.clicked.connect(self._show_history)
        self._button_row = button
        self._shape: list[int] | None = None  # values per row of what's shown
        self._texts: list[QLabel] = []
        self._show(box_lines(None, True))

    def _show(self, lines: list[tuple[str, list[str]]]) -> None:
        texts = [t for label, values in lines for t in (label, *values)]
        shape = [len(values) for _, values in lines]
        if shape == self._shape:  # same rows: new text only, or the box blinks each tick
            for w, t in zip(self._texts, texts, strict=True):
                w.setText(t)
            return
        self._shape = shape
        while self._lines.count():  # rebuild: the label/value rows are few and cheap
            item = self._lines.takeAt(0)
            if (w := item.widget()) and w is not self._button_row:
                w.deleteLater()
        self._texts = []
        for label, values in lines:
            row = [text_label(label, LABEL_PT, LABEL_COLOR)]
            row += [text_label(v, VALUE_PT, VALUE_COLOR, bold=True) for v in values]
            for w in row:
                self._lines.addWidget(w)
            self._texts += row
            self._lines.addSpacing(6)
        self._lines.addWidget(self._button_row)

    def _show_history(self) -> None:
        self._history.refresh()
        self._history.show()
        self._history.raise_()

    def _save(self, now: float, *, flush_open: bool) -> None:
        for seg in self._meter.pop_closed():
            save_segment(self._conn, seg)
        if flush_open and (seg := self._meter.open_segment()):
            save_segment(self._conn, seg)
            self._last_flush = now

    def update(self, r: Reading | None, _game_rect: tuple | None, now: float) -> None:
        self._meter.feed(r)
        if self._last_flush is None:
            self._last_flush = now
        self._save(now, flush_open=now - self._last_flush >= _FLUSH_S)
        self._show(box_lines(self._meter.rate(now), r is None))

    def shutdown(self, now: float) -> None:
        self._meter.close(now)
        self._save(now, flush_open=False)
