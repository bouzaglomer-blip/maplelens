# MapleLens

An open-source overlay for **MapleStory Classic** that keeps you in the game.
Instead of alt-tabbing to price sites, class guides and route finders, MapleLens
reads what's on your screen and shows what you need on top of the game window.

> **Status: Phase 0.** The repository, tooling and guardrails are in place.
> There's nothing to run yet. The first tool, the EXP meter, is next.

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

1. **EXP meter:** EXP/hour and time to level at your current spot.
2. **Class helper:** the guide's advice for your level (gear, training spots, AP/SP).
3. **Prices:** market lookups without leaving the game.
4. **Path arrow:** routes drawn as an arrow over the game.

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
