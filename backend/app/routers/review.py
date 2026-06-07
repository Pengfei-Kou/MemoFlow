"""
复习流程路由
GET  /api/review/next          — 获取下一张待复习卡片
POST /api/review/batch         — 批量提交复习打分
POST /api/review/{block_id}    — 提交复习打分
V3 改进：新增 deck_id + include_children 过滤，按 card_order 排序
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

from app.database import get_session
from app.schemas import (
    ReviewRequest, ReviewNextResponse, ReviewSubmitResponse,
    BatchReviewRequest, BatchReviewSubmitResponse,
)
from app.services.review_service import (
    get_next_review, submit_single_review, submit_passage_review,
)

router = APIRouter(prefix="/api/review", tags=["Review"])


@router.get("/next", response_model=ReviewNextResponse)
def get_next_review_card(
    session: Session = Depends(get_session),
    deck_id: Optional[int] = Query(default=None, description="限定复习范围的 Deck ID"),
    include_children: bool = Query(default=True, description="是否包含子 Deck"),
):
    """获取下一张待复习的卡片（优先级：到期复习 > 新卡片）"""
    result = get_next_review(session, deck_id, include_children)
    if result is None:
        raise HTTPException(status_code=404, detail="Deck 不存在")
    return result


@router.post("/batch", response_model=BatchReviewSubmitResponse)
def submit_batch_review_rating(
    req: BatchReviewRequest,
    session: Session = Depends(get_session),
):
    """批量提交复习打分，更新整篇文章的 SM-2 调度状态"""
    result = submit_passage_review(session, req.block_ids, req.overall_quality)
    if not result:
        raise HTTPException(status_code=404, detail="卡片不存在")
    return result


@router.post("/{block_id}", response_model=ReviewSubmitResponse)
def submit_review_rating(
    block_id: int,
    req: ReviewRequest,
    session: Session = Depends(get_session),
):
    """提交单卡复习打分，更新 SM-2 调度状态"""
    result = submit_single_review(session, block_id, req.quality)
    if not result:
        raise HTTPException(status_code=404, detail="卡片不存在")
    return result
