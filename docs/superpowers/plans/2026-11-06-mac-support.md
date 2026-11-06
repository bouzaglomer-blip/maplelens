# Mac Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** MapleLens runs from source on macOS against Nexon's Mac client (the Windows game in Wine), with Windows behaviour unchanged.

**Architecture:** The OS-facing modules split into a shared part plus one backend per platform: `capture.py` (shared `pick_window` + re-exports) over `capture_win.py` / `capture_mac.py`, and `readers/ocr.py` (shared crop/mask/trim/cache) over `readers/ocr_win.py` / `readers/ocr_mac.py`. On the Mac, the overlay's windows become non-activating panels through a small `overlay_mac.py`. Readers and tools don't change, except that on the Mac `map_name` snaps OCR text to the known map titles.

**Tech Stack:** Python 3.12, uv, ruff, pytest, numpy, opencv-python-headless, PySide6. Windows only: mss, winrt-*. macOS only: pyobjc-framework-Quartz, pyobjc-framework-Vision, pyobjc-framework-Cocoa (AppKit; already a dependency of Quartz, declared because we import it).

**Spec:** `docs/superpowers/specs/2026-11-06-mac-support-design.md`. Read it first, especially "Spike results". This plan doesn't repeat them.

## Global Constraints

- Screen-only rule (`AGENTS.md`). `uv run python scripts/check_screen_only.py` passes after every task. Don't write banned names under `src/` or `scripts/`, comments included.
- **Windows unchanged**: same behaviour, same expected test values, Windows CI green after every task. The shared crop/mask/trim OCR pipeline (`SCALE`, `PAD`, `MARGIN`, ink masks) is not touched.
- On the Mac: no Accessibility API, no AppleScript, nothing that reads the Wine prefix, the game's files or the game process, and nothing that activates or focuses the game window. MapleLens may activate or deactivate **itself**.
- Dependencies by marker only: `sys_platform == 'win32'` for mss and winrt-*, `sys_platform == 'darwin'` for pyobjc-*. Nothing else new.
- `client_rect` returns **physical pixels** of the game's client area (no title bar), top-left origin, in the units of `grab`'s output.
- Settings on the Mac: `~/Library/Application Support/MapleLens`.
- Fixtures: `tests/fixtures/screens/<reader>_<case>_<W>x<H>_<uiscale>.png`, cropped from normalized frames, no names, chat or other players. The owner reviews each new PNG before commit. The spike's full frame is never committed.
- Line length 100, ruff `E,F,I,UP,B`. Commits end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Branch `claude/mac-support`; never push unless the owner asks.

## Review Focus

1. **Game minimized, on another Space, or closed.** Expected: no rect, the layer hides, no error spam. → `test_client_rect_offscreen_is_none` (Task 3).
2. **Screen Recording not granted, or revoked mid-run.** Expected: one clear message at launch, then the "no reading" path, never a crash loop. → `test_ensure_access_prints_once_when_denied` (Task 3).
3. **Game on a non-Retina external display.** Expected: rect and capture at scale 1, readers still work. → `test_client_rect_scale_1` (Task 3).
4. **A map that isn't in `maps.json`** (new content). Expected: the raw OCR text stands; never snapped to a lookalike. → `test_snap_unknown_map_keeps_text` (Task 5).
5. **Numbered sibling maps** (`… I` / `… II` / `… III`). Expected: never snapped to the wrong numeral. → `test_snap_roman_siblings` (Task 5).

---

### Task 1: Guard knows the Mac

**Files:**
- Modify: `scripts/check_screen_only.py`
- Test: `tests/test_screen_only_guard.py`

**Interfaces:**
- Produces: guard messages `banned import '<name>'` (unchanged) and `banned system call '<name>'` (renamed from `banned Win32 call`, now covering both systems).

