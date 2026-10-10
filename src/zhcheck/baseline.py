"""基线（baseline）：让存量问题不再阻塞新增代码。

用法：``zhcheck --write-baseline`` 记录当前全部问题，此后仅对"新增"问题报错。
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from pathlib import Path

from .engine import AnalysisResult

BASELINE_VERSION = 1


def fingerprint(rule_id: str, line_text: str) -> str:
    payload = "%s|%s" % (rule_id, line_text.strip())
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]


def build(results: Sequence[AnalysisResult]) -> dict[str, object]:
    files: dict[str, dict[str, int]] = {}
    for result in results:
        if not result.issues:
            continue
        bucket = files.setdefault(result.relpath, {})
        for issue in result.issues:
            key = fingerprint(issue.rule_id, result.index.line_text(issue.line))
            bucket[key] = bucket.get(key, 0) + 1
    return {
        "version": BASELINE_VERSION,
        "files": {name: files[name] for name in sorted(files)},
    }


def load(path: str) -> dict[str, object]:
    file_path = Path(path)
    if not file_path.is_file():
        return {"version": BASELINE_VERSION, "files": {}}
    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"version": BASELINE_VERSION, "files": {}}
    if not isinstance(data, dict) or not isinstance(data.get("files"), dict):
        return {"version": BASELINE_VERSION, "files": {}}
    return data


def save(path: str, data: dict[str, object]) -> None:
    file_path = Path(path)
    file_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def suppress(results: Sequence[AnalysisResult], baseline: dict[str, object]) -> int:
    """就地过滤掉基线中已有的问题，返回被抑制的数量。"""
    files: dict[str, dict[str, int]] = baseline.get("files", {})  # type: ignore[assignment]
    suppressed = 0
    for result in results:
        bucket = files.get(result.relpath)
        if not bucket:
            continue
        remaining: list = []
        for issue in result.issues:
            key = fingerprint(issue.rule_id, result.index.line_text(issue.line))
            count = bucket.get(key, 0)
            if count > 0:
                bucket[key] = count - 1
                suppressed += 1
                continue
            remaining.append(issue)
        result.issues = remaining
        result.suppressed = suppressed
    return suppressed
