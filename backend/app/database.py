"""
数据库引擎与会话管理
V2 改进：数据库路径通过 config 统一管理
"""

from sqlmodel import SQLModel, Session, create_engine

from app.config import settings

# 创建引擎
connect_args = {"check_same_thread": False}  # SQLite 多线程兼容
engine = create_engine(
    settings.database_url,
    echo=settings.debug,
    connect_args=connect_args,
)


def create_db_and_tables():
    """初始化数据库：如果表不存在则创建"""
    SQLModel.metadata.create_all(engine)


def get_session():
    """
    FastAPI 依赖注入：获取数据库会话
    用法：session: Session = Depends(get_session)
    """
    with Session(engine) as session:
        yield session
