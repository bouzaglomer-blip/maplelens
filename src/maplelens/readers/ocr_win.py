"""Windows OCR backend: the engine built into Windows, no example letters needed."""

import asyncio

import numpy as np


def engine():
    """An English OCR engine (the game text is English), else the user-profile one, else None."""
    try:
        from winrt.windows.globalization import Language
        from winrt.windows.media.ocr import OcrEngine

        en = OcrEngine.try_create_from_language(Language("en-US"))
        return en or OcrEngine.try_create_from_user_profile_languages()
    except Exception:  # missing packages, or WinRT failing (old Windows, no OCR feature)
        return None


def recognize(img: np.ndarray) -> list[str]:
    """Stripped text lines of a padded black-on-white uint8 gray image."""
    from winrt.windows.graphics.imaging import BitmapPixelFormat, SoftwareBitmap

    h, w = img.shape
    bmp = SoftwareBitmap.create_copy_from_buffer(img.tobytes(), BitmapPixelFormat.GRAY8, w, h)

    async def run():
        return await engine().recognize_async(bmp)

    # asyncio.run, not the operation's blocking get(): get() refuses to block the Qt
    # main thread (a single-threaded apartment).
    return [line.text.strip() for line in asyncio.run(run()).lines]
