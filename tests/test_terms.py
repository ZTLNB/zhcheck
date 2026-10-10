"""词表类规则测试。"""

from __future__ import annotations

import unittest

from helpers import fixed, issues_of, lint
from zhcheck.config import Config


class ConfusablesTest(unittest.TestCase):
    def test_flags_known_wrong_word(self) -> None:
        issues = issues_of("请检查你的帐号", "ZC009")
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].severity, "error")

    def test_fix_replaces_with_correct_word(self) -> None:
        self.assertEqual(fixed("请检查你的帐号"), "请检查你的账号")

    def test_note_is_attached(self) -> None:
        issues = issues_of("请检查你的帐号", "ZC009")
        self.assertTrue(issues[0].note)

    def test_warning_level_entry(self) -> None:
        issues = issues_of("其它选项", "ZC009")
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].severity, "warning")

    def test_ignores_correct_word(self) -> None:
        self.assertEqual(issues_of("请检查你的账号", "ZC009"), [])

    def test_ignores_code_span(self) -> None:
        self.assertEqual(issues_of("字段名 `帐号` 保持不变", "ZC009"), [])

    def test_custom_confusable_from_config(self) -> None:
        config = Config()
        config.confusables = {"登陆系统": "登录系统"}
        issues = issues_of("请先登陆系统", "ZC009", config=config)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].fixes[0].replacement, "登录系统")

    def test_custom_confusable_overrides_default(self) -> None:
        config = Config()
        config.confusables = {"帐号": "账户"}
        issues = issues_of("请检查你的帐号", "ZC009", config=config)
        self.assertEqual(issues[0].fixes[0].replacement, "账户")

    def test_longer_entry_wins(self) -> None:
        config = Config()
        config.confusables = {"帐号问题": "账号问题"}
        issues = issues_of("这是帐号问题", "ZC009", config=config)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].fixes[0].replacement, "账号问题")


class TermsTest(unittest.TestCase):
    def test_flags_lowercase_technology_name(self) -> None:
        issues = issues_of("使用 github 托管", "ZC010")
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].severity, "warning")

    def test_fix_normalises_case(self) -> None:
        self.assertEqual(fixed("使用 github 托管"), "使用 GitHub 托管")

    def test_multiple_terms_in_one_line(self) -> None:
        issues = issues_of("mysql 与 nginx 与 javascript", "ZC010")
        self.assertEqual(len(issues), 3)

    def test_respects_word_boundary(self) -> None:
        # sqlite / a.sql 中的 sql 不应被误报
        self.assertEqual(issues_of("sqlite3 数据库", "ZC010"), [])
        self.assertEqual(issues_of("打开 a.sql 文件", "ZC010"), [])

    def test_hyphen_suffix_still_matches(self) -> None:
        self.assertEqual(fixed("编码 utf-8"), "编码 UTF-8")

    def test_ignores_url(self) -> None:
        self.assertEqual(issues_of("见 https://github.com/x", "ZC010"), [])

    def test_custom_term_from_config(self) -> None:
        config = Config()
        config.terms = {"SpringBoot": "Spring Boot"}
        issues = issues_of("基于 SpringBoot 开发", "ZC010", config=config)
        self.assertEqual(len(issues), 1)

    def test_can_be_disabled(self) -> None:
        result = lint("使用 github 托管", select=["ZC009"])
        self.assertEqual(result.issues, [])


class DataIntegrityTest(unittest.TestCase):
    def test_data_files_are_loadable(self) -> None:
        from zhcheck.rules.terms import DEFAULT_CONFUSABLES, DEFAULT_TERMS

        self.assertGreater(len(DEFAULT_CONFUSABLES), 100)
        self.assertGreater(len(DEFAULT_TERMS), 80)

    def test_no_self_replacement(self) -> None:
        from zhcheck.rules.terms import DEFAULT_CONFUSABLES, DEFAULT_TERMS

        for entry in (*DEFAULT_CONFUSABLES, *DEFAULT_TERMS):
            self.assertNotEqual(
                entry["wrong"], entry["right"], "词表存在自我替换：%s" % entry["wrong"]
            )

    def test_no_duplicate_wrong_forms(self) -> None:
        from zhcheck.rules.terms import DEFAULT_CONFUSABLES, DEFAULT_TERMS

        for entries in (DEFAULT_CONFUSABLES, DEFAULT_TERMS):
            wrongs = [entry["wrong"] for entry in entries]
            self.assertEqual(len(wrongs), len(set(wrongs)), "词表存在重复条目")


if __name__ == "__main__":
    unittest.main()
