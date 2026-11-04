"""Character level reader."""

import numpy as np

from maplelens.readers import glyphs

# Digit boxes, relative to the lv_label anchor's top-left (normalized frame).
# Wide enough for three boxes; the class line starts a few px further right.
LV_DX, LV_DY, LV_W, LV_H = 24, 1, 47, 14
# Ink: the light digits; the orange boxes behind them stay below about 60 in blue.
LV_INK_LO, LV_INK_HI = (100, 100, 100), (255, 255, 255)
# Real digits match their templates pixel-exactly at every resolution. Allow 1 px of
# 49, so a digit with no template (an 8 is 5 px from a 3) reads None, not a wrong level.
LEVEL_MAX_DIFF = 0.03
# ponytail: level digits only 2,3 seen (and 4 at 1920x1080);
# add templates from a grab at another level


def parse_level(text: str) -> int | None:
    """Digits only, 1..200, else None."""
    if not (text.isascii() and text.isdigit()):
        return None
    level = int(text)
    return level if 1 <= level <= 200 else None


def read_level(frame: np.ndarray) -> int | None:
    """Character level from a normalized frame, or None if unreadable."""
    hit = glyphs.find_anchor(frame, "lv_label")
    if hit is None:
        return None
    x, y = hit[0] + LV_DX, hit[1] + LV_DY
    m = glyphs.mask(frame[y : y + LV_H, x : x + LV_W], LV_INK_LO, LV_INK_HI)
    text = glyphs.read_text(m, "level_font", space_px=LV_W, max_diff=LEVEL_MAX_DIFF)
    return None if text is None else parse_level(text)
