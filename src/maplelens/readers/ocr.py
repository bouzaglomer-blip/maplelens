"""Words (map name, class) via the OCR built into the system: no example letters needed."""

import sys
from functools import cache, lru_cache

import cv2
import numpy as np

# OCR input: the text cut from the native shot at 3x the 768 look, masked, trimmed to
# its ink, black on white, padded 12 px. Measured on the owner's grabs: 2x, 4x, colour
# crops, or the empty rest of a box left in all missed words.
SCALE = 3
PAD = 12
# Box margin, normalized px, so a cut never clips a stroke. 2 px reached the minimap
# bar's button border and read it as an 'I'.
MARGIN = 1


def _backend():
    """The platform OCR module, or None where there is none (or its import fails)."""
    try:
        if sys.platform == "win32":
            from maplelens.readers import ocr_win

            return ocr_win
    except Exception:
        pass
    return None


@cache
def engine():
    """The platform OCR engine, or None when the system has none."""
    backend = _backend()
    return backend.engine() if backend else None


def crop(frame: np.ndarray, native: np.ndarray, box: tuple[int, int, int, int]) -> np.ndarray:
    """Box (x, y, w, h) of the normalized `frame` (the 768 look), cut from `native` (the
    same shot at any size) with MARGIN around it, and scaled to SCALE x the 768 look.

    Native pixels keep detail the downscale to 768 loses: masks of normalized crops
    dropped a trailing 'I' or '1>' on the grabs.
    """
    x, y, w, h = box
    s = native.shape[0] / frame.shape[0]
    x0, y0 = max(0, int((x - MARGIN) * s)), max(0, int((y - MARGIN) * s))
    c = native[y0 : int((y + h + MARGIN) * s), x0 : int((x + w + MARGIN) * s)]
    return cv2.resize(c, None, fx=SCALE / s, fy=SCALE / s, interpolation=cv2.INTER_CUBIC)


@lru_cache(maxsize=64)
def _recognize(shape: tuple[int, int], data: bytes) -> list[str]:
    img = np.where(np.frombuffer(data, bool).reshape(shape), 0, 255).astype(np.uint8)
    img = cv2.copyMakeBorder(img, PAD, PAD, PAD, PAD, cv2.BORDER_CONSTANT, value=255)
    return _backend().recognize(img)


def read_lines(m: np.ndarray) -> list[str] | None:
    """Text lines of a bool ink mask (True = ink, already at the OCR scale, see crop),
    or None when the system has no OCR engine. Cached by mask bytes, 64 entries."""
    if engine() is None:
        return None
    rows, cols = np.flatnonzero(m.any(axis=1)), np.flatnonzero(m.any(axis=0))
    if rows.size == 0:
        return []
    m = np.ascontiguousarray(m[rows[0] : rows[-1] + 1, cols[0] : cols[-1] + 1], bool)
    return _recognize(m.shape, m.tobytes())
