import math
from pathlib import Path

import cv2
import numpy as np
import pytest
from screens import SCREENS, raw, screen

from maplelens.readers import ExpValue, Reading, glyphs, job, map_name, ocr, read_all, skill_window
from maplelens.readers.exp import EXP_DX, EXP_DY, EXP_H, EXP_INK_HI, EXP_INK_LO, EXP_W, read_exp
from maplelens.readers.job import JOB_DX, JOB_DY, JOB_H, read_job
from maplelens.readers.level import LV_DX, LV_DY, LV_H, LV_INK_HI, LV_INK_LO, LV_W, read_level
from maplelens.readers.map_name import known_titles, read_map_name, snap_title
from maplelens.readers.minimap_pos import read_player, read_view
from maplelens.readers.skill_window import SkillRow, SkillWindow, read_skill_window
from maplelens.readers.stat_window import UNREADABLE, StatWindow, parse_stat, read_stat_window

# One entry per fixture file; None where the value is covered. Fixtures are crops of the
# game window as captured; a crop not at 1366x768 has its top-left in the window in its
# name (_x<X>_y<Y>), and screen() un-stretches it. A new resolution = new files + entries.
EXPECTED = {
    # 16:10: the game's picture is 1228 wide here, not 1366.
    "exp_a_1920x1200_100_x1016_y1145.png": ExpValue(17528, 23.98),
    "level_a_1920x1200_100_x347_y1156.png": 28,
    "job_a_1920x1200_100_x347_y1148.png": "Rogue",
    "minimap_a_1920x1200_100_x0_y0.png": "Kerning City Subway / Line 1 <Area 1>",
    "exp_a_2560x1440_100_x1345_y1373.png": ExpValue(13616, 39.67),
    "exp_b_2560x1440_100_x1345_y1373.png": ExpValue(20297, 59.14),
    "exp_c_2560x1440_100_x1345_y1373.png": ExpValue(20842, 60.73),
    "exp_d_2560x1440_100_x1345_y1373.png": ExpValue(20472, 59.65),
    "exp_covered_2560x1440_100_x1345_y1373.png": None,  # inventory window over the EXP text
    "level_a_2560x1440_100_x544_y1386.png": 23,
    "level_covered_2560x1440_100_x544_y1386.png": None,  # grey rectangle pasted over the digits
    "exp_a_1366x768_100.png": ExpValue(29183, 85.03),
    "exp_b_1366x768_100.png": ExpValue(30000, 87.41),
    "exp_c_1366x768_100.png": ExpValue(30684, 89.41),
    "exp_d_1366x768_100.png": ExpValue(29257, 85.25),
    "exp_covered_1366x768_100.png": None,  # grey rectangle pasted over the value
    "level_a_1366x768_100.png": 23,
    "level_covered_1366x768_100.png": None,  # grey rectangle pasted over the digits
    "exp_a_1920x1080_100_x1008_y1029.png": ExpValue(33764, 98.38),
    "exp_b_1920x1080_100_x1008_y1029.png": ExpValue(34214, 99.69),  # last frame before the level-up
    "exp_c_1920x1080_100_x1008_y1029.png": ExpValue(2, 0.0),  # first frame after it
    "exp_d_1920x1080_100_x1008_y1029.png": ExpValue(409, 1.01),
    "exp_e_1920x1080_100_x1008_y1029.png": ExpValue(33133, 96.54),
    "exp_f_1920x1080_100_x1008_y1029.png": ExpValue(506, 1.25),
    "exp_covered_1920x1080_100_x1008_y1029.png": None,  # grey rectangle pasted over the value
    "level_a_1920x1080_100_x407_y1039.png": 23,
    "level_b_1920x1080_100_x407_y1039.png": 24,
    "level_covered_1920x1080_100_x407_y1039.png": None,  # grey rectangle pasted over the digits
    # Job crops: LV label + class line; the name line below is painted over.
    "job_a_2560x1440_100_x544_y1377.png": "Rogue",
    "job_a_1366x768_100.png": "Rogue",
    "job_a_1920x1080_100_x407_y1032.png": "Rogue",
    "job_covered_2560x1440_100_x544_y1377.png": None,  # grey rectangle pasted over the class line
    "job_covered_1366x768_100.png": None,  # grey rectangle pasted over the class line
    "job_covered_1920x1080_100_x407_y1032.png": None,  # grey rectangle pasted over the class line
    # Minimap crops: title bar + title lines only, never the map area.
    "minimap_a_2560x1440_100_x0_y0.png": "Victoria Road / Kerning City",
    "minimap_b_2560x1440_100_x0_y0.png": "Victoria Road / Construction Site North of Kerning City",
    "minimap_c_2560x1440_100_x0_y0.png": "Victoria Road / Sunset Sky",
    "minimap_d_2560x1440_100_x0_y0.png": "Victoria Road / Perion",
    "minimap_e_2560x1440_100_x0_y0.png": "Victoria Road / Lith Harbor",
    "minimap_f_2560x1440_100_x0_y0.png": "Victoria Road / Henesys",
    "minimap_g_2560x1440_100_x0_y0.png": "Victoria Road / Henesys Townstreet",
    "minimap_h_2560x1440_100_x0_y0.png": "Warning Street / The Swamp of Despair I",
    "minimap_i_2560x1440_100_x0_y0.png": "Kerning City Subway / Line 1 <Area 1>",
    "minimap_j_2560x1440_100_x0_y0.png": "Kerning City Subway / Transfer Area",
    "minimap_bar_a_2560x1440_100_x0_y0.png": "Victoria Road / Thieves' Hideout",
    "minimap_bar_b_2560x1440_100_x0_y0.png": "Victoria Road / Subway Ticketing Booth",
    "minimap_bar_c_2560x1440_100_x0_y0.png": "Victoria Road / Perion Department Store",
    "minimap_covered_2560x1440_100_x0_y0.png": None,  # inventory window over the title lines
    "minimap_nominimap_2560x1440_100_x428_y0.png": None,  # game scene pasted over the minimap
    "minimap_a_1366x768_100.png": "Kerning City Subway / Transfer Area",
    "minimap_a_1920x1080_100_x0_y0.png": "Kerning City Subway / Transfer Area",
}

