"""Quest window reader: which quest the game's quest window shows (the reading comes later)."""

from dataclasses import dataclass


@dataclass(frozen=True)
class QuestOpen:
    name: str  # as read; it may match no quest in the data
    taken: bool | None  # True: the In Progress tab, False: Available, None: can't tell
