"""Find the game window and grab its pixels. Window geometry and screen capture only."""

import sys


def pick_window(titles: list[tuple[int, str]], title: str) -> int | None:
    """Exact title match wins; otherwise the first substring match."""
    exact = next((h for h, t in titles if t == title), None)
    return exact if exact is not None else next((h for h, t in titles if title in t), None)


if sys.platform == "win32":
    from maplelens.capture_win import (
        client_rect,
        ensure_access,
        find_window,
        grab,
        list_windows,
        set_dpi_aware,
        window_title,
    )
elif sys.platform == "darwin":
    from maplelens.capture_mac import (  # noqa: F401
        client_rect,
        ensure_access,
        find_window,
        grab,
        list_windows,
        set_dpi_aware,
        window_title,
    )