# Player position fixtures: the whole minimap panel, map area included; other players'
# markers painted out. Values: the dot's centre as fractions of the map area, measured
# by hand (map area = the opaque map picture, centred on see-through padding).
EXPECTED_POS = {
    "pos_a_1920x1080_100_x0_y0.png": (0.482, 0.626),  # Transfer Area, map narrower than window
    "pos_b_2560x1440_100_x0_y0.png": (0.392, 0.229),  # Construction Site North, long title
    "pos_c_2560x1440_100_x0_y0.png": (0.552, 0.661),  # Henesys Townstreet, small map
    "pos_d_1366x768_100.png": (0.518, 0.626),  # Transfer Area, native pixels
    "pos_e_2560x1440_100_x0_y0.png": (0.500, 0.795),  # Lith Harbor, map as wide as the window
    "pos_f_2560x1440_100_x0_y0.png": (0.305, 0.777),  # Perion, map taller than the window
    # The Forest North of Ellinia: 130 px of a 428 px tall picture, hidden portals.
    "pos_fne_bottom_2560x1440_100_x0_y0.png": (0.246, 0.518),
    "pos_fne_mid_2560x1440_100_x0_y0.png": (0.300, 0.446),
    "pos_fne_top_2560x1440_100_x0_y0.png": (0.469, 0.304),
    "pos_fne_bottom_1366x768_100.png": (0.223, 0.830),
    "pos_fne_mid_1366x768_100.png": (0.515, 0.446),  # a monster shows through the minimap
    "pos_fne_top_1366x768_100.png": (0.485, 0.295),
    "pos_tunnel_2560x1440_100_x0_y0.png": (0.493, 0.446),  # Tree Tunnel; a dot painted out
    "pos_bar_2560x1440_100_x0_y0.png": None,  # minimap minimized to its bar
    "pos_covered_2560x1440_100_x0_y0.png": None,  # inventory window over the map area
    "pos_nominimap_1920x1080_100_x250_y137.png": None,  # game scene, no minimap
}

