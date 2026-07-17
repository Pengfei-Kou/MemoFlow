"""
数据库 CRUD 操作
V2 改进：
  - 修复重复 import
  - 新增编辑/删除/暂停功能
  - mastered 阈值改为 config 可配
  - 支持搜索和分页
V3 新增：
  - Deck CRUD（含树形查询、子集递归查询）
  - Source/Review/Stats 新增 deck_id 过滤
"""

from datetime import datetime, timedelta, timezone

from sqlmodel import Session, select, func, col

from app.models import Source, Block, Deck, ReviewLog, AppSetting
from app.config import settings
from app.services import fsrs_scheduler
from app.services.scheduler import calculate_sm2, get_next_review_date
from app.services.timeutils import local_day_bounds, logical_date


# ============================================================
# Deck 操作
# ============================================================

def get_default_deck(session: Session) -> Deck:
    """获取或创建默认 Deck（"Default"）"""
    stmt = select(Deck).where(Deck.path == "Default")
    deck = session.exec(stmt).first()
    if not deck:
        deck = Deck(name="Default", path="Default")
        session.add(deck)
        session.flush()
    return deck


def create_deck(
    session: Session,
    name: str,
    parent_path: str | None = None,
    parser_config: dict | None = None,
    card_order: str = "sequential_then_random",
) -> Deck:
    """创建 Deck，自动计算 path"""
    path = f"{parent_path}/{name}" if parent_path else name

    # 查找父节点
    parent_id = None
    if parent_path:
        parent = session.exec(select(Deck).where(Deck.path == parent_path)).first()
        if not parent:
            raise ValueError(f"父节点 '{parent_path}' 不存在，请先创建父 Deck")
        parent_id = parent.id

    deck = Deck(
        name=name,
        path=path,
        parent_id=parent_id,
        parser_config=parser_config or {
            "strategy": "sentence_en_zh",
            "source_lang": "English",
            "target_lang": "Chinese",
            "custom_prompt": None,
        },
        card_order=card_order,
    )
    session.add(deck)
    session.flush()
    return deck


def get_all_decks(session: Session) -> list[Deck]:
    """获取所有 Deck（按 path 排序）"""
    return session.exec(select(Deck).order_by(Deck.path)).all()


def get_deck_by_id(session: Session, deck_id: int) -> Deck | None:
    """获取单个 Deck"""
    return session.get(Deck, deck_id)


def update_deck(
    session: Session,
    deck_id: int,
    name: str | None = None,
    parser_config: dict | None = None,
    card_order: str | None = None,
) -> Deck | None:
    """修改 Deck（只更新传入字段）"""
    deck = session.get(Deck, deck_id)
    if not deck:
        return None

    if name is not None and name != deck.name:
        old_path = deck.path
        # 计算新 path
        parent_prefix = old_path[: old_path.rfind("/") + 1] if "/" in old_path else ""
        new_path = parent_prefix + name
        # 更新本身及所有子孙的 path
        children = session.exec(
            select(Deck).where(col(Deck.path).startswith(old_path + "/"))
        ).all()
        for child in children:
            child.path = new_path + child.path[len(old_path):]
            session.add(child)
        deck.name = name
        deck.path = new_path

    if parser_config is not None:
        deck.parser_config = parser_config
    if card_order is not None:
        deck.card_order = card_order

    session.add(deck)
    session.flush()
    return deck


def delete_deck(session: Session, deck_id: int) -> bool:
    """删除 Deck（级联删除子孙 Deck 及其 Sources 和 Blocks）"""
    deck = session.get(Deck, deck_id)
    if not deck:
        return False

    # 找出所有子孙 Deck（含自身）
    all_decks = session.exec(
        select(Deck).where(
            (Deck.id == deck_id) | col(Deck.path).startswith(deck.path + "/")
        )
    ).all()
    descendant_ids = [d.id for d in all_decks]

    # 删除这些 Deck 下的所有 Sources（cascade 会删 Blocks）
    sources = session.exec(
        select(Source).where(col(Source.deck_id).in_(descendant_ids))
    ).all()
    for source in sources:
        session.delete(source)
    session.flush()

    # 删除所有子孙 Deck（深度优先：先删子再删父）
    for d in sorted(all_decks, key=lambda x: x.path, reverse=True):
        session.delete(d)

    session.flush()
    return True


