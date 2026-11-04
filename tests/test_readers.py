from pathlib import Path

import cv2
import numpy as np
import pytest

from maplelens.readers import ExpValue, Reading, glyphs, job, map_name, ocr, read_all
from maplelens.readers.exp import EXP_DX, EXP_DY, EXP_H, EXP_INK_HI, EXP_INK_LO, EXP_W, read_exp
from maplelens.readers.job import JOB_DX, JOB_DY, JOB_H, read_job
from maplelens.readers.level import LV_DX, LV_DY, LV_H, LV_INK_HI, LV_INK_LO, LV_W, read_level
from maplelens.readers.map_name import read_map_name
from maplelens.readers.minimap_pos import read_player, read_view

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
    # Job crops: LV label + class line; the name line below is painted over.
    "job_a_2560x1440_100.png": "Rogue",
    "job_a_1366x768_100.png": "Rogue",
    "job_a_1920x1080_100.png": "Rogue",
    "job_covered_2560x1440_100.png": None,  # grey rectangle pasted over the class line
    "job_covered_1366x768_100.png": None,  # grey rectangle pasted over the class line
    "job_covered_1920x1080_100.png": None,  # grey rectangle pasted over the class line
    # Minimap crops: title bar + title lines only, never the map area.
    "minimap_a_2560x1440_100.png": "Victoria Road / Kerning City",
    "minimap_b_2560x1440_100.png": "Victoria Road / Construction Site North of Kerning City",
    "minimap_c_2560x1440_100.png": "Victoria Road / Sunset Sky",
    "minimap_d_2560x1440_100.png": "Victoria Road / Perion",
    "minimap_e_2560x1440_100.png": "Victoria Road / Lith Harbor",
    "minimap_f_2560x1440_100.png": "Victoria Road / Henesys",
    "minimap_g_2560x1440_100.png": "Victoria Road / Henesys Townstreet",
    "minimap_h_2560x1440_100.png": "Warning Street / The Swamp of Despair I",
    "minimap_i_2560x1440_100.png": "Kerning City Subway / Line 1 <Area 1>",
    "minimap_j_2560x1440_100.png": "Kerning City Subway / Transfer Area",
    "minimap_bar_a_2560x1440_100.png": "Victoria Road / Thieves' Hideout",
    "minimap_bar_b_2560x1440_100.png": "Victoria Road / Subway Ticketing Booth",
    "minimap_bar_c_2560x1440_100.png": "Victoria Road / Perion Department Store",
    "minimap_covered_2560x1440_100.png": None,  # inventory window over the title lines
    "minimap_nominimap_2560x1440_100.png": None,  # game scene pasted over the minimap
    "minimap_a_1366x768_100.png": "Kerning City Subway / Transfer Area",
    "minimap_a_1920x1080_100.png": "Kerning City Subway / Transfer Area",
}