- [ ] **Step 1: Write the failing tests**
  - `test_flags_mac_name`: a file with `Quartz.CGEventPost(0, e)`, `CGEventCreateKeyboardEvent(None, 0, True)`, `task_for_pid(t, p, r)`, `AXUIElementPerformAction(el, a)`, `CGWarpMouseCursorPosition(p)`, `app.activateWithOptions_(0)` on lines 1–6. Assert exit 2 and `bad.py:<n>: banned system call '<name>'` for each.
  - `test_flags_mac_modules`: `import ApplicationServices`, `from HIServices import AXUIElementCreateApplication`, `import ScriptingBridge`, `import applescript`, `import appscript` → exit 2, `banned import` for each.
  - `test_mac_lookalikes_not_flagged`: `import Quartz`, `import Vision`, `from AppKit import NSApplication`, `CGWindowListCreateImage(r, o, w, i)`, `CGRequestScreenCaptureAccess()`, `NSApp.activateIgnoringOtherApps_(True)` → exit 0.
  - Update `test_flags_win32_name` and `test_syntax_error_does_not_crash` to the new `banned system call` wording.

- [ ] **Step 2: Run to verify they fail**

Run: `uv run --no-project --python 3.12 --with pytest python -m pytest tests/test_screen_only_guard.py -q` (the guard is stdlib only; this works before Task 2)
Expected: the new tests FAIL.

- [ ] **Step 3: Extend the guard**
  - Rename `BANNED_WIN32` → `BANNED_CALLS` (keep every Windows entry) and `WIN32_RE` → `CALLS_RE`. Add, with a reason each: `CGEventPost`, `CGEventPostToPid`, `CGEventPostToPSN`, `CGEventCreateKeyboardEvent`, `CGEventCreateMouseEvent`, `CGEventCreateScrollWheelEvent`, `CGEventCreateScrollWheelEvent2`, `CGEventTapCreate`, `CGEventTapCreateForPid`, `CGEventTapCreateForPSN`, `CGWarpMouseCursorPosition`, `CGAssociateMouseAndMouseCursorPosition`, `task_for_pid`, `mach_vm_read`, `mach_vm_read_overwrite`, `mach_vm_write`, `vm_read`, `vm_write`, `ptrace`, `AXUIElementPerformAction`, `AXUIElementSetAttributeValue`, `AXUIElementPostKeyboardEvent`, `NSAppleScript`, `activateWithOptions` (activates another app).
  - The `[AW]?` suffix stays. Also allow a trailing `_` so pyobjc spellings match (`activateWithOptions_`).
  - Add to `BANNED_MODULES`: `ApplicationServices`, `HIServices` (Accessibility, drives other apps), `ScriptingBridge`, `applescript`, `appscript`, `osascript` (AppleScript).
  - Update the module docstring: "Win32 calls" → "system calls (Windows and macOS)".

- [ ] **Step 4: Run to verify they pass**, plus `uv run --no-project --python 3.12 python scripts/check_screen_only.py` → `screen-only guard: OK`.

- [ ] **Step 5: Commit** — `feat(guard): ban the macOS ways to send input, read memory or drive apps`

---

### Task 2: One project on both systems (deps, settings, split, CI)

**Files:**
- Modify: `pyproject.toml`, `uv.lock`, `src/maplelens/store.py`, `src/maplelens/capture.py`, `src/maplelens/readers/ocr.py`, `src/maplelens/overlay.py`, `tests/conftest.py`, `tests/test_readers.py:182`, `.github/workflows/ci.yml`
- Create: `src/maplelens/capture_win.py`, `src/maplelens/readers/ocr_win.py`
- Test: `tests/test_store.py`, `tests/test_capture.py`

