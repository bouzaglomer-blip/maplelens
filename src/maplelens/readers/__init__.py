"""Readers: screenshot -> value. Only the shared types live here for now."""

from dataclasses import dataclass


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
