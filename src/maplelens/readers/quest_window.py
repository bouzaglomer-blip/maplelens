"""Quest window reader: which quest the game's quest window shows, and from which tab.

The details pane's header and the list rows show the quest's chain name, cut with "…"
when long; the quest's own name is the first grey line on the white body, never cut.
"""

import json
from dataclasses import dataclass
from functools import cache
from pathlib import Path

import numpy as np

from maplelens.readers import glyphs, map_name, ocr, window
from maplelens.readers.window import UNREADABLE


@dataclass(frozen=True)
class QuestOpen:
    name: str  # as read; it may match no quest in the data
    taken: bool | None  # True: the In Progress tab, False: Available, None: can't tell


# The window, 768-scale (548x397 at 1366x768, 770x556 at 1920x1080): size, and the anchor
# (the "QUEST" title bar, template, offset from its top-left).
WIN_W, WIN_H = 548, 397
ANCHORS = [("quest_title", (4, 7))]
# The tabs' rows and columns: Available, In Progress, Completed. The open one is pink:
# red over blue by PINK_RB. Measured: about 935 pink px on the open tab, at most 73 on
# the others (their edges, at 1920x1080); PINK_MIN sits well between.
TAB_Y = (24, 42)
TABS_X = ((4, 78), (78, 150), (150, 222))
TAKEN = (False, True, None)  # None: the Completed tab, nothing to help with
PINK_RB, PINK_MIN = 40, 400
# The details body (x, y, w, h), left of its scrollbar and under the blue header block.
BODY = (256, 106, 268, 256)
# Ink, to find the lines: the grey text (51 on In Progress, 102 on Available); blue
# and red words have one channel at 255. The quest's name is the first ink line whose row
# above is the body's white (the Quest Summary box above it is beige, 213-225).
INK_LO, INK_HI = (0, 0, 0), (150, 150, 150)
WHITE = 245
# The OCR's mask keeps the bold strokes' soft edges too: on the grabs, at 6 sub-pixel
# offsets each, Windows OCR read every name exactly from 200 to 210; 190 and 215 lost
# letters ("Cal (Is", "Filho").
OCR_INK_HI = (205, 205, 205)


@cache
def known_quest_names() -> frozenset[str]:
    data = Path(__file__).parents[1] / "data" / "quests.json"
    return frozenset(q["name"] for q in json.loads(data.read_text("utf-8"))["quests"])


def _tab(win: np.ndarray) -> int | None:
    """Index of the open (pink) tab in TABS_X, or None if no single tab is pink."""
    px = win[TAB_Y[0] : TAB_Y[1]].astype(int)
    pink = px[..., 2] - px[..., 0] > PINK_RB
    counts = [int(pink[:, a:b].sum()) for a, b in TABS_X]
    best = int(np.argmax(counts))
    return best if counts[best] >= PINK_MIN else None


def _name_line(win: np.ndarray) -> tuple[int, int] | None:
    """Rows (first, last) of the window holding the quest's name, or None."""
    x, y, w, h = BODY
    body = win[y : y + h, x : x + w]
    rows = np.flatnonzero(glyphs.mask(body, INK_LO, INK_HI).any(axis=1))
    for run in np.split(rows, np.flatnonzero(np.diff(rows) > 1) + 1):
        if run.size and run[0] > 0 and (np.median(body[run[0] - 1], axis=0) >= WHITE).all():
            return y + int(run[0]), y + int(run[-1])
    return None


def read_quest_window(
    frame: np.ndarray, native: np.ndarray | None = None, scale: float | None = None
) -> QuestOpen | str | None:
    """The quest window in `frame` (normalized), read from `native` (default `frame`).

    None if no window is found or it shows the Completed tab; UNREADABLE if one is but
    its details body is off screen or its name can't be read.
    """
    native = frame if native is None else native
    scale = native.shape[0] / frame.shape[0] if scale is None else scale
    hit = window.align(frame, native, scale, ANCHORS, (WIN_W, WIN_H))
    if hit is None:
        return None
    win, (wx, wy) = hit
    tab = _tab(win)
    if tab is not None and TAKEN[tab] is None:
        return None
    x, y, w, h = BODY
    fh, fw = frame.shape[:2]
    if not (0 <= wx + x <= fw - w and 0 <= wy + y <= fh - h):
        return UNREADABLE
    line = _name_line(win)
    if line is None:
        return UNREADABLE
    box = (wx + x, wy + line[0], w, line[1] - line[0] + 1)
    lines = ocr.read_lines(glyphs.mask(ocr.crop(frame, native, box), INK_LO, OCR_INK_HI))
    text = " ".join(lines or []).strip()
    if not text or not text.isprintable():
        return UNREADABLE
    return QuestOpen(
        map_name.snap_title(text, known_quest_names()), None if tab is None else TAKEN[tab]
    )
