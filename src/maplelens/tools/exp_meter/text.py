"""Text for the EXP meter box and history window. Pure: no Qt."""

from datetime import date, datetime

from maplelens.tools.exp_meter.meter import Rate


def format_duration(minutes: float) -> str:
    m = round(minutes)
    if m < 1:
        return "<1m"
    h, m = divmod(m, 60)
    return f"{h}h {m}m" if h else f"{m}m"


def box_lines(rate: Rate | None, waiting: bool) -> list[tuple[str, list[str]]]:
    """The EXP tab's content as (grey label, value lines) pairs."""
    if waiting:
        return [("waiting for game", [])]
    if rate is None:
        exp, pct, eta = "— /h", "—% /h", "—"
    else:
        exp = f"{rate.exp_per_min * 60:,.0f} /h"
        pct = f"{rate.pct_per_min * 60:.2f}% /h"
        eta = "—" if rate.minutes_to_level is None else format_duration(rate.minutes_to_level)
    label = "EXP · paused" if rate and rate.paused else "EXP · last 5 min"
    return [(label, [exp, pct]), ("Level up in", [eta])]


def format_last(ts: float, now: float) -> str:
    day = datetime.fromtimestamp(ts).date()
    days_ago = (date.fromtimestamp(now) - day).days
    if days_ago == 0:
        return "today"
    if days_ago == 1:
        return "yesterday"
    return f"{day:%b} {day.day}"
