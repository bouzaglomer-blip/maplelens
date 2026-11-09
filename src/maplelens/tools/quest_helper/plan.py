"""Quest rows: the places to go for one quest. Pure logic, no Qt."""

from collections.abc import Callable, Collection
from dataclasses import dataclass

from .data import Item, Mob, Npc, Quest, QuestData

NEAR_TIE = 0.8  # a map with this share of the top spawn count counts as tied

NO_ITEM = "Where to get it: unknown"
NO_SPAWN = "Where it spawns: unknown"
NOT_LISTED = "Not in the map list yet"

TIMES = chr(0xD7)  # the multiplication sign

Hops = Callable[[str], int | None]  # map changes from the player; None: unknown or no route


@dataclass(frozen=True)
class Target:
    title: str
    sub: str
    map_id: str | None  # None: not clickable
    at: tuple[int, int] | None
    npc: str | None  # the NPC's name, for the arrival line
    info: bool  # sub is a grey info line


def _hops(hops: Hops, map_id: str) -> float:
    h = hops(map_id)
    return float("inf") if h is None else h


def best_map(spawns: dict[str, int], listed: Collection[str], hops: Hops) -> str | None:
    here = {m: c for m, c in spawns.items() if m in listed}
    if not here:
        return None
    top = max(here.values())
    near = [m for m, c in here.items() if c >= NEAR_TIE * top]
    return min(near, key=lambda m: (_hops(hops, m), -here[m], m))


def npc_place(npc: Npc, listed: Collection[str], hops: Hops) -> tuple[str, int, int] | None:
    here = [p for p in npc.places if p[0] in listed]
    return min(here, key=lambda p: (_hops(hops, p[0]), p), default=None)


def find_quest(data: QuestData, name: str) -> Quest | None:
    found = [q for q in data.quests.values() if q.name == name]
    return found[0] if len(found) == 1 else None


def shared_name(data: QuestData, name: str) -> bool:
    return sum(q.name == name for q in data.quests.values()) > 1


def show_giver(taken: bool | None, tracked: bool) -> bool:
    return not taken if taken is not None else not tracked


def also_for(map_id: str, others: list[tuple[str, list[Target]]]) -> list[str]:
    return [name for name, ts in others if any(t.map_id == map_id for t in ts)]


def _mob_map(data: QuestData, mob: Mob, hops: Hops) -> str | None:
    return best_map(mob.spawns, data.map_names.keys(), hops)


def _info(title: str, why: str) -> Target:
    return Target(title, why, None, None, None, True)


def _npc_row(data: QuestData, npc_id: int, suffix: str, hops: Hops) -> Target:
    npc = data.npcs[npc_id]
    p = npc_place(npc, data.map_names.keys(), hops)
    if p is None:
        return Target(npc.name, NOT_LISTED, None, None, npc.name, True)
    sub = f"{data.map_names[p[0]]} · {suffix}" if suffix else data.map_names[p[0]]
    return Target(npc.name, sub, p[0], (p[1], p[2]), npc.name, False)


def _top_dropper(data: QuestData, ids: list[int], hops: Hops) -> Mob:
    # most spawns on its best map; one with no listed map comes last
    def key(m: Mob) -> tuple[int, int]:
        b = _mob_map(data, m, hops)
        return (0, -m.spawns[b]) if b else (1, 0)

    return min((data.mobs[i] for i in ids), key=key)


def _loose_item(data: QuestData, item: Item, n: int, hops: Hops) -> Target:
    """The row for a quest item that doesn't ride on one of the quest's monsters."""
    title = f"{item.name} {TIMES}{n}"
    if item.drops:
        m = _top_dropper(data, list(item.drops), hops)
        b = _mob_map(data, m, hops)
        if b is None:
            return _info(title, NOT_LISTED if m.spawns else NO_SPAWN)
        return Target(title, f"{m.name} · {data.map_names[b]}", b, None, None, False)
    if item.shops:
        listed = data.map_names.keys()
        shops = [(npc_place(data.npcs[i], listed, hops), data.npcs[i].name) for i in item.shops]
        shops = [(p, npc) for p, npc in shops if p]
        if not shops:
            return _info(title, NOT_LISTED)
        p, npc = min(shops, key=lambda s: (_hops(hops, s[0][0]), s[0]))
        return Target(title, f"{npc} · {data.map_names[p[0]]}", p[0], (p[1], p[2]), npc, False)
    return _info(title, NO_ITEM)


def targets(data: QuestData, quest: Quest, *, giver: bool, hops: Hops) -> list[Target]:
    on_mob: dict[int, list[str]] = {i: [] for i, _ in quest.mobs}
    loose: list[Target] = []
    for item_id, n in quest.items:
        if item_id in quest.start_items:
            continue
        item = data.items[item_id]
        mine = [i for i in item.drops if i in on_mob]
        if mine:
            m = _top_dropper(data, mine, hops)
            on_mob[m.id].append(f"{item.name.removeprefix(m.name + ' ')} {TIMES}{n}")
        else:
            loose.append(_loose_item(data, item, n, hops))

    rows: list[Target] = []
    same = quest.giver is not None and quest.giver == quest.taker
    if giver and quest.giver is not None:
        rows.append(_npc_row(data, quest.giver, "" if same else "gives the quest", hops))
    for mob_id, count in quest.mobs:
        mob = data.mobs[mob_id]
        title = " · ".join([f"{mob.name} {TIMES}{count}", *on_mob[mob_id]])
        b = _mob_map(data, mob, hops)
        if b:
            rows.append(Target(title, data.map_names[b], b, None, None, False))
        else:
            rows.append(_info(title, NOT_LISTED if mob.spawns else NO_SPAWN))
    rows += loose
    if quest.taker is not None and not (giver and same):
        rows.append(_npc_row(data, quest.taker, "hand in", hops))
    return rows
