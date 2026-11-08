"""Job (class) reader: the line right of the level, above the character name."""

import difflib

import numpy as np

from maplelens.readers import glyphs, ocr

# ponytail: wizard/mage spellings below are unverified on screen; check them on a grab.
# ponytail: a dropped word that leaves another job ("Chief Bandit" -> "Bandit") reads
# that job; only a word prior could tell.
JOBS = frozenset(
    {
        "Beginner",
        "Warrior",
        "Magician",
        "Bowman",
        "Thief",
        "Rogue",
        "Fighter",
        "Page",
        "Spearman",
        "Wizard (Fire, Poison)",
        "Wizard (Ice, Lightning)",
        "Cleric",
        "Hunter",
        "Crossbowman",
        "Assassin",
        "Bandit",
        "Crusader",
        "White Knight",
        "Dragon Knight",
        "Mage (Fire, Poison)",
        "Mage (Ice, Lightning)",
        "Priest",
        "Ranger",
        "Sniper",
        "Hermit",
        "Chief Bandit",
        "Hero",
        "Paladin",
        "Dark Knight",
        "Arch Mage (Fire, Poison)",
        "Arch Mage (Ice, Lightning)",
        "Bishop",
        "Bowmaster",
        "Marksman",
        "Night Lord",
        "Shadower",
    }
)

# Single words of multi-word jobs that are no job themselves ("Chief", "Knight").
_PART_WORDS = {w for j in JOBS for w in j.split()} - JOBS

# Class line box, relative to the lv_label anchor's top-left (normalized frame).
# Rows -6..6 hold the line with its descenders; the name line starts at row 9.
# It ends 2 px before the HP gauge's border. ponytail: a long job like
# "Arch Mage (Ice, Lightning)" may not fit; unverified, no grab of one
JOB_DX, JOB_DY, JOB_W, JOB_H = 70, -6, 128, 13
# Ink: the light grey letters; the dark status bar behind them stays below 100.
JOB_INK_LO, JOB_INK_HI = (128, 128, 128), (255, 255, 255)


def read_job(frame: np.ndarray) -> str | None:
    """Job name from a normalized frame, or None if unreadable or not close to a known job."""
    y0 = max(0, frame.shape[0] - glyphs.STATUS_BAND)
    hit = glyphs.find_anchor(frame[y0:], "lv_label")
    if hit is None:
        return None
    x, y = hit[0] + JOB_DX, y0 + hit[1] + JOB_DY
    if y < 0:
        return None
    img = ocr.crop(frame, (x, y, JOB_W, JOB_H))
    lines = ocr.read_lines(glyphs.mask(img, JOB_INK_LO, JOB_INK_HI))
    if not lines:
        return None
    # OCR may misread a letter ("Roque"); snap to the nearest known job, but not across
    # dropped letters ("Herm" -> "Hermit") or a dropped word ("Chief" -> "Thief").
    text = " ".join(lines)
    if text in _PART_WORDS:
        return None
    near = difflib.get_close_matches(text, JOBS, n=1, cutoff=0.8)
    return near[0] if near and abs(len(near[0]) - len(text)) <= 1 else None
