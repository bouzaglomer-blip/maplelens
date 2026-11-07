# Tray Icon and Menu Button Implementation Plan

Spec: `docs/superpowers/specs/2026-11-07-tray-and-menu-button-design.md`. Branch:
`tray-menu-spec`, from or-keren/maplelens `main` at 4199c20 (v0.1.0, PR #10 merged). One
commit per task. The PR goes from the fork (`dbeilin/maplelens`) to `or-keren/maplelens`
once Checkpoint C passes. It changes no `version`: the release goes through Prepare
release.

## Overview

On Windows, MapleLens gets a tray icon. Right-clicking it opens the box's menu, and
left-clicking it hides or shows everything MapleLens draws. On every platform, the box
gets a ⋯ button in its top-right corner that opens the same menu. Right-clicking the box
still works too. Every "right-click" in the app, README and installer becomes "⋯".

## Architecture decisions

- **One list, filled on open.** The box's own `actions()` stay the menu. A helper on
  `Box`, `attach_menu(menu: QMenu)`, connects the menu's `aboutToShow` so it clears and
  re-adds `self.actions()` each time it opens. The ⋯ button's menu and the tray's menu
  both use it. So the update check's runtime items show up everywhere, and nothing keeps
  a second list *(my call: the spec left the name to the builder)*.
  - `QMenu.clear()` deletes only actions the menu owns. The box owns these, including
    the "Pick game window…" submenu, so they survive. A test opens the menu twice to
    prove it.
- **The tray is in `app.py`, behind a seam.** `make_tray(box, icon, *, tray_cls,
  available)` builds it. Offscreen tests pass a fake tray class and `available=True`,
  because a real `QSystemTrayIcon` needs a real tray. `main()` passes `QSystemTrayIcon`
  and `QSystemTrayIcon.isSystemTrayAvailable() and sys.platform == "win32"`.
- **Hidden is a flag in `main()`, not a window state.** `Shown` (a tiny class with `on:
  bool` and `toggle()`) is read by the tick before `layer.show()`. `Box.allow_typing`
  shows the box again only if it was visible before the flag change. Qt's own
  `isVisible()` can't be the flag, because the tick hides and shows the `Layer` on its
  own when the game is lost or found.
- **The icon is package data.** `src/maplelens/data/icon.ico` is the one copy. The exe,
  Setup and the tray all point at it, and the build's `REQUIRED` list and `--self-check`
  both prove it's in the bundle and loads.
- **The risky part comes first** (T1): whether the frozen app can load the `.ico`.
  `qico.dll` ships, but `--self-check` runs without a `QApplication`, and the tray is
  useless without its icon.

## Dependency graph

```
T1 icon as package data, loads in the frozen app      T2 ⋯ button + attach_menu
   │                                                      │
   │                                                      ├── T3 text: "right-click" → "⋯"
   │                                                      │
   └──────────────────────┬───────────────────────────────┘
                          T4 tray icon, right-click menu (Windows)
                          │
                          T5 Hide / Show (tray left-click + menu item)
                          │
                          T6 docs, installed-build run, PR
```

T1 and T2 are independent, as are T3 and T4. Daniel works alone, so they run in order.

## Phase 1: the foundations

### Task T1: the icon as package data, loaded by the frozen app

**Description:**
- `git mv packaging/windows/icon.ico src/maplelens/data/icon.ico`.
- `maplelens.spec`: `icon=` points at the new path (`ROOT / "src" / "maplelens" / "data"
  / "icon.ico"`).
- `maplelens.iss`: `SetupIconFile=..\..\src\maplelens\data\icon.ico`, relative to the
  `.iss`.
- `app.py`: `ICON = Path(__file__).parent / "data" / "icon.ico"`. `self_check` fails if
  `QImage(str(ICON)).isNull()`. If `QImage` can't use its plugins without an app, use a
  `QGuiApplication` on the offscreen platform inside `self_check`. That window-free check
  is what the build runs.
- `scripts/build_installer.py`: add `_internal/maplelens/data/icon.ico` to `REQUIRED`.
- `tests/test_build_installer.py`: `test_icon_exists` checks the new path.

**Acceptance criteria:**
- [ ] `uv run --group build python scripts/build_installer.py` builds the setup. The
      setup exe and `MapleLens.exe` still show the icon in Explorer.
      *2026-11-07: builds (PyInstaller embeds the icon, ISCC takes the new path). The
      Explorer look is still to check by hand.*
- [x] `dist\MapleLens\MapleLens.exe --self-check` exits 0. With the bundled
      `icon.ico` deleted, or `qico.dll` deleted, it exits 1.
      *2026-11-07: 0, 1, 1, and 0 again once restored. The first build failed it: `ICON`
      came from `app.py`'s own folder, which the frozen app runs outside the package, so
      it's found from `maplelens.__file__` instead.*
- [x] `packaging/windows/icon.ico` is gone, and nothing points at it
      (`git grep "windows/icon.ico"` finds only the older specs and plans, which stay as
      written).

**Verification:** `uv run pytest tests/test_build_installer.py tests/test_app.py`, the
four checks, and the build above.

**Dependencies:** none. **Files:** `src/maplelens/data/icon.ico`,
`packaging/windows/maplelens.spec`, `packaging/windows/maplelens.iss`,
`scripts/build_installer.py`, `src/maplelens/app.py`, `tests/test_build_installer.py`.
**Scope:** M.

### Task T2: the ⋯ button and `attach_menu`

**Description:**
- `overlay.py`: a top row (`QHBoxLayout`) holds the tab strip and the status line, which
  take turns as today, with the ⋯ button on the right in both states. `set_status`
  keeps toggling the strip, pages and status. The ⋯ isn't part of any of them.
- The button is styled like the notice's ×: flat, `LABEL_COLOR`, `Qt.NoFocus`, pointing
  hand. Clicking it pops up a `QMenu` filled by `attach_menu`, just under the button.
- `attach_menu(menu)`: on `aboutToShow`, `menu.clear()`, then `menu.addAction(a)` for
  each of `self.actions()`.
- Glyph: try "⋯" (U+22EF) in Segoe UI. If Qt's fallback shows a box or the wrong
  height, use "•••" or paint three dots. Record the choice in the commit message, because
  T3's text uses it.
- Docstrings drop "right-click" ("the box's menu").

**Acceptance criteria:**
- [ ] Offscreen tests: the ⋯ is visible with tabs and while `set_status("Looking…")`
      shows. Its menu lists `box.actions()` in order, including an item added with
      `at=0` after the menu was attached. Opening it twice leaves every action alive and
      working. The button has `Qt.NoFocus`, and pressing it leaves `_drag_from` at
      `None`. `contextMenuPolicy()` is still `Qt.ActionsContextMenu`.
- [ ] By hand, `uv run maplelens` on Windows: the ⋯ sits top-right at 100% and 150%
      scaling, in both states. Its menu opens under it, and after picking an item or
      pressing Esc, the game still has the keyboard.

**Verification:** `uv run pytest tests/test_overlay.py`, the four checks, and the run
above.

**Dependencies:** none. **Files:** `src/maplelens/overlay.py`, `tests/test_overlay.py`.
**Scope:** S.

### Checkpoint A: the foundations

- [ ] T1 and T2 committed, and the four checks pass.
- [ ] The frozen self-check proves the icon loads.
- [ ] Daniel has seen the ⋯ on the box and agrees with the glyph and the place.

## Phase 2: the feature

### Task T3: text points at ⋯

**Description:**
- `app.py`: `LOOKING` → "Looking for MapleStory… click ⋯ to pick the game window".
  `update_notice` → "Update to X.Y.Z: click ⋯". `UPDATE_FAILED` → "Update failed: click
  ⋯". `build_box`'s docstring. (Use the T2 glyph throughout.)
- `maplelens.iss`: "MapleLens is still running. Quit it from the ⋯ menu on its box or
  its tray icon, then try again."
- `README.md`: the install step, Updating, the update-check paragraph and the
  from-source paragraph say "click ⋯ on the box" where they say "right-click the box".
- "Looking for…" one line or two (spec, open question): pick by how it looks at 100% and
  150%, next to the ⋯.
- Update the tests that assert the old strings.

**Acceptance criteria:**
- [ ] `git grep -i "right-click\|right click" -- src README.md packaging` finds nothing
      in what the player sees. The box's right-click still works, it just isn't
      mentioned.
- [ ] `test_notice_fits_the_tab_width_at_the_longest_version` passes with the new text.
- [ ] By hand: the "Looking for…" state reads well next to the ⋯ at 100% and 150%.

**Verification:** `uv run pytest`, the four checks.

**Dependencies:** T2. **Files:** `src/maplelens/app.py`, `packaging/windows/maplelens.iss`,
`README.md`, `tests/test_app.py`, `tests/test_overlay.py`. **Scope:** S.

### Task T4: the tray icon and its menu (Windows)

**Description:**
- `app.py`: `make_tray(box, icon, *, tray_cls=QSystemTrayIcon, available) -> tray |
  None`. When `available`, it builds the tray with `QIcon(str(ICON))`, the tooltip
  "MapleLens", and a `QMenu` that `box.attach_menu` fills, then `show()`s it. Otherwise
  it returns `None`.
- `main()` calls it after `update_check`, with `available = sys.platform == "win32" and
  QSystemTrayIcon.isSystemTrayAvailable()`, and keeps the reference (a tray with no
  reference is collected and vanishes).
- Quit from the tray is the box's own "Quit MapleLens" action, so `aboutToQuit` saves as
  today.

**Acceptance criteria:**
- [ ] Tests with a fake tray class: the tooltip is "MapleLens", the icon isn't null, and
      the menu lists `box.actions()`, including an update item added afterwards. With
      `available=False` there's no tray.
- [ ] By hand, `uv run maplelens` on Windows: the icon shows in the notification area
      (or its overflow) with the tooltip. Right-click shows the same menu as ⋯. Quit
      from it saves the session (it's in History after a restart). The game keeps the
      keyboard afterwards.

**Verification:** `uv run pytest tests/test_app.py`, the four checks, and the run above.

**Dependencies:** T1, T2. **Files:** `src/maplelens/app.py`, `tests/test_app.py`.
**Scope:** S.

### Task T5: Hide / Show

**Description:**
- `app.py`: `Shown` holds `on` and `toggle()`. Toggling hides or shows the box and the
  `Layer`, and relabels the menu item "Hide MapleLens" ↔ "Show MapleLens".
- The item goes in just before Quit (`at=-1`), and only when `make_tray` returned a tray.
- The tray's `activated` with `QSystemTrayIcon.Trigger` (left click) calls `toggle()`.
- The tick shows the `Layer` only while `shown.on`. It still runs the tools, the readers
  and `poll_updates` while hidden.
- `overlay.py`: `allow_typing` calls `show()` only if the box was visible before the flag
  change.
- Not saved: every start begins shown.

**Acceptance criteria:**
- [ ] Tests (fake tray, offscreen): toggling hides the box and the `Layer`, and the label
      reads "Show MapleLens". A tick with the game "found" (faked `client_rect`/`grab`)
      leaves both hidden and still updates the EXP tool. Toggling back shows both.
      `allow_typing(False)` on a hidden box leaves it hidden. With no tray there's no
      Hide item.
- [ ] By hand: left-clicking the tray icon hides the box and the arrow, and again brings
      them back. A double-click toggles once, not twice. While hidden for a minute of
      play, the EXP session keeps counting.

**Verification:** `uv run pytest`, the four checks, and the run above.

**Dependencies:** T4. **Files:** `src/maplelens/app.py`, `src/maplelens/overlay.py`,
`tests/test_app.py`, `tests/test_overlay.py`. **Scope:** M.

### Checkpoint B: the feature works from source

- [ ] T3–T5 committed, and `uv run pytest` and the four checks pass on Windows.
- [ ] Spec Testing → by hand on Windows, steps 1–6, from `uv run maplelens`.
- [ ] Daniel tries it in a real play session before Phase 3.

## Phase 3: ship it

### Task T6: docs, the installed build, then the PR

**Description:**
- `README.md`: one line under the install steps about the tray icon: left-click hides or
  shows MapleLens, right-click opens the same menu as ⋯. (Windows only.)
- `AGENTS.md` Layout: `data/icon.ico` (the app icon) under `data/`, and drop the icon from
  the `packaging/windows/` line.
- Spec status line: built, with the date. Tick this plan's boxes, with run notes for the
  manual checks.
- Build the setup, install it over v0.1.0, and run spec Testing → by hand on Windows,
  steps 1–7, on the installed app. Step 2's update item comes from a test release on the
  fork, as in the update-check plan's U7. Delete that test release afterwards.
- Mac: CI only, unless a Mac is at hand for spec Testing → by hand on a Mac. Say which
  in the PR.
- Push `tray-menu-spec` to the fork and open the PR to `or-keren/maplelens` *(ask
  Daniel first: both are outward-facing)*.

**Acceptance criteria:**
- [ ] Every spec success criterion holds, each with a test or a run note. Mac-only ones
      say whether a Mac or only CI checked them.
- [ ] The installed build: tray icon with the right icon, ⋯ menu, Hide/Show, and Quit
      from the tray all work. The hand-run Setup over a running MapleLens shows the new
      "still running" text.
- [ ] CI is green on the PR (Windows and macOS).

**Verification:** the build, the installed run, and CI.

**Dependencies:** T1–T5. **Files:** `README.md`, `AGENTS.md`, the spec, this plan.
**Scope:** S.

### Checkpoint C: done

- [ ] All spec success criteria met.
- [ ] PR open from the fork, CI green, Daniel has reviewed it.

## Risks and mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| The frozen app can't load `icon.ico` (no plugin path without an app, or `qico.dll` dropped) | High: a blank tray icon | T1 first. `--self-check` loads it, and the build fails if it doesn't. |
| A `QMenu` shown from the box or the tray takes focus from the game | High: the anti-goal | By-hand focus checks in T2 and T4, as in the update-check plan's focus runs. Same Qt path as today's right-click menu. |
| `menu.clear()` deletes the box's actions | Med: menu items vanish after one open | The box owns its actions. A test opens each menu twice and triggers an item after. |
| A tick re-shows a hidden box or arrow | Med: Hide doesn't stick | One `Shown` flag read by the tick and `allow_typing`, with a test for each. |
| "⋯" renders as a box or off-centre in Segoe UI | Low | T2 falls back to "•••" or painted dots, and T3's text follows. |
| On the Mac, the ⋯ menu opens under the panel | Low: the panel sits at `NSPopUpMenuWindowLevel - 1` | Spec Testing → by hand on a Mac, if a Mac is at hand. Otherwise the PR says it's unchecked. |
| The tray is collected because nothing holds it | Low | `main()` keeps the reference. The T4 by-hand run would show it at once. |

## Open questions

- **Owner (from the spec): the icon's new home** in `src/maplelens/data/`. T1 assumes yes.
  If the owner says no, the build copies it there instead, and only T1 changes.
- **Daniel: is a Mac at hand** for the spec's by-hand Mac check, or is it CI only (T6)?
