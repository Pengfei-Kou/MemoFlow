"""
FSRS 调度测试：评分映射、新卡学习步、SM-2 老卡接种、状态回写
"""

from datetime import datetime, timedelta, timezone

from app.models import Block
from app.services.fsrs_scheduler import (
    QUALITY_TO_RATING,
    apply_review,
    block_to_card,
    ef_to_difficulty,
)
from fsrs import Rating, State


def _new_block(**kwargs) -> Block:
    defaults = dict(source_id=1, sequence_number=1, content="Hello.", quiz="你好")
    defaults.update(kwargs)
    return Block(**defaults)


NOW = datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc)


class TestRatingMap:
    def test_quality_maps_to_fsrs_ratings(self):
        assert QUALITY_TO_RATING == {
            1: Rating.Again, 3: Rating.Hard, 4: Rating.Good, 5: Rating.Easy,
        }


class TestEfToDifficulty:
    def test_bounds(self):
        assert ef_to_difficulty(1.3) == 10.0  # 最难的 EF → 最高难度
        assert ef_to_difficulty(3.0) == 1.0   # 最简单的 EF → 最低难度

    def test_out_of_range_clamped(self):
        assert ef_to_difficulty(0.5) == 10.0
        assert ef_to_difficulty(5.0) == 1.0


class TestNewCard:
    def test_good_enters_learning_step(self):
        block = _new_block()
        apply_review(block, 4, now=NOW)
        assert block.fsrs_state == int(State.Learning)
        assert block.stability is not None and block.difficulty is not None
        # 默认学习步 (1min, 10min)：新卡 Good → 约 10 分钟后再出
        assert block.next_review - NOW < timedelta(hours=1)
        assert block.interval == 0
        assert block.reps == 1

    def test_again_resets_reps(self):
        block = _new_block(reps=3)
        apply_review(block, 1, now=NOW)
        assert block.reps == 0


class TestSm2Seeding:
    def test_old_card_seeds_from_interval_and_ef(self):
        block = _new_block(
            interval=6, ease_factor=2.5, reps=2,
            last_review=NOW - timedelta(days=6),
            next_review=NOW,
        )
        card = block_to_card(block)
        assert card.state == State.Review
        assert card.stability == 6.0
        assert card.difficulty == ef_to_difficulty(2.5)

    def test_review_after_seeding_grows_interval(self):
        block = _new_block(
            interval=6, ease_factor=2.5, reps=2,
            last_review=NOW - timedelta(days=6),
            next_review=NOW,
        )
        apply_review(block, 4, now=NOW)
        assert block.fsrs_state == int(State.Review)
        assert block.interval > 6  # 按时复习评"良"，间隔应增长
        assert block.next_review > NOW + timedelta(days=6)

    def test_fsrs_state_roundtrip(self):
        block = _new_block()
        apply_review(block, 4, now=NOW)
        card = block_to_card(block)  # 有 FSRS 状态后应原样重建，而非再接种
        assert card.state == State(block.fsrs_state)
        assert card.stability == block.stability
