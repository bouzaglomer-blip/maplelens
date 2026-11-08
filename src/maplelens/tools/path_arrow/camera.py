"""Minimap -> world position -> normalized-frame pixels (768 high)."""

import cv2
import numpy as np

from maplelens.readers import minimap_pos
from maplelens.readers.minimap_pos import MinimapView
from maplelens.tools.path_arrow.maps import MapInfo, Minimap

# World units per normalized pixel.
WORLD_PER_PX = 1.0
# Camera centre's vertical offset from the player (the dot's world y), in world units:
# when the camera has caught up, the feet sit at y 384 + 161.
CAM_DY = -161.0
# World units per minimap pixel.
SCALE = 16
# An NPC marker's centre relative to the NPC's own position, in minimap px.
NPC_DX, NPC_DY = -0.6, -6.9
# A portal spiral's centre relative to the portal, in minimap px (Perion, Lith Harbor).
PORTAL_DX, PORTAL_DY = -0.4, -7.6
# An unclipped map area is within 1-2 px of w/16 x h/16; clipped ones lack 80+ px.
CLIP_SLACK = 4
# Matching markers to the map's NPCs and portals: a hit is within MATCH_TOL px on both
# axes; the scroll needs MIN_MATCH hits and MATCH_MARGIN more than any other scroll.
# Two is enough: with the margin, no other scroll in reach may match even one marker.
MATCH_TOL = 1.0
MIN_MATCH = 2
MATCH_MARGIN = 2
# Matching the window's pixels to the map's picture, compared on the picture's solid art
# only (the rest is see-through, so it shows whatever scene is behind). Mean squared
# difference per channel, 0-1 scale. From The Forest North of Ellinia (bottom to top) and
# Kerning City, Henesys, Lith Harbor, Perion at 2560 and 1366, and The Tree Tunnel and
# Tree Dungeon I at 2560: the right scroll scores <= 0.0052, and the next one more than
# 2 px away is >= 3x worse (Forest North, towns: >= 5x) and >= 0.0053 worse; the best spot
# on any other map's picture scores >= 0.0092; a frame mid-scroll scored 0.0092.
# The gap is a ratio because even-textured maps (the tunnel) make every scroll fit
# somewhat; the small fixed part keeps a near-0 best (1366 is 1:1) from passing alone.
PIC_MAX_MSE = 0.007
PIC_RATIO = 2.0
PIC_MARGIN = 0.003
PIC_MIN_SOLID = 600  # solid picture px under the window, markers left out
MARK_R = 6  # px left out around each marker centre
# Other players' red and party orange dot fills (BGR), and their size: about our own dot's
# (6x6 of 24 px), loosely, since leaving out a bit of map art by mistake costs little.
OTHER_LO, OTHER_HI = (0, 0, 170), (90, 160, 255)
OTHER_SIDE, OTHER_AREA = (5, 7), (18, 28)


def to_world(f: tuple[float, float], mm: Minimap) -> tuple[float, float]:
    """Inverse of the map data's fx = (x + cx) / w, fy = (y + cy) / h."""
    return f[0] * mm.w - mm.cx, f[1] * mm.h - mm.cy


