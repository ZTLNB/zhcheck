"""标点类规则：全半角混用、重复标点、省略号、破折号、括号引号、全角字母数字。"""

from __future__ import annotations

import re

from ..chars import (
    DUPLICATE_PUNCT,
    FULL_PUNCT_IN_EN,
    FULL_TO_HALF,
    HALF_PUNCT_IN_CN,
    HALF_TO_FULL,
    is_ascii_alnum,
    is_cjk_punct,
    is_cn_context,
    is_fullwidth_alnum,
    is_han,
    to_halfwidth,
)
from ..issues import Fix, Issue
from . import Rule, ScanContext

_RE_HALF_PUNCT = re.compile(r"[%s]" % re.escape(HALF_PUNCT_IN_CN))
_RE_FULL_PUNCT = re.compile(r"[%s]" % re.escape(FULL_PUNCT_IN_EN))
_RE_ELLIPSIS_DOTS = re.compile(r"\.{3,}")
_RE_ELLIPSIS_STOPS = re.compile(r"\u3002{3,}")
_RE_DASH = re.compile(r"(?<!-)--(?!-)")
_RE_SINGLE_EM_DASH = re.compile(r"(?<!\u2014)\u2014(?!\u2014)")
_RE_PARENS = re.compile(r"\(([^()\n]*)\)")
_RE_DOUBLE_QUOTES = re.compile(r'"([^"\n]*)"')
_RE_FULLWIDTH_ALNUM = re.compile(r"[\uff10-\uff19\uff21-\uff3a\uff41-\uff5a]+")

_MSG_HALF_IN_CN = "中文语境应使用全角标点「%s」"
_MSG_FULL_IN_EN = "英文语境应使用半角标点「%s」"


def check_half_punct_in_cn(ctx: ScanContext) -> list[Issue]:
    issues: list[Issue] = []
    text = ctx.text
    n = len(text)
    for match in _RE_HALF_PUNCT.finditer(text):
        i = match.start()
        if not ctx.active(i, i + 1):
            continue
        if i == 0 or ctx.mask[i - 1]:
            continue
        prev = text[i - 1]
        if not (is_han(prev) or is_cjk_punct(prev)):
            continue
        char = text[i]
        end = i + 1
        # 全角标点后不再留空格，因此顺手把紧跟的一个空格一起替换掉
        absorbs_space = (
            end < n
            and text[end] == " "
            and not ctx.mask[end]
            and end + 1 < n
            and text[end + 1] not in " \t\r\n"
        )
        if absorbs_space:
            end += 1
        full = HALF_TO_FULL[char]
        issues.append(
            ctx.emit(
                "ZC002",
                i,
                end,
                _MSG_HALF_IN_CN % full,
                fixes=[Fix(i, end, full)],
            )
        )
    return issues


def check_full_punct_in_en(ctx: ScanContext) -> list[Issue]:
    issues: list[Issue] = []
    text = ctx.text
    n = len(text)
    for match in _RE_FULL_PUNCT.finditer(text):
        i = match.start()
        if i == 0 or i + 1 >= n:
            continue
        if not ctx.active(i - 1, i + 2):
            continue
        if not (is_ascii_alnum(text[i - 1]) and is_ascii_alnum(text[i + 1])):
            continue
        char = text[i]
        half = FULL_TO_HALF[char]
        issues.append(
            ctx.emit(
                "ZC003",
                i,
                i + 1,
                _MSG_FULL_IN_EN % half,
                fixes=[Fix(i, i + 1, half + " ")],
            )
        )
    return issues


def check_duplicate_punct(ctx: ScanContext) -> list[Issue]:
    issues: list[Issue] = []
    text = ctx.text
    mask = ctx.mask
    n = len(text)
    i = 0
    while i < n:
        char = text[i]
        if mask[i] or char not in DUPLICATE_PUNCT:
            i += 1
            continue
        j = i
        while j + 1 < n and text[j + 1] == char and not mask[j + 1]:
            j += 1
        run = j - i + 1
        if run < 2:
            i += 1
            continue
        if char in (".", "\u3002") and run >= 3:
            i = j + 1
            continue  # 三个及以上的点/句号交给 ZC005 处理成省略号
        if char.isascii():
            left = text[i - 1] if i > 0 else ""
            right = text[j + 1] if j + 1 < n else ""
            # 只有处在中文语境（汉字或中文标点）中才判定为误用，
            # 避免把英文里的 "Hello!!" 误报出来
            if not (is_cn_context(left) or is_cn_context(right)):
                i = j + 1
                continue
        issues.append(
            ctx.emit(
                "ZC004",
                i,
                j + 1,
                "重复标点「%s」应只保留一个" % (char * run),
                fixes=[Fix(i, j + 1, char)],
            )
        )
        i = j + 1
    return issues


def check_ellipsis(ctx: ScanContext) -> list[Issue]:
    issues: list[Issue] = []
    text = ctx.text
    n = len(text)
    for pattern in (_RE_ELLIPSIS_DOTS, _RE_ELLIPSIS_STOPS):
        for match in pattern.finditer(text):
            start, end = match.span()
            if not ctx.active(start, end):
                continue
            left = text[start - 1] if start > 0 else ""
            right = text[end] if end < n else ""
            if not (is_cn_context(left) or is_cn_context(right)):
                continue
            issues.append(
                ctx.emit(
                    "ZC005",
                    start,
                    end,
                    "中文省略号应使用「……」（六个点）",
                    fixes=[Fix(start, end, "\u2026\u2026")],
                )
            )
    return issues