# Stat window crops: the window plus 3 px of margin, as captured. Level 28,
# AP 5, STR 4 / DEX 25 / INT 4 / LUK 122 (+2 gear). `plus`: the single-arrow + button
# centres in the normalized frame, measured at 768 and within 1 px at the other sizes.
_STAT = {
    "level": 28,
    "ap": 5,
    "base": {"STR": 4, "DEX": 25, "INT": 4, "LUK": 122},
    "total": {"STR": 4, "DEX": 25, "INT": 4, "LUK": 124},
}
_PLUS = {"STR": (155, 184), "DEX": (155, 202), "INT": (155, 220), "LUK": (155, 238)}
EXPECTED_STAT = {
    "stat_a_1366x768_100.png": StatWindow(**_STAT, plus=_PLUS),
    "stat_a_1920x1080_100_x826_y21.png": StatWindow(
        **_STAT, plus={k: (x + 1, y) for k, (x, y) in _PLUS.items()}
    ),
    "stat_a_2560x1440_100_x1102_y13.png": StatWindow(**_STAT, plus=_PLUS),
    # A later grab, 16:10: AP 0, LUK 127 (+2 gear).
    "stat_a_1920x1200_100_x548_y353.png": StatWindow(
        28,
        0,
        {"STR": 4, "DEX": 25, "INT": 4, "LUK": 127},
        {"STR": 4, "DEX": 25, "INT": 4, "LUK": 129},
        _PLUS,
    ),
    "stat_covered_1366x768_100.png": UNREADABLE,  # inventory over the left half of the rows
    "stat_edge_1366x768_100.png": None,  # window mostly off the left edge: no anchor found
}

# Skill window crops: the window plus 3 px of margin, as captured. Rogue tab, 3 SP; `plus`: the
# single-arrow + centres in the normalized frame (768 measured, within 1 px elsewhere).
_SKILL_ROWS = (
    (4000000, 15),
    (4000001, 15),
    (4001000, 2),
    (4001001, 0),
    (4001002, 0),
    (4001003, 20),
)
_SKILL = SkillWindow(
    "Rogue", 3, tuple(SkillRow(i, lv, (148, 125 + 40 * n)) for n, (i, lv) in enumerate(_SKILL_ROWS))
)
EXPECTED_SKILL = {
    "skill_a_1366x768_100.png": _SKILL,
    "skill_a_1920x1080_100_x819_y9.png": _SKILL,
    "skill_a_2560x1440_100_x1093_y13.png": _SKILL,
    "skill_a_1920x1200_100_x1313_y297.png": SkillWindow(  # a later grab, 16:10
        "Rogue",
        0,
        tuple(
            SkillRow(i, lv, (148, 125 + 40 * n))
            for n, (i, lv) in enumerate(
                zip((r[0] for r in _SKILL_ROWS), (15, 15, 3, 2, 0, 20), strict=True)
            )
        ),
    ),
    "skill_covered_2560x1440_100_x810_y1.png": UNREADABLE,  # title covered, SKILL POINT shows
    "skill_edge_2560x1440_100_x1027_y1.png": None,  # window mostly off the left edge
}


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
    img = screen("exp_a_2560x1440_100_x1345_y1373.png")
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
    title = {"title_ellinia_1920x1080_100_x0_y0.png"}  # test_map_name_ellinia
    assert set(EXPECTED) | set(EXPECTED_POS) | set(EXPECTED_STAT) | set(EXPECTED_SKILL) | title == {
        p.name for p in SCREENS.glob("*.png")
    }


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


