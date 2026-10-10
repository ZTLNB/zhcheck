"""文本扫描：屏蔽区间（mask）与行内指令（directives）。

设计要点：zhcheck 不做完整 Markdown AST 解析，而是构造一个"屏蔽掩码"——
把不该被检查的字符（代码块、行内代码、URL、HTML 标签、链接目标等）标记为
1，规则只在掩码为 0 的字符上工作。这样既零依赖，又能天然支持任意文本格式。
"""

from __future__ import annotations

import bisect
import re
from collections.abc import Sequence
from dataclasses import dataclass, field

MODE_MARKDOWN = "markdown"
MODE_TEXT = "text"
MODE_AUTO = "auto"

_DIRECTIVE_RE = re.compile(
    r"^[ \t]*(?:<!--[ \t]*)?zhcheck-(disable-file|disable-next-line|disable|enable)\b"
    r"(?P<rules>[^>]*?)(?:-->)?[ \t]*$"
)
_RULE_ID_RE = re.compile(r"[A-Z]{2}\d{3}")

_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_HTML_TAG_RE = re.compile(r"</?[A-Za-z][A-Za-z0-9-]*(?:[ \t][^<>\n]*)?/?>")
_HTML_ENTITY_RE = re.compile(r"&(?:[A-Za-z][A-Za-z0-9]{1,31}|#\d{1,7}|#x[0-9A-Fa-f]{1,6});")
_URL_RE = re.compile(
    r"(?:https?|ftp|file|mailto|ssh|git)://"
    r"[^\s<>\"'\u3001\u3002\uff0c\uff09\u3011\u300b\u300d\u201d]+"
)
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_MD_LINK_DEST_RE = re.compile(r"\]\(([^()\n]*)\)")
_MD_REF_DEF_RE = re.compile(r"^[ \t]{0,3}\[[^\]\n]+\]:[ \t]*\S+.*$", re.MULTILINE)
_MD_FENCE_RE = re.compile(r"^[ \t]{0,3}(`{3,}|~{3,})")
_MD_HR_RE = re.compile(r"^[ \t]{0,3}([-*_])[ \t]*(?:\1[ \t]*){2,}[ \t]*$", re.MULTILINE)
_MATH_RE = re.compile(r"(?<!\\)\$[^$\n]+\$")
_FOOTNOTE_REF_RE = re.compile(r"\[\^[^\]\n]+\]")
_WIN_PATH_RE = re.compile(r"[A-Za-z]:\\(?:[^\s<>\"'|]+\\?)+")
_REL_PATH_RE = re.compile(r"\.{1,2}/[\w.@+-][\w.@+-/]*")
_ABS_PATH_RE = re.compile(r"(?<![\w/])/(?:[\w.@+-]+/)+[\w.@+-]*")
_FRONT_MATTER_RE = re.compile(r"\A---[ \t]*\r?\n.*?\r?\n---[ \t]*(?:\r?\n|\Z)", re.DOTALL)


class LineIndex:
    """字符偏移 <-> (行, 列) 互查。行、列均从 1 开始。"""

    __slots__ = ("text", "starts")

    def __init__(self, text: str) -> None:
        self.text = text
        starts = [0]
        for i, ch in enumerate(text):
            if ch == "\n":
                starts.append(i + 1)
        self.starts: list[int] = starts

    def line_of(self, offset: int) -> int:
        return bisect.bisect_right(self.starts, offset)

    def column_of(self, offset: int) -> int:
        line = self.line_of(offset)
        return offset - self.starts[line - 1] + 1

    def span_of_line(self, line: int) -> tuple[int, int]:
        start = self.starts[line - 1]
        end = self.starts[line] - 1 if line < len(self.starts) else len(self.text)
        return start, end

    def line_text(self, line: int) -> str:
        start, end = self.span_of_line(line)
        return self.text[start:end]

    def line_count(self) -> int:
        return len(self.starts)


@dataclass
class Directives:
    """文件级与行级规则禁用信息。``None`` 表示"全部规则"。"""

    file_disabled: frozenset[str] | None = None
    disabled_lines: dict[int, frozenset[str] | None] = field(default_factory=dict)

    def is_disabled(self, rule_id: str, line: int) -> bool:
        if self.file_disabled is not None and (not self.file_disabled or rule_id in self.file_disabled):
            return True
        if line in self.disabled_lines:
            rules = self.disabled_lines[line]
            if rules is None or rule_id in rules:
                return True
        return False


def _parse_rule_list(raw: str) -> frozenset[str] | None:
    ids = _RULE_ID_RE.findall(raw or "")
    if not ids:
        return None
    return frozenset(ids)


def _add_disabled(directives: Directives, line_no: int, rules: frozenset[str] | None) -> None:
    """把某行的禁用规则并入已有状态（``None`` 表示全部规则，优先级最高）。"""
    if rules is None:
        directives.disabled_lines[line_no] = None
        return
    if line_no not in directives.disabled_lines:
        directives.disabled_lines[line_no] = rules
        return
    current = directives.disabled_lines[line_no]
    if current is None:
        return
    directives.disabled_lines[line_no] = frozenset(set(current) | set(rules))


