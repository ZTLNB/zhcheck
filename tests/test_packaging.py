"""工程一致性自查。

这些用例不测试功能，而是防止"改了代码忘了改文档"这类漂移：
规则表、版本号、许可证、打包元数据、pre-commit 声明必须彼此对得上。
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

import zhcheck
from zhcheck.rules import rule_ids

ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = ROOT / "pyproject.toml"
README = ROOT / "README.md"
CHANGELOG = ROOT / "CHANGELOG.md"
PRE_COMMIT = ROOT / ".pre-commit-hooks.yaml"
LICENSE = ROOT / "LICENSE"

RULE_TABLE_ROW = re.compile(r"^\|\s*(ZC\d{3})\s*\|", re.MULTILINE)
PYPROJECT_VERSION = re.compile(r'^version = "([^"]+)"', re.MULTILINE)


class MetadataTest(unittest.TestCase):
    def setUp(self) -> None:
        self.pyproject = PYPROJECT.read_text(encoding="utf-8")

    def test_version_matches_pyproject(self) -> None:
        match = PYPROJECT_VERSION.search(self.pyproject)
        self.assertIsNotNone(match, "pyproject.toml 中未找到 version 字段")
        self.assertEqual(zhcheck.__version__, match.group(1))

    def test_console_script_is_declared(self) -> None:
        self.assertIn('zhcheck = "zhcheck.cli:main"', self.pyproject)

    def test_runtime_has_no_dependencies(self) -> None:
        match = re.search(r"^dependencies = \[\]$", self.pyproject, re.MULTILINE)
        self.assertIsNotNone(match, "运行时依赖必须为空，零依赖是本项目的核心取向")

    def test_package_data_declares_json_tables(self) -> None:
        self.assertIn('zhcheck = ["data/*.json"]', self.pyproject)

    def test_license_is_mit(self) -> None:
        self.assertIn('license = "MIT"', self.pyproject)
        self.assertIn("MIT License", LICENSE.read_text(encoding="utf-8"))

    def test_python_requirement_is_declared(self) -> None:
        self.assertIn('requires-python = ">=3.9"', self.pyproject)


class DocumentationSyncTest(unittest.TestCase):
    def test_readme_rule_table_covers_every_registered_rule(self) -> None:
        documented = sorted(RULE_TABLE_ROW.findall(README.read_text(encoding="utf-8")))
        self.assertEqual(
            documented,
            sorted(rule_ids()),
            "README 的规则表与实际注册的规则不一致，新增规则后需同步文档",
        )

    def test_readme_rule_table_has_no_duplicates(self) -> None:
        documented = RULE_TABLE_ROW.findall(README.read_text(encoding="utf-8"))
        self.assertEqual(len(documented), len(set(documented)))

    def test_readme_rule_count_matches_registry(self) -> None:
        match = re.search(r"\*\*(\d+) 条内置规则\*\*", README.read_text(encoding="utf-8"))
        self.assertIsNotNone(match, "README 未声明内置规则数量")
        self.assertEqual(int(match.group(1)), len(rule_ids()))

    def test_changelog_mentions_current_version(self) -> None:
        text = CHANGELOG.read_text(encoding="utf-8")
        self.assertIn("[%s]" % zhcheck.__version__, text)

    def test_pre_commit_hooks_are_declared(self) -> None:
        text = PRE_COMMIT.read_text(encoding="utf-8")
        self.assertIn("- id: zhcheck", text)
        self.assertIn("- id: zhcheck-fix", text)
        self.assertIn("language: python", text)

    def test_readme_documents_pre_commit_usage(self) -> None:
        self.assertIn(".pre-commit-config.yaml", README.read_text(encoding="utf-8"))


class DataIntegrityTest(unittest.TestCase):
    def test_rule_ids_are_sequential_without_gaps(self) -> None:
        numbers = [int(rid[2:]) for rid in rule_ids()]
        self.assertEqual(numbers, list(range(1, len(numbers) + 1)))

    def test_data_files_are_valid_json(self) -> None:
        data_dir = ROOT / "src" / "zhcheck" / "data"
        files = sorted(data_dir.glob("*.json"))
        self.assertGreaterEqual(len(files), 2)
        for path in files:
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertIn("entries", payload, "%s 缺少 entries 字段" % path.name)
            self.assertTrue(payload["entries"], "%s 的 entries 为空" % path.name)


if __name__ == "__main__":
    unittest.main()