needs_ocr = pytest.mark.skipif(ocr.engine() is None, reason="no OCR engine")


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
        ("minimap_bar_a_2560x1440_100_x0_y0.png", ["A b : C"], "A b / C"),
        ("minimap_bar_a_2560x1440_100_x0_y0.png", ["A b :", "C"], "A b / C"),
        ("minimap_bar_a_2560x1440_100_x0_y0.png", ["A b C"], None),
        ("minimap_bar_a_2560x1440_100_x0_y0.png", ["A : b : C"], None),
        ("minimap_bar_a_2560x1440_100_x0_y0.png", [": C"], None),
    ],
)
def test_map_name_from_ocr_lines(monkeypatch, name, lines, want):
    monkeypatch.setattr(map_name.ocr, "read_lines", lambda m: lines)
    assert read_map_name(screen(name)) == want


V = "Victoria Road / "


@pytest.mark.parametrize(
    "text, want",
    [
        (V + "Sumset Sky", V + "Sunset Sky"),
        (V + "Lithı Harhor", V + "Lith Harbor"),
        (V + "Lith Harlor", V + "Lith Harbor"),
        (
            V + "Construction Site Nortlı of Kerning City",
            V + "Construction Site North of Kerning City",
        ),
        (V + "kerning City", V + "Kerning City"),
        ("Hidden Street / ist Accompaniment <Bonus>", "Hidden Street / 1st Accompaniment <Bonus>"),
        (V + "The Forest North of", V + "The Forest North of Ellinia"),  # last word dropped
    ],
)
def test_snap_misreads(text, want):
    assert snap_title(text, known_titles()) == want


@pytest.mark.parametrize(
    "text, want",
    [
        ("Warning Street / The Swamp of Despair 1", "Warning Street / The Swamp of Despair I"),
        ("Warning Street / The Swamp of Despair 11", "Warning Street / The Swamp of Despair II"),
        ("Warning Street / The Swamp of Despair I", "Warning Street / The Swamp of Despair I"),
        ("Warning Street / The Swamp of Despair II", "Warning Street / The Swamp of Despair II"),
    ],
)
def test_snap_roman_siblings(text, want):
    assert snap_title(text, known_titles()) == want


@pytest.mark.parametrize(
    "text", [V + "Zzyzx Hollow", "A b / C", V + "Tree Dungeon, Forest Up North", V + "The Forest"]
)
def test_snap_unknown_map_keeps_text(text):
    assert snap_title(text, known_titles()) == text


def test_snap_exact_is_kept():
    text = "Kerning City Subway / Line 1 <Area 1>"
    assert snap_title(text, known_titles()) == text


def test_snap_needs_a_lead_over_runner_up():
    # near-tie between <Area 1>/<Area 3> style siblings must stay unsnapped (SNAP_LEAD)
    text = "Kerning City Subway / Line 1 cArea 13"
    assert snap_title(text, known_titles()) == text


def test_map_name_snaps_misreads(monkeypatch):
    monkeypatch.setattr(map_name.ocr, "read_lines", lambda m: ["Victoria Road", "Sumset Sky"])
    assert read_map_name(screen("minimap_a_1366x768_100.png")) == V + "Sunset Sky"


@needs_ocr
def test_map_name_ellinia():
    """Windows OCR has read 'Eflinia' from this title; the snap fixes it."""
    assert read_map_name(screen("title_ellinia_1920x1080_100_x0_y0.png")) == V + "Ellinia"


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
    name = "job_a_2560x1440_100_x544_y1377.png"
    img = screen(name)
    x, y = _job_box(img)
    # Every pixel of the word "Rogue" (5 glyphs, about 37 px wide).
    for out in _flips(img, x, y, x + 40, y + JOB_H, on=(255, 255, 255), off=(60, 60, 60)):
        assert read_job(out) in (None, "Rogue")


@needs_ocr
def test_map_one_px_noise_is_never_another_name():
    name = "minimap_a_2560x1440_100_x0_y0.png"
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
    # Every reader gets just the game's picture: 768 rows, 1366 wide at 16:9.
    assert seen == [[(768, 1366, 3)]] * 4


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
        ("pos_a_1920x1080_100_x0_y0.png", 0),  # Transfer Area has no NPCs
        ("pos_c_2560x1440_100_x0_y0.png", 1),  # Henesys Townstreet
        ("pos_e_2560x1440_100_x0_y0.png", 5),  # Lith Harbor: 6 shown, 1 hit by the inpainting
    ],
)
def test_read_view_npc_markers(name, n):
    view = read_view(screen(name))
    assert len(view.npcs) == n
    assert read_player(screen(name)) == (view.dot[0] / view.size[0], view.dot[1] / view.size[1])


