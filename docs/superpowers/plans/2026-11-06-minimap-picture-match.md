# Minimap Picture Match Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Place the player on scrolled minimaps by matching the visible minimap against a shipped picture of the whole map, and tell the player when the next portal is hidden.

**Architecture:** A one-off conversion (outside the repo) adds the OSMS Data Explorer minimap pictures as `data/minimaps/<id>.png` and a `hidden` flag on portals in our `maps.json`. `read_view` keeps the map-area pixels; `camera.player_world` tries a picture match first and falls back to today's marker match. `route.Trip` answers "is the next portal hidden?" and the Path tab shows a line for it.

**Tech Stack:** Python, numpy, OpenCV (`cv2.matchTemplate`), PySide6, pytest. No new dependency.

**Spec:** `docs/superpowers/specs/2026-11-06-minimap-picture-match-design.md`

## Global Constraints

- Screen-reading only: capture pixels and draw our own window. No game memory, game files, network or input. `uv run python scripts/check_screen_only.py` must pass. Don't write banned module or Win32 names in comments/docstrings under `src/` or `scripts/`.
- No new dependency. `cv2` and `numpy` are already in.
- Must work at **1366x768, 1920x1080 and 2560x1440** (owner, 2026-11-06).
- If the match isn't clear, return None (arrow hides). Never a confident wrong position.
- The conversion runs once **outside the repo** (scratchpad); only our files are committed. Pictures are downloaded from the website, never read from game files.
- Fixtures: cropped to the minimap panel (title plus map area), passed through `glyphs.normalize` first, no other players' dots, no names or chat. The owner reviews every new PNG before commit. Full-frame grabs never go in the repo.
- Every task ends green: `uv run pytest`, `uv run ruff check`, `uv run ruff format --check`, the guard.

## Review Focus

1. **Other players' or party dots inside the minimap window**: the scroll must come out the same as without them. Test: Task 2, `test_picture_scroll_ignores_painted_dots`.
2. **Repetitive art** (the tree columns on The Forest North of Ellinia): two scrolls score almost the same, so the answer must be None, not a guess. Test: Task 2, `test_picture_scroll_repeating_picture_is_none`.
3. **A view from another map** (a stale frame right after a portal, or a same-title neighbour): the match must fail (None), not snap to the best wrong spot. Test: Task 2, `test_picture_scroll_wrong_map_is_none`.
4. **Window stopped at the picture's edge** (scroll 0 or the maximum, give or take `CLIP_SLACK`): it must still match. Test: Task 2, the `bottom` and `top` fixtures in `test_player_world_by_picture_fixtures`.
5. **Both methods must agree where both work**: a Lith Harbor or Perion frame placed by its picture lands where its markers put it. Test: Task 2, `test_picture_and_markers_agree`.

---

### Task 1: Data: minimap pictures and hidden portals

**Files:**
- Create: `src/maplelens/data/minimaps/<9-digit id>.png` (generated)
- Modify: `src/maplelens/data/maps.json` (generated: `"hidden": true` on some portals)
- Modify: `src/maplelens/tools/path_arrow/maps.py`
- Modify: `README.md` (credit line, under the meowdb line at line 11), `AGENTS.md` (Layout: `data/minimaps/`)
- Test: `tests/test_maps.py`

**Interfaces:**
- Produces: `Portal(x: int, y: int, to: str, hidden: bool = False)`; `maps.PICTURES: Path` (the `data/minimaps` folder); `maps.picture(map_id: str) -> np.ndarray | None` (BGR, cached; None when there is no file).

