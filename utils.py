from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import config

TZ = ZoneInfo(config.TIMEZONE)


def now() -> datetime:
    return datetime.now(TZ)


def rub(value: float | None) -> str:
    if value is None:
        return "нет в наличии"
    return f"{value:,.0f} ₽".replace(",", " ")


def local(ts_iso: str) -> datetime:
    """UTC ISO из БД → локальное время бизнеса."""
    dt = datetime.fromisoformat(ts_iso)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(TZ)


def short(name: str, n: int = 40) -> str:
    return name if len(name) <= n else name[:n - 1] + "…"
