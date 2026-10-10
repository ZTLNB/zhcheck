"""配置加载、glob 匹配与规则开关测试。"""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest import mock

from helpers import temporary_directory, working_directory
from zhcheck import config as config_module
from zhcheck.config import (
    Config,
    ConfigError,
    build_settings,
    dumps_default_config,
    find_config,
    is_target_file,
    load_config,
    match_any,
    match_glob,
    should_prune_dir,
)


class MatchGlobTest(unittest.TestCase):
    def test_double_star_matches_root_file(self) -> None:
        self.assertTrue(match_glob("**/*.md", "README.md"))

    def test_double_star_matches_nested_file(self) -> None:
        self.assertTrue(match_glob("**/*.md", "docs/guide/intro.md"))

    def test_extension_mismatch(self) -> None:
        self.assertFalse(match_glob("**/*.md", "a.txt"))

    def test_bare_name_matches_anywhere(self) -> None:
        self.assertTrue(match_glob("CHANGELOG.md", "docs/CHANGELOG.md"))
        self.assertTrue(match_glob("CHANGELOG.md", "CHANGELOG.md"))

    def test_directory_prefix(self) -> None:
        self.assertTrue(match_glob("node_modules/**", "node_modules/a/b.md"))
        self.assertFalse(match_glob("node_modules/**", "src/node_modules.md"))

    def test_backslash_path_is_normalised(self) -> None:
        self.assertTrue(match_glob("docs/**/*.md", "docs\\guide\\a.md"))

    def test_match_any(self) -> None:
        patterns = ["**/*.md", "**/*.txt"]
        self.assertTrue(match_any(patterns, "a.txt"))
        self.assertFalse(match_any(patterns, "a.py"))


class PruneAndFilterTest(unittest.TestCase):
    def test_prune_known_directories(self) -> None:
        exclude = [".git/**", "node_modules/**", "**/.venv/**"]
        self.assertTrue(should_prune_dir("node_modules", exclude))
        self.assertTrue(should_prune_dir(".git", exclude))
        self.assertTrue(should_prune_dir("pkg/.venv", exclude))
        self.assertFalse(should_prune_dir("src", exclude))

    def test_is_target_file(self) -> None:
        config = Config()
        self.assertTrue(is_target_file("README.md", config))
        self.assertFalse(is_target_file("main.py", config))
        self.assertFalse(is_target_file("node_modules/a.md", config))