def get_deck_source_ids(session: Session, deck_id: int, include_children: bool = True) -> list[int]:
    """获取 Deck 范围内所有 Source 的 id 列表"""
    deck = session.get(Deck, deck_id)
    if not deck:
        return []

    if include_children:
        # 用 path LIKE 'parent/%' 匹配所有子孙
        child_decks = session.exec(
            select(Deck).where(
                (Deck.id == deck_id) | col(Deck.path).startswith(deck.path + "/")
            )
        ).all()
        deck_ids = [d.id for d in child_decks]
    else:
        deck_ids = [deck_id]

    sources = session.exec(
        select(Source.id).where(col(Source.deck_id).in_(deck_ids))
    ).all()
    return list(sources)


# ============================================================
# Source 操作
# ============================================================

def create_source(
    session: Session,
    title: str,
    content_hash: str,
    original_text: str,
    source_type: str = "text",
    url: str | None = None,
    deck_id: int | None = None,
) -> Source:
    """创建来源（幂等：相同 hash 不重复创建）"""
    statement = select(Source).where(Source.content_hash == content_hash)
    existing = session.exec(statement).first()
    if existing:
        return existing

    source = Source(
        title=title,
        content_hash=content_hash,
        original_text=original_text,
        source_type=source_type,
        url=url,
        deck_id=deck_id,
    )
    session.add(source)
    session.flush()
    return source


def get_all_sources(session: Session) -> list[dict]:
    """获取所有来源（含卡片计数）"""
    statement = (
        select(
            Source.id,
            Source.title,
            Source.source_type,
            Source.created_at,
            Source.deck_id,
            func.count(Block.id).label("block_count"),
        )
        .outerjoin(Block, Source.id == Block.source_id)
        .group_by(Source.id)
        .order_by(Source.created_at.desc())
    )
    results = session.exec(statement).all()
    return [
        {
            "id": r[0],
            "title": r[1],
            "source_type": r[2],
            "created_at": r[3],
            "deck_id": r[4],
            "block_count": r[5],
        }
        for r in results
    ]


def get_source_by_id(session: Session, source_id: int) -> Source | None:
    """获取单个来源（含关联卡片）"""
    return session.get(Source, source_id)


def delete_source(session: Session, source_id: int) -> bool:
    """删除来源及其所有卡片（级联删除）"""
    source = session.get(Source, source_id)
    if not source:
        return False
    session.delete(source)
    session.flush()
    return True


# ============================================================
# Block 操作
# ============================================================

def create_block(
    session: Session,
    source_id: int,
    sequence: int,
    content: str,
    quiz: str,
) -> Block:
    """创建一张复习卡片"""
    block = Block(
        source_id=source_id,
        sequence_number=sequence,
        content=content,
        quiz=quiz,
    )
    session.add(block)
    session.flush()
    return block


