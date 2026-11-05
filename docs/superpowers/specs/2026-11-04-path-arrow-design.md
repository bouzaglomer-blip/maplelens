# MapleLens — Phase 2 design: path arrow + overlay tabs

Date: 2026-11-04. Status: approved by owner 2026-11-04.

## Intent

When a quest sends the owner somewhere, today they open a fan site, run its path
finder (start map → destination map), and then keep checking the site's pictures to see
**which portal to take on each map**. That last part is the pain (owner: "to always
understand where are the portals I need to go to in each map").

The path arrow removes the site from the loop. You pick a destination in the overlay,
and a plain arrow over your character points at the next portal, on every map, until you
arrive. The overlay box gets one tab per tool, so this and later tools (class helper,
prices) share one small box.

The screen-only rule in `AGENTS.md` holds for every part of this document. The tool
reads pixels and draws its own windows. It never presses keys or clicks for the player.

## Goals

- **Path tab in the overlay box** (owner): type part of a map name, pick the destination,
  tick or untick **Use taxi**, press **Start**. The route starts from the map you're on.
- **Route list on the overlay** (owner): while a route runs, the Path tab lists the maps
  on it. Maps already passed are crossed out and yours is highlighted. **Stop** ends it.
- **Arrow only during a running route** (owner): a plain arrow just above the
  character, aimed in a **straight line** at the next portal (owner picked mockups A and D).
  On a taxi leg it aims at the Regular Cab NPC instead.
- **Reroute on a wrong turn** (owner: "the path should change accordingly"): if you land
  on a map that isn't the next one on the route, the route is recomputed from that map.
- **Tabs** (owner asked, I recommended): one box, a tab strip at the top, one tab per
  tool. EXP is the first tab, Path the second. Hidden tabs keep running. A dot on the Path
  tab shows a route is running while you look at another tab.
- **New look for the EXP tab** (owner, 2026-11-04: "like in the artifact"): the same
  content as today's box, laid out as in mockup 1. Small grey labels ("EXP · last 5 min",
  "Level up in"), the values larger and bold beneath them, and History as a button at the
  bottom. The same look carries over to the Path tab, so the box reads as one design.
- **Our own map data file** (owner): a bundled file in our own format, holding only what
  the tool needs, built so maps can be added later.

Mockups the owner reacted to: https://claude.ai/artifact/SVf4ei24LGX6btFXyErtjJ
(states 1 to 4 of the box; the arrow is mockup A, aimed as in D).

## Non-goals

- **Walking-path arrow** (mockup E: aim at the next rope or ladder). The data has no
  platforms or ropes. The straight-line arrow is the design; the owner works out the climb.
- **Teleports within a map** (the data has them as `intraPortals`). Not used for now.
- **Return scrolls**, boats, and other travel items or NPCs besides the Regular Cab.
- **Choosing the destination by NPC, mob or quest.** Destination is a map, picked by name.
- **Remembering a running route across restarts.** Quitting ends the route *(my call)*.
- **Live updates of the map data.** The file ships with the app and changes by commit.

## Anti-goals

- Anything breaking the screen-only rule. In particular: no network fetch at runtime and
  no reading of game files to build the map data,
  and no call that focuses or activates the game window.
- An arrow that points somewhere wrong with confidence. When the tool isn't sure where
  you are (map unreadable, minimap closed, map not in the data), the arrow hides and the
  Path tab says why. It never shows a stale or guessed direction.
- The EXP meter getting worse: only its look changes. Its numbers, "waiting for game"
  state, history, History button, saved box position and right-click menu (Quit) stay as today.
- An overlay that blocks clicks to the game outside MapleLens's own box. The arrow is
  drawn on the existing click-through `Layer`.

## How it behaves (owner decided unless marked)

**Starting.** On the Path tab: a "From:" line with the map you're on, a search field,
a list of matches, a **Use taxi** checkbox, and **Start**. Typing filters maps by a
case-insensitive substring of the map name or street name *(my call)*. Use taxi is
remembered in `settings.json` *(my call: default on, as the owner's earlier mockup
reaction showed it ticked)*. Start is disabled while the current map is unknown.

**Typing and focus** (owner, 2026-11-04). Today every MapleLens window refuses keyboard
focus. The search field has to take focus so you can type, and only while you're typing
in it; the rest of the box and the EXP tab keep refusing focus as today. While the field
has focus the game gets no keys. After Start, you click back into the game yourself.
MapleLens never activates, focuses or brings forward the game window (owner picked this
over bringing the game forward: MapleLens only ever looks at the game window).

