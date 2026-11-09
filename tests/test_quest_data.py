import json
from pathlib import Path

from maplelens.tools.quest_helper.data import DATA, MAPS, load

SMALL = Path(__file__).parent / "fixtures" / "quests_small.json"
MAP_JSON = json.loads(MAPS.read_text("utf-8"))


def test_loads_small_fixture():
    d = load(SMALL, MAPS)
    q = d.quests[1001]
    assert (q.giver, q.taker) == (2, 1)
    assert q.mobs == ((2, 3),) and q.items == ((4000001, 10), (4031000, 1))
    assert q.start_items == (4031000,)
    assert d.npcs[1].places == (("000000001", -46, 280),)
    assert d.mobs[2].spawns == {"000000040": 6}
    assert d.items[4000001].drops == (2,) and d.items[4031000].shops == (1,)
    assert d.map_names["000000001"] == "Mushroom Town - West Entrance"


def test_every_reference_resolves():
    d = load()
    for q in d.quests.values():
        assert {q.giver, q.taker} - {None} <= d.npcs.keys()
        assert {m for m, _ in q.mobs} <= d.mobs.keys()
        assert {i for i, _ in q.items} | set(q.start_items) <= d.items.keys()
    for i in d.items.values():
        assert set(i.drops) <= d.mobs.keys() and set(i.shops) <= d.npcs.keys()


def test_npc_places_are_map_markers():
    marks = {m["id"]: {(n["x"], n["y"]) for n in m["npcs"]} for m in MAP_JSON}
    for n in load().npcs.values():
        for map_id, x, y in n.places:
            assert (x, y) in marks[map_id], (n.name, map_id)


def test_kept_quests():
    d = load()
    assert len(d.quests) > 150  # Classic has 179 outside events, citizenship and crafting
    assert not [q for q in d.quests.values() if "Citizen" in q.name]
    q = d.quests[1001]
    assert q.start_items == (4031000,)
    assert (q.giver, q.taker) == (2, 1)
    assert d.npcs[1].name == "Heena"


def test_every_quest_has_somewhere_to_go():
    for q in load().quests.values():
        assert q.giver or q.taker or q.mobs or q.items, q.id


def test_default_path_is_the_shipped_file():
    assert DATA.name == "quests.json"
