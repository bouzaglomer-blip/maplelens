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
    # 4 gains of 1.0 at level 22, then (100 - 98) + 1 = 3.0 across the wrap;
    # the first gain only starts the clock, so 6.0 over 120 s
    assert m.rate(150.5).pct_per_min == pytest.approx(6.0 / (120 / 60))
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
    for i, pct in enumerate([47, 48, 49, 50]):
        feed(m, i * 30, pct * 1000, pct)
    before = (m.open_segment().pct, m.rate(130).pct_per_min)
    feed(m, 120, 45000, 45)
    assert (m.open_segment().pct, m.rate(130).pct_per_min) == before


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
    assert m.rate(100) is None  # no gains, so no active time


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
    steady(m, 4)
    feed(m, 120, 500, 5.0, map_name="Town")
    closed = m.pop_closed()
    assert [s.pct for s in closed] == [pytest.approx(1.5)]
    seg = m.open_segment()
    assert seg.map_name == "Town"
    assert seg.pct == 0
    assert seg.exp == 0
    assert m.rate(100).pct_per_min == pytest.approx(1.0)


def test_paused_stretch_adds_no_active_time():
    m = ExpMeter()
    feed(m, 0, 1000, 10.0)
    for _ in range(4):
        m.feed(None)
    feed(m, 50, 1100, 10.5)
    seg = m.open_segment()
    assert seg.active_s == 0
    assert seg.pct == 0  # the first gain after the stretch only starts the clock, as live


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
    assert m.rate(131).pct_per_min == pytest.approx(1.0 / (100 / 60))


def test_covered_level_up_never_negative():
    m = ExpMeter()
    feed(m, 0, 50000, 50.0)
    feed(m, 30, 51000, 51.0)
    for t, level in [(60, 22), (90, 23)]:
        for dt in (0, 0.5):
            m.feed(Reading(t + dt, None, level, "Rogue", MAP))
    feed(m, 120, 60000, 30.0, level=23)
    segs = [*m.pop_closed(), m.open_segment()]
    assert all(s.pct >= 0 and s.exp >= 0 for s in segs)
    assert segs[0].pct == pytest.approx(1.0)
    assert m.rate(150).pct_per_min > 0


def test_paused_gain_not_credited_to_segment():
    m = ExpMeter()
    steady(m, 3)  # segment pct 1.0
    feed(m, 90, 1150, 11.5, map_name=None)
    assert m.open_segment().pct == pytest.approx(1.0)
    assert m.rate(150).pct_per_min == pytest.approx(1.5 / (90 / 60))


def test_single_dropped_frame_keeps_accrual():
    m = ExpMeter()
    feed(m, 0, 1000, 10.0)
    feed(m, 30, 1050, 10.5)
    m.feed(None)
    feed(m, 60, 1100, 11.0)
    assert m.open_segment().active_s == pytest.approx(60)


def test_rate_after_a_minute_of_active_time_even_if_app_started_earlier():
    m = ExpMeter()
    m.feed(None)  # app running long before any game reading
    for i in range(4):  # baseline at 1000.5; 1030.5 starts the clock; 1060.5, 1090.5 count
        feed(m, 1000 + i * 30, 1000 + 100 * i, 10 + 0.5 * i)
    rate = m.rate(1091)
    assert rate.pct_per_min == pytest.approx(1.0)
    assert not rate.paused


def test_afk_gap_neither_counts_nor_decays():
    m = ExpMeter()
    steady(m, 5)  # gains of 0.5 at 30.5 .. 120.5, active 120 s
    before = m.rate(121).pct_per_min
    assert m.rate(400).pct_per_min == pytest.approx(before)
    assert m.rate(400).paused
    feed(m, 600, 1300, 13.0)  # first gain after AFK: 1.0, gap 479.5 s, not counted
    assert m.rate(601).pct_per_min == pytest.approx(before)
    feed(m, 630, 1350, 13.5)
    assert m.rate(631).pct_per_min == pytest.approx(2.5 / (150 / 60))


def test_window_is_last_five_active_minutes_across_a_gap():
    m = ExpMeter()
    steady(m, 11)  # 10 gains of 0.5 over 300 active s, ending 300.5 at 15.0%
    for i in range(1, 5):  # 4 gains of 1.0; the one at 900.5 follows AFK, so it starts a stretch
        feed(m, 900 + (i - 1) * 30, 1500 + 100 * i, 15.0 + i)
    # window: the 3 counted 1.0 gains (90 s) + the last 7 old 0.5 gains (210 s)
    assert m.rate(991).pct_per_min == pytest.approx((3.0 + 3.5) / 5)


def test_walk_from_town_is_not_training_time():
    m = ExpMeter()
    feed(m, 0, 1000, 10.0)  # app started in town
    for i in range(1, 5):  # first kill 80 s later, then one every 30 s
        feed(m, 50 + i * 30, 1000 + 100 * i, 10 + 0.5 * i)
    # only the 3 gains after the first kill count: 1.5 % over 90 s
    assert m.rate(171).pct_per_min == pytest.approx(1.0)


def test_lasting_jump_is_learned_after_three_kills():
    """A 2x event or a richer map: every kill is suddenly 6x the old size, and stays so."""
    m = ExpMeter()
    steady(m, 13)  # 12 gains of 0.5 at 30.5 .. 360.5, last pct 16.0
    for i in range(1, 6):  # 5 gains of 3.0 at 390.5 .. 510.5
        feed(m, 360 + i * 30, 1600 + 300 * i, 16.0 + 3.0 * i)
    # the first two look like misreads; the third agrees, so it and the rest count
    assert m.open_segment().pct == pytest.approx(6.0 + 3 * 3.0)
    # window: the 3 counted 3.0 gains (gaps 90, 30, 30) + the last 5 old 0.5 gains (150 s)
    rate = m.rate(511)
    assert rate.pct_per_min == pytest.approx((9.0 + 2.5) / 5)
    assert not rate.paused


@pytest.mark.parametrize("first", [3, 15])  # the break right after the first kills, or later
def test_a_break_between_kills_is_not_training_time(first):
    """Buffing, walking to the spot, looting: a minute with no kill, under the idle cutoff."""
    m = ExpMeter()
    before = [2 * i for i in range(first)]
    kills = before + [before[-1] + 60 + 2 * i for i in range(60)]  # then 2 min of a kill / 2 s
    for i, t in enumerate(kills):
        feed(m, t, 1000 + 10 * i, 10 + 0.01 * i)
    # one kill per 2 s is 300 EXP/min; the break used to cut it until it left the window
    assert m.rate(kills[-1] + 1).exp_per_min == pytest.approx(300)
    seg = m.open_segment()  # the History row: the same sums
    assert seg.active_s == pytest.approx(2 * (len(kills) - 2))
    assert seg.exp / seg.active_s * 60 == pytest.approx(300)
