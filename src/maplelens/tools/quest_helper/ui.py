"""The quest helper's Quests tab: the quest open in the game, then the tracked ones."""

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QFontMetrics
from PySide6.QtWidgets import QFrame, QHBoxLayout, QScrollArea, QVBoxLayout, QWidget
from shiboken6 import delete

from maplelens.overlay import (
    ACCENT,
    EDGE,
    FONT,
    LABEL_COLOR,
    LABEL_PT,
    TAB_W,
    VALUE_COLOR,
    InfoLine,
    Row,
    mark_button,
    primary_button,
    secondary_button,
    text_label,
)
from maplelens.readers import Reading
from maplelens.readers.quest_window import NAME_UNREADABLE, QuestOpen
from maplelens.tools.quest_helper.data import Quest, QuestData, load
from maplelens.tools.quest_helper.plan import (
    Target,
    also_for,
    find_quest,
    shared_name,
    show_giver,
    targets,
)

EMPTY = "Open a quest in the game to see where to go"
UNKNOWN = "This quest isn't in MapleLens's list yet"
SHARED_NAME = "Several quests have this name; MapleLens can't tell which yet"
UNREAD = "Can't read the quest window: move it fully into view"
NAME_UNREAD = "Can't read the quest's name: scroll its text to the top"
OPEN = "Open in the game"
TRACK = "Track"
TRACKED = "Tracked ✓"
STOP = "Stop"
TRACKING = "Tracking · {n} quests"
TRACKING_ONE = "Tracking · 1 quest"
GOING = "Going · {n} maps away"
GOING_ONE = "Going · 1 map away"
GOING_HERE = "Going · on this map"
ALSO = "also for {quest}"
SHUT, SHOWN = "▸", "▾"
CLOSE = "\u00d7"  # the multiplication sign, the box's close mark

TOP = 4  # the tab's top margin, as the Class tab's
# The tallest Class tab state test_class_ui builds (box_with_tools, STATES): Rogue Lv 28,
# 302 px laid out at TAB_W in the box (its sizeHint says 319, before its wrapped lines
# get their width). Past it, the tab scrolls.
MAX_H = 302
BAR = 4  # the scroll bar's width; the tab's own lines leave room for it
_BAR_STYLE = f"""
QScrollBar:vertical {{ width: {BAR}px; background: transparent; margin: 0; }}
QScrollBar::handle:vertical {{ background: {EDGE}; border-radius: 2px; min-height: 20px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}"""


def _fit(widget, text: str, room: int) -> None:
    """Set `text` cut to `room` px; the full text is the tooltip."""
    widget.setText(QFontMetrics(widget.font()).elidedText(text, Qt.ElideRight, room))
    widget.setToolTip(text)


def _line(left: QWidget, right: QWidget) -> QWidget:
    line = QWidget()
    row = QHBoxLayout(line)
    row.setContentsMargins(0, 2, 0, 0)
    row.setSpacing(6)
    row.addWidget(left)
    row.addStretch()
    row.addWidget(right, 0, Qt.AlignVCenter)
    return line


