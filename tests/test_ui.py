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
