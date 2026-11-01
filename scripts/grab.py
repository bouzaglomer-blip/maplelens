"""Save full-frame screenshots of the game window for building/testing readers.

No args: list visible window titles.
--title T --label L: grab that window once to <data dir>/grabs/L_WxH.png
Add --every S --minutes M: one grab every S seconds for M minutes,
saved as L_NNN_WxH.png. Ctrl+C stops cleanly.
"""

import argparse
import sys
import time
from pathlib import Path

import cv2

from maplelens.capture import (
    client_rect,
    find_window,
    grab,
    list_windows,
    set_dpi_aware,
    window_title,
)
from maplelens.store import data_dir, load_settings, save_settings


def _save(frame, out_dir: Path, name: str) -> tuple[Path, float]:
    h, w = frame.shape[:2]
    out = out_dir / name.format(size=f"{w}x{h}")
    # imencode + write_bytes: imwrite fails silently on non-ASCII paths
    out.write_bytes(cv2.imencode(".png", frame)[1].tobytes())
    return out, float(frame.mean())


def _remember_title(title: str) -> None:
    path = data_dir() / "settings.json"
    settings = load_settings(path)
    settings["window_title"] = title
    save_settings(path, settings)


def _auto(args, out_dir: Path) -> int:
    end = time.monotonic() + args.minutes * 60
    n = black = 0
    try:
        while time.monotonic() < end:
            hwnd = find_window(args.title)
            rect = client_rect(hwnd) if hwnd is not None else None
            if rect is None:
                print("skipped: window missing or minimized")
            else:
                if n == 0:
                    print(f"matched window: {window_title(hwnd)}")
                    _remember_title(args.title)
                n += 1
                out, mean = _save(grab(rect), out_dir, f"{args.label}_{n:03d}_{{size}}.png")
                print(f"{out}  mean brightness {mean:.1f}")
                if mean < 5:
                    black += 1
                    print("capture returned a black frame - tell the developer")
            time.sleep(args.every)
    except KeyboardInterrupt:
        print("stopped")
    print(f"saved {n} frames, {black} black")
    return 1 if black else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--title")
    ap.add_argument("--label")
    ap.add_argument("--every", type=float, help="auto mode: seconds between grabs")
    ap.add_argument("--minutes", type=float, help="auto mode: total duration")
    args = ap.parse_args()
    if bool(args.title) != bool(args.label):
        ap.error("--title and --label go together")
    if (args.every is None) != (args.minutes is None):
        ap.error("--every and --minutes go together")
    if args.every is not None and (args.every <= 0 or args.minutes <= 0):
        ap.error("--every and --minutes must be positive")
    if args.every is not None and not args.title:
        ap.error("--every/--minutes need --title and --label")
    set_dpi_aware()
    if not args.title:
        print("\n".join(list_windows()))
        return 0
    out_dir = data_dir() / "grabs"
    out_dir.mkdir(exist_ok=True)
    if args.every is not None:
        return _auto(args, out_dir)  # window may appear later; missing ticks are skipped
    hwnd = find_window(args.title)
    if hwnd is None:
        print(f"no visible window with '{args.title}' in its title", file=sys.stderr)
        return 1
    print(f"matched window: {window_title(hwnd)}")
    rect = client_rect(hwnd)
    if rect is None:
        print("window is minimized or gone", file=sys.stderr)
        return 1
    _remember_title(args.title)
    out, mean = _save(grab(rect), out_dir, f"{args.label}_{{size}}.png")
    print(f"{out}  mean brightness {mean:.1f}")
    if mean < 5:
        print("capture returned a black frame - tell the developer")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