# Player position fixtures: the whole minimap panel, map area included; other players'
# markers painted out. Values: the dot's centre as fractions of the map area, measured
# by hand (map area = the opaque map picture, centred on see-through padding).
EXPECTED_POS = {
    "pos_a_1920x1080_100.png": (0.482, 0.626),  # Transfer Area, map narrower than window
    "pos_b_2560x1440_100.png": (0.392, 0.229),  # Construction Site North, long title
    "pos_c_2560x1440_100.png": (0.552, 0.661),  # Henesys Townstreet, small map
    "pos_d_1366x768_100.png": (0.518, 0.626),  # Transfer Area, native pixels
    "pos_e_2560x1440_100.png": (0.500, 0.795),  # Lith Harbor, map as wide as the window
    "pos_f_2560x1440_100.png": (0.305, 0.777),  # Perion, map taller than the window
    "pos_bar_2560x1440_100.png": None,  # minimap minimized to its bar
    "pos_covered_2560x1440_100.png": None,  # inventory window over the map area
    "pos_nominimap_1920x1080_100.png": None,  # game scene, no minimap
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


def _three_plus_two_px(g):
    """A '3' with its upper-left stroke filled in: 2 px off, nearer a '9' than a '3'."""
    g = g.copy()
    g[2, :2] = g[1, :2]
    return g


@pytest.mark.parametrize(
    "name", [n for n, v in EXPECTED.items() if n.startswith("level_") and v == 23]
)
def test_level_digit_2px_off_is_none(name):
    """A digit 2 px off every template reads None, never a neighbouring digit."""
    img = screen(name)
    x, y = glyphs.find_anchor(img, "lv_label")
    x, y = x + LV_DX, y + LV_DY
    box = img[y : y + LV_H, x : x + LV_W]
    m = glyphs.mask(box, LV_INK_LO, LV_INK_HI)
    cols = np.flatnonzero(m.any(axis=0))
    gx = cols[np.flatnonzero(np.diff(cols) > 1)[-1] + 1]  # left edge of the last glyph, the 3
    gy = np.flatnonzero(m[:, gx:].any(axis=1))[0]
    g = m[gy : gy + 7, gx : gx + 7]
    box[gy : gy + 7, gx : gx + 7][_three_plus_two_px(g) & ~g] = 255
    assert read_level(img) is None


SPRITES = Path(__file__).parent.parent / "scripts" / "level_sprites"


@pytest.mark.parametrize("d", "0123456789")
def test_level_reads_every_digit(d):
    """At 1366x768 the game draws the digit images 1:1: each one put in the ones box of
    a level 23 reads as 2<d>."""
    img = screen("level_a_1366x768_100.png")
    three = cv2.imread(str(SPRITES / "3.png"), cv2.IMREAD_UNCHANGED)
    sp = cv2.imread(str(SPRITES / f"{d}.png"), cv2.IMREAD_UNCHANGED)
    opaque = three[..., 3] == 255
    res = cv2.matchTemplate(img, np.ascontiguousarray(three[..., :3]), cv2.TM_SQDIFF)
    _, _, (bx, by), _ = cv2.minMaxLoc(res)
    box = img[by : by + 13, bx : bx + 11]
    box[opaque] = sp[..., :3][opaque]
    assert read_level(img) == int(f"2{d}")


def test_expected_matches_fixture_files():
    assert set(EXPECTED) | set(EXPECTED_POS) == {p.name for p in SCREENS.glob("*.png")}


def test_exp_one_px_noise_is_never_another_value():
    """R17: flip each pixel of an '8' (1366 look); the read is None or the true value."""
    name = "exp_a_1366x768_100.png"
    img = screen(name)
    x, y = glyphs.find_anchor(img, "exp_label")
    x, y = x + EXP_DX, y + EXP_DY
    m = glyphs.mask(img[y : y + EXP_H, x : x + EXP_W], EXP_INK_LO, EXP_INK_HI)
    eight = next(t for c, t in glyphs._font("exp_font") if c == "8" and t.shape[1] < 7)
    th, tw = eight.shape
    gy, gx = next(
        (r, c)
        for r in range(m.shape[0] - th + 1)
        for c in range(m.shape[1] - tw + 1)
        if (m[r : r + th, c : c + tw] == eight).all()
    )
    for yy in range(y + gy, y + gy + th):
        for xx in range(x + gx, x + gx + tw):
            out = img.copy()
            out[yy, xx] = (0, 0, 0) if m[yy - y, xx - x] else (255, 255, 255)
            assert read_exp(out) in (None, EXPECTED[name]), (xx, yy)


needs_ocr = pytest.mark.skipif(ocr.engine() is None, reason="no Windows OCR engine")


def test_crop_maps_the_normalized_box_onto_the_native_shot():
    img = screen("minimap_a_1366x768_100.png")
    native = cv2.resize(img, None, fx=2, fy=2, interpolation=cv2.INTER_NEAREST)
    box = (40, 18, 120, 31)
    want = ocr.crop(img, img, box).astype(int)
    got = ocr.crop(img, native, box)
    assert got.shape == want.shape
    assert np.abs(got - want).mean() < 8  # a 1-px shift gives about 18
    assert np.abs(ocr.crop(img, native, (41, 18, 120, 31)) - want).mean() > 15


def test_read_lines_without_engine_is_none(monkeypatch):
    monkeypatch.setattr(ocr, "engine", lambda: None)
    assert ocr.read_lines(np.ones((5, 5), bool)) is None


@needs_ocr
def test_read_lines_empty_mask_has_no_lines():
    assert ocr.read_lines(np.zeros((30, 90), bool)) == []


@needs_ocr
@pytest.mark.parametrize("name", sorted(p.name for p in SCREENS.glob("job_*.png")))
def test_read_job(name):
    assert read_job(screen(name)) == EXPECTED[name]


@needs_ocr
@pytest.mark.parametrize("name", sorted(p.name for p in SCREENS.glob("minimap_*.png")))
def test_read_map_name(name):
    assert read_map_name(screen(name)) == EXPECTED[name]


@pytest.mark.parametrize(
    "lines, want",
    [
        (["Rogue"], "Rogue"),
        (["Roque"], "Rogue"),
        (["Xyzzy"], None),
        (["Chief"], None),  # "Chief Bandit" with a word dropped, not "Thief"
        (["Herm"], None),  # "Hermit" cut short
        (["Mage (Fire, Poison)"], "Mage (Fire, Poison)"),
        (["Mage (Fire, Poisn)"], "Mage (Fire, Poison)"),
        (["Night", "Lord"], "Night Lord"),
        ([], None),
        (None, None),
    ],
)
def test_job_snaps_to_known_job(monkeypatch, lines, want):
    monkeypatch.setattr(job.ocr, "read_lines", lambda m: lines)
    assert read_job(screen("job_a_1366x768_100.png")) == want


@pytest.mark.parametrize(
    "name, lines, want",
    [
        ("minimap_a_1366x768_100.png", ["A b", "C"], "A b / C"),
        ("minimap_a_1366x768_100.png", ["A b"], None),
        ("minimap_a_1366x768_100.png", ["A", "B", "C"], None),
        ("minimap_a_1366x768_100.png", ["A", "B\ufffd"], None),
        ("minimap_a_1366x768_100.png", ["A", "B\x07"], None),
        ("minimap_a_1366x768_100.png", None, None),
        ("minimap_bar_a_2560x1440_100.png", ["A b : C"], "A b / C"),
        ("minimap_bar_a_2560x1440_100.png", ["A b :", "C"], "A b / C"),
        ("minimap_bar_a_2560x1440_100.png", ["A b C"], None),
        ("minimap_bar_a_2560x1440_100.png", ["A : b : C"], None),
        ("minimap_bar_a_2560x1440_100.png", [": C"], None),
    ],
)
def test_map_name_from_ocr_lines(monkeypatch, name, lines, want):
    monkeypatch.setattr(map_name.ocr, "read_lines", lambda m: lines)
    assert read_map_name(screen(name)) == want


def _job_box(img):
    x, y = glyphs.find_anchor(img, "lv_label")
    return x + JOB_DX, y + JOB_DY


def _flips(img, x0, y0, x1, y1, on, off):
    """Copies of img, each with one pixel in the box flipped: ink -> `off`, else -> `on`."""
    for yy in range(y0, y1):
        for xx in range(x0, x1):
            out = img.copy()
            out[yy, xx] = off if (img[yy, xx] == on).all() or img[yy, xx].min() >= 128 else on
            yield out


@needs_ocr
def test_job_one_px_noise_is_never_another_job():
    name = "job_a_2560x1440_100.png"
    img = screen(name)
    x, y = _job_box(img)
    # Every pixel of the word "Rogue" (5 glyphs, about 37 px wide).
    for out in _flips(img, x, y, x + 40, y + JOB_H, on=(255, 255, 255), off=(60, 60, 60)):
        assert read_job(out) in (None, "Rogue")


@needs_ocr
def test_map_one_px_noise_is_never_another_name():
    name = "minimap_a_2560x1440_100.png"
    img = screen(name)
    # The "K" of "Kerning City": normal-form name line, normalized coordinates.
    for out in _flips(img, 48, 43, 58, 54, on=(255, 255, 255), off=(204, 187, 153)):
        assert read_map_name(out) in (None, EXPECTED[name])


def test_read_all_normalizes_once(monkeypatch):
    from maplelens.readers import exp, job, level, map_name

    seen, calls = [], []
    real = glyphs.normalize
    monkeypatch.setattr(glyphs, "normalize", lambda f: calls.append(1) or real(f))
    for mod, fn, value in [
        (exp, "read_exp", ExpValue(1, 0.5)),
        (level, "read_level", 7),
        (job, "read_job", "Rogue"),
        (map_name, "read_map_name", "A / B"),
    ]:
        monkeypatch.setattr(
            mod, fn, lambda *frames, v=value: seen.append([f.shape for f in frames]) or v
        )
    got = read_all(np.zeros((1440, 2560, 3), np.uint8), 12.5)
    assert got == Reading(12.5, ExpValue(1, 0.5), 7, "Rogue", "A / B")
    assert calls == [1]
    # The word readers (OCR) also get the native frame: they crop their text from it.
    small, native = (768, 1365, 3), (1440, 2560, 3)
    assert seen == [[small], [small], [small, native], [small, native]]


@pytest.mark.parametrize("name", sorted(p.name for p in SCREENS.glob("pos_*.png")))
def test_read_player(name):
    got, want = read_player(screen(name)), EXPECTED_POS[name]
    if want is None:
        assert got is None
    else:
        assert got is not None
        assert abs(got[0] - want[0]) <= 0.02 and abs(got[1] - want[1]) <= 0.02, got


@pytest.mark.parametrize(
    "name, n",
    [
        ("pos_a_1920x1080_100.png", 0),  # Transfer Area has no NPCs
        ("pos_c_2560x1440_100.png", 1),  # Henesys Townstreet
        ("pos_e_2560x1440_100.png", 5),  # Lith Harbor: 6 shown, 1 hit by the inpainting
    ],
)
def test_read_view_npc_markers(name, n):
    view = read_view(screen(name))
    assert len(view.npcs) == n
    assert read_player(screen(name)) == (view.dot[0] / view.size[0], view.dot[1] / view.size[1])


# The minimap's other markers, BGR, sampled from the owner's grabs.
OTHER_DOTS = [
    (0, 0, 255),  # other player (red)
    (0, 142, 254),  # party member (orange)
    (3, 222, 241),  # the party marker's "+" (yellow-orange)
    (70, 104, 255),  # faded player dot (salmon)
    (255, 221, 17),  # cyan player dot
    (0, 228, 0),  # NPC (green)
    (165, 192, 8),  # portal spiral (blue)
    (226, 0, 226),  # magenta NPC
    (221, 255, 0),  # cyan triangle
]


def test_read_player_ignores_other_dots():
    """The dot, recoloured to each other marker and pasted elsewhere, changes nothing."""
    img = screen("pos_a_1920x1080_100.png")
    want = read_player(img)
    assert want is not None
    # The "you" dot with its ring (dot pixels x 82..87, y 141..146 in this fixture).
    patch = img[138:150, 79:91].copy()
    fill = glyphs.mask(patch, (25, 180, 200), (110, 255, 255))
    spots = [(25, 80), (60, 80), (120, 80), (140, 100), (30, 120), (100, 120), (30, 160)]
    spots += [(120, 160), (60, 170)]
    for colour, (x, y) in zip(OTHER_DOTS, spots, strict=True):
        dot = patch.copy()
        dot[fill] = colour
        img[y : y + 12, x : x + 12] = dot
    assert read_player(img) == want


def test_read_player_two_you_dots_is_none():
    """A second dot-shaped yellow blob (e.g. map art): no guessing which one is you."""
    img = screen("pos_a_1920x1080_100.png")
    assert read_player(img) is not None
    img[80:92, 25:37] = img[138:150, 79:91].copy()  # the dot and its ring, top-left of the map
    assert read_player(img) is None


def test_read_player_window_over_map_edge_is_none():
    """A window over the map's edge and the frame, dot still visible: the map area is
    unknown, so no position rather than a wrong one."""
    img = screen("pos_a_1920x1080_100.png")
    img[150:199, 0:60] = (200, 200, 200)
    assert read_player(img) is None


def test_read_all_fills_player():
    frame = np.zeros((768, 1366, 3), np.uint8)
    fixture = screen("pos_a_1920x1080_100.png")
    frame[: fixture.shape[0], : fixture.shape[1]] = fixture
    got = read_all(frame, 1.0)
    assert got.player is not None
    assert got.player == read_player(frame)
