from maplelens.readers import ExpValue, Reading
from maplelens.store import DEFAULTS
from maplelens.tools.exp_meter.history import history, open_db


def test_tool_flushes_open_segment_each_minute(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from maplelens.tools.exp_meter.ui import ExpMeterTool

    app = QApplication.instance() or QApplication([])
    conn = open_db(tmp_path / "h.db")
    tool = ExpMeterTool(dict(DEFAULTS, boxes={}), conn, lambda: None)
    for i in range(73):  # 3 minutes at 2.5 s; each EXP value is read twice, as the meter needs
        t = 1000.0 + i * 2.5
        exp = ExpValue(1000 + i // 2 * 100, 10 + i // 2 * 0.1)
        tool.update(Reading(t, exp, 50, "Mage", "Ant Tunnel"), None, t)
    rows = history(conn)
    assert len(rows) == 1  # nothing closed, so this came from the periodic flush
    assert rows[0].active_s >= 120
    tool.shutdown(1182.5)
    app.processEvents()


def test_closing_history_window_does_not_quit(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    from maplelens.tools.exp_meter.ui import HistoryWindow

    app = QApplication.instance() or QApplication([])
    win = HistoryWindow(open_db(tmp_path / "h.db"))
    win.show()
    survived = []
    QTimer.singleShot(0, win.close)
    QTimer.singleShot(200, lambda: survived.append(1))
    QTimer.singleShot(300, app.quit)  # exec() must still be running at 200 ms
    app.exec()
    assert survived == [1]


def test_quit_menu_item_saves_and_quits(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    from maplelens.app import build_box
    from maplelens.tools.exp_meter.ui import ExpMeterTool

    app = QApplication.instance() or QApplication([])
    conn = open_db(tmp_path / "h.db")
    tool = ExpMeterTool(dict(DEFAULTS, boxes={}), conn, lambda: None)
    for i in range(9):  # 20 s of play: too short for the periodic flush
        t = 1000.0 + i * 2.5
        exp = ExpValue(1000 + i // 2 * 100, 10 + i // 2 * 0.1)
        tool.update(Reading(t, exp, 50, "Mage", "Ant Tunnel"), None, t)
    assert history(conn) == []
    box = build_box(dict(DEFAULTS, boxes={}), lambda: None, [tool])
    (quit_item,) = [a for a in box.actions() if a.text() == "Quit MapleLens"]
    save = lambda: tool.shutdown(1020.0)  # noqa: E731 - what app.py connects
    app.aboutToQuit.connect(save)
    QTimer.singleShot(0, quit_item.trigger)
    timed_out = []
    QTimer.singleShot(2000, lambda: (timed_out.append(1), app.exit()))  # no hang if Quit fails
    try:
        app.exec()
    finally:
        app.aboutToQuit.disconnect(save)
    assert not timed_out
    assert len(history(conn)) == 1


def test_history_button_on_exp_tab(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QPushButton

    from maplelens.tools.exp_meter.ui import ExpMeterTool

    QApplication.instance() or QApplication([])
    tool = ExpMeterTool(dict(DEFAULTS, boxes={}), open_db(tmp_path / "h.db"), lambda: None)
    assert tool.title == "EXP"
    (button,) = tool.tab.findChildren(QPushButton)
    assert button.text() == "History"
    button.click()
    assert tool._history.isVisible()
    tool._history.close()
