"""规则注册表与扫描上下文。"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from ..chars import is_han
from ..issues import Fix, Issue
from ..textscan import LineIndex

MAX_EXCERPT = 120


@dataclass
class ScanContext:
    """一次文件扫描的共享上下文。规则只通过它读数据、写问题。"""

    text: str
    mask: bytearray
    index: LineIndex
    mode: str
    display_path: str
    relpath: str
    severity_overrides: dict[str, str] = field(default_factory=dict)
    severity_defaults: dict[str, str] = field(default_factory=dict)
    extra_confusables: dict[str, str] = field(default_factory=dict)
    extra_terms: dict[str, str] = field(default_factory=dict)

    def active(self, start: int, end: int) -> bool:
        """区间 [start, end) 是否完全未被屏蔽。"""
        if start < 0 or end > len(self.mask) or start >= end:
            return False
        return all(not self.mask[i] for i in range(start, end))

    def has_han(self, start: int, end: int) -> bool:
        """区间内是否存在未被屏蔽的汉字。"""
        return any(
            not self.mask[i] and is_han(self.text[i])
            for i in range(max(start, 0), min(end, len(self.text)))
        )

    def emit(
        self,
        rule_id: str,
        start: int,
        end: int,
        message: str,
        fixes: Sequence[Fix] = (),
        severity: str = "",
        note: str = "",
    ) -> Issue:
        line = self.index.line_of(start)
        column = self.index.column_of(start)
        line_start, line_end = self.index.span_of_line(line)
        excerpt = self.text[line_start:line_end].strip()
        if len(excerpt) > MAX_EXCERPT:
            excerpt = excerpt[: MAX_EXCERPT - 3] + "..."
        resolved = (
            severity
            or self.severity_overrides.get(rule_id)
            or self.severity_defaults.get(rule_id)
            or "warning"
        )
        return Issue(
            rule_id=rule_id,
            message=message,
            severity=resolved,
            line=line,
            column=column,
            start=start,
            end=end,
            excerpt=excerpt,
            fixes=tuple(fixes),
            note=note,
        )


RuleCheck = Callable[[ScanContext], list[Issue]]


@dataclass(frozen=True)
class Rule:
    id: str
    name: str
    severity: str
    category: str
    description: str
    check: RuleCheck
    fixable: bool = False
    enabled_by_default: bool = True
    reference: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "severity": self.severity,
            "category": self.category,
            "description": self.description,
            "fixable": self.fixable,
            "enabled_by_default": self.enabled_by_default,
            "reference": self.reference,
        }


def _load_rules() -> tuple[Rule, ...]:
    from . import punctuation, spacing, terms

    collected: list[Rule] = []
    for module in (spacing, punctuation, terms):
        collected.extend(module.RULES)
    collected.sort(key=lambda rule: rule.id)
    ids = [rule.id for rule in collected]
    if len(ids) != len(set(ids)):
        raise RuntimeError("规则 ID 重复：%s" % ids)
    return tuple(collected)


REGISTRY: tuple[Rule, ...] = _load_rules()
RULES_BY_ID: dict[str, Rule] = {rule.id: rule for rule in REGISTRY}


def rule_ids() -> list[str]:
    return [rule.id for rule in REGISTRY]