def get_blocks(
    session: Session,
    deck_id: int | None = None,
    source_id: int | None = None,
    search: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> list[Block]:
    """获取卡片列表（支持按来源筛选、关键词搜索、分页）"""
    statement = select(Block)

    if deck_id is not None:
        source_ids = get_deck_source_ids(session, deck_id, include_children=True)
        if not source_ids:
            return []
        statement = statement.where(col(Block.source_id).in_(source_ids))

    if source_id is not None:
        statement = statement.where(Block.source_id == source_id)

    if search:
        keyword = f"%{search}%"
        statement = statement.where(
            col(Block.content).ilike(keyword) | col(Block.quiz).ilike(keyword)
        )

    statement = statement.order_by(Block.id).offset(offset).limit(limit)
    return session.exec(statement).all()


def get_block_by_id(session: Session, block_id: int) -> Block | None:
    """获取单张卡片"""
    return session.get(Block, block_id)


def update_block(
    session: Session,
    block_id: int,
    content: str | None = None,
    quiz: str | None = None,
    is_suspended: bool | None = None,
    notes: list[dict] | None = None,
) -> Block | None:
    """编辑卡片（只更新传入的字段；notes 传空列表 = 清空）"""
    block = session.get(Block, block_id)
    if not block:
        return None

    if content is not None:
        block.content = content
    if quiz is not None:
        block.quiz = quiz
    if is_suspended is not None:
        block.is_suspended = is_suspended
    if notes is not None:
        block.notes = notes

    session.add(block)
    session.flush()
    return block


def get_block_context(session: Session, block_id: int, radius: int = 2) -> list[Block] | None:
    """获取卡片在原文中的上下文（同 Source、sequence_number ±radius，含自身）"""
    block = session.get(Block, block_id)
    if not block:
        return None
    return session.exec(
        select(Block)
        .where(Block.source_id == block.source_id)
        .where(Block.sequence_number >= block.sequence_number - radius)
        .where(Block.sequence_number <= block.sequence_number + radius)
        .order_by(Block.sequence_number)
    ).all()


def count_lapses(session: Session, block_id: int) -> int:
    """该卡片累计"忘了"次数（leech 检测用）"""
    return session.exec(
        select(func.count())
        .select_from(ReviewLog)
        .where(ReviewLog.block_id == block_id)
        .where(ReviewLog.quality == 1)
    ).one()


def get_leech_blocks(session: Session, threshold: int) -> dict[int, int]:
    """所有达到 leech 阈值的卡片 → {block_id: 忘记次数}"""
    rows = session.exec(
        select(ReviewLog.block_id, func.count().label("lapses"))
        .where(ReviewLog.quality == 1)
        .group_by(ReviewLog.block_id)
        .having(func.count() >= threshold)
    ).all()
    return {row[0]: row[1] for row in rows}


def delete_block(session: Session, block_id: int) -> bool:
    """删除单张卡片"""
    block = session.get(Block, block_id)
    if not block:
        return False
    session.delete(block)
    session.flush()
    return True


# ============================================================
# 复习相关
# ============================================================

def get_due_blocks(
    session: Session,
    limit: int | None = None,
    source_ids: list[int] | None = None,
    card_order: str = "sequential_then_random",
    exclude_block_id: int | None = None,
    due_before: datetime | None = None,
) -> list[Block]:
    """获取到期待复习的卡片（排除已暂停的）

    exclude_block_id：预取下一张时排除正在展示的卡。
    due_before：到期判定边界（naive UTC）。默认为逻辑日终点=「今天到期」；
    传当前时刻则只取真正到期的卡（学习步稍后才到点的卡不算）。
    """
    if limit is None:
        limit = settings.review_cards_per_session

    if due_before is None:
        _, due_before = local_day_bounds()
    statement = (
        select(Block)
        .where(Block.next_review < due_before)
        .where(Block.is_suspended == False)
    )

    if source_ids is not None:
        statement = statement.where(col(Block.source_id).in_(source_ids))
    if exclude_block_id is not None:
        statement = statement.where(Block.id != exclude_block_id)

    if card_order == "always_sequential":
        statement = statement.order_by(Block.source_id, Block.sequence_number)
        return session.exec(statement.limit(limit)).all()

    if card_order == "always_random":
        statement = statement.order_by(func.random())
        return session.exec(statement.limit(limit)).all()

    # 默认档：最危险优先——按 FSRS 预测记住率升序，最可能已遗忘的先复习。
    # 刚评"忘了"的卡记住率会重置到接近 1，自然排到队尾，不会立刻再出现。
    blocks = list(session.exec(statement).all())
    now = datetime.now(timezone.utc)
    blocks.sort(key=lambda b: fsrs_scheduler.retrievability(b, now))
    return blocks[:limit]


def get_new_blocks(
    session: Session,
    limit: int | None = None,
    source_ids: list[int] | None = None,
    card_order: str = "sequential_then_random",
    exclude_block_id: int | None = None,
) -> list[Block]:
    """获取从未学习过的新卡片（排除已暂停的）"""
    if limit is None:
        limit = settings.new_cards_per_session

    statement = (
        select(Block)
        .where(Block.next_review == None)  # noqa: E711
        .where(Block.is_suspended == False)
    )

    if source_ids is not None:
        statement = statement.where(col(Block.source_id).in_(source_ids))
    if exclude_block_id is not None:
        statement = statement.where(Block.id != exclude_block_id)

    if card_order == "always_random":
        statement = statement.order_by(func.random())
    else:
        # sequential_then_random 和 always_sequential 的新卡都按顺序
        statement = statement.order_by(Block.source_id, Block.sequence_number)

    statement = statement.limit(limit)
    return session.exec(statement).all()


def get_due_source_batch(
    session: Session,
    source_ids: list[int] | None = None,
) -> list[Block]:
    """获取下一个需要复习的整个 Source 的所有卡片 (Passage-level review)"""
    _, day_end = local_day_bounds()

    # 1. 找出一个有卡片到期的 source_id
    subquery = select(Block.source_id).where(Block.next_review < day_end).where(Block.is_suspended == False)
    if source_ids is not None:
        subquery = subquery.where(col(Block.source_id).in_(source_ids))
    subquery = subquery.order_by(Block.source_id).limit(1)
    target_source_id = session.exec(subquery).first()
    
    if not target_source_id:
        return []
        
    # 2. 返回该 source 的所有非暂停卡片
    return session.exec(
        select(Block)
        .where(Block.source_id == target_source_id)
        .where(Block.is_suspended == False)
        .order_by(Block.sequence_number)
    ).all()


def get_new_source_batch(
    session: Session,
    source_ids: list[int] | None = None,
) -> list[Block]:
    """获取下一个需要学习的整个新 Source 的所有卡片 (Passage-level review)"""
    subquery = select(Block.source_id).where(Block.next_review == None).where(Block.is_suspended == False) # noqa: E711
    if source_ids is not None:
        subquery = subquery.where(col(Block.source_id).in_(source_ids))
    subquery = subquery.order_by(Block.source_id).limit(1)
    target_source_id = session.exec(subquery).first()
    
    if not target_source_id:
        return []
        
    return session.exec(
        select(Block)
        .where(Block.source_id == target_source_id)
        .where(Block.is_suspended == False)
        .order_by(Block.sequence_number)
    ).all()


def count_due_blocks(
    session: Session,
    source_ids: list[int] | None = None,
    count_by_source: bool = False,
) -> int:
    """高效统计今日到期卡片数（或到期的 Source 组数）"""
    _, day_end = local_day_bounds()

    count_expr = func.count(func.distinct(Block.source_id)) if count_by_source else func.count()
    stmt = (
        select(count_expr)
        .select_from(Block)
        .where(Block.next_review < day_end)
        .where(Block.is_suspended == False)
    )
    if source_ids is not None:
        stmt = stmt.where(col(Block.source_id).in_(source_ids))
    return session.exec(stmt).one()


def count_new_blocks(
    session: Session,
    source_ids: list[int] | None = None,
    count_by_source: bool = False,
) -> int:
    """高效统计新卡片数（或新 Source 组数）"""
    count_expr = func.count(func.distinct(Block.source_id)) if count_by_source else func.count()
    stmt = (
        select(count_expr)
        .select_from(Block)
        .where(Block.next_review == None)  # noqa: E711
        .where(Block.is_suspended == False)
    )
    if source_ids is not None:
        stmt = stmt.where(col(Block.source_id).in_(source_ids))
    return session.exec(stmt).one()


def count_today_reviewed(session: Session, source_ids: list[int] | None = None, count_by_source: bool = False) -> int:
    """统计今日已复习数量（或 Source 组数）
    
    "已复习" = last_review 在今天 且 first_reviewed_at 在今天之前
    "今天" = 本地逻辑日（时区 + 凌晨滚动，见 timeutils）
    """
    today_start, _ = local_day_bounds()
    count_expr = func.count(func.distinct(Block.source_id)) if count_by_source else func.count()
    stmt = (
        select(count_expr)
        .select_from(Block)
        .where(Block.last_review >= today_start)
        .where(Block.first_reviewed_at < today_start)
    )
    if source_ids is not None:
        stmt = stmt.where(col(Block.source_id).in_(source_ids))
    return session.exec(stmt).one()


def relearn_source(session: Session, source_id: int) -> int | None:
    """整篇重学：清空该来源全部卡片的调度进度（ReviewLog 历史保留）。
    返回重置的卡片数；来源不存在返回 None。"""
    source = session.get(Source, source_id)
    if not source:
        return None
    blocks = session.exec(select(Block).where(Block.source_id == source_id)).all()
    for b in blocks:
        b.next_review = None
        b.last_review = None
        b.first_reviewed_at = None
        b.reps = 0
        b.interval = 0
        b.ease_factor = 2.5
        b.stability = None
        b.difficulty = None
        b.fsrs_state = None
        b.fsrs_step = None
        session.add(b)
    session.flush()
    return len(blocks)


def count_due_tomorrow(session: Session, source_ids: list[int] | None = None) -> int:
    """明天（下一个逻辑日）到期的卡片数"""
    _, day_end = local_day_bounds()
    stmt = (
        select(func.count())
        .select_from(Block)
        .where(Block.next_review >= day_end)
        .where(Block.next_review < day_end + timedelta(days=1))
        .where(Block.is_suspended == False)
    )
    if source_ids is not None:
        stmt = stmt.where(col(Block.source_id).in_(source_ids))
    return session.exec(stmt).one()


def get_setting(session: Session, key: str, default: str | None = None) -> str | None:
    """读应用级 KV 设置；未设置返回 default"""
    row = session.get(AppSetting, key)
    return row.value if row else default


def set_setting(session: Session, key: str, value: str) -> None:
    """写应用级 KV 设置（upsert，不 commit）"""
    row = session.get(AppSetting, key)
    if row:
        row.value = value
    else:
        row = AppSetting(key=key, value=value)
    session.add(row)


def get_sources_started_today(session: Session, source_ids: list[int] | None = None) -> list[int]:
    """今天（本地逻辑日）开始学新卡的 Source ID 列表"""
    today_start, _ = local_day_bounds()
    stmt = (
        select(func.distinct(Block.source_id))
        .where(Block.first_reviewed_at >= today_start)
    )
    if source_ids is not None:
        stmt = stmt.where(col(Block.source_id).in_(source_ids))
    return list(session.exec(stmt).all())


def get_new_blocks_article_quota(
    session: Session,
    per_day: int,
    source_ids: list[int] | None = None,
    exclude_block_id: int | None = None,
) -> list[Block]:
    """按篇配额取下一张新卡：先接着学今天开了头的文章（不受配额限制，
    保证开篇必学完），配额有余才开新的一篇"""
    started = get_sources_started_today(session, source_ids)
    if started:
        blocks = get_new_blocks(
            session, limit=1, source_ids=started,
            card_order="sequential_then_random", exclude_block_id=exclude_block_id,
        )
        if blocks:
            return blocks
    if len(started) >= per_day:
        return []
    return get_new_blocks(
        session, limit=1, source_ids=source_ids,
        card_order="sequential_then_random", exclude_block_id=exclude_block_id,
    )


def count_new_within_article_quota(
    session: Session,
    per_day: int,
    source_ids: list[int] | None = None,
) -> int:
    """按篇配额下，今天还允许学的新卡总数（进行中文章的余卡 + 配额内未开文章的整卡）"""
    started = set(get_sources_started_today(session, source_ids))
    stmt = (
        select(Block.source_id, func.count())
        .where(Block.next_review == None)  # noqa: E711
        .where(Block.is_suspended == False)
    )
    if source_ids is not None:
        stmt = stmt.where(col(Block.source_id).in_(source_ids))
    stmt = stmt.group_by(Block.source_id).order_by(Block.source_id)

    total = 0
    articles_left = max(0, per_day - len(started))
    for sid, n in session.exec(stmt).all():
        if sid in started:
            total += n
        elif articles_left > 0:
            total += n
            articles_left -= 1
    return total


def count_today_new(session: Session, source_ids: list[int] | None = None, count_by_source: bool = False) -> int:
    """统计今日已学的新卡数量（或 Source 组数）
    
    "今日新学" = first_reviewed_at 在今天（本地逻辑日，见 timeutils）
    """
    today_start, _ = local_day_bounds()
    count_expr = func.count(func.distinct(Block.source_id)) if count_by_source else func.count()
    stmt = (
        select(count_expr)
        .select_from(Block)
        .where(Block.first_reviewed_at >= today_start)
    )
    if source_ids is not None:
        stmt = stmt.where(col(Block.source_id).in_(source_ids))
    return session.exec(stmt).one()


def _apply_rating(block: Block, quality: int, now: datetime) -> None:
    """按配置的调度算法更新 block 的调度字段（不改 last_review，不落库）"""
    if settings.scheduler_algorithm == "fsrs":
        fsrs_scheduler.apply_review(block, quality, now)
        return

    # SM-2 回退路径
    result = calculate_sm2(
        quality=quality,
        previous_interval=block.interval,
        previous_ease_factor=block.ease_factor,
        previous_reps=block.reps,
    )
    block.interval = result["interval"]
    block.ease_factor = result["ease_factor"]
    block.reps = result["reps"]
    next_date = get_next_review_date(result["interval"])
    block.next_review = datetime(
        next_date.year, next_date.month, next_date.day, tzinfo=timezone.utc
    )


# 调度状态快照涉及的字段（撤销恢复用）
_SCHED_FIELDS = (
    "reps", "interval", "ease_factor",
    "stability", "difficulty", "fsrs_state", "fsrs_step",
    "last_review", "next_review", "first_reviewed_at",
)
_SCHED_DT_FIELDS = {"last_review", "next_review", "first_reviewed_at"}


def _snapshot_state(block: Block) -> dict:
    """卡片当前调度状态 → JSON 可存的快照（datetime 转 ISO 字符串）"""
    snap = {}
    for f in _SCHED_FIELDS:
        v = getattr(block, f)
        snap[f] = v.isoformat() if (f in _SCHED_DT_FIELDS and v is not None) else v
    return snap


def _restore_state(block: Block, snap: dict) -> None:
    """快照 → 写回卡片调度状态"""
    for f in _SCHED_FIELDS:
        v = snap.get(f)
        if f in _SCHED_DT_FIELDS and v is not None:
            v = datetime.fromisoformat(v)
        setattr(block, f, v)


def _log_review(session: Session, block: Block, quality: int, now: datetime, state_before: dict) -> None:
    """追加一条复习日志（除"撤销"外永不更新/删除）"""
    session.add(ReviewLog(
        block_id=block.id,
        quality=quality,
        reviewed_at=now,
        interval_before=state_before.get("interval", 0),
        interval_after=block.interval,
        stability_after=block.stability,
        difficulty_after=block.difficulty,
        state_before=state_before,
    ))


def undo_last_review(session: Session, block_id: int) -> Block | None:
    """
    撤销该卡片最近一次评分：按日志快照恢复调度状态，并删除那条日志。
    没有可撤销的日志（或卡片不存在）返回 None。
    """
    block = session.get(Block, block_id)
    if not block:
        return None

    log = session.exec(
        select(ReviewLog)
        .where(ReviewLog.block_id == block_id)
        .where(ReviewLog.state_before != None)  # noqa: E711
        .order_by(col(ReviewLog.id).desc())
        .limit(1)
    ).first()
    if not log:
        return None

    _restore_state(block, log.state_before)
    session.delete(log)  # 撤销 = 这次评分"没发生过"，日志一并移除
    session.add(block)
    session.flush()
    return block


def submit_review(session: Session, block_id: int, quality: int) -> Block | None:
    """
    处理复习打分：
    1. 调用调度算法（FSRS / SM-2）更新卡片状态与下次复习时间
    2. 追加复习日志
    """
    block = session.get(Block, block_id)
    if not block:
        return None

    now = datetime.now(timezone.utc)
    state_before = _snapshot_state(block)

    _apply_rating(block, quality, now)

    block.last_review = now
    if block.first_reviewed_at is None:
        block.first_reviewed_at = now

    _log_review(session, block, quality, now, state_before)
    session.add(block)
    session.flush()
    return block

def submit_batch_review(session: Session, block_ids: list[int], quality: int) -> dict:
    """
    处理批量（Passage级别）复习打分：整篇一个评分，逐卡更新调度状态并记日志。

    FSRS 路径下每张卡保留自己真实的 stability/difficulty（fuzzing 已关闭，
    同评分历史的卡片到期日自然聚在一起）；整篇下次出现时机 = 最早到期的卡。
    """
    if not block_ids:
        return {}

    blocks = session.exec(select(Block).where(col(Block.id).in_(block_ids))).all()
    if not blocks:
        return {}

    now = datetime.now(timezone.utc)

    for block in blocks:
        state_before = _snapshot_state(block)
        _apply_rating(block, quality, now)
        block.last_review = now
        if block.first_reviewed_at is None:
            block.first_reviewed_at = now
        _log_review(session, block, quality, now, state_before)
        session.add(block)

    session.flush()

    next_review_dt = min(b.next_review for b in blocks)
    return {
        "updated_count": len(blocks),
        "new_interval": max(b.interval for b in blocks),
        "new_ease_factor": round(sum(b.ease_factor for b in blocks) / len(blocks), 2),
        "next_review": next_review_dt
    }


# ============================================================
# 统计
# ============================================================

def get_stats(session: Session, source_ids: list[int] | None = None) -> dict:
    """获取学习统计（可按 source_ids 过滤）"""

    def filtered(stmt):
        if source_ids is not None:
            stmt = stmt.where(col(Block.source_id).in_(source_ids))
        return stmt

    total = session.exec(
        filtered(select(func.count()).select_from(Block))
    ).one()

    mastered = session.exec(
        filtered(
            select(func.count()).select_from(Block).where(
                Block.interval >= settings.mastered_threshold
            )
        )
    ).one()

    new = session.exec(
        filtered(
            select(func.count()).select_from(Block).where(
                Block.next_review == None  # noqa: E711
            )
        )
    ).one()

    _, day_end = local_day_bounds()
    due_today = session.exec(
        filtered(
            select(func.count()).select_from(Block).where(
                Block.next_review < day_end
            )
        )
    ).one()

    learning = total - mastered - new

    return {
        "total": total,
        "mastered": mastered,
        "learning": max(0, learning),
        "new": new,
        "due_today": due_today,
    }


def get_today_summary(session: Session, source_ids: list[int] | None = None) -> dict:
    """
    今日（本地逻辑日）复习小结：复习次数与记住率。
    基于 ReviewLog 统计，不含迁移回填的 quality=NULL 行。
    """
    day_start, day_end = local_day_bounds()
    stmt = (
        select(ReviewLog.quality)
        .where(ReviewLog.reviewed_at >= day_start)
        .where(ReviewLog.reviewed_at < day_end)
        .where(ReviewLog.quality != None)  # noqa: E711
    )
    if source_ids is not None:
        stmt = stmt.join(Block, ReviewLog.block_id == Block.id).where(
            col(Block.source_id).in_(source_ids)
        )

    qualities = session.exec(stmt).all()
    reviewed = len(qualities)
    again = sum(1 for q in qualities if q < 3)
    return {
        "reviewed": reviewed,
        "again": again,
        "retention": round(1 - again / reviewed, 3) if reviewed else None,
        "streak": _compute_streak(session),
    }


def _compute_streak(session: Session) -> int:
    """
    连续学习天数（按本地逻辑日，全局统计不分 Deck）。
    今天还没复习不断签：从昨天往回数，今天有复习则计入。
    """
    review_days = {logical_date(dt) for dt in session.exec(select(ReviewLog.reviewed_at)).all()}
    if not review_days:
        return 0
    today = logical_date()
    day = today if today in review_days else today - timedelta(days=1)
    streak = 0
    while day in review_days:
        streak += 1
        day -= timedelta(days=1)
    return streak


def get_review_history(
    session: Session,
    days: int = 90,
    source_ids: list[int] | None = None,
) -> list[dict]:
    """
    统计过去 N 天每天的复习次数（基于 ReviewLog 聚合，按本地逻辑日分组）。
    返回：[{"date": "2025-05-30", "count": 12}, ...]，按日期升序。

    注：ReviewLog 追加式保留全部历史（含已删卡片的），复习一次记一次，
    不再像旧实现那样被 last_review 覆盖改写。
    """
    today = logical_date()
    start_date = today - timedelta(days=days - 1)
    # 起点放宽一天，避免 UTC/本地时差漏掉边界记录，Python 侧再精确过滤
    range_start = datetime(start_date.year, start_date.month, start_date.day) - timedelta(days=1)

    stmt = select(ReviewLog.reviewed_at).where(ReviewLog.reviewed_at >= range_start)
    if source_ids is not None:
        stmt = (
            select(ReviewLog.reviewed_at)
            .join(Block, ReviewLog.block_id == Block.id)
            .where(ReviewLog.reviewed_at >= range_start)
            .where(col(Block.source_id).in_(source_ids))
        )

    date_map: dict[str, int] = {}
    for reviewed_at in session.exec(stmt).all():
        d_str = logical_date(reviewed_at).strftime("%Y-%m-%d")
        date_map[d_str] = date_map.get(d_str, 0) + 1

    result = []
    for i in range(days):
        d_str = (start_date + timedelta(days=i)).strftime("%Y-%m-%d")
        result.append({"date": d_str, "count": date_map.get(d_str, 0)})

    return result
