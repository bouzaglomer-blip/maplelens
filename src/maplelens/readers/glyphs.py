"""Template matching on screenshots: find an anchor, read bitmap-font text."""

from pathlib import Path

import cv2
import numpy as np

TEMPLATES = Path(__file__).parent / "templates"
BASE_H = 768
# Default share of a glyph's pixels that may differ from its template.
MAX_DIFF = 0.10
# A cached anchor spot is trusted only on a pixel-exact match.
EXACT = 0.9999
# Glyph file stems that are not the character itself. A stem may carry a variant
# suffix after '_' (e.g. 3_1366.png): one char can have several templates.
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

Font = list[tuple[str, np.ndarray]]  # (char, ink mask) per template file

_images: dict[str, np.ndarray] = {}
_fonts: dict[str, Font] = {}
_anchors: dict[str, list[str]] = {}
_last_hit: dict[str, tuple[int, tuple[int, int]]] = {}  # name -> (variant, spot)


def clear_cache() -> None:
    _images.clear()
    _fonts.clear()
    _anchors.clear()
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


def _anchor_names(name: str) -> list[str]:
    """Template stems for anchor `name`: <name>.png and variants <name>_<digits>.png."""
    if name not in _anchors:
        paths = [TEMPLATES / f"{name}.png"] + sorted(TEMPLATES.glob(f"{name}_[0-9]*.png"))
        _anchors[name] = [p.stem for p in paths if p.exists()]
        if not _anchors[name]:
            raise FileNotFoundError(TEMPLATES / f"{name}.png")
    return _anchors[name]


def find_anchor(frame: np.ndarray, name: str, threshold: float = 0.9) -> tuple[int, int] | None:
    """Top-left of the best match of anchor `name` (any variant) scoring >= threshold, else None."""
    tpls = [load(n) for n in _anchor_names(name)]
    # Fast path: a pixel-exact match at the last spot cannot be beaten (ties aside).
    if name in _last_hit:
        i, (x, y) = _last_hit[name]
        th, tw = tpls[i].shape[:2]
        crop = frame[y : y + th, x : x + tw]
        if crop.shape == tpls[i].shape:
            if cv2.matchTemplate(crop, tpls[i], cv2.TM_CCOEFF_NORMED)[0, 0] >= EXACT:
                return x, y
    best, hit = threshold, None
    for i, tpl in enumerate(tpls):
        if frame.shape[0] < tpl.shape[0] or frame.shape[1] < tpl.shape[1]:
            continue
        _, score, _, loc = cv2.minMaxLoc(cv2.matchTemplate(frame, tpl, cv2.TM_CCOEFF_NORMED))
        if score >= best:
            best, hit = score, (i, loc)
    if hit is None:
        _last_hit.pop(name, None)
        return None
    _last_hit[name] = hit
    return hit[1]


def mask(img: np.ndarray, lo: tuple[int, int, int], hi: tuple[int, int, int]) -> np.ndarray:
    """Bool mask of pixels with BGR inside [lo, hi]."""
    return cv2.inRange(img, np.array(lo, np.uint8), np.array(hi, np.uint8)) > 0


def _font(font: str) -> Font:
    if font not in _fonts:
        paths = sorted((TEMPLATES / font).glob("*.png"))
        if not paths:
            raise FileNotFoundError(f"no glyph PNGs in {TEMPLATES / font}")
        glyphs = []
        for p in paths:
            img = cv2.imread(str(p), cv2.IMREAD_GRAYSCALE)
            if img is None:
                raise FileNotFoundError(f"cannot read glyph {p}")
            name = p.stem.split("_")[0]
            glyphs.append((CHAR_NAMES.get(name, name), img > 127))
        _fonts[font] = glyphs
    return _fonts[font]


def _match(glyph: np.ndarray, templates: Font, max_diff: float) -> tuple[str, int] | None:
    """(char, differing pixels) of the closest template, or None if none is close enough."""
    best = None
    for ch, t in templates:
        if abs(glyph.shape[0] - t.shape[0]) > 1 or abs(glyph.shape[1] - t.shape[1]) > 1:
            continue
        g = cv2.resize(
            glyph.astype(np.uint8), (t.shape[1], t.shape[0]), interpolation=cv2.INTER_NEAREST
        ).astype(bool)
        diff = np.count_nonzero(g != t)
        if diff <= max_diff * t.size and (best is None or diff <= best[1]):
            best = ch, diff
    return best


def _rows(m: np.ndarray) -> np.ndarray:
    rows = np.flatnonzero(m.any(axis=1))
    return m[rows[0] : rows[-1] + 1]


def _split(run: np.ndarray, templates: Font, max_diff: float) -> str | None:
    """Cut a run of touching glyphs into template matches, fewest differing pixels in total."""
    widest = max(t.shape[1] for _, t in templates) + 1
    w = run.shape[1]
    best = {0: (0, "")}  # columns read so far -> (differing pixels, text)
    for i in range(w):
        if i not in best:
            continue
        for j in range(i + 1, min(w, i + widest) + 1):
            hit = _match(_rows(run[:, i:j]), templates, max_diff)
            if hit and (j not in best or best[i][0] + hit[1] < best[j][0]):
                best[j] = best[i][0] + hit[1], best[i][1] + hit[0]
    return best[w][1] if w in best else None


def read_text(m: np.ndarray, font: str, space_px: int, max_diff: float = MAX_DIFF) -> str | None:
    """Read a bool ink mask with the bitmap font `font`; None if any glyph is unknown.

    A glyph matches a template when at most `max_diff` of its pixels differ.
    """
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
        hit = _match(_rows(sub), templates, max_diff)
        # Glyphs can touch after the resize to BASE_H; then cut the run by templates.
        text = hit[0] if hit else _split(sub, templates, max_diff)
        if text is None:
            return None
        out += text
    return out
