"""基线（baseline）机制测试。"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from helpers import lint, temporary_directory
from zhcheck import baseline as baseline_mod


class FingerprintTest(unittest.TestCase):
    def test_same_rule_and_line_gives_same_fingerprint(self) -> None:
        self.assertEqual(
            baseline_mod.fingerprint("ZC001", "使用Python"),
            baseline_mod.fingerprint("ZC001", "  使用Python  "),
        )

    def test_different_rule_gives_different_fingerprint(self) -> None:
        self.assertNotEqual(
            baseline_mod.fingerprint("ZC001", "使用Python"),
            baseline_mod.fingerprint("ZC002", "使用Python"),
        )

    def test_different_line_gives_different_fingerprint(self) -> None:
        self.assertNotEqual(
            baseline_mod.fingerprint("ZC001", "使用Python"),
            baseline_mod.fingerprint("ZC001", "使用Ruby"),
        )


class BaselineRoundTripTest(unittest.TestCase):
    def test_build_and_suppress(self) -> None:
        results = [lint("使用Python编写", path="a.md")]
        data = baseline_mod.build(results)
        self.assertEqual(data["version"], baseline_mod.BASELINE_VERSION)
        self.assertIn("a.md", data["files"])

        fresh = [lint("使用Python编写", path="a.md")]
        suppressed = baseline_mod.suppress(fresh, data)
        self.assertEqual(suppressed, 2)
        self.assertEqual(fresh[0].issues, [])

    def test_new_issue_is_not_suppressed(self) -> None:
        data = baseline_mod.build([lint("使用Python编写", path="a.md")])
        fresh = [lint("使用Python编写\n新增中文Ruby问题", path="a.md")]
        baseline_mod.suppress(fresh, data)
        self.assertEqual([issue.rule_id for issue in fresh[0].issues], ["ZC001", "ZC001"])

    def test_counts_are_consumed(self) -> None:
        data = baseline_mod.build([lint("使用Python编写", path="a.md")])
        first = [lint("使用Python编写", path="a.md")]
        baseline_mod.suppress(first, data)
        # 同一份基线第二次使用时不生效（计数已被消耗）
        second = [lint("使用Python编写", path="a.md")]
        self.assertEqual(baseline_mod.suppress(second, data), 0)

    def test_save_and_load(self) -> None:
        with temporary_directory() as tmp:
            path = tmp / "bl.json"
            baseline_mod.save(str(path), baseline_mod.build([lint("使用Python", path="a.md")]))
            self.assertTrue(path.is_file())
            loaded = baseline_mod.load(str(path))
            self.assertIn("a.md", loaded["files"])

    def test_load_missing_file_returns_empty(self) -> None:
        loaded = baseline_mod.load("definitely/not/here.json")
        self.assertEqual(loaded["files"], {})

    def test_load_broken_file_returns_empty(self) -> None:
        with temporary_directory() as tmp:
            path = tmp / "bl.json"
            path.write_text("{broken", encoding="utf-8")
            self.assertEqual(baseline_mod.load(str(path))["files"], {})

    def test_baseline_json_is_sorted(self) -> None:
        with temporary_directory() as tmp:
            path = tmp / "bl.json"
            baseline_mod.save(
                str(path),
                baseline_mod.build([lint("使用Python", path="b.md"), lint("使用Ruby", path="a.md")]),
            )
            payload = json.loads(Path(path).read_text(encoding="utf-8"))
            self.assertEqual(list(payload["files"]), ["a.md", "b.md"])


if __name__ == "__main__":
    unittest.main()
