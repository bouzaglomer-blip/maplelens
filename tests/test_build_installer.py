import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
_spec = importlib.util.spec_from_file_location(
    "build_installer", ROOT / "scripts" / "build_installer.py"
)
build_installer = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build_installer)


def test_freeze_only_runs_pyinstaller_on_the_spec():
    calls = []
    assert build_installer.main(["--freeze-only"], run=calls.append) == 0
    [cmd] = calls
    assert cmd[1:3] == ["-m", "PyInstaller"]
    assert str(ROOT / "packaging" / "windows" / "maplelens.spec") in cmd
    assert cmd[cmd.index("--distpath") + 1] == str(ROOT / "dist")
    assert cmd[cmd.index("--workpath") + 1] == str(ROOT / "build")


def test_spec_file_exists():
    assert (ROOT / "packaging" / "windows" / "maplelens.spec").is_file()


def test_full_build_not_available_yet():
    with pytest.raises(SystemExit, match="--freeze-only"):
        build_installer.main([], run=lambda cmd: None)
