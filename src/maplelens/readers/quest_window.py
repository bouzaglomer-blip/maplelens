"""Quest window reader: which quest the game's quest window shows, and from which tab.

The details pane's header and the list rows show the quest's chain name, cut with "…"
when long; the quest's own name is the first grey line on the white body, never cut.
That line is trusted only when it snaps to a known Classic quest name: a scrolled pane
or another layout puts a description line there instead.
"""

import json
from dataclasses import dataclass
from functools import cache, lru_cache
from pathlib import Path

import numpy as np

from maplelens.readers import glyphs, map_name, ocr, window
from maplelens.readers.window import UNREADABLE

NAME_UNREADABLE = "name unreadable"  # a window is there; its name line isn't a known name


@dataclass(frozen=True)
class QuestOpen:
    name: str  # as read; it may match no quest in the data
    taken: bool | None  # True: the In Progress tab, False: Available, None: can't tell


# The window, 768-scale (548x397 at 1366x768, 770x556 at 1920x1080): size, and the anchor
# (the "QUEST" title bar, template, offset from its top-left). Coarse scores (grey
# TM_CCOEFF_NORMED on the normalized frame): the quest grabs 1.00 at 1366 and 0.858 at
# 1920; stat_a 0.53-0.56, skill_a at most 0.52, title_ellinia 0.45. The stat title clears
# window.COARSE_MIN, so it's the exact-spot ANCHOR_MIN and the tab gate that reject it.
WIN_W, WIN_H = 548, 397
ANCHORS = [("quest_title", (4, 7))]
# The tabs' rows and columns: Available, In Progress, Completed. The open one is pink:
# red over blue by PINK_RB. Measured: about 935 pink px on the open tab, at most 73 on
# the others (their edges, at 1920x1080); PINK_MIN sits well between. No pink tab: not
# a quest window.
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
    """The quests' names, and the Classic quests left out on purpose ("other_names")."""
    raw = json.loads((Path(__file__).parents[1] / "data" / "quests.json").read_text("utf-8"))
    return frozenset(q["name"] for q in raw["quests"]) | frozenset(raw["other_names"])


@lru_cache(maxsize=256)
def _snap(text: str) -> str | None:
    """The known quest name `text` reads as, else None."""
    name = map_name.snap_title(text, known_quest_names())
    return name if name in known_quest_names() else None


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

    None if no window is found, no tab is open (pink) or it's the Completed tab;
    UNREADABLE if one is but the frame's edge cuts its details body; NAME_UNREADABLE if
    no name line is found (the text is scrolled) or it doesn't read as a known quest name.

    Limit: the "QUEST" title is the anchor, at the window's top-left, so a window dragged
    past the frame's left or top edge isn't found and reads None, as if closed.
    """
    native = frame if native is None else native
    scale = native.shape[0] / frame.shape[0] if scale is None else scale
    hit = window.align(frame, native, scale, ANCHORS, (WIN_W, WIN_H))
    if hit is None:
        return None
    win, (wx, wy) = hit
    tab = _tab(win)
    if tab is None or TAKEN[tab] is None:
        return None
    x, y, w, h = BODY
    fh, fw = frame.shape[:2]
    if not (0 <= wx + x <= fw - w and 0 <= wy + y <= fh - h):
        return UNREADABLE
    line = _name_line(win)
    if line is None:
        return NAME_UNREADABLE
    box = (wx + x, wy + line[0], w, line[1] - line[0] + 1)
    lines = ocr.read_lines(glyphs.mask(ocr.crop(frame, native, box), INK_LO, OCR_INK_HI))
    text = " ".join(lines or []).strip()
    # OCR marks what it cannot read with replacement or control characters.
    name = _snap(text) if text.isprintable() and "\ufffd" not in text else None
    return NAME_UNREADABLE if name is None else QuestOpen(name, TAKEN[tab])
