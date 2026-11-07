"""AP plan: where unspent AP go, and how far each stat is over or behind the plan."""

from collections.abc import Sequence
from dataclasses import dataclass

from maplelens.tools.class_helper.data import STATS, Band, Build, Skill, SpStep


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


def _walk(steps, levels, points, skills):  # -> dict | None (None: next point hits an unknown skill)
    lv = dict(levels)
    for _ in range(points):
        step = None
        for s in steps:
            if lv.get(s.skill, -1) >= s.up_to:
                continue
            req = skills[s.skill].requires
            if any(r not in lv for r in req):  # a prerequisite we can't see: can't tell if met
                return None
            if all(lv[r] >= n for r, n in req.items()):
                step = s
                break
        if step is None:
            break
        if step.skill not in lv:
            return None
        lv[step.skill] += 1
    return lv


def sp_advice(
    steps: Sequence[SpStep],
    levels: dict[int, int],
    unspent: int,
    skills: dict[int, Skill],
    tab: str,
) -> dict[int, Advice] | None:
    after = _walk(steps, levels, unspent, skills)
    if after is None:
        return None
    advice = {k: Advice(add=after[k] - v) for k, v in levels.items()}
    tab_ids = [k for k, sk in skills.items() if sk.job == tab]
    expected = None
    if all(k in levels for k in tab_ids):
        expected = _walk(steps, dict.fromkeys(tab_ids, 0), sum(levels.values()) + unspent, skills)
    planned = {s.skill for s in steps}
    for k, v in levels.items():
        if k not in planned:
            advice[k] = Advice(over=v)
        elif expected is not None:
            add = advice[k].add
            advice[k] = Advice(
                add=add, over=max(0, v - expected[k]), behind=max(0, expected[k] - v - add)
            )
    return advice
