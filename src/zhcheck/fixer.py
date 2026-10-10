"""自动修复：挑选互不冲突的替换并应用。"""

from __future__ import annotations

from collections.abc import Sequence

from .issues import Fix, Issue


def select_fixes(issues: Sequence[Issue]) -> list[Fix]:
    """收集所有替换，按位置排序并丢弃互相重叠的部分。"""
    candidates: list[Fix] = []
    seen = set()
    for issue in issues:
        for fix in issue.fixes:
            key = (fix.start, fix.end, fix.replacement)
            if key in seen:
                continue
            seen.add(key)
            candidates.append(fix)

    candidates.sort(key=lambda item: (item.start, item.end))
    chosen: list[Fix] = []
    last_end = -1
    for fix in candidates:
        if fix.start < last_end:
            continue
        chosen.append(fix)
        last_end = max(last_end, fix.end)
    return chosen


def apply_fixes(text: str, fixes: Sequence[Fix]) -> str:
    """从后往前应用替换，避免偏移失效。"""
    for fix in sorted(fixes, key=lambda item: (item.start, item.end), reverse=True):
        text = text[: fix.start] + fix.replacement + text[fix.end :]
    return text