@pytest.mark.parametrize(
    "name, n",
    [
        ("pos_c_2560x1440_100_x0_y0.png", 0),  # Henesys Townstreet: none in view
        ("pos_d_1366x768_100.png", 1),  # Transfer Area, native pixels
        ("pos_e_2560x1440_100_x0_y0.png", 3),  # Lith Harbor: the sea isn't a spiral
        ("pos_f_2560x1440_100_x0_y0.png", 5),  # Perion: 2 more cut by the window's edge
    ],
)
def test_read_view_portal_spirals(name, n):
    assert len(read_view(screen(name)).portals) == n


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
    img = screen("pos_a_1920x1080_100_x0_y0.png")
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
    img = screen("pos_a_1920x1080_100_x0_y0.png")
    assert read_player(img) is not None
    img[80:92, 25:37] = img[138:150, 79:91].copy()  # the dot and its ring, top-left of the map
    assert read_player(img) is None


def test_read_player_window_over_map_edge_is_none():
    """A window over the map's edge and the frame, dot still visible: the map area is
    unknown, so no position rather than a wrong one."""
    img = screen("pos_a_1920x1080_100_x0_y0.png")
    img[150:199, 0:60] = (200, 200, 200)
    assert read_player(img) is None


def test_read_all_fills_player():
    frame = np.zeros((768, 1366, 3), np.uint8)
    fixture = screen("pos_a_1920x1080_100_x0_y0.png")
    frame[: fixture.shape[0], : fixture.shape[1]] = fixture
    got = read_all(frame, 1.0)
    assert got.player is not None
    assert got.player == read_player(frame)
    assert got.minimap is not None and got.minimap == read_view(frame)


def test_mac_vision_request_failure_raises(monkeypatch):
    vision = pytest.importorskip("Vision")
    from maplelens.readers import ocr_mac

    class Failing:
        @classmethod
        def alloc(cls):
            return cls()

        def initWithData_options_(self, data, options):
            return self

        def performRequests_error_(self, requests, error):
            return False, "boom"

    monkeypatch.setattr(vision, "VNImageRequestHandler", Failing)
    with pytest.raises(RuntimeError, match="boom"):
        ocr_mac.recognize(np.full((40, 40), 255, np.uint8))


@pytest.mark.parametrize(
    "text, want",
    [
        ("25", (25, 25)),
        ("124(122+2)", (122, 124)),
        ("4(4+0)", (4, 4)),
        ("25(20+4)", None),
        ("", None),
        ("2a", None),
        ("25(20+", None),
    ],
)
def test_parse_stat(text, want):
    assert parse_stat(text) == want


@pytest.mark.parametrize("name", sorted(p.name for p in SCREENS.glob("stat_*.png")))
def test_read_stat_window(name):
    got, want = read_stat_window(screen(name)), EXPECTED_STAT[name]
    if isinstance(want, StatWindow) and isinstance(got, StatWindow):
        assert (got.level, got.ap, got.base, got.total) == (
            want.level,
            want.ap,
            want.base,
            want.total,
        )
        for k, (x, y) in want.plus.items():
            assert abs(got.plus[k][0] - x) <= 1 and abs(got.plus[k][1] - y) <= 1, (k, got.plus)
    else:
        assert got == want


@pytest.mark.parametrize("name", sorted(p.name for p in SCREENS.glob("exp_a_*.png")))
def test_no_stat_window_reads_none(name):
    assert read_stat_window(screen(name)) is None


