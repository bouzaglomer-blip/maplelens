"""A quest's rewards as the Quests tab shows them: the closed line and the opened groups."""

from dataclasses import dataclass

from maplelens.tools.quest_helper.data import Quest, QuestData
from maplelens.tools.quest_helper.plan import TIMES

EN_DASH = chr(0x2013)

_BRANCHES = {
    "Beginner": ("Beginner",),
    "Warrior": (
        "Warrior Fighter Page Spearman Crusader White_Knight Dragon_Knight Hero Paladin Dark_Knight"
    ),
    "Magician": (
        "Magician Wizard_(Fire,_Poison) Wizard_(Ice,_Lightning) Cleric Mage_(Fire,_Poison) "
        "Mage_(Ice,_Lightning) Priest Arch_Mage_(Fire,_Poison) Arch_Mage_(Ice,_Lightning) Bishop"
    ),
    "Bowman": "Bowman Hunter Crossbowman Ranger Sniper Bowmaster Marksman",
    "Thief": "Thief Rogue Assassin Bandit Hermit Chief_Bandit Night_Lord Shadower",
}
BRANCH = {
    j.replace("_", " "): b
    for b, jobs in _BRANCHES.items()
    for j in (jobs.split() if isinstance(jobs, str) else jobs)
}


def branch(job: str | None) -> str | None:
    return BRANCH.get(job) if job else None


@dataclass(frozen=True)
class Shown:
    item: int
    name: str
    count: int
    tip: str  # hover text


@dataclass(frozen=True)
class Group:
    label: str  # "" for the items a quest always gives
    items: tuple[Shown, ...]


def _shown(data: QuestData, r, by_class: bool = False) -> Shown:
    item = data.items.get(r.item)
    name = item.name if item else f"Item {r.item}"
    tip = name + (f" {TIMES}{r.count}" if r.count > 1 else "")
    if by_class and r.cls:
        tip += f" ({r.cls})"
    if r.gender:
        tip += f" ({r.gender})"
    return Shown(r.item, name, r.count, tip)


def _money(exp: int, mesos: int) -> str:
    return " · ".join(
        p for p in (f"{exp:,} EXP" if exp else "", f"{mesos:,} mesos" if mesos else "") if p
    )


def _contribution(quest: Quest) -> str | None:
    c = quest.rewards.contribution
    if not c:
        return None
    town, low, high = c
    return f"{town} contribution +{low}" + (f"{EN_DASH}{high}" if high != low else "")


def chain_rest(data: QuestData, quest: Quest) -> list[Quest]:
    """Quests of this quest's chain that come after it, following `after` links only."""
    if not quest.chain:
        return []
    found: set[int] = {quest.id}
    grew = True
    while grew:
        grew = False
        for q in data.quests.values():
            if q.chain == quest.chain and q.id not in found and found.intersection(q.after):
                found.add(q.id)
                grew = True
    found.discard(quest.id)
    return [q for q in data.quests.values() if q.id in found]


def details(data: QuestData, quest: Quest, branch: str | None) -> tuple[Group | str, ...]:
    items = quest.rewards.items
    plain = [r for r in items if not r.cls]
    out: list[Group | str] = []
    for kind, label in (("always", ""), ("pick", "You pick 1 of:"), ("random", "Random, 1 of:")):
        if group := tuple(_shown(data, r) for r in plain if r.kind == kind):
            out.append(Group(label, group))
    classed = [r for r in items if r.cls and (branch is None or r.cls == branch)]
    if classed:
        label = "By class:" if branch is None else "For your class:"
        out.append(Group(label, tuple(_shown(data, r, branch is None) for r in classed)))
    if line := _contribution(quest):
        out.append(line)
    rest = chain_rest(data, quest)
    if rest:
        n = len(rest)
        money = _money(sum(q.rewards.exp for q in rest), sum(q.rewards.mesos for q in rest))
        out.append(f"Rest of chain ({n} quest{'s' * (n > 1)}): +{money}".rstrip(" +"))
    return tuple(out)


def summary(data: QuestData, quest: Quest) -> str:
    if money := _money(quest.rewards.exp, quest.rewards.mesos):
        return money
    first = next((x for x in details(data, quest, None) if isinstance(x, Group)), None)
    if first:
        return first.items[0].tip if len(first.items) == 1 else f"{len(first.items)} items"
    return _contribution(quest) or ""
