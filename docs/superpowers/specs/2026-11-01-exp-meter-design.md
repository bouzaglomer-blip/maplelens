# MapleLens — Phase 1 design: EXP meter + the shared base

Date: 2026-11-01. Status: approved by owner 2026-11-01.

## Intent

While grinding, the owner wants to know, without leaving the game:

- **how fast they're earning EXP right now**: raw EXP per minute and % of the
  level per minute;
- **how long until they level up** at that pace;
- **where they were best**: a history, kept across sessions and days, of every
  map they trained in, with their average EXP/min there, plus their class and
  level at the time.

The EXP meter is also the first real tool, so it builds the **base every
later tool stands on**: capture, readers, overlay, saved data, tool loop.
The next tool is the **path finder** (owner's call, changing the Phase 0 roadmap
order, where the path arrow came last). The base is shaped so the path finder slots in
without a rebuild, but nothing is built for it yet.

The screen-only rule in `AGENTS.md` holds for every part of this document.

## Goals

- Live box over the game: EXP/h, %/h, time to level (owner change 2026-11-04: shown per hour).
- History table across days: one row per map + class + level.
- Map, class and level read off the screen; the user types nothing in.
- **Works at any game resolution** (owner: "I want it to work everywhere").
  Owner plays at 2560x1440 on a monitor with Windows display scaling 125%.
  Capture must be per-monitor DPI-aware so scaling doesn't shift anything.
- A base the path finder (and later class helper, prices) can add to without
  restructuring.

## Non-goals

- Path finder, class helper, prices: not built. No minimap reader, no map
  connection data, no destination input yet.
- Support for game UI scales other than the default. If the game ever draws its
  UI bigger, that's a new template set, added when someone hits it.
- Packaging as an .exe. Run with `uv run maplelens` for now.
- Settings UI. The one setting (idle cutoff) lives in a small config file.

## Anti-goals

- Anything breaking the screen-only rule. No global keyboard hooks, no input
  to the game. MapleLens's own windows take their own clicks only.
- Recording garbage: a misread frame (menu over the EXP bar, loading screen)
  must be skipped, never counted as EXP gained or lost.
- Losing history on a crash or a forced close.
- An overlay that blocks clicks to the game outside MapleLens's own box.

## How the numbers work (owner decided)

- **Live meter = rolling average** over the last few minutes, not
  since start, so it follows map changes and buffs. Window: **5 minutes**
  *(my call)*.
- **Time to level** = (100% − current %) ÷ current %/min. Shows "—" until
  there's at least a minute of data or while the rate is zero.
- **Per-map average counts only time inside that map, and not idle time.**
  Rule: look at the gap between consecutive EXP gains. Short gaps (respawn
  waits, tanky mobs, repositioning) **count** as active time; a gap longer than
  the **idle cutoff** is dropped entirely. Cutoff: **90 s** *(my call)*,
  configurable. Owner explicitly wants respawn waits counted.
- Per-map average = EXP gained in that map ÷ active time in that map, grouped
  by **map + class + level**. A level-up starts a new row.
- **Level-up mid-stream:** a % drop together with level going up is a level-up,
  not a loss. Gained = (100 − old %) + new %. Raw EXP across a level-up uses the
  old level's total (derived from raw ÷ %) *(my call; builder may refine)*.
- **Death EXP loss doesn't count at all** (owner decided): a % drop with no
  level change is not subtracted. The new value just becomes the baseline.
- **Big one-off jumps don't count** (owner decided): quest turn-ins, boss
  kills and the like are left out of both the live meter and the map average.
  The new value becomes the baseline, and time keeps counting. Detection: a single
  gain larger than **5× the median gain** over the rolling window *(my call;
  threshold configurable)*. Until the window has ~10 gains, no jump is
  flagged.

## UI (owner decided, from mockups)

- **Live box: small, draggable, anywhere over the game** (owner picked
  option B over a strip on the EXP bar). Shows label "EXP · last 5 min",
  EXP/h, %/h, "Level up in Xh Ym". Remembers its position.
- **History table: its own normal window**, opened from a button on the box
  *(my call)*. Columns: Map, Class, Lvl, Avg EXP/h, Avg %/h, Active time,
  Last there. Sortable by clicking a column header. Default sort: last there,
  newest first *(my call)*.

## The base (architecture)

Five parts. Only what the EXP meter uses gets built; the shape is what's
shared.

