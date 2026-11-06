# Path arrow: place the player by matching the minimap picture

## Why

On tall or wide maps the minimap window shows only part of the map, so the "you" dot
alone doesn't say where you are. Today `camera._scroll` works out how far the window has
scrolled by matching the NPC markers and portal spirals it can see to the map data, and it
needs at least two of them in view. Hidden portals (walk there and press ↑) draw no spiral.
On a map like **The Forest North of Ellinia** (2081×6857, 19 hidden tree-dungeon portals,
2 visible portals, 1 NPC at the very top) most of the map has 0–1 markers in view, so the
tab says "No arrow on this part of the map yet" and the arrow never shows. The owner hit
exactly this.

Better portal data doesn't fix it: our `maps.json` already has every one of those hidden
portals. What's missing is a way to place the player that doesn't depend on markers.

## The source

[OSMS Data Explorer](https://osmsdataexplorer.com) (by ohmi) publishes, per map:

- `data/current/images/maps/<9-digit id>.png`: the clean minimap picture, no markers.
  It is exactly the game's minimap size: 130×428 for The Forest North of Ellinia, whose
  `minimap` is w 2081 / h 6857, i.e. `w/16 × h/16` (our `camera.SCALE`). 299 maps have
  one; together about 4.8 MB (avg 16 KB, max 66 KB).
- `data/current/portals.json`: every portal with a `type`. Type 1 = hidden (no spiral),
  type 2 = normal visible portal, type 3 = another kind (36 of ours).
- `data/current/maps.json`: map list (336 maps; 334 overlap ours, ours has 453).

Checked against our data (2026-11-06): all 598 of our portals on the 328 shared maps pair
with exactly one site portal, using the same destination map and one fixed x/y offset per
map (the site's coordinates are shifted per map; the offset is constant within a map).
Of ours: 421 are type 2, 141 type 1, 36 type 3; 66 maps have at least one hidden portal.
The site lists no map-to-map links between known maps that we lack.

## What the owner decided

- Ship the site's minimap pictures with the app and match the visible minimap against
  them to place the player. (Owner, 2026-11-06: "sounds good".)
- Keep today's marker matching as the fallback for maps with no picture.
- Bring in which portals are hidden, and show a hint on the Path tab when the arrow
  points at one.
- Size is fine; my plan to ship only the pictures that are needed went unchallenged.

## Goals

1. With the minimap open, the arrow shows everywhere on The Forest North of Ellinia,
   bottom to top, and anywhere else a picture exists, whatever markers are in view.
2. When the next portal is hidden, the tab says so, e.g. "Hidden portal: stand on it and
   press ↑" *(wording: builder)*.
3. Nothing that works today gets worse: maps that fit the window and the big town maps
   (Henesys, Kerning City, Perion, Lith Harbor) still place the player.

## Non-goals

- Replacing our `maps.json` with the site's data, or adding the site's 2 extra maps.
- Intra-map teleports (`intra_map` in the site's data). Still not used.
- Live downloads. Pictures and data ship with the app and change by commit, like today.
- Fixing the sideways camera drift noted in `camera.to_screen`; unrelated.

## Anti-goals

- Anything that isn't screen reading. We compare captured minimap pixels with a picture
  we ship. No game files are read to build anything (the pictures come from the website),
  no memory, no input. The guard must stay green.
- A wrong position shown with confidence. If the match isn't clear, return None and hide
  the arrow, same as today.
- A new dependency. `cv2` and `numpy` are already in.

## How it works

### 1. Data (one-off conversion, outside the repo)

Same rule as the original path arrow spec: the conversion runs once outside the repo and
only our files are committed.

- **Pictures:** `src/maplelens/data/minimaps/<id>.png`, our 9-digit ids. Ship only maps
  whose picture can be bigger than the minimap window, i.e. the ones that can scroll
  *(my call)*. The builder works out the window's largest size from fixtures/code; if
  that can't be pinned down, ship all 299 (4.8 MB is acceptable).
- **Hidden flag:** in `maps.json`, a portal with no spiral on the minimap gets
  `"hidden": true`; others leave it out. Pair each of our portals to the site's by
  destination map + the map's one offset (above). Type 1 is hidden. Whether type 3 shows
  a spiral is unknown: the builder checks one type-3 portal in an owner grab, or asks the
  owner to look in-game, and sets the flag to match.
- `maps.Portal` gains `hidden: bool = False`.

### 2. Placing the player (`camera.py`)

New first step in `player_world` for a clipped window: if the map has a picture, find
the scroll by matching the window's pixels against the picture over the possible scroll
range (`cv2.matchTemplate` or similar; the window is a crop of the picture plus markers).

- The window is in normalized px and the picture is in minimap px; they're meant to be
  1:1 (that's what `fits`/`same_size` already rely on). Normalization resampling may
  blur it slightly; the match must tolerate that.
- Markers (dot, NPCs, spirals, other players' dots) sit on top of the picture and must
  not throw the match off: mask them out or use a score that shrugs them off *(builder)*.
- Accept the best scroll only if it's clearly better than the next best one away from it
  (a margin, like `_scroll`'s). Repetitive art (the tree columns in this very map) is the
  risk; the margin is the guard. Otherwise None.
- No picture, or no clear match → today's `_scroll` (marker matching), unchanged except
  that hidden portals no longer predict a spiral (fewer false candidates).
- `can_place` and the tab's "No arrow on this part of the map yet" line follow: a map
  with a picture can always be placed in principle.
- Loading pictures: lazily per map, cached *(builder)*.

### 3. Hidden-portal hint (`ui.py`)

When the trip's current target is a hidden portal, the tab shows one extra line saying so.
When the player can't be placed (no target), the line still shows if every portal to the
next map is hidden *(my call)*. Only for portals, not cab steps. Exact wording and
placement in the tab: builder, within the existing style.

Also my calls: the window's pixels reach `camera.py` however the builder sees fit
(`MinimapView` doesn't carry them today); portals on the 125 maps the site lacks keep
`hidden` off; a picture whose size isn't `w/16 × h/16` (±1) isn't shipped.

## Spike first

Before building on it, the builder proves the match on real grabs: the owner provides
`scripts/grab.py` crops of the minimap on The Forest North of Ellinia at three heights
(bottom, middle, top) and one on a big town map, **at each of 1366x768, 1920x1080 and
2560x1440** (owner, 2026-11-06: it must work at all three, like the marker matching).
Score and margin are set from all three, so no resolution gets a confident wrong answer. Same fixture
rules as before: map area only, no other players nearby, owner reviews every PNG before
commit. If the picture doesn't line up with the game's minimap well enough to give one
clear answer, stop and bring it back to the owner.

## Tests

- Fixture tests, per resolution (1366, 1920, 2560): the Forest North grabs give a world
  position within a few minimap px of the truth; a big-map grab still works.
- A unit test that a view not matching anywhere (e.g. noise) returns None.
- The shipped-data test also checks every picture's size is `w/16 × h/16` (±1) of its
  map's `minimap`, and every `hidden` flag sits on a portal.

## Docs to update

- `README.md` credit: add "Minimap pictures and portal types from
  [OSMS Data Explorer](https://osmsdataexplorer.com)." next to the meowdb line.
- `AGENTS.md` Layout: add `data/minimaps/`.

## Done means

With the game windowed or borderless and the minimap open, the owner can:

1. start a route into the Tree Dungeons from The Forest North of Ellinia and see the
   arrow at every height on that map;
2. see the hidden-portal line when the arrow points at a tree-dungeon entrance;
3. still get the arrow on Henesys / Kerning City and on a small map that fits.

`uv run pytest`, `uv run ruff check`, `uv run ruff format --check` and the guard pass.

## Left to the builder

Match method, mask/score and margin; how the window's max size is found; picture loading
and caching; hint wording and placement; the type-3 check.
