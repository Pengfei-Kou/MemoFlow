"""
FSRS 调度（py-fsrs / FSRS-6），scheduler_algorithm="fsrs" 时替代 SM-2

设计要点：
- 评分维度保持 1/3/4/5（忘/难/中/易），映射到 FSRS 的 Again/Hard/Good/Easy，
  前端与 API 不感知算法切换
- 旧 SM-2 卡片（有复习进度但无 FSRS 状态）在首次经过 FSRS 复习时"接种"：
  stability ≈ 当前 interval，difficulty 由 ease_factor 线性映射
- enable_fuzzing=False：passage 模式（always_sequential deck）依赖同一 Source
  的卡片到期日聚在一起，间隔模糊化会把它们打散导致整篇天天出现
- Block.interval 继续维护（=本次调度的间隔天数），供"已掌握"统计与展示用
"""

from datetime import datetime, timezone

from fsrs import Scheduler, Card, Rating, State

from app.config import settings
from app.models import Block

QUALITY_TO_RATING = {
    1: Rating.Again,
    3: Rating.Hard,
    4: Rating.Good,
    5: Rating.Easy,
}

_scheduler: Scheduler | None = None


def _get_scheduler() -> Scheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = Scheduler(
            desired_retention=settings.desired_retention,
            enable_fuzzing=False,
        )
    return _scheduler


def ef_to_difficulty(ease_factor: float) -> float:
    """SM-2 ease_factor（1.3~3.0，越大越简单）→ FSRS difficulty（1~10，越大越难）"""
    ef = min(max(ease_factor, 1.3), 3.0)
    return round(10.0 - (ef - 1.3) / (3.0 - 1.3) * 9.0, 2)


def _as_utc(dt: datetime | None) -> datetime | None:
    """DB 里存的是 naive UTC，py-fsrs 要求 aware"""
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def block_to_card(block: Block) -> Card:
    """Block → FSRS Card；旧 SM-2 卡片做一次性接种"""
    if block.stability is not None:
        return Card(
            state=State(block.fsrs_state),
            step=block.fsrs_step,
            stability=block.stability,
            difficulty=block.difficulty,
            due=_as_utc(block.next_review),
            last_review=_as_utc(block.last_review),
        )

    if block.last_review is not None:
        # SM-2 老卡接种：进度不清零，近似换算
        return Card(
            state=State.Review,
            step=None,
            stability=float(max(block.interval, 1)),
            difficulty=ef_to_difficulty(block.ease_factor),
            due=_as_utc(block.next_review),
            last_review=_as_utc(block.last_review),
        )

    return Card()  # 全新卡


def apply_review(block: Block, quality: int, now: datetime | None = None) -> None:
    """对 block 执行一次 FSRS 评分，就地更新调度字段（不落库、不改 last_review）"""
    now = now or datetime.now(timezone.utc)
    card = block_to_card(block)
    card, _ = _get_scheduler().review_card(
        card, QUALITY_TO_RATING[quality], review_datetime=now
    )

    block.stability = card.stability
    block.difficulty = card.difficulty
    block.fsrs_state = int(card.state)
    block.fsrs_step = card.step
    block.next_review = card.due
    block.interval = max(0, (card.due - now).days)
    # reps 语义保留：连续成功次数（供统计参考，FSRS 本身不用）
    block.reps = 0 if quality < 3 else block.reps + 1