@pytest.mark.parametrize(
    "name, ks",
    [
        ("stat_a_2560x1440_100_x1102_y13.png", range(0, 15, 2)),
        ("stat_a_1920x1080_100_x826_y21.png", range(0, 12, 2)),  # to ceil(2s) = 3 frame px
    ],
)
def test_stat_reads_at_every_offset(name, ks):
    """Dropping captured rows and columns moves the window to another sub-pixel offset;
    it still reads, and its + buttons stay on the same pixels of the game's picture."""
    img, (x0, y0), client = raw(name)
    base = read_stat_window(screen(name))
    for k in ks:
        got = read_stat_window(glyphs.normalize(img[k:, k:], (x0 + k, y0 + k), client))
        assert isinstance(got, StatWindow), k
        assert (got.level, got.ap, got.base, got.total) == (
            base.level,
            base.ap,
            base.base,
            base.total,
        )
        dx, dy = _moved(x0, k, 1366, client[0]), _moved(y0, k, 768, client[1])
        assert got.plus == {key: (x - dx, y - dy) for key, (x, y) in base.plus.items()}, k


def _moved(j0, k, n, m):
    """How far the un-stretched crop's first pixel moves when its first k captured pixels
    (of m, from j0) are dropped: n of them are the game's picture."""

    def first(j):
        return math.floor((j + 0.5) * n / m - 0.5)

    return first(j0 + k) - first(j0)


def test_stat_ap_check(monkeypatch):
    from maplelens.readers import stat_window

    img = screen("stat_a_1366x768_100.png")
    assert isinstance(read_stat_window(img), StatWindow)
    real = stat_window.window.read_number_text
    monkeypatch.setattr(
        stat_window.window,
        "read_number_text",
        lambda win, box: "7" if box[0] == stat_window.AP_X else real(win, box),
    )
    assert read_stat_window(img) == UNREADABLE  # 4 + 25 + 4 + 122 + 7 > 25 + 5 * 27


def test_stat_light_overlay_over_a_tail_is_not_read():
    """A light, borderless patch over "(122+2)" must not read as a plain "124" LUK."""
    img = screen("stat_a_1366x768_100.png")
    img[3 + 228 : 3 + 243, 3 + 90 : 3 + 140] = 222  # the LUK strip's tail, field grey
    assert read_stat_window(img) == UNREADABLE


def test_stat_plus_off_frame_is_unreadable():
    """Fields all read, but the frame's right edge cuts through the + buttons."""
    assert read_stat_window(screen("stat_a_1366x768_100.png")[:, :155]) == UNREADABLE


def test_number_text_ambiguous_glyph_is_none(monkeypatch):
    """Two chars that match a glyph about equally: no guess."""
    from maplelens.readers import window

    win = np.full((20, 40, 3), 222, np.uint8)
    g = next(t for c, t in window._glyphs() if c == "8")
    win[3:16, 5 : 5 + g.shape[1]] = g[..., None].astype(np.uint8)
    box = (0, 0, 40, 20)
    assert window.read_number_text(win, box) == "8"
    # An "8" that is mostly a "0": blend the middle row in.
    win[3 + 6, 5:12] = 222
    assert window.read_number_text(win, box) in (None, "0")  # never a confident wrong read
    monkeypatch.setattr(window, "_font", [("8", g), ("B", g)])
    assert window.read_number_text(win, box) is None  # identical scores: no margin


def test_number_text_light_patch_off_the_glyphs_is_none():
    """The background check: a non-ink patch that differs from the field voids the read."""
    from maplelens.readers import window

    win = np.full((20, 40, 3), 222, np.uint8)
    g = next(t for c, t in window._glyphs() if c == "8")
    win[3:16, 5 : 5 + g.shape[1]] = g[..., None].astype(np.uint8)
    box = (0, 0, 40, 20)
    assert window.read_number_text(win, box) == "8"
    win[2:4, 30:36] = 222 - window.BG_TOL - 8  # darker than the field, but above INK
    assert window.read_number_text(win, box) is None


def test_every_known_skill_name_snaps_to_itself():
    from maplelens.readers import skill_window

    names = list(skill_window.known_skills())
    assert [n for n in names if skill_window._snap(n, names) != n] == []


