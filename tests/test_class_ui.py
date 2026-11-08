from pathlib import Path

import pytest

from maplelens.readers import Reading
from maplelens.readers.skill_window import SkillRow, SkillWindow
from maplelens.readers.stat_window import StatWindow
from maplelens.readers.window import UNREADABLE
from maplelens.store import DEFAULTS
from maplelens.tools.class_helper.data import MAPS, load

SMALL = Path(__file__).parent / "fixtures" / "classes_small.json"
RECT = (0, 0, 1366, 768)


def R(job="Rogue", level=12, stats=None, skills=None):
    return Reading(0.0, None, level, job, None, stats=stats, skills=skills)


PLUS = {"STR": (170, 100), "DEX": (170, 120), "INT": (170, 140), "LUK": (170, 160)}
NIMBLE = 4000000


def s(str_, dex, int_, luk):
    return {"STR": str_, "DEX": dex, "INT": int_, "LUK": luk}


def SW(level=12, ap=0, base=None, plus=None):
    base = base or s(4, 25, 4, 4)
    return StatWindow(level, ap, base, dict(base), PLUS if plus is None else plus)


def KW(tab="Rogue", sp=0, rows=()):
    return SkillWindow(tab, sp, tuple(rows))


ALL_ROGUE = [SkillRow(NIMBLE, 0, (150, 120))]
ALL_BANDIT = [SkillRow(4200000, 0, (150, 120))]
LATER_ROWS_ONLY = [SkillRow(4000001, 0, (150, 120))]


def pos(x, y):
    return (x, y)  # RECT is 768 high at dpr 1


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


def test_planless_job_hides_the_picker(make):
    tool = make()
    tool.update(R(level=12), RECT, 0)
    assert not tool._builds.isHidden()
    tool.update(R(job="Hermit", level=72), RECT, 1)
    assert tool._builds.isHidden()


def test_bad_class_builds_setting_is_reset(make):
    tool = make()
    tool._settings["class_builds"] = "oops"
    tool.update(R(level=12), RECT, 0)
    assert tool._settings["class_builds"] == {}


def test_rings_on_the_plus_buttons(make):
    tool = make()
    tool.update(R(level=20, stats=SW(level=20, ap=5, base=s(4, 25, 4, 30))), RECT, 0)
    assert tool.marks() == [("5 here", pos(*PLUS["LUK"]))]


def test_marks_can_be_turned_off(make):
    saved = []
    tool = make(on_changed=lambda: saved.append(dict(tool._settings)))
    tool.update(R(level=20, stats=SW(level=20, ap=5, base=s(4, 25, 4, 30))), RECT, 0)
    tool.set_marks(False)
    assert tool.marks() == [] and saved[-1]["class_marks"] is False
    tool.update(R(level=20, stats=SW(level=20, ap=5, base=s(4, 25, 4, 30))), RECT, 1)
    assert tool.marks() == []  # stays off; the tab still reads the window
    tool.set_marks(True)
    assert tool.marks() == [("5 here", pos(*PLUS["LUK"]))]


def test_the_tab_box_and_the_menu_follow_each_other(make):
    from PySide6.QtWidgets import QCheckBox

    tool = make()
    tool.update(R(level=20, stats=SW(level=20, ap=5, base=s(4, 25, 4, 30))), RECT, 0)
    (box,) = tool.tab.findChildren(QCheckBox)
    menu = []
    tool.marks_changed = menu.append
    assert box.isChecked()
    box.click()  # the player unticks it in the tab
    assert tool.marks() == [] and menu == [False]
    tool.set_marks(True)  # the menu item
    assert box.isChecked() and menu == [False, True] and tool.marks()
    tool.set_marks(True)  # the box following the menu: nothing new
    assert menu == [False, True]


def test_marks_follow_and_hide(make):
    tool = make()
    tool.update(R(level=20, stats=SW(level=20, ap=5)), RECT, 0)
    moved = SW(level=20, ap=5, plus={k: (x + 40, y) for k, (x, y) in PLUS.items()})
    tool.update(R(level=20, stats=moved), RECT, 1)
    assert [p for _, p in tool.marks()] == [pos(PLUS["LUK"][0] + 40, PLUS["LUK"][1])]
    tool.update(R(level=20), RECT, 2)
    assert tool.marks() == []