class QuestHelperTool:
    def __init__(  # noqa: PLR0913, PLR0917 - the tool's collaborators, as the other tools take
        self,
        settings: dict,
        on_settings_changed: Callable[[], None],
        go: Callable[[str, tuple[int, int] | None, str | None], None],
        heading: Callable[[], tuple[str, tuple[int, int] | None, int] | None],
        stop: Callable[[], None],
        hops: Callable[[str], int | None],
        data: QuestData | None = None,
    ):
        self.title = "Quests"
        self.open = False  # the quest window is in this reading
        self._settings, self._changed = settings, on_settings_changed
        self._go, self._heading, self._stop, self._hops = go, heading, stop, hops
        self._data = load() if data is None else data
        self._clean()
        self._quest: QuestOpen | str | None = None  # the quest window, as shown
        self._misses = 0  # readings in a row without it
        self._shown: list | None = None  # the items now drawn
        self.tab = QWidget()
        self.tab.setFixedWidth(TAB_W)
        self._scroll = QScrollArea()
        self._scroll.setFrameShape(QFrame.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.setWidgetResizable(True)
        self._scroll.setFixedWidth(TAB_W)
        self._scroll.viewport().setAutoFillBackground(False)  # the box shows through
        self._scroll.verticalScrollBar().setStyleSheet(_BAR_STYLE)
        for w in (self._scroll, self._scroll.verticalScrollBar()):
            w.setFocusPolicy(Qt.NoFocus)
        self._holder = QWidget()  # the scrolled widget; each redraw swaps the body in it
        QVBoxLayout(self._holder).setContentsMargins(0, 0, 0, 0)
        self._scroll.setWidget(self._holder)
        self._holder.setAutoFillBackground(False)  # setWidget turned it on
        self._body: QWidget | None = None
        self._old: QWidget | None = None
        col = QVBoxLayout(self.tab)
        col.setContentsMargins(0, TOP, 0, 0)
        col.addWidget(self._scroll)
        self._render()

    def _clean(self) -> None:
        """Keep the quest ids the data still has; a hand-edited bad value is replaced."""
        s, quests = self._settings, self._data.quests
        ids = s.get("quests_tracked")
        ids = ids if isinstance(ids, list) else []
        s["quests_tracked"] = list(dict.fromkeys(i for i in ids if type(i) is int and i in quests))
        if s.get("quests_expanded") not in s["quests_tracked"]:
            s["quests_expanded"] = None

    def update(self, r: Reading | None, _game_rect, _now: float) -> None:
        quest = r.quest if r is not None else None
        self.open = quest is not None
        if quest is not None:
            self._quest, self._misses = quest, 0
        else:
            self._misses += 1
            if self._misses >= 2:  # one missed reading keeps it
                self._quest = None
        self._render()

    # --- actions ----------------------------------------------------------

    def _save(self) -> None:
        self._changed()
        self._render()

    def _track(self, qid: int) -> None:
        self._settings["quests_tracked"].append(qid)
        self._settings["quests_expanded"] = qid  # shown open once the window closes
        self._save()

    def _untrack(self, qid: int) -> None:
        self._settings["quests_tracked"].remove(qid)
        if self._settings["quests_expanded"] == qid:
            self._settings["quests_expanded"] = None
        self._save()

    def _expand(self, qid: int) -> None:
        shown = self._settings["quests_expanded"] == qid
        self._settings["quests_expanded"] = None if shown else qid
        self._save()

    def _go_to(self, map_id: str, at: tuple[int, int] | None, npc: str | None) -> None:
        self._go(map_id, at, npc)
        self._render()  # outline the row now, not on the next tick

    def _stop_trip(self) -> None:
        self._stop()
        self._render()

    # --- view -------------------------------------------------------------

    def _items(self) -> list:
        """Items are tuples, drawn in order: ("info", text), ("label", text),
        ("open", id, name, tracked), ("head", id, name, expanded),
        ("row", title, sub, map id, at, npc, info), ("run", title, sub)."""
        d, q = self._data, self._quest
        tracked = self._settings["quests_tracked"]
        out, top = self._top(q, tracked) if q is not None else ([], None)
        listed = [i for i in tracked if top is None or i != top.id]
        plans = {i: targets(d, d.quests[i], giver=False, hops=self._hops) for i in listed}
        if top is not None:
            giver = show_giver(q.taken, top.id in tracked)
            plans[top.id] = targets(d, top, giver=giver, hops=self._hops)
        going = self._heading()

        def rows(qid: int) -> list:
            others = [(d.quests[j].name, plans[j]) for j in tracked if j != qid]  # tracked only
            return [self._row(t, others, going) for t in plans[qid]]

        if top is not None:
            out += rows(top.id)
        if listed:
            n = len(tracked)  # the open one too, though it shows only on top
            out.append(("label", TRACKING_ONE if n == 1 else TRACKING.format(n=n)))
        for i in listed:
            expanded = i == self._settings["quests_expanded"]
            out.append(("head", i, d.quests[i].name, expanded))
            if expanded:
                out += rows(i)
        return out or [("info", EMPTY)]

    def _top(self, q: QuestOpen | str, tracked: list[int]) -> tuple[list, Quest | None]:
        """The top part's first lines, and the quest it shows rows for, if any."""
        if q == NAME_UNREADABLE:
            return [("label", OPEN), ("info", NAME_UNREAD)], None
        if not isinstance(q, QuestOpen):  # UNREADABLE: one move fixes it, so yellow
            return [("label", OPEN), ("action", UNREAD)], None
        if shared_name(self._data, q.name):
            return [("label", OPEN), ("info", SHARED_NAME)], None
        top = find_quest(self._data, q.name)
        if top is None:
            return [("label", OPEN), ("info", UNKNOWN)], None
        return [("label", OPEN), ("open", top.id, top.name, top.id in tracked)], top

    @staticmethod
    def _row(t: Target, others: list, going) -> tuple:
        if going is not None and t.map_id is not None and (t.map_id, t.at) == going[:2]:
            n = going[2]
            return (
                "run",
                t.title,
                GOING_HERE if n == 0 else GOING_ONE if n == 1 else GOING.format(n=n),
            )
        sub = t.sub
        names = also_for(t.map_id, others) if t.map_id else []
        if names:
            sub = f"{sub} · {ALSO.format(quest=', '.join(names))}"
        return ("row", t.title, sub, t.map_id, t.at, t.npc, t.info)

    def _widget(self, item) -> QWidget:
        kind = item[0]
        if kind == "info":
            return InfoLine(item[1])
        if kind == "action":
            line = text_label(item[1], LABEL_PT, ACCENT)
            line.setWordWrap(True)
            return line
        if kind == "label":
            return text_label(item[1], LABEL_PT, LABEL_COLOR)
        if kind == "row":
            _, title, sub, map_id, at, npc, info = item
            go = (lambda: self._go_to(map_id, at, npc)) if map_id else None
            row = Row(title, sub, go, info=info)
            row.setToolTip(sub)  # the sub-line is cut to fit
            return row
        if kind == "run":
            _, title, sub = item
            return Row(
                title, sub, None, outline=True, trailing=secondary_button(STOP, self._stop_trip)
            )
        if kind == "open":
            _, qid, name, tracked = item
            if tracked:
                end = text_label(TRACKED, LABEL_PT, LABEL_COLOR)
            else:
                end = primary_button(TRACK, lambda: self._track(qid))
            label = text_label("", LABEL_PT, VALUE_COLOR, bold=True)
            _fit(label, name, TAB_W - BAR - end.sizeHint().width() - 6)
            return _line(label, end)
        _, qid, name, expanded = item  # a tracked quest's header
        close = mark_button(CLOSE, LABEL_PT, lambda: self._untrack(qid))
        head = mark_button("", LABEL_PT, lambda: self._expand(qid), color=VALUE_COLOR)
        head.setFont(QFont(FONT, LABEL_PT, QFont.Bold))
        mark = f"{SHOWN if expanded else SHUT} "
        room = (
            TAB_W - BAR - close.sizeHint().width() - 6 - head.fontMetrics().horizontalAdvance(mark)
        )
        _fit(head, name, room)
        head.setText(mark + head.text())
        return _line(head, close)

    def _render(self) -> None:
        """Redraw only when the items changed."""
        items = self._items()
        if self._shown == items:
            return
        self._shown = items
        body = QWidget()
        col = QVBoxLayout(body)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(3)
        for item in items:
            col.addWidget(self._widget(item))
        # The body drawn before stays, hidden, until the next redraw: a click handler may
        # still be running in it. The one before that goes now.
        if self._old is not None:
            delete(self._old)
        self._old = self._body
        if self._body is not None:
            self._body.hide()
            self._holder.layout().removeWidget(self._body)
        self._body = body
        self._holder.layout().addWidget(body)
        h = body.heightForWidth(TAB_W) if body.hasHeightForWidth() else body.sizeHint().height()
        self._scroll.setFixedHeight(min(h, MAX_H - TOP))
