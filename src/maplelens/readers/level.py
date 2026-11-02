"""Character level reader."""


def parse_level(text: str) -> int | None:
    """Digits only, 1..200, else None."""
    if not (text.isascii() and text.isdigit()):
        return None
    level = int(text)
    return level if 1 <= level <= 200 else None
