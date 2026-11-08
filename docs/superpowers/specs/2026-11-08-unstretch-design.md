# Undo the game's stretch instead of resizing

## Problem

The game draws one picture, 768 rows high, and stretches it to the window with bilinear
filtering. `glyphs.normalize` used to shrink the captured frame back to 768 rows (area
averaging). That shrink blurs each glyph differently at every window size and sub-pixel
offset, so exact templates needed a variant per resolution (89 level digits, 36 EXP glyphs,
three of each anchor) and still missed any size nobody had captured: 1920x1200 read nothing.

## Finding

Measured on the owner's grabs at full size (1366x768, 1920x1080, 1920x1200, 2560x1440):

- Every captured frame is a bilinear stretch (half-pixel centres) of a picture 768 rows
  high, aligned to the window's top-left. Re-stretching the solved picture misses the
  shot by under 1 grey level (p99), windows and minimap included.
- The picture is 1366 wide at 16:9 and 1228 at 16:10 (both even; not plain rounding of
  768 x aspect). A width 1 px off misses by 14-32 grey levels.
- The stretch is per axis: width / 1366 across, height / 768 down.

## Design

`glyphs.normalize(frame, origin=(0, 0), client=None)` solves the stretch backwards by
least squares, per axis: two matrix products with inverses cached per window size (normal
equations; the stretch matrix's A'A is tridiagonal). The result is the game's own
picture, so:

- one template per glyph and anchor, pixel-exact at any window size;
- the window readers find their window by its anchor (no sub-pixel search), and OCR reads
  the picture at 3x (no native frame passed around);
- portal spirals are one exact 8x8 / 34 px blob (all 316 seen on the grabs), and the
  "you" dot one 6x6 / 24 px blob (once on each of 291 minimaps); the old ranges, made for
  blurred pixels, let Henesys roofs pass as a second dot;
- a window anchor scores 1.00 where it shows, so it needs 0.9 (another window's title bar
  scored 0.76 for the skill window's);
- OCR upscales the picture 3x bilinear: cubic read "III" as "Ill" and "VII" as "W".

Checked against the old code on the owner's 304 full-size grabs: EXP, level, job and
stats read the same or better (EXP gained on 5 grabs, level on 3, everything on
1920x1200); map names the same but one, now read in full; more portal spirals found
(ones next to map art or at the edge); no false skill window over the inventory.

The picture width is the floor or ceil of 768 x aspect, whichever re-stretches the frame
back best (the even one on a tie, e.g. a black frame); it is kept per window size once
the other is clearly off.

`origin` / `client` let a crop be undone on its own: fixtures are crops as captured, with
their top-left in the window in the file name (`_x<X>_y<Y>`), loaded by `tests/screens.py`.

## Limits

- Below 768 rows (1280x720) the game shrinks its picture and the detail is gone: plain
  resize there, as before, so exact templates mostly miss.
- ~60-80 ms per frame at 1080p-1440p (dense matrices; they are banded, ~20 taps, if it
  ever matters), under 1 s once per window size.
- The overlay still maps picture pixels to the window with one scale (height / 768);
  across that is off by up to 1.3 px at the right edge.
- Mac (Retina 2732x1536, exactly 2x) is untested: its old fixtures were already shrunk
  and are gone until new full-size grabs exist.