def _scroll(view: MinimapView, info: MapInfo) -> tuple[float, float] | None:
    """How far (px) a clipped window is scrolled into the map picture, or None.

    The window keeps the player centred and stops at the picture's edges, so the scroll
    is read from the NPC markers and portal spirals it shows against the map's NPC and
    portal positions. A marker only ever matches a position of its own kind.
    """
    # ponytail: a clipped map showing fewer than MIN_MATCH markers (a hunting field with
    # no NPCs and one portal in view) still gets None. Upgrade: per-map platform shapes.
    mm = info.minimap

    def at(x, y, d):
        return (x + mm.cx) / SCALE + d[0], (y + mm.cy) / SCALE + d[1]

    pred = [(*at(x, y, (NPC_DX, NPC_DY)), 0) for x, y in info.npcs]
    pred += [(*at(p.x, p.y, (PORTAL_DX, PORTAL_DY)), 1) for p in info.portals if not p.hidden]
    seen = [(x, y, 0) for x, y in view.npcs] + [(x, y, 1) for x, y in view.portals]
    room = (mm.w / SCALE - view.size[0], mm.h / SCALE - view.size[1])
    found = []
    for m in seen:
        for p in pred:
            s = (p[0] - m[0], p[1] - m[1])
            if p[2] != m[2] or not all(
                -CLIP_SLACK <= s[i] <= max(room[i], 0) + CLIP_SLACK for i in (0, 1)
            ):
                continue
            hits = [
                (q[0] - n[0], q[1] - n[1])
                for n in seen
                for q in pred
                if q[2] == n[2]
                and abs(q[0] - n[0] - s[0]) <= MATCH_TOL
                and abs(q[1] - n[1] - s[1]) <= MATCH_TOL
            ]
            found.append((len(hits), tuple(np.mean(hits, axis=0))))
    if not found:
        return None
    n, best = max(found)
    rival = max(
        (k for k, s in found if max(abs(s[0] - best[0]), abs(s[1] - best[1])) > 2 * MATCH_TOL),
        default=0,
    )
    if n < MIN_MATCH or rival > n - MATCH_MARGIN:
        return None
    return float(best[0]), float(best[1])


def _corr(img: np.ndarray, templ: np.ndarray) -> np.ndarray:
    """sum(templ(p) * img(p + s)) for every shift s."""
    return cv2.matchTemplate(img, templ, cv2.TM_CCORR)


def picture_scroll(view: MinimapView, pic: np.ndarray) -> tuple[float, float] | None:
    """How far (px) the window is scrolled into the map's picture (BGRA), or None.

    Compares the window with the picture at every scroll, on the picture's solid pixels
    only and leaving out the markers drawn over it (ours, NPCs, spirals, other players).
    None unless one scroll fits well and clearly better than any other.
    """
    if view.pixels is None:
        return None
    v = view.pixels.astype(np.float32) / 255
    m = np.ones(v.shape[:2], np.float32)
    for x, y in (view.dot, *view.npcs, *view.portals):
        m[max(0, int(y) - MARK_R) : int(y) + MARK_R, max(0, int(x) - MARK_R) : int(x) + MARK_R] = 0
    # Other players' red and party members' orange dots: dot-shaped blobs only, since
    # map art can be red or orange too (Perion's rocks).
    for bw, bh, area, (x, y) in minimap_pos._blobs(view.pixels, OTHER_LO, OTHER_HI):
        if (
            OTHER_SIDE[0] <= min(bw, bh)
            and max(bw, bh) <= OTHER_SIDE[1]
            and abs(bw - bh) <= 1
            and OTHER_AREA[0] <= area <= OTHER_AREA[1]
        ):
            m[
                max(0, int(y) - MARK_R) : int(y) + MARK_R, max(0, int(x) - MARK_R) : int(x) + MARK_R
            ] = 0
    pad = CLIP_SLACK  # a window a few px bigger than the picture still fits
    p = cv2.copyMakeBorder(pic, pad, pad, pad, pad, cv2.BORDER_CONSTANT, value=0)
    if v.shape[0] > p.shape[0] or v.shape[1] > p.shape[1]:
        return None
    w = (p[:, :, 3] == 255).astype(np.float32)
    p = p[:, :, :3].astype(np.float32) / 255
    # sum over px of m*w*(v - p)^2, per channel, expanded into three correlations.
    d = sum(
        _corr(w, m * v[:, :, c] ** 2)
        - 2 * _corr(w * p[:, :, c], m * v[:, :, c])
        + _corr(w * p[:, :, c] ** 2, m)
        for c in range(3)
    )
    n = _corr(w, m)
    mse = np.where(n >= PIC_MIN_SOLID, np.maximum(d, 0) / np.maximum(n, 1) / 3, np.inf)
    y, x = np.unravel_index(np.argmin(mse), mse.shape)
    best = mse[y, x]
    near = 2 * int(MATCH_TOL)
    mse[max(0, y - near) : y + near + 1, max(0, x - near) : x + near + 1] = np.inf
    rival = mse.min()
    if best > PIC_MAX_MSE or rival < PIC_RATIO * best or rival - best < PIC_MARGIN:
        return None
    return float(x - pad), float(y - pad)