**Interfaces:**
- Produces (`maplelens.capture`, both systems): `pick_window(titles: list[tuple[int, str]], title: str) -> int | None` (unchanged, defined here), and re-exported from the platform module: `list_windows() -> list[str]`, `find_window(title: str) -> int | None`, `window_title(hwnd: int) -> str`, `client_rect(hwnd: int) -> tuple[int, int, int, int] | None`, `grab(hwnd: int, rect: tuple[int, int, int, int]) -> np.ndarray` (**new `hwnd` first argument**; Windows ignores it), `set_dpi_aware() -> None`, `ensure_access() -> bool` (Windows: always `True`).
- Produces (`maplelens.readers.ocr`): unchanged public API (`engine()`, `crop`, `read_lines`, `SCALE`, `PAD`, `MARGIN`). Backend contract for `ocr_win` / `ocr_mac`: `engine() -> object | None` and `recognize(img: np.ndarray) -> list[str]`, where `img` is the padded black-on-white `uint8` gray image `ocr._recognize` builds today, and the result is stripped lines.
- Produces (`maplelens.store`): `data_dir() -> Path`.

- [ ] **Step 1: Write the failing tests**
  - `test_data_dir_mac(monkeypatch, tmp_path)`: with `sys.platform` patched to `"darwin"` and `HOME` set to `tmp_path`, `data_dir() == tmp_path / "Library/Application Support/MapleLens"` and it exists.
  - `test_data_dir_windows(monkeypatch, tmp_path)`: `"win32"`, `APPDATA=tmp_path` → `tmp_path / "MapleLens"`.

- [ ] **Step 2: Run on the Mac to see the current state**

Run: `uv sync`
Expected: FAIL building `winrt-runtime` ("Unsupported compiler: unix").

- [ ] **Step 3: Make it work**
  - `pyproject.toml`: add markers to mss and the three winrt deps; add `pyobjc-framework-Quartz`, `pyobjc-framework-Vision`, `pyobjc-framework-Cocoa` with `; sys_platform == 'darwin'` (current versions). Run `uv lock`.
  - `store.data_dir`: `~/Library/Application Support/MapleLens` on darwin (via `Path.home()`), `%APPDATA%\MapleLens` otherwise.
  - Move everything but `pick_window` from `capture.py` to `capture_win.py`, `grab` taking `hwnd` first, plus `ensure_access() -> bool: return True`. `capture.py` keeps `pick_window` and re-exports from `capture_win` when `sys.platform == "win32"` (Task 3 adds the darwin branch). `capture_win` takes the `_windows()` list and `pick_window` from `capture.py`, so there's no duplicate. Watch for the import cycle: define `pick_window` before the platform import.
  - Move `engine()`'s WinRT body and the WinRT half of `_recognize` to `readers/ocr_win.py` (`engine()`, `recognize(img)`). `ocr.py` keeps `@cache engine()` delegating to the platform backend (`None` on other systems, or when the import fails), and `_recognize(shape, data)` builds the padded image as today and calls `backend.recognize(img)`.
  - `overlay.exclude_from_capture`: `import ctypes` / `wintypes` stay. Do the `windll` call only when `sys.platform == "win32"`, else nothing.
  - Update callers to `grab(hwnd, rect)`: `app.py` tick and `scripts/grab.py` (both call sites).
  - `tests/conftest.py`: `QT_QPA_FONTDIR` = `/System/Library/Fonts` on darwin, the Windows fonts folder otherwise.
  - `tests/test_readers.py:182`: skip reason `"no OCR engine"`.
  - CI: `strategy.matrix.os: [windows-latest, macos-latest]`, `runs-on: ${{ matrix.os }}`.

- [ ] **Step 4: Verify on the Mac**

Run: `uv sync && uv run pytest -q && uv run ruff check && uv run ruff format --check && uv run python scripts/check_screen_only.py`
Expected: all pass. The `needs_ocr` tests are skipped (no Mac backend yet). Any other Mac-only failure (font metrics in `test_path_ui`, for example) is fixed here without changing a Windows expectation.

- [ ] **Step 5: Commit** — `build: run on macOS too (platform deps, settings folder, capture/OCR split, CI matrix)`

---

### Task 3: Mac capture and Screen Recording permission

**Files:**
- Create: `src/maplelens/capture_mac.py`
- Modify: `src/maplelens/capture.py` (darwin branch), `src/maplelens/app.py`, `scripts/grab.py`
- Test: `tests/test_capture_mac.py` (module-level `pytest.importorskip("Quartz")`)

