"""macOS: find the game window and grab its pixels. Window geometry and screen capture only."""

import functools

import numpy as np
import Quartz
from AppKit import NSMakeRect, NSScreen, NSWindow, NSWindowStyleMaskTitled

from maplelens.capture import pick_window


def set_dpi_aware() -> None:
    pass  # nothing to do on macOS


def window_entries(infos: list[dict]) -> list[tuple[int, str]]:
    """One (id, text) per window title and per owner name, front to back."""
    found: list[tuple[int, str]] = []
    for info in infos:
        for key in ("kCGWindowName", "kCGWindowOwnerName"):
            if info.get(key):
                found.append((info["kCGWindowNumber"], info[key]))
    return found


def _infos() -> list[dict]:
    opts = Quartz.kCGWindowListOptionOnScreenOnly
    return list(Quartz.CGWindowListCopyWindowInfo(opts, Quartz.kCGNullWindowID) or [])


def _windows() -> list[tuple[int, str]]:
    return window_entries(_infos())


def list_windows() -> list[str]:
    out = []
    for i in _infos():
        owner, name = i.get("kCGWindowOwnerName"), i.get("kCGWindowName")
        if owner or name:
            out.append(f"{owner} — {name}" if owner and name else owner or name)
    return out


def find_window(title: str) -> int | None:
    return pick_window(_windows(), title)


def window_title(wid: int) -> str:
    return next((t for h, t in _windows() if h == wid), "")


def client_rect_from(
    bounds: dict, onscreen: bool, title_pt: float, scale: float
) -> tuple[int, int, int, int] | None:
    """Window bounds in points -> client area (left, top, width, height) in pixels."""
    h = bounds["Height"] - title_pt
    if not onscreen or h <= 0 or bounds["Width"] <= 0:
        return None
    return (
        round(bounds["X"] * scale),
        round((bounds["Y"] + title_pt) * scale),
        round(bounds["Width"] * scale),
        round(h * scale),
    )


@functools.cache
def _title_bar_pt() -> float:
    frame = NSWindow.frameRectForContentRect_styleMask_(
        NSMakeRect(0, 0, 100, 100), NSWindowStyleMaskTitled
    )
    return frame.size.height - 100


def _screen_at(x: float, y: float):
    """NSScreen holding the CG point (x, y): CG has a top-left origin, NSScreen bottom-left."""
    screens = NSScreen.screens()
    ny = screens[0].frame().size.height - y
    for s in screens:
        f = s.frame()
        if (
            f.origin.x <= x < f.origin.x + f.size.width
            and f.origin.y < ny <= f.origin.y + f.size.height
        ):
            return s
    return NSScreen.mainScreen()


def client_rect(wid: int) -> tuple[int, int, int, int] | None:
    infos = Quartz.CGWindowListCopyWindowInfo(Quartz.kCGWindowListOptionIncludingWindow, wid)
    info = next((i for i in infos or [] if i["kCGWindowNumber"] == wid), None)
    if info is None:
        return None
    b = info["kCGWindowBounds"]
    screen = _screen_at(b["X"] + 1, b["Y"] + 1)
    f = screen.frame()
    borderless = b["Width"] == f.size.width and b["Height"] == f.size.height
    return client_rect_from(
        b,
        bool(info.get("kCGWindowIsOnscreen")),
        0 if borderless else _title_bar_pt(),
        screen.backingScaleFactor(),
    )


def grab(wid: int, rect: tuple[int, int, int, int]) -> np.ndarray:
    img = Quartz.CGWindowListCreateImage(
        Quartz.CGRectNull,
        Quartz.kCGWindowListOptionIncludingWindow,
        wid,
        Quartz.kCGWindowImageBoundsIgnoreFraming,
    )
    if img is None:
        raise RuntimeError("window capture failed")
    w, h = Quartz.CGImageGetWidth(img), Quartz.CGImageGetHeight(img)
    srgb = Quartz.CGColorSpaceCreateWithName(Quartz.kCGColorSpaceSRGB)  # readers expect sRGB
    ctx = Quartz.CGBitmapContextCreate(None, w, h, 8, w * 4, srgb, Quartz.kCGImageAlphaNoneSkipLast)
    Quartz.CGContextDrawImage(ctx, Quartz.CGRectMake(0, 0, w, h), img)
    buf = Quartz.CGBitmapContextGetData(ctx).as_buffer(w * h * 4)
    rgb = np.frombuffer(buf, np.uint8).reshape(h, w, 4)[:, :, :3]
    # cut the title bar (top rows) and anything right of the client area
    return np.ascontiguousarray(rgb[h - rect[3] :, : rect[2], ::-1])


def ensure_access() -> bool:
    if Quartz.CGPreflightScreenCaptureAccess():
        return True
    Quartz.CGRequestScreenCaptureAccess()
    print(
        "MapleLens needs Screen Recording permission to read the game window. It captures\n"
        "only that window's pixels, nothing else.\n"
        "macOS grants it to the app that started MapleLens (for example Terminal): allow it\n"
        "in System Settings > Privacy & Security > Screen & System Audio Recording,\n"
        "then run MapleLens again."
    )
    return False