- [ ] **Step 1: Run the conversion in the scratchpad (not committed).** Write a script in the scratchpad that, run with `python -I`:
  - downloads `https://osmsdataexplorer.com/data/current/portals.json` and `.../maps.json` into their own new folder;
  - for each map with a picture (`minimap` field in the site's `maps.json`, e.g. `images/maps/010002070.png` → `https://osmsdataexplorer.com/data/current/images/maps/010002070.png`) that is also in our `maps.json` with a non-null `minimap`, downloads it and keeps it only if its size is `round(w/16) × round(h/16)` ±1. It writes the kept ones to `src/maplelens/data/minimaps/<our 9-digit id>.png`. Ship **all** that pass, about 4.8 MB. The spec allows this when the window's largest size can't be pinned down, and it needs no guess at that size.
  - pairs each of our portals with the site's. Per map, the site's coordinates are ours plus one fixed `(dx, dy)`. Find it as the most common `(q.x - p.x, q.y - p.y)` over pairs with the same destination (`q.dest_map` zero-padded to 9 = `p.to`). Each of our portals then has exactly one site portal at that offset (checked 2026-11-06: 598/598, no exceptions). Set `"hidden": true` where that portal's `type == 1`, and leave the key out otherwise. Maps the site lacks keep no flags. Print the counts: expect 141 hidden of 598 paired, on 66 maps.
  - rewrites `maps.json` keeping its one-entry-per-line layout and key order, adding only `hidden`.
  The script asserts that every portal on a shared map pairs exactly once, and stops if one doesn't.

- [ ] **Step 2: Write the failing tests** in `tests/test_maps.py`:

```python
def test_shipped_pictures_match_minimap_size():
    maps = load()
    files = list(PICTURES.glob("*.png"))
    assert len(files) >= 250
    for f in files:
        mm = maps[f.stem].minimap
        h, w = picture(f.stem).shape[:2]
        assert abs(w - mm.w / 16) <= 1.5 and abs(h - mm.h / 16) <= 1.5, f.stem


def test_picture_missing_is_none():
    assert picture("999999999") is None


def test_forest_north_of_ellinia_hidden_portals():
    m = load()["010002070"]
    assert sum(p.hidden for p in m.portals) == 19
    assert {p.to for p in m.portals if not p.hidden} == {"010002060", "010004090"}
    assert picture("010002070").shape[:2] == (428, 130)
```

- [ ] **Step 3: Run:** `uv run pytest tests/test_maps.py -v`. Expected: FAIL (`PICTURES`/`picture` not defined).

- [ ] **Step 4: Implement** `Portal.hidden: bool = False` (it loads through the existing `Portal(**p)`), `PICTURES = Path(__file__).parents[2] / "data" / "minimaps"`, and `picture(map_id)` with `functools.cache`. Read with `cv2.imdecode(np.fromfile(path, np.uint8), cv2.IMREAD_COLOR)`, because `imread` fails on non-ASCII paths, the same problem `grab.py` notes for writing. Return None when the file doesn't exist.

- [ ] **Step 5: Docs.** README: under the meowdb line, add `> Minimap pictures and portal types from [OSMS Data Explorer](https://osmsdataexplorer.com).` In AGENTS.md's Layout, change the data line to `data/maps.json` — the map data; `data/minimaps/` — minimap pictures.

- [ ] **Step 6: Run** the full suite, ruff, format check and guard. Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add src/maplelens/data src/maplelens/tools/path_arrow/maps.py tests/test_maps.py README.md AGENTS.md
git commit -m "feat(path_arrow): ship minimap pictures and mark hidden portals"
```

---

### Task 2: Place the player by matching the picture

**Files:**
- Modify: `src/maplelens/readers/minimap_pos.py` (`MinimapView` keeps the pixels)
- Modify: `src/maplelens/tools/path_arrow/camera.py`
- Modify: `src/maplelens/tools/path_arrow/ui.py:319` and `:365` (pass the picture)
- Create: fixtures `tests/fixtures/screens/pos_fne_{bottom,mid,top}_{1366x768,1920x1080,2560x1440}_100.png`, `pos_town_{1366x768,1920x1080,2560x1440}_100.png`
- Test: `tests/test_camera.py`

**Interfaces:**
- Consumes: `maps.picture(map_id) -> np.ndarray | None` (Task 1).
- Produces:
  - `MinimapView.pixels: np.ndarray | None`, the normalized BGR map area (`size` wide and high). Declare it `field(default=None, compare=False, repr=False)` so equality and repr keep working.
  - `camera.picture_scroll(view: MinimapView, pic: np.ndarray) -> tuple[float, float] | None`: px scrolled into the picture, the same meaning as `_scroll`'s result.
  - `player_world(view, info, pic: np.ndarray | None = None)` and `can_place(view, info, pic: np.ndarray | None = None)`.

- [ ] **Step 1: Get the grabs (owner).** Stop and ask the owner for full-frame grabs with `uv run python scripts/grab.py --title <window> --label fne`. At each of 1366x768, 1920x1080 and 2560x1440 they need:
  - The Forest North of Ellinia with the character at the bottom, the middle and the top of the map;
  - one big town map (Henesys or Kerning City).

  That's 12 grabs, all with the minimap open and no other players near. Wait for them.

- [ ] **Step 2: Cut fixtures.** Normalize each grab (`glyphs.normalize`), then crop the minimap panel the way the existing `pos_*` fixtures are cropped, saving to the names above. Check that each crop shows no other player's dot, and show the owner every PNG before committing.

- [ ] **Step 3: Spike (scratchpad, throwaway).** For each fixture, take `read_view(img).pixels` and the map's `picture()`, and run a masked `cv2.matchTemplate`.
  - **Measure the true scroll by hand:** save the crop pasted onto the picture at the found scroll and look at it. On the bottom crops the two visible portals also give it through the existing `_scroll`.
  - **Pick the method:** the match mode, the mask, and two constants, `PIC_MAX_SCORE` (worst accepted best score) and `PIC_MARGIN` (how much better the best scroll must be than the best one more than `2 * MATCH_TOL` px away). They must hold at all three resolutions.
  - **Starting point:** mask boxes around the dot, the NPC markers and the spirals. Pad the picture by `CLIP_SLACK` px with `cv2.BORDER_REPLICATE` so a view a few px larger still fits, then take the pad off the result.
  - **If no setting gives one clear right answer** on all 12 crops, **stop** and report to the owner (spec, "Spike first").

- [ ] **Step 4: Write the failing tests** in `tests/test_camera.py`. `EXPECTED_SCROLL` holds the hand-measured `(sx, sy)` per fixture file from Step 3.

```python
@pytest.mark.parametrize("name", sorted(EXPECTED_SCROLL))
def test_player_world_by_picture_fixtures(name):
    view = read_view(cv2.imread(str(SCREENS / name)))
    info = load()["010002070"] if "fne" in name else load()[TOWN_ID]
    sx, sy = EXPECTED_SCROLL[name]
    want = ((view.dot[0] + sx) * 16 - info.minimap.cx, (view.dot[1] + sy) * 16 - info.minimap.cy)
    assert player_world(view, info, picture(info.id)) == approx(want, abs=32)  # 2 minimap px


def test_forest_north_mid_has_too_few_markers():  # why this exists: markers alone fail
    view = read_view(cv2.imread(str(SCREENS / "pos_fne_mid_2560x1440_100.png")))
    assert player_world(view, load()["010002070"]) is None


def test_picture_scroll_ignores_painted_dots():
    # paint three 6x6 dots in other players' red and party orange (colours from the grabs)
    # at spots away from our dot; same scroll as unpainted, within 0.5 px


def test_picture_scroll_repeating_picture_is_none():
    # a picture made of one 40x40 tile repeated 3x10, a view cut from it: None


def test_picture_scroll_wrong_map_is_none():
    view = read_view(cv2.imread(str(SCREENS / "pos_fne_mid_2560x1440_100.png")))
    assert picture_scroll(view, picture("010004000")) is None  # Perion's picture


def test_picture_and_markers_agree():
    for name, id in (("pos_e_2560x1440_100.png", "010000000"), ("pos_f_2560x1440_100.png", "010004000")):
        view, info = read_view(cv2.imread(str(SCREENS / name))), load()[id]
        assert player_world(view, info, picture(id)) == approx(player_world(view, info), abs=16)


def test_can_place_with_picture():
    view = MinimapView((200, 100), (100.0, 50.0), ())
    assert not can_place(view, big(npcs=()))
    assert can_place(view, big(npcs=()), np.zeros((100, 400, 3), np.uint8))
```

  The two comment-only tests are written out in full by the implementer, with the assertions their comments state. `TOWN_ID` is the town map the owner grabbed.

- [ ] **Step 5: Run:** `uv run pytest tests/test_camera.py -v`. Expected: the new tests FAIL (`pixels`/`picture_scroll` not defined).

- [ ] **Step 6: Implement.**
  - `read_view` sets `pixels=img.copy()`.
  - `picture_scroll` uses the Step 3 method and constants, each constant with a comment naming the fixtures it was set from, like the existing ones.
  - In `player_world`, for a clipped view: `s = picture_scroll(view, pic) if pic is not None and view.pixels is not None else None`, then `s = s or _scroll(view, info)`. The rest stays the same.
  - `can_place` returns True when `pic is not None` and the map has a minimap.
  - In `ui.py`, `_world` and `_why` pass `picture(here.id)` to both functions. The test maps' ids have no files, so the UI tests are unchanged.

- [ ] **Step 7: Run** the full suite, ruff, format check and guard. Expected: all pass, the old `pos_*` tests included.

- [ ] **Step 8: Commit**

```bash
git add src/maplelens/readers/minimap_pos.py src/maplelens/tools/path_arrow/camera.py src/maplelens/tools/path_arrow/ui.py tests/test_camera.py tests/fixtures/screens/pos_fne_* tests/fixtures/screens/pos_town_*
git commit -m "feat(path_arrow): place the player by matching the minimap picture"
```

---

### Task 3: Hidden portals: no phantom spirals, and a hint

**Files:**
- Modify: `src/maplelens/tools/path_arrow/camera.py` (`_scroll`, `can_place`)
- Modify: `src/maplelens/tools/path_arrow/route.py`
- Modify: `src/maplelens/tools/path_arrow/ui.py` (`_render`)
- Test: `tests/test_camera.py`, `tests/test_route.py`, `tests/test_path_ui.py`

**Interfaces:**
- Consumes: `Portal.hidden` (Task 1).
- Produces: `Trip.hidden_next(player: tuple[float, float] | None) -> bool`; `ui.HIDDEN = "Hidden portal: stand on it and press ↑"`.

- [ ] **Step 1: Write the failing tests.**

```python
# test_route.py (build a small graph the way the file's other tests do)
def test_hidden_next_follows_the_target():
    # here has a hidden portal to B at (0, 0) and a visible one to B at (1000, 0)
    assert trip.hidden_next((10, 0)) is True
    assert trip.hidden_next((990, 0)) is False
    assert trip.hidden_next(None) is False  # not every portal to B is hidden


def test_hidden_next_unknown_position_all_hidden():
    # here's only portal to B is hidden
    assert trip.hidden_next(None) is True


def test_hidden_next_cab_step_or_arrived_is_false(): ...


# test_camera.py
def test_hidden_portals_predict_no_spiral():
    # big() map whose only portals are hidden: two spirals seen where they'd be -> None
    # the same with hidden=False -> placed (as test_player_world_perion_by_portals_alone)


# test_path_ui.py: add mk("H", "Hollow", [(0, 0, "B", True)]) to MAPS (mk builds Portal(*p))
def test_hidden_portal_hint(make):
    tool = make()
    go(tool, "H", "B")
    feed(tool, title("H"), 1.0)
    assert tool._message.text() == HIDDEN and tool.arrow.isVisible()
```

- [ ] **Step 2: Run:** `uv run pytest tests/test_route.py tests/test_camera.py tests/test_path_ui.py -v`. Expected: the new tests FAIL.

- [ ] **Step 3: Implement.**
  - **`camera.py`:** `_scroll` predicts spirals only for `not p.hidden` portals. `can_place` counts only those portals too.
  - **`route.py`:**
    - `hidden_next` returns False when there's no route, the trip has arrived, or this step is a cab step.
    - With a position, it returns whether the portal `target` aims at is hidden. Pull out a helper, `_next_portals()`, that both `target` and `hidden_next` use.
    - With no position, it returns True only if every portal to the next map is hidden.
  - **`ui.py` `_render`:** the message shows `why` and `HIDDEN` (when `self.trip and self.trip.hidden_next(world)`), joined by a newline, and is visible if either is non-empty.

- [ ] **Step 4: Run** the full suite, ruff, format check and guard. Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/maplelens/tools/path_arrow tests/test_route.py tests/test_camera.py tests/test_path_ui.py
git commit -m "feat(path_arrow): hidden portals show no spiral and get a hint"
```

- [ ] **Step 6: Owner check in the game** (spec, "Done means"). Ask the owner to run `uv run maplelens` and check three things:
  1. A route from The Forest North of Ellinia into a Tree Dungeon shows the arrow at every height of the map.
  2. The hidden-portal line shows when the arrow points at a tree-dungeon entrance.
  3. The arrow still works on Henesys or Kerning City, and on a small map that fits.

  Also ask whether a type-3 portal they pass shows a swirl. If it doesn't, rerun the Task 1 conversion with type 3 counted as hidden and commit that. Report what they saw.
