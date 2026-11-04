from pathlib import Path

import cv2
import numpy as np
import pytest

from maplelens.readers import ExpValue, glyphs
from maplelens.readers.exp import EXP_DX, EXP_W, read_exp
from maplelens.readers.level import LV_DX, LV_DY, LV_H, LV_INK_HI, LV_INK_LO, LV_W, read_level

SCREENS = Path(__file__).parent / "fixtures" / "screens"

# One entry per fixture file; None where the value is covered. Fixtures are crops of
# frames already passed through glyphs.normalize. A new resolution = new files + entries.
EXPECTED = {
    "exp_a_2560x1440_100.png": ExpValue(13616, 39.67),
    "exp_b_2560x1440_100.png": ExpValue(20297, 59.14),
    "exp_c_2560x1440_100.png": ExpValue(20842, 60.73),
    "exp_d_2560x1440_100.png": ExpValue(20472, 59.65),
    "exp_covered_2560x1440_100.png": None,  # inventory window over the EXP text
    "level_a_2560x1440_100.png": 23,
    "level_covered_2560x1440_100.png": None,  # grey rectangle pasted over the digits
    "exp_a_1366x768_100.png": ExpValue(29183, 85.03),
    "exp_b_1366x768_100.png": ExpValue(30000, 87.41),
    "exp_c_1366x768_100.png": ExpValue(30684, 89.41),
    "exp_d_1366x768_100.png": ExpValue(29257, 85.25),
    "exp_covered_1366x768_100.png": None,  # grey rectangle pasted over the value
    "level_a_1366x768_100.png": 23,
    "level_covered_1366x768_100.png": None,  # grey rectangle pasted over the digits
    "exp_a_1920x1080_100.png": ExpValue(33764, 98.38),
    "exp_b_1920x1080_100.png": ExpValue(34214, 99.69),  # last frame before the level-up
    "exp_c_1920x1080_100.png": ExpValue(2, 0.0),  # first frame after it
    "exp_d_1920x1080_100.png": ExpValue(409, 1.01),
    "exp_e_1920x1080_100.png": ExpValue(33133, 96.54),
    "exp_f_1920x1080_100.png": ExpValue(506, 1.25),
    "exp_covered_1920x1080_100.png": None,  # grey rectangle pasted over the value
    "level_a_1920x1080_100.png": 23,
    "level_b_1920x1080_100.png": 24,
    "level_covered_1920x1080_100.png": None,  # grey rectangle pasted over the digits
}


def screen(name: str):
    return cv2.imread(str(SCREENS / name), cv2.IMREAD_COLOR)


@pytest.fixture(autouse=True)
def fresh_cache():
    glyphs.clear_cache()


@pytest.mark.parametrize("name", sorted(p.name for p in SCREENS.glob("exp_*.png")))
def test_read_exp(name):
    assert read_exp(screen(name)) == EXPECTED[name]


@pytest.mark.parametrize("name", sorted(p.name for p in SCREENS.glob("level_*.png")))
def test_read_level(name):
    assert read_level(screen(name)) == EXPECTED[name]


def test_exp_partial_text_is_none():
    img = screen("exp_a_2560x1440_100.png")
    x, _ = glyphs.find_anchor(img, "exp_label")
    x0 = x + EXP_DX
    img[:, x0 + int(EXP_W * 0.7) : x0 + EXP_W] = 0
    assert read_exp(img) is None


def _eight(g):
    """A '3' glyph mask turned into an '8': left strokes on rows 2 and 4, full middle bar."""
    g = g.copy()
    g[2, :2], g[4, :2], g[3] = g[1, :2], g[5, :2], g[0]
    return g


def _three_plus_two_px(g):
    """A '3' with its upper-left stroke filled in: 2 px off, nearer a '9' than a '3'."""
    g = g.copy()
    g[2, :2] = g[1, :2]
    return g


@pytest.mark.parametrize(
    "name", [n for n, v in EXPECTED.items() if n.startswith("level_") and v == 23]
)
@pytest.mark.parametrize("change", [_eight, _three_plus_two_px])
def test_level_digit_without_template_is_none(name, change):
    """Only 2 and 3 have templates: a level 28 must read None, never 23."""
    img = screen(name)
    x, y = glyphs.find_anchor(img, "lv_label")
    x, y = x + LV_DX, y + LV_DY
    box = img[y : y + LV_H, x : x + LV_W]
    m = glyphs.mask(box, LV_INK_LO, LV_INK_HI)
    cols = np.flatnonzero(m.any(axis=0))
    gx = cols[np.flatnonzero(np.diff(cols) > 1)[-1] + 1]  # left edge of the last glyph, the 3
    gy = np.flatnonzero(m[:, gx:].any(axis=1))[0]
    g = m[gy : gy + 7, gx : gx + 7]
    box[gy : gy + 7, gx : gx + 7][change(g) & ~g] = 255
    assert read_level(img) is None