def test_unreadable_window_hides_marks_and_says_why(make):
    from maplelens.tools.class_helper.ui import STAT_UNREAD

    tool = make()
    tool.update(R(level=20, stats=SW(level=20, ap=5)), RECT, 0)
    tool.update(R(level=20, stats=UNREADABLE), RECT, 1)
    assert tool.marks() == [] and STAT_UNREAD in texts(tool)


def test_over_and_behind_tags(make):
    tool = make()
    tool.update(R(level=20, stats=SW(level=20, ap=0, base=s(4, 35, 4, 20))), RECT, 0)
    assert {t for t, _ in tool.marks()} == {"DEX 10 over plan", "LUK 10 behind plan"}


def test_scroll_the_list_once(make):
    from maplelens.tools.class_helper.ui import SCROLL

    tool = make()
    tool.update(R(level=20, skills=KW(rows=LATER_ROWS_ONLY, sp=2)), RECT, 0)
    assert [t for t, _ in tool.marks()] == [SCROLL]


def test_skill_ring_and_merged_memory(make):
    tool = make()
    tool.update(R(level=20, skills=KW(rows=ALL_ROGUE, sp=2)), RECT, 0)
    assert tool.marks() == [("2 here", pos(150, 120))]
    tool.update(R(level=20, skills=KW(rows=LATER_ROWS_ONLY, sp=2)), RECT, 1)
    assert tool.skills["Rogue"] == {NIMBLE: 0, 4000001: 0}


def test_tabs_are_remembered_apart(make):
    tool = make()
    tool.update(R(level=32, job="Bandit", skills=KW(tab="Rogue", sp=2, rows=ALL_ROGUE)), RECT, 0)
    tool.update(R(level=32, job="Bandit", skills=KW(tab="Bandit", sp=0, rows=ALL_BANDIT)), RECT, 1)
    tool.update(R(level=32, job="Bandit"), RECT, 2)
    assert "1st job tab: 2 SP to place" in texts(tool)


def test_lower_skill_level_means_another_character(make):
    tool = make()
    first = [SkillRow(NIMBLE, 5, (150, 120)), SkillRow(4000001, 3, (150, 160))]
    tool.update(R(level=20, skills=KW(rows=first, sp=2)), RECT, 0)
    tool.update(R(level=20, skills=KW(rows=[SkillRow(NIMBLE, 2, (150, 120))], sp=2)), RECT, 1)
    assert tool.skills["Rogue"] == {NIMBLE: 2}


def test_marks_scale_with_client_and_dpr(make, monkeypatch):
    from maplelens.overlay import Layer, game_to_layer

    monkeypatch.setattr(Layer, "devicePixelRatioF", lambda self: 2.0)
    tool = make()
    tool.update(R(level=20, stats=SW(level=20, ap=5)), (0, 0, 2560, 1440), 0)
    k = 1440 / 768
    x, y = PLUS["LUK"]
    assert tool.marks() == [("5 here", game_to_layer(x * k, y * k, 2.0))]


def test_stat_window_of_another_level_gets_no_marks(make):
    tool = make()
    tool.update(R(level=20, stats=SW(level=19, ap=5)), RECT, 0)
    assert tool.marks() == []


class _Quiet:
    running = False
    dot = False

    def update(self, *_):
        pass


class _Box:
    def set_tab_dot(self, *_):
        pass


def test_marks_survive_the_app_tick(make):
    from maplelens import app

    tool = make()
    reading = R(level=20, stats=SW(level=20, ap=5, base=s(4, 25, 4, 30)))
    app.update_tools(_Box(), _Quiet(), _Quiet(), tool, reading, RECT, 0.0, set())
    assert tool.marks() == [("5 here", pos(*PLUS["LUK"]))]


def test_marks_hide_when_the_class_tool_raises(make, monkeypatch):
    import sys

    from maplelens import app

    monkeypatch.setattr(sys, "stderr", None)
    tool = make()
    reading = R(level=20, stats=SW(level=20, ap=5, base=s(4, 25, 4, 30)))
    tool.update(reading, RECT, 0)
    assert tool.marks()
    monkeypatch.setattr(tool, "_draw_marks", lambda: (_ for _ in ()).throw(ValueError("x")))
    app.update_tools(_Box(), _Quiet(), _Quiet(), tool, reading, RECT, 1.0, set())
    assert tool.marks() == []
