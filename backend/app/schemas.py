"""
Pydantic 模型：API 请求/响应的数据校验
与 SQLModel 的 table model 分离，避免泄露内部字段
V3 新增：Deck 相关 schema
"""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


# ============================================================
# 请求模型 (Request)
# ============================================================

class CardCandidate(BaseModel):
    """一张待入库的卡片（预览确认流中用户可编辑/剔除）"""
    content: str = Field(..., min_length=1, description="原句（答案）")
    quiz: str = Field(..., min_length=1, description="提示（问题）")


class SourceImportRequest(BaseModel):
    """导入新内容的请求体"""
    text: str = Field(..., min_length=10, description="待拆解的原始文本")
    title: Optional[str] = Field(default=None, description="标题（可选，默认取文本前20字）")
    source_type: str = Field(default="text", description="来源类型: text / url / file")
    url: Optional[str] = Field(default=None, description="原始 URL（如果从网页导入）")
    deck_id: Optional[int] = Field(default=None, description="所属 Deck ID；未传则分配到 Default Deck")
    cards: Optional[list[CardCandidate]] = Field(
        default=None,
        description="预览确认后的卡片列表；提供时跳过 LLM 拆解直接入库",
    )


class ReviewRequest(BaseModel):
    """复习打分的请求体"""
    quality: Literal[1, 3, 4, 5] = Field(..., description="评分: 1=忘, 3=难, 4=良, 5=易")

class BatchReviewRequest(BaseModel):
    """文章级批量复习打分的请求体"""
    block_ids: list[int] = Field(..., description="这批卡片的 ID 列表")
    overall_quality: Literal[1, 3, 4, 5] = Field(..., description="综合评分: 1=忘, 3=难, 4=良, 5=易")


class BlockUpdateRequest(BaseModel):
    """编辑卡片的请求体（所有字段可选，只更新传入的字段）"""
    content: Optional[str] = Field(default=None, description="英文原文")
    quiz: Optional[str] = Field(default=None, description="中文提示")
    is_suspended: Optional[bool] = Field(default=None, description="是否暂停复习")
    notes: Optional[list[dict]] = Field(default=None, description="附属知识点 [{zh, en}]，传空列表清空")


class DeckCreateRequest(BaseModel):
    """创建 Deck 的请求体"""
    name: str = Field(..., description="当前节点显示名（如 'Grammar'）")
    parent_path: Optional[str] = Field(default=None, description="父节点完整路径（如 'English'）")
    parser_config: Optional[dict] = Field(default=None, description="AI 拆解规则")
    card_order: str = Field(default="sequential_then_random", description="卡片顺序策略")


class DeckUpdateRequest(BaseModel):
    """修改 Deck 的请求体（所有字段可选）"""
    name: Optional[str] = Field(default=None, description="新的显示名")
    parser_config: Optional[dict] = Field(default=None, description="AI 拆解规则")
    card_order: Optional[str] = Field(default=None, description="卡片顺序策略")


class UrlFetchRequest(BaseModel):
    """URL 抓取的请求体"""
    url: str = Field(..., description="要抓取的 URL")


# ============================================================
# 响应模型 (Response)
# ============================================================

class BlockResponse(BaseModel):
    """单张卡片的响应"""
    id: int
    source_id: int
    sequence_number: int
    content: str
    quiz: str
    reps: int
    interval: int
    ease_factor: float
    last_review: Optional[datetime]
    next_review: Optional[datetime]
    is_suspended: bool
    notes: Optional[list[dict]] = None
    stability: Optional[float] = None  # FSRS 记忆稳定性
    difficulty: Optional[float] = None  # FSRS 难度（1~10）

    model_config = {"from_attributes": True}


class SourceListItem(BaseModel):
    """来源列表中的单项（不含完整卡片）"""
    id: int
    title: str
    source_type: str
    created_at: datetime
    block_count: int
    deck_id: Optional[int] = None

    model_config = {"from_attributes": True}


class SourceDetailResponse(BaseModel):
    """来源详情（含卡片列表）"""
    id: int
    title: str
    source_type: str
    url: Optional[str]
    original_text: str
    created_at: datetime
    deck_id: Optional[int] = None
    blocks: list[BlockResponse]

    model_config = {"from_attributes": True}


class SourcePreviewResponse(BaseModel):
    """LLM 拆解预览（未入库）"""
    title: str
    deck_id: Optional[int] = None
    cards: list[CardCandidate]
    warning: Optional[str] = None


class BlockContextItem(BaseModel):
    """上下文回溯中的一句"""
    id: int
    sequence_number: int
    content: str
    quiz: str
    is_current: bool = False


class SourceImportResponse(BaseModel):
    """导入成功后的响应"""
    source_id: int
    title: str
    block_count: int
    blocks: list[BlockResponse]
    deck_id: Optional[int] = None
    warning: Optional[str] = None


class ReviewNextResponse(BaseModel):
    """下一张待复习卡片的响应"""
    block: Optional[BlockResponse] = None
    batch: Optional[list[BlockResponse]] = None  # [V3新增] 文章级复习时的整段卡片
    remaining: int  # 队列中剩余数量
    is_new: bool  # 是新卡片还是到期复习
    source_title: Optional[str] = None  # [V3新增] 来源标题
    deck_name: Optional[str] = None     # [V3新增] Deck 名称
    review_mode: str = "card"           # [V3新增] "card" 或 "passage"
    predicted_intervals: Optional[dict[int, str]] = None  # 四档评分的预测间隔（仅单卡模式）


class ReviewSubmitResponse(BaseModel):
    """提交打分后的响应"""
    block_id: int
    new_interval: int
    new_ease_factor: float
    next_review: datetime
    message: str
    leech: bool = False  # 累计忘记次数达到阈值（水蛭卡），建议编辑改写或暂停

class BatchReviewSubmitResponse(BaseModel):
    """批量提交打分后的响应"""
    updated_count: int
    new_interval: int
    new_ease_factor: float
    next_review: datetime
    message: str


class StatsResponse(BaseModel):
    """全局统计数据"""
    total: int  # 总卡片数
    mastered: int  # 已掌握（interval >= 21）
    learning: int  # 学习中（有 next_review 但 interval < 21）
    new: int  # 新卡片（从未学过）
    due_today: int  # 今日到期


class TodaySummaryResponse(BaseModel):
    """今日（本地逻辑日）复习小结"""
    reviewed: int  # 今日已复习次数（不含历史回填）
    again: int  # 其中评"忘了"的次数
    retention: Optional[float] = None  # 记住率 = 1 - again/reviewed；无复习时为 None
    streak: int = 0  # 连续学习天数（全局，今天未复习不断签）


class DeckResponse(BaseModel):
    """Deck 响应"""
    id: int
    name: str
    path: str
    parent_id: Optional[int]
    parser_config: dict
    card_order: str
    created_at: datetime

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    """通用消息响应"""
    message: str
    success: bool = True


class MarkdownImportSourceItem(BaseModel):
    """Markdown 导入后，每个 Source 的摘要"""
    source_id: int
    title: str
    card_count: int


class MarkdownImportResponse(BaseModel):
    """Markdown 文件导入成功后的响应"""
    deck_id: int
    deck_name: str
    file_name: str
    total_sources: int
    total_cards: int
    sources: list[MarkdownImportSourceItem]
