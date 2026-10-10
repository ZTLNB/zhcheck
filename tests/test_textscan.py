"""屏蔽掩码与行内指令的单元测试。"""

from __future__ import annotations

import unittest

from zhcheck.textscan import (
    MODE_MARKDOWN,
    MODE_TEXT,
    LineIndex,
    build_mask,
    parse_directives,
    resolve_mode,
)


def unprotected(text: str, mode: str = MODE_MARKDOWN) -> str:
    mask = build_mask(text, mode)
    return "".join(ch for i, ch in enumerate(text) if not mask[i])


class BuildMaskTest(unittest.TestCase):
    def test_masks_fenced_code_block(self) -> None:
        text = "正文中文abc\n\n```python\nprint('中文abc')\n```\n\n尾部中文abc"
        remaining = unprotected(text)
        self.assertNotIn("print", remaining)
        self.assertIn("正文中文abc", remaining)
        self.assertIn("尾部中文abc", remaining)

    def test_masks_tilde_fence(self) -> None:
        text = "~~~\n中文abc\n~~~\n中文abc"
        remaining = unprotected(text)
        self.assertEqual(remaining.count("中文abc"), 1)

    def test_masks_inline_code(self) -> None:
        text = "看 `中文abc` 与 ``a`b`` 与裸露的中文abc"
        remaining = unprotected(text)
        self.assertNotIn("看 `", remaining)
        self.assertEqual(remaining.count("中文abc"), 1)

    def test_masks_urls_and_emails(self) -> None:
        text = "见 https://example.com/a,b 与 me@example.com 结尾"
        remaining = unprotected(text)
        self.assertNotIn("example.com/a,b", remaining)
        self.assertNotIn("me@", remaining)

    def test_masks_link_destination_but_keeps_text(self) -> None:
        text = "链接 [中文abc](https://example.com/x,y) 结束"
        remaining = unprotected(text)
        self.assertIn("中文abc", remaining)
        self.assertNotIn("example.com", remaining)

    def test_masks_front_matter(self) -> None:
        text = "---\ntitle: 中文abc\n---\n正文中文abc"
        remaining = unprotected(text)
        self.assertEqual(remaining.count("中文abc"), 1)

    def test_masks_html_comment_and_tag(self) -> None:
        text = "<!-- 中文abc --><div class=\"中文abc\">正文中文abc</div>"
        remaining = unprotected(text)
        self.assertEqual(remaining.count("中文abc"), 1)

    def test_masks_hr_line(self) -> None:
        text = "上一行\n\n---\n\n下一行"
        remaining = unprotected(text)
        self.assertNotIn("---", remaining)

    def test_text_mode_keeps_code_untouched(self) -> None:
        # 纯文本模式只屏蔽 URL 等，不处理 Markdown 语法
        text = "```\n中文abc\n```"
        remaining = unprotected(text, MODE_TEXT)
        self.assertIn("中文abc", remaining)

    def test_extra_exception_pattern(self) -> None:
        text = "使用Python编写"
        mask = build_mask(text, MODE_MARKDOWN, extra_patterns=["Python"])
        self.assertEqual("".join("1" if bit else "0" for bit in mask), "0011111100")

    def test_empty_text(self) -> None:
        self.assertEqual(len(build_mask("", MODE_MARKDOWN)), 0)


class DirectiveTest(unittest.TestCase):
    def parse(self, text: str):
        index = LineIndex(text)
        return parse_directives(text, index)

    def test_disable_next_line(self) -> None:
        text = "<!-- zhcheck-disable-next-line ZC001 -->\n第二行\n第三行"
        directives, spans = self.parse(text)
        self.assertTrue(directives.is_disabled("ZC001", 2))
        self.assertFalse(directives.is_disabled("ZC001", 3))
        self.assertFalse(directives.is_disabled("ZC002", 2))
        self.assertEqual(len(spans), 1)

    def test_disable_range(self) -> None:
        text = "第一行\n<!-- zhcheck-disable ZC001 -->\n第二行\n第三行\n<!-- zhcheck-enable -->\n第四行"
        directives, _ = self.parse(text)
        self.assertTrue(directives.is_disabled("ZC001", 3))
        self.assertTrue(directives.is_disabled("ZC001", 4))
        self.assertFalse(directives.is_disabled("ZC001", 5))
        self.assertFalse(directives.is_disabled("ZC002", 3))

    def test_disable_all_rules(self) -> None:
        text = "<!-- zhcheck-disable -->\n第二行"
        directives, _ = self.parse(text)
        self.assertTrue(directives.is_disabled("ZC001", 2))
        self.assertTrue(directives.is_disabled("ZC012", 2))

    def test_disable_file(self) -> None:
        text = "<!-- zhcheck-disable-file ZC009 -->\n任意内容"
        directives, _ = self.parse(text)
        self.assertTrue(directives.is_disabled("ZC009", 2))
        self.assertFalse(directives.is_disabled("ZC001", 2))

    def test_directive_and_range_do_not_clobber(self) -> None:
        text = (
            "<!-- zhcheck-disable ZC002 -->\n"
            "<!-- zhcheck-disable-next-line ZC001 -->\n"
            "第三行\n"
        )
        directives, _ = self.parse(text)
        self.assertTrue(directives.is_disabled("ZC002", 3))
        self.assertTrue(directives.is_disabled("ZC001", 3))

    def test_bare_directive_without_comment(self) -> None:
        text = "zhcheck-disable ZC001\n第二行"
        directives, spans = self.parse(text)
        self.assertTrue(directives.is_disabled("ZC001", 2))
        self.assertEqual(len(spans), 1)

    def test_no_directive(self) -> None:
        directives, spans = self.parse("普通文本")
        self.assertEqual(spans, [])
        self.assertFalse(directives.is_disabled("ZC001", 1))


class ResolveModeTest(unittest.TestCase):
    def test_extension_detection(self) -> None:
        self.assertEqual(resolve_mode("auto", "README.md"), MODE_MARKDOWN)
        self.assertEqual(resolve_mode("auto", "notes.markdown"), MODE_MARKDOWN)
        self.assertEqual(resolve_mode("auto", "a.txt"), MODE_TEXT)
        self.assertEqual(resolve_mode("auto", "a.rst"), MODE_TEXT)

    def test_explicit_mode_wins(self) -> None:
        self.assertEqual(resolve_mode(MODE_TEXT, "README.md"), MODE_TEXT)
        self.assertEqual(resolve_mode(MODE_MARKDOWN, "a.txt"), MODE_MARKDOWN)


class LineIndexTest(unittest.TestCase):
    def test_locate(self) -> None:
        text = "第一行\n第二行\n第三行"
        index = LineIndex(text)
        self.assertEqual(index.line_of(0), 1)
        self.assertEqual(index.line_of(4), 2)
        self.assertEqual(index.column_of(4), 1)
        self.assertEqual(index.line_of(8), 3)
        self.assertEqual(index.line_text(2), "第二行")

    def test_last_line_without_newline(self) -> None:
        index = LineIndex("a\nb")
        self.assertEqual(index.line_of(2), 2)
        self.assertEqual(index.line_text(2), "b")


if __name__ == "__main__":
    unittest.main()
