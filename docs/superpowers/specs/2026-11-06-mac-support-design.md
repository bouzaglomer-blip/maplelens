# MapleLens — Mac support design

Date: 2026-11-06. Status: approved by owner 2026-11-06.

## Intent

MapleLens runs only on Windows today. MapleStory Classic also ships for the Mac through
Nexon's Mac launcher, and the owner wants **other Mac players** to be able to use
MapleLens too (owner).

On the Mac, the launcher runs the **Windows game client inside Wine** (found on the
owner's Mac, 2026-11-06: `MapleStory Launcher.app/Contents/SharedSupport/maplestoryna`
bundles Wine and starts `MapleStory.exe`). So the game draws the same pixels as on
Windows, and everything that works on a screenshot carries over: readers, both tools,
history, routes. What has to change is the code that talks to the operating system:
finding the window, capturing it, OCR, the overlay windows' behaviour, and the settings
folder.

The screen-only rule in `AGENTS.md` holds for every part of this document, unchanged.

## Spike results (owner's Mac, 2026-11-06)

A throwaway test on a MacBook (macOS 26.5.1, Apple silicon, Retina) with the game
running, against commit `0b7902a`:

- **Window.** The macOS window list has the game as owner name
  `MapleStory Classic World`, window title `MapleStory` (the title is only visible once
  Screen Recording permission is granted). Windowed, 1366×768 points of game plus a
  28-point macOS title bar; bounds 1366×796 points.
- **Capture.** `CGWindowListCreateImage` with the game's window ID and
  `kCGWindowListOptionIncludingWindow` works on macOS 26.5.1 (deprecated by Apple, still
  working). 2732×1592 px, about 45 ms per grab after the first (114 ms). It captures
  **only that window**, so MapleLens's own windows never appear in it.
- **Colour.** A Mac capture comes back in the display's colour space (Display P3). As is,
  the minimap title panel reads BGR (202, 186, 160) against the expected (204, 187, 153),
  past the readers' tolerance. Drawn into an sRGB bitmap context, it reads exactly
  (204, 187, 153). EXP and level read correctly either way, the minimap and OCR crops
  only after the sRGB conversion.
- **Readers.** On the sRGB frame with the title bar cut off (2732×1536), and on the same
  frame halved to 1366×768: EXP 23,749 (43.26%) ✓, level 26 ✓. With macOS Vision as the
  OCR engine plugged into the existing mask pipeline: job `Rogue` ✓, map
  `Dungeon / Sleepywood` ✓. `read_all` took 583 ms including Vision's first-call warm-up.
- **Existing OCR tests with Vision** (the `needs_ocr` tests, Vision swapped in behind the
  unchanged shared crop/mask/trim pipeline). Jobs: all fixtures pass, including the
  one-pixel noise test. Map names: 4 of the 2560-wide fixtures misread (`Sumset Sky`,
  `Lithı Harhor`, `Nortlı of Kerning City`, `Despair 1` for `Despair I`), and the noise
  test produced `kerning City`. Vision's language correction didn't help. Snapping each
  misread to the closest of the 447 titles in `maps.json` (difflib) fixed all of them:
  scores 0.94 to 0.97, runner-ups 0.75 to 0.80, except `Despair 1`, which scored 0.974
  for `Despair I` against 0.962 for `Despair II`.
- **Minimap dot.** Not found on that map: yellow house art passes the dot filter. This
  happens on Windows too; filed as #5, not part of this work.
- **Permission.** `CGRequestScreenCaptureAccess()` showed the macOS prompt; after the
  owner allowed it, capture worked without restarting the app that asked.

## Goals

- **Same commands on the Mac** (owner: run from source for now). `uv sync`,
  `uv run maplelens`, `uv run python scripts/grab.py`, `uv run pytest`, ruff and the
  guard all work on macOS, and still work on Windows exactly as they do today.
- **Find the game window** by the saved `window_title`, with the existing `pick_window`
  rule (exact match first, else the first substring match). On the Mac, a window matches
  on its title or its owner name *(my call: so either `MapleStory` or
  `MapleStory Classic World` works)*. `grab.py` with no arguments lists the visible
  windows so the player can pick one, as on Windows.
