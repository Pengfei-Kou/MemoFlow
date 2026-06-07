"""
Tests for the Markdown parser (郝炟英语口语 format).
"""

from app.services.md_parser import parse_haodao_markdown, _is_chinese, _is_english


class TestLanguageDetection:
    """Tests for _is_chinese and _is_english helpers."""

    def test_chinese_sentence(self):
        assert _is_chinese("这是一个测试句子")

    def test_english_sentence(self):
        assert _is_english("This is a test sentence.")

    def test_chinese_is_not_english(self):
        assert not _is_english("这是一个测试句子")

    def test_english_is_not_chinese(self):
        assert not _is_chinese("This is a test sentence.")

    def test_mixed_mostly_chinese(self):
        assert _is_chinese("这是一个test测试")

    def test_mixed_mostly_english(self):
        assert _is_english("This is a 测试 sentence.")


class TestParseHaodaoMarkdown:
    """Tests for the full parser pipeline."""

    def test_basic_pair(self):
        """Standard Chinese line + English translation → one card."""
        md = """# 1 Video 1
## 1.1 Content
你好世界
Hello world.
"""
        result = parse_haodao_markdown(md)
        assert len(result) == 1
        assert result[0]["source_title"] == "1 Video 1"
        assert len(result[0]["cards"]) == 1
        assert result[0]["cards"][0]["quiz"] == "你好世界"
        assert result[0]["cards"][0]["content"] == "Hello world."

    def test_multiple_pairs(self):
        """Multiple Chinese-English pairs in one Content section."""
        md = """# 1 Video 1
## 1.1 Content
你好
Hello.
再见
Goodbye.
"""
        result = parse_haodao_markdown(md)
        assert len(result) == 1
        cards = result[0]["cards"]
        assert len(cards) == 2
        assert cards[0]["quiz"] == "你好"
        assert cards[1]["quiz"] == "再见"

    def test_quiz_section_skipped(self):
        """H2 sections with 'Quiz' should be entirely skipped."""
        md = """# 1 Video 1
## 1.1 Content
你好
Hello.
## 1.2 Quiz
这不应该被解析
This should not be parsed.
"""
        result = parse_haodao_markdown(md)
        cards = result[0]["cards"]
        assert len(cards) == 1
        assert cards[0]["quiz"] == "你好"

    def test_multiple_sections(self):
        """Multiple H1 sections → multiple Source entries."""
        md = """# 1 Video 1
## 1.1 Content
你好
Hello.
# 2 Video 2
## 2.1 Content
再见
Goodbye.
"""
        result = parse_haodao_markdown(md)
        assert len(result) == 2
        assert result[0]["source_title"] == "1 Video 1"
        assert result[1]["source_title"] == "2 Video 2"

    def test_empty_file(self):
        """Empty file returns empty list."""
        assert parse_haodao_markdown("") == []

    def test_no_valid_cards(self):
        """File with only headers and no content → empty list."""
        md = """# 1 Video 1
## 1.1 Quiz
Some quiz content
"""
        result = parse_haodao_markdown(md)
        assert result == []

    def test_bullet_notes_extracted(self):
        """Bullet lines with '中文：English' format should be extracted as notes."""
        md = """# 1 Video 1
## 1.1 Content
你好世界
Hello world.
- 早上好：Good morning.
"""
        result = parse_haodao_markdown(md)
        cards = result[0]["cards"]
        assert len(cards) == 1
        assert "notes" in cards[0]
        assert len(cards[0]["notes"]) == 1
        assert cards[0]["notes"][0]["zh"] == "早上好"
        assert cards[0]["notes"][0]["en"] == "Good morning."

    def test_non_content_h2_skipped(self):
        """H2 sections that are neither Content nor Quiz are skipped."""
        md = """# 1 Video 1
## 1.1 Vocabulary
一些词汇
Some vocab.
## 1.2 Content
你好
Hello.
"""
        result = parse_haodao_markdown(md)
        cards = result[0]["cards"]
        assert len(cards) == 1
        assert cards[0]["quiz"] == "你好"

    def test_section_with_only_quiz_excluded(self):
        """A section that only has Quiz subsections produces no cards → excluded from result."""
        md = """# 1 Video 1
## 1.1 Quiz
测试题
Test question.
"""
        result = parse_haodao_markdown(md)
        assert result == []

    def test_short_lines_filtered(self):
        """Lines shorter than 2 chars (quiz) or 3 chars (content) should be filtered."""
        md = """# 1 Video 1
## 1.1 Content
啊
Hi
正常的句子
A normal sentence.
"""
        result = parse_haodao_markdown(md)
        cards = result[0]["cards"]
        # "啊"/"Hi" are too short, only the second pair should survive
        assert len(cards) == 1
        assert cards[0]["quiz"] == "正常的句子"
