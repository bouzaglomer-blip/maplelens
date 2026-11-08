"""The class helper's Class tab: where to train now, then what's next."""

from collections.abc import Callable

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget
from shiboken6 import delete

from maplelens.overlay import (
    ACCENT,
    CHIP_BG,
    FONT,
    HERE_BG,
    LABEL_COLOR,
    LABEL_PT,
    TAB_W,
    VALUE_COLOR,
    InfoLine,
    Layer,
    game_to_layer,
    text_label,
)
from maplelens.readers import Reading, glyphs
from maplelens.readers.skill_window import SkillWindow
from maplelens.readers.stat_window import StatWindow
from maplelens.readers.window import UNREADABLE
from maplelens.tools.class_helper.data import ClassData, Place, load
from maplelens.tools.class_helper.plan import (
    advance_ready,
    ap_advice,
    band_at,
    gear,
    milestones,
    short,
    short_name,
    sp_advice,
    training,
)

MARKS = "AP/SP marks on game windows"
NO_CLASS = "Can't read your class yet"
NO_PLAN = "No plan for {} yet"
TRAIN = "Train here · click to go"
NO_SPOTS = "No training spots in the guide for Lv {}"
READY = "Job advance is ready"
NEXT = "Next"
OPEN_STATS = "Open your stat window once"
STAT_UNREAD = "Can't read your stat window: move it fully into view"
SKILL_UNREAD = "Can't read your skill window: move it fully into view"
SCROLL = "scroll the list once"
TIERS = {0: "Beginner", 1: "1st job", 2: "2nd job"}
RING_R, TAG_GAP = 11, 26  # ring radius; the tag starts this far right of the + centre
MARK_PT = 9  # the tags over the game's windows keep their size; the box's labels grew

DASH = "\u2013"
_PAD = 6  # a row's side padding


class Row(QWidget):
    """One line to act on: a name, a grey line under it, and a yellow \u203a when a click goes
    somewhere. Names never wrap: they're cut to fit, the full one is the tooltip."""

    def __init__(
        self,
        name: str,
        sub: str,
        on_click: Callable[[], None] | None,
        *,
        best: bool = False,
        outline: bool = False,
    ):
        super().__init__()
        self.name, self.sub, self.best = name, sub, best
        self.clickable, self._on_click = on_click is not None, on_click
        self.setObjectName("row")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setFocusPolicy(Qt.NoFocus)
        bg = HERE_BG if best or outline else "transparent"
        edge = f"1px solid {ACCENT}" if outline else f"1px solid {bg}"
        self.setStyleSheet(f"#row {{ background: {bg}; border: {edge}; border-radius: 4px; }}")
        if self.clickable:
            self.setCursor(Qt.PointingHandCursor)
        row = QHBoxLayout(self)
        row.setContentsMargins(_PAD, 3, _PAD, 3)
        row.setSpacing(6)
        col = QVBoxLayout()
        col.setSpacing(0)
        arrow = text_label("\u203a", LABEL_PT + 2, ACCENT, bold=True)  # single right angle
        room = TAB_W - 2 * _PAD - 2 - (arrow.sizeHint().width() + 6 if self.clickable else 0)
        title = text_label(name, LABEL_PT, VALUE_COLOR, bold=best or outline)
        title.setText(QFontMetrics(title.font()).elidedText(name, Qt.ElideRight, room))
        title.setToolTip(name)
        col.addWidget(title)
        if sub:
            under = text_label(sub, LABEL_PT, LABEL_COLOR)
            under.setText(QFontMetrics(under.font()).elidedText(sub, Qt.ElideRight, room))
            col.addWidget(under)
        row.addLayout(col, 1)
        if self.clickable:
            row.addWidget(arrow, 0, Qt.AlignVCenter)

    def click(self) -> None:
        if self._on_click:
            self._on_click()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.rect().contains(event.position().toPoint()):
            self.click()


