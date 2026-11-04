"""Text for the EXP meter box and history window. Pure: no Qt."""

from datetime import date, datetime

from maplelens.tools.exp_meter.meter import Rate


def format_duration(minutes: float) -> str:
    m = round(minutes)
    if m < 1:
        return "<1m"
    h, m = divmod(m, 60)
    return f"{h}h {m}m" if h else f"{m}m"


def format_box(rate: Rate | None, waiting: bool) -> str:
    if waiting:
        return "waiting for game"
    if rate is None:
        exp, pct, eta = "—", "—", "—"
    else:
        exp = f"{rate.exp_per_min * 60:,.0f}"
        pct = f"{rate.pct_per_min * 60:.2f}"
        eta = "—" if rate.minutes_to_level is None else format_duration(rate.minutes_to_level)
    return f"EXP · last 5 min\n{exp} /h\n{pct}% /h\nLevel up in\n{eta}"


def format_last(ts: float, now: float) -> str:
    day = datetime.fromtimestamp(ts).date()
    days_ago = (date.fromtimestamp(now) - day).days
    if days_ago == 0:
        return "today"
    if days_ago == 1:
        return "yesterday"
    return f"{day:%b} {day.day}"
