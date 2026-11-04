from pathlib import Path

import cv2
from pytest import approx

from maplelens.readers.minimap_pos import MinimapView, read_view
from maplelens.tools.path_arrow import camera
from maplelens.tools.path_arrow.camera import player_world, to_screen, to_world
from maplelens.tools.path_arrow.maps import MapInfo, Minimap, load

MM = Minimap(2000, 1000, 1000, 500)
VIEW = (1366, 768)
SCREENS = Path(__file__).parent / "fixtures" / "screens"


def test_to_world_inverts_minimap_formula():
    x, y = 300, -120
    f = ((x + MM.cx) / MM.w, (y + MM.cy) / MM.h)
    assert to_world(f, MM) == approx((x, y))


def test_to_screen_centres_player_mid_map():
    assert to_screen((0, 0), (0, 0), MM, VIEW)[0] == approx(683)


def test_to_screen_clamps_at_left_edge():
    player = (-950, 0)  # 50 from the map's left edge
    assert to_screen(player, player, MM, VIEW)[0] == approx(50)


def test_to_screen_narrow_map_centres_map():
    mm = Minimap(1000, 1000, 400, 500)  # map centre at world x 100
    for px in (-300, 100, 500):
        assert to_screen((100, 0), (px, 0), mm, VIEW)[0] == approx(683)


def test_to_screen_no_clamp_at_map_top():
    player = (0, -MM.cy - 200)  # above the minimap's top: the camera still follows
    assert to_screen(player, player, MM, VIEW)[1] == approx(384 - camera.CAM_DY)


def test_to_screen_clamps_at_map_bottom():
    player = (0, MM.h - MM.cy - 10)
    assert to_screen(player, player, MM, VIEW)[1] == approx(768 - 10)


def test_camera_constants_from_spike():
    # Name-tag ground truth over 76 grabs on Transfer Area, Construction Site North,
    # Sunset Sky and Line 1 (1366, 1920, 2560): portal x within ~5 px of the visible
    # portal, feet settle at y 545 = 384 + 161. NPC marker offset: Construction Site North
    # and Henesys Townstreet; clipped-map scroll checked on Kerning City, Henesys, Perion
    # and Lith Harbor (all 26 frames within 0.2 minimap px of the picture shift).
    assert camera.WORLD_PER_PX == 1.0
    assert camera.CAM_DY == -161.0
    assert camera.SCALE == 16
    assert (camera.NPC_DX, camera.NPC_DY) == (-0.6, -6.9)


# A clipped map: picture 400x100 px, window 200x100 px.
BIG_MM = Minimap(6400, 1600, 800, 800)
NPCS = ((-400, 0), (800, -320), (1600, 160), (2400, -480), (4000, 0))


def marks(scroll, npcs=NPCS, mm=BIG_MM):
    """Where the window shows each NPC, scrolled by `scroll` px, if inside it."""
    out = []
    for x, y in npcs:
        mx = (x + mm.cx) / 16 + camera.NPC_DX - scroll
        my = (y + mm.cy) / 16 + camera.NPC_DY
        if 0 <= mx < 200 and 0 <= my < 100:
            out.append((mx, my))
    return tuple(out)


def big(npcs=NPCS):
    return MapInfo("1", "s", "n", True, BIG_MM, (), None, npcs)


def test_player_world_unclipped_uses_fraction():
    info = MapInfo("1", "s", "n", True, MM, (), None)
    view = MinimapView((125, 62), (62.5, 31.0), ())
    assert player_world(view, info) == approx(to_world((0.5, 0.5), MM))


def test_player_world_clipped_from_npc_markers():
    view = MinimapView((200, 100), (100.0, 50.0), marks(37))
    assert player_world(view, big()) == approx(((100 + 37) * 16 - 800, 50 * 16 - 800))


def test_player_world_too_few_markers_is_none():
    view = MinimapView((200, 100), (100.0, 50.0), marks(37)[:2])
    assert player_world(view, big()) is None


def test_player_world_ambiguous_is_none():
    # NPCs every 800 units: a shift of 50 px matches as well as the true one.
    npcs = tuple((x, 0) for x in range(-400, 5600, 800))
    view = MinimapView((200, 100), (100.0, 50.0), marks(60, npcs))
    assert player_world(view, big(npcs)) is None


def test_player_world_lith_harbor_fixture():
    # pos_e (s2560b_023): window 209 of 391 px, scrolled 146 px (picture shift vs a
    # frame scrolled 77 px: 69 px).
    view = read_view(cv2.imread(str(SCREENS / "pos_e_2560x1440_100.png")))
    info = load()["010000000"]
    assert len(view.npcs) >= 5
    x, _ = player_world(view, info)
    assert x == approx((view.dot[0] + 146) * 16 - info.minimap.cx, abs=16)


def test_player_world_perion_fixture():
    # pos_f (s2560b_021): window 112 of 193 px tall, stopped at the picture's bottom
    # (scrolled 80 px down); 203 of 204 px wide, so not scrolled sideways.
    view = read_view(cv2.imread(str(SCREENS / "pos_f_2560x1440_100.png")))
    mm = load()["010004000"].minimap
    got = player_world(view, load()["010004000"])
    want = (view.dot[0] * 16 - mm.cx, (view.dot[1] + 80) * 16 - mm.cy)
    assert got == approx(want, abs=16)
