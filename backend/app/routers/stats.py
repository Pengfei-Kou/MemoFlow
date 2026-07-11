"""
统计数据路由
GET /api/stats         — 获取学习统计
GET /api/stats/history — 获取复习历史（热力图数据）
V3 改进：新增 deck_id + include_children 过滤
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session

from app.database import get_session
from app.schemas import StatsResponse, TodaySummaryResponse
from app.crud import get_stats, get_review_history, get_today_summary, get_deck_source_ids, get_leech_blocks
from app.config import settings

router = APIRouter(prefix="/api/stats", tags=["Stats"])


@router.get("", response_model=StatsResponse)
def get_statistics(
    session: Session = Depends(get_session),
    deck_id: Optional[int] = Query(default=None, description="限定统计范围的 Deck ID"),
    include_children: bool = Query(default=True, description="是否包含子 Deck"),
):
    """获取学习统计数据（可按 Deck 过滤）"""
    source_ids = None
    if deck_id is not None:
        source_ids = get_deck_source_ids(session, deck_id, include_children)

    return get_stats(session, source_ids=source_ids)


@router.get("/today", response_model=TodaySummaryResponse)
def get_today(
    session: Session = Depends(get_session),
    deck_id: Optional[int] = Query(default=None, description="限定统计范围的 Deck ID"),
    include_children: bool = Query(default=True, description="是否包含子 Deck"),
):
    """今日（本地逻辑日）复习小结：已复习次数 / 忘记次数 / 记住率"""
    source_ids = None
    if deck_id is not None:
        source_ids = get_deck_source_ids(session, deck_id, include_children)

    return get_today_summary(session, source_ids=source_ids)


@router.get("/leeches")
def get_leeches(session: Session = Depends(get_session)):
    """水蛭卡清单：累计忘记次数 >= 阈值的卡片 {block_id: lapses}"""
    return get_leech_blocks(session, settings.leech_threshold)


@router.get("/history")
def get_history(
    session: Session = Depends(get_session),
    days: int = Query(default=90, ge=7, le=365, description="统计天数（7~365）"),
    deck_id: Optional[int] = Query(default=None, description="限定统计范围的 Deck ID"),
    include_children: bool = Query(default=True, description="是否包含子 Deck"),
):
    """
    获取过去 N 天每天的复习次数，用于热力图展示。
    返回格式：[{"date": "2025-05-30", "count": 12}, ...]
    """
    source_ids = None
    if deck_id is not None:
        source_ids = get_deck_source_ids(session, deck_id, include_children)

    return get_review_history(session, days=days, source_ids=source_ids)