```
src/maplelens/
  capture/     find the game window, grab its pixels
  readers/     screenshot -> one value, pure functions
  overlay/     the see-through layer + draggable boxes + plain windows
  store.py     the saved-data file
  app.py       the tool loop; entry point `maplelens`
  tools/exp_meter/   the EXP meter (logic + its box + its table window)
```

### Capture

- Finds the game window by title and gets its client-area position and size,
  every tick (the window can move). Uses read-only window-geometry calls via
  `ctypes`; nothing that touches the game process. Must be DPI-aware so
  coordinates match pixels.
- Grabs the client area as a numpy array. Library: `mss` *(my call, from the
  Phase 0 design)*.
- **Rate: 2 frames/second** *(my call)*. EXP changes slowly; cheap on CPU.
- Game not found / minimized: tools receive "no frame", the box shows
  "waiting for game", and active time doesn't accrue.

### Readers

Pure functions `frame -> value | None`, each in its own module, each tested
against cropped PNG fixtures (per `AGENTS.md`). `None` means "couldn't read
this frame", never a guess.

What the screen shows (from an owner screenshot, 2026-11-01):

- Status bar, bottom center: `LV.` + level in orange digits; to its right the
  **class name on the top line and the character name on the line below**;
  then HP, MP and `EXP 23,605 [81.45%]`. That's raw EXP plus % with two decimals.
- Minimap window, top left: title in two lines, **region** (`Dungeon`) over
  **map name** (`Ant Tunnel III`). The reader returns both, and the map key is
  region + name *(my call; map names may repeat across regions)*.
- Crops for class must stop above the character-name line.

EXP meter needs four:

| Reader | Reads | Shared with |
|---|---|---|
| `exp` | raw EXP and EXP % from the status bar | — |
| `level` | level digits from the status bar | class helper |
| `job` | class name from the status bar (fixed, small set of names) | class helper |
| `map_name` | current map name (minimap title) | **path finder** |

- **No fixed coordinates.** Each reader first *finds* its region by searching
  the frame for an anchor that looks the same at every resolution: the `EXP`
  label and `LV.` on the status bar, the `mini map` title bar on the minimap
  *(my call)*. Then it reads at a fixed offset from the anchor. Anchor
  positions are cached and re-searched only when a read fails, to keep CPU
  low.
- **The game scales its whole picture with the window** (measured from owner
  screenshots, 2026-11-01: the status bar is ~795 px wide at 1366x768 and
  ~1500 px at 2560x1440, the same ratio as the resolutions). So every reader
  first **resizes the frame to a base height of 768 px** (area interpolation),
  then finds anchors and reads. Templates are cut from **1366x768** grabs,
  where the game's pixels map 1:1 *(my call)*. Glyph matching must tolerate
  the slight blur that rescaling leaves. The anchor search still covers the
  whole frame, because the minimap can be anywhere.
- Capture reads the window's own client area.
- Matching approach is the builder's call, with constraints: no external
  program the end user must install (e.g. no separate OCR engine), and it must
  be deterministic so fixture tests are stable. Template matching against
  small glyph/word images is the expected route for digits and class names.
- **`map_name` is the riskiest reader** (free-form text, many maps). Build it
  as a **general glyph reader** of the minimap-title font, not one template
  per map *(my call)*: one alphabet's worth of fixtures covers every map, and the
  path finder needs every map.
- **Map unreadable** (minimap closed/minimized, unknown text): accrual pauses.
  No time is credited to any map until the name reads again *(my call; avoids
  mislabelled rows)*. The live box keeps running, since it doesn't need the map.
- **Templates are committed to the repo** under the package, next to the
  readers *(my call)*. They're tiny UI crops, the same kind of material the
  fixtures already are. No first-run calibration flow.
- **Sanity filter** (in the tool, not the readers): reject a reading that
  jumps implausibly (e.g. EXP % up by more than a few % in half a second
  with no level change) as a misread. Require a value to be seen on 2
  consecutive frames before acting on it *(my call)*.

### Overlay

Built with PySide6 (Qt) *(my call, from Phase 0 design)*.

- **Layer:** one transparent, always-on-top, **click-through** window that
  tracks the game window's client area. Empty for the EXP meter, but it's
  where the path finder's arrow over the character will be drawn. It exists
  in Phase 1 so the coordinate mapping (game pixels → overlay pixels) is
  built and tested once.
- **Boxes:** small always-on-top windows that *do* take clicks (drag, buttons)
  but only on themselves. Each tool owns its own box(es). Positions saved per
  box, relative to the game window.
