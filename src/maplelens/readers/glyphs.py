"""Template matching on screenshots: find an anchor, read bitmap-font text."""

from pathlib import Path

import cv2
import numpy as np

TEMPLATES = Path(__file__).parent / "templates"
BASE_H = 768
# A glyph matches a template when at most this share of pixels differ.
MAX_DIFF = 0.10
# A cached anchor spot is trusted only on a pixel-exact match.
EXACT = 0.9999
# Glyph file stems that are not the character itself.
CHAR_NAMES = {
    "comma": ",",
    "dot": ".",
    "pct": "%",
    "lbr": "[",
    "rbr": "]",
    "slash": "/",
    "lt": "<",
    "gt": ">",
}

_images: dict[str, np.ndarray] = {}
_fonts: dict[str, dict[str, np.ndarray]] = {}
_last_hit: dict[str, tuple[int, int]] = {}


def clear_cache() -> None:
    _images.clear()
    _fonts.clear()
    _last_hit.clear()


def load(name: str) -> np.ndarray:
    """templates/<name>.png as BGR, cached."""
    if name not in _images:
        img = cv2.imread(str(TEMPLATES / f"{name}.png"), cv2.IMREAD_COLOR)
        if img is None:
            raise FileNotFoundError(TEMPLATES / f"{name}.png")
        _images[name] = img
    return _images[name]


def normalize(frame: np.ndarray) -> np.ndarray:
    """Resize to height BASE_H, keeping aspect. A frame already that high is returned as is."""
    h, w = frame.shape[:2]
    if h == BASE_H:
        return frame
    return cv2.resize(frame, (round(w * BASE_H / h), BASE_H), interpolation=cv2.INTER_AREA)


def find_anchor(frame: np.ndarray, name: str, threshold: float = 0.9) -> tuple[int, int] | None:
    """Top-left of the best match of anchor `name` scoring >= threshold, else None."""
    tpl = load(name)
    th, tw = tpl.shape[:2]
    if frame.shape[0] < th or frame.shape[1] < tw:
        return None
    # Fast path: a pixel-exact match at the last spot cannot be beaten (ties aside).
    if name in _last_hit:
        x, y = _last_hit[name]
        crop = frame[y : y + th, x : x + tw]
        if crop.shape == tpl.shape:
            score = cv2.matchTemplate(crop, tpl, cv2.TM_CCOEFF_NORMED)[0, 0]
            if score >= EXACT:
                return x, y
    _, best, _, loc = cv2.minMaxLoc(cv2.matchTemplate(frame, tpl, cv2.TM_CCOEFF_NORMED))
    if best < threshold:
        _last_hit.pop(name, None)
        return None
    _last_hit[name] = loc
    return loc


def mask(img: np.ndarray, lo: tuple[int, int, int], hi: tuple[int, int, int]) -> np.ndarray:
    """Bool mask of pixels with BGR inside [lo, hi]."""
    return cv2.inRange(img, np.array(lo, np.uint8), np.array(hi, np.uint8)) > 0


def _font(font: str) -> dict[str, np.ndarray]:
    if font not in _fonts:
        paths = sorted((TEMPLATES / font).glob("*.png"))
        if not paths:
            raise FileNotFoundError(f"no glyph PNGs in {TEMPLATES / font}")
        glyphs = {}
        for p in paths:
            img = cv2.imread(str(p), cv2.IMREAD_GRAYSCALE)
            if img is None:
                raise FileNotFoundError(f"cannot read glyph {p}")
            glyphs[CHAR_NAMES.get(p.stem, p.stem)] = img > 127
        _fonts[font] = glyphs
    return _fonts[font]


def _match(glyph: np.ndarray, templates: dict[str, np.ndarray]) -> str | None:
    best, best_diff = None, MAX_DIFF
    for ch, t in templates.items():
        if abs(glyph.shape[0] - t.shape[0]) > 1 or abs(glyph.shape[1] - t.shape[1]) > 1:
            continue
        g = cv2.resize(
            glyph.astype(np.uint8), (t.shape[1], t.shape[0]), interpolation=cv2.INTER_NEAREST
        ).astype(bool)
        diff = np.count_nonzero(g != t) / t.size
        if diff <= best_diff:
            best, best_diff = ch, diff
    return best


def read_text(m: np.ndarray, font: str, space_px: int) -> str | None:
    """Read a bool ink mask with the bitmap font `font`; None if any glyph is unknown."""
    templates = _font(font)
    cols = np.flatnonzero(m.any(axis=0))
    if cols.size == 0:
        return None
    # Runs of ink columns: split where consecutive ink columns are not adjacent.
    runs = np.split(cols, np.flatnonzero(np.diff(cols) > 1) + 1)
    out = ""
    prev_end = None
    for run in runs:
        x0, x1 = run[0], run[-1] + 1
        if prev_end is not None and x0 - prev_end >= space_px:
            out += " "
        prev_end = x1
        sub = m[:, x0:x1]
        rows = np.flatnonzero(sub.any(axis=1))
        ch = _match(sub[rows[0] : rows[-1] + 1], templates)
        if ch is None:
            return None
        out += ch
    return out
