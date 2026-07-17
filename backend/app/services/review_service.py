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
    count_lapses, get_setting, get_sources_started_today,
    get_new_blocks_article_quota, count_new_within_article_quota,
    count_source_blocks,
)
from app.models import Block, Source
from app.schemas import (
    ReviewNextResponse, ReviewSubmitResponse, BlockResponse,
    BatchReviewSubmitResponse,
)
from app.services import fsrs_scheduler

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


def _humanize_interval_short(due: datetime, now: datetime) -> str:
    """预测间隔 → 评分按钮上的短标签（如 10分钟 / 3天 / 2个月）"""
    minutes = (due - now).total_seconds() / 60
    if minutes < 90:
        return f"{max(1, round(minutes))}分钟"
    if minutes < 60 * 36:
        return f"{round(minutes / 60)}小时"
    days = minutes / 1440
    if days < 60:
        return f"{round(days)}天"
    return f"{round(days / 30.4)}个月"


def get_new_quota_config(session: Session) -> tuple[str, int]:
    """新学配额配置：(单位 cards|articles, 每日数量)。用户设置优先，环境变量兜底"""
    unit = get_setting(session, "new_quota_unit", "cards") or "cards"
    raw = get_setting(session, "new_per_day", "")
    try:
        per_day = int(raw) if raw else settings.new_cards_per_session
    except ValueError:
        per_day = settings.new_cards_per_session
    return unit, max(0, per_day)


def _count_new_allowed(session: Session, unit: str, per_day: int,
                       source_ids: list[int] | None, count_by_source: bool) -> int:
    """今天还允许学的新卡数（供 remaining 展示；按篇时含进行中文章的余卡）"""
    if unit == "articles":
        return count_new_within_article_quota(session, per_day, source_ids)
    new_today = count_today_new(session, source_ids=source_ids, count_by_source=count_by_source)
    quota_left = max(0, per_day - new_today)
    total_new = count_new_blocks(session, source_ids=source_ids, count_by_source=count_by_source)
    return min(quota_left, total_new)


def count_today_remaining(session: Session, source_ids: list[int] | None = None) -> int:
    """今日剩余任务量（今天到期的 + 配额内新卡），供底部导航角标等展示"""
    reviewed_today = count_today_reviewed(session, source_ids=source_ids)
    review_left = max(0, settings.review_cards_per_session - reviewed_today)
    due = min(count_due_blocks(session, source_ids=source_ids), review_left)
    unit, per_day = get_new_quota_config(session)
    return due + _count_new_allowed(session, unit, per_day, source_ids, False)


def _predict_interval_labels(block: Block) -> dict[int, str] | None:
    """四档评分各自的预测间隔标签；仅 FSRS 算法下提供"""
    if settings.scheduler_algorithm != "fsrs":
        return None
    now = datetime.now(timezone.utc)
    return {
        q: _humanize_interval_short(due, now)
        for q, due in fsrs_scheduler.predict_intervals(block, now).items()
    }


def get_next_review(
    session: Session,
    deck_id: int | None = None,
    include_children: bool = True,
    exclude_block_id: int | None = None,
) -> ReviewNextResponse:
    """
    获取下一张待复习的卡片。

    优先级：到期复习 > 新卡片。
    支持 deck_id 过滤和 card_order 排序；
    exclude_block_id 用于前端预取下一张时跳过正在展示的卡。
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

    unit, per_day = get_new_quota_config(session)
    if unit == "articles":
        # 按篇：配额管"今天开几篇"，开了头的文章保证能学完
        started = get_sources_started_today(session, source_ids=source_ids)
        new_quota_left = max(0, per_day - len(started))
    else:
        new_today = count_today_new(session, source_ids=source_ids, count_by_source=count_by_source)
        new_quota_left = max(0, per_day - new_today)

    def _due_response(due: list[Block], due_batch: list[Block]) -> ReviewNextResponse:
        total_due = count_due_blocks(session, source_ids=source_ids, count_by_source=count_by_source)

        remaining_due = min(max(0, total_due - 1), review_quota_left - 1)
        remaining_new = _count_new_allowed(session, unit, per_day, source_ids, count_by_source)
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
            predicted_intervals=_predict_interval_labels(block) if not due_batch else None,
        )

    # 1. 先查真正到期的（next_review <= 当前时刻）。学习步稍后才到点的卡
    #    不在此列——Anki 式：让位给新卡，别刚评完就再次怼脸上
    due = []
    due_batch = []
    if review_quota_left > 0:
        if card_order == "always_sequential":
            due_batch = get_due_source_batch(session, source_ids=source_ids)
            if due_batch:
                due = [due_batch[0]]
        else:
            due = get_due_blocks(
                session, limit=1, source_ids=source_ids,
                card_order=card_order, exclude_block_id=exclude_block_id,
                due_before=datetime.now(timezone.utc).replace(tzinfo=None),
            )

    if due:
        return _due_response(due, due_batch)

    # 2. 没有到期的，拿新卡片
    new = []
    new_batch = []
    if card_order == "always_sequential":
        if new_quota_left > 0:
            new_batch = get_new_source_batch(session, source_ids=source_ids)
            if new_batch:
                new = [new_batch[0]]
    elif unit == "articles":
        # 开新篇由 helper 按配额把关；今天开了头的文章即使配额用尽也接着出
        new = get_new_blocks_article_quota(
            session, per_day, source_ids=source_ids, exclude_block_id=exclude_block_id,
        )
    elif new_quota_left > 0:
        new = get_new_blocks(
            session, limit=1, source_ids=source_ids,
            card_order=card_order, exclude_block_id=exclude_block_id,
        )

    if new:
        allowed = _count_new_allowed(session, unit, per_day, source_ids, count_by_source)
        remaining = max(0, allowed - 1)

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
            predicted_intervals=_predict_interval_labels(block) if not new_batch else None,
            source_position=(
                f"{block.sequence_number}/{count_source_blocks(session, block.source_id)}"
                if not new_batch else None
            ),
        )

    # 3. 新卡也没了：提前拉今天稍后到期的学习步卡（Anki 的 learn-ahead），
    #    避免用户对着"全部完成"空等十分钟
    if review_quota_left > 0 and card_order != "always_sequential":
        due = get_due_blocks(
            session, limit=1, source_ids=source_ids,
            card_order=card_order, exclude_block_id=exclude_block_id,
        )
        if due:
            return _due_response(due, [])

    # 4. 全部完成
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

    # Leech 检测：评"忘了"时看累计忘记次数是否达阈值
    leech = False
    if quality == 1:
        leech = count_lapses(session, block_id) >= settings.leech_threshold

    session.commit()
    session.refresh(block)
    label = QUALITY_LABELS.get(quality, str(quality))

    message = f"评分「{label}」→ 下次复习 {_humanize_next_review(block.next_review)}"
    if leech:
        message += "｜🧟 这张卡反复忘记，建议编辑改写或暂停"

    return ReviewSubmitResponse(
        block_id=block.id,
        new_interval=block.interval,
        new_ease_factor=block.ease_factor,
        next_review=block.next_review,
        message=message,
        leech=leech,
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
