"""命令行端到端测试。"""

from __future__ import annotations

import json
import unittest

from helpers import run_cli, temporary_directory, working_directory

BAD = "使用Python编写,注意:你的帐号\n"
FIXED = "使用 Python 编写，注意：你的账号\n"


class InfoCommandsTest(unittest.TestCase):
    def test_version(self) -> None:
        code, out, _ = run_cli(["--version"])
        self.assertEqual(code, 0)
        self.assertIn("zhcheck", out)

    def test_list_rules(self) -> None:
        code, out, _ = run_cli(["--list-rules"])
        self.assertEqual(code, 0)
        self.assertIn("ZC001", out)
        self.assertIn("ZC012", out)

    def test_init_creates_config(self) -> None:
        with temporary_directory() as tmp, working_directory(tmp):
            code, out, _ = run_cli(["--init"])
            self.assertEqual(code, 0)
            target = tmp / ".zhcheckrc.json"
            self.assertTrue(target.is_file())
            json.loads(target.read_text(encoding="utf-8"))
            code, _, err = run_cli(["--init"])
            self.assertEqual(code, 2)
            self.assertIn("已存在", err)


class LintTest(unittest.TestCase):
    def test_reports_issues_and_exits_one(self) -> None:
        with temporary_directory() as tmp, working_directory(tmp):
            (tmp / "a.md").write_text(BAD, encoding="utf-8")
            code, out, _ = run_cli(["a.md", "--no-color"])
            self.assertEqual(code, 1)
            self.assertIn("ZC001", out)
            self.assertIn("ZC009", out)

    def test_clean_file_exits_zero(self) -> None:
        with temporary_directory() as tmp, working_directory(tmp):
            (tmp / "a.md").write_text(FIXED, encoding="utf-8")
            code, out, _ = run_cli(["a.md", "--no-color"])
            self.assertEqual(code, 0)
            self.assertIn("未发现问题", out)

    def test_fail_on_none_always_exits_zero(self) -> None:
        with temporary_directory() as tmp, working_directory(tmp):
            (tmp / "a.md").write_text(BAD, encoding="utf-8")
            code, _, _ = run_cli(["a.md", "--fail-on", "none"])
            self.assertEqual(code, 0)

    def test_fail_on_warning(self) -> None:
        with temporary_directory() as tmp, working_directory(tmp):
            (tmp / "a.md").write_text("使用 github 托管\n", encoding="utf-8")
            self.assertEqual(run_cli(["a.md"])[0], 0)
            self.assertEqual(run_cli(["a.md", "--fail-on", "warning"])[0], 1)

    def test_quiet_mode_only_prints_summary(self) -> None:
        with temporary_directory() as tmp, working_directory(tmp):
            (tmp / "a.md").write_text(BAD, encoding="utf-8")
            code, out, _ = run_cli(["a.md", "--quiet"])
            self.assertEqual(code, 1)
            self.assertEqual(len(out.strip().splitlines()), 1)

    def test_json_format(self) -> None:
        with temporary_directory() as tmp, working_directory(tmp):
            (tmp / "a.md").write_text(BAD, encoding="utf-8")
            code, out, _ = run_cli(["a.md", "--format", "json"])
            payload = json.loads(out)
            self.assertEqual(code, 1)
            self.assertEqual(payload["version"], 1)
            self.assertGreater(payload["summary"]["total"], 0)
            self.assertEqual(payload["files"][0]["path"], "a.md")

    def test_github_format(self) -> None:
        with temporary_directory() as tmp, working_directory(tmp):
            (tmp / "a.md").write_text(BAD, encoding="utf-8")
            _, out, _ = run_cli(["a.md", "--format", "github"])
            self.assertTrue(out.startswith("::error file=a.md,line=1,col="))

    def test_missing_path_warns_without_failing(self) -> None:
        with temporary_directory() as tmp, working_directory(tmp):
            code, _, err = run_cli(["nope.md"])
            self.assertEqual(code, 0)
            self.assertIn("路径不存在", err)

    def test_directory_traversal_skips_excluded(self) -> None:
        with temporary_directory() as tmp, working_directory(tmp):
            (tmp / "docs").mkdir()
            (tmp / "docs" / "a.md").write_text(BAD, encoding="utf-8")
            (tmp / "node_modules").mkdir()
            (tmp / "node_modules" / "b.md").write_text(BAD, encoding="utf-8")
            _, out, _ = run_cli([".", "--format", "json"])
            paths = [item["path"] for item in json.loads(out)["files"]]
            self.assertEqual(paths, ["docs/a.md"])

    def test_explicit_file_bypasses_include_filter(self) -> None:
        with temporary_directory() as tmp, working_directory(tmp):
            (tmp / "a.rst").write_text(BAD, encoding="utf-8")
            self.assertEqual(run_cli(["."])[0], 0)
            self.assertEqual(run_cli(["a.rst"])[0], 1)

    def test_encoding_detection_for_gbk(self) -> None:
        with temporary_directory() as tmp, working_directory(tmp):
            (tmp / "a.md").write_bytes(BAD.encode("gbk"))
            code, out, _ = run_cli(["a.md", "--no-color"])
            self.assertEqual(code, 1)
            self.assertIn("ZC009", out)

    def test_bom_is_preserved_on_fix(self) -> None:
        with temporary_directory() as tmp, working_directory(tmp):
            (tmp / "a.md").write_bytes(b"\xef\xbb\xbf" + BAD.encode("utf-8"))
            self.assertEqual(run_cli(["a.md", "--fix"])[0], 0)
            raw = (tmp / "a.md").read_bytes()
            self.assertTrue(raw.startswith(b"\xef\xbb\xbf"))
            self.assertEqual(raw.decode("utf-8-sig"), FIXED)

    def test_crlf_is_preserved_on_fix(self) -> None:
        with temporary_directory() as tmp, working_directory(tmp):
            (tmp / "a.md").write_bytes(BAD.replace("\n", "\r\n").encode("utf-8"))
            self.assertEqual(run_cli(["a.md", "--fix"])[0], 0)
            raw = (tmp / "a.md").read_bytes()
            self.assertNotIn(b"\n\n", raw)
            self.assertEqual(raw.decode("utf-8"), FIXED.replace("\n", "\r\n"))


