"""Readers: screenshot -> value, plus the shared types and read_all."""

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from maplelens.readers.minimap_pos import MinimapView
    from maplelens.readers.stat_window import StatWindow


@dataclass(frozen=True)
class ExpValue:
    raw: int
    pct: float


@dataclass(frozen=True)
class Reading:
    t: float
    exp: ExpValue | None
    level: int | None
    job: str | None
    map_name: str | None
    player: tuple[float, float] | None = None  # see minimap_pos.read_player
    minimap: "MinimapView | None" = None  # see minimap_pos.read_view
    stats: "StatWindow | str | None" = None  # see stat_window.read_stat_window


def read_all(frame: np.ndarray, t: float) -> Reading:
    """Read every field from one game frame. Submodules load here, not at import time."""
    from maplelens.readers import exp, glyphs, job, level, map_name, minimap_pos, stat_window

    img = glyphs.normalize(frame)
    view = minimap_pos.read_view(img)
    return Reading(
        t,
        exp.read_exp(img),
        level.read_level(img),
        job.read_job(img, frame),
        map_name.read_map_name(img, frame),
        None if view is None else view.fraction,
        view,
        stat_window.read_stat_window(img, frame, frame.shape[0] / glyphs.BASE_H),
    )
