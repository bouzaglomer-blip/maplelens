from maplelens.tools.path_arrow.maps import MapInfo, Minimap, Portal, find, load, search

MINIMAP = Minimap(100, 100, 50, 50)


def M(id, street, name, portals=(), cab=None, minimap=MINIMAP):
    return MapInfo(id, street, name, False, minimap, tuple(portals), cab)


def test_shipped_data_loads():
    maps = load()
    assert len(maps) >= 450
    for m in maps.values():
        for p in m.portals:
            assert p.to in maps
        if m.cab:
            assert all(t in maps for t in m.cab.to)
    cab_titles = {m.title for m in maps.values() if m.cab}
    assert {
        "Victoria Road / Henesys",
        "Victoria Road / Ellinia",
        "Victoria Road / Kerning City",
        "Victoria Road / Perion",
        "Dungeon / Sleepywood",
    } <= cab_titles


def test_find_unique():
    assert find(load(), "Dungeon / Sleepywood", None).name == "Sleepywood"


def test_find_duplicate_uses_previous():
    a = M("A", "Maple Road", "Mushroom Town")
    b = M("B", "Maple Road", "Mushroom Town")
    p = M("P", "X", "P", portals=[Portal(0, 0, "B")])
    maps = {m.id: m for m in (a, b, p)}
    title = "Maple Road / Mushroom Town"
    assert find(maps, title, "P") is b
    assert find(maps, title, None) is None
    assert find(maps, title, "X") is None


def test_find_unknown_is_none():
    assert find(load(), "Nowhere / Nothing", None) is None


def test_search():
    maps = load()
    res = search(maps, "ant tun")
    assert res and all("Ant Tunnel" in m.name for m in res)
    assert search(maps, "") == [] and search(maps, "   ") == []
    a = M("1", "S", "Zed Ant")
    b = M("2", "S", "Ant Hill")
    c = M("3", "S", "Ant Alpha")
    small = {m.id: m for m in (a, b, c)}
    assert [m.id for m in search(small, "ANT")] == ["3", "2", "1"]
    assert len(search(small, "ant", limit=2)) == 2
