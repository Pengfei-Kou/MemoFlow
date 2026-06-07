"""
Deck 管理路由（V3 新增）
GET    /api/decks       — 获取所有 Deck（列表）
POST   /api/decks       — 创建 Deck
GET    /api/decks/{id}  — 获取单个 Deck 详情
PUT    /api/decks/{id}  — 修改 Deck
DELETE /api/decks/{id}  — 删除 Deck（级联删除 Sources 和 Blocks）
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.database import get_session
from app.schemas import DeckCreateRequest, DeckUpdateRequest, DeckResponse, MessageResponse
from app.crud import create_deck, get_all_decks, get_deck_by_id, update_deck, delete_deck

router = APIRouter(prefix="/api/decks", tags=["Decks"])


@router.get("", response_model=list[DeckResponse])
def list_decks(session: Session = Depends(get_session)):
    """获取所有 Deck（按 path 排序）"""
    return get_all_decks(session)


@router.post("", response_model=DeckResponse)
def create_new_deck(req: DeckCreateRequest, session: Session = Depends(get_session)):
    """创建新 Deck"""
    try:
        deck = create_deck(
            session=session,
            name=req.name,
            parent_path=req.parent_path,
            parser_config=req.parser_config,
            card_order=req.card_order,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    session.commit()
    session.refresh(deck)
    return deck


@router.get("/{deck_id}", response_model=DeckResponse)
def get_deck(deck_id: int, session: Session = Depends(get_session)):
    """获取单个 Deck 详情"""
    deck = get_deck_by_id(session, deck_id)
    if not deck:
        raise HTTPException(status_code=404, detail="Deck 不存在")
    return deck


@router.put("/{deck_id}", response_model=DeckResponse)
def modify_deck(deck_id: int, req: DeckUpdateRequest, session: Session = Depends(get_session)):
    """修改 Deck（名称、parser_config、card_order）"""
    deck = update_deck(
        session=session,
        deck_id=deck_id,
        name=req.name,
        parser_config=req.parser_config,
        card_order=req.card_order,
    )
    if not deck:
        raise HTTPException(status_code=404, detail="Deck 不存在")
    session.commit()
    session.refresh(deck)
    return deck


@router.delete("/{deck_id}", response_model=MessageResponse)
def remove_deck(deck_id: int, session: Session = Depends(get_session)):
    """删除 Deck（级联删除 Sources 和 Blocks）"""
    success = delete_deck(session, deck_id)
    if not success:
        raise HTTPException(status_code=404, detail="Deck 不存在")
    session.commit()
    return MessageResponse(message=f"Deck {deck_id} 及其内容已删除")