def fits(view: MinimapView, mm: Minimap) -> bool:
    """The window shows the whole map picture (not clipped)."""
    return view.size[0] >= mm.w / SCALE - CLIP_SLACK and view.size[1] >= mm.h / SCALE - CLIP_SLACK


def same_size(view: MinimapView, mm: Minimap | None) -> bool:
    """The view is this map's whole picture: its size within CLIP_SLACK px on both axes."""
    if mm is None:
        return False
    return all(
        abs(v - m / SCALE) <= CLIP_SLACK for v, m in zip(view.size, (mm.w, mm.h), strict=True)
    )


def by_size(maps: dict[str, MapInfo], title: str, view: MinimapView) -> MapInfo | None:
    """The one map titled `title` whose whole picture is the view's size, else None.

    Tells same-title neighbours apart (Maple Road / Mushroom Town: 88x47 vs 94x53 px).
    """
    hits = [m for m in maps.values() if m.title == title and same_size(view, m.minimap)]
    return hits[0] if len(hits) == 1 else None


def can_place(view: MinimapView, info: MapInfo, pic: np.ndarray | None = None) -> bool:
    """False where player_world is always None: no minimap, or clipped with no picture and
    too few markers."""
    mm = info.minimap
    spirals = sum(not p.hidden for p in info.portals)
    if mm is None:
        return False
    return fits(view, mm) or pic is not None or len(info.npcs) + spirals >= MIN_MATCH


def player_world(
    view: MinimapView, info: MapInfo, pic: np.ndarray | None = None
) -> tuple[float, float] | None:
    """The player's world position, or None when the minimap can't tell it for sure.

    A clipped window is placed by the map's picture `pic` (BGRA) if given, else by markers.
    """
    mm = info.minimap
    if mm is None:
        return None
    (vw, vh), (dx, dy) = view.size, view.dot
    if fits(view, mm):
        # A bigger view is another map's picture (a same-title neighbour): don't guess.
        return to_world((dx / vw, dy / vh), mm) if same_size(view, mm) else None
    s = picture_scroll(view, pic) if pic is not None else None
    if s is None:
        s = _scroll(view, info)
    if s is None:
        return None
    return (dx + s[0]) * SCALE - mm.cx, (dy + s[1]) * SCALE - mm.cy


def to_screen(
    pt: tuple[float, float],
    player: tuple[float, float],
    mm: Minimap,
    view: tuple[float, float],
) -> tuple[float, float]:
    """World point `pt` in normalized-frame pixels, the player being at world `player`.

    Sideways the camera follows the player and stops at the map's edges (centred on a
    map narrower than the view). Vertically it follows and stops only at the bottom.
    """
    # ponytail: the game camera lets the character drift up to ~128 px either side of
    # the centre mid-map (lag/dead zone), which the minimap doesn't show. At an edge where
    # the camera stops it is usually exact, but on some maps (Transfer Area, Line 1) the
    # camera's side bounds sit inside the minimap's, so x is ~100 px off there too.
    # Upgrade: find the character on screen by some read that isn't another player's
    # info, or per-map camera bounds, if the owner wants it tighter.
    half_w = view[0] * WORLD_PER_PX / 2
    if mm.w <= 2 * half_w:
        cx = mm.w / 2 - mm.cx
    else:
        cx = min(max(player[0], half_w - mm.cx), mm.w - mm.cx - half_w)
    # Not clamped at the minimap's top: in Transfer Area the camera goes ~330 units above
    # it (s2560b_043). The bottom clamp was never contradicted, so it stays.
    cy = min(player[1] + CAM_DY, mm.h - mm.cy - view[1] * WORLD_PER_PX / 2)
    return (
        (pt[0] - cx) / WORLD_PER_PX + view[0] / 2,
        (pt[1] - cy) / WORLD_PER_PX + view[1] / 2,
    )