class FixTest(unittest.TestCase):
    def test_fix_writes_file(self) -> None:
        with temporary_directory() as tmp, working_directory(tmp):
            (tmp / "a.md").write_text(BAD, encoding="utf-8")
            code, out, _ = run_cli(["a.md", "--fix", "--no-color"])
            self.assertEqual(code, 0)
            self.assertIn("已修改", out)
            self.assertEqual((tmp / "a.md").read_text(encoding="utf-8"), FIXED)

    def test_dry_run_does_not_write(self) -> None:
        with temporary_directory() as tmp, working_directory(tmp):
            (tmp / "a.md").write_text(BAD, encoding="utf-8")
            code, out, _ = run_cli(["a.md", "--fix", "--dry-run"])
            self.assertEqual(code, 0)
            self.assertIn("[dry-run]", out)
            self.assertEqual((tmp / "a.md").read_text(encoding="utf-8"), BAD)

    def test_fix_reports_remaining_issues(self) -> None:
        with temporary_directory() as tmp, working_directory(tmp):
            # 帐号 已在禁用词表中被移除的场景：这里用指令禁用 ZC009，修复后仍应无残留
            (tmp / "a.md").write_text("<!-- zhcheck-disable ZC009 -->\n" + BAD, encoding="utf-8")
            code, out, _ = run_cli(["a.md", "--fix", "--no-color"])
            self.assertEqual(code, 0)
            self.assertIn("未发现问题", out)


