"""EXP rate, idle time and per-map/class/level segments from a stream of readings."""

from collections import deque
from dataclasses import dataclass, replace
from statistics import median

from maplelens.readers import ExpValue, Reading


@dataclass
class Rate:
    exp_per_min: float
    pct_per_min: float
    minutes_to_level: float | None
    paused: bool = False  # no gain for longer than the idle cutoff: the numbers are the last ones


@dataclass
class Segment:
    start: float
    end: float
    map_name: str
    job: str
    level: int
    exp: int = 0
    pct: float = 0.0
    active_s: float = 0.0


class _Confirmed:
    """A field's value, which only changes once the same raw value arrives twice in a row."""

    def __init__(self):
        self.last = self.value = None

    def update(self, v) -> bool:
        changed = v == self.last and v != self.value
        if changed:
            self.value = v
        self.last = v
        return changed


class ExpMeter:
    def __init__(self, idle_cutoff_s: float = 90, jump_factor: float = 5, window_s: float = 300):
        self.idle_cutoff_s = idle_cutoff_s
        self.jump_factor = jump_factor
        self.window_s = window_s
        self._exp, self._level, self._job, self._map = fields = tuple(
            _Confirmed() for _ in range(4)
        )
        self._fields = fields
        self._base: tuple[ExpValue, int | None] | None = None  # last non-None exp and its level
        # (t, raw, pct, gap) gains whose gap since the previous exp event is under the cutoff
        self._window: deque[tuple[float, int, float, float]] = deque()
        self._event_t: float | None = None  # last exp event: the baseline or an accepted gain
        self._recent: deque[float] = deque(maxlen=50)  # pct of the last counted gains
        self._seg: Segment | None = None
        self._closed: list[Segment] = []
        self._last_event_t: float | None = None

    def feed(self, r: Reading | None) -> None:
        t = r.t if r else None
        vals = (r.exp, r.level, r.job, r.map_name) if r else (None,) * 4
        exp_ch, *_ = (f.update(v) for f, v in zip(self._fields, vals, strict=True))

        level = self._level.value
        ctx = (self._map.value, self._job.value, level)

        # 1. exp change, credited to the segment open now (a level-up's wrap goes to the old level)
        # the baseline is the last confirmed non-None exp; an unreadable bar never resets it
        if exp_ch and self._exp.value is not None:
            if self._base is not None:
                self._on_exp(*self._base, None in ctx, t)
            else:
                self._event_t = t
            self._base = (self._exp.value, level)

        # 2. close on a confirmed change to a different non-None value, then open
        seg = self._seg
        if seg and any(
            c is not None and c != s
            for c, s in zip(ctx, (seg.map_name, seg.job, seg.level), strict=True)
        ):
            self._close(t)
        if self._seg is None and None not in ctx:
            self._seg = Segment(t, t, *ctx[:2], level)
            self._last_event_t = t

        # 3. map, job or level confirmed unreadable: pause accrual, keep the segment
        if None in ctx:
            self._last_event_t = None

    def _gain(self, old: ExpValue, old_level) -> tuple[float, float] | None:
        """(exp, %) gained since `old`, or None for a death, a misread or a spike."""
        new, level = self._exp.value, self._level.value
        gain = None
        if old_level is None or level is None:
            return None
        if level == old_level:
            if new.raw >= old.raw and new.pct >= old.pct:  # a drop at the same level is a death
                gain = (new.raw - old.raw, new.pct - old.pct)
        elif level > old_level:
            # ponytail: level-up needs the level and the % drop to confirm on the same feed;
            # a level misread at that moment counts the wrap as a death. Look at the level
            # one feed later if that shows up.
            base = old.raw / (old.pct / 100) - old.raw if old.pct else 0
            gain = (round(base) + new.raw, (100 - old.pct) + new.pct)
        if gain and len(self._recent) >= 10:
            med = median(self._recent)
            if med > 0 and gain[1] > self.jump_factor * med:
                return None
        return gain

    def _on_exp(self, old: ExpValue, old_level, paused: bool, t: float) -> None:
        gain = self._gain(old, old_level)
        if gain:
            self._recent.append(gain[1])
            # a gain right after an idle stretch only starts a new one: neither its time nor its exp
            if (gap := t - self._event_t) <= self.idle_cutoff_s:
                self._window.append((t, *gain, gap))
                active = sum(g[3] for g in self._window)
                while active - self._window[0][3] >= self.window_s:  # last window_s of active time
                    active -= self._window.popleft()[3]
            self._event_t = t
        seg = self._seg
        if seg and not paused:  # gains while paused count in the live rate only
            if self._last_event_t is not None and t - self._last_event_t <= self.idle_cutoff_s:
                seg.active_s += t - self._last_event_t
            if gain:
                seg.exp += gain[0]
                seg.pct += gain[1]
            seg.end = self._last_event_t = t

    def _close(self, t: float) -> None:
        if self._seg:
            self._seg.end = t
            self._closed.append(self._seg)
        self._seg = self._last_event_t = None

    def rate(self, now: float) -> Rate | None:
        """EXP per minute of active time over the last `window_s` of it; None under a minute."""
        active = sum(g[3] for g in self._window)
        if active < 60:
            return None
        minutes = active / 60
        pct_per_min = sum(g[2] for g in self._window) / minutes
        exp = self._exp.value
        left = (100 - exp.pct) / pct_per_min if exp and pct_per_min > 0 else None
        paused = now - self._event_t > self.idle_cutoff_s
        return Rate(sum(g[1] for g in self._window) / minutes, pct_per_min, left, paused)

    @property
    def job(self) -> str | None:
        return self._job.value

    @property
    def level(self) -> int | None:
        return self._level.value

    def pop_closed(self) -> list[Segment]:
        closed, self._closed = self._closed, []
        return closed

    def open_segment(self) -> Segment | None:
        return replace(self._seg) if self._seg else None

    def close(self, now: float) -> None:
        self._close(now)