- **Plain windows:** ordinary windows (the history table, later the path
  finder's destination input). Text is typed into MapleLens's own window,
  never into the game.
- Hotkeys, if ever needed: Qt shortcuts on MapleLens's own windows only. No
  global hooks.

### Saved data

- One SQLite file (stdlib `sqlite3`) in `%APPDATA%\MapleLens\maplelens.db`
  *(my call)*. Settings (idle cutoff, box positions) in a small JSON file next
  to it.
- Each tool owns its own tables; tools never read each other's.
- EXP meter stores **segments**: map, class, level, start time, end time, EXP
  gained, % gained, active seconds. A segment closes on map change, level
  change, idle gap, or app exit. The table view sums segments by map + class
  + level.
- **The open segment is written at least once a minute**, so a crash loses at
  most a minute.

### Tool loop

- `app.py` runs a timer at the capture rate: grab frame → run the readers the
  tools need → hand each tool a `Reading` (timestamp + each reader's value or
  `None`) → the tool updates its own state and box.
- A tool is a class with `update(reading)` and owns its windows. No registry,
  no plugin system: `app.py` lists the tools it starts. A reader runs at most once
  per frame even if two tools want it.
- Tools depend only on readers, overlay and store — never on another tool
  (per `AGENTS.md`).

### First build step: capture check + fixture grabber

The builder can't run the game, so step 1 of the plan is a small script the
owner runs (`uv run python scripts/grab.py` *(my call)*). It:

- lists visible window titles, so the owner can pick the game's;
- grabs the game window with the real capture code and saves full frames as
  lossless PNGs to `%APPDATA%\MapleLens\grabs\`, never the repo;
- has an **auto mode**: one frame every N seconds for M minutes while the owner
  plays normally *(my call, to save the owner from running a command per
  shot)*. The controller can start it in the background.

If the frame comes back black, capture has to switch to Windows Graphics
Capture before anything else. The main session is at **1366x768** (the template
base): a few maps, a range of EXP values, a level-up if one is close, and a
menu over the bar once. Shorter sessions at **1920x1080 and 2560x1440** prove
the rescaling. The builder cuts fixture crops (no name line, chat or other
players) from those frames. The owner reviews each crop before commit, and
reader tests run on every resolution. Fixtures are named
`<reader>_<case>_<WxH>_100.png`. Pasted chat screenshots can't be used: they
arrive shrunk and lossy.

## Testing

- Every reader: pytest against cropped fixtures in `tests/fixtures/screens/`,
  named with resolution + UI scale. Include at least one "unreadable" fixture
  per reader (covered by a menu, loading screen) that must return `None`.
- EXP meter maths (rolling rate, idle cutoff, level-up, segment splitting):
  plain unit tests feeding fake `Reading` sequences. No screenshots needed.
- Overlay and capture: a manual check against the running game; no
  automated test of Qt windows.
- Guard, ruff, pytest all pass in CI (Windows).

## Constraints

- Windows 10/11, game windowed or borderless (true fullscreen hides overlays).
  Owner normally plays full screen and confirmed the game can switch; the
  README already states the requirement.
- Python 3.12, `uv`, ruff, pytest (Phase 0).
- New dependencies expected: `mss`, `numpy`, `PySide6`, maybe `opencv-python`
  for template matching. None are on the guard's banned list. Add only what's
  used.
- Fixtures: cropped to the reader's region; never character names, chat or
  other players. The status bar shows the character name next to level/class:
  crops must exclude it.

## Done means

- With the game running at the supported resolution, the box shows live
  EXP/min, %/min and time to level that match the owner's manual check over a
  10-minute grind within a few percent.
- Walking to a new map starts a new history row; going AFK for 5 minutes adds
  no active time; a level-up starts a new row and doesn't show a loss.
- Killing MapleLens mid-grind and restarting keeps history up to the last
  minute.
- Reader tests, maths tests, guard and ruff pass in CI.
- `README` roadmap updated: EXP meter, then path finder.

## Left to the builder

- Template-matching details, glyph extraction, crop coordinates.
- Exact sanity-filter thresholds.
- Qt window flags and the click-through mechanism (Qt-level, not input
  hooks).
- Box visual styling (semi-transparent dark, monospace numbers, as mocked).
- Schema details beyond the segment fields listed.

## Open questions

None blocking. Carried from Phase 0, for later phases: Nexon's terms on
overlays/screen capture for MapleStory Classic; where the path finder's
map-connection data comes from and whether its source permits using it.
