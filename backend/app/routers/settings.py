"""
应用设置路由
GET /api/settings/review — 读复习设置（每日新学配额）
PUT /api/settings/review — 改复习设置
"""

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.crud import set_setting
from app.database import get_session
from app.schemas import ReviewSettingsResponse, ReviewSettingsUpdateRequest
from app.services.review_service import get_new_quota_config

router = APIRouter(prefix="/api/settings", tags=["Settings"])


@router.get("/review", response_model=ReviewSettingsResponse)
def get_review_settings(session: Session = Depends(get_session)):
    """当前每日新学配额（用户设置优先，环境变量兜底）"""
    unit, per_day = get_new_quota_config(session)
    return ReviewSettingsResponse(new_quota_unit=unit, new_per_day=per_day)


@router.put("/review", response_model=ReviewSettingsResponse)
def update_review_settings(
    req: ReviewSettingsUpdateRequest,
    session: Session = Depends(get_session),
):
    """修改每日新学配额（单位：篇/张）"""
    set_setting(session, "new_quota_unit", req.new_quota_unit)
    set_setting(session, "new_per_day", str(req.new_per_day))
    session.commit()
    return ReviewSettingsResponse(new_quota_unit=req.new_quota_unit, new_per_day=req.new_per_day)
