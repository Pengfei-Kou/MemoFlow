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
from app.routers import sources, blocks, review, stats, decks

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

# HTTP Basic Auth：AUTH_USERNAME / AUTH_PASSWORD 都配置时启用（公网部署必开，见 CONTEXT.md 第 6 节）
if settings.auth_username and settings.auth_password:

    @app.middleware("http")
    async def basic_auth(request: Request, call_next):
        if request.url.path == "/api/health":  # 容器健康检查免鉴权
            return await call_next(request)
        header = request.headers.get("authorization", "")
        ok = False
        if header.startswith("Basic "):
            try:
                user, _, pwd = base64.b64decode(header[6:]).decode("utf-8").partition(":")
                ok = secrets.compare_digest(user, settings.auth_username) and secrets.compare_digest(
                    pwd, settings.auth_password
                )
            except Exception:
                ok = False
        if not ok:
            return Response(status_code=401, headers={"WWW-Authenticate": 'Basic realm="MemoFlow"'})
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
            return FileResponse(candidate)
        return FileResponse(_static_dir / "index.html")

else:

    @app.get("/", tags=["Health"])
    def root():
        """开发模式健康检查（生产由 SPA 接管 /）"""
        return {
            "app": "MemoFlow V3",
            "status": "running",
            "docs": "/docs",
        }
