from pathlib import Path

import pytest

from maplelens.readers import Reading
from maplelens.readers.stat_window import StatWindow
from maplelens.store import DEFAULTS
from maplelens.tools.class_helper.data import MAPS, load

SMALL = Path(__file__).parent / "fixtures" / "classes_small.json"
RECT = (0, 0, 1366, 768)


def R(job="Rogue", level=12, stats=None, skills=None):
    return Reading(0.0, None, level, job, None, stats=stats, skills=skills)


def SW(level=12, ap=0):
    base = {"STR": 4, "DEX": 25, "INT": 4, "LUK": 4}
    return StatWindow(level, ap, base, dict(base), {})


@pytest.fixture
def make(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from maplelens.overlay import Layer
    from maplelens.tools.class_helper.ui import ClassHelperTool

    QApplication.instance() or QApplication([])

    def build(on_changed=lambda: None, best_rate=lambda t: None):
        layer = Layer()
        layer.show()
        gone = []
        settings = dict(DEFAULTS, class_builds={})
        tool = ClassHelperTool(
            settings, on_changed, layer, gone.append, best_rate, load(SMALL, MAPS)
        )
        tool.gone = gone
        return tool

    return build


def texts(tool):
    from PySide6.QtWidgets import QLabel

    return [w.text() for w in tool.tab.findChildren(QLabel) if not w.isHidden()]


def go_buttons(tool):
    from PySide6.QtWidgets import QPushButton

    bs = [b for b in tool.tab.findChildren(QPushButton) if b.text() == "Go" and not b.isHidden()]
    return sorted(bs, key=lambda b: b.mapTo(tool.tab, b.rect().topLeft()).y())


def test_unknown_class_says_so(make):
    from maplelens.tools.class_helper.ui import NO_CLASS

    tool = make()
    tool.update(R(job=None, level=None), RECT, 0)
    assert NO_CLASS in texts(tool)


def test_no_plan_for_job(make):
    from maplelens.tools.class_helper.ui import NO_PLAN

    tool = make()
    tool.update(R(job="Hermit", level=72), RECT, 0)
    assert NO_PLAN.format("Hermit") in texts(tool)


def test_training_rows_go_and_best_rate(make):
    tool = make(best_rate=lambda t: 1234.0)
    tool.update(R(level=12), RECT, 0)
    assert any("best 1,234/min" in t for t in texts(tool))
    go_buttons(tool)[0].click()
    assert tool.gone == ["000000001"]


def test_stats_never_read_then_badge_until_level_changes(make):
    from maplelens.tools.class_helper.ui import OPEN_STATS

    tool = make()
    tool.update(R(level=12), RECT, 0)
    assert OPEN_STATS in texts(tool)
    tool.update(R(level=12, stats=SW(level=12, ap=3)), RECT, 1)
    assert "3 AP to spend" in texts(tool)
    tool.update(R(level=13), RECT, 2)
    assert not any("AP to spend" in t for t in texts(tool))


def test_stat_window_of_another_level_is_unread(make):
    from maplelens.tools.class_helper.ui import STAT_UNREAD

    tool = make()
    tool.update(R(level=12, stats=SW(level=11, ap=3)), RECT, 0)
    assert STAT_UNREAD in texts(tool)
    assert not any("AP to spend" in t for t in texts(tool))


def test_build_picker_saved(make):
    saved = []
    tool = make(on_changed=lambda: saved.append(1))
    tool.update(R(level=12), RECT, 0)
    tool._builds.setCurrentText("Sindit")
    assert tool._settings["class_builds"] == {"Rogue": "Sindit"} and saved


def test_job_flicker_keeps_tab(make):
    from maplelens.tools.class_helper.ui import NO_CLASS

    tool = make()
    tool.update(R(level=12), RECT, 0)
    tool.update(R(job=None, level=12), RECT, 1)
    assert NO_CLASS not in texts(tool) and not tool.dot


def test_character_switch_forgets(make):
    from maplelens.tools.class_helper.ui import OPEN_STATS

    tool = make()
    tool.update(R(level=25, stats=SW(level=25, ap=0)), RECT, 0)
    tool.update(R(job="Magician", level=20), RECT, 1)
    assert OPEN_STATS in texts(tool)


def test_level_up_dot_until_opened(make):
    tool = make()
    tool.update(R(level=14), RECT, 0)  # tab not shown
    tool.update(R(level=15), RECT, 1)  # a new map or gear at 15
    assert tool.dot
    tool.tab.show()
    tool.update(R(level=15), RECT, 2)
    assert not tool.dot
