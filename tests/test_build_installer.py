import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
_spec = importlib.util.spec_from_file_location(
    "build_installer", ROOT / "scripts" / "build_installer.py"
)
build_installer = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build_installer)


@pytest.fixture
def bundle_ok(monkeypatch):
    monkeypatch.setattr(build_installer, "check_bundle", lambda src, bundle: None)


def test_freeze_only_runs_pyinstaller_then_the_self_check(bundle_ok):
    calls = []
    assert build_installer.main(["--freeze-only"], run=calls.append) == 0
    cmd, check = calls
    assert check == [str(ROOT / "dist" / "MapleLens" / "MapleLens.exe"), "--self-check"]
    assert cmd[1:3] == ["-m", "PyInstaller"]
    assert str(ROOT / "packaging" / "windows" / "maplelens.spec") in cmd
    assert cmd[cmd.index("--distpath") + 1] == str(ROOT / "dist")
    assert cmd[cmd.index("--workpath") + 1] == str(ROOT / "build")


def test_spec_file_exists():
    assert (ROOT / "packaging" / "windows" / "maplelens.spec").is_file()


def test_full_build_not_available_yet(bundle_ok):
    with pytest.raises(SystemExit, match="--freeze-only"):
        build_installer.main([], run=lambda cmd: None)


def test_failed_self_check_fails_the_build(bundle_ok):
    def run(cmd):
        if "--self-check" in cmd:
            raise build_installer.subprocess.CalledProcessError(1, cmd)

    with pytest.raises(SystemExit, match="self-check"):
        build_installer.main(["--freeze-only"], run=run)


def _pngs(root, names):
    for n in names:
        (root / n).parent.mkdir(parents=True, exist_ok=True)
        (root / n).write_bytes(b"")


def test_check_bundle_counts_templates_and_minimaps(tmp_path):
    files = ["readers/templates/a.png", "readers/templates/f/1.png", "data/minimaps/m.png"]
    src, bundle = tmp_path / "src", tmp_path / "bundle"
    _pngs(src, files)
    _pngs(bundle, files)
    build_installer.check_bundle(src, bundle)  # same files: fine
    (bundle / "readers/templates/f/1.png").unlink()
    with pytest.raises(SystemExit, match="templates"):
        build_installer.check_bundle(src, bundle)
