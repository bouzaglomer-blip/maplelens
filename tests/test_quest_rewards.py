from dataclasses import replace

from maplelens.readers.job import JOBS
from maplelens.tools.quest_helper.data import load
from maplelens.tools.quest_helper.rewards import (
    BRANCH,
    Group,
    Shown,
    branch,
    chain_rest,
    details,
    summary,
)


def test_summary():
    d = load()
    assert summary(d, d.quests[10201]) == "7,020 EXP · 1,140 mesos"
    assert summary(d, d.quests[506001]) == "334 EXP · 409 mesos"
    assert "Henesys contribution +100–325" in details(d, d.quests[506001], None)
    assert (
        summary(
            d, replace(d.quests[10600], rewards=replace(d.quests[10600].rewards, exp=0, mesos=0))
        )
        == "Blue Potion ×20"
    )


def test_random_group_and_chain():
    d = load()
    out = details(d, d.quests[10201], None)
    assert out[0].label == "Random, 1 of:" and len(out[0].items) == 6
    assert out[0].items[0].tip == "Bronze Ore ×7"
    assert out[-1] == "Rest of chain (4 quests): +28,080 EXP · 4,560 mesos"
    assert [q.id for q in chain_rest(d, d.quests[10204])] == [10205]
    last = details(d, d.quests[10205], None)  # the last of its chain: no chain line
    assert not any(isinstance(x, str) and x.startswith("Rest of chain") for x in last)


def test_class_items():
    d = load()
    mine = details(d, d.quests[10205], "Thief")
    assert mine[0] == Group("For your class:", (Shown(1002156, "Dark Pilfer", 1, "Dark Pilfer"),))
    every = details(d, d.quests[10205], None)
    assert every[0].label == "By class:" and every[0].items[0].tip == "Old Wisconsin (Beginner)"


def test_pick_and_always():
    d = load()
    mage = [x for x in details(d, d.quests[10401], "Magician") if isinstance(x, Group)]
    assert [g.label for g in mage] == ["For your class:"]  # Blackbull: class-only picks
    assert [s.item for s in mage[0].items] == [2043702, 2043802]
    assert details(d, d.quests[10600], None)[0] == Group(
        "", (Shown(2000003, "Blue Potion", 20, "Blue Potion ×20"),)
    )


def test_branch():
    assert branch("Rogue") == "Thief" and branch("Arch Mage (Ice, Lightning)") == "Magician"
    assert branch(None) is None and set(BRANCH) == JOBS