**Interfaces:**
- Consumes: the `maplelens.capture` API from Task 2.
- Produces (pure, in `capture_mac`): `window_entries(infos: list[dict]) -> list[tuple[int, str]]`, one `(kCGWindowNumber, text)` per non-empty `kCGWindowName` **and** one per `kCGWindowOwnerName`, front to back, so `pick_window`'s exact-then-substring rule matches either. `client_rect_from(bounds: dict, onscreen: bool, title_pt: float, scale: float) -> tuple[int, int, int, int] | None`, where bounds are CG points `{"X","Y","Width","Height"}`.

- [ ] **Step 1: Write the failing tests**
  - `test_window_entries_title_and_owner`: infos `[{num 7, owner "MapleStory Classic World", name "MapleStory"}, {num 9, owner "Google Chrome", name "MapleStory Classic Thief Guide"}]` → `pick_window(window_entries(infos), "MapleStory") == 7` and `pick_window(..., "MapleStory Classic World") == 7`.
  - `test_client_rect_retina`: bounds `X=0, Y=0, W=1366, H=796`, onscreen, `title_pt=28`, `scale=2` → `(0, 56, 2732, 1536)` (spike values).
  - `test_client_rect_scale_1`: the same bounds at `X=1512` with `scale=1` → `(1512, 28, 1366, 768)`.
  - `test_client_rect_no_title_bar`: `title_pt=0` → the whole bounds × scale.
  - `test_client_rect_offscreen_is_none`: `onscreen=False` → `None`. A height ≤ the title bar → `None`.
  - `test_ensure_access_prints_once_when_denied(monkeypatch, capsys)`: preflight patched to `False`, request patched to record calls → `ensure_access()` returns `False`, the request is made once, and stdout names Screen Recording and System Settings.

- [ ] **Step 2: Run to verify they fail** — `uv run pytest tests/test_capture_mac.py -v` → FAIL (no module).

