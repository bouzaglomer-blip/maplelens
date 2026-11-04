"""Player position reader: the yellow "you" dot on the minimap.

The minimap's map area sits in a white frame under the title. The map picture fills the
frame's height; when it is narrower than the window it is centred on see-through padding.
"""

import cv2
import numpy as np

from maplelens.readers import glyphs, map_name

# Frame rows relative to the minimap_title anchor: the map area's first row.
MAP_DY = 66
# The frame's white side line runs 2 px left of the anchor, down to 2 rows past the map.
SIDE_DX, SIDE_PAST = -2, 2
# The map area ends 3 px before the title box's end (map_name's plain-panel width).
RIGHT_PAD = 3
# Min channel of the frame's white lines; padding over a bright scene stays below it.
WHITE = 245
# Padding edges: columns where at least half the rows step by this much (max channel)
# from the next column. Fixtures: 80+ at real edges, under 35 inside full-width maps.
EDGE_STEP = 60
# Left and right padding may differ by this much (odd widths, resizing).
EDGE_SLACK = 2
# The dot's yellow fill (BGR); the party marker's orange has green under 160, its "+"
# blue under 25. Normalized, the fill is a 6x6 disc of 23-24 px at every resolution;
# yellow map art (Henesys roofs: 7x5, 6x4) fails the size or the squareness.
DOT_LO, DOT_HI = (25, 180, 200), (110, 255, 255)
DOT_SIDE = (5, 7)
DOT_SQUARE = 1  # max width - height difference
DOT_AREA = (18, 28)


def _map_area(frame: np.ndarray, x: int, y: int) -> tuple[int, int, int, int] | None:
    """(x0, y0, x1, y1) of the map picture, or None if the frame isn't intact."""
    y0 = y + MAP_DY
    w = map_name._plain(frame[y + map_name.TITLE_DY, x + map_name.TITLE_DX :], map_name.PANEL)
    x0, x1 = x, x + map_name.TITLE_DX + w - RIGHT_PAD
    side = frame[y0:, x + SIDE_DX].min(axis=1) >= WHITE
    y1 = y0 + (int(np.argmin(side)) if not side.all() else len(side)) - SIDE_PAST
    if y1 - y0 < 10 or x1 - x0 < 20 or y1 + 1 >= frame.shape[0]:
        return None
    # A window over the map breaks the frame's bottom line (or the right one).
    if frame[y1 + 1, x0:x1].min() < WHITE or frame[y0:y1, x1 + 2].min() < WHITE:
        return None
    a = frame[y0:y1, x0:x1].astype(int)
    step = np.median(np.abs(np.diff(a, axis=1)).max(axis=2), axis=0)  # col i | i+1
    edges = np.flatnonzero(step >= EDGE_STEP) + 1
    width = x1 - x0
    pairs = [
        (step[left - 1] + step[right - 1], left, right)
        for left in edges[edges < width // 2]
        for right in edges[edges > width // 2]
        if abs(left - (width - right)) <= EDGE_SLACK
    ]
    if pairs:
        _, left, right = max(pairs)
        x0, x1 = x0 + left, x0 + right
    return x0, y0, x1, y1


def read_player(frame: np.ndarray) -> tuple[float, float] | None:
    """The "you" dot's centre as (fx, fy) fractions of the minimap's map area, or None.

    `frame` is normalized. None when the minimap is closed, minimized, covered, or the
    dot isn't found exactly once.
    """
    hit = glyphs.find_anchor(frame[: map_name.BAND_H, : map_name.BAND_W], "minimap_title")
    area = None if hit is None else _map_area(frame, *hit)
    if area is None:
        return None
    x0, y0, x1, y1 = area
    m = glyphs.mask(frame[y0:y1, x0:x1], DOT_LO, DOT_HI).astype(np.uint8)
    n, _, stats, centres = cv2.connectedComponentsWithStats(m, connectivity=8)
    dots = []
    for i in range(1, n):
        w, h, px = stats[i, cv2.CC_STAT_WIDTH : cv2.CC_STAT_AREA + 1]
        if (
            DOT_SIDE[0] <= min(w, h)
            and max(w, h) <= DOT_SIDE[1]
            and abs(w - h) <= DOT_SQUARE
            and DOT_AREA[0] <= px <= DOT_AREA[1]
        ):
            dots.append(centres[i])
    if len(dots) != 1:
        return None
    cx, cy = dots[0] + 0.5  # pixel centres -> edges
    return float(cx / (x1 - x0)), float(cy / (y1 - y0))
