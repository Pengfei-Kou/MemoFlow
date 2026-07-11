"""
本地逻辑日（时区 + 凌晨滚动）边界测试

默认配置：America/Toronto + 凌晨 4 点滚动。
关键场景：多伦多晚上（UTC 已过午夜）仍算"今天"；凌晨 4 点前仍算"昨天"。
"""

from datetime import date, datetime, timedelta, timezone

from app.services.timeutils import local_day_bounds, logical_date


def _utc(y, m, d, hh=0, mm=0):
    return datetime(y, m, d, hh, mm, tzinfo=timezone.utc)


class TestLogicalDate:
    def test_toronto_evening_still_today(self):
        # UTC 1/15 02:00 = 多伦多 1/14 21:00 (EST, UTC-5) → 逻辑日 1/14
        assert logical_date(_utc(2026, 1, 15, 2, 0)) == date(2026, 1, 14)

    def test_before_rollover_counts_as_yesterday(self):
        # 多伦多 1/15 03:59（UTC 08:59）→ 凌晨 4 点前，仍算 1/14
        assert logical_date(_utc(2026, 1, 15, 8, 59)) == date(2026, 1, 14)

    def test_after_rollover_is_new_day(self):
        # 多伦多 1/15 04:01（UTC 09:01）→ 新的一天 1/15
        assert logical_date(_utc(2026, 1, 15, 9, 1)) == date(2026, 1, 15)

    def test_naive_input_treated_as_utc(self):
        assert logical_date(datetime(2026, 1, 15, 2, 0)) == date(2026, 1, 14)


class TestLocalDayBounds:
    def test_bounds_contain_now_and_are_naive(self):
        now = _utc(2026, 1, 15, 2, 0)
        start, end = local_day_bounds(now)
        assert start.tzinfo is None and end.tzinfo is None
        assert start <= now.replace(tzinfo=None) < end

    def test_bounds_are_24h_and_start_at_rollover(self):
        start, end = local_day_bounds(_utc(2026, 1, 15, 2, 0))
        assert end - start == timedelta(hours=24)
        # 逻辑日 1/14 的起点 = 多伦多 1/14 04:00 EST = UTC 09:00
        assert start == datetime(2026, 1, 14, 9, 0)

    def test_utc_midnight_does_not_split_the_day(self):
        # 多伦多同一晚 19:30（UTC 00:30 已翻日）与 23:30 属于同一逻辑日
        d1 = logical_date(_utc(2026, 1, 15, 0, 30))
        d2 = logical_date(_utc(2026, 1, 15, 4, 30))
        assert d1 == d2 == date(2026, 1, 14)
