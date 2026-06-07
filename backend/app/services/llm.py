"""
LLM ETL 服务：使用 OpenAI 兼容接口（LiteLLM / OpenAI）将原始文本拆解为复习卡片
V3 改进：调用 parsers.build_prompt() 替换硬编码 prompt
"""

import json
import logging
from typing import Optional

from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.config import settings
from app.services.parsers import build_prompt

logger = logging.getLogger(__name__)

_client: Optional[OpenAI] = None


def _get_client() -> OpenAI:
    """懒加载 OpenAI 兼容客户端（单例）"""
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            timeout=60.0,
        )
        logger.info(f"LLM 客户端已初始化 → {settings.llm_base_url}，模型: {settings.model_name}")
    return _client


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=15),
    retry=retry_if_exception_type((ConnectionError, TimeoutError, OSError)),
    before_sleep=lambda state: logger.warning(
        f"LLM 调用失败（第 {state.attempt_number} 次），{state.outcome.exception()!r}，正在重试..."
    ),
)
def _call_llm(prompt: str) -> str | None:
    """带重试的 LLM API 调用，返回原始 content 字符串"""
    client = _get_client()
    response = client.chat.completions.create(
        model=settings.model_name,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        response_format={"type": "json_object"},
    )
    return response.choices[0].message.content


def parse_text_with_llm(raw_text: str, parser_config: dict | None = None) -> list[dict]:
    """
    ETL 核心：将原始文本拆解为 [{content, quiz}, ...] 卡片列表

    流程：
    1. 用 parser_config 构建 Prompt（默认 sentence_en_zh strategy）
    2. 解析返回的 JSON
    3. Python 硬校验：content 必须是原文子集（防幻觉）
    """
    if not raw_text or len(raw_text) < 10:
        return []

    if parser_config is None:
        parser_config = {"strategy": "sentence_en_zh", "source_lang": "English", "target_lang": "Chinese"}

    logger.info(f"开始 LLM 拆解，strategy={parser_config.get('strategy')}，文本长度: {len(raw_text)}")

    prompt = build_prompt(parser_config, raw_text)

    try:
        content_str = _call_llm(prompt)
        if not content_str:
            logger.warning("LLM 返回内容为空")
            return []

        # 清洗 JSON（有时模型会多输出 markdown 代码块）
        clean = content_str.replace("```json", "").replace("```", "").strip()
        data = json.loads(clean)

        # 兼容：返回 list 或包裹在 dict 里的 list
        blocks_data: list[dict] = []
        if isinstance(data, list):
            blocks_data = data
        elif isinstance(data, dict):
            for value in data.values():
                if isinstance(value, list):
                    blocks_data = value
                    break

        if not blocks_data:
            logger.warning(f"未找到有效数据数组: {data}")
            return []

    except Exception as e:
        logger.error(f"LLM 调用失败: {e}")
        return []

    # --- 硬校验：拦截幻觉（仅对 sentence_en_zh 和 cloze strategy 校验 content 原文匹配） ---
    strategy = parser_config.get("strategy", "sentence_en_zh")
    apply_hallucination_check = strategy in ("sentence_en_zh", "cloze")

    valid_blocks = []
    for item in blocks_data:
        content = item.get("content", "").strip()
        quiz = item.get("quiz", "").strip()

        if not content or not quiz:
            continue

        if apply_hallucination_check:
            if content not in raw_text and content.rstrip(".,?!;:") not in raw_text:
                logger.warning(f"拦截幻觉: '{content[:60]}...'")
                continue

        valid_blocks.append({"content": content, "quiz": quiz})

    logger.info(f"LLM 拆解完成：{len(valid_blocks)}/{len(blocks_data)} 通过校验")
    return valid_blocks
