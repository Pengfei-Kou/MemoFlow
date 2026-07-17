"""
Markdown 文件解析器（针对「郝炟英语口语」格式）

支持的文档结构：
  # N Video N            ← 顶层章节标题（→ Source 标题）
  ## N.1 Content         ← 学习内容段（要解析的部分）
  中文句                  ← 问题
  English translation.   ← 答案
  - 注释说明              ← 可选：跳过
  - 中文例句：English     ← 可选：提取为额外卡片

  ## N.2 Quiz            ← 跳过整个段落

解析规则：
1. 按 `#` H1 标题分 Section（每个 H1 → 一个 Source）
2. 只解析 H2 标题中含 "content" / "内容" 的段落
3. 跳过 H2 标题中含 "quiz" / "测验" 的段落
4. 逐行扫描：
   - 纯中文行 → quiz (问题)
   - 纯英文行（紧接中文行）→ content (答案)
   - bullet 中 `中文：English` 格式 → 额外卡片
"""

import re
from typing import Iterator

# ── 语言检测 ───────────────────────────────────────────────

_CJK_RE = re.compile(r'[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef]')
_EN_WORD_RE = re.compile(r'[a-zA-Z]')


def _is_chinese(text: str) -> bool:
    """判断文本是否以中文为主"""
    cjk = len(_CJK_RE.findall(text))
    return cjk > 0 and cjk >= len(text) * 0.15


def _is_english(text: str) -> bool:
    """判断文本是否以英文为主（且不是注释说明行）"""
    en = len(_EN_WORD_RE.findall(text))
    cjk = len(_CJK_RE.findall(text))
    return en > 0 and en > cjk


# ── 内容段解析 ─────────────────────────────────────────────

def _clean_markdown_symbols(text: str) -> str:
    """清理多余的 Markdown/LaTeX 符号，如 **、$$、$5\\%$"""
    text = re.sub(r'[*_]{2}', '', text)
    text = re.sub(r'\$\$', '', text)
    # 内联公式仅限内部无空白（$5\%$、$x$），防止误伤 "costs $5 and $10" 这类真美元
    text = re.sub(r'\$([^$\s]+)\$', r'\1', text)
    text = re.sub(r'\\([%$&#_])', r'\1', text)   # LaTeX 转义：\% → %

    return text.strip()

def _parse_content_section(lines: list[str]) -> list[dict]:
    """
    解析 Content 段中的所有行，返回 [{content, quiz}, ...] 列表。

    逻辑：
    - 两个相邻的非空行，第一行中文 + 第二行英文 → 一张主卡片
    - bullet 行 `- 中文：英文` → 一张例句卡片
    - 其他 bullet 注释行 → 跳过
    """
    cards: list[dict] = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()

        # 跳过空行、H2 标题、代码块
        if not line or line.startswith('#') or line.startswith('```'):
            i += 1
            continue

        # ── Bullet 注释行 ──────────────────────────────────
        if line.startswith('- ') or line.startswith('* ') or line.startswith('\t- '):
            bullet = re.sub(r'^[-*]\s*|\t[-*]\s*', '', line).strip()
            # 提取「中文：英文」例句（冒号分隔，两侧分别是中英文）
            for sep in ['：', ': ']:
                if sep in bullet:
                    parts = bullet.split(sep, 1)
                    if len(parts) == 2:
                        zh_part = _clean_markdown_symbols(parts[0])
                        en_part = _clean_markdown_symbols(parts[1])
                        # 过滤掉非例句的格式说明（如 "根据语句的严谨性：Forecast > project > expect"）
                        if (
                            _is_chinese(zh_part)
                            and _is_english(en_part)
                            and len(zh_part) >= 3
                            and len(en_part) >= 3
                            # 排除纯说明行（没有动词格式，全是逗号分隔的词语列表）
                            and not (zh_part.count('，') > 2 and '：' not in zh_part)
                        ):
                            if cards:
                                if 'notes' not in cards[-1]:
                                    cards[-1]['notes'] = []
                                cards[-1]['notes'].append({'zh': zh_part, 'en': en_part})
                            else:
                                cards.append({'quiz': zh_part, 'content': en_part})
                    break
            i += 1
            continue

        # ── 主卡片：中文行 + 下一行英文 ────────────────────
        if _is_chinese(line):
            # 去掉括号（表示旁白/对方的话，仍然保留句子）
            quiz = re.sub(r'^[（(]|[）)]$', '', line)
            quiz = _clean_markdown_symbols(quiz)
            # 向后找英文翻译行
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1  # 跳过空行
            if j < len(lines):
                next_line = lines[j].strip()
                if next_line and _is_english(next_line) and not next_line.startswith('#'):
                    # 取英文行，去掉末尾注释 (要求连字符前至少有一个空格，避免误删连字符单词)
                    content = re.sub(r'\s+[-–—].*$', '', next_line)
                    content = _clean_markdown_symbols(content)
                    # 避免过短的翻译
                    if quiz and content and len(quiz) >= 2 and len(content) >= 3:
                        cards.append({'quiz': quiz, 'content': content})
                    i = j + 1
                    continue
        i += 1

    return cards


# ── 顶层解析 ───────────────────────────────────────────────

def _split_into_sections(text: str) -> Iterator[tuple[str, str]]:
    """
    按 H1 标题切分，返回 (title, body) 的迭代器。
    """
    parts = re.split(r'^(#\s+.+)$', text, flags=re.MULTILINE)
    # parts: ['', '# Title', 'body', '# Title2', 'body2', ...]
    i = 1
    while i < len(parts) - 1:
        title = parts[i].lstrip('#').strip()
        body = parts[i + 1]
        yield title, body
        i += 2


def _is_content_heading(heading: str) -> bool:
    lh = heading.lower()
    return 'content' in lh or '内容' in lh


def _is_quiz_heading(heading: str) -> bool:
    lh = heading.lower()
    return 'quiz' in lh or '测验' in lh or '练习' in lh


def parse_haodao_markdown(text: str) -> list[dict]:
    """
    解析整个 Markdown 文件，返回：
    [
      {
        "source_title": "1 Video 1",
        "cards": [{"content": "...", "quiz": "..."}, ...]
      },
      ...
    ]
    跳过 cards 为空的 section。
    """
    result = []

    for section_title, section_body in _split_into_sections(text):
        # 按 H2 切分内部段落
        subsections = re.split(r'^(##\s+.+)$', section_body, flags=re.MULTILINE)

        all_cards: list[dict] = []
        i = 1
        while i < len(subsections) - 1:
            h2_title = subsections[i].lstrip('#').strip()
            h2_body = subsections[i + 1]
            i += 2

            if _is_quiz_heading(h2_title):
                continue
            if not _is_content_heading(h2_title):
                continue

            lines = h2_body.splitlines()
            cards = _parse_content_section(lines)
            all_cards.extend(cards)

        if all_cards:
            result.append({
                'source_title': section_title,
                'cards': all_cards,
            })

    return result
