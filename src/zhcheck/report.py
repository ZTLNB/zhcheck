"""输出格式：人类可读文本、JSON、GitHub Actions 注解。"""

from __future__ import annotations

import json
import unicodedata
from collections.abc import Sequence

from .engine import AnalysisResult
from .issues import Summary
from .rules import REGISTRY, RULES_BY_ID

_COLORS = {
    "error": "\033[31m",
    "warning": "\033[33m",
    "info": "\033[36m",
    "dim": "\033[90m",
    "bold": "\033[1m",
    "reset": "\033[0m",
}

_ORDER = {"error": 0, "warning": 1, "info": 2}


def _paint(text: str, color: str, enabled: bool) -> str:
    if not enabled:
        return text
    return "%s%s%s" % (_COLORS.get(color, ""), text, _COLORS["reset"])


def build_summary(results: Sequence[AnalysisResult], suppressed: int = 0) -> Summary:
    summary = Summary(suppressed=suppressed)
    by_rule: dict = {}
    for result in results:
        if result.issues:
            summary.files += 1
        for issue in result.issues:
            summary.total += 1
            setattr(summary, issue.severity, getattr(summary, issue.severity) + 1)
            if issue.fixable:
                summary.fixable += 1
            by_rule[issue.rule_id] = by_rule.get(issue.rule_id, 0) + 1
    summary.by_rule = by_rule
    return summary


def format_text(results: Sequence[AnalysisResult], summary: Summary, *, color: bool = False) -> str:
    lines: list[str] = []
    for result in results:
        if not result.issues:
            continue
        lines.append(_paint(result.relpath, "bold", color))
        for issue in result.issues:
            label = "%-7s" % issue.severity
            head = "  %4d:%-4d %s %s  %s" % (
                issue.line,
                issue.column,
                _paint(label, issue.severity, color),
                issue.rule_id,
                issue.message,
            )
            lines.append(head)
            if issue.excerpt:
                lines.append("        %s %s" % (_paint(">", "dim", color), issue.excerpt))
            if issue.note:
                lines.append("        %s %s" % (_paint("!", "dim", color), issue.note))
        lines.append("")

    if summary.total == 0:
        lines.append("未发现问题。")
    else:
        lines.append(
            "共 %d 个问题（%d error / %d warning / %d info），涉及 %d 个文件，其中 %d 个可自动修复。"
            % (
                summary.total,
                summary.error,
                summary.warning,
                summary.info,
                summary.files,
                summary.fixable,
            )
        )
        if summary.suppressed:
            lines.append("已按基线抑制 %d 个存量问题。" % summary.suppressed)
        if summary.fixable:
            lines.append("提示：运行 zhcheck --fix 可自动修复其中 %d 个问题。" % summary.fixable)
    return "\n".join(lines) + "\n"


def format_json(results: Sequence[AnalysisResult], summary: Summary) -> str:
    payload = {
        "version": 1,
        "summary": summary.to_dict(),
        "files": [
            {
                "path": result.relpath,
                "mode": result.mode,
                "issues": [issue.to_dict() for issue in result.issues],
            }
            for result in results
            if result.issues
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def format_github(results: Sequence[AnalysisResult]) -> str:
    lines: list[str] = []
    for result in results:
        for issue in result.issues:
            level = {"error": "error", "warning": "warning", "info": "notice"}.get(
                issue.severity, "warning"
            )
            message = issue.message.replace("\n", " ")
            lines.append(
                "::%s file=%s,line=%d,col=%d,title=%s::%s"
                % (level, result.relpath, issue.line, issue.column, issue.rule_id, message)
            )
    return "\n".join(lines) + ("\n" if lines else "")


def _display_width(text: str) -> int:
    """按终端显示宽度计算字符串长度：中日韩全角字符算两列。"""
    return sum(2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1 for ch in text)


def _pad(text: str, size: int) -> str:
    return text + " " * max(0, size - _display_width(text))


def format_rules() -> str:
    header = "  ".join(
        [_pad("ID", 7), _pad("级别", 10), _pad("分类", 12), _pad("可修复", 8), "说明"]
    )
    lines = [header, "-" * 96]
    for rule in REGISTRY:
        name = rule.name + ("（默认关闭）" if not rule.enabled_by_default else "")
        lines.append(
            "  ".join(
                [
                    _pad(rule.id, 7),
                    _pad(rule.severity, 10),
                    _pad(rule.category, 12),
                    _pad("是" if rule.fixable else "否", 8),
                    name,
                ]
            )
        )
        lines.append("        " + rule.description)
    return "\n".join(lines) + "\n"


def format_statistics(summary: Summary) -> str:
    """按规则汇总，便于在问题量大的项目里先定位主要矛盾。"""
    if summary.total == 0:
        return "未发现问题。\n"
    rows = sorted(summary.by_rule.items(), key=lambda item: (-item[1], item[0]))
    header = "  ".join(
        [_pad("规则", 8), _pad("级别", 8), _pad("分类", 12), _pad("数量", 8), "说明"]
    )
    lines = ["按规则汇总：", header, "-" * 76]
    for rule_id, count in rows:
        rule = RULES_BY_ID[rule_id]
        lines.append(
            "  ".join(
                [
                    _pad(rule_id, 8),
                    _pad(rule.severity, 8),
                    _pad(rule.category, 12),
                    _pad(str(count), 8),
                    rule.name,
                ]
            )
        )
    lines.append("")
    lines.append(
        "共 %d 个问题（%d error / %d warning / %d info），涉及 %d 个文件，其中 %d 个可自动修复。"
        % (
            summary.total,
            summary.error,
            summary.warning,
            summary.info,
            summary.files,
            summary.fixable,
        )
    )
    if summary.suppressed:
        lines.append("已按基线抑制 %d 个存量问题。" % summary.suppressed)
    return "\n".join(lines) + "\n"
