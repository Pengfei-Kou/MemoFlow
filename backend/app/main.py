"""
MemoFlow V3 — FastAPI 应用入口
注册路由、中间件、生命周期事件
"""

import base64
import logging
import secrets
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response

from app.config import settings
from app.database import create_db_and_tables
from app.routers import sources, blocks, review, stats, decks, auth
from app.services.auth import SESSION_COOKIE, verify_session_token

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时初始化数据库"""
    logger.info("MemoFlow V3 启动中...")
    create_db_and_tables()
    logger.info("数据库初始化完成")
    yield
    logger.info("MemoFlow V3 已关闭")


# 创建 FastAPI 应用
app = FastAPI(
    title="MemoFlow V3",
    description="基于 LLM 的智能间隔重复系统 — REST API（含 Deck 学科仓库）",
    version="3.0.0",
    lifespan=lifespan,
)

# 鉴权：AUTH_USERNAME / AUTH_PASSWORD 都配置时启用（公网部署必开，见 CONTEXT.md 第 6 节）
# 两种凭据并行有效：登录页签发的会话 cookie（浏览器）/ HTTP Basic Auth（curl 脚本）。
# 静态壳（SPA/资源）放行——登录页本身要能加载，页面数据都在 /api 后面。
if settings.auth_username and settings.auth_password:
    _PUBLIC_PATHS = {"/api/health", "/api/auth/login"}
    _PROTECTED_PREFIXES = ("/api/", "/docs", "/openapi.json", "/redoc")

    def _has_valid_basic(request: Request) -> bool:
        header = request.headers.get("authorization", "")
        if not header.startswith("Basic "):
            return False
        try:
            user, _, pwd = base64.b64decode(header[6:]).decode("utf-8").partition(":")
        except Exception:
            return False
        return secrets.compare_digest(user, settings.auth_username) and secrets.compare_digest(
            pwd, settings.auth_password
        )

    def _has_valid_session(request: Request) -> bool:
        token = request.cookies.get(SESSION_COOKIE, "")
        return bool(token) and verify_session_token(token)

    @app.middleware("http")
    async def auth_gate(request: Request, call_next):
        path = request.url.path
        if path.startswith(_PROTECTED_PREFIXES) and path not in _PUBLIC_PATHS:
            if not (_has_valid_session(request) or _has_valid_basic(request)):
                # /api 的 401 不带 WWW-Authenticate：带了会触发浏览器原生弹窗，
                # 抢走登录页；/docs 等浏览器直达页保留弹窗兜底
                headers = None if path.startswith("/api/") else {"WWW-Authenticate": 'Basic realm="MemoFlow"'}
                return Response(status_code=401, headers=headers)
        return await call_next(request)


# CORS：允许前端跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite 开发服务器
        "http://localhost:3000",  # 备用端口
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(auth.router)
app.include_router(decks.router)
app.include_router(sources.router)
app.include_router(blocks.router)
app.include_router(review.router)
app.include_router(stats.router)


@app.get("/api/health", tags=["Health"])
def health():
    """健康检查（免鉴权，供容器 HEALTHCHECK 使用）"""
    return {
        "app": "MemoFlow V3",
        "status": "running",
        "docs": "/docs",
    }


# 生产模式：托管前端构建产物（STATIC_DIR 配置时启用，SPA history 路由回退到 index.html）
_static_dir = Path(settings.static_dir).resolve() if settings.static_dir else None

if _static_dir and _static_dir.is_dir():

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        if full_path.startswith("api/"):
            return JSONResponse({"detail": "Not Found"}, status_code=404)
        candidate = (_static_dir / full_path).resolve()
        if full_path and candidate.is_file() and candidate.is_relative_to(_static_dir):
            # Vite 产物带内容散列，可永久缓存；其余（manifest/图标等）短缓存
            if full_path.startswith("assets/"):
                return FileResponse(candidate, headers={"Cache-Control": "public, max-age=31536000, immutable"})
            return FileResponse(candidate, headers={"Cache-Control": "public, max-age=3600"})
        # index.html 必须每次校验，否则移动端/PWA 拿着旧壳加载不到新版
        return FileResponse(_static_dir / "index.html", headers={"Cache-Control": "no-cache"})

else:

    @app.get("/", tags=["Health"])
    def root():
        """开发模式健康检查（生产由 SPA 接管 /）"""
        return {
            "app": "MemoFlow V3",
            "status": "running",
            "docs": "/docs",
        }
