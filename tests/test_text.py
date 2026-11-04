from datetime import datetime

from maplelens.tools.exp_meter.meter import Rate
from maplelens.tools.exp_meter.text import format_box, format_duration, format_last


def test_format_box_values():
    assert (
        format_box(Rate(12480, 0.42, 137), False)
        == "EXP · last 5 min\n748,800 /h\n25.20% /h\nLevel up in\n2h 17m"
    )


def test_format_box_no_rate():
    assert format_box(None, False) == "EXP · last 5 min\n— /h\n—% /h\nLevel up in\n—"


def test_format_box_no_level_eta():
    assert format_box(Rate(100, 0.1, None), False).endswith("Level up in\n—")


def test_format_box_waiting():
    assert format_box(None, True) == "waiting for game"


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
