"""Shared by the draggable-window readers (stat, skill): find the window, read digits.

glyphs.normalize gives back the game's own picture, so a window lands on whole pixels:
find() cuts it out at its best anchor, and read_number_text() correlates grey glyph
templates (templates/window_font/).
"""

import cv2
import numpy as np

from maplelens.readers import glyphs

UNREADABLE = "unreadable"  # a window was found but a field could not be read

# An anchor must score this (grey TM_CCOEFF_NORMED): 1.00 where it shows; another
# window's title bar scored 0.76 for skill_title on the owner's grabs.
ANCHOR_MIN = 0.9
# A glyph needs this score. Accepted glyphs scored 1.0 on the fixtures.
GLYPH_MIN = 0.8
# No other char may score within this of an accepted glyph within 1 px, at any score.
# Smallest runner-up gap measured on the stat fixtures: 0.157.
GLYPH_MARGIN = 0.07
# Outside the glyphs a strip must be its background: within BG_TOL of the median grey.
# Measured on the stat fixtures: 0 (flat 222 fields, 255 for the AP box).
BG_TOL = 12
GLYPH_H = 13
INK = 90  # grey below this is ink (dark digits on a light field)

_font: list[tuple[str, np.ndarray]] = []


def _gray(img: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)


def _cut(img: np.ndarray, x: int, y: int, w: int, h: int) -> np.ndarray:
    """img[y:y+h, x:x+w], black where that lies outside img."""
    out = np.zeros((h, w, 3), img.dtype)
    x0, y0, x1, y1 = max(x, 0), max(y, 0), min(x + w, img.shape[1]), min(y + h, img.shape[0])
    if x1 > x0 and y1 > y0:
        out[y0 - y : y1 - y, x0 - x : x1 - x] = img[y0:y1, x0:x1]
    return out


def find(
    frame: np.ndarray, anchors: list[tuple[str, tuple[int, int]]], size: tuple[int, int]
) -> tuple[np.ndarray, tuple[int, int]] | None:
    """The window as a BGR image of `size` (w, h), and its top-left in `frame`.

    `anchors`: (template name, offset from the window's top-left); the best-scoring one
    places the window. None if none scores ANCHOR_MIN.
    """
    g = _gray(frame)
    best, spot = ANCHOR_MIN, None
    for name, (ax, ay) in anchors:
        t = _gray(glyphs.load(name))
        if g.shape[0] < t.shape[0] or g.shape[1] < t.shape[1]:
            continue
        _, sc, _, loc = cv2.minMaxLoc(cv2.matchTemplate(g, t, cv2.TM_CCOEFF_NORMED))
        if sc >= best:
            best, spot = sc, (loc[0] - ax, loc[1] - ay)
    if spot is None:
        return None
    return _cut(frame, *spot, *size), spot


def _glyphs() -> list[tuple[str, np.ndarray]]:
    if not _font:
        for p in sorted((glyphs.TEMPLATES / "window_font").glob("*.png")):
            img = glyphs.imread(p, cv2.IMREAD_GRAYSCALE)
            _font.append((glyphs.CHAR_NAMES.get(p.stem, p.stem), img.astype(np.float32)))
    return _font


def read_number_text(win: np.ndarray, box: tuple[int, int, int, int]) -> str | None:
    """The digits and signs in `box` (x, y, w, h of `win`), or None.

    Every ink column of the box must belong to a glyph that scores GLYPH_MIN and beats
    every other char at that spot by GLYPH_MARGIN. The box's top and bottom rows are not
    checked for ink (its border may lie there).
    """
    x, y, w, h = box
    strip = _gray(win[y : y + h, x : x + w]).astype(np.float32)
    if strip.shape[0] < GLYPH_H or strip.shape[1] < 3:
        return None
    chosen = _accepted(strip)
    if chosen is None:
        return None
    ink = np.flatnonzero((strip[1:-1] < INK).any(axis=0))
    if ink.size == 0 or not all(any(a <= i < b for a, b, _ in chosen) for i in ink):
        return None
    # Everything outside the glyphs must be the field's background: a light overlay
    # without a border would hide text and leave no ink to notice.
    bg = np.ones(strip.shape, bool)
    bg[:2] = bg[-2:] = False  # the field's own edge may lie on the strip's border rows
    bg[:, :3] = False  # and its left edge on the first columns
    for a, b, _ in chosen:
        bg[:, a - 1 : b + 1] = False
    if bg.any() and (np.abs(strip[bg] - np.median(strip[bg])) > BG_TOL).any():
        return None
    return "".join(c for _, _, c in chosen)


def _accepted(strip: np.ndarray) -> list[tuple[int, int, str]] | None:
    """Non-overlapping glyphs (ink start, ink end, char), left to right; None if one is
    ambiguous (another char within GLYPH_MARGIN of it, within 1 px, at any score)."""
    scores = {}
    for ch, t in _glyphs():
        if strip.shape[1] >= t.shape[1]:
            r = cv2.matchTemplate(strip, t, cv2.TM_CCOEFF_NORMED).max(axis=0)
            scores.setdefault(ch, []).append((t.shape[1], r))
    cands = []
    for ch, rows in scores.items():
        for tw, s in rows:
            peaks = (s >= GLYPH_MIN) & (s >= np.r_[-1, s[:-1]]) & (s >= np.r_[s[1:], -1])
            cands += [(float(s[i]), i + 1, i + tw - 1, ch) for i in np.flatnonzero(peaks)]
    chosen: list[tuple[int, int, str]] = []
    for sc, a, b, ch in sorted(cands, reverse=True):
        if any(a < cb and b > ca for ca, cb, _ in chosen):
            continue
        rivals = (
            s[max(a - 2, 0) : a + 1].max(initial=-1)
            for c, r in scores.items()
            for _, s in r
            if c != ch
        )
        if any(v > sc - GLYPH_MARGIN for v in rivals):
            return None
        chosen.append((a, b, ch))
    return sorted(chosen)
