"""空格类规则测试。"""

from __future__ import annotations

import unittest

from helpers import fixed, ids, issues_of, lint
from zhcheck.config import Config


class MixedSpacingTest(unittest.TestCase):
    def test_flags_chinese_then_ascii(self) -> None:
        issues = issues_of("使用Python编写", "ZC001")
        self.assertEqual(len(issues), 2)

    def test_no_flag_when_space_present(self) -> None:
        self.assertEqual(issues_of("使用 Python 编写", "ZC001"), [])

    def test_fix_produces_correct_text(self) -> None:
        self.assertEqual(fixed("使用Python编写"), "使用 Python 编写")

    def test_fix_handles_multiple_boundaries(self) -> None:
        self.assertEqual(fixed("第1章有2个例子"), "第 1 章有 2 个例子")

    def test_ignores_ascii_only_text(self) -> None:
        self.assertEqual(issues_of("Hello world", "ZC001"), [])

    def test_ignores_punctuation_boundary(self) -> None:
        # 中文与半角标点相邻不属于本规则（由 ZC002 处理）
        self.assertEqual(issues_of("中文,后续", "ZC001"), [])

    def test_ignores_code_span(self) -> None:
        self.assertEqual(issues_of("使用 `Python` 编写", "ZC001"), [])
        self.assertEqual(issues_of("```\n中文abc\n```", "ZC001"), [])

    def test_ignores_url(self) -> None:
        self.assertEqual(issues_of("见 https://example.com/a1 结束", "ZC001"), [])

    def test_fix_is_idempotent(self) -> None:
        once = fixed("中文abc中文def")
        self.assertEqual(fixed(once), once)


class MultiSpaceTest(unittest.TestCase):
    def test_flags_multiple_spaces_between_chinese(self) -> None:
        issues = issues_of("中文   中文", "ZC011")
        self.assertEqual(len(issues), 1)

    def test_fix_collapses_to_single_space(self) -> None:
        self.assertEqual(fixed("中文   中文"), "中文 中文")

    def test_ignores_markdown_list_indent(self) -> None:
        self.assertEqual(issues_of("  - 列表项", "ZC011"), [])

    def test_ignores_ascii_only(self) -> None:
        self.assertEqual(issues_of("a   b", "ZC011"), [])


class NumberUnitTest(unittest.TestCase):
    def test_disabled_by_default(self) -> None:
        self.assertEqual(issues_of("内存 16GB", "ZC008"), [])

    def test_enabled_by_config(self) -> None:
        config = Config()
        config.rules = {"ZC008": {"enabled": True}}
        issues = issues_of("内存 16GB", "ZC008", config=config)
        self.assertEqual(len(issues), 1)

    def test_fix_inserts_space(self) -> None:
        config = Config()
        config.rules = {"ZC008": {"enabled": True}}
        self.assertEqual(fixed("内存 16GB", config=config), "内存 16 GB")

    def test_unknown_unit_not_flagged(self) -> None:
        config = Config()
        config.rules = {"ZC008": {"enabled": True}}
        self.assertEqual(issues_of("变量 abc1 结束", "ZC008", config=config), [])


class RuleSelectionTest(unittest.TestCase):
    def test_select_limits_rules(self) -> None:
        self.assertEqual(ids("使用Python编写,后续", select=["ZC002"]), ["ZC002"])

    def test_ignore_removes_rule(self) -> None:
        self.assertNotIn("ZC001", ids("使用Python编写", ignore=["ZC001"]))

    def test_mode_text_skips_markdown_syntax(self) -> None:
        result = lint("```\n中文abc\n```", mode="text")
        self.assertTrue(any(issue.rule_id == "ZC001" for issue in result.issues))


if __name__ == "__main__":
    unittest.main()
