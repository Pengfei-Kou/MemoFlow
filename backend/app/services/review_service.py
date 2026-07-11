"""
复习业务逻辑服务层

将 review router 中的复杂业务逻辑抽到此处：
- 配额计算
- card vs passage 分流
- Source/Deck 信息查询
- 评分提交

Router 层只做：参数校验 → 调用 Service → 返回响应
"""

from datetime import datetime, timezone

from sqlmodel import Session

from app.config import settings
from app.crud import (
    get_due_blocks, get_new_blocks, submit_review as crud_submit_review,
    get_due_source_batch, get_new_source_batch, submit_batch_review as crud_submit_batch_review,
    count_due_blocks, count_new_blocks, count_today_reviewed, count_today_new,
    get_deck_by_id, get_deck_source_ids, undo_last_review as crud_undo_last_review,
)
from app.models import Source
from app.schemas import (
    ReviewNextResponse, ReviewSubmitResponse, BlockResponse,
    BatchReviewSubmitResponse,
)

# 统一评分标签（前端只提供 1/3/4/5 四档，SM-2 算法将 <3 视为忘记）
QUALITY_LABELS: dict[int, str] = {
    1: "忘记",
    3: "困难",
    4: "良好",
    5: "简单",
}


def _get_source_and_deck_info(session: Session, source_id: int) -> tuple[str | None, str | None]:
    """获取 Source 标题和所属 Deck 名称"""
    source = session.get(Source, source_id)
    if not source:
        return None, None
    deck_name = None
    if source.deck_id:
        deck = get_deck_by_id(session, source.deck_id)
        if deck:
            deck_name = deck.name
    return source.title, deck_name


def get_next_review(
    session: Session,
    deck_id: int | None = None,
    include_children: bool = True,
) -> ReviewNextResponse:
    """
    获取下一张待复习的卡片。

    优先级：到期复习 > 新卡片。
    支持 deck_id 过滤和 card_order 排序。
    """
    # 确定 card_order 和 source_ids
    card_order = "sequential_then_random"
    source_ids = None

    if deck_id is not None:
        deck = get_deck_by_id(session, deck_id)
        if not deck:
            return None  # 由 Router 层转为 404
        card_order = deck.card_order
        source_ids = get_deck_source_ids(session, deck_id, include_children)
        if not source_ids:
            return ReviewNextResponse(block=None, remaining=0, is_new=False)

    count_by_source = (card_order == "always_sequential")

    reviewed_today = count_today_reviewed(session, source_ids=source_ids, count_by_source=count_by_source)
    review_quota_left = max(0, settings.review_cards_per_session - reviewed_today)

    new_today = count_today_new(session, source_ids=source_ids, count_by_source=count_by_source)
    new_quota_left = max(0, settings.new_cards_per_session - new_today)

    # 1. 先查到期的
    due = []
    due_batch = []
    if review_quota_left > 0:
        if card_order == "always_sequential":
            due_batch = get_due_source_batch(session, source_ids=source_ids)
            if due_batch:
                due = [due_batch[0]]
        else:
            due = get_due_blocks(session, limit=1, source_ids=source_ids, card_order=card_order)

    if due:
        total_due = count_due_blocks(session, source_ids=source_ids, count_by_source=count_by_source)
        total_new = count_new_blocks(session, source_ids=source_ids, count_by_source=count_by_source)

        remaining_due = min(max(0, total_due - 1), review_quota_left - 1)
        remaining_new = min(total_new, new_quota_left)
        remaining = remaining_due + remaining_new

        block = due[0]
        source_title, deck_name = _get_source_and_deck_info(session, block.source_id)

        return ReviewNextResponse(
            block=BlockResponse.model_validate(block) if not due_batch else None,
            batch=[BlockResponse.model_validate(b) for b in due_batch] if due_batch else None,
            remaining=max(0, remaining),
            is_new=False,
            source_title=source_title,
            deck_name=deck_name,
            review_mode="passage" if due_batch else "card",
        )

    # 2. 没有到期的，拿新卡片
    new = []
    new_batch = []
    if new_quota_left > 0:
        if card_order == "always_sequential":
            new_batch = get_new_source_batch(session, source_ids=source_ids)
            if new_batch:
                new = [new_batch[0]]
        else:
            new = get_new_blocks(session, limit=1, source_ids=source_ids, card_order=card_order)

    if new:
        total_new = count_new_blocks(session, source_ids=source_ids, count_by_source=count_by_source)
        remaining = min(max(0, total_new - 1), new_quota_left - 1)

        block = new[0]
        source_title, deck_name = _get_source_and_deck_info(session, block.source_id)

        return ReviewNextResponse(
            block=BlockResponse.model_validate(block) if not new_batch else None,
            batch=[BlockResponse.model_validate(b) for b in new_batch] if new_batch else None,
            remaining=max(0, remaining),
            is_new=True,
            source_title=source_title,
            deck_name=deck_name,
            review_mode="passage" if new_batch else "card",
        )

    # 3. 全部完成
    return ReviewNextResponse(block=None, remaining=0, is_new=False)


def _humanize_next_review(next_review) -> str:
    """下次复习时间 → 人话（FSRS 学习步可能是分钟级，不再一律是"N 天"）"""
    now = datetime.now(timezone.utc)
    due = next_review.replace(tzinfo=timezone.utc) if next_review.tzinfo is None else next_review
    delta = due - now
    minutes = delta.total_seconds() / 60
    if minutes < 90:
        return f"{max(1, round(minutes))} 分钟后"
    if minutes < 60 * 36:
        return f"{round(minutes / 60)} 小时后"
    return f"{delta.days} 天后"


def submit_single_review(session: Session, block_id: int, quality: int) -> ReviewSubmitResponse | None:
    """提交单卡复习打分，返回响应对象；不存在返回 None。"""
    block = crud_submit_review(session, block_id, quality)
    if not block:
        return None

    session.commit()
    session.refresh(block)
    label = QUALITY_LABELS.get(quality, str(quality))

    return ReviewSubmitResponse(
        block_id=block.id,
        new_interval=block.interval,
        new_ease_factor=block.ease_factor,
        next_review=block.next_review,
        message=f"评分「{label}」→ 下次复习 {_humanize_next_review(block.next_review)}",
    )


def undo_review(session: Session, block_id: int) -> ReviewSubmitResponse | None:
    """撤销该卡片最近一次评分（按日志快照恢复）；不可撤销时返回 None。"""
    block = crud_undo_last_review(session, block_id)
    if not block:
        return None

    session.commit()
    session.refresh(block)

    return ReviewSubmitResponse(
        block_id=block.id,
        new_interval=block.interval,
        new_ease_factor=block.ease_factor,
        next_review=block.next_review or datetime.now(timezone.utc),
        message="已撤销上次评分",
    )


def submit_passage_review(
    session: Session,
    block_ids: list[int],
    overall_quality: int,
) -> BatchReviewSubmitResponse | None:
    """提交批量（Passage）复习打分，返回响应对象；不存在返回 None。"""
    result = crud_submit_batch_review(session, block_ids, overall_quality)
    if not result:
        return None

    session.commit()
    label = QUALITY_LABELS.get(overall_quality, str(overall_quality))

    return BatchReviewSubmitResponse(
        updated_count=result["updated_count"],
        new_interval=result["new_interval"],
        new_ease_factor=result["new_ease_factor"],
        next_review=result["next_review"],
        message=f"综合判定「{label}」→ 下次复习 {_humanize_next_review(result['next_review'])}",
    )