def test_skill_name_near_twins_do_not_snap():
    from maplelens.readers import skill_window

    twins = ["Blunt Weapon Mastery", "Blunt Weapon Booster"]
    assert skill_window._snap("Blunt Weapon Maoster", twins) is None  # 0.95 vs 0.90
    assert skill_window._snap("Blunt Weapon Mastery", twins) == twins[0]  # clean read
    assert skill_window._snap(
        "Final Attack: Spear", ["Final Attack: Spear", "Final Attack: Polearm"]
    )


def _same_skills(got, want):
    assert isinstance(got, SkillWindow), got
    assert (got.tab, got.sp) == (want.tab, want.sp)
    assert [(r.skill, r.level) for r in got.rows] == [(r.skill, r.level) for r in want.rows]
    for g, w in zip(got.rows, want.rows, strict=True):
        assert abs(g.plus[0] - w.plus[0]) <= 1 and abs(g.plus[1] - w.plus[1]) <= 1, g


@needs_ocr
@pytest.mark.parametrize("name", sorted(p.name for p in SCREENS.glob("skill_*.png")))
def test_read_skill_window(name, monkeypatch):
    read, seen = skill_window.ocr.read_lines, []
    monkeypatch.setattr(skill_window.ocr, "read_lines", lambda m: seen.append(read(m)) or seen[-1])
    got, want = read_skill_window(screen(name)), EXPECTED_SKILL[name]
    if isinstance(want, SkillWindow):
        assert isinstance(got, SkillWindow), (got, seen)  # seen: the names as the OCR read them
        _same_skills(got, want)
    else:
        assert got == want, seen


def test_a_name_with_ink_read_as_nothing_is_unreadable(monkeypatch):
    """A covered name the OCR reads as nothing is not a blank row."""
    calls = []
    monkeypatch.setattr(skill_window.ocr, "read_lines", lambda m: calls.append(m) and [])
    assert read_skill_window(screen("skill_a_1366x768_100.png")) == UNREADABLE
    assert len(calls) == 1  # the first row's ink, and no further


@needs_ocr
def test_unknown_skill_name_is_unreadable(monkeypatch):
    monkeypatch.setattr(skill_window, "known_skills", dict)
    assert read_skill_window(screen("skill_a_1366x768_100.png")) == UNREADABLE


@needs_ocr
def test_skill_level_over_max_is_unreadable(monkeypatch):
    real = skill_window.known_skills()
    monkeypatch.setattr(skill_window, "known_skills", lambda: real)
    monkeypatch.setattr(skill_window, "_max", lambda skill: 14 if skill == 4000000 else 20)
    assert read_skill_window(screen("skill_a_1366x768_100.png")) == UNREADABLE


@needs_ocr
def test_skill_tab_is_the_job_every_row_shares(monkeypatch):
    names = {"Nimble Body": [(1, "A")], "Keen Eyes": [(2, "B")]}
    monkeypatch.setattr(skill_window, "known_skills", lambda: names)
    assert read_skill_window(screen("skill_a_1366x768_100.png")) == UNREADABLE


@needs_ocr
@pytest.mark.parametrize(
    "name, ks",
    [
        ("skill_a_2560x1440_100_x1093_y13.png", range(0, 15, 2)),
        ("skill_a_1920x1080_100_x819_y9.png", range(0, 12, 2)),
    ],
)
def test_skill_reads_at_every_offset(name, ks):
    img, (x0, y0), client = raw(name)
    base = read_skill_window(screen(name))
    for k in ks:
        got = read_skill_window(glyphs.normalize(img[k:, k:], (x0 + k, y0 + k), client))
        dx, dy = _moved(x0, k, 1366, client[0]), _moved(y0, k, 768, client[1])
        want = [(r.skill, r.level, (r.plus[0] - dx, r.plus[1] - dy)) for r in base.rows]
        assert [(r.skill, r.level, r.plus) for r in got.rows] == want, k


def test_skill_plus_off_frame_is_unreadable():
    assert read_skill_window(screen("skill_a_1366x768_100.png")[:, :140]) == UNREADABLE


@pytest.mark.parametrize("name", sorted(p.name for p in SCREENS.glob("stat_a_*.png")))
def test_no_skill_window_in_a_stat_window(name):
    assert read_skill_window(screen(name)) is None
