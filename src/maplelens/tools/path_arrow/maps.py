"""The bundled map data: portals, minimap geometry and cab links."""

import json
from dataclasses import dataclass
from pathlib import Path

DATA = Path(__file__).with_name("maps.json")


@dataclass(frozen=True)
class Portal:
    x: int
    y: int
    to: str


@dataclass(frozen=True)
class Cab:
    x: int
    y: int
    to: tuple[str, ...]


@dataclass(frozen=True)
class Minimap:
    w: int
    h: int
    cx: int
    cy: int


@dataclass(frozen=True)
class MapInfo:
    id: str
    street: str
    name: str
    town: bool
    minimap: Minimap | None
    portals: tuple[Portal, ...]
    cab: Cab | None
    npcs: tuple[tuple[int, int], ...] = ()  # world positions; the minimap marks them

    @property
    def title(self) -> str:
        return f"{self.street} / {self.name}"


def load(path: Path = DATA) -> dict[str, MapInfo]:
    maps = {}
    for e in json.loads(path.read_text(encoding="utf-8")):
        cab = e.get("cab")
        maps[e["id"]] = MapInfo(
            e["id"],
            e["street"],
            e["name"],
            e["town"],
            Minimap(**e["minimap"]) if e["minimap"] else None,
            tuple(Portal(**p) for p in e["portals"]),
            Cab(cab["x"], cab["y"], tuple(cab["to"])) if cab else None,
            tuple((n["x"], n["y"]) for n in e["npcs"]),
        )
    return maps


def find(maps: dict[str, MapInfo], title: str, previous: str | None) -> MapInfo | None:
    """The map with this title; if several share it, the one `previous` leads to."""
    hits = [m for m in maps.values() if m.title == title]
    if len(hits) <= 1:
        return hits[0] if hits else None
    prev = maps.get(previous) if previous else None
    if prev is None:
        return None
    linked = [m for m in hits if any(p.to == m.id for p in prev.portals)]
    return linked[0] if len(linked) == 1 else None


def search(maps: dict[str, MapInfo], text: str, limit: int = 8) -> list[MapInfo]:
    """Maps whose name or street contains `text`; names starting with it first."""
    t = text.strip().lower()
    if not t:
        return []
    hits = [m for m in maps.values() if t in m.name.lower() or t in m.street.lower()]
    hits.sort(key=lambda m: (not m.name.lower().startswith(t), m.name))
    return hits[:limit]
