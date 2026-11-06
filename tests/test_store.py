from maplelens.store import DEFAULTS, data_dir, load_settings, save_settings


def test_missing_settings_gives_defaults(tmp_path):
    assert load_settings(tmp_path / "x.json") == DEFAULTS


def test_settings_roundtrip_keeps_defaults(tmp_path):
    p = tmp_path / "s.json"
    save_settings(p, {"window_title": "Maple"})
    s = load_settings(p)
    assert s["window_title"] == "Maple"
    assert s["idle_cutoff_s"] == 90


def test_corrupt_settings_gives_defaults(tmp_path):
    p = tmp_path / "s.json"
    p.write_text("{not json")
    assert load_settings(p) == DEFAULTS


def test_data_dir_mac(monkeypatch, tmp_path):
    monkeypatch.setattr("sys.platform", "darwin")
    monkeypatch.setenv("HOME", str(tmp_path))
    want = tmp_path / "Library/Application Support/MapleLens"
    assert data_dir() == want
    assert want.is_dir()


def test_data_dir_windows(monkeypatch, tmp_path):
    monkeypatch.setattr("sys.platform", "win32")
    monkeypatch.setenv("APPDATA", str(tmp_path))
    assert data_dir() == tmp_path / "MapleLens"