def parse_directives(text: str, index: LineIndex) -> tuple[Directives, list[tuple[int, int]]]:
    """单趟解析行内指令，返回 (指令信息, 需要屏蔽的区间列表)。"""
    directives = Directives()
    spans: list[tuple[int, int]] = []

    active: set = set()
    all_disabled = False

    for line_no in range(1, index.line_count() + 1):
        start, end = index.span_of_line(line_no)
        stripped = index.text[start:end].strip()
        match = _DIRECTIVE_RE.match(stripped)
        if match is None:
            if all_disabled:
                directives.disabled_lines[line_no] = None
            elif active:
                _add_disabled(directives, line_no, frozenset(active))
            continue

        spans.append((start, end))
        kind = match.group(1)
        rules = _parse_rule_list(match.group("rules"))
        if kind == "disable-file":
            directives.file_disabled = rules if rules is not None else frozenset()
        elif kind == "disable-next-line":
            _add_disabled(directives, line_no + 1, rules)
        elif kind == "disable":
            if rules is None:
                all_disabled = True
            else:
                active |= set(rules)
        elif kind == "enable":
            if rules is None:
                all_disabled = False
                active.clear()
            else:
                active -= set(rules)

    return directives, spans


def _mask(mask: bytearray, start: int, end: int) -> None:
    limit = len(mask)
    if start < 0:
        start = 0
    if end > limit:
        end = limit
    for i in range(start, end):
        mask[i] = 1


def mask_span(mask: bytearray, start: int, end: int) -> None:
    """把区间 [start, end) 标记为"不参与检查"（供指令行等场景复用）。"""
    _mask(mask, start, end)


def _mask_regex(mask: bytearray, text: str, pattern: re.Pattern[str], group: int = 0) -> None:
    for match in pattern.finditer(text):
        start, end = match.span(group)
        if start >= 0:
            _mask(mask, start, end)


def _mask_fenced_code(mask: bytearray, text: str) -> None:
    offset = 0
    fence_char = ""
    fence_len = 0
    block_start = -1
    for raw_line in text.splitlines(keepends=True):
        stripped = raw_line.rstrip("\r\n").strip()
        if not fence_char:
            match = _MD_FENCE_RE.match(raw_line.rstrip("\r\n"))
            if match:
                fence_char = match.group(1)[0]
                fence_len = len(match.group(1))
                block_start = offset
        else:
            is_closing_fence = (
                stripped
                and stripped[0] == fence_char
                and len(stripped) >= fence_len
                and set(stripped) == {fence_char}
            )
            if is_closing_fence:
                _mask(mask, block_start, offset + len(raw_line))
                fence_char = ""
                block_start = -1
        offset += len(raw_line)
    if fence_char and block_start >= 0:
        _mask(mask, block_start, len(text))


def _mask_inline_code(mask: bytearray, text: str) -> None:
    """按 CommonMark 的简化规则处理反引号：等长反引号配对。"""
    i = 0
    n = len(text)
    while i < n:
        if text[i] != "`":
            i += 1
            continue
        run = 0
        while i + run < n and text[i + run] == "`":
            run += 1
        opener = i
        j = i + run
        found = -1
        while j < n:
            if text[j] == "`":
                close_run = 0
                while j + close_run < n and text[j + close_run] == "`":
                    close_run += 1
                if close_run == run:
                    found = j
                    break
                j += close_run
            else:
                j += 1
        if found == -1:
            i = opener + run
            continue
        _mask(mask, opener, found + run)
        i = found + run


def resolve_mode(mode: str, path: str) -> str:
    """把 auto 解析成具体的 markdown / text。"""
    if mode in (MODE_MARKDOWN, MODE_TEXT):
        return mode
    lowered = path.lower()
    if lowered.endswith((".md", ".markdown", ".mdown", ".mkd")):
        return MODE_MARKDOWN
    return MODE_TEXT


def build_mask(
    text: str,
    mode: str = MODE_MARKDOWN,
    extra_patterns: Sequence[str] = (),
) -> bytearray:
    """构造屏蔽掩码：1 表示该字符不参与检查。"""
    mask = bytearray(len(text))
    if not text:
        return mask

    for pattern in extra_patterns:
        try:
            _mask_regex(mask, text, re.compile(pattern))
        except re.error:
            continue

    _mask_regex(mask, text, _HTML_COMMENT_RE)
    _mask_regex(mask, text, _URL_RE)
    _mask_regex(mask, text, _EMAIL_RE)

    if mode == MODE_MARKDOWN:
        _mask_regex(mask, text, _FRONT_MATTER_RE)
        _mask_fenced_code(mask, text)
        _mask_regex(mask, text, _HTML_TAG_RE)
        _mask_regex(mask, text, _MD_LINK_DEST_RE, group=1)
        _mask_regex(mask, text, _MD_REF_DEF_RE)
        _mask_regex(mask, text, _MD_HR_RE)
        _mask_inline_code(mask, text)
        _mask_regex(mask, text, _MATH_RE)
        _mask_regex(mask, text, _FOOTNOTE_REF_RE)

    _mask_regex(mask, text, _HTML_ENTITY_RE)
    _mask_regex(mask, text, _WIN_PATH_RE)
    _mask_regex(mask, text, _REL_PATH_RE)
    _mask_regex(mask, text, _ABS_PATH_RE)

    return mask
