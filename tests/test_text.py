from datetime import datetime

from maplelens.tools.exp_meter.meter import Rate
from maplelens.tools.exp_meter.text import (
    best_lines,
    box_lines,
    format_duration,
    format_last,
    short_name,
)


def test_box_lines_values():
    assert box_lines(Rate(12480, 0.42, 137), False) == [
        ("EXP · last 5 min", ["748,800 /h", "25.20% /h"]),
        ("Level up in", ["2h 17m"]),
    ]


def test_box_lines_no_rate():
    assert box_lines(None, False) == [
        ("EXP · measuring", ["— /h", "—% /h"]),
        ("Level up in", ["—"]),
    ]


def test_box_lines_early_rate():
    assert box_lines(Rate(12480, 0.42, 137, early=True), False)[0] == (
        "EXP · measuring",
        ["748,800 /h", "25.20% /h"],
    )


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


def test_box_lines_paused():
    assert box_lines(Rate(100, 0.1, None, paused=True), False)[0][0] == "EXP · paused"


def test_box_lines_unread():
    assert box_lines(Rate(100, 0.1, None, paused=True), False, True)[0][0] == "EXP · can't read bar"


def test_short_name():
    assert short_name("Victoria Island / Henesys Hunting Ground I") == "Henesys Hunting Ground I"
    assert short_name("No Street") == "No Street"


def test_best_lines_waiting():
    assert best_lines(None, 28, []) == ("Best maps: waiting for your class and level", [])


def test_best_lines_empty_and_rows():
    assert best_lines("Rogue", 28, [])[0] == "Best for Rogue, Lv 28 (±3): no 5-minute visits yet"
    head, rows = best_lines("Rogue", 28, [("Hidden Street / Pig Beach", 700.0, 0.03)])
    assert head == "Best for Rogue, Lv 28 (±3)"
    assert rows == [("Pig Beach", "42,000 EXP/h", "1.80% /h")]
