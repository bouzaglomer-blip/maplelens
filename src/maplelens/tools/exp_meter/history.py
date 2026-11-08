"""SQLite storage for finished EXP segments, and the per-map/class/level history table."""

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from maplelens.tools.exp_meter.meter import Segment


@dataclass
class HistoryRow:
    map_name: str
    job: str
    level: int
    exp_per_min: float
    pct_per_min: float
    active_s: float
    last: float


def open_db(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS exp_segments(start REAL PRIMARY KEY, end REAL, map TEXT,"
        " job TEXT, level INTEGER, exp INTEGER, pct REAL, active_s REAL)"
    )
    return conn


def save_segment(conn: sqlite3.Connection, seg: Segment) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO exp_segments VALUES (?,?,?,?,?,?,?,?)",
        (seg.start, seg.end, seg.map_name, seg.job, seg.level, seg.exp, seg.pct, seg.active_s),
    )
    conn.commit()


def history(conn: sqlite3.Connection) -> list[HistoryRow]:
    rows = conn.execute(
        "SELECT map, job, level, SUM(exp) / SUM(active_s) * 60, SUM(pct) / SUM(active_s) * 60,"
        " SUM(active_s), MAX(end) FROM exp_segments WHERE active_s > 0"
        " GROUP BY map, job, level ORDER BY MAX(end) DESC"
    )
    return [HistoryRow(*r) for r in rows]


def best_rate(conn: sqlite3.Connection, title: str) -> float | None:
    """The highest per-level EXP/min on one map, grouped as `history` does."""
    (best,) = conn.execute(
        "SELECT MAX(r) FROM (SELECT SUM(exp) / SUM(active_s) * 60 AS r FROM exp_segments"
        " WHERE map = ? AND active_s > 0 GROUP BY job, level)",
        (title,),
    ).fetchone()
    return best
