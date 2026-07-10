"""
Alembic env.py — 配置 Alembic 使用 SQLModel 的 metadata 和项目数据库 URL。

从 app.config 读取 database_url，确保和应用使用同一个数据库。
"""

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# 导入所有模型，确保 SQLModel.metadata 包含所有表定义
from sqlmodel import SQLModel
from app.models import Deck, Source, Block  # noqa: F401
from app.config import settings

# Alembic Config 对象
config = context.config

# 从应用配置注入数据库 URL（覆盖 alembic.ini 中的占位符）
config.set_main_option("sqlalchemy.url", settings.database_url)

# 日志配置
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# SQLModel metadata — autogenerate 需要这个
target_metadata = SQLModel.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (生成 SQL 脚本，不连接数据库)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,  # SQLite 需要 batch mode
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (连接数据库直接执行)."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,  # SQLite ALTER TABLE 需要 batch mode
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
