"""
卡片管理路由
GET    /api/blocks          — 获取卡片列表
GET    /api/blocks/{id}     — 获取单张卡片
PUT    /api/blocks/{id}     — 编辑卡片
DELETE /api/blocks/{id}     — 删除卡片
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

from app.database import get_session
from app.schemas import BlockResponse, BlockUpdateRequest, BlockContextItem, MessageResponse
from app.crud import get_blocks, get_block_by_id, update_block, delete_block, get_block_context

router = APIRouter(prefix="/api/blocks", tags=["Blocks"])


@router.get("", response_model=list[BlockResponse])
def list_blocks(
    deck_id: int | None = Query(default=None, description="按 Deck 筛选"),
    source_id: int | None = Query(default=None, description="按来源筛选"),
    search: str | None = Query(default=None, description="关键词搜索"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=5000, ge=1, le=10000),
    session: Session = Depends(get_session),
):
    """获取卡片列表（支持筛选、搜索、分页）"""
    return get_blocks(session, deck_id=deck_id, source_id=source_id, search=search, offset=offset, limit=limit)


@router.get("/{block_id}", response_model=BlockResponse)
def get_block(block_id: int, session: Session = Depends(get_session)):
    """获取单张卡片详情"""
    block = get_block_by_id(session, block_id)
    if not block:
        raise HTTPException(status_code=404, detail="卡片不存在")
    return block


@router.get("/{block_id}/context", response_model=list[BlockContextItem])
def block_context(
    block_id: int,
    radius: int = Query(default=2, ge=1, le=5),
    session: Session = Depends(get_session),
):
    """上下文回溯：返回该句在原文中的前后句（含自身，is_current 标记）"""
    blocks = get_block_context(session, block_id, radius)
    if blocks is None:
        raise HTTPException(status_code=404, detail="卡片不存在")
    return [
        BlockContextItem(
            id=b.id, sequence_number=b.sequence_number,
            content=b.content, quiz=b.quiz, is_current=(b.id == block_id),
        )
        for b in blocks
    ]


@router.put("/{block_id}", response_model=BlockResponse)
def edit_block(
    block_id: int,
    req: BlockUpdateRequest,
    session: Session = Depends(get_session),
):
    """编辑卡片（修改内容/提示/暂停状态）"""
    block = update_block(
        session,
        block_id,
        content=req.content,
        quiz=req.quiz,
        is_suspended=req.is_suspended,
    )
    if not block:
        raise HTTPException(status_code=404, detail="卡片不存在")
    session.commit()
    session.refresh(block)
    return block


@router.delete("/{block_id}", response_model=MessageResponse)
def remove_block(block_id: int, session: Session = Depends(get_session)):
    """删除单张卡片"""
    success = delete_block(session, block_id)
    if not success:
        raise HTTPException(status_code=404, detail="卡片不存在")
    session.commit()
    return MessageResponse(message=f"卡片 {block_id} 已删除")
