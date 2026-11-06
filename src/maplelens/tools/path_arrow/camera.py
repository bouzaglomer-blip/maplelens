"""Minimap -> world position -> normalized-frame pixels (768 high)."""

import numpy as np

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
# An unclipped map area is within 1-2 px of w/16 x h/16; clipped ones lack 80+ px.
CLIP_SLACK = 4
# Matching NPC markers to the map's NPCs: a hit is within MATCH_TOL px on both axes;
# the scroll needs MIN_MATCH hits and MATCH_MARGIN more than any other scroll.
MATCH_TOL = 1.0
MIN_MATCH = 3
MATCH_MARGIN = 2


def to_world(f: tuple[float, float], mm: Minimap) -> tuple[float, float]:
    """Inverse of the map data's fx = (x + cx) / w, fy = (y + cy) / h."""
    return f[0] * mm.w - mm.cx, f[1] * mm.h - mm.cy


def _scroll(view: MinimapView, mm: Minimap, npcs) -> tuple[float, float] | None:
    """How far (px) a clipped window is scrolled into the map picture, or None.

    The window keeps the player centred and stops at the picture's edges, so the scroll
    is read from the NPC markers it shows against the map's NPC positions.
    """
    # ponytail: NPC markers only, so 46 of the 58 maps wider than the window (fewer than
    # MIN_MATCH NPCs, mostly hunting fields) always get None. Upgrade: also match the
    # portal spirals against `portals` (they sit at (0, -7) px from the portal).
    pred = [((x + mm.cx) / SCALE + NPC_DX, (y + mm.cy) / SCALE + NPC_DY) for x, y in npcs]
    room = (mm.w / SCALE - view.size[0], mm.h / SCALE - view.size[1])
    found = []
    for m in view.npcs:
        for p in pred:
            s = (p[0] - m[0], p[1] - m[1])
            if not all(-CLIP_SLACK <= s[i] <= max(room[i], 0) + CLIP_SLACK for i in (0, 1)):
                continue
            hits = [
                (q[0] - n[0], q[1] - n[1])
                for n in view.npcs
                for q in pred
                if abs(q[0] - n[0] - s[0]) <= MATCH_TOL and abs(q[1] - n[1] - s[1]) <= MATCH_TOL
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


def can_place(view: MinimapView, info: MapInfo) -> bool:
    """False where player_world is always None: no minimap, or clipped with too few NPCs."""
    mm = info.minimap
    return mm is not None and (fits(view, mm) or len(info.npcs) >= MIN_MATCH)


def player_world(view: MinimapView, info: MapInfo) -> tuple[float, float] | None:
    """The player's world position, or None when the minimap can't tell it for sure."""
    mm = info.minimap
    if mm is None:
        return None
    (vw, vh), (dx, dy) = view.size, view.dot
    if fits(view, mm):
        # A bigger view is another map's picture (a same-title neighbour): don't guess.
        return to_world((dx / vw, dy / vh), mm) if same_size(view, mm) else None
    s = _scroll(view, mm, info.npcs)
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
