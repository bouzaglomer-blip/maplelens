"""Text for the EXP meter box and history window. Pure: no Qt."""

from datetime import date, datetime

from maplelens.tools.exp_meter.meter import Rate


def format_duration(minutes: float) -> str:
    m = round(minutes)
    if m < 1:
        return "<1m"
    h, m = divmod(m, 60)
    return f"{h}h {m}m" if h else f"{m}m"


def box_lines(
    rate: Rate | None, waiting: bool, unread: bool = False
) -> list[tuple[str, list[str]]]:
    """The EXP tab's content as (grey label, value lines) pairs; `unread`: the bar is unreadable."""
    if waiting:
        return [("waiting for game", [])]
    if rate is None:
        exp, pct, eta = "— /h", "—% /h", "—"
    else:
        exp = f"{rate.exp_per_min * 60:,.0f} /h"
        pct = f"{rate.pct_per_min * 60:.2f}% /h"
        eta = "—" if rate.minutes_to_level is None else format_duration(rate.minutes_to_level)
    if unread:
        label = "EXP · can't read bar"
    elif rate is None or rate.early:
        label = "EXP · measuring"
    else:
        label = "EXP · paused" if rate.paused else "EXP · last 5 min"
    return [(label, [exp, pct]), ("Level up in", [eta])]


def format_last(ts: float, now: float) -> str:
    day = datetime.fromtimestamp(ts).date()
    days_ago = (date.fromtimestamp(now) - day).days
    if days_ago == 0:
        return "today"
    if days_ago == 1:
        return "yesterday"
    return f"{day:%b} {day.day}"


def short_name(title: str) -> str:
    """A map title without its street: "Victoria Island / Henesys" -> "Henesys"."""
    return title.rpartition(" / ")[2]


def best_lines(
    job: str | None, level: int | None, rows: list[tuple[str, float, float]]
) -> tuple[str, list[tuple[str, str, str]]]:
    """The History strip: a header and (map, EXP/h, %/h) per row of `history.best_maps`."""
    if job is None or level is None:
        return "Best maps: waiting for your class and level", []
    head = f"Best for {job}, Lv {level} (±3)"
    if not rows:
        return f"{head}: no 5-minute visits yet", []
    return head, [
        (short_name(m), f"{exp * 60:,.0f} EXP/h", f"{pct * 60:.2f}% /h") for m, exp, pct in rows
    ]
