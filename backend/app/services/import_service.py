"""
导入业务逻辑服务层

将 sources router 中的导入编排逻辑抽到此处：
- 文本导入（LLM 拆解）
- Markdown 文件导入（规则解析）

Router 层只做：参数校验 → 调用 Service → 返回响应
"""

import hashlib

from sqlmodel import Session

from app.models import Block
from app.schemas import (
    SourceImportRequest,
    SourceImportResponse,
    BlockResponse,
    MarkdownImportResponse,
)
from app.crud import (
    create_source, get_deck_by_id, get_default_deck,
)
from app.services.llm import parse_text_with_llm
from app.services.md_parser import parse_haodao_markdown


def import_text(
    session: Session,
    req: SourceImportRequest,
) -> SourceImportResponse:
    """
    文本导入流程：
    1. 确定 Deck 和 parser_config
    2. 调用 LLM 拆解
    3. 创建 Source + Block
    4. 统一 commit

    Raises:
        ValueError: Deck 不存在
        RuntimeError: LLM 拆解失败
    """
    warning = None
    if req.deck_id:
        deck = get_deck_by_id(session, req.deck_id)
        if not deck:
            raise ValueError(f"Deck {req.deck_id} 不存在")
        parser_config = deck.parser_config
    else:
        deck = get_default_deck(session)
        parser_config = deck.parser_config
        warning = f"未指定 Deck，已自动分配到 Default Deck（id={deck.id}）"

    # 调用 LLM 拆解
    blocks_data = parse_text_with_llm(req.text, parser_config)
    if not blocks_data:
        raise RuntimeError("AI 提取失败：未能从文本中生成有效卡片")

    # 创建 Source
    title = req.title if req.title else req.text[:20] + "..."
    content_hash = hashlib.sha256(req.text.encode()).hexdigest()

    source = create_source(
        session=session,
        title=title,
        content_hash=content_hash,
        original_text=req.text,
        source_type=req.source_type,
        url=req.url,
        deck_id=deck.id,
    )

    # 批量创建 Block
    created_blocks = []
    for i, item in enumerate(blocks_data):
        block = Block(
            source_id=source.id,
            sequence_number=i + 1,
            content=item["content"],
            quiz=item["quiz"],
        )
        session.add(block)
        created_blocks.append(block)

    session.commit()
    for block in created_blocks:
        session.refresh(block)

    return SourceImportResponse(
        source_id=source.id,
        title=source.title,
        block_count=len(created_blocks),
        blocks=[BlockResponse.model_validate(b) for b in created_blocks],
        deck_id=deck.id,
        warning=warning,
    )


def import_markdown(
    session: Session,
    text: str,
    filename: str,
    deck_id: int,
) -> MarkdownImportResponse:
    """
    Markdown 文件导入流程：
    1. 验证 Deck
    2. 规则解析 Markdown
    3. 批量创建 Sources + Blocks
    4. 统一 commit

    Raises:
        ValueError: Deck 不存在 / 无有效卡片
    """
    deck = get_deck_by_id(session, deck_id)
    if not deck:
        raise ValueError(f"Deck {deck_id} 不存在")

    # 规则解析
    sections = parse_haodao_markdown(text)
    if not sections:
        raise ValueError(
            "未能从文件中提取有效卡片，请确认文件格式符合「郝炟英语口语」格式"
        )

    # 批量创建
    created_sources = []
    total_cards = 0

    for section in sections:
        source_title = section["source_title"]
        cards = section["cards"]
        if not cards:
            continue

        source_text = "\n".join(f"{c['quiz']} / {c['content']}" for c in cards)
        content_hash = hashlib.sha256(f"{deck_id}:{source_title}".encode()).hexdigest()

        source = create_source(
            session=session,
            title=source_title,
            content_hash=content_hash,
            original_text=source_text,
            source_type="text",
            deck_id=deck.id,
        )

        for i, card in enumerate(cards):
            block = Block(
                source_id=source.id,
                sequence_number=i + 1,
                content=card["content"],
                quiz=card["quiz"],
                notes=card.get("notes"),
            )
            session.add(block)

        created_sources.append({
            "source_id": source.id,
            "title": source_title,
            "card_count": len(cards),
        })
        total_cards += len(cards)

    session.commit()

    return MarkdownImportResponse(
        deck_id=deck.id,
        deck_name=deck.name,
        file_name=filename,
        total_sources=len(created_sources),
        total_cards=total_cards,
        sources=created_sources,
    )
