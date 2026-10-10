"""词表类规则：易混词/错别字、术语规范写法。

规则本身不含词表——词表以 JSON 数据文件维护（``src/zhcheck/data/``），
因此新增词条只需提交一行数据，不必改动任何 Python 代码。
"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from ..issues import Fix, Issue
from . import Rule, ScanContext

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# 词边界：不允许匹配到更长的 ASCII 标识符内部（如 sqlite 中的 sql、a.sql）
_BOUNDARY_LEFT = r"(?<![A-Za-z0-9_.])"
_BOUNDARY_RIGHT = r"(?![A-Za-z0-9_.])"


def _load(name: str) -> list[dict[str, Any]]:
    path = _DATA_DIR / name
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):  # pragma: no cover - 数据文件损坏时优雅降级
        return []
    entries = data.get("entries", [])
    return [entry for entry in entries if entry.get("wrong") and entry.get("right")]


DEFAULT_CONFUSABLES: tuple[dict[str, Any], ...] = tuple(_load("confusables.json"))
DEFAULT_TERMS: tuple[dict[str, Any], ...] = tuple(_load("terms.json"))

_CACHE: dict[tuple[Any, ...], tuple[Any, dict[str, dict[str, Any]]]] = {}


def _compile(entries: Sequence[dict[str, Any]]):
    """把词表编译成一个合并正则，避免逐词扫描全文。"""
    wrongs = sorted({entry["wrong"] for entry in entries}, key=len, reverse=True)
    if not wrongs:
        return None, {}
    pattern = re.compile(
        _BOUNDARY_LEFT + "(?:" + "|".join(re.escape(w) for w in wrongs) + ")" + _BOUNDARY_RIGHT
    )
    lookup: dict[str, dict[str, Any]] = {}
    for entry in entries:
        lookup[entry["wrong"]] = entry
    return pattern, lookup


def _get_compiled(entries: Sequence[dict[str, Any]]):
    key = tuple((entry["wrong"], entry["right"]) for entry in entries)
    cached = _CACHE.get(key)
    if cached is None:
        cached = _compile(entries)
        _CACHE[key] = cached
    return cached


def _merge(
    defaults: Sequence[dict[str, Any]],
    extras: dict[str, str],
    severity: str,
    note: str,
) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = [dict(entry) for entry in defaults]
    for wrong, right in extras.items():
        merged.append({"wrong": wrong, "right": right, "severity": severity, "note": note})
    return merged


def _run(
    ctx: ScanContext,
    entries: Sequence[dict[str, Any]],
    rule_id: str,
    default_severity: str,
    message: str,
) -> list[Issue]:
    pattern, lookup = _get_compiled(entries)
    if pattern is None:
        return []
    issues: list[Issue] = []
    for match in pattern.finditer(ctx.text):
        start, end = match.span()
        if not ctx.active(start, end):
            continue
        entry = lookup.get(match.group(0))
        if entry is None:
            continue
        right = entry["right"]
        note = entry.get("note", "")
        text = message.format(wrong=match.group(0), right=right)
        issues.append(
            ctx.emit(
                rule_id,
                start,
                end,
                text,
                fixes=[Fix(start, end, right)],
                severity=entry.get("severity", default_severity),
                note=note,
            )
        )
    return issues


def check_confusables(ctx: ScanContext) -> list[Issue]:
    entries = _merge(
        DEFAULT_CONFUSABLES,
        ctx.extra_confusables,
        "error",
        "来自配置文件的自定义易混词",
    )
    return _run(ctx, entries, "ZC009", "error", "疑似误用「{wrong}」，规范写法为「{right}」")


def check_terms(ctx: ScanContext) -> list[Issue]:
    entries = _merge(
        DEFAULT_TERMS,
        ctx.extra_terms,
        "warning",
        "来自配置文件的自定义术语",
    )
    return _run(ctx, entries, "ZC010", "warning", "术语「{wrong}」的规范写法为「{right}」")


RULES = (
    Rule(
        id="ZC009",
        name="易混词与错别字",
        severity="error",
        category="terms",
        description="命中内置易混词表（帐号/账号、按装/安装 等），可配置扩展。",
        check=check_confusables,
        fixable=True,
        reference="data/confusables.json",
    ),
    Rule(
        id="ZC010",
        name="术语规范写法",
        severity="warning",
        category="terms",
        description="技术术语的大小写与写法统一（Github/GitHub、mysql/MySQL 等）。",
        check=check_terms,
        fixable=True,
        reference="data/terms.json",
    ),
)
