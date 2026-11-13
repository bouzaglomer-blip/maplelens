# Quest rewards in the Quests tab — design

Issue: [#46](https://github.com/or-keren/maplelens/issues/46) "show requirements and
rewards for quests before accepting them". Mockup:
https://claude.ai/artifact/JAFTcSeoTeZJrjyFAfVX8a (private to the owner; layout A is the
one picked).

## Why

The game's quest window doesn't always show a quest's rewards, on the Available tab or
on In Progress (owner). The player wants to see what a quest pays while deciding whether
to take it, and, for a quest in a chain, what the rest of the chain pays on top.

The screen-only rule in `AGENTS.md` holds: nothing new is read from the screen. The
rewards come from data shipped with the app, for quests the Quests tab already shows.

## Goals

- **Every quest the Quests tab shows gets its rewards** (owner): the quest open in the
  game (Available or In Progress tab) and the tracked quests.
- **One line by default** (owner picked option B of three, below): a reward line with
  EXP and mesos. When the quest has more (items, citizenship contribution, a chain), the
  line starts with ▸ and a click opens the details under it.
- **Everything readable when opened** (owner: "see all of the rewards" instead of "…"):
  the details' text lines wrap; nothing in them is cut.
- **Item pictures** (owner): each reward item shows the game's icon for it (layout A,
  owner).
- **Rest of the chain**: in the details, the EXP and mesos the chain's later quests pay
  together.

## Non-goals

- **A "worth it" mark** on lucrative quests (owner: no mark; the numbers are enough).
- **Rewards for quests not shown in the tab**, and marks drawn over the game's quest list.
  The owner wants pay only for the quests they selected; reading every list row would
  also cost OCR on every tick.
- **Fame.** Neither source has fame rewards; the game shows them.
- **Items of the rest of the chain.** Its line adds up EXP and mesos only.

## Anti-goals

- **A longer tab by default.** Closed, the rewards add exactly one line per quest that
  shows rows (the open quest; the one expanded tracked quest). A tracked quest's
  collapsed header stays one line. Past `MAX_H` the tab scrolls, as today.
- **A confidently wrong item.** When the player's class is unknown, a class-only reward
  isn't guessed: every class's item is shown (rule below).
- **Numbers that differ from the game.** Checked: OSMS gives 7,020 EXP and 1,140 mesos for
  "Collecting 50 Cursed Dolls", as the game's window shows them (issue's screenshot);
  meowdb gives the same numbers as OSMS on the quests both list (10201, 10205, 10700).
- **Fetching anything at runtime**, icons included. Everything ships with the app.

## Approaches (owner picked B, then A for items)

How the rewards fit in the tab:

- **A. Always open.** EXP, items and chain on 2–4 lines under every quest. Everything at a
  glance, but the "where to go" rows slide down or off the bottom.
- **B. One line that opens.** The numbers at a glance; items, contribution and chain on
  click; the tab remembers open or closed. **Chosen.**
- **C. Hover only.** A tooltip on the quest's name: no lines at all, but nothing shows it's
  there, and the mouse has to leave the game for the overlay.

How items show in the opened details:

- **A. Icons in a row**, count on the icon, name on hover; a group of one or two items
  shows the name beside the icon. A 6-item random reward is one line. **Chosen.**
- **B. Icon and name on every line.** Every name readable, but a 6-item random reward is 6
  lines, and some quests offer 7–8.

## How it behaves

### Where the line goes

```
Collecting 50 Cursed Dolls     Closest|Best [Track]     <- the "open" line, as today
▸ 7,020 EXP · 1,140 mesos                                <- new
Rowen the Fairy        Ellinia · gives the quest  ›      <- rows, as today
```

- **The open quest**: right under its name line, above its rows. Same on Available and In
  Progress.
- **A tracked quest**: only while it is expanded, right under its header, above its rows.
  Collapsed headers get nothing *(my call: the list would double in height)*.
- **No reward data**: no line *(my call)*. 13 kept quests have no rewards in OSMS.

### The closed line

- `7,020 EXP · 1,140 mesos`, numbers with thousands separators, words in the label grey
  and numbers in white (as in the mockup). A quest paying only one of them shows that one.
- A quest paying neither shows its items' text instead (e.g. `Red Potion ×20`,
  `1 of 7 items`).
- ▸ at the start only when the details have something the closed line doesn't; then the
  whole line is the click target (it counts as touching the box, as every click does).
  ▾ when open.
- This one line is cut with "…" to the tab's width if it must, full text as tooltip. It
  is short in practice (the longest EXP and mesos fit at the default width).

### The details (▾, opened)

Indented under the reward line, in this order. Text lines **wrap**; nothing is cut.

1. **Items the quest always gives.**
2. **Items you pick** (OSMS `reward_choices`, `choose_one`; 10 quests), under the label
   `You pick 1 of:`.
3. **Random items** (OSMS `reward_random`, the other `guaranteed: false` items), under
   `Random, 1 of:` *(my call: the two work differently in game, so they're worded
   differently)*.
4. **Class-only items** (OSMS `classes`): only those for the player's class branch, under
   `For your class:`. With the class unknown, all of them under `By class:`, each
   icon's tooltip naming its class. Gender-only items (one quest) are both shown, the
   tooltip naming `male` / `female` *(my call)*.
