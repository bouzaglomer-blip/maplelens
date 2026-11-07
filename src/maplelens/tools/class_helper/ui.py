"""The class helper's Class tab: training maps, gear, the job advance and the next step."""

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QPushButton, QVBoxLayout, QWidget
from shiboken6 import delete

from maplelens.overlay import ACCENT, LABEL_COLOR, LABEL_PT, TAB_W, VALUE_COLOR, Layer, text_label
from maplelens.readers import Reading
from maplelens.readers.skill_window import SkillWindow
from maplelens.readers.stat_window import StatWindow
from maplelens.readers.window import UNREADABLE
from maplelens.tools.class_helper.data import ClassData, Place, load
from maplelens.tools.class_helper.plan import (
    advance_due,
    advance_text,
    gear,
    next_step,
    short,
    training,
)

NO_CLASS = "Can't read your class yet"
NO_PLAN = "No plan for {} yet"
OPEN_STATS = "Open your stat window once"
STAT_UNREAD = "Can't read your stat window: move it fully into view"
SKILL_UNREAD = "Can't read your skill window: move it fully into view"

DASH = "\u2013"
_FIELD, _DARK = "#0b0f15", "#2a1d00"
_STYLE = f"""
QComboBox {{ background: {_FIELD}; color: {VALUE_COLOR}; border: 1px solid {ACCENT};
    border-radius: 4px; padding: 1px 6px; }}
QPushButton#go {{ background: {ACCENT}; color: {_DARK}; font-weight: bold; border: 0;
    border-radius: 4px; padding: 2px 8px; }}
"""


def _go_map(place: Place | None) -> str | None:
    return place.map_id if place else None


