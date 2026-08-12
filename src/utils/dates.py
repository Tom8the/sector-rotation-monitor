from __future__ import annotations

from datetime import date, timedelta


def yyyymmdd(value: date) -> str:
    return value.strftime("%Y%m%d")


def lookback_start(end_date: date, days: int) -> str:
    return yyyymmdd(end_date - timedelta(days=days))