**Route.** Fewest map changes from the current map to the destination, over portals
from the data, plus cab rides when taxi is on. Ties broken any stable way *(builder)*.
If no route exists, the tab says so and nothing starts.

**Running.** The tab shows "To <destination> · <n> of <total>" and the route list
(mockup 3). The arrow sits just above the character's head and aims at the next portal.
If the current map has several portals to the next map, it aims at the nearest one
*(my call)*. On a cab leg it aims at the Regular Cab NPC.

**Map changes.** On each change of the read map name:
- next map on the route → advance;
- another map further on the route → jump to it;
- off the route → recompute from here, keeping the destination and taxi choice.

**Arriving** *(my call, owner did not object)*. When you reach the destination the arrow
hides, the tab shows "Arrived at <map>" for about 5 seconds, then returns to the search
state.

**When it can't see** *(my call, owner did not object)*. The route stays running in
every case below. Only the arrow hides, and the tab shows one line saying why. It comes
back on its own once the problem clears.
- map name read but the "you" dot not found (minimap minimized to its bar, or its map
  area covered): "Open your minimap to see the arrow", straight away;
- map name unreadable. The map name comes from the minimap's own title, so a closed
  minimap and a loading screen look the same. Silent for short gaps; after about
  3 seconds unreadable, the same "Open your minimap to see the arrow" *(my call; the
  builder tunes the delay)*. While it's unreadable, map changes go unseen; when it comes
  back, the jump and reroute rules catch up;
- map read but not in the data: "This map isn't in MapleLens's map list yet";
- map in the data but has no minimap (47 of 453 maps): route list only, "No minimap on
  this map".

## The parts

### 1. Map data file (ours)

`src/maplelens/tools/path_arrow/maps.json`, one entry per map. Our format, nothing
else from the source kept:

```json
{
  "id": "000000001",
  "street": "Maple Road",
  "name": "Mushroom Town - West Entrance",
  "town": true,
  "minimap": {"w": 1498, "h": 985, "cx": 254, "cy": 310},
  "portals": [{"x": 1116, "y": 365, "to": "000000010"}],
  "cab": {"x": 833, "y": 125, "to": ["…"]},
  "npcs": [{"x": -46, "y": 280}, {"x": 833, "y": 125}]
}
```

- `minimap` is null for maps with no minimap. `cab` is absent unless the map has a
  Regular Cab.
- `npcs` holds every NPC's world position; the minimap marks them, and big maps use
  them to place you (section 4, "Big maps").