def check_dash(ctx: ScanContext) -> list[Issue]:
    issues: list[Issue] = []
    text = ctx.text
    n = len(text)
    for match in _RE_DASH.finditer(text):
        start, end = match.span()
        if not ctx.active(start, end):
            continue
        left = text[start - 1] if start > 0 else ""
        right = text[end] if end < n else ""
        if not (is_cn_context(left) or is_cn_context(right)):
            continue
        issues.append(
            ctx.emit(
                "ZC006",
                start,
                end,
                "中文破折号应使用「——」（两个字符）",
                fixes=[Fix(start, end, "\u2014\u2014")],
            )
        )
    for match in _RE_SINGLE_EM_DASH.finditer(text):
        start, end = match.span()
        if not ctx.active(start, end):
            continue
        left = text[start - 1] if start > 0 else ""
        right = text[end] if end < n else ""
        if not (is_cn_context(left) and is_cn_context(right)):
            continue
        issues.append(
            ctx.emit(
                "ZC006",
                start,
                end,
                "中文破折号应使用「——」（两个字符），当前只有一个",
            )
        )
    return issues


def check_brackets_and_quotes(ctx: ScanContext) -> list[Issue]:
    issues: list[Issue] = []
    for match in _RE_PARENS.finditer(ctx.text):
        if not (ctx.active(match.start(), match.start() + 1) and ctx.active(match.end() - 1, match.end())):
            continue
        if not ctx.has_han(match.start(1), match.end(1)):
            continue
        issues.append(
            ctx.emit(
                "ZC007",
                match.start(),
                match.end(),
                "中文内容应使用全角括号「（）」",
                fixes=[
                    Fix(match.start(), match.start() + 1, "\uff08"),
                    Fix(match.end() - 1, match.end(), "\uff09"),
                ],
            )
        )
    for match in _RE_DOUBLE_QUOTES.finditer(ctx.text):
        if not (ctx.active(match.start(), match.start() + 1) and ctx.active(match.end() - 1, match.end())):
            continue
        if not ctx.has_han(match.start(1), match.end(1)):
            continue
        issues.append(
            ctx.emit(
                "ZC007",
                match.start(),
                match.end(),
                "中文内容应使用中文引号「“”」",
                fixes=[
                    Fix(match.start(), match.start() + 1, "\u201c"),
                    Fix(match.end() - 1, match.end(), "\u201d"),
                ],
            )
        )
    return issues


def check_fullwidth_alnum(ctx: ScanContext) -> list[Issue]:
    issues: list[Issue] = []
    for match in _RE_FULLWIDTH_ALNUM.finditer(ctx.text):
        start, end = match.span()
        if not ctx.active(start, end):
            continue
        if not any(is_fullwidth_alnum(ch) for ch in match.group(0)):
            continue
        replacement = "".join(to_halfwidth(ch) for ch in match.group(0))
        issues.append(
            ctx.emit(
                "ZC012",
                start,
                end,
                "全角字母/数字「%s」应改为半角「%s」" % (match.group(0), replacement),
                fixes=[Fix(start, end, replacement)],
            )
        )
    return issues


RULES = (
    Rule(
        id="ZC002",
        name="中文语境半角标点",
        severity="error",
        category="punctuation",
        description="中文语境中使用了半角逗号/分号/冒号/问号/叹号，应改为全角。",
        check=check_half_punct_in_cn,
        fixable=True,
        reference="GB/T 15834 · 标点符号用法",
    ),
    Rule(
        id="ZC003",
        name="英文语境全角标点",
        severity="warning",
        category="punctuation",
        description="全角标点被纯英文/数字夹在中间，应改为半角。",
        check=check_full_punct_in_en,
        fixable=True,
    ),
    Rule(
        id="ZC004",
        name="重复标点",
        severity="error",
        category="punctuation",
        description="出现「，，」「。。」「！！」等重复标点，应只保留一个。",
        check=check_duplicate_punct,
        fixable=True,
    ),
    Rule(
        id="ZC005",
        name="省略号写法",
        severity="warning",
        category="punctuation",
        description="中文省略号应为「……」，而不是「...」或「。。。」。",
        check=check_ellipsis,
        fixable=True,
    ),
    Rule(
        id="ZC006",
        name="破折号写法",
        severity="warning",
        category="punctuation",
        description="中文破折号应为「——」（两个字符），而不是「--」或单个「—」。",
        check=check_dash,
        fixable=True,
    ),
    Rule(
        id="ZC007",
        name="括号与引号混用",
        severity="warning",
        category="punctuation",
        description="包裹中文内容时使用了半角括号或半角引号，应改为全角括号/中文引号。",
        check=check_brackets_and_quotes,
        fixable=True,
    ),
    Rule(
        id="ZC012",
        name="全角字母数字",
        severity="warning",
        category="punctuation",
        description="输入法误切换导致的全角字母或数字，应改为半角。",
        check=check_fullwidth_alnum,
        fixable=True,
    ),
)
