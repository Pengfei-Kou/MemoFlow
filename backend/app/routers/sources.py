"""
来源管理路由
POST /api/sources/import           — 导入文本并 LLM 拆解
POST /api/sources/import-markdown  — 上传 MD 文件，规则解析生成多个 Source
POST /api/sources/fetch-url        — 抓取 URL 正文（返回预览文本，不存库）
GET  /api/sources                  — 获取来源列表
GET  /api/sources/{id}             — 获取来源详情
DELETE /api/sources/{id}           — 删除来源
V3 改进：import 新增 deck_id，LLM 调用使用 Deck 的 parser_config
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlmodel import Session

from app.database import get_session
from app.schemas import (
    SourceImportRequest,
    SourceImportResponse,
    SourcePreviewResponse,
    SourceListItem,
    SourceDetailResponse,
    MessageResponse,
    UrlFetchRequest,
    MarkdownImportResponse,
)
from app.crud import get_all_sources, get_source_by_id, delete_source
from app.services.import_service import import_text, import_markdown, preview_text
from app.services.url_fetcher import fetch_url_text

router = APIRouter(prefix="/api/sources", tags=["Sources"])


@router.post("/preview", response_model=SourcePreviewResponse)
def preview_source(
    req: SourceImportRequest,
    session: Session = Depends(get_session),
):
    """LLM 拆解预览（不入库）：返回卡片候选，供编辑/剔除后走 /import 确认入库"""
    try:
        return preview_text(session, req)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post("/import", response_model=SourceImportResponse)
def import_source(
    req: SourceImportRequest,
    session: Session = Depends(get_session),
):
    """导入文本 → LLM 拆解 → 存入数据库"""
    try:
        return import_text(session, req)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post("/import-markdown", response_model=MarkdownImportResponse)
async def import_markdown_file(
    file: UploadFile = File(..., description="Markdown 文件（.md）"),
    deck_id: int = Form(..., description="目标 Deck ID"),
    session: Session = Depends(get_session),
):
    """上传 Markdown 文件（郝炟英语口语格式），规则解析后批量创建 Sources + Blocks。"""
    # 验证文件类型
    if file.filename and not file.filename.lower().endswith('.md'):
        raise HTTPException(status_code=400, detail="只支持 .md 文件")

    # 读取文件内容
    try:
        raw_bytes = await file.read()
        text = raw_bytes.decode('utf-8')
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="文件编码错误，请使用 UTF-8 编码的 Markdown 文件")

    if not text.strip():
        raise HTTPException(status_code=400, detail="文件内容为空")

    try:
        return import_markdown(session, text, file.filename or "unknown.md", deck_id)
    except ValueError as e:
        status = 404 if "不存在" in str(e) else 422
        raise HTTPException(status_code=status, detail=str(e))


@router.post("/fetch-url")
def fetch_url_preview(body: UrlFetchRequest):
    """
    抓取 URL 正文，返回文本预览（不存库）。
    请求体：{"url": "https://..."}
    返回：{"title": "...", "text": "...", "url": "...", "char_count": N}
    """
    url = body.url.strip()
    if not url or not url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="请提供有效的 http/https URL")
    try:
        result = fetch_url_text(url)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"抓取失败：{e}")
    if not result["text"]:
        raise HTTPException(status_code=422, detail="未能从该页面提取到有效文本内容")
    return result


@router.get("", response_model=list[SourceListItem])
def list_sources(session: Session = Depends(get_session)):
    """获取所有来源列表（含卡片计数）"""
    return get_all_sources(session)


@router.get("/{source_id}", response_model=SourceDetailResponse)
def get_source(source_id: int, session: Session = Depends(get_session)):
    """获取来源详情（含所有卡片）"""
    source = get_source_by_id(session, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="来源不存在")
    return source


@router.delete("/{source_id}", response_model=MessageResponse)
def remove_source(source_id: int, session: Session = Depends(get_session)):
    """删除来源及其所有卡片"""
    success = delete_source(session, source_id)
    if not success:
        raise HTTPException(status_code=404, detail="来源不存在")
    session.commit()
    return MessageResponse(message=f"来源 {source_id} 及其卡片已删除")
