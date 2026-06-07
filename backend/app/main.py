"""
MemoFlow V3 — FastAPI 应用入口
注册路由、中间件、生命周期事件
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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


@app.get("/", tags=["Health"])
def root():
    """健康检查"""
    return {
        "app": "MemoFlow V3",
        "status": "running",
        "docs": "/docs",
    }
