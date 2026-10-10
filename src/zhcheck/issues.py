"""问题（Issue）与修复（Fix）的数据结构。"""

from __future__ import annotations

from dataclasses import dataclass, field

SEVERITY_ORDER = {"error": 3, "warning": 2, "info": 1}
SEVERITY_NAMES = ("error", "warning", "info")


@dataclass(frozen=True)
class Fix:
    """一次文本替换。``start == end`` 表示纯插入。"""

    start: int
    end: int
    replacement: str


@dataclass
class Issue:
    rule_id: str
    message: str
    severity: str
    line: int
    column: int
    start: int
    end: int
    excerpt: str = ""
    fixes: tuple[Fix, ...] = ()
    note: str = ""

    @property
    def fixable(self) -> bool:
        return bool(self.fixes)

    def to_dict(self) -> dict:
        data = {
            "rule": self.rule_id,
            "severity": self.severity,
            "line": self.line,
            "column": self.column,
            "message": self.message,
            "excerpt": self.excerpt,
            "fixable": self.fixable,
        }
        if self.note:
            data["note"] = self.note
        return data


@dataclass
class Summary:
    total: int = 0
    error: int = 0
    warning: int = 0
    info: int = 0
    files: int = 0
    fixable: int = 0
    suppressed: int = 0
    by_rule: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "total": self.total,
            "error": self.error,
            "warning": self.warning,
            "info": self.info,
            "files": self.files,
            "fixable": self.fixable,
            "suppressed": self.suppressed,
            "by_rule": dict(sorted(self.by_rule.items())),
        }