5. **Citizenship contribution**: `Henesys contribution +100` or, when it depends on the
   citizenship grade (OSMS `by_grade`), the range `+100–325`.
6. **Rest of the chain**: `Rest of chain (4 quests): +28,080 EXP · 4,560 mesos`. "Rest" is
   every quest with the same chain name that needs this one done first, directly or
   through other quests of any chain: a story can pass through another chain and come
   back (owner, 2026-11-13: the Abyss story runs Echoes of the Abyss 10612–10614, A Fragile
   Sanctuary 10615–10616, Echoes again 10617–10618, Sanctuary again 10619–10620). Only
   quests of this chain are counted, so a branch into another chain (10508 leads into
   two) adds nothing. Quests not out yet count too (owner: 10617–10620 start
   2026-12-09). A quest with no chain, or whose rest pays nothing, gets no line.

**Items, layout A:** each item group (1–4) is one wrapping row of icons. An icon sits on a
small square slot (the mockup's: 26 px, dark fill), the count in its corner when above 1,
the item's name (and count, class or gender) as its tooltip. A group of **one or two
items** shows each as icon + name on its own line instead (`Blue Potion ×15`). An item
with no icon shows an empty slot with its name beside it, as a one- or two-item group
does *(my call)*.

### Open or closed

One setting for every quest, saved in `settings.json` (`quest_rewards_open`, default
closed) *(my call: a per-quest memory would surprise more than it helps)*. A hand-edited
bad value reads as closed, as `_clean` does for the other keys.

### Class branch

The job reader's names map to the five classes: Beginner; Warrior (Warrior, Fighter,
Page, Spearman and their later jobs); Magician (Magician, Wizard…, Mage…, Cleric, Priest,
Arch Mage…, Bishop); Bowman (Bowman, Hunter, Crossbowman, Ranger, Sniper, Bowmaster,
Marksman); Thief (Thief, Rogue, Assassin, Bandit, Hermit, Chief Bandit, Night Lord,
Shadower). A small table in the quest helper; the tool gets the job from `Reading.job`,
which it already receives.

## The parts

### 1. Data

`quests.json` gains, per quest, its rewards and what the chain needs:

- EXP, mesos; items with count and kind (always, pick, random), classes, gender;
  citizenship contribution (town, amount or by-grade range).
- The chain: each quest's chain name and its prerequisite quests (`after`, every
  prerequisite in the file, whatever its chain).
- Names of every reward item (the `items` table, or a separate name table; builder's
  call).

**Icons:** one PNG per reward item in `src/maplelens/data/item_icons/<item id>.png`
(about 195 files, about 1 KB each, 26–32 px), from OSMS `items.json`'s `icon_url`. Fetched
once by the conversion, politely (identifying user agent, a pause between requests), and
committed. Check that the Windows and Mac builds ship the new folder (the specs in
`packaging/` may list data folders).

**Sources**, by the one-off conversion outside the repo, as the first build of
`quests.json` (existing fields unchanged):

- **OSMS** `quests.json` and `items.json` (CC BY 4.0, already credited): every quest it
  has, joined by quest id.
- **meowdb** `https://meowdb.com/_data/quests.json` (owner's permission; credited) for the
  15 of the 10600s OSMS doesn't have (10600–10604, 10607–10616) (owner). 10613–10616 are
  round one of the Abyss story, separate quests from round two's 10617–10620 (same
  names, other rewards); they were first joined to round two by name, which gave them
  round two's rewards (fixed 2026-11-13). From meowdb:
  `exp`, `mesos`, `get` (items with `itemId`, `name`, `count`), `parent` (the chain name),
  `requiresAll` (prerequisites). **Known gap:** meowdb lists only guaranteed items (for
  10201 it lists none where OSMS lists six random ores), so any random or class rewards of
  these 15 quests don't show. Item names and icons come from OSMS by `itemId` where it has
  them, else meowdb's name and no icon.

Data checks in `tests/`: every reward item id has a name; every chain's "rest" refers to
quests in the file; every reward item has an icon file or is on a short list of known
missing ones.

### 2. Logic (pure, `plan.py`)

From a quest, the data and the player's class branch (or None): the closed line's text,
whether it opens, and the detail groups (label, items with icon id, name, count) and
lines. The rest of the chain and its totals. The job → branch table. Tested without Qt.

### 3. Tab (`ui.py`)

New item kinds for the reward line, a detail line and an icon group, placed as above.
Clicking the reward line flips the setting and redraws. `Reading.job` is kept from
`update`. Icons load once per item id (cached `QPixmap`).

## Done means

- The open quest and the expanded tracked quest show the reward line; ▸ opens and closes
  the details for all quests; the state survives a restart.
- Opened details: all text visible (wrapped), icons shown, names on hover.
- Tests: data checks; the logic's output for a quest with each reward kind (always,
  pick, random, class with and without a class, contribution, chain, a meowdb quest); a
  tab test that the line is there, the toggle works, and an icon group draws.
- `uv run pytest`, `uv run ruff check`, the screen-only guard pass.
- Checked by eye on a screenshot: the tab with a long quest name, the line closed and
  open, at the default tab width; a random reward of 6+ items.
- The frozen build (`--freeze-only`) contains `data/item_icons/`.

## Left to the builder

The JSON schema; whether details are labels or `InfoLine`s; the exact indent, slot size
and spacing (match the Class tab's look and the mockup); wording of item-count fallbacks.
