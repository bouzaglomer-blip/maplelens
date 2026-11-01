"""Save a full-frame screenshot of the game window for building/testing readers.

No args: list visible window titles.
--title SUBSTR --label NAME: grab that window to <data dir>/grabs/NAME_WxH.png
"""

import argparse
import sys

import cv2

from maplelens.capture import client_rect, find_window, grab, list_windows, set_dpi_aware
from maplelens.store import data_dir, load_settings, save_settings


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--title")
    ap.add_argument("--label")
    args = ap.parse_args()
    set_dpi_aware()
    if not (args.title and args.label):
        print("\n".join(list_windows()))
        return 0
    hwnd = find_window(args.title)
    if hwnd is None:
        print(f"no visible window with '{args.title}' in its title", file=sys.stderr)
        return 1
    rect = client_rect(hwnd)
    if rect is None:
        print("window is minimized or gone", file=sys.stderr)
        return 1
    settings_path = data_dir() / "settings.json"
    settings = load_settings(settings_path)
    settings["window_title"] = args.title
    save_settings(settings_path, settings)
    frame = grab(rect)
    out_dir = data_dir() / "grabs"
    out_dir.mkdir(exist_ok=True)
    h, w = frame.shape[:2]
    out = out_dir / f"{args.label}_{w}x{h}.png"
    # imencode + write_bytes: imwrite fails silently on non-ASCII paths
    out.write_bytes(cv2.imencode(".png", frame)[1].tobytes())
    mean = float(frame.mean())
    print(f"{out}  mean brightness {mean:.1f}")
    if mean < 5:
        print("capture returned a black frame - tell the developer")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
