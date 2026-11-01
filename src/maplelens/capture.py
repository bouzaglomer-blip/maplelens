"""Find the game window and grab its pixels. Window geometry and screen capture only."""

import ctypes
from ctypes import wintypes

import mss
import numpy as np

user32 = ctypes.windll.user32
_ENUM_PROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
user32.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.IsIconic.argtypes = [wintypes.HWND]
user32.SetProcessDpiAwarenessContext.argtypes = [ctypes.c_void_p]

_PER_MONITOR_AWARE_V2 = -4


def set_dpi_aware() -> None:
    try:
        user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(_PER_MONITOR_AWARE_V2))
    except OSError:
        pass  # Qt may have set it already


def _windows() -> list[tuple[int, str]]:
    found: list[tuple[int, str]] = []

    def visit(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            buf = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(hwnd, buf, 256)
            if buf.value:
                found.append((hwnd, buf.value))
        return True

    user32.EnumWindows(_ENUM_PROC(visit), 0)
    return found


def list_windows() -> list[str]:
    return [title for _, title in _windows()]


def find_window(title: str) -> int | None:
    return next((h for h, t in _windows() if title in t), None)


def client_rect(hwnd: int) -> tuple[int, int, int, int] | None:
    if user32.IsIconic(hwnd):
        return None
    r = wintypes.RECT()
    if not user32.GetClientRect(hwnd, ctypes.byref(r)):
        return None
    origin = wintypes.POINT(0, 0)
    if not user32.ClientToScreen(hwnd, ctypes.byref(origin)):
        return None
    return origin.x, origin.y, r.right, r.bottom


def grab(rect: tuple[int, int, int, int]) -> np.ndarray:
    left, top, w, h = rect
    with mss.mss() as sct:
        shot = sct.grab({"left": left, "top": top, "width": w, "height": h})
    return np.array(shot)[:, :, :3]  # mss gives BGRA; drop alpha
