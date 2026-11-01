# MapleLens — agent instructions

A screen-reading-only overlay for MapleStory Classic. Read this before changing anything.

## The rule (non-negotiable)

MapleLens is **screen-reading only**. It may capture pixels of the game
window and draw its own separate window on top. It must never:

- read or write game process memory, or inject into / attach to the process
- read, modify, or hook game files or the client's network traffic
- send input (keys/clicks) to the game — no automation of any kind

Breaking this can get players banned. `scripts/check_screen_only.py` enforces
it in CI and after every Claude Code edit. If a task seems to need any of the
above, stop and say so instead of working around it.

## Commands

```
uv sync                                      # set up / update the environment
uv run pytest                                # tests
uv run ruff check                            # lint
uv run ruff format                           # format
uv run python scripts/check_screen_only.py   # screen-only guard
```

## Layout

- `src/maplelens/` — the package (empty in Phase 0)
- `scripts/check_screen_only.py` — the guard; banned lists live there, with reasons
- `tests/` — pytest; `tests/fixtures/screens/` holds cropped PNG screenshots
- `docs/superpowers/specs/`, `docs/superpowers/plans/` — designs and plans

Planned, **not yet** created (add when the EXP meter needs them):
`capture/` (grab the game window), `readers/` (screenshot → value),
`overlay/` (the see-through window), `tools/<name>/` (one folder per tool:
exp meter, class helper, prices, path arrow).

## Conventions

- Readers are pure functions `screenshot -> value`, tested against PNG
  fixtures, so tests never need the game running.
- Each tool lives in its own folder and depends only on readers + overlay,
  never on another tool.
- Don't add a dependency for what a few lines can do. Never add a module on
  the guard's banned list.
- Don't write the banned module or Win32 names in comments or docstrings under
  `src/` or `scripts/` — the guard matches text.

## Fixture screenshots

- Crop to the region the reader needs (EXP bar, minimap…), never the full screen.
- Never commit character names, chat, or other players' info.
- Put resolution and UI scale in the filename, e.g. `exp_bar_1366x768_100.png`.
