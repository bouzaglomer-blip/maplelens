"""Words (map name, class) via the OCR built into Windows: no example letters needed."""

import asyncio
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


@cache
def engine():
    """An English OCR engine (the game text is English), else the user-profile one, else None."""
    try:
        from winrt.windows.globalization import Language
        from winrt.windows.media.ocr import OcrEngine

        en = OcrEngine.try_create_from_language(Language("en-US"))
        return en or OcrEngine.try_create_from_user_profile_languages()
    except Exception:  # missing packages, or WinRT failing (old Windows, no OCR feature)
        return None


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
    from winrt.windows.graphics.imaging import BitmapPixelFormat, SoftwareBitmap

    img = np.where(np.frombuffer(data, bool).reshape(shape), 0, 255).astype(np.uint8)
    img = cv2.copyMakeBorder(img, PAD, PAD, PAD, PAD, cv2.BORDER_CONSTANT, value=255)
    h, w = img.shape
    bmp = SoftwareBitmap.create_copy_from_buffer(img.tobytes(), BitmapPixelFormat.GRAY8, w, h)

    async def run():
        return await engine().recognize_async(bmp)

    # asyncio.run, not the operation's blocking get(): get() refuses to block the Qt
    # main thread (a single-threaded apartment).
    return [line.text.strip() for line in asyncio.run(run()).lines]


def read_lines(m: np.ndarray) -> list[str] | None:
    """Text lines of a bool ink mask (True = ink, already at the OCR scale, see crop),
    or None when Windows has no OCR engine. Cached by mask bytes, 64 entries."""
    if engine() is None:
        return None
    rows, cols = np.flatnonzero(m.any(axis=1)), np.flatnonzero(m.any(axis=0))
    if rows.size == 0:
        return []
    m = np.ascontiguousarray(m[rows[0] : rows[-1] + 1, cols[0] : cols[-1] + 1], bool)
    return _recognize(m.shape, m.tobytes())