class LoadConfigTest(unittest.TestCase):
    def test_missing_config_uses_defaults(self) -> None:
        with temporary_directory() as tmp, working_directory(tmp):
            config = load_config(None, start=tmp)
            self.assertEqual(config.fail_on, "error")
            self.assertEqual(config.mode, "auto")
            self.assertIn("**/*.md", config.include)

    def test_reads_json_config(self) -> None:
        with temporary_directory() as tmp:
            (tmp / ".zhcheckrc.json").write_text(
                json.dumps(
                    {
                        "fail_on": "warning",
                        "mode": "text",
                        "rules": {"ZC001": {"enabled": False, "severity": "info"}},
                        "disabled_rules": ["ZC012"],
                        "confusables": {"登陆": "登录"},
                        "terms": {"SpringBoot": "Spring Boot"},
                        "exceptions": ["v\\d+"],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            config = load_config(None, start=tmp)
            self.assertEqual(config.fail_on, "warning")
            self.assertEqual(config.mode, "text")
            self.assertFalse(config.rules["ZC001"]["enabled"])
            self.assertEqual(config.disabled_rules, ["ZC012"])
            self.assertEqual(config.confusables, {"登陆": "登录"})
            self.assertEqual(config.terms, {"SpringBoot": "Spring Boot"})
            self.assertEqual(config.exceptions, ["v\\d+"])

    def test_finds_config_in_parent_directory(self) -> None:
        with temporary_directory() as tmp:
            (tmp / ".zhcheckrc.json").write_text('{"fail_on": "info"}', encoding="utf-8")
            nested = tmp / "a" / "b"
            nested.mkdir(parents=True)
            config = load_config(None, start=nested)
            self.assertEqual(config.fail_on, "info")
            self.assertEqual(Path(config.config_dir), tmp.resolve())

    def test_explicit_config_path(self) -> None:
        with temporary_directory() as tmp:
            path = tmp / "custom.json"
            path.write_text('{"mode": "markdown"}', encoding="utf-8")
            config = load_config(str(path))
            self.assertEqual(config.mode, "markdown")

    def test_unknown_field_raises(self) -> None:
        with temporary_directory() as tmp:
            path = tmp / ".zhcheckrc.json"
            path.write_text('{"unknown": 1}', encoding="utf-8")
            with self.assertRaises(ConfigError):
                load_config(str(path))

    def test_unknown_rule_raises(self) -> None:
        with temporary_directory() as tmp:
            path = tmp / ".zhcheckrc.json"
            path.write_text('{"rules": {"ZC999": {"enabled": true}}}', encoding="utf-8")
            with self.assertRaises(ConfigError):
                load_config(str(path))

    def test_invalid_severity_raises(self) -> None:
        with temporary_directory() as tmp:
            path = tmp / ".zhcheckrc.json"
            path.write_text('{"rules": {"ZC001": {"severity": "fatal"}}}', encoding="utf-8")
            with self.assertRaises(ConfigError):
                load_config(str(path))

    def test_invalid_fail_on_raises(self) -> None:
        with temporary_directory() as tmp:
            path = tmp / ".zhcheckrc.json"
            path.write_text('{"fail_on": "maybe"}', encoding="utf-8")
            with self.assertRaises(ConfigError):
                load_config(str(path))

    def test_broken_json_raises(self) -> None:
        with temporary_directory() as tmp:
            path = tmp / ".zhcheckrc.json"
            path.write_text("{not json", encoding="utf-8")
            with self.assertRaises(ConfigError):
                load_config(str(path))

    def test_missing_explicit_path_raises(self) -> None:
        with self.assertRaises(ConfigError):
            load_config("no/such/file.json")

    def test_default_config_template_is_valid_json(self) -> None:
        payload = json.loads(dumps_default_config())
        self.assertIn("include", payload)
        self.assertIn("rules", payload)


class PyprojectConfigTest(unittest.TestCase):
    """pyproject.toml 配置：3.11 起用标准库 tomllib，3.9/3.10 需要 tomli。"""

    def test_reads_tool_section(self) -> None:
        with temporary_directory() as tmp:
            (tmp / "pyproject.toml").write_text(
                '[tool.zhcheck]\nmode = "markdown"\nfail_on = "warning"\n'
                'disabled_rules = ["ZC012"]\n',
                encoding="utf-8",
            )
            config = load_config(None, start=tmp)
            self.assertEqual(config.mode, "markdown")
            self.assertEqual(config.fail_on, "warning")
            self.assertEqual(config.disabled_rules, ["ZC012"])
            self.assertEqual(config.warnings, [])

    def test_find_config_returns_pyproject_with_section(self) -> None:
        with temporary_directory() as tmp:
            (tmp / "pyproject.toml").write_text('[tool.zhcheck]\nmode = "text"\n', encoding="utf-8")
            found = find_config(tmp)
            self.assertIsNotNone(found)
            self.assertEqual(found.name, "pyproject.toml")
            self.assertEqual(found.parent.resolve(), tmp.resolve())

    def test_pyproject_without_section_is_ignored(self) -> None:
        with temporary_directory() as tmp:
            (tmp / "pyproject.toml").write_text('[project]\nname = "demo"\n', encoding="utf-8")
            self.assertIsNone(find_config(tmp))

    def test_json_config_takes_precedence_over_pyproject(self) -> None:
        with temporary_directory() as tmp:
            (tmp / "pyproject.toml").write_text('[tool.zhcheck]\nmode = "text"\n', encoding="utf-8")
            (tmp / ".zhcheckrc.json").write_text('{"mode": "markdown"}', encoding="utf-8")
            self.assertEqual(load_config(None, start=tmp).mode, "markdown")

    def test_warns_instead_of_silently_ignoring_without_toml_parser(self) -> None:
        with temporary_directory() as tmp:
            (tmp / "pyproject.toml").write_text(
                '[tool.zhcheck]\nmode = "text"\n', encoding="utf-8"
            )
            with mock.patch.object(config_module, "TOML_MODULE", None):
                config = load_config(None, start=tmp)
            # 配置未生效，但必须给出可操作的提示，而不是静默忽略
            self.assertEqual(config.mode, "auto")
            self.assertEqual(len(config.warnings), 1)
            self.assertIn("tomllib", config.warnings[0])
            self.assertIn(".zhcheckrc.json", config.warnings[0])

    def test_explicit_pyproject_without_parser_raises_helpful_error(self) -> None:
        with temporary_directory() as tmp:
            path = tmp / "pyproject.toml"
            path.write_text('[tool.zhcheck]\nmode = "text"\n', encoding="utf-8")
            with mock.patch.object(config_module, "TOML_MODULE", None), self.assertRaises(
                ConfigError
            ) as caught:
                load_config(str(path))
            self.assertIn("tomllib", str(caught.exception))

    def test_explicit_pyproject_without_section_raises(self) -> None:
        with temporary_directory() as tmp:
            path = tmp / "pyproject.toml"
            path.write_text('[project]\nname = "demo"\n', encoding="utf-8")
            with self.assertRaises(ConfigError):
                load_config(str(path))

    def test_mentions_tool_zhcheck_is_textual_probe(self) -> None:
        with temporary_directory() as tmp:
            path = tmp / "pyproject.toml"
            path.write_text('[tool.zhcheck]\nmode = "text"\n', encoding="utf-8")
            self.assertTrue(config_module._mentions_tool_zhcheck(path))
            path.write_text('[tool.other]\nmode = "text"\n', encoding="utf-8")
            self.assertFalse(config_module._mentions_tool_zhcheck(path))


class BuildSettingsTest(unittest.TestCase):
    def test_defaults_follow_rule_flags(self) -> None:
        settings = build_settings(Config())
        self.assertTrue(settings.is_enabled("ZC001"))
        self.assertFalse(settings.is_enabled("ZC008"))

    def test_disabled_rules(self) -> None:
        config = Config(disabled_rules=["ZC001"])
        self.assertFalse(build_settings(config).is_enabled("ZC001"))

    def test_severity_override(self) -> None:
        config = Config(rules={"ZC001": {"severity": "info"}})
        self.assertEqual(build_settings(config).severity_of("ZC001", "error"), "info")

    def test_select_restricts_to_listed_rules(self) -> None:
        settings = build_settings(Config(), select=["ZC001,ZC002"])
        self.assertTrue(settings.is_enabled("ZC001"))
        self.assertTrue(settings.is_enabled("ZC002"))
        self.assertFalse(settings.is_enabled("ZC009"))

    def test_ignore_disables_rule(self) -> None:
        settings = build_settings(Config(), ignore=["ZC001"])
        self.assertFalse(settings.is_enabled("ZC001"))

    def test_unknown_rule_in_selection_raises(self) -> None:
        with self.assertRaises(ConfigError):
            build_settings(Config(), select=["ZC999"])

    def test_lowercase_rule_id_is_accepted(self) -> None:
        settings = build_settings(Config(), select=["zc001"])
        self.assertTrue(settings.is_enabled("ZC001"))


if __name__ == "__main__":
    unittest.main()
