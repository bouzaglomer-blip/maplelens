import subprocess
import sys
from pathlib import Path

GUARD = Path(__file__).resolve().parent.parent / "scripts" / "check_screen_only.py"


def run_guard(*args, cwd=None):
    return subprocess.run(
        [sys.executable, str(GUARD), *args], capture_output=True, text=True, cwd=cwd
    )


def test_flags_banned_import(tmp_path):
    f = tmp_path / "bad.py"
    f.write_text("import pymem\nfrom scapy.all import sniff\nimport frida.core\n", encoding="utf-8")
    r = run_guard(str(f))
    assert r.returncode == 2
    assert "bad.py:1: banned import 'pymem'" in r.stderr
    assert "bad.py:2: banned import 'scapy'" in r.stderr
    assert "bad.py:3: banned import 'frida'" in r.stderr


def test_flags_win32_name(tmp_path):
    f = tmp_path / "bad.py"
    f.write_text("x = 1\nk32.ReadProcessMemory(h)\nuser32.SendMessageW(w)\n", encoding="utf-8")
    r = run_guard(str(f))
    assert r.returncode == 2
    assert "bad.py:2: banned Win32 call 'ReadProcessMemory'" in r.stderr
    assert "bad.py:3: banned Win32 call 'SendMessage'" in r.stderr


def test_clean_file_passes(tmp_path):
    f = tmp_path / "ok.py"
    f.write_text("import json\nfrom pathlib import Path\n", encoding="utf-8")
    assert run_guard(str(f)).returncode == 0


def test_lookalikes_not_flagged(tmp_path):
    f = tmp_path / "ok.py"
    f.write_text(
        "import mousepad\nimport keyboard_layout\nShowSendMessageBox()\n", encoding="utf-8"
    )
    assert run_guard(str(f)).returncode == 0


def test_non_ascii_file_still_checked(tmp_path):
    f = tmp_path / "bad.py"
    f.write_text("# 메이플 ✓\nimport pymem\n", encoding="utf-8")
    r = run_guard(str(f))
    assert r.returncode == 2 and "bad.py:2" in r.stderr


def test_syntax_error_does_not_crash(tmp_path):
    f = tmp_path / "half.py"
    f.write_text("def broken(:\n    OpenProcess(1)\n", encoding="utf-8")
    r = run_guard(str(f))
    assert "Traceback" not in r.stderr
    assert r.returncode == 2 and "half.py:2: banned Win32 call 'OpenProcess'" in r.stderr


def test_directory_arg_walks_py_files(tmp_path):
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "a.py").write_text("import pyautogui\n", encoding="utf-8")
    (tmp_path / "pkg" / "notes.txt").write_text("import pymem\n", encoding="utf-8")
    r = run_guard(str(tmp_path))
    assert r.returncode == 2 and "pyautogui" in r.stderr and "pymem" not in r.stderr


def test_bom_file_still_checked(tmp_path):
    f = tmp_path / "bad.py"
    f.write_bytes(b"\xef\xbb\xbfimport pymem\n")
    r = run_guard(str(f))
    assert r.returncode == 2 and "bad.py:1: banned import 'pymem'" in r.stderr


def test_flags_dynamic_import(tmp_path):
    f = tmp_path / "bad.py"
    f.write_text('importlib.import_module("pymem")\n__import__("frida.core")\n', encoding="utf-8")
    r = run_guard(str(f))
    assert r.returncode == 2
    assert "bad.py:1: banned import 'pymem'" in r.stderr
    assert "bad.py:2: banned import 'frida'" in r.stderr


def test_flags_game_input_libs_and_message_variants(tmp_path):
    f = tmp_path / "bad.py"
    f.write_text(
        "import pydirectinput\nimport ahk\nwin32gui.SendMessageTimeout(h)\nPostThreadMessageW(t)\n",
        encoding="utf-8",
    )
    r = run_guard(str(f))
    assert r.returncode == 2
    assert "bad.py:1: banned import 'pydirectinput'" in r.stderr
    assert "bad.py:2: banned import 'ahk'" in r.stderr
    assert "bad.py:3: banned Win32 call 'SendMessageTimeout'" in r.stderr
    assert "bad.py:4: banned Win32 call 'PostThreadMessage'" in r.stderr


def test_repo_is_clean_from_any_cwd(tmp_path):
    assert run_guard(cwd=tmp_path).returncode == 0