class StdinTest(unittest.TestCase):
    def test_reads_stdin(self) -> None:
        code, out, _ = run_cli(["-", "--no-color"], stdin=BAD.encode("utf-8"))
        self.assertEqual(code, 1)
        self.assertIn("ZC001", out)

    def test_stdin_with_fix_prints_fixed_text(self) -> None:
        code, out, _ = run_cli(["-", "--fix"], stdin=BAD.encode("utf-8"))
        self.assertEqual(code, 0)
        self.assertEqual(out, FIXED)

    def test_stdin_filename_controls_mode(self) -> None:
        payload = "```\n中文abc\n```\n".encode()
        code, out, _ = run_cli(["-", "--stdin-filename", "a.txt", "--no-color"], stdin=payload)
        self.assertEqual(code, 1)
        self.assertIn("ZC001", out)


class BaselineCliTest(unittest.TestCase):
    def test_write_then_suppress(self) -> None:
        with temporary_directory() as tmp, working_directory(tmp):
            (tmp / "a.md").write_text(BAD, encoding="utf-8")
            code, out, _ = run_cli(["a.md", "--write-baseline"])
            self.assertEqual(code, 0)
            self.assertIn("已写入基线", out)
            self.assertTrue((tmp / ".zhcheck-baseline.json").is_file())

            code, out, _ = run_cli(["a.md", "--no-color"])
            self.assertEqual(code, 0)
            self.assertIn("未发现问题", out)

            (tmp / "a.md").write_text(BAD + "新增中文Ruby问题\n", encoding="utf-8")
            code, out, _ = run_cli(["a.md", "--no-color"])
            self.assertEqual(code, 1)
            self.assertIn("新增中文Ruby问题", out)

    def test_no_baseline_flag(self) -> None:
        with temporary_directory() as tmp, working_directory(tmp):
            (tmp / "a.md").write_text(BAD, encoding="utf-8")
            run_cli(["a.md", "--write-baseline"])
            code, _, _ = run_cli(["a.md", "--no-baseline"])
            self.assertEqual(code, 1)


class ErrorHandlingTest(unittest.TestCase):
    def test_unknown_rule_in_select(self) -> None:
        with temporary_directory() as tmp, working_directory(tmp):
            (tmp / "a.md").write_text(BAD, encoding="utf-8")
            code, _, err = run_cli(["a.md", "--select", "ZC999"])
            self.assertEqual(code, 2)
            self.assertIn("未知规则", err)

    def test_broken_config(self) -> None:
        with temporary_directory() as tmp, working_directory(tmp):
            (tmp / "a.md").write_text(BAD, encoding="utf-8")
            (tmp / ".zhcheckrc.json").write_text('{"fail_on": "nope"}', encoding="utf-8")
            code, _, err = run_cli(["a.md"])
            self.assertEqual(code, 2)
            self.assertIn("配置错误", err)

    def test_config_rule_toggle_is_applied(self) -> None:
        with temporary_directory() as tmp, working_directory(tmp):
            (tmp / "a.md").write_text(BAD, encoding="utf-8")
            (tmp / ".zhcheckrc.json").write_text(
                json.dumps({"rules": {"ZC001": False, "ZC009": False}}), encoding="utf-8"
            )
            _, out, _ = run_cli(["a.md", "--format", "json"])
            rules = {issue["rule"] for item in json.loads(out)["files"] for issue in item["issues"]}
            self.assertNotIn("ZC001", rules)
            self.assertNotIn("ZC009", rules)

    def test_select_flag_overrides_config(self) -> None:
        with temporary_directory() as tmp, working_directory(tmp):
            (tmp / "a.md").write_text(BAD, encoding="utf-8")
            (tmp / ".zhcheckrc.json").write_text(
                json.dumps({"rules": {"ZC001": False}}), encoding="utf-8"
            )
            _, out, _ = run_cli(["a.md", "--select", "ZC001", "--format", "json"])
            rules = {issue["rule"] for item in json.loads(out)["files"] for issue in item["issues"]}
            self.assertEqual(rules, {"ZC001"})


if __name__ == "__main__":
    unittest.main()
