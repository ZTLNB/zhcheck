"""空格类规则：中英混排、多余空格、数字与单位。"""

from __future__ import annotations

import re

from ..chars import is_han
from ..issues import Fix, Issue
from . import Rule, ScanContext

# 汉字/假名（与 chars.is_han 保持一致，用于正则加速）
_HAN = r"\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff"

_RE_HAN_THEN_ASCII = re.compile(r"([%s])([0-9A-Za-z])" % _HAN)
_RE_ASCII_THEN_HAN = re.compile(r"([0-9A-Za-z])([%s])" % _HAN)
_RE_MULTI_SPACE = re.compile(r" {2,}")
_RE_NUM_UNIT = re.compile(r"(?<![0-9A-Za-z.])(\d+)([A-Za-z]{1,4})(?![0-9A-Za-z])")

# 数字与单位之间加空格的单位白名单（避免把变量名、版本号误判）
UNIT_WHITELIST = frozenset(
    [
        "b", "bit", "kb", "mb", "gb", "tb", "pb", "kib", "mib", "gib", "tib",
        "kg", "g", "mg", "t", "km", "m", "cm", "mm", "nm", "um",
        "ms", "us", "ns", "s", "min", "h", "d",
        "hz", "khz", "mhz", "ghz", "w", "kw", "mw", "v", "mv", "kv", "a", "ma", "mah",
        "fps", "dpi", "ppi", "px", "pt", "em", "rem", "rpm", "db",
        "bps", "kbps", "mbps", "gbps", "kva",
    ]
)

_MSG_SPACE = "中文与英文/数字之间应留一个空格"


def check_mixed_spacing(ctx: ScanContext) -> list[Issue]:
    issues: list[Issue] = []
    for pattern in (_RE_HAN_THEN_ASCII, _RE_ASCII_THEN_HAN):
        for match in pattern.finditer(ctx.text):
            start, end = match.span()
            if not ctx.active(start, end):
                continue
            insert_at = start + 1
            issues.append(
                ctx.emit(
                    "ZC001",
                    start,
                    end,
                    _MSG_SPACE,
                    fixes=[Fix(insert_at, insert_at, " ")],
                )
            )
    return issues


def check_multi_space(ctx: ScanContext) -> list[Issue]:
    issues: list[Issue] = []
    text = ctx.text
    for match in _RE_MULTI_SPACE.finditer(text):
        start, end = match.span()
        if not ctx.active(start, end):
            continue
        left = text[start - 1] if start > 0 else ""
        right = text[end] if end < len(text) else ""
        if not (is_han(left) or is_han(right)):
            continue
        issues.append(
            ctx.emit(
                "ZC011",
                start,
                end,
                "中文语境中连续多个空格，应只保留一个",
                fixes=[Fix(start, end, " ")],
            )
        )
    return issues


def check_number_unit(ctx: ScanContext) -> list[Issue]:
    issues: list[Issue] = []
    for match in _RE_NUM_UNIT.finditer(ctx.text):
        start, end = match.span()
        if not ctx.active(start, end):
            continue
        unit = match.group(2)
        if unit.lower() not in UNIT_WHITELIST:
            continue
        insert_at = match.start(2)
        issues.append(
            ctx.emit(
                "ZC008",
                start,
                end,
                "数字与单位之间应留一个空格（如「16 GB」）",
                fixes=[Fix(insert_at, insert_at, " ")],
            )
        )
    return issues


RULES = (
    Rule(
        id="ZC001",
        name="中英混排空格",
        severity="error",
        category="spacing",
        description="中文与英文/数字相邻时应留一个空格，例如「使用 Python 编写」。",
        check=check_mixed_spacing,
        fixable=True,
        reference="中文文案排版指北 · 空格",
    ),
    Rule(
        id="ZC008",
        name="数字与单位空格",
        severity="info",
        category="spacing",
        description="数字与计量单位之间应留一个空格（如「16 GB」「3 GHz」）。默认关闭。",
        check=check_number_unit,
        fixable=True,
        enabled_by_default=False,
        reference="GB/T 15835 · 量和单位",
    ),
    Rule(
        id="ZC011",
        name="中文语境多余空格",
        severity="info",
        category="spacing",
        description="中文之间出现连续多个空格时应只保留一个。",
        check=check_multi_space,
        fixable=True,
    ),
)
