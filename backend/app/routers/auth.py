"""
登录/登出路由
POST /api/auth/login  — 校验账密，签发会话 cookie（"记住我"=90 天，否则浏览器会话级）
POST /api/auth/logout — 清除会话 cookie
GET  /api/auth/me     — 探测当前是否已通过鉴权（受中间件保护，能到达即已登录）
"""

import asyncio
import secrets

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field

from app.config import settings
from app.services.auth import SESSION_COOKIE, make_session_token

router = APIRouter(prefix="/api/auth", tags=["Auth"])


class LoginRequest(BaseModel):
    username: str = Field(..., max_length=100)
    password: str = Field(..., max_length=200)
    remember: bool = Field(default=True, description="记住我：90 天长效会话")


@router.post("/login")
async def login(body: LoginRequest, response: Response):
    if not (settings.auth_username and settings.auth_password):
        raise HTTPException(status_code=400, detail="服务端未启用鉴权")

    ok = secrets.compare_digest(body.username, settings.auth_username) and secrets.compare_digest(
        body.password, settings.auth_password
    )
    if not ok:
        await asyncio.sleep(1)  # 失败惩罚延迟，拖慢暴力尝试
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    token = make_session_token(settings.session_days)
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=settings.session_days * 86400 if body.remember else None,  # None=会话级
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
    )
    return {"message": "登录成功", "remember_days": settings.session_days if body.remember else 0}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"message": "已退出登录"}


@router.get("/me")
def me():
    """能到达这里说明已通过中间件鉴权"""
    return {"authenticated": True, "username": settings.auth_username}