class ClassHelperTool:
    def __init__(  # noqa: PLR0913, PLR0917 - the tool's collaborators, as the other tools take
        self,
        settings: dict,
        on_settings_changed: Callable[[], None],
        layer: Layer,
        go: Callable[[str], None],
        best_rate: Callable[[str], float | None],
        data: ClassData | None = None,
    ):
        self.title = "Class"
        self.dot = False
        self._settings, self._changed = settings, on_settings_changed
        self._layer, self._go, self._best_rate = layer, go, best_rate
        self._data = load() if data is None else data
        self._job: str | None = None
        self._level: int | None = None
        self._stats: tuple[StatWindow, int] | None = None  # the window, the level it was read at
        self.skills: dict[str, dict[int, int]] = {}  # tab -> {skill id: level}
        self.sp: dict[str, tuple[int, int]] = {}  # tab -> (unspent SP, level it was read at)
        self._shown: tuple | None = None  # the items now drawn
        self._content: tuple | None = None  # the level-up dot's key
        self._plan_job: str | None = None
        self._r: Reading | None = None
        self._seen_at = 0  # the level at the last update
        self.tab = self._build_tab()
        self._render([(("label", NO_CLASS, ACCENT), None)])

    def _build_tab(self) -> QWidget:
        tab = QWidget()
        tab.setStyleSheet(_STYLE)
        tab.setFixedWidth(TAB_W)
        self._builds = QComboBox()
        self._builds.setFocusPolicy(Qt.NoFocus)
        self._builds.hide()
        self._builds.currentTextChanged.connect(self._on_build)
        self._body = QWidget()
        col = QVBoxLayout(tab)
        col.setContentsMargins(0, 4, 0, 0)
        col.setSpacing(6)
        col.addWidget(self._builds)
        col.addWidget(self._body)
        return tab

    def hide_marks(self) -> None:
        pass  # the marks on the game windows come later

    def _on_build(self, name: str) -> None:
        if self._plan_job is None or not name:
            return
        self._choices()[self._plan_job] = name
        self._changed()
        self._render_last()

    # --- memory -----------------------------------------------------------

    def _remember(self, r: Reading | None) -> None:
        job = r.job if r else None
        level = r.level if r else None
        if (job and self._job and job != self._job) or (
            level is not None and self._level is not None and level < self._level
        ):
            self._stats, self._content = None, None
            self.skills, self.sp = {}, {}
        self._job = job or self._job
        self._level = level if level is not None else self._level
        if r is None:
            return
        st = r.stats
        if isinstance(st, StatWindow) and (r.level is None or st.level == r.level):
            self._stats = (st, st.level)
        sk = r.skills
        if isinstance(sk, SkillWindow) and self._level is not None:
            self.skills[sk.tab] = {row.skill: row.level for row in sk.rows}
            self.sp[sk.tab] = (sk.sp, self._level)

    def _stats_now(self) -> StatWindow | None:
        if self._stats and self._stats[1] == self._level:
            return self._stats[0]
        return None

    def _points(self) -> tuple[int, int]:
        st = self._stats_now()
        sp = sum(n for n, at in self.sp.values() if at == self._level)
        return (st.ap if st else 0, sp)

    # --- view -------------------------------------------------------------

    def update(self, r: Reading | None, _game_rect: tuple | None, _now: float) -> None:
        self._remember(r)
        self._r = r
        self._render_last()

    def _render_last(self) -> None:
        was = self._content
        items, content = self._items(self._r)
        self._render(items)
        level = self._level
        if self.tab.isVisible():
            self.dot = False
        elif was is not None and content != was and level is not None and level > self._seen_at:
            self.dot = True
        self._content = content
        self._seen_at = level if level is not None else 0

    def _items(self, r: Reading | None):  # -> (items, dot key)
        """Items are (kind, text..., go map) tuples, drawn in order."""
        if self._job is None or self._level is None:
            return [(("label", NO_CLASS, ACCENT), None)], None
        job, level = self._job, self._level
        plan = self._data.plan(job)
        out = [(("label", f"{job} · Lv {level}", VALUE_COLOR), None)]
        key = [job]
        self._plan_job = plan.job if plan else None
        if plan is None:
            out.append((("label", NO_PLAN.format(job), ACCENT), None))
            self._builds.hide()
        else:
            more, extra = self._plan_items(plan, level)
            out += more
            key += extra
        out += [(("label", t, ACCENT), None) for t in self._reasons(r)]
        return out, tuple(key)

    def _plan_items(self, plan, level: int):  # -> (items, dot key parts)
        out = []
        self._fill_builds(plan)
        build = plan.build(self._choices().get(plan.job))
        ap, sp = self._points()
        if ap or sp:
            halves = [f"{n} {w}" for n, w in ((ap, "AP"), (sp, "SP")) if n]
            out.append((("label", " · ".join(halves) + " to spend", ACCENT), None))
        out.append((("label", "Train here", LABEL_COLOR), None))
        rows = [r for r in training(plan, level) if r.place]
        for row in rows:
            out += self._train_items(row)
        gear_items, gkey = self._gear_items(build, level)
        out += gear_items
        tkey = [r.place.map_id or r.place.name for r in rows]
        adv = advance_due(plan, build, level)
        if adv:
            out.append((("label", advance_text(adv), VALUE_COLOR), None))
            where = " · ".join(p for p in (adv.npc, adv.where.name if adv.where else None) if p)
            if where:
                out.append((("label", where, LABEL_COLOR), _go_map(adv.where)))
        step = next_step(plan, build, level)
        if step:
            out.append((("label", "Next step", LABEL_COLOR), None))
            out.append((("label", step, VALUE_COLOR), None))
        return out, [tuple(tkey), tuple(gkey), adv is not None, ap + sp]

    def _train_items(self, row) -> list:
        detail = f"Lv {row.from_level}{DASH}{row.to_level} · mobs {row.mobs[0]}{DASH}{row.mobs[1]}"
        rate = self._best_rate(row.place.title) if row.place.title else None
        if rate:
            detail += f" · best {rate:,.0f}/min"
        return [
            (("label", row.place.name, VALUE_COLOR), None),
            (("label", detail, LABEL_COLOR), row.place.map_id),
        ]

    def _gear_items(self, build, level: int):  # -> (items, item ids)
        now, nxt = gear(build, level)
        out, ids = [], [g.item.id for g in (now, nxt) if g]
        if now or nxt:
            out.append((("label", "Gear", LABEL_COLOR), None))
        if now:
            out.append((("label", f"Now: {now.item.name}", VALUE_COLOR), None))
        if nxt:
            text = f"Next: {nxt.item.name} at {nxt.from_level}"
            out.append((("label", text, VALUE_COLOR), _go_map(nxt.where)))
            st = self._stats_now()
            lack = short(nxt.item, st.total if st else None)
            if lack:
                text = ", ".join(f"{n} {k} short" for k, n in lack.items())
                out.append((("label", text, ACCENT), None))
        return out, ids

    def _reasons(self, r: Reading | None) -> list[str]:
        st = r.stats if r else None
        bad = st == UNREADABLE or (
            isinstance(st, StatWindow) and r.level is not None and st.level != r.level
        )
        out = []
        if bad:
            out.append(STAT_UNREAD)
        elif self._stats_now() is None:
            out.append(OPEN_STATS)
        if r and r.skills == UNREADABLE:
            out.append(SKILL_UNREAD)
        return out

    def _choices(self) -> dict:
        """The saved build per job; a hand-edited non-dict value is replaced by an empty one."""
        if not isinstance(self._settings.get("class_builds"), dict):
            self._settings["class_builds"] = {}
        return self._settings["class_builds"]

    def _fill_builds(self, plan) -> None:
        names = [b.name for b in plan.builds]
        have = [self._builds.itemText(i) for i in range(self._builds.count())]
        want = plan.build(self._choices().get(plan.job)).name
        if have != names:
            self._builds.blockSignals(True)
            self._builds.clear()
            self._builds.addItems(names)
            self._builds.blockSignals(False)
        if self._builds.currentText() != want:
            self._builds.blockSignals(True)
            self._builds.setCurrentText(want)
            self._builds.blockSignals(False)
        self._builds.setVisible(len(names) > 1)

    def _render(self, items) -> None:
        """Redraw only when the items changed."""
        if self._shown == items:
            return
        self._shown = items
        old, self._body = self._body, QWidget()
        col = QVBoxLayout(self._body)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(2)
        for (_, text, color), map_id in items:
            label = text_label(text, LABEL_PT, color)
            label.setWordWrap(True)
            label.setMinimumWidth(0)
            if map_id is None:
                col.addWidget(label)
                continue
            line = QWidget()
            row = QHBoxLayout(line)
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(6)
            row.addWidget(label, 1)
            button = QPushButton("Go")
            button.setObjectName("go")
            button.setFocusPolicy(Qt.NoFocus)
            button.clicked.connect(lambda _=False, m=map_id: self._go(m))
            row.addWidget(button)
            col.addWidget(line)
        parent = self.tab.layout()
        parent.removeWidget(old)
        parent.addWidget(self._body)
        delete(old)  # at once: a widget left to deleteLater still shows in the tab's children
