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

    # 鉴权（两项都设置时启用；本地开发留空即关闭）
    # 生效方式：登录页会话 cookie（默认 90 天）或 HTTP Basic Auth（脚本用）二选一
    auth_username: str = ""
    auth_password: str = ""
    session_days: int = 90  # "记住我"会话有效期

    # 前端构建产物目录（生产容器内为 /app/static；留空则不托管前端）
    static_dir: str = ""

    # 调度参数
    mastered_threshold: int = 21  # interval >= 21 天算"已掌握"
    new_cards_per_session: int = 20  # 每次新卡片上限
    review_cards_per_session: int = 200  # 每次复习卡片上限

    # 调度算法：fsrs（默认）/ sm2（回退开关，出问题时切回）
    scheduler_algorithm: str = "fsrs"
    desired_retention: float = 0.9  # FSRS 目标记忆保持率
    # FSRS 个性化参数（21 个逗号分隔浮点数；留空用 FSRS-6 默认权重）。
    # ReviewLog 攒够 ~1000 条评分后跑 optimizer，把结果填到这里即可生效，不用改代码
    fsrs_parameters: str = ""

    # "逻辑日"判定：本地时区 + 凌晨滚动（存储仍一律 UTC，见 services/timeutils.py）
    timezone: str = "America/Toronto"
    day_rollover_hour: int = 4


# 单例
settings = Settings()
