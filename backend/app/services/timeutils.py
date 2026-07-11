"""
本地时区"逻辑日"计算

存储一律 UTC 不变；但"今天"的判定（配额、到期、热力图）按
settings.timezone 的本地日 + 凌晨 day_rollover_hour 滚动（Anki 同款设计）：
本地凌晨 4 点前的复习仍算前一天，避免 UTC 日界（多伦多晚 8 点）把一天劈成两半。
"""

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.config import settings


def _tz() -> ZoneInfo:
    return ZoneInfo(settings.timezone)


def logical_date(dt_utc: datetime | None = None):
    """UTC 时刻 → 所属的本地"逻辑日"（date）"""
    dt_utc = dt_utc or datetime.now(timezone.utc)
    if dt_utc.tzinfo is None:
        dt_utc = dt_utc.replace(tzinfo=timezone.utc)
    shifted = dt_utc.astimezone(_tz()) - timedelta(hours=settings.day_rollover_hour)
    return shifted.date()


def local_day_bounds(now: datetime | None = None) -> tuple[datetime, datetime]:
    """
    当前逻辑日的 [start, end) 边界，返回 naive UTC datetime
    （与 SQLite 中的存储格式一致，可直接用于列比较）
    """
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    day = logical_date(now)
    start_local = datetime(
        day.year, day.month, day.day, settings.day_rollover_hour, tzinfo=_tz()
    )
    end_local = start_local + timedelta(days=1)
    return (
        start_local.astimezone(timezone.utc).replace(tzinfo=None),
        end_local.astimezone(timezone.utc).replace(tzinfo=None),
    )
