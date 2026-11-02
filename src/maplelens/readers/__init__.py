"""Readers: screenshot -> value, plus the shared types and read_all."""

from dataclasses import dataclass

import numpy as np


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


def read_all(frame: np.ndarray, t: float) -> Reading:
    """Read every field from one game frame. Submodules load here, not at import time."""
    from maplelens.readers import exp, glyphs, job, level, map_name

    img = glyphs.normalize(frame)
    return Reading(
        t, exp.read_exp(img), level.read_level(img), job.read_job(img), map_name.read_map_name(img)
    )
