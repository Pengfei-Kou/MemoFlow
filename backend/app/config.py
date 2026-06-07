"""
应用配置管理
使用 pydantic-settings 从 .env 文件加载配置
"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/ 目录的绝对路径，无论从哪里运行都能找到 .env
_BACKEND_DIR = Path(__file__).parent.parent


class Settings(BaseSettings):
    """全局配置，自动从 .env 文件和环境变量读取"""

    model_config = SettingsConfigDict(
        env_file=_BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM 配置（兼容 OpenAI 接口 / LiteLLM）
    llm_api_key: str = "placeholder"
    llm_base_url: str = "https://api.openai.com/v1"  # LiteLLM: http://your-host:4000/v1
    model_name: str = "gemini-2.5-flash"

    # 数据库
    database_url: str = "sqlite:///memoflow_v3.db"

    # 服务
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False

    # SM-2 参数
    mastered_threshold: int = 21  # interval >= 21 天算"已掌握"
    new_cards_per_session: int = 20  # 每次新卡片上限
    review_cards_per_session: int = 200  # 每次复习卡片上限


# 单例
settings = Settings()
