"""Plan the fewest-hop route between maps, and keep a trip in step with the player."""

import math
from collections import deque
from dataclasses import dataclass

from maplelens.tools.path_arrow.maps import MapInfo


@dataclass(frozen=True)
class Step:
    map_id: str
    cab: bool  # leave this map by its cab


def _edges(m: MapInfo, taxi: bool):
    for p in m.portals:
        yield p.to, False
    if taxi and m.cab:
        for to in m.cab.to:
            yield to, True


def plan(maps: dict[str, MapInfo], start: str, goal: str, taxi: bool) -> list[Step] | None:
    if start not in maps:
        return None
    came: dict[str, tuple[str, bool] | None] = {start: None}
    queue = deque([start])
    while queue and goal not in came:
        cur = queue.popleft()
        for to, cab in _edges(maps[cur], taxi):
            if to in maps and to not in came:
                came[to] = (cur, cab)
                queue.append(to)
    if goal not in came:
        return None
    steps = [Step(goal, False)]
    while (prev := came[steps[0].map_id]) is not None:
        steps.insert(0, Step(prev[0], prev[1]))
    return steps


class Trip:
    def __init__(self, maps: dict[str, MapInfo], start: str, goal: str, taxi: bool):
        self.maps, self.goal, self.taxi = maps, goal, taxi
        self.steps = plan(maps, start, goal, taxi)
        self.index = 0

    def on_map(self, map_id: str) -> None:
        if self.steps and self.steps[self.index].map_id == map_id:
            return
        for i, s in enumerate(self.steps or ()):
            if s.map_id == map_id:
                self.index = i
                return
        self.steps = plan(self.maps, map_id, self.goal, self.taxi)
        self.index = 0

    @property
    def arrived(self) -> bool:
        return self.steps is not None and self.steps[self.index].map_id == self.goal

    def target(self, player: tuple[float, float]) -> tuple[int, int] | None:
        if self.steps is None or self.arrived:
            return None
        here = self.maps[self.steps[self.index].map_id]
        if self.steps[self.index].cab:
            return (here.cab.x, here.cab.y)
        nxt = self.steps[self.index + 1].map_id
        hits = [p for p in here.portals if p.to == nxt]
        best = min(hits, key=lambda p: math.dist(player, (p.x, p.y)))
        return (best.x, best.y)