- **Capture only the game's client area**, as BGR uint8 like today: the game window by
  ID, converted to sRGB, the macOS title bar cut off. The frame the readers get looks
  like a Windows grab of the same game at the Mac's pixel size.
- **OCR via macOS Vision** (`VNRecognizeTextRequest`, accurate level, `en-US`, language
  correction off), behind the existing `ocr.read_lines` interface: same input (a bool
  ink mask at the OCR scale), same output, same `None` when no engine is available, same
  cache. Windows keeps its own OCR engine unchanged.
- **Map names snap to known titles on the Mac** *(my call, from the spike)*: the Mac path
  snaps the OCR'd map name to the closest known `street / name` title, the way the job
  reader already snaps to known jobs. Rules: digit `1` at the end becomes roman `I`
  before matching; a snap needs a high score **and** a clear lead over the runner-up,
  else the raw OCR text stands (a map missing from the data still reads as itself).
  When Vision and the tests disagree, Mac-only pre- or post-processing in the Vision
  path is allowed; the shared crop/mask/trim pipeline and the Windows path are not
  changed. Every existing OCR fixture test, the noise tests included, must pass on both
  systems with the same expected values. Readers can't import tools, so the title list
  has to reach the reader without `readers/` depending on `tools/path_arrow/` (the
  builder decides how).
- **Overlay that stays put while playing.** The box, the path arrow layer and the history
  window show over the game and **stay visible while the game has focus**. By default
  macOS hides a Qt `Tool` window when its app is inactive, which here is always, since
  the player is in the game. Click-through on the layer, dragging the box, and typing in
  the Path tab all work as on Windows.
- **The game keeps the keyboard** (owner, 2026-11-06: "Game keeps it"). Clicking or
  dragging the box, switching tabs, using its right-click menu or opening History never
  takes keyboard focus from the game, and doesn't switch the active app, as on Windows
  (`Qt.WindowDoesNotAcceptFocus`). On the Mac this likely needs the windows to behave
  as non-activating panels, and MapleLens to run without a Dock icon or menu bar of its
  own. The one exception is the Path tab's search field, as on Windows (`allow_typing`):
  while it needs typing, MapleLens may take the keyboard. When typing ends (Start, Stop,
  or the field closing), the game is the frontmost app again. If handing focus back
  automatically would mean activating the game window (an anti-goal), the player clicks
  the game once, and only in that case.
- **Screen Recording permission at launch.** `maplelens` and `grab.py` check the
  permission first. If it's missing, they ask macOS for it and print a plain message:
  what the permission is for, that it belongs to the app that started MapleLens (e.g.
  Terminal), and to run again once it's allowed. Never a silent black or empty frame.
- **Settings on the Mac** in `~/Library/Application Support/MapleLens`.
- **Guard knows the Mac.** `scripts/check_screen_only.py` also bans the macOS ways to
  break the rule, with reasons, and has tests for them like the Windows entries. At
  least: posting or creating keyboard/mouse events and event taps (the `CGEvent…` post,
  create and tap calls), moving the cursor, reading or writing another process's memory
  (`task_for_pid`, the `mach_vm_…` read/write calls, `ptrace`), driving other apps' UI
  (Accessibility `AXUIElement…` actions and attribute writes, AppleScript/System Events,
  ScriptingBridge), and activating another app. The builder writes the final list.
- **CI on both systems**: the existing job runs on `windows-latest` and `macos-latest`.
  The OCR fixture tests (`needs_ocr`) run on macOS with Vision and must pass there.
