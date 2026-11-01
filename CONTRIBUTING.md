# Contributing to MapleLens

Thanks for helping. Please read the rule below first. It's the one thing we never bend.

## The rule

MapleLens is **screen-reading only**. It may capture pixels of the game
window and draw its own separate window on top. It must never:

- read or write game process memory, or inject into / attach to the process
- read, modify, or hook game files or the client's network traffic
- send input (keys/clicks) to the game — no automation of any kind

Breaking this can get players banned. Pull requests that break it are closed,
however useful the feature. If you're not sure whether an idea crosses the
line, open an issue and ask first.

## Setup

You need [uv](https://docs.astral.sh/uv/) (`winget install astral-sh.uv`).

```
git clone https://github.com/<you>/maplelens.git
cd maplelens
uv sync
```

## Checks (CI runs exactly these)

```
uv run ruff check
uv run ruff format --check                   # `uv run ruff format` fixes it
uv run python scripts/check_screen_only.py   # screen-only guard
uv run pytest
```

## Workflow

1. Fork the repo and create a branch: `git checkout -b exp-meter-level-reader`.
2. Make your change, with tests.
3. Run the checks above.
4. Open a pull request and fill in the template. The `check` job must pass.

## What a good pull request looks like

- **Small:** one tool, one reader, or one fix.
- **Tested:** readers come with fixture screenshots and a test that reads them.
- **Explained:** what in-game moment it helps, and how you tested it in game, if you did.

## Adding a fixture screenshot

Readers are tested against saved screenshots, so nobody needs the game open to run tests.

- Crop to the region the reader needs (EXP bar, minimap…), never the full screen.
- **Never** include character names, chat, or other players' info.
- Put resolution and UI scale in the filename, e.g. `exp_bar_1366x768_100.png`.
- Save under `tests/fixtures/screens/`.

## Using an AI coding agent

Welcome. Claude Code, Codex, Cursor and similar tools read `AGENTS.md`
automatically, so they know the rule and the commands. You don't have to set
anything up. Claude Code also runs the guard after every edit.

You're still responsible for what you submit: read the code, run it, and make sure it
does what the PR says.

## Reporting problems

- **Bugs and ideas:** open an issue from the templates.
- **Security problems, or code that could get players banned:** don't open a public
  issue. See [SECURITY.md](SECURITY.md).

By taking part you agree to the [Code of Conduct](CODE_OF_CONDUCT.md).
