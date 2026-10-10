"""自动修复测试。"""

from __future__ import annotations

import unittest

from helpers import fixed, lint
from zhcheck.fixer import apply_fixes, select_fixes
from zhcheck.issues import Fix, Issue


def make_issue(start: int, end: int, replacement: str, rule_id: str = "ZC001") -> Issue:
    return Issue(
        rule_id=rule_id,
        message="m",
        severity="error",
        line=1,
        column=start + 1,
        start=start,
        end=end,
        fixes=(Fix(start, end, replacement),),
    )


class SelectFixesTest(unittest.TestCase):
    def test_drops_overlapping_fixes(self) -> None:
        issues = [make_issue(0, 3, "A"), make_issue(2, 5, "B")]
        chosen = select_fixes(issues)
        self.assertEqual([fix.replacement for fix in chosen], ["A"])

    def test_keeps_adjacent_fixes(self) -> None:
        issues = [make_issue(0, 2, "A"), make_issue(2, 4, "B")]
        self.assertEqual(len(select_fixes(issues)), 2)

    def test_deduplicates_identical_fixes(self) -> None:
        issues = [make_issue(0, 2, "A", "ZC001"), make_issue(0, 2, "A", "ZC002")]
        self.assertEqual(len(select_fixes(issues)), 1)

    def test_keeps_insertions_at_same_offset(self) -> None:
        issues = [
            Issue("ZC001", "m", "error", 1, 1, 0, 0, fixes=(Fix(0, 0, " "),)),
            Issue("ZC011", "m", "info", 1, 1, 0, 0, fixes=(Fix(0, 0, " "),)),
        ]
        self.assertEqual(len(select_fixes(issues)), 1)

    def test_issue_without_fix_is_skipped(self) -> None:
        issues = [
            Issue("ZC006", "m", "warning", 1, 1, 0, 1, fixes=()),
            make_issue(3, 4, "X"),
        ]
        self.assertEqual(len(select_fixes(issues)), 1)


class ApplyFixesTest(unittest.TestCase):
    def test_applies_from_the_end(self) -> None:
        text = "abcdef"
        fixes = [Fix(0, 1, "X"), Fix(3, 4, "Y")]
        self.assertEqual(apply_fixes(text, fixes), "XbcYef")

    def test_insertion(self) -> None:
        self.assertEqual(apply_fixes("ab", [Fix(1, 1, "-")]), "a-b")

    def test_empty_fix_list(self) -> None:
        self.assertEqual(apply_fixes("abc", []), "abc")


class EndToEndFixTest(unittest.TestCase):
    def test_all_fixable_issues_are_resolved(self) -> None:
        text = "使用Python编写,注意:你的帐号"
        once = fixed(text)
        self.assertEqual(once, "使用 Python 编写，注意：你的账号")
        self.assertEqual(lint(once).issues, [])

    def test_repeated_fix_converges(self) -> None:
        # 一轮修复可能暴露新的可修复问题（全角字母转半角后触发中英混排空格），
        # 因此修复应迭代到收敛而不是只跑一轮。
        text = "破折号--省略号...全角ＡＢ全角引号\"中文\""
        once = fixed(text)
        twice = fixed(once)
        self.assertEqual(fixed(twice), twice)
        self.assertNotEqual(once, twice)

    def test_protected_regions_survive_fix(self) -> None:
        text = "正文中文abc\n\n```\n中文abc\n```\n"
        self.assertEqual(fixed(text), "正文中文 abc\n\n```\n中文abc\n```\n")


if __name__ == "__main__":
    unittest.main()
