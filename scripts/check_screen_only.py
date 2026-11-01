"""Screen-only guard: fail if code could touch the game client.

MapleLens may only capture pixels and draw its own window. This script flags
imports and Win32 calls that read/write process memory, capture network
traffic, or send input. It is a speed bump against honest mistakes, not a
security boundary.

Usage: python scripts/check_screen_only.py [PATH ...]
With no PATH, scans src/ and scripts/ of this repo. Exits 2 on violations
(2 so a Claude Code hook feeds the report back to the model).
"""

import ast
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SELF = Path(__file__).resolve()

BANNED_MODULES = {
    "pymem",  # reads/writes process memory
    "frida",  # injects into processes
    "scapy",  # packet capture
    "pydivert",  # intercepts network traffic (WinDivert)
    "pyshark",  # packet capture
    "win32process",  # process handles / memory access
    "pywinauto",  # drives other apps' UI (sends input)
    "pyautogui",  # sends keys/clicks
    "pynput",  # sends keys/clicks
    "keyboard",  # sends keys / global hooks
    "mouse",  # sends clicks / global hooks
}

BANNED_WIN32 = [
    "ReadProcessMemory",  # reads game memory
    "WriteProcessMemory",  # writes game memory
    "OpenProcess",  # gets a handle to the game process
    "VirtualAllocEx",  # allocates memory in another process
    "CreateRemoteThread",  # code injection
    "SendInput",  # sends keys/clicks
    "SetWindowsHookEx",  # global input hooks
    "keybd_event",  # sends keys
    "mouse_event",  # sends clicks
    "PostMessage",  # sends input messages to the game window
    "SendMessage",  # sends input messages to the game window
]

WIN32_RE = re.compile(r"\b(" + "|".join(BANNED_WIN32) + r")[AW]?\b")


def find_violations(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    found = []
    try:
        for node in ast.walk(ast.parse(text)):
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names = [node.module]
            else:
                continue
            for name in names:
                top = name.split(".")[0]
                if top in BANNED_MODULES:
                    found.append((node.lineno, f"banned import '{top}'"))
    except SyntaxError:
        pass  # half-written file; the name check below still runs
    for lineno, line in enumerate(text.splitlines(), 1):
        for m in WIN32_RE.finditer(line):
            found.append((lineno, f"banned Win32 call '{m.group(1)}'"))
    return [f"{path}:{lineno}: {msg}" for lineno, msg in sorted(found)]


def iter_py_files(paths: list[Path]):
    for p in paths:
        files = sorted(p.rglob("*.py")) if p.is_dir() else [p]
        for f in files:
            if f.resolve() != SELF:
                yield f


def main(argv: list[str]) -> int:
    paths = [Path(a) for a in argv] or [REPO / "src", REPO / "scripts"]
    violations = [v for f in iter_py_files(paths) for v in find_violations(f)]
    for v in violations:
        print(v, file=sys.stderr)
    if violations:
        print(f"screen-only guard: {len(violations)} violation(s)", file=sys.stderr)
        return 2
    print("screen-only guard: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
