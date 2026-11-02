"""EXP bar reader."""

import re

from maplelens.readers import ExpValue

_EXP = re.compile(r"(\d+(?:,\d+)*)\[(\d{1,3}\.\d\d)%\]", re.ASCII)


def parse_exp(text: str) -> ExpValue | None:
    """'23,605 [81.45%]' -> ExpValue(23605, 81.45); None if malformed or pct not in [0, 100)."""
    m = _EXP.fullmatch(text.replace(" ", ""))
    if not m:
        return None
    pct = float(m[2])
    if not 0 <= pct < 100:
        return None
    return ExpValue(int(m[1].replace(",", "")), pct)
