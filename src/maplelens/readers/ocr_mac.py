"""macOS OCR backend: the Vision text recognizer built into macOS, no example letters needed."""

from functools import cache

import cv2
import numpy as np


@cache
def engine():
    """The Vision module, or None when it cannot be imported."""
    try:
        import Vision

        return Vision
    except Exception:  # pyobjc missing
        return None


def recognize(img: np.ndarray) -> list[str]:
    """Stripped text lines of a padded black-on-white uint8 gray image."""
    from Foundation import NSData

    vision = engine()
    png = cv2.imencode(".png", img)[1].tobytes()
    req = vision.VNRecognizeTextRequest.alloc().init()
    req.setRecognitionLevel_(vision.VNRequestTextRecognitionLevelAccurate)
    req.setUsesLanguageCorrection_(False)  # game words are not dictionary words
    req.setRecognitionLanguages_(["en-US"])
    handler = vision.VNImageRequestHandler.alloc().initWithData_options_(
        NSData.dataWithBytes_length_(png, len(png)), None
    )
    handler.performRequests_error_([req], None)
    return [o.topCandidates_(1)[0].string().strip() for o in req.results() or []]
