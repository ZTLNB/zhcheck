"""扫描引擎：把文本变成一组问题。"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from .config import Config, Settings
from .issues import Issue
from .rules import REGISTRY, ScanContext
from .textscan import LineIndex, build_mask, mask_span, parse_directives, resolve_mode


@dataclass
class AnalysisResult:
    display_path: str
    relpath: str
    text: str
    mask: bytearray
    index: LineIndex
    mode: str = "auto"
    issues: list[Issue] = field(default_factory=list)
    suppressed: int = 0


def analyze(
    text: str,
    *,
    display_path: str,
    relpath: str,
    settings: Settings,
    config: Config,
) -> AnalysisResult:
    mode = resolve_mode(config.mode, display_path)
    index = LineIndex(text)
    directives, directive_spans = parse_directives(text, index)
    mask = build_mask(text, mode, config.exceptions)
    for start, end in directive_spans:
        mask_span(mask, start, end)

    context = ScanContext(
        text=text,
        mask=mask,
        index=index,
        mode=mode,
        display_path=display_path,
        relpath=relpath,
        severity_overrides=dict(settings.severity),
        severity_defaults={rule.id: rule.severity for rule in REGISTRY},
        extra_confusables=dict(config.confusables),
        extra_terms=dict(config.terms),
    )

    issues: list[Issue] = []
    for rule in REGISTRY:
        if not settings.is_enabled(rule.id):
            continue
        for issue in rule.check(context):
            if directives.is_disabled(issue.rule_id, issue.line):
                continue
            issues.append(issue)

    issues = _dedupe(issues)
    issues.sort(key=lambda item: (item.line, item.column, item.rule_id))
    return AnalysisResult(
        display_path=display_path,
        relpath=relpath,
        text=text,
        mask=mask,
        index=index,
        mode=mode,
        issues=issues,
    )


def _dedupe(issues: Sequence[Issue]) -> list[Issue]:
    seen = set()
    unique: list[Issue] = []
    for issue in issues:
        key = (issue.rule_id, issue.start, issue.end, issue.message)
        if key in seen:
            continue
        seen.add(key)
        unique.append(issue)
    return unique


def count_by_severity(issues: Sequence[Issue]) -> dict[str, int]:
    counts = {"error": 0, "warning": 0, "info": 0}
    for issue in issues:
        counts[issue.severity] = counts.get(issue.severity, 0) + 1
    return counts
