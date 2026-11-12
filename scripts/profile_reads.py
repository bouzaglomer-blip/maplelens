"""Time `read_all` per reader on saved frames, to measure a change to the per-tick work.

Usage: profile_reads.py FRAME... [--passes N]
Each frame is cropped with `capture.picture_box`, then all frames are read in order N times
(default 3) after one warm-up pass, the way a tick would. Prints the median and max of one
`read_all` call, then ms per tick and calls per tick for each reader (R) and each inner cost
(normalize, find_anchor, window.align, read_scaled). Inner costs sit inside the readers' time.
It never captures: it only reads the PNG files it is given.
`taskpolicy -b uv run python scripts/profile_reads.py ...` runs it on the efficiency cores,
a worse case than Game Mode (15x vs 8.7x measured).
"""

import argparse
import statistics
import time
from pathlib import Path

import cv2

from maplelens import capture
from maplelens.readers import (
    exp,
    glyphs,
    job,
    level,
    map_name,
    minimap_pos,
    quest_tracker,
    quest_window,
    read_all,
    skill_window,
    stat_window,
    window,
)

READERS = [
    (exp, "read_exp"),
    (level, "read_level"),
    (job, "read_job"),
    (map_name, "read_map_name"),
    (minimap_pos, "read_view"),
    (stat_window, "read_stat_window"),
    (skill_window, "read_skill_window"),
    (quest_window, "read_quest_window"),
    (quest_tracker, "read_quest_tracker"),
]
INNER = [
    (glyphs, "normalize"),
    (glyphs, "find_anchor"),
    (window, "align"),
    (glyphs, "read_scaled"),
]


def _load(path: str):
    frame = glyphs.imread(Path(path), cv2.IMREAD_COLOR)
    if frame is None:
        raise SystemExit(f"cannot read {path}")
    x, y, w, h = capture.picture_box(frame)
    return frame[y : y + h, x : x + w]


def _wrap(totals, originals, mod, name, label):
    fn = getattr(mod, name)
    originals.append((mod, name, fn))
    totals[label] = [0.0, 0]

    def timed(*a, **k):
        t0 = time.perf_counter()
        try:
            return fn(*a, **k)
        finally:
            totals[label][0] += time.perf_counter() - t0
            totals[label][1] += 1

    setattr(mod, name, timed)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("frames", nargs="+")
    ap.add_argument("--passes", type=int, default=3)
    args = ap.parse_args(argv)
    frames = [_load(p) for p in args.frames]

    totals: dict[str, list[float]] = {}  # label -> [seconds, calls]
    originals = []
    for mod, name in READERS:
        _wrap(totals, originals, mod, name, f"R {name}")
    for mod, name in INNER:
        _wrap(
            totals,
            originals,
            mod,
            name,
            name if mod is glyphs else f"{mod.__name__.rsplit('.', 1)[-1]}.{name}",
        )
    try:
        for f in frames:  # warm-up: fills the caches a running tick would have
            read_all(f, 0.0)
        for v in totals.values():
            v[:] = [0.0, 0]
        times = []
        for _ in range(args.passes):
            for f in frames:
                t0 = time.perf_counter()
                read_all(f, 0.0)
                times.append((time.perf_counter() - t0) * 1000)
    finally:
        for mod, name, fn in originals:
            setattr(mod, name, fn)

    n = len(times)
    print(f"read_all ms: median {statistics.median(times):.0f}  max {max(times):.0f} (n={n})")
    for label, (sec, calls) in totals.items():
        print(f"  {label:<22} {sec * 1000 / n:7.1f} ms  {calls / n:5.1f} calls")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(__import__("sys").argv[1:]))
