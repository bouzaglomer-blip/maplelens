"""Build the level digit templates (readers/templates/level_font) from the digit images.

scripts/level_sprites/<d>.png are the status bar's level digit boxes (11x13, one per
digit) as published by maplestory.io. The game draws its 1366x768 picture and scales it
to the window with bilinear filtering; that, then our normalize to 768 rows, gives each
resolution its own pixel shapes. This renders each digit that way at every box position
nearby and keeps every shape it can come out as.

Checked on the owner's grabs: the 2, 3 and 4 cut from real screens at 1366x768,
1920x1080 and 2560x1440 were all reproduced (--check lists any template that is not).

Usage: uv run python scripts/make_level_font.py [--check]
--check only reports; without it the level_font folder is rewritten.
"""

import itertools
import sys
from pathlib import Path

import cv2
import numpy as np

from maplelens.readers import glyphs, level

REPO = Path(__file__).resolve().parent.parent
SPRITES = REPO / "scripts" / "level_sprites"
OUT = glyphs.TEMPLATES / "level_font"
SIZES = {"1366": (1366, 768), "1920": (1920, 1080), "2560": (2560, 1440)}
# Box top-left in the 1366x768 picture: tens and ones box of a two-digit level.
BOXES_X, BOX_Y = (329, 341), 744
# ponytail: 1- and 3-digit levels were never seen; their boxes are assumed to sit within
# SHIFT px of these. A 1366x768 window reads them anyway (no scaling there).
SHIFT = 12
# A pixel within EDGE of the ink cutoff may land either side of it on the real screen
# (the game's rounding differs from this one by 1 level): both shapes are kept.
EDGE = 1


def _shapes(f: np.ndarray, x: int) -> set[tuple[tuple[int, int], bytes]]:
    """Every ink shape of the box at normalized column ~x, edge pixels either way."""
    lo = level.LV_INK_LO[0]
    box = f[BOX_Y - 2 : BOX_Y + 15, x - 2 : x + 13].min(axis=2).astype(int)
    edge = np.argwhere(np.abs(box - lo) <= EDGE)
    out = set()
    for flips in itertools.product((False, True), repeat=len(edge)):
        m = box >= lo
        for (r, c), on in zip(edge, flips, strict=True):
            m[r, c] = on
        if not m.any():
            continue
        rows, cols = np.flatnonzero(m.any(axis=1)), np.flatnonzero(m.any(axis=0))
        g = np.ascontiguousarray(m[rows[0] : rows[-1] + 1, cols[0] : cols[-1] + 1])
        out.add((g.shape, g.tobytes()))
    return out


def build() -> dict[str, dict[str, set]]:
    shapes: dict[str, dict[str, set]] = {r: {} for r in SIZES}
    for d in "0123456789":
        sp = cv2.imread(str(SPRITES / f"{d}.png"), cv2.IMREAD_UNCHANGED)
        opaque = sp[..., 3] == 255
        for res, size in SIZES.items():
            found = shapes[res].setdefault(d, set())
            for x in range(min(BOXES_X) - SHIFT, max(BOXES_X) + SHIFT + 1):
                frame = np.full((768, 1366, 3), 17, np.uint8)
                frame[BOX_Y : BOX_Y + 13, x : x + 11][opaque] = sp[..., :3][opaque]
                up = cv2.resize(frame, size, interpolation=cv2.INTER_LINEAR)  # 1366: as is
                f = glyphs.normalize(up)
                # the box lands at the same normalized column, give or take the rounding
                nx = round(x * f.shape[1] / 1366)
                found |= _shapes(f, nx)
    return shapes


def main(argv: list[str]) -> int:
    shapes = build()
    owner: dict = {}
    for res, by_digit in shapes.items():
        for d, found in by_digit.items():
            for s in found:
                if owner.setdefault(s, d) != d:
                    print(f"shape of {d} at {res} is also {owner[s]}", file=sys.stderr)
                    return 1
    for p in sorted(OUT.glob("*.png")):
        t = cv2.imread(str(p), cv2.IMREAD_GRAYSCALE) > 127
        d = p.stem.split("_")[0]
        if owner.get((t.shape, np.ascontiguousarray(t).tobytes())) != d:
            print(f"{p.name}: not reproduced")
    print(f"{len(owner)} shapes, no shape shared by two digits")
    if "--check" in argv:
        return 0
    for p in OUT.glob("*.png"):
        p.unlink()
    count: dict[str, int] = {}
    for (shape, data), d in sorted(owner.items(), key=lambda kv: (kv[1], kv[0])):
        m = np.frombuffer(data, bool).reshape(shape)
        count[d] = count.get(d, 0) + 1
        cv2.imwrite(str(OUT / f"{d}_{count[d]:03d}.png"), m.astype(np.uint8) * 255)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
