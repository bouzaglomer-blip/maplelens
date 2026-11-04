from datetime import datetime

from maplelens.tools.exp_meter.meter import Rate
from maplelens.tools.exp_meter.text import box_lines, format_duration, format_last


def test_box_lines_values():
    assert box_lines(Rate(12480, 0.42, 137), False) == [
        ("EXP · last 5 min", ["748,800 /h", "25.20% /h"]),
        ("Level up in", ["2h 17m"]),
    ]


def test_box_lines_no_rate():
    assert box_lines(None, False) == [
        ("EXP · last 5 min", ["— /h", "—% /h"]),
        ("Level up in", ["—"]),
    ]


def test_box_lines_no_level_eta():
    assert box_lines(Rate(100, 0.1, None), False)[1] == ("Level up in", ["—"])


def test_box_lines_waiting():
    assert box_lines(None, True) == [("waiting for game", [])]


def test_format_duration():
    assert format_duration(137) == "2h 17m"
    assert format_duration(45) == "45m"
    assert format_duration(0.4) == "<1m"


def test_format_last():
    now = datetime(2026, 11, 1, 15, 0).timestamp()
    assert format_last(datetime(2026, 11, 1, 1, 0).timestamp(), now) == "today"
    assert format_last(datetime(2026, 10, 31, 23, 0).timestamp(), now) == "yesterday"
    assert format_last(datetime(2026, 10, 29, 12, 0).timestamp(), now) == "Oct 29"
    assert format_last(datetime(2026, 10, 5, 12, 0).timestamp(), now) == "Oct 5"