- [ ] **Step 3: Implement `capture_mac.py`**
  - `_windows()`: `window_entries(CGWindowListCopyWindowInfo(kCGWindowListOptionOnScreenOnly, kCGNullWindowID))`. `list_windows()` shows each window once as `"<owner> — <name>"`. `find_window`, `window_title`: as on Windows.
  - `client_rect(wid)`: the window's info via `kCGWindowListOptionIncludingWindow`; `onscreen` from `kCGWindowIsOnscreen`. `title_pt` is the titled-window frame/content height difference from `NSWindow.frameRectForContentRect_styleMask_` (computed once), or 0 when the bounds equal a screen's frame (borderless). `scale` is the `backingScaleFactor` of the `NSScreen` holding the window's top-left (NSScreen uses a bottom-left origin; convert), with `NSScreen.mainScreen()` as fallback.
  - `grab(wid, rect)`: `CGWindowListCreateImage(CGRectNull, kCGWindowListOptionIncludingWindow, wid, kCGWindowImageBoundsIgnoreFraming)`, drawn into an RGB bitmap context in `kCGColorSpaceSRGB` (as in the spike), converted to BGR `uint8`, then the bottom `rect[3]` rows and the left `rect[2]` columns (cuts the title bar). Raise `RuntimeError` if the image is `None`; the app's tick already turns an exception into "no reading", reported once.
  - `ensure_access()`: `CGPreflightScreenCaptureAccess()` → `True`; else `CGRequestScreenCaptureAccess()` and print: what Screen Recording is for (MapleLens captures only the game window's pixels); that macOS grants it to the app that started MapleLens (e.g. Terminal), in System Settings → Privacy & Security → Screen & System Audio Recording; and to run again once allowed. Return `False`.
  - `set_dpi_aware()`: no-op.
  - `capture.py`: `elif sys.platform == "darwin":` re-export from `capture_mac`.
  - `app.main` and `grab.main`: `if not ensure_access(): return 1` right after `set_dpi_aware()`.

- [ ] **Step 4: Run the tests** → PASS. Then check against the live game (the owner's game is running windowed):

Run: `uv run python scripts/grab.py` → the list includes `MapleStory Classic World — MapleStory`.
Run: `uv run python scripts/grab.py --title MapleStory --label mac`
Expected: `…/grabs/mac_2732x1536.png`, mean brightness well above 5. Open it: no macOS title bar; with the minimap open where it was in the spike, row 48, column 100 (the spike's row 104 less the 56-row title bar) is BGR `(204, 187, 153)`.

- [ ] **Step 5: Commit** — `feat(capture): find and grab the game window on macOS`

---

### Task 4: Mac OCR via Vision

**Files:**
- Create: `src/maplelens/readers/ocr_mac.py`
- Modify: `src/maplelens/readers/ocr.py` (darwin backend)
- Test: `tests/test_readers.py` (existing `needs_ocr` tests now run on the Mac)

**Interfaces:**
- Consumes: the backend contract from Task 2.
- Produces: `ocr_mac.engine() -> object | None`, `ocr_mac.recognize(img: np.ndarray) -> list[str]`.

- [ ] **Step 1: Run the OCR tests on the Mac** — `uv run pytest tests/test_readers.py -k "ocr or read_job or read_map_name or noise or empty_mask" -q` → skipped (no backend).

- [ ] **Step 2: Implement `ocr_mac.py`.** `engine()` returns the `Vision` module, or `None` if the import fails. `recognize(img)` encodes `img` to PNG (`cv2.imencode`) into `NSData`, runs a `VNRecognizeTextRequest` (recognition level accurate, `setUsesLanguageCorrection_(False)`, languages `["en-US"]`) through `VNImageRequestHandler.initWithData_options_`, and returns each observation's top candidate, stripped, in order. `ocr.py` picks `ocr_mac` on darwin.

- [ ] **Step 3: Run the same tests**
Expected (from the spike): every job test (the job noise test included), the empty-mask test and the map tests pass, **except** `test_read_map_name` for `minimap_b`, `_c`, `_e` and `_h` (2560) and `test_map_one_px_noise_is_never_another_name`. Task 5 fixes those. Record the actual failures in the commit message.

- [ ] **Step 4: Timing.** On the owner's grab from Task 3: the first `read_all` may take ~0.6 s. Run it three more times on the same frame and on a second grab; each must be under 250 ms (half the tick). If not, stop and report the number.

- [ ] **Step 5: Commit** — `feat(ocr): macOS Vision backend`

---

### Task 5: Snap Mac map names to known titles

**Files:**
- Move: `src/maplelens/tools/path_arrow/maps.json` → `src/maplelens/data/maps.json` (`git mv`)
- Modify: `src/maplelens/tools/path_arrow/maps.py` (`DATA`), `src/maplelens/readers/map_name.py`
- Test: `tests/test_readers.py`

**Interfaces:**
- Produces (`map_name`): `snap_title(text: str, titles: Collection[str]) -> str`, `known_titles() -> frozenset[str]` (`@cache`; `f"{street} / {name}"` for each entry of `maplelens/data/maps.json`), `SNAP = sys.platform == "darwin"`, `SNAP_MIN = 0.9`, `SNAP_LEAD = 0.1`.
- `maps.DATA` points at the new path; `maps.load()` is otherwise unchanged.

- [ ] **Step 1: Write the failing tests** (they run on every system; `snap_title` is pure)
  - `test_snap_misreads` (parametrized, `titles=known_titles()`): `Victoria Road / Sumset Sky` → `… / Sunset Sky`; `Victoria Road / Lithı Harhor` → `… / Lith Harbor`; `Victoria Road / Lith Harlor` → `… / Lith Harbor`; `Victoria Road / Construction Site Nortlı of Kerning City` → `… North of Kerning City`; `Victoria Road / kerning City` → `Victoria Road / Kerning City`.
  - `test_snap_roman_siblings`: `Warning Street / The Swamp of Despair 1` → `… Despair I`; `… Despair 11` → `… Despair II`; `… Despair I` and `… Despair II` → unchanged.
  - `test_snap_unknown_map_keeps_text`: `Victoria Road / Zzyzx Hollow` → unchanged; `A b / C` → unchanged.
  - `test_snap_exact_is_kept`: `Kerning City Subway / Line 1 <Area 1>` → unchanged (its digits stay digits).
  - `test_map_name_snaps_only_on_mac(monkeypatch)`: `read_lines` patched to `["Victoria Road", "Sumset Sky"]` on `minimap_a_1366x768_100.png`. With `map_name.SNAP` True → `Victoria Road / Sunset Sky`; with False → `Victoria Road / Sumset Sky`.

- [ ] **Step 2: Run to verify they fail** (`snap_title` undefined).

- [ ] **Step 3: Implement**
  - `snap_title`: (1) `text` in `titles` → `text`. (2) A trailing standalone `1`, `11` or `111` replaced by `I`, `II` or `III`: if the result is in `titles`, return it. (3) `difflib.SequenceMatcher(None, text, t).ratio()` against every title; return the best only if it is ≥ `SNAP_MIN` and leads the runner-up by ≥ `SNAP_LEAD`; else `text`. `@lru_cache(maxsize=256)` on a `(text)`-keyed wrapper over `known_titles()`.
  - `read_map_name`: apply `snap_title(result, known_titles())` to the non-`None` result of `_normal` / `_bar` when `SNAP`.
  - `SNAP_MIN` / `SNAP_LEAD` come from the spike (true matches 0.945–0.974, runner-ups ≤ 0.80). If a test needs other values, change them, but don't add rules.

- [ ] **Step 4: Run all tests** — `uv run pytest -q` on the Mac: everything passes, including all `needs_ocr` map tests and the map noise test. On Windows (CI), `SNAP` is False and the expected values are unchanged.

- [ ] **Step 5: Commit** — `feat(map_name): snap macOS OCR misreads to known map titles`

---

### Task 6: Overlay on the Mac (visible while playing, game keeps the keyboard)

**Files:**
- Create: `src/maplelens/overlay_mac.py`
- Modify: `src/maplelens/overlay.py`, `src/maplelens/tools/exp_meter/ui.py:23,80`, `src/maplelens/app.py`
- Test: `tests/test_overlay.py`

**Interfaces:**
- Produces (`overlay`): `native_setup(widget: QWidget) -> None` replaces `exclude_from_capture` in every `showEvent` (Layer, Box, the History window). On Windows it is today's display-affinity call. On the Mac with Qt platform `"cocoa"` it calls `overlay_mac.make_panel(widget)`. Otherwise nothing (offscreen tests). `FONT = "Segoe UI"` on Windows, `"Helvetica Neue"` on the Mac.
- Produces (`overlay_mac`): `make_panel(widget) -> None`, `make_accessory() -> None`, `release_keyboard() -> None`.

- [ ] **Step 1: Write the failing tests**
  - `test_native_setup_offscreen_is_noop(monkeypatch)`: offscreen `Box`, `show()` → no exception, and `overlay_mac.make_panel` (patched to record) is not called.
  - `test_font_per_platform`: `overlay.FONT == ("Helvetica Neue" if sys.platform == "darwin" else "Segoe UI")`.
  - `test_allow_typing_off_releases_keyboard_on_mac(monkeypatch)`: with `sys.platform` `"darwin"` and `overlay_mac.release_keyboard` recorded, `box.allow_typing(False)` calls it once and `allow_typing(True)` doesn't.

- [ ] **Step 2: Run to verify they fail.**

- [ ] **Step 3: Implement**
  - `make_panel(widget)`: the `NSWindow` behind `widget.winId()` (an `NSView` pointer: `objc.objc_object(c_void_p=int(widget.winId())).window()`). Add `NSWindowStyleMaskNonactivatingPanel` to its style mask when it's an `NSPanel`, `setHidesOnDeactivate_(False)`, `setLevel_(NSFloatingWindowLevel)`. Keep `setBecomesKeyOnlyIfNeeded_(True)` so clicks and drags don't take the keyboard.
  - `make_accessory()`: `NSApplication.sharedApplication().setActivationPolicy_(NSApplicationActivationPolicyAccessory)` (no Dock icon or menu bar). Called in `app.main` right after `QApplication(...)` on darwin.
  - `release_keyboard()`: the box resigns key (`NSApp.keyWindow().resignKeyWindow()` when it's ours) so keys go back to the game, which stays the active app throughout. MapleLens never calls anything on the game's app or window.
  - `Box.allow_typing(on)`: unchanged on Windows. On the Mac it also calls `release_keyboard()` when `on` is False. `setWindowFlag` recreates the native window; `showEvent` → `native_setup` re-applies the panel setup.
  - Fonts: check the box's EXP and Path tabs at the 186 px tab width; nothing new elides.

- [ ] **Step 4: Run the tests** → PASS. Then the owner checks with the game running (`uv run maplelens`) and confirms each item:
  1. The box and the path arrow stay visible while playing (game focused).
  2. Click a tab, drag the box, open its right-click menu, open History: no Dock icon, the menu bar stays the game's, and the next key press moves the character.
  3. Path tab: click the search field, type part of a map name, pick it, Start. Typing went into the field, and after Start the next key press goes to the game.
  4. Clicks on the arrow layer reach the game.
  5. Box position persists across a restart; the box follows the game window when it's moved.
  If 2 or 3 fail with the panel setup above, stop and report. Don't fall back to activating the game.

- [ ] **Step 5: Commit** — `feat(overlay): macOS panels that stay visible and leave the keyboard to the game`

---

### Task 7: Mac fixtures and docs

**Files:**
- Create: `tests/fixtures/screens/exp_mac_2732x1536_100.png`, `level_mac_2732x1536_100.png`, `job_mac_2732x1536_100.png`, `minimap_mac_2732x1536_100.png`
- Modify: `tests/test_readers.py` (`EXPECTED`), `README.md`, `AGENTS.md`, `CONTRIBUTING.md` (if it lists requirements)

- [ ] **Step 1: Add the `EXPECTED` entries** (failing: files missing): `exp_mac_…: ExpValue(23749, 43.26)`, `level_mac_…: 26`, `job_mac_…: "Rogue"`, `minimap_mac_…: "Dungeon / Sleepywood"`.

- [ ] **Step 2: Make the crops** from the spike frame (`game_srgb.png` in the design session's scratchpad, 2732×1592; cut the top 56 rows), or from the Task 3 grab `mac_2732x1536.png`, which needs no cutting. `glyphs.normalize` it, then crop each region **the way the existing fixture of that reader is cropped** (compare with the `_1366x768_` files: same box, same paint-over of the character-name line for `job`; title bar and title lines only for `minimap`). Nothing in them may show the character name, chat or other players. Show the owner the four PNGs and wait for an OK before committing.

- [ ] **Step 3: Run** `uv run pytest -q` → all pass on the Mac. `test_expected_matches_fixture_files` passes.

- [ ] **Step 4: Docs.**
  - README Requirements: `Windows 10/11, or macOS with MapleStory Classic from Nexon's Mac launcher`; windowed; on the Mac, the first run asks for Screen Recording for the app you start MapleLens from (Terminal, say). Run section: on the Mac, `--title MapleStory`.
  - AGENTS.md Layout: `capture.py` (shared) + `capture_win.py` / `capture_mac.py`; `readers/ocr_win.py` / `ocr_mac.py`; `overlay_mac.py`; `data/maps.json`; drop `maps.json` from the path_arrow line.

- [ ] **Step 5: Commit** — `test: Mac fixtures; docs: macOS requirements and layout`

---

After Task 7: run `uv run pytest -q`, ruff, format check and the guard on the Mac. Then ask the owner whether to push and open a PR, so CI runs on both systems.
