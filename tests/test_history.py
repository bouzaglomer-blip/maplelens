from pytest import approx

from maplelens.tools.exp_meter.history import best_rate, history, open_db, save_segment
from maplelens.tools.exp_meter.meter import Segment


def _seg(start, exp=0, active_s=60.0, level=44, map_name="Henesys", job="Hero", pct=0.0):
    return Segment(start, start + 60, map_name, job, level, exp, pct, active_s)


def test_history_groups_and_averages(tmp_path):
    conn = open_db(tmp_path / "t.db")
    save_segment(conn, _seg(0, exp=600, pct=1.2))
    save_segment(conn, _seg(100, exp=0))
    (row,) = history(conn)
    assert row.exp_per_min == approx(300)
    assert row.pct_per_min == approx(0.6)
    assert row.active_s == 120
    assert row.last == 160


def test_level_split_rows(tmp_path):
    conn = open_db(tmp_path / "t.db")
    save_segment(conn, _seg(0, level=44))
    save_segment(conn, _seg(100, level=45))
    assert len(history(conn)) == 2


def test_resave_same_segment_replaces(tmp_path):
    conn = open_db(tmp_path / "t.db")
    save_segment(conn, _seg(0, exp=100))
    save_segment(conn, _seg(0, exp=900))
    (row,) = history(conn)
    assert row.exp_per_min == approx(900)


def test_order_newest_first(tmp_path):
    conn = open_db(tmp_path / "t.db")
    save_segment(conn, _seg(0, map_name="Old"))
    save_segment(conn, _seg(100, map_name="New"))
    assert [r.map_name for r in history(conn)] == ["New", "Old"]


def test_zero_active_excluded(tmp_path):
    conn = open_db(tmp_path / "t.db")
    save_segment(conn, _seg(0, active_s=0.0))
    assert history(conn) == []


def test_best_rate(tmp_path):
    conn = open_db(tmp_path / "t.db")
    save_segment(conn, _seg(0, exp=600, level=44))
    save_segment(conn, _seg(100, exp=900, level=45))
    assert best_rate(conn, "Henesys") == approx(900)
    assert best_rate(conn, "Nowhere") is None