- World → minimap fraction: `fx = (x + cx) / w`, `fy = (y + cy) / h` (verified against the
  source's own path finder code).
- Cab destinations: the source has cabs in Henesys, Ellinia, Kerning City, Perion and
  Sleepywood, and treats any cab town as reachable from any other. The builder writes that
  into each `cab.to` and confirms the list in-game with the owner (one ride is enough to
  see the cab's menu).
  The data has six cab towns: those five plus Lith Harbor, whose VIP Cab (NPC 104) the
  source treats as a cab too.
- Only portals that lead to another map are kept. Which source portal types those are is
  the builder's call from the data.
- The source is the map data behind meowdb's MapleStory Classic path finder
  (`https://meowdb.com/_data/maps.json`). The conversion is a **one-off run outside the
  repo** *(my call: the owner wants none of the source's format kept)*. Only our file is
  committed. Its format is this section.
- Map names are matched to the map-name reader's output, which is
  `"<street> / <name>"`. Five street + name pairs repeat in the data (e.g. two
  "Maple Road / Mushroom Town"). When the read name matches several entries, pick the one
  that the previous map has a portal to; if still ambiguous, treat the map as unknown.

### 2. Player position reader (new, the risky part)

`readers/minimap_pos.py`: normalized frame → the yellow "you" dot's position as a
fraction `(fx, fy)` of the minimap's map area, or `None`. Pure function, tested against
fixture PNGs, like every reader.

- It finds the minimap via the same anchors `map_name.py` already uses, then the map
  area below the title, then the dot by colour. Colours, offsets and sizes are named
  constants from fixtures *(builder)*.
- `None` when the minimap is closed, in bar form, covered, or the dot isn't found.
- `Reading` gains a `player: tuple[float, float] | None` field and `read_all` fills it.
- **Fixtures.** The existing minimap fixtures stop above the map area on purpose: it shows
  other players' dots. The new fixtures need the map area. Capture them on maps with no
  other players around, and the owner reviews every new PNG before commit (same rule as
  Task 5 Step 7 of the EXP meter plan). The owner provides grabs with `scripts/grab.py`.

### 3. Route logic (pure)

`tools/path_arrow/route.py`: load the data, find a map by read name, search by text,
plan a route (fewest hops, optional cab edges), and step a running route on each map
change (advance / jump / reroute / arrived). No Qt. Unit tests on a small hand-made graph,
plus one test that the shipped file loads and every portal's `to` exists in it.

### 4. Where to draw the arrow

The arrow needs the **character's spot on the screen**. The minimap gives the player's
world position. The screen position is the camera's offset: the camera follows the
character and stops at the map's edges.

Approach *(builder, must spike first)*: estimate the camera from the player's world
position, the visible world size (the game scales with the window; frames normalize to
768 high), and the map's bounds from `minimap`. Then character screen spot = world
position − camera. Check it against the owner's grabs, including one near a map edge.
If it's good in the middle of maps but off near edges, that's acceptable for now; mark
the ceiling with a `ponytail:` comment. If it can't be made to work, stop and bring it
back to the owner before building on it. Don't fall back to reading the character's
name tag: that's another player's-info-style read we don't want.

**Spike result and owner decision (2026-11-04).** Scale and height work (portals land
within ~5 px; 1 world unit = 1 normalized px). Sideways, the game camera lets the
character drift up to ~128 px from screen centre, and the minimap doesn't show by how
much, so mid-map the estimate can be off by that much (median 65 px over 76 frames). At
a map edge, where the camera stops, it's exact. The owner chose to keep this: the arrow
sits near screen centre, moves to the exact spot at map edges, and always points the
right way. Drawing it on the minimap instead was offered and declined.
Vertically, the camera isn't stopped at the minimap's top edge (some maps show ~330 units
above it), so only the bottom edge clamps.

**Big maps.** Henesys, Kerning City, Perion and Lith Harbor are bigger than the minimap
window, which scrolls to keep the player in the middle, so the dot alone doesn't give a
position there. The owner asked for a second spike: match the portal (and NPC) markers
visible in the window against the map data to recover how far the window has scrolled.
Where that gives no unambiguous answer, those maps get the route list and no arrow.

Arrow direction = from the player's world position to the target's world position,
straight line. It's drawn on the shared `Layer`, which is already excluded from capture,
so readers never see it.

### 5. Tabs in the overlay

The tab strip belongs to `overlay.py`, not to a tool, so tools still never depend on each
other. Shape *(builder)*: the box takes tabs, each a title + a widget the tool owns; the
app adds the EXP meter's tab, then the Path tab. History stays a button on the EXP tab
(mockup 1). The right-click menu (Quit) stays on the whole box. The box keeps its saved position under its current settings key
so nobody's box jumps.

The EXP tab shows today's content in the new look (mockup 1): labels and values as
separate lines, not one monospace text block. `text.py` stays pure (no Qt); it hands
the tab label/value pairs instead of one string *(builder decides the exact shape)*. The Path tab has three
states: choosing (mockup 2), running (mockup 3), and the short "Arrived" line. The tab
dot (mockup 4) shows whenever a route is running.

### 6. App wiring

`app.py` makes the path tool next to the EXP tool and feeds both the same `Reading` and
game rect each tick. No new dependency: Qt already has what tabs and drawing need.

## Docs to update

- `AGENTS.md` Layout: add `tools/path_arrow/` and `readers/minimap_pos.py`; drop path arrow
  from "Planned, not yet created".
- `README.md`: status line for Phase 2. The roadmap order already lists the path arrow
  second. Add one credit line (owner, 2026-11-04): map and portal data adapted from
  [meowdb](https://meowdb.com/msclassic).
- Harness design (2026-11-01) lists the path arrow last; add a one-line note that the
  owner moved it to second (the EXP meter spec already records that).

## Done means

With the game windowed or borderless and the minimap open, the owner can:

1. see the EXP tab in the new look, with the same numbers as before;
2. on the Path tab, find a destination by typing part of its name and press Start;
3. follow the arrow over their character through each map to the destination, with the
   route list keeping up;
4. take a wrong portal on purpose and see the route and arrow change;
5. do one trip with a cab leg (taxi on) and one without (taxi off);
6. close the minimap and see the arrow hide with the message, then come back.

`uv run pytest`, `uv run ruff check`, `uv run ruff format --check` and the guard all pass.

## Left to the builder

Colours, sizes and offsets for the dot reader; the tab widget's look within the
existing box style; the arrow's size, colour and how far above the head it sits; route
tie-breaking; which source portal types count; how the box API changes to take tabs.
