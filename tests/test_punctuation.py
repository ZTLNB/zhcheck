"""标点类规则测试。"""

from __future__ import annotations

import unittest

from helpers import fixed, issues_of


class HalfPunctInChineseTest(unittest.TestCase):
    def test_flags_comma_after_chinese(self) -> None:
        self.assertEqual(len(issues_of("中文,后续", "ZC002")), 1)

    def test_fix_uses_fullwidth_and_absorbs_space(self) -> None:
        self.assertEqual(fixed("中文, 后续"), "中文，后续")

    def test_fix_without_space(self) -> None:
        self.assertEqual(fixed("中文,后续"), "中文，后续")

    def test_flags_colon_and_semicolon(self) -> None:
        self.assertEqual(len(issues_of("注意: 这里；不对", "ZC002")), 1)

    def test_ignores_number_thousand_separator(self) -> None:
        self.assertEqual(issues_of("数值 1,000 元", "ZC002"), [])

    def test_ignores_ascii_sentence(self) -> None:
        self.assertEqual(issues_of("Hello, world", "ZC002"), [])

    def test_ignores_code_span(self) -> None:
        self.assertEqual(issues_of("调用 `a, b` 函数", "ZC002"), [])

    def test_severity_is_error(self) -> None:
        self.assertEqual(issues_of("中文,后续", "ZC002")[0].severity, "error")


class FullPunctInEnglishTest(unittest.TestCase):
    def test_flags_fullwidth_comma_between_ascii(self) -> None:
        self.assertEqual(len(issues_of("Node，Python 都不错", "ZC003")), 1)

    def test_fix_uses_halfwidth_with_space(self) -> None:
        self.assertEqual(fixed("Node，Python"), "Node, Python")

    def test_ignores_fullwidth_comma_in_chinese(self) -> None:
        self.assertEqual(issues_of("中文，后续", "ZC003"), [])


class DuplicatePunctTest(unittest.TestCase):
    def test_flags_double_fullwidth_comma(self) -> None:
        self.assertEqual(len(issues_of("中文，，后续", "ZC004")), 1)

    def test_fix_keeps_single(self) -> None:
        self.assertEqual(fixed("中文，，后续"), "中文，后续")

    def test_flags_triple_full_stop(self) -> None:
        issues = issues_of("结束。。。", "ZC004")
        self.assertEqual(issues, [])

    def test_ellipsis_handled_by_zc005(self) -> None:
        self.assertEqual(len(issues_of("结束。。。", "ZC005")), 1)

    def test_ignores_ascii_duplicate_in_english(self) -> None:
        self.assertEqual(issues_of("Hello!!", "ZC004"), [])

    def test_flags_ascii_duplicate_in_chinese(self) -> None:
        self.assertEqual(len(issues_of("中文!! 后续", "ZC004")), 1)


class EllipsisTest(unittest.TestCase):
    def test_flags_three_dots_in_chinese(self) -> None:
        self.assertEqual(len(issues_of("等等...然后", "ZC005")), 1)

    def test_fix_uses_six_dots(self) -> None:
        self.assertEqual(fixed("等等...然后"), "等等……然后")

    def test_flags_three_full_stops(self) -> None:
        self.assertEqual(fixed("等等。。。然后"), "等等……然后")

    def test_ignores_english_ellipsis(self) -> None:
        self.assertEqual(issues_of("wait... then", "ZC005"), [])


class DashTest(unittest.TestCase):
    def test_flags_double_hyphen(self) -> None:
        self.assertEqual(len(issues_of("这是破折号--后面", "ZC006")), 1)

    def test_fix_uses_two_em_dashes(self) -> None:
        self.assertEqual(fixed("这是破折号--后面"), "这是破折号——后面")

    def test_ignores_cli_flag(self) -> None:
        self.assertEqual(issues_of("执行 --help 查看", "ZC006"), [])

    def test_flags_single_em_dash_without_fix(self) -> None:
        issues = issues_of("这是破折号—后面", "ZC006")
        self.assertEqual(len(issues), 1)
        self.assertFalse(issues[0].fixable)

    def test_ignores_markdown_hr(self) -> None:
        self.assertEqual(issues_of("上文\n\n---\n\n下文", "ZC006"), [])


class BracketQuoteTest(unittest.TestCase):
    def test_flags_halfwidth_parens_with_chinese(self) -> None:
        self.assertEqual(len(issues_of("这是(中文)括号", "ZC007")), 1)

    def test_fix_uses_fullwidth_parens(self) -> None:
        self.assertEqual(fixed("这是(中文)括号"), "这是（中文）括号")

    def test_ignores_parens_with_ascii_only(self) -> None:
        self.assertEqual(issues_of("这是(english)括号", "ZC007"), [])

    def test_ignores_markdown_link_destination(self) -> None:
        self.assertEqual(issues_of("见 [链接](https://example.com)", "ZC007"), [])

    def test_flags_halfwidth_quotes_with_chinese(self) -> None:
        self.assertEqual(len(issues_of('这是"中文"引号', "ZC007")), 1)

    def test_fix_uses_chinese_quotes(self) -> None:
        self.assertEqual(fixed('这是"中文"引号'), "这是“中文”引号")

    def test_fix_is_idempotent(self) -> None:
        once = fixed("这是(中文)括号和\"中文\"引号")
        self.assertEqual(fixed(once), once)


class FullwidthAlnumTest(unittest.TestCase):
    def test_flags_fullwidth_letters_and_digits(self) -> None:
        self.assertEqual(len(issues_of("版本 ＡＢＣ１２３ 发布", "ZC012")), 1)

    def test_fix_converts_to_halfwidth(self) -> None:
        self.assertEqual(fixed("版本 ＡＢＣ１２３ 发布"), "版本 ABC123 发布")

    def test_ignores_ascii(self) -> None:
        self.assertEqual(issues_of("版本 ABC123 发布", "ZC012"), [])


class ChineseContextBoundaryTest(unittest.TestCase):
    """中文标点包裹的片段同样属于中文语境，规则不应漏报。"""

    def test_ellipsis_inside_chinese_brackets(self) -> None:
        self.assertEqual(len(issues_of("例如「...」这种写法", "ZC005")), 1)

    def test_dash_inside_chinese_brackets(self) -> None:
        self.assertEqual(len(issues_of("例如「--」这种写法", "ZC006")), 1)

    def test_duplicate_punct_inside_chinese_brackets(self) -> None:
        self.assertEqual(len(issues_of("例如「，，」这种写法", "ZC004")), 1)

    def test_still_ignores_pure_english_context(self) -> None:
        self.assertEqual(issues_of('He said "wait..." loudly', "ZC005"), [])
        self.assertEqual(issues_of('a -- b', "ZC006"), [])


if __name__ == "__main__":
    unittest.main()
