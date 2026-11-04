# Path Arrow + Overlay Tabs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A Path tab in the overlay box where you pick a destination map, and a plain arrow over your character that points at the next portal (or Regular Cab) on every map until you arrive. The box gets one tab per tool and a new look for the EXP tab.

**Architecture:** A bundled `maps.json` in our own format feeds pure modules: `maps.py` (load, find by read name, search), `route.py` (fewest-hop plan, a running `Trip`), and `camera.py` (minimap fraction → world → screen). A new pure reader, `readers/minimap_pos.py`, finds the yellow "you" dot. `overlay.Box` gains tabs. The app owns the box and adds the EXP tab, then the Path tab. The arrow is a child widget of the existing click-through `Layer`.

**Tech Stack:** Python 3.12, uv, ruff, pytest, numpy, opencv-python-headless, PySide6 (all already installed). No new dependency.

**Spec:** `docs/superpowers/specs/2026-11-04-path-arrow-design.md`. Read it first; this plan points at its sections instead of repeating them. Mockups: https://claude.ai/artifact/SVf4ei24LGX6btFXyErtjJ

## Global Constraints

- Screen-only rule (`AGENTS.md`). `uv run python scripts/check_screen_only.py` passes after every task. Don't write banned module or Win32 names under `src/` or `scripts/`, comments included.
- No new dependency. No network access at runtime. No reading of game files.
- MapleLens never focuses, activates or brings forward the game window. MapleLens windows refuse focus (`Qt.WindowDoesNotAcceptFocus`) **except** the box while its search field is in use (Task 5, `Box.allow_typing`).
- Values from the spec: "Arrived at …" shows **5 s**; "Open your minimap…" after **3 s** of no map name; a map-name change counts once seen on **2 consecutive readings**; Use taxi defaults **on**, saved as `settings["path_taxi"]`.
- Exact copy (spec): `Open your minimap to see the arrow`, `This map isn't in MapleLens's map list yet`, `No minimap on this map`, `Arrived at {name}`, `To {destination} · {n} of {total}`, `From: {name} (where you are)`, `Use taxi`, `Start`, `Stop`. Added here: `From: (can't read your map yet)` and `No route from here to {destination}`.
- `{name}` in tab copy is the map's `name` only (e.g. `Ant Tunnel I`). The route list shows `name` too.
- The box keeps its settings key `"exp_meter"` under `settings["boxes"]`, so nobody's box moves.
- Fixtures: `tests/fixtures/screens/<reader>_<case>_<W>x<H>_100.png`, cropped, no names, chat or other players. The owner reviews each new PNG before commit. Full-frame grabs (`%APPDATA%\MapleLens\grabs\`, 129 of them today) **never** go in the repo, and neither does anything drawn on them.
- Line length 100, ruff `E,F,I,UP,B`. Commits end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Current branch; never push.

## Review Focus

1. **Other dots on the minimap** (party, other players, NPCs, portals) taken for "you". Expected: only the yellow dot counts. → `test_read_player_ignores_other_dots` (Task 2).
2. **The map name blinks to None or misreads for one frame during a map change.** Expected: no reroute and no advance on a single reading. → `test_one_frame_misread_does_not_reroute` (Task 6).
3. **A portal back to a map earlier on the route.** Expected: the route rewinds to that map, with no reroute and no list rebuilt. → `test_trip_back_to_earlier_map_rewinds` (Task 4).
4. **Start pressed while already standing on the destination.** Expected: "Arrived at …" straight away, no crash, no arrow. → `test_trip_start_at_goal_arrives` (Task 4).
5. **Game window resized mid-route.** Expected: the arrow stays over the character at the new size. → `test_arrow_follows_game_rect_size` (Task 6).

---

### Task 1: Our map data file + `maps.py`

**Files:**
- Create: `src/maplelens/tools/path_arrow/__init__.py` (empty), `src/maplelens/tools/path_arrow/maps.json`, `src/maplelens/tools/path_arrow/maps.py`
- Test: `tests/test_maps.py`

**Interfaces:**
- Produces (all frozen dataclasses in `maps.py`):
  - `Portal(x: int, y: int, to: str)`, `Cab(x: int, y: int, to: tuple[str, ...])`, `Minimap(w: int, h: int, cx: int, cy: int)`
  - `MapInfo(id: str, street: str, name: str, town: bool, minimap: Minimap | None, portals: tuple[Portal, ...], cab: Cab | None)` with property `title -> str` = `f"{street} / {name}"`, the map-name reader's format.
  - `DATA: Path` (the bundled file), `load(path: Path = DATA) -> dict[str, MapInfo]` keyed by id.
  - `find(maps: dict[str, MapInfo], title: str, previous: str | None) -> MapInfo | None`
  - `search(maps: dict[str, MapInfo], text: str, limit: int = 8) -> list[MapInfo]`

- [ ] **Step 1: Convert the data (one-off, outside the repo).** Download `https://meowdb.com/_data/maps.json` into a new empty folder in the scratchpad. Write the converter in a *different* scratchpad folder and run it with `python -I`. Output is the spec's "Map data file" format, a JSON list with **one map per line**, so diffs stay readable. Rules:
  - keep a portal only if it has a `toMapId` that is another map present in the data; report how many were dropped;
  - `minimap` is null when `hasMinimapImage` is false;
  - `cab`: the NPC named `Regular Cab` (the source also treats NPC id `104` on map `010000000` as a cab; include it the same way). `cab.to` = every other cab map's id. Print the cab maps' titles for the owner;
  - drop every other source field. Neither the converter nor the source file goes in the repo.
- [ ] **Step 2: Write failing tests** in `tests/test_maps.py`. Build small hand-made `MapInfo` dicts with a helper `M(id, street, name, portals=(), cab=None, minimap=Minimap(100, 100, 50, 50))`.
  - `test_shipped_data_loads`: `len(load()) >= 450`. Every `portal.to` and every `cab.to` id is a key. `{"Victoria Road / Henesys", "Victoria Road / Ellinia", "Victoria Road / Kerning City", "Victoria Road / Perion", "Dungeon / Sleepywood"}` ⊆ titles of maps with a cab.
  - `test_find_unique`: `find(maps, "Dungeon / Sleepywood", None).name == "Sleepywood"`.
  - `test_find_duplicate_uses_previous`: two `"Maple Road / Mushroom Town"` maps A and B, and P with a portal to B. `find(..., previous="P")` is B. `find(..., previous=None)` and `find(..., previous="X")` are None.
  - `test_find_unknown_is_none`.
  - `test_search`: case-insensitive substring of `name` or `street`. `search(load(), "ant tun")` is non-empty and every result's name contains "Ant Tunnel". Results whose name *starts with* the text come first, then the rest by name. `search(maps, "")` and `search(maps, "   ")` are `[]`. At most `limit` results.
- [ ] **Step 3:** Run `uv run pytest tests/test_maps.py -v`. Expected: FAIL (module missing).
- [ ] **Step 4:** Implement `maps.py`. `load` builds the dataclasses from the JSON (tuples, not lists).
- [ ] **Step 5:** Run it again: PASS. Then the full suite, ruff, `ruff format --check` and the guard.
- [ ] **Step 6: Commit** (`feat(path_arrow): map data and lookup`).

### Task 2: Player position reader

**Files:**
- Create: `src/maplelens/readers/minimap_pos.py`, fixtures `tests/fixtures/screens/minimap_pos_*_*.png`
- Modify: `src/maplelens/readers/__init__.py` (`Reading`, `read_all`), `tests/test_readers.py`

**Interfaces:**
- Consumes: `glyphs.find_anchor`, `glyphs.normalize`, and the anchors `minimap_title`/`minimap_bar` that `map_name.py` uses. Reuse `map_name.BAND_W`/`BAND_H`.
- Produces: `read_player(frame: np.ndarray) -> tuple[float, float] | None`, taking a normalized frame and returning the dot's centre as `(fx, fy)` fractions of the minimap's **map area** (0..1 each). `Reading` gains a last field `player: tuple[float, float] | None = None`, which `read_all` fills.

- [ ] **Step 1: Cut fixtures** from the owner's grabs, each passed through `normalize` first. Crop the minimap panel (title plus map area) and nothing else. Use only frames where **no other player's dot** is in the map area. Cases: `minimap_pos_a/b/c_<res>_100.png` (at least two resolutions, at least two maps, the dot in different places), `minimap_pos_bar_*` (bar form → None), `minimap_pos_covered_*` (map area covered → None), `minimap_pos_nominimap_*` (→ None). Write `EXPECTED_POS` by measuring the dot centre and the map area in each image yourself.
- [ ] **Step 2: Write failing tests** in `tests/test_readers.py`:
  - `test_read_player` parametrized over `EXPECTED_POS`, within `0.02` on each axis. Keys must equal the `minimap_pos_*` files.
  - `test_read_player_ignores_other_dots` (Review Focus 1): copy fixture `a`, paint 3 px dots in the minimap's other dot colours (take them from the grabs: other players, party, NPC, portal) at other spots in the map area. The result equals the unpainted one.
  - `test_read_all_fills_player`: `read_all` on a fixture-sized frame gives a `Reading` whose `player` equals `read_player`'s result.
- [ ] **Step 3:** Run. Expected: FAIL.
- [ ] **Step 4:** Implement `read_player`. Named constants at the top for the map-area offset from the anchor, the dot's colour range and its size bounds, all taken from the fixtures. Find the map area's edges from the panel's own pixels, because the panel widens for long names.
- [ ] **Step 5:** Run: PASS. Then the full suite (existing `Reading(...)` calls must still work thanks to the default), ruff, format and the guard.
- [ ] **Step 6: Owner review:** list each new PNG and ask the owner to confirm it has no names, chat or other players. Commit only after they confirm.
- [ ] **Step 7: Commit** (`feat(readers): player position on the minimap`).

### Task 3: Camera — spike first, then keep it

The arrow's whole value depends on this. **Gate:** if Step 3 fails, stop and report to the owner. Do not start Task 6.

**Files:**
- Create: `src/maplelens/tools/path_arrow/camera.py`
- Test: `tests/test_camera.py`

**Interfaces:**
- Consumes: `Minimap` (Task 1), `read_player` (Task 2).
- Produces:
  - `to_world(f: tuple[float, float], mm: Minimap) -> tuple[float, float]` = `(f[0] * mm.w - mm.cx, f[1] * mm.h - mm.cy)`, the inverse of the spec's formula.
  - `to_screen(pt: tuple[float, float], player: tuple[float, float], mm: Minimap, view: tuple[float, float]) -> tuple[float, float]`: world point → normalized-frame pixels (768 high), given the player's world position and the view size in normalized px.
  - Module constants found by the spike: `WORLD_PER_PX` (expected 1.0) and `CAM_DY` (vertical offset of the camera centre from the player).

- [ ] **Step 1: Write failing tests** (pure math, made-up `Minimap(2000, 1000, 1000, 500)`, `view=(1366, 768)`):
  - `test_to_world_inverts_minimap_formula`: `to_world(((x + cx) / w, (y + cy) / h), mm) == (x, y)`.
  - `test_to_screen_centres_player_mid_map`: player at world `(0, 0)` → `to_screen(player, ...)` x is `683`.
  - `test_to_screen_clamps_at_left_edge`: player at world x `-950` (50 from the map's left edge) → screen x is `50` (camera stopped at the edge).
  - `test_to_screen_narrow_map_centres_map`: a map narrower than the view → the map's centre is at screen x `683` wherever the player is.
- [ ] **Step 2:** Implement `camera.py` until they pass. The camera centre is `player + (0, CAM_DY)`, clamped so the view stays inside `[-cx, w - cx] × [-cy, h - cy]`. On an axis where the map is smaller than the view, it's centred.
- [ ] **Step 3: Spike against the grabs.** Write a throwaway script in the scratchpad (not the repo). For at least 8 grabs, across 2+ maps and 2+ resolutions, including 2 with the character near a map edge: normalize, `read_player`, `to_world`, then draw (on a copy saved to the scratchpad) a marker at `to_screen(player)` and one at `to_screen(portal)` for every portal from `maps.json`. The portal markers check the scale and camera independently of the character. Tune `WORLD_PER_PX` and `CAM_DY`. **Pass:** the character marker is within ~30 normalized px of the character's head mid-map, and the portal markers sit on the visible portals. Show the owner 3 marked images locally (they're the owner's own grabs; don't commit them). If edges are off but mid-map passes, add a `ponytail:` comment naming the ceiling. If mid-map fails, **stop** and report.
- [ ] **Step 4:** Add the tuned values to the tests as `test_camera_constants_from_spike` (asserts the constants, with a comment naming the grabs used), then run the full suite, ruff, format and the guard.
- [ ] **Step 5: Commit** (`feat(path_arrow): minimap to screen camera`).

### Task 4: Route planning and the running trip

**Files:**
- Create: `src/maplelens/tools/path_arrow/route.py`
- Test: `tests/test_route.py`

**Interfaces:**
- Consumes: `MapInfo`, `Portal`, `Cab` (Task 1).
- Produces:
  - `Step(map_id: str, cab: bool)` (frozen): `cab=True` means you leave this map by its cab. The last step's `cab` is False.
  - `plan(maps, start: str, goal: str, taxi: bool) -> list[Step] | None`: fewest hops by BFS over portals, plus cab edges when `taxi`. Neighbours are visited in a stable order (portals in file order, then cab destinations). Returns `[Step(start, False)]` when `start == goal`, and None when the goal is unreachable.
  - `class Trip(maps, start: str, goal: str, taxi: bool)` with attributes `goal`, `taxi`, `steps: list[Step] | None`, `index: int`, and:
    - `on_map(map_id: str) -> None`: same map → nothing; a later route map → jump; an earlier route map → rewind; off the route → `steps = plan(map_id, ...)`, `index = 0`.
    - `arrived -> bool` (property): `steps` is not None and `steps[index].map_id == goal`.
    - `target(player: tuple[float, float]) -> tuple[int, int] | None`: on a cab step, the cab's `(x, y)`. Otherwise the portal to `steps[index + 1]` nearest to `player`. None when arrived or with no route.

Graph for the tests: chain `A → B → C → D` by portals (and back), `A` with a cab to `D`, and `E` isolated.

- [ ] **Step 1: Write failing tests:**
  - `test_plan_fewest_hops`: `plan(A, D, taxi=False)` ids `== [A, B, C, D]`, all `cab=False`. With `taxi=True`: `[Step(A, True), Step(D, False)]`.
  - `test_plan_unreachable_is_none`: `plan(A, E, ...)` is None.
  - `test_trip_advance` and `test_trip_jump_ahead`: `on_map(B)` gives index 1; `on_map(D)` from index 0 gives `arrived`.
  - `test_trip_back_to_earlier_map_rewinds` (Review Focus 3): at C, `on_map(B)` gives index 1 and the same `steps` object.
  - `test_trip_reroutes_off_route_keeping_taxi`: a trip planned without taxi, then `on_map(X)` where X is off the route but connected → new plan from X with `taxi` unchanged.
  - `test_trip_start_at_goal_arrives` (Review Focus 4): `Trip(maps, D, D, False).arrived` is True and `target(...)` is None.
  - `test_target_nearest_portal`: B with two portals to C, at x=0 and x=1000. Player at x=900 → the x=1000 portal.
  - `test_target_cab_step`: taxi trip at A → `target` is A's cab position.
- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3:** Implement `route.py`.
- [ ] **Step 4:** Run: PASS. Full suite, ruff, format, guard.
- [ ] **Step 5: Commit** (`feat(path_arrow): route planning and trip`).

### Task 5: Tabs in the box + the EXP tab's new look

**Files:**
- Modify: `src/maplelens/overlay.py`, `src/maplelens/tools/exp_meter/text.py`, `src/maplelens/tools/exp_meter/ui.py`, `src/maplelens/app.py`
- Test: `tests/test_overlay.py`, `tests/test_text.py`, `tests/test_ui.py`

**Interfaces:**
- Produces:
  - `Box.add_tab(title: str, widget: QWidget) -> int`, `Box.set_tab_dot(index: int, on: bool) -> None`, `Box.allow_typing(on: bool) -> None` (clears or sets `Qt.WindowDoesNotAcceptFocus` and keeps the box shown). `Box.set_text`/`add_button` go away once nothing uses them. `place` and the saved position are unchanged.
  - `text.box_lines(rate: Rate | None, waiting: bool) -> list[tuple[str, list[str]]]`, replacing `format_box`. It's a list of (grey label, value lines).
  - `ExpMeterTool(settings, conn, on_settings_changed)` keeps its signature but no longer owns a box. It exposes `title = "EXP"` and `tab: QWidget` (labels and values in the mockup-1 look, plus a **History** button), and keeps `update(r, game_rect, now)`/`shutdown(now)`.
  - `app.build_box(settings: dict, save: Callable[[], None], tools: list) -> Box`: makes `Box("exp_meter", ...)`, adds each tool's `tab` under its `title`, adds the right-click item `Quit MapleLens` → `QApplication.quit`, shows it. `main()` calls `box.place(rect)` each tick (moved out of the tool).

Look (mockup 1): font `Segoe UI`. Labels 9 pt in `#9fb0c8`; values 12 pt bold in `#ffffff`. Tab strip: inactive `#9fb0c8`, active white with a 2 px `#ffcc33` underline. The dot is a 6 px `#ffcc33` circle after the title. Box background as today.

- [ ] **Step 1: Write failing tests:**
  - `test_text.py`: turn each `format_box` test into `box_lines`. E.g. `box_lines(Rate(12480, 0.42, 137), False) == [("EXP · last 5 min", ["748,800 /h", "25.20% /h"]), ("Level up in", ["2h 17m"])]`. No rate → values `"— /h"`, `"—% /h"`, `"—"`. Waiting → `[("waiting for game", [])]`.
  - `test_overlay.py` (offscreen, as in `test_ui.py`): `test_box_tabs_switch` (two tabs; selecting tab 1 hides tab 0's widget); `test_tab_dot` (`set_tab_dot(1, True)` shows it, `False` hides it); `test_allow_typing_toggles_focus_flag` (the flag is off after `True` and back on after `False`; the box stays visible).
  - `test_ui.py`: the three existing tests use `tool.tab` and `build_box` instead of `tool._box`. The quit test finds `Quit MapleLens` in `build_box(...)`'s actions. Add `test_history_button_on_exp_tab`.
- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3:** Implement. The tab strip and tab switching live in `overlay.py`, so no tool imports another.
- [ ] **Step 4:** Run: PASS. Full suite, ruff, format, guard. Then `uv run maplelens` with the game open: the EXP tab shows the same numbers in the new look, and the box opens where it was last left.
- [ ] **Step 5: Commit** (`feat(overlay): tabs; new look for the EXP tab`).

### Task 6: The Path tab and the arrow

**Files:**
- Create: `src/maplelens/tools/path_arrow/ui.py`
- Modify: `src/maplelens/store.py` (`DEFAULTS["path_taxi"] = True`)
- Test: `tests/test_path_ui.py`

**Interfaces:**
- Consumes: `maps.load/find/search`, `route.Trip`, `camera.player_world/to_screen`, `minimap_pos.read_view`/`MinimapView`, `overlay.Layer`, `overlay.game_to_layer`, and `Box.allow_typing` through a callback.
- **Amended after Task 3 (2026-11-04):** `Reading` gains `minimap: MinimapView | None = None`, which `read_all` fills from `read_view` (same normalized frame). The tool gets the player's world position only from `camera.player_world(r.minimap, info)`, never from `to_world(r.player, ...)`: on maps bigger than the minimap window `read_player`'s fraction covers only the visible part, and only `player_world` can tell (it returns None there unless the NPC markers fix the scroll). A None world position means no arrow, with `No minimap on this map` when the map is one `player_world` can never place. Add one line to `read_player`'s docstring: valid only on maps that fit the minimap window.
- Produces: `PathArrowTool(settings: dict, on_settings_changed: Callable[[], None], layer: Layer, allow_typing: Callable[[bool], None], maps: dict[str, MapInfo] | None = None)` (None → `load()`), with `title = "Path"`, `tab: QWidget`, `running: bool` (property, for the dot), `arrow: QWidget` (child of `layer`), and `update(r: Reading | None, game_rect: tuple | None, now: float) -> None`.

Behaviour is the spec's "How it behaves" and "When it can't see" sections, with the copy from Global Constraints. Notes:
- Current map = `find(maps, r.map_name, previous_id)`, acted on only once the same title has been read on 2 consecutive updates. The "3 s unreadable" clock starts at the first `None` map name.
- Arrow position: `to_screen(player_world, player_world, ...)` moved up by a named `ARROW_DY` above the head. Normalized px → client px is `× game_h / 768`; then `game_to_layer` for DPI. Angle = `atan2` from the player's world position to `trip.target(...)`. The arrow is hidden whenever any of these is None, or when not running.
- Clicking the search field calls `allow_typing(True)` and focuses it. Start, Escape, picking a match, or the field losing focus calls `allow_typing(False)`.
- When a route starts, `on_settings_changed` is called if `path_taxi` changed.

- [ ] **Step 1: Write failing tests** (offscreen; hand-made maps A → B → C with minimaps; readings built as `Reading(t, None, None, None, title, player=..., minimap=MinimapView(...))` (or with `camera.player_world` monkeypatched), each sent twice to confirm):
  - `test_search_lists_matches`: typing `"b"` into the field lists map B (and only maps whose name or street contains "b").
  - `test_no_route_message`: at A, pick an unreachable map, Start → `No route from here to {name}`, not `running`.
  - `test_start_shows_arrow_and_header`: at A, pick C, Start → `running`, the header is `To C · 1 of 3`, `arrow.isVisible()`.
  - `test_one_frame_misread_does_not_reroute` (Review Focus 2): while running at A, one reading of an unrelated title then back to A → `trip.steps` unchanged, no reroute.
  - `test_wrong_map_reroutes`: confirmed reading of a map off the route → new steps from it, header updated.
  - `test_arrival_then_search`: at C → `Arrived at C`, arrow hidden; 5 s later (`now + 5.1`) the search state is back and `running` is False.
  - `test_minimap_message_after_3s`: running, map name None at t, t+2 → no message; at t+3.1 → `Open your minimap to see the arrow`, arrow hidden; the route is still `running`.
  - `test_dot_missing_message_immediately`: title readable, `player=None` → the minimap message on the first confirmed reading.
  - `test_unknown_map_message` and `test_no_minimap_message` (a map with `minimap=None` → route list, no arrow).
  - `test_start_disabled_when_map_unknown`.
  - `test_taxi_choice_saved`: untick Use taxi, Start → `settings["path_taxi"] is False` and the callback ran.
  - `test_arrow_follows_game_rect_size` (Review Focus 5): the same reading with `game_rect=(0, 0, 1366, 768)` and then `(0, 0, 2732, 1536)` → the arrow's centre doubles (dpr 1 offscreen).
  - `test_typing_toggles_focus`: clicking the field calls `allow_typing(True)`; Start calls `allow_typing(False)`.
- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3:** Implement `ui.py`. Same look as Task 5. The route list matches mockup 3: done maps struck through and grey, yours highlighted with `▸`, a `taxi` tag on cab steps.
- [ ] **Step 4:** Run: PASS. Full suite, ruff, format, guard.
- [ ] **Step 5: Commit** (`feat(path_arrow): path tab and arrow`).

### Task 7: Wire it up, docs, owner check

**Files:**
- Modify: `src/maplelens/app.py`, `AGENTS.md`, `README.md`, `docs/superpowers/specs/2026-11-01-maplelens-harness-design.md`

- [ ] **Step 1:** `main()` makes `PathArrowTool(settings, save, layer, box.allow_typing)` after the EXP tool. `build_box` gets both. Each tick feeds both tools the same reading and rect, and sets `box.set_tab_dot(path_index, path.running)`. `shutdown` stays EXP-only.
- [ ] **Step 2:** Docs, as the spec's "Docs to update" lists: AGENTS.md Layout (`tools/path_arrow/` with `maps`, `route`, `camera`, `ui`, `maps.json`; `readers/minimap_pos.py`; drop the path arrow from "Planned"); README status → Phase 2, plus the credit line `Map and portal data adapted from [meowdb](https://meowdb.com/msclassic).`; the harness design gets a one-line note that the owner moved the path arrow to second.
- [ ] **Step 3:** Full suite, ruff, format, guard.
- [ ] **Step 4: Owner check against the spec's "Done means"** (all 6 items). Also have the owner take one cab ride and read out the cab's destination menu. If it differs from `cab.to`, fix `maps.json` and re-run Task 1's test.
- [ ] **Step 5: Commit** (`feat: path arrow in the app; docs`).
