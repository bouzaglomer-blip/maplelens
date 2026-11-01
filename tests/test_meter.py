from dataclasses import replace

import pytest

from maplelens.readers import ExpValue, Reading
from maplelens.tools.exp_meter.meter import ExpMeter

MAP = "Dungeon / Ant Tunnel III"


def R(t, raw, pct, level=22, job="Rogue", map_name=MAP):
    return Reading(t, ExpValue(raw, pct), level, job, map_name)


def feed(m, *args, **kw):
    """Feed a reading twice (t and t+0.5) so it confirms at t+0.5."""
    r = R(*args, **kw)
    m.feed(r)
    m.feed(replace(r, t=r.t + 0.5))


def steady(m, n, step_s=30, start_pct=10.0):
    for i in range(n):
        feed(m, i * step_s, int((start_pct + 0.5 * i) * 100), start_pct + 0.5 * i)


def test_steady_gain_rate():
    m = ExpMeter()
    for i in range(13):
        feed(m, i * 30, 1000 + 100 * i, 10 + 0.5 * i)
    rate = m.rate(360.5)
    assert rate.exp_per_min == pytest.approx(200)
    assert rate.pct_per_min == pytest.approx(1.0)
    assert rate.minutes_to_level == pytest.approx((100 - 16.0) / 1.0)


def test_rate_none_before_a_minute():
    m = ExpMeter()
    steady(m, 3, step_s=20)
    assert m.rate(40.5) is None


def test_short_gaps_count_long_gaps_dont():
    m = ExpMeter()
    for i, t in enumerate([0, 60, 300, 330]):
        feed(m, t, 1000 + 100 * i, 10 + 0.5 * i)
    assert m.open_segment().active_s == pytest.approx(60 + 30)


def test_level_up_counts_across_wrap():
    m = ExpMeter()
    for i, pct in enumerate([94, 95, 96, 97, 98]):
        feed(m, i * 30, pct * 1000, pct)
    feed(m, 150, 1000, 1.0, level=23)
    # 4 gains of 1.0 at level 22, then (100 - 98) + 1 = 3.0 across the wrap
    assert m.rate(150.5).pct_per_min == pytest.approx(7.0 / (150.5 / 60))
    closed = m.pop_closed()
    assert len(closed) == 1
    assert closed[0].level == 22
    assert closed[0].pct == pytest.approx(7.0)
    assert closed[0].exp == 4000 + 3000
    seg = m.open_segment()
    assert seg.level == 23
    assert seg.pct == 0


def test_death_not_counted():
    m = ExpMeter()
    for i, pct in enumerate([48, 49, 50]):
        feed(m, i * 30, pct * 1000, pct)
    before = (m.open_segment().pct, m.rate(100).pct_per_min)
    feed(m, 90, 45000, 45)
    assert (m.open_segment().pct, m.rate(100).pct_per_min) == before


def test_jump_not_counted():
    m = ExpMeter()
    steady(m, 13)  # 12 gains of 0.5, last pct 16.0
    feed(m, 390, 2600, 26.0)  # +10 jump
    feed(m, 420, 2650, 26.5)  # counts from the new baseline
    assert m.open_segment().pct == pytest.approx(6.5)
    # window (121, 421]: gains at i = 5..12 and i = 14, nine of 0.5 over 300 s
    assert m.rate(421).pct_per_min == pytest.approx(0.9)


def test_single_frame_misread_ignored():
    m = ExpMeter()
    feed(m, 0, 500, 5.0)
    m.feed(R(30, 999, 9.99))
    feed(m, 60, 500, 5.0)
    assert m.open_segment().pct == 0
    assert m.rate(100).pct_per_min == 0


def test_map_change_closes_segment():
    m = ExpMeter()
    steady(m, 3)
    feed(m, 90, 1100, 11.0, map_name="Other Map")
    closed = m.pop_closed()
    assert [s.map_name for s in closed] == [MAP]
    assert closed[0].pct == pytest.approx(1.0)
    assert m.open_segment().map_name == "Other Map"
    assert m.pop_closed() == []


def test_death_then_map_change_counts_nothing():
    m = ExpMeter()
    steady(m, 3)
    feed(m, 90, 500, 5.0, map_name="Town")
    closed = m.pop_closed()
    assert [s.pct for s in closed] == [pytest.approx(1.0)]
    seg = m.open_segment()
    assert seg.map_name == "Town"
    assert seg.pct == 0
    assert seg.exp == 0
    assert m.rate(100).pct_per_min == pytest.approx(1.0 / (100 / 60))


def test_paused_stretch_adds_no_active_time():
    m = ExpMeter()
    feed(m, 0, 1000, 10.0)
    for _ in range(4):
        m.feed(None)
    feed(m, 50, 1100, 10.5)
    assert m.open_segment().active_s == 0


def test_unreadable_map_keeps_the_segment():
    m = ExpMeter()
    steady(m, 2)
    feed(m, 60, 1000, 11.0, map_name=None)
    feed(m, 90, 1100, 11.5)
    assert m.pop_closed() == []
    assert m.open_segment().start == 0.5


def test_close_closes_open_segment():
    m = ExpMeter()
    steady(m, 2)
    m.close(100)
    assert len(m.pop_closed()) == 1
    assert m.open_segment() is None


def test_covered_bar_keeps_baseline():
    m = ExpMeter()
    steady(m, 3)  # last pct 11.0
    for i in range(4):
        r = Reading(90 + i * 10, None, 22, "Rogue", MAP)
        m.feed(r)
    feed(m, 130, 1150, 11.5)
    assert m.open_segment().pct == pytest.approx(1.5)
    assert m.rate(131).pct_per_min == pytest.approx(1.5 / (131 / 60))
