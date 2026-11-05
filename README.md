# MapleLens

An open-source overlay for **MapleStory Classic** that keeps you in the game.
Instead of alt-tabbing to price sites, class guides and route finders, MapleLens
reads what's on your screen and shows what you need on top of the game window.

> **Status: Phase 2: path arrow.** The EXP meter (EXP/min, time to level, History window)
> is built, and so is the path arrow: pick a destination on the Path tab and an arrow over
> your character points the way, map by map.
>
> Map and portal data adapted from [meowdb](https://meowdb.com/msclassic).

## The promise: screen-reading only

MapleLens is **screen-reading only**. It may capture pixels of the game
window and draw its own separate window on top. It must never:

- read or write game process memory, or inject into / attach to the process
- read, modify, or hook game files or the client's network traffic
- send input (keys/clicks) to the game — no automation of any kind

Every change is checked by `scripts/check_screen_only.py` in CI. That script is
a speed bump against honest mistakes, not a security boundary. The rule itself
is what matters, and pull requests that break it are not accepted.

## Requirements

- Windows 10/11
- The game running **windowed or borderless**. True fullscreen hides overlay windows.

## Roadmap

1. **EXP meter:** EXP/min, time to level, and history per map.
2. **Path arrow:** routes drawn as an arrow over the game.
3. **Class helper:** the guide's advice for your level (gear, training spots, AP/SP).
4. **Prices:** market lookups without leaving the game.

## Run

Start the game windowed or borderless, then save its window title once and run:

```
uv run python scripts/grab.py --title <game title> --label first
uv run maplelens
```

Drag the box where you want it. History opens the per-map table.

## Development

```
git clone https://github.com/or-keren/maplelens.git
cd maplelens
uv sync
```

Then `uv run pytest`. See [CONTRIBUTING.md](CONTRIBUTING.md) for the full guide.

## Disclaimer

Unofficial fan project; not affiliated with Nexon. MapleStory is a trademark of
Nexon. Use at your own risk.

## License

[MIT](LICENSE)