class _Mark(QWidget):
    """A ring of ACCENT with a tag beside it, or a quiet tag alone. Never takes a click."""

    def __init__(self, layer: Layer):
        super().__init__(layer)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFont(QFont(FONT, MARK_PT, QFont.Bold))
        self.tag, self.centre, self.ring = "", (0, 0), False
        self.hide()

    def put(self, tag: str, centre: tuple[float, float], ring: bool) -> None:
        self.tag, self.centre, self.ring = tag, centre, ring
        w = TAG_GAP + QFontMetrics(self.font()).horizontalAdvance(tag) + 6
        self.setGeometry(round(centre[0]) - RING_R, round(centre[1]) - RING_R, w, 2 * RING_R)
        self.show()
        self.update()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setFont(self.font())
        colour = QColor(ACCENT if self.ring else LABEL_COLOR)
        if self.ring:
            p.setPen(QPen(colour, 3))
            p.drawEllipse(QRectF(2, 2, 2 * RING_R - 4, 2 * RING_R - 4))
        p.setPen(colour)
        p.drawText(
            QRectF(TAG_GAP, 0, self.width() - TAG_GAP, self.height()), Qt.AlignVCenter, self.tag
        )


def _tag(stat: str, a) -> str:
    if a.add:
        return f"{a.add} here"
    if a.over:
        return f"{stat}{a.over} over plan"
    return f"{stat}{a.behind} behind plan" if a.behind else ""


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
        self.builds_changed: Callable[[], None] = lambda: None  # the menu's Build item follows
        self._builds_seen: tuple | None = None  # (job, build names, build) last told
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
        self._rect: tuple | None = None
        self._pool: list[_Mark] = []  # the layer owns them; they are hidden and reused
        self._marks: list[tuple[str, tuple[float, float], bool]] = []
        self.tab = QWidget()
        self.tab.setFixedWidth(TAB_W)
        self._body = QWidget()
        col = QVBoxLayout(self.tab)
        col.setContentsMargins(0, 4, 0, 0)
        col.addWidget(self._body)
        self._render([("info", NO_CLASS)])

    def hide_marks(self) -> None:
        for m in self._pool:
            m.hide()

    def set_marks(self, on: bool) -> None:
        """Turn the marks on the game's windows on or off (the menu's item); the tab stays."""
        if self._settings.get("class_marks", True) == on:
            return
        self._settings["class_marks"] = on
        self._changed()
        self._draw_marks()

    def marks(self) -> list[tuple[str, tuple[int, int]]]:
        return [(m.tag, m.centre) for m in self._pool if not m.isHidden()]

    def _draw_marks(self) -> None:
        self.hide_marks()
        r, rect = self._r, self._rect
        if not self._settings.get("class_marks", True):
            return
        if r is None or rect is None or self._job is None or self._level is None:
            return
        k = rect[3] / glyphs.BASE_H  # normalized px -> client px
        dpr = self._layer.devicePixelRatioF()
        found = self._ap_marks(r) + self._sp_marks(r)
        while len(self._pool) < len(found):
            self._pool.append(_Mark(self._layer))
        for m, (tag, (x, y), ring) in zip(self._pool, found, strict=False):
            m.put(tag, game_to_layer(x * k, y * k, dpr), ring)

    def _ap_marks(self, r: Reading) -> list:
        st, level = r.stats, self._level
        plan = self._data.plan(self._job)
        if not isinstance(st, StatWindow) or st.level != level or plan is None:
            return []
        band = band_at(plan.build(self._choices().get(plan.job)), level)
        if band is None:
            return []
        out = []
        for stat, a in ap_advice(band, level, st.base, st.ap).items():
            if stat in st.plus:
                tag = _tag(stat + " ", a)
                if tag:
                    out.append((tag, st.plus[stat], a.add > 0))
        return out

    def _sp_marks(self, r: Reading) -> list:
        sk = r.skills
        plan = self._data.plan(sk.tab) if isinstance(sk, SkillWindow) else None
        if plan is None or not sk.rows:
            return []
        steps = plan.build(self._choices().get(plan.job)).sp
        advice = sp_advice(steps, self.skills[sk.tab], sk.sp, self._data.skills, sk.tab)
        if advice is None:
            return [(SCROLL, sk.rows[0].plus, False)]
        planned = {s.skill for s in steps}
        out = []
        for row in sk.rows:
            a = advice.get(row.skill)
            tag = _tag("", a) if row.skill in planned else ("off plan" if a and a.over else "")
            if a and tag:
                out.append((tag, row.plus, a.add > 0))
        return out

    def _plan(self):
        return self._data.plan(self._plan_job) if self._plan_job else None

    def build_names(self) -> list[str]:
        """The current plan's builds, when there's a choice to make."""
        plan = self._plan()
        names = [b.name for b in plan.builds] if plan else []
        return names if len(names) > 1 else []

    def build_name(self) -> str | None:
        plan = self._plan()
        return plan.build(self._choices().get(plan.job)).name if plan else None

    def pick_build(self, name: str) -> None:
        if self._plan_job is None or not name:
            return
        self._choices()[self._plan_job] = name
        self._changed()
        self._render_last()

    def _tell_builds(self) -> None:
        seen = (self._plan_job, tuple(self.build_names()), self.build_name())
        if seen != self._builds_seen:
            self._builds_seen = seen
            self.builds_changed()

    # --- memory -----------------------------------------------------------

    def _remember(self, r: Reading | None) -> None:
        job = r.job if r else None
        level = r.level if r else None
        sk = r.skills if r else None
        lower = isinstance(sk, SkillWindow) and any(
            row.level < self.skills.get(sk.tab, {}).get(row.skill, 0) for row in sk.rows
        )  # skill levels never fall within one character
        if (
            (job and self._job and job != self._job)
            or (level is not None and self._level is not None and level < self._level)
            or lower
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
        if isinstance(sk, SkillWindow) and self._level is not None:
            self.skills.setdefault(sk.tab, {}).update({row.skill: row.level for row in sk.rows})
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

    def update(self, r: Reading | None, game_rect: tuple | None, _now: float) -> None:
        self._remember(r)
        self._r, self._rect = r, game_rect
        self._render_last()

    def _render_last(self) -> None:
        was = self._content
        items, content = self._items(self._r)
        self._render(items)
        self._draw_marks()
        self._tell_builds()
        level = self._level
        if self.tab.isVisible():
            self.dot = False
        elif was is not None and content != was and level is not None and level > self._seen_at:
            self.dot = True
        self._content = content
        self._seen_at = level if level is not None else 0

    def _items(self, r: Reading | None):  # -> (items, dot key)
        """Items are tuples, drawn in order: ("info", text), ("label", text, colour),
        ("header", text, chip), ("row", name, sub, go map, best, outline), ("divider",)."""
        if self._job is None or self._level is None:
            return [("info", NO_CLASS)], None
        job, level = self._job, self._level
        plan = self._data.plan(job)
        self._plan_job = plan.job if plan else None
        hints = [("info", t) for t in self._tab_lines(r) + self._reasons(r)]
        if plan is None:  # the hints stay: a 1st-job tab's SP still needs placing
            return [("info", NO_PLAN.format(job)), *hints], (job,)
        build = plan.build(self._choices().get(plan.job))
        ap, sp = self._points()
        chip = " · ".join(f"{n} {w}" for n, w in ((ap, "AP"), (sp, "SP")) if n)
        out = [("header", f"{job} · Lv {level}", chip)]
        adv = advance_ready(plan, build, level)
        if adv:
            where = short_name(adv.where.name) if adv.where else None
            sub = " · ".join(p for p in (adv.npc, where) if p)
            out.append(("row", READY, sub, _go_map(adv.where), False, True))
        out += self._train_items(plan, level, best=adv is None)
        out += self._next_items(plan, build, level)
        out += hints
        tkey = tuple(t.place.map_id or t.place.name for t in training(plan, level) if t.place)
        gkey = tuple(g.item.id for g in gear(build, level) if g)
        return out, (job, tkey, gkey, adv is not None, ap + sp)

    def _train_items(self, plan, level: int, *, best: bool) -> list:
        rows = [t for t in training(plan, level) if t.place]
        if not rows:
            return [("label", TRAIN, LABEL_COLOR), ("info", NO_SPOTS.format(level))]
        rates = [self._best_rate(t.place.title) if t.place.title else None for t in rows]
        known = [(rate, i) for i, rate in enumerate(rates) if rate]
        top = max(known)[1] if best and known else None
        out = [("label", TRAIN, LABEL_COLOR)]
        for i, (t, rate) in enumerate(zip(rows, rates, strict=True)):
            sub = (
                f"your best · {rate:,.0f}/min" if rate else f"mobs Lv {t.mobs[0]}{DASH}{t.mobs[1]}"
            )
            out.append(("row", short_name(t.place.name), sub, t.place.map_id, i == top, False))
        return out

    def _next_items(self, plan, build, level: int) -> list:
        steps = milestones(plan, build, level)
        if not steps:
            return []
        out = [("divider",), ("label", NEXT, LABEL_COLOR)]
        st = self._stats_now()
        for m in steps:  # "Lv 30 · Advance" over "Assassin or Bandit": short lines, never cut
            kind, _, detail = m.text.partition(": ")
            out.append(("row", f"Lv {m.level} · {kind}", detail, _go_map(m.where), False, False))
            lack = short(m.item, st.total if st else None) if m.item else {}
            if lack:
                out.append(
                    ("label", ", ".join(f"{n} {k} short" for k, n in lack.items()), LABEL_COLOR)
                )
        return out

    def _tab_lines(self, r: Reading | None) -> list[str]:
        """A skill tab left with SP, other than the one open now."""
        open_tab = r.skills.tab if r and isinstance(r.skills, SkillWindow) else None
        out = []
        for tab, (n, at) in self.sp.items():
            plan = self._data.plan(tab)
            if tab != open_tab and n > 0 and at == self._level and plan:
                out.append(f"{TIERS.get(plan.tier, tab)} tab: {n} SP to place")
        return out

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

    def _widget(self, item) -> QWidget:
        kind = item[0]
        if kind == "info":
            return InfoLine(item[1])
        if kind == "label":
            label = text_label(item[1], LABEL_PT, item[2])
            label.setWordWrap(True)
            return label
        if kind == "divider":
            line = QWidget()
            line.setFixedHeight(1)
            line.setAttribute(Qt.WA_StyledBackground, True)
            line.setStyleSheet(f"background: {HERE_BG};")
            return line
        if kind == "row":
            _, name, sub, map_id, best, outline = item
            go = (lambda m=map_id: self._go(m)) if map_id else None
            return Row(name, sub, go, best=best, outline=outline)
        _, text, chip = item  # the header
        head = QWidget()
        row = QHBoxLayout(head)
        row.setContentsMargins(0, 0, 0, 2)
        row.addWidget(text_label(text, LABEL_PT, LABEL_COLOR))
        row.addStretch()
        if chip:
            badge = text_label(chip, LABEL_PT, ACCENT, bold=True)
            badge.setObjectName("chip")
            badge.setStyleSheet(
                f"#chip {{ color: {ACCENT}; background: {CHIP_BG}; border-radius: 8px;"
                " padding: 0 7px; }"
            )
            row.addWidget(badge)
        return head

    def _render(self, items) -> None:
        """Redraw only when the items changed."""
        if self._shown == items:
            return
        self._shown = items
        old, self._body = self._body, QWidget()
        col = QVBoxLayout(self._body)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(3)
        for item in items:
            col.addWidget(self._widget(item))
        parent = self.tab.layout()
        parent.insertWidget(parent.indexOf(old), self._body)
        parent.removeWidget(old)
        delete(old)  # at once: a widget left to deleteLater still shows in the tab's children
