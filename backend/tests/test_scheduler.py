"""
Tests for SM-2 scheduling algorithm and date calculations.
"""

from datetime import datetime, timezone

from app.services.scheduler import calculate_sm2, get_next_review_date


class TestCalculateSM2:
    """Tests for the core SM-2 algorithm."""

    def test_first_review_perfect(self):
        """First review with quality=5 → interval=1, reps=1."""
        result = calculate_sm2(quality=5, previous_interval=0, previous_ease_factor=2.5, previous_reps=0)
        assert result["interval"] == 1
        assert result["reps"] == 1
        assert result["ease_factor"] >= 2.5  # quality=5 increases EF

    def test_second_review_perfect(self):
        """Second review with quality=5 → interval=6, reps=2."""
        result = calculate_sm2(quality=5, previous_interval=1, previous_ease_factor=2.5, previous_reps=1)
        assert result["interval"] == 6
        assert result["reps"] == 2

    def test_third_review_interval_grows(self):
        """Third+ review: interval = previous_interval * ease_factor."""
        result = calculate_sm2(quality=5, previous_interval=6, previous_ease_factor=2.5, previous_reps=2)
        assert result["interval"] == round(6 * 2.5)  # 15
        assert result["reps"] == 3

    def test_quality_below_3_resets(self):
        """quality < 3 resets interval to 1 and reps to 0 (forgot)."""
        result = calculate_sm2(quality=1, previous_interval=15, previous_ease_factor=2.5, previous_reps=5)
        assert result["interval"] == 1
        assert result["reps"] == 0

    def test_quality_3_hard_but_passes(self):
        """quality=3 (hard) should still advance reps but interval doesn't go up much."""
        result = calculate_sm2(quality=3, previous_interval=6, previous_ease_factor=2.5, previous_reps=2)
        assert result["reps"] == 3
        assert result["interval"] >= 1

    def test_ease_factor_floor(self):
        """ease_factor should never go below 1.3."""
        # Repeated quality=1 should keep EF at floor
        result = calculate_sm2(quality=1, previous_interval=1, previous_ease_factor=1.3, previous_reps=0)
        assert result["ease_factor"] >= 1.3

    def test_ease_factor_decreases_on_low_quality(self):
        """quality=3 should decrease ease_factor from default 2.5."""
        result = calculate_sm2(quality=3, previous_interval=6, previous_ease_factor=2.5, previous_reps=2)
        assert result["ease_factor"] < 2.5

    def test_ease_factor_increases_on_high_quality(self):
        """quality=5 should increase ease_factor."""
        result = calculate_sm2(quality=5, previous_interval=6, previous_ease_factor=2.5, previous_reps=2)
        assert result["ease_factor"] > 2.5

    def test_interval_always_positive(self):
        """Interval should always be at least 1."""
        result = calculate_sm2(quality=1, previous_interval=0, previous_ease_factor=1.3, previous_reps=0)
        assert result["interval"] >= 1

    def test_progression_5_5_5(self):
        """Simulate 3 consecutive perfect reviews: interval should grow monotonically."""
        r1 = calculate_sm2(quality=5, previous_interval=0, previous_ease_factor=2.5, previous_reps=0)
        r2 = calculate_sm2(quality=5, previous_interval=r1["interval"], previous_ease_factor=r1["ease_factor"], previous_reps=r1["reps"])
        r3 = calculate_sm2(quality=5, previous_interval=r2["interval"], previous_ease_factor=r2["ease_factor"], previous_reps=r2["reps"])
        assert r1["interval"] < r2["interval"] < r3["interval"]


class TestGetNextReviewDate:
    """Tests for UTC date calculation."""

    def test_returns_future_date(self):
        """Next review date should be in the future."""
        today = datetime.now(timezone.utc).date()
        result = get_next_review_date(1)
        assert result > today

    def test_interval_0_is_today(self):
        """Interval 0 should return today."""
        today = datetime.now(timezone.utc).date()
        result = get_next_review_date(0)
        assert result == today

    def test_interval_7(self):
        """Interval 7 should be exactly 7 days from today."""
        today = datetime.now(timezone.utc).date()
        result = get_next_review_date(7)
        assert (result - today).days == 7
