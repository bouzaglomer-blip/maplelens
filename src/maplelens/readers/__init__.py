"""Readers: screenshot -> value, plus the shared types and read_all."""

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from maplelens.readers.minimap_pos import MinimapView
    from maplelens.readers.skill_window import SkillWindow
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
    skills: "SkillWindow | str | None" = None  # see skill_window.read_skill_window


def read_all(frame: np.ndarray, t: float) -> Reading:
    """Read every field from one game frame. Submodules load here, not at import time."""
    from maplelens.readers import (
        exp,
        glyphs,
        job,
        level,
        map_name,
        minimap_pos,
        skill_window,
        stat_window,
    )

    img = glyphs.normalize(frame)
    view = minimap_pos.read_view(img)
    return Reading(
        t,
        exp.read_exp(img),
        level.read_level(img),
        job.read_job(img),
        map_name.read_map_name(img),
        None if view is None else view.fraction,
        view,
        stat_window.read_stat_window(img),
        skill_window.read_skill_window(img),
    )
