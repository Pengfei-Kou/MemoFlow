"""
Parser 插件系统（V3）
采用"预设 Strategy + 自定义 Prompt 模板"的两层设计。
不使用动态代码执行，所有 Strategy 均为预定义模板。
"""

STRATEGIES: dict[str, dict] = {
    "sentence_en_zh": {
        "prompt_template": (
            "你是一个严格的数据提取助手。请阅读以下{source_lang}文本，将其拆解为学习卡片。\n"
            "规则：\n"
            "1. 识别文本中的{source_lang}原句作为 \"content\"，必须严谨摘录原文，禁止修改任何单词、标点。\n"
            "2. 为每句原文生成{target_lang}提示问题作为 \"quiz\"。注意：直接输出中文问题即可，不要加\"英文原文是什么\"或者\"翻译\"这类前缀。\n"
            "3. 输出格式必须是 JSON 数组：[{{\"content\": \"...\", \"quiz\": \"...\"}}]\n"
            "4. 忽略无意义的闲聊。只输出 JSON，不要有任何其他文字。\n\n"
            "待处理文本：\n{text}"
        )
    },
    "haodao_oral": {
        "prompt_template": (
            "你是一个英语口语学习助手。以下文本来自「郝炟英语口语」课程，格式为：\n"
            "  中文句子\n"
            "  English translation.\n"
            "  - 注释或例句（中文：English）\n\n"
            "任务：提取所有中英文对作为学习卡片。\n"
            "规则：\n"
            "1. 每组「中文句 + 英文翻译」提取为一张卡片：quiz=中文句，content=英文翻译（严格摘录原文）\n"
            "2. Bullet 中「中文：English」格式的例句也提取为卡片（quiz=中文，content=English）\n"
            "3. 纯注释说明行（没有对应英文的）跳过\n"
            "4. 输出格式必须是 JSON 数组：[{{\"content\": \"...\", \"quiz\": \"...\"}}]\n"
            "5. 只输出 JSON，不要有任何其他文字。\n\n"
            "待处理文本：\n{text}"
        )
    },
    "vocabulary": {
        "prompt_template": (
            "你是一个词汇学习助手。请阅读以下{source_lang}文本，提取重要词汇制成学习卡片。\n"
            "规则：\n"
            "1. \"content\" 为词汇原文（包含词性，如 \"accountability (n.)\"）\n"
            "2. \"quiz\" 为{target_lang}释义 + 例句（格式：\"释义：... | 例：...\"）\n"
            "3. 输出格式必须是 JSON 数组：[{{\"content\": \"...\", \"quiz\": \"...\"}}]\n"
            "4. 只输出 JSON，不要有任何其他文字。\n\n"
            "待处理文本：\n{text}"
        )
    },
    "qa_pairs": {
        "prompt_template": (
            "你是一个知识提炼助手。请阅读以下文本，从中提取问答对制成学习卡片。\n"
            "规则：\n"
            "1. \"quiz\" 为问题，\"content\" 为答案（从原文提炼，禁止编造）\n"
            "2. 问题应覆盖文本的核心知识点\n"
            "3. 输出格式必须是 JSON 数组：[{{\"content\": \"...\", \"quiz\": \"...\"}}]\n"
            "4. 只输出 JSON，不要有任何其他文字。\n\n"
            "待处理文本：\n{text}"
        )
    },
    "cloze": {
        "prompt_template": (
            "你是一个填空题生成助手。请阅读以下文本，生成填空题学习卡片。\n"
            "规则：\n"
            "1. \"quiz\" 为含有 _____ 的填空句（从原文提取关键词替换为空格）\n"
            "2. \"content\" 为完整原句（正确答案）\n"
            "3. 每道题只挖一个空，选择最重要的词汇或短语\n"
            "4. 输出格式必须是 JSON 数组：[{{\"content\": \"...\", \"quiz\": \"...\"}}]\n"
            "5. 只输出 JSON，不要有任何其他文字。\n\n"
            "待处理文本：\n{text}"
        )
    },
    "custom": {
        "prompt_template": "{custom_prompt}\n\n待处理文本：\n{text}"
    },
}


def build_prompt(parser_config: dict, raw_text: str) -> str:
    """
    根据 Deck 的 parser_config 构建 LLM Prompt。

    parser_config 结构：
    {
        "strategy": "sentence_en_zh",
        "source_lang": "English",
        "target_lang": "Chinese",
        "custom_prompt": null
    }
    """
    strategy = parser_config.get("strategy", "sentence_en_zh")
    if strategy not in STRATEGIES:
        strategy = "sentence_en_zh"

    template = STRATEGIES[strategy]["prompt_template"]
    return template.format(
        text=raw_text,
        source_lang=parser_config.get("source_lang", "English"),
        target_lang=parser_config.get("target_lang", "Chinese"),
        custom_prompt=parser_config.get("custom_prompt") or "",
    )
