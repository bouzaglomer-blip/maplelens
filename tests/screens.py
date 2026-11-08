"""Load fixture screenshots (tests/fixtures/screens) as the readers see them."""

import re
from pathlib import Path

import cv2

from maplelens.readers import glyphs

SCREENS = Path(__file__).parent / "fixtures" / "screens"


def raw(name: str):
    """(crop as captured, its top-left in the game window, the window's (w, h)).

    A crop not at 1366x768 carries its top-left in its name: ..._WxH_100_x<X>_y<Y>.png.
    """
    m = re.search(r"_(\d+)x(\d+)_\d+(?:_x(\d+)_y(\d+))?\.png$", name)
    origin = (int(m[3]), int(m[4])) if m[3] else (0, 0)
    return cv2.imread(str(SCREENS / name), cv2.IMREAD_COLOR), origin, (int(m[1]), int(m[2]))


def screen(name: str):
    """The fixture un-stretched to the game's own picture, as read_all hands it on."""
    img, origin, client = raw(name)
    return glyphs.normalize(img, origin, client)
