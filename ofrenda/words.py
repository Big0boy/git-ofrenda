"""Small helpers for saying dates and lifespans the way an epitaph would."""

from __future__ import annotations

from datetime import datetime


def day(when: datetime) -> str:
    return f"{when.day} {when:%b %Y}"


def year(when: datetime) -> str:
    return f"{when:%Y}"


def _plural(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def span(days: float) -> str:
    if days < 1:
        hours = round(days * 24)
        return "less than an hour" if hours < 1 else _plural(hours, "hour")
    if days < 31:
        return _plural(round(days), "day")
    months = round(days / 30.44)
    if months < 12:
        return _plural(months, "month")
    years, months = divmod(months, 12)
    return _plural(years, "year") + (f", {_plural(months, 'month')}" if months else "")
