"""
数据库模型定义
V2 改进：
  - Source 新增 original_text 字段（保存原文）
  - Block 新增 is_suspended 字段（暂停复习）
  - datetime.utcnow() → datetime.now(timezone.utc)
V3 新增：
  - Deck 模型（树形学科仓库）
  - Source 新增 deck_id 外键
"""

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import SQLModel, Field, Relationship, Column, JSON


class Deck(SQLModel, table=True):
    """学科仓库表：树形结构，支持任意深度嵌套"""

    id: Optional[int] = Field(default=None, primary_key=True)

    # 当前节点显示名（如 "Grammar"）
    name: str = Field(index=True)

    # 完整路径（如 "English/Grammar"），唯一索引
    path: str = Field(unique=True, index=True)

    # 父节点（可选，根节点为 None）
    parent_id: Optional[int] = Field(default=None, foreign_key="deck.id")

    # AI 拆解规则，JSON 格式
    parser_config: dict = Field(default_factory=lambda: {
        "strategy": "sentence_en_zh",
        "source_lang": "English",
        "target_lang": "Chinese",
        "custom_prompt": None,
    }, sa_column=Column(JSON))

    # 卡片顺序策略
    card_order: str = Field(default="sequential_then_random")

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    # 关系
    sources: list["Source"] = Relationship(back_populates="deck")


class Source(SQLModel, table=True):
    """来源表：存储原始学习材料"""

    id: Optional[int] = Field(default=None, primary_key=True)
    title: str = Field(index=True)

    # 去重：存原文的 MD5 哈希
    content_hash: str = Field(unique=True, index=True)

    # [V2新增] 保存原文，支持重新拆解和未来 RAG
    original_text: str = Field(default="")

    # 来源类型：text / url / file
    source_type: str = Field(default="text")
    url: Optional[str] = Field(default=None)

    # [V3新增] 所属 Deck
    deck_id: Optional[int] = Field(default=None, foreign_key="deck.id", index=True)

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    # 关系：一个 Source 对应多个 Block
    blocks: list["Block"] = Relationship(
        back_populates="source",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )

    # 关系：所属 Deck
    deck: Optional[Deck] = Relationship(back_populates="sources")


class Block(SQLModel, table=True):
    """复习卡片表：最小复习单元，包含 SM-2 调度状态"""

    id: Optional[int] = Field(default=None, primary_key=True)

    # 外键
    source_id: int = Field(foreign_key="source.id", index=True)

    # 排序序号（用于上下文回溯）
    sequence_number: int

    # 内容
    content: str  # 英文原文 (Answer)
    quiz: str  # 中文提示 (Question)

    # --- 调度字段（interval/reps 两种算法共用；ease_factor 仅 SM-2）---
    reps: int = Field(default=0)
    interval: int = Field(default=0)
    ease_factor: float = Field(default=2.5)

    # --- FSRS 调度字段（scheduler_algorithm="fsrs" 时使用；旧 SM-2 卡片首次复习时接种）---
    stability: Optional[float] = Field(default=None)
    difficulty: Optional[float] = Field(default=None)
    fsrs_state: Optional[int] = Field(default=None)  # 1=Learning 2=Review 3=Relearning
    fsrs_step: Optional[int] = Field(default=None)  # 学习阶段的步数索引
    first_reviewed_at: Optional[datetime] = Field(default=None)
    last_review: Optional[datetime] = Field(default=None)
    next_review: Optional[datetime] = Field(default=None, index=True)

    # [V2新增] 暂停复习（保留卡片但不出现在复习队列中）
    is_suspended: bool = Field(default=False)

    # 交互式笔记/子卡片 (JSON格式存储)
    notes: Optional[list[dict]] = Field(
        default=None, sa_column=Column(JSON)
    )

    # 关系
    source: Source = Relationship(back_populates="blocks")


class ReviewLog(SQLModel, table=True):
    """
    复习日志：追加式，永不更新/删除（卡片删除后日志保留，Anki revlog 同款语义）。
    用途：真实热力图 / 遗忘率统计 / 未来 FSRS 参数个性化优化的训练数据。
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    block_id: int = Field(index=True)  # 不设 FK：日志比卡片长寿
    quality: Optional[int] = Field(default=None)  # 1/3/4/5；None=历史回填（评分未知）
    reviewed_at: datetime = Field(
        index=True, default_factory=lambda: datetime.now(timezone.utc)
    )
    interval_before: int = Field(default=0)
    interval_after: int = Field(default=0)
    stability_after: Optional[float] = Field(default=None)
    difficulty_after: Optional[float] = Field(default=None)

    # 评分前的完整调度状态快照（撤销用；历史回填行无快照故不可撤销）
    state_before: Optional[dict] = Field(default=None, sa_column=Column(JSON))
