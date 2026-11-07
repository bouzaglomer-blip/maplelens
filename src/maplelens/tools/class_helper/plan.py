"""AP plan: where unspent AP go, and how far each stat is over or behind the plan."""

from dataclasses import dataclass

from maplelens.tools.class_helper.data import STATS, Band, Build


@dataclass(frozen=True)
class Advice:
    add: int = 0
    over: int = 0
    behind: int = 0


def band_at(build: Build, level: int) -> Band | None:
    return next((b for b in build.ap if b.from_level <= level <= b.to_level), None)


def ap_advice(band: Band, level: int, stats: dict[str, int], unspent: int) -> dict[str, Advice]:
    plan = [*band.hold, band.rest]
    budget = sum(stats[k] for k in plan) + unspent  # points the plan's stats share
    expected, left = {}, budget
    for k, target in band.targets(level).items():  # holds in data order
        expected[k] = min(target, left)
        left -= expected[k]
    expected[band.rest] = left
    adds, left = {}, unspent
    for k in plan:  # holds first, the rest last
        adds[k] = min(max(0, expected[k] - stats[k]), left)
        left -= adds[k]
    advice = {k: Advice() for k in STATS}
    for k in plan:
        advice[k] = Advice(
            add=adds[k],
            over=max(0, stats[k] - expected[k]),
            behind=max(0, expected[k] - stats[k] - adds[k]),
        )
    return advice
