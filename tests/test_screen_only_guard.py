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
    assert "bad.py:2: banned system call 'ReadProcessMemory'" in r.stderr
    assert "bad.py:3: banned system call 'SendMessage'" in r.stderr


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
    assert r.returncode == 2 and "half.py:2: banned system call 'OpenProcess'" in r.stderr


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
    assert "bad.py:3: banned system call 'SendMessageTimeout'" in r.stderr
    assert "bad.py:4: banned system call 'PostThreadMessage'" in r.stderr


def test_flags_banned_namespace_by_dotted_prefix(tmp_path):
    f = tmp_path / "bad.py"
    f.write_text(
        "import winrt.windows.ui.input.preview.injection\n"
        "from winrt.windows.ui.input.preview import injection\n"
        "from winrt.windows.ui.input.preview.injection import InputInjector\n"
        '__import__("winrt.windows.ui.input.preview.injection")\n',
        encoding="utf-8",
    )
    r = run_guard(str(f))
    assert r.returncode == 2
    for line in (1, 2, 3, 4):
        assert f"bad.py:{line}: banned import 'winrt.windows.ui.input'" in r.stderr


def test_flags_whole_input_namespace_and_keyword_import(tmp_path):
    f = tmp_path / "bad.py"
    f.write_text(
        "import winrt.windows.ui.input\n"
        "from winrt.windows.ui import input\n"
        'importlib.import_module(name="winrt.windows.ui.input.core")\n',
        encoding="utf-8",
    )
    r = run_guard(str(f))
    assert r.returncode == 2
    for line in (1, 2, 3):
        assert f"bad.py:{line}: banned import 'winrt.windows.ui.input'" in r.stderr


def test_namespace_siblings_not_flagged(tmp_path):
    f = tmp_path / "ok.py"
    f.write_text(
        "from winrt.windows.media.ocr import OcrEngine\n"
        "from winrt.windows.ui import inputx\n"
        "import winrt.windows.ui.inputpane\n",
        encoding="utf-8",
    )
    assert run_guard(str(f)).returncode == 0


def test_flags_banned_package_in_lock(tmp_path):
    lock = tmp_path / "uv.lock"
    lock.write_text(
        '[[package]]\nname = "winrt-windows-media-ocr"\n\n'
        '[[package]]\nname = "WinRT-Windows-UI-Input-Preview-Injection"\n',
        encoding="utf-8",
    )
    r = run_guard(str(lock))
    assert r.returncode == 2
    assert "uv.lock:5: banned package 'WinRT-Windows-UI-Input-Preview-Injection'" in r.stderr
    assert "media-ocr" not in r.stderr


def test_clean_lock_passes(tmp_path):
    lock = tmp_path / "uv.lock"
    lock.write_text('[[package]]\nname = "winrt-windows-media-ocr"\n', encoding="utf-8")
    assert run_guard(str(lock)).returncode == 0


def test_repo_is_clean_from_any_cwd(tmp_path):
    assert run_guard(cwd=tmp_path).returncode == 0


def test_flags_mac_name(tmp_path):
    f = tmp_path / "bad.py"
    f.write_text(
        "Quartz.CGEventPost(0, e)\n"
        "CGEventCreateKeyboardEvent(None, 0, True)\n"
        "task_for_pid(t, p, r)\n"
        "AXUIElementPerformAction(el, a)\n"
        "CGWarpMouseCursorPosition(p)\n"
        "app.activateWithOptions_(0)\n",
        encoding="utf-8",
    )
    r = run_guard(str(f))
    assert r.returncode == 2
    names = [
        "CGEventPost",
        "CGEventCreateKeyboardEvent",
        "task_for_pid",
        "AXUIElementPerformAction",
        "CGWarpMouseCursorPosition",
        "activateWithOptions",
    ]
    for n, name in enumerate(names, 1):
        assert f"bad.py:{n}: banned system call '{name}'" in r.stderr


def test_flags_mac_modules(tmp_path):
    f = tmp_path / "bad.py"
    f.write_text(
        "import ApplicationServices\n"
        "from HIServices import AXUIElementCreateApplication\n"
        "import ScriptingBridge\n"
        "import applescript\n"
        "import appscript\n",
        encoding="utf-8",
    )
    r = run_guard(str(f))
    assert r.returncode == 2
    names = ["ApplicationServices", "HIServices", "ScriptingBridge", "applescript", "appscript"]
    for n, name in enumerate(names, 1):
        assert f"bad.py:{n}: banned import '{name}'" in r.stderr


def test_mac_lookalikes_not_flagged(tmp_path):
    f = tmp_path / "ok.py"
    f.write_text(
        "import Quartz\n"
        "import Vision\n"
        "from AppKit import NSApplication\n"
        "CGWindowListCreateImage(r, o, w, i)\n"
        "CGRequestScreenCaptureAccess()\n"
        "NSApp.activateIgnoringOtherApps_(True)\n",
        encoding="utf-8",
    )
    assert run_guard(str(f)).returncode == 0