- **Mac fixtures** *(my call)*: crops of the spike's frame (Retina, 2732×1536 once the
  title bar is cut, converted to sRGB), named by the existing convention:
  `<reader>_mac_2732x1536_100.png` (the last number is the game's UI scale, which is
  100%; the Retina size shows in the resolution). They cover EXP, level, job and the normal minimap form (map name).
  Expected values from the spike: EXP 23,749 (43.26%), level 26, `Rogue`,
  `Dungeon / Sleepywood`. The minimized "bar" form and the minimap position are not
  covered (no bar-form grab, and #5). The frame is in this design session's scratch
  folder and is never committed whole (it shows names and chat). If it's gone, the
  owner re-grabs with `grab.py` once Mac capture works, so fixtures never block the
  rest.
- **README**: Requirements list macOS with Nexon's Mac launcher, windowed, plus the
  Screen Recording step.

## Non-goals

- **A downloadable Mac app** (owner: "postpone the real app for later stages"): no
  `.app` bundle, code signing, notarisation or installer. Players run from source, as on
  Windows today. Until then, the Screen Recording permission belongs to the app that
  starts MapleLens, not to MapleLens.
- **macOS fullscreen** (the green button, which moves the game to its own Space). The
  owner plays windowed. Windowed is the supported mode, as on Windows *(my call)*.
- **The Sleepywood minimap dot** (owner: filed as #5).
- **ScreenCaptureKit.** The deprecated `CGWindowListCreateImage` works today and is far
  simpler. If Apple removes it, swapping it out is a change confined to the Mac capture
  code *(my call)*.
- **Separate testing on Intel Macs or mixed-scale multi-monitor setups.** No special
  code for them. Fix if a player reports a problem.

## Anti-goals

- Anything breaking the screen-only rule. On the Mac in particular: no Accessibility API
  (it can drive other apps, and needs a permission MapleLens has no use for), no
  AppleScript, nothing that reads the Wine prefix, the game's files or the game process,
  and nothing that activates or focuses the game window.
- Any change in behaviour on Windows. Windows players should not notice this work.
- A silent failure on the Mac: missing permission, a missing window or a missing OCR
  engine each produce a clear message or the existing "no reading" path, never a crash
  loop or frozen numbers.

## Constraints

- `AGENTS.md` conventions hold: readers stay pure `screenshot -> value`; tools depend only
  on readers + overlay; no dependency for what a few lines can do; no banned names in
  comments or docstrings under `src/` or `scripts/`.
- Dependencies are per platform, by environment marker: the `winrt-…` packages only on
  Windows (`sys_platform == 'win32'`), `pyobjc-framework-Quartz` and
  `pyobjc-framework-Vision` only on macOS (`sys_platform == 'darwin'`). `mss` is only used
  by the Windows capture and can be marked Windows-only too *(my call)*. `uv.lock` is
  regenerated and resolves on both. Neither pyobjc package is on the guard's banned list,
  but Quartz exposes the event-posting calls, so the guard's name check is what keeps them
  out (the same situation as WinRT's input namespace today).
- Units: `client_rect` keeps meaning **physical pixels**, the unit of `grab`'s output and
  what `game_to_layer` divides by the device pixel ratio. On the Mac, Quartz gives points
  with a top-left origin; multiply by the backing scale of the screen the window is on.
- The tick stays 500 ms. A slow first tick (Vision warm-up) is fine; later ticks must
  fit, which the OCR cache should already ensure *(builder: measure)*.
- The project's Claude Code hook runs `uv run … check_screen_only.py` after every edit,
  so `uv sync` has to work on the Mac before that hook stops erroring there.

## Left to the builder

- How the platform split is laid out in code: an `if sys.platform` branch inside each
  module, or a small per-platform module next to it (`capture`, `ocr`). Keep the shared,
  pure parts (`pick_window`, `crop`, the mask trimming) in one place and tested on both.
- How the title bar is found and cut: from the window's frame versus its content area,
  or a measured height. It must be right for a windowed game, and do nothing when the
  window has no title bar.
- The font for the box on the Mac (Segoe UI isn't there), checked against the 186 px tab
  width so nothing new gets elided. Also the test font directory in `tests/conftest.py`,
  which points at `C:\Windows\Fonts` today.
- Which Qt attribute or window flag keeps the `Tool` windows visible when the app is
  inactive, verified with the game focused. `exclude_from_capture` and `set_dpi_aware`
  become no-ops on the Mac, since window-ID capture never sees MapleLens's own windows.
- The exact list of banned macOS names and modules, with a one-line reason each.
- Whether `grab.py`'s window list on the Mac shows owner names, titles or both.
