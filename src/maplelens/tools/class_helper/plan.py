"""AP plan: where unspent AP go, and how far each stat is over or behind the plan."""

from collections.abc import Sequence
from dataclasses import dataclass

from maplelens.tools.class_helper.data import (
    STATS,
    Advance,
    Band,
    Build,
    GearRow,
    Item,
    JobPlan,
    Skill,
    SpStep,
    TrainRow,
)

MAX_MAPS = 3
ADVANCE_EARLY = 2


@dataclass(frozen=True)
class Advice:
    add: int = 0
    over: int = 0
    behind: int = 0


def band_at(build: Build, level: int) -> Band | None:
    """Bands are [from, to): edges are shared, so the later band wins (the last also takes 200)."""
    return next((b for b in reversed(build.ap) if b.from_level <= level <= b.to_level), None)


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


def training(plan: JobPlan, level: int) -> list[TrainRow]:
    rows = [r for r in plan.training if r.from_level <= level <= r.to_level]
    return rows[:MAX_MAPS]


def gear(build: Build, level: int) -> tuple[GearRow | None, GearRow | None]:
    i = sum(g.from_level <= level for g in build.gear)  # rows are in level order
    return (
        build.gear[i - 1] if i else None,
        build.gear[i] if i < len(build.gear) else None,
    )


def short(item: Item, stats: dict[str, int] | None) -> dict[str, int]:
    """Points missing per stat, judged on total stats (base + gear), as the game checks."""
    if stats is None:
        return {}
    return {
        k: n - stats.get(k, 0) for k, n in item.req.items() if k != "level" and stats.get(k, 0) < n
    }


def advance_due(plan: JobPlan, build: Build, level: int) -> Advance | None:
    adv = plan.advance_for(build)
    return adv if adv and level >= adv.level - ADVANCE_EARLY else None


def _jobs(adv: Advance) -> str:
    return " or ".join(f"{'an' if j[0] in 'AEIOU' else 'a'} {j}" for j in adv.next_jobs)


def advance_text(adv: Advance) -> str:
    return f"At {adv.level}: become {_jobs(adv)}"


def next_step(plan: JobPlan, build: Build, level: int) -> str | None:
    cands = []  # (milestone level, text); min() keeps the first on a tie
    if adv := plan.advance_for(build):
        cands.append((adv.level, f"become {_jobs(adv)}"))
    if nxt := gear(build, level)[1]:
        cands.append((nxt.from_level, f"get {nxt.item.name}"))
    if build.reset_at is not None and level <= build.reset_at:
        cands.append((build.reset_at, f"reset AP for the {build.name} build"))
    if not cands:
        return None
    at, text = min(cands, key=lambda c: c[0])
    return f"{'Now' if at <= level else f'At {at}'}: {text}"
