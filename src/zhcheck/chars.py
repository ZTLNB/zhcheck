"""字符分类与标点映射。

本模块刻意只依赖标准库，且不使用正则以外的解析手段，保证在任意文本
（Markdown、纯文本、字幕、i18n 文案）上都能工作。
"""

from __future__ import annotations

import unicodedata

# 汉字、假名等"表意文字"范围。注意：这里刻意不包含全角标点与全角字母数字，
# 因为它们在排版规则中的语义完全不同。
_HAN_RANGES = (
    (0x2E80, 0x2EFF),    # CJK 部首补充
    (0x3040, 0x30FF),    # 平假名 / 片假名
    (0x3400, 0x4DBF),    # CJK 扩展 A
    (0x4E00, 0x9FFF),    # CJK 基本区
    (0xF900, 0xFAFF),    # CJK 兼容表意文字
    (0x20000, 0x2FA1F),  # CJK 扩展 B~F
)

# 中文标点（含全角标点、中文引号、破折号、省略号）
_CJK_PUNCT_SINGLE = frozenset(
    "\u2018\u2019\u201c\u201d\u2014\u2015\u2026\u3001\u3002\u3008\u3009"
    "\u300a\u300b\u300c\u300d\u300e\u300f\u3010\u3011\u3014\u3015"
)

# 半角标点 -> 全角标点（中文语境）
HALF_TO_FULL = {
    ",": "\uff0c",
    ";": "\uff1b",
    ":": "\uff1a",
    "!": "\uff01",
    "?": "\uff1f",
    "(": "\uff08",
    ")": "\uff09",
}

# 全角标点 -> 半角标点（英文语境，带尾随空格由调用方决定）
FULL_TO_HALF = {
    "\uff0c": ",",
    "\uff1b": ";",
    "\uff1a": ":",
    "\uff01": "!",
    "\uff1f": "?",
}

# 允许出现在"中文语境"判断中的半角标点（规则 ZC002 的目标集合）
HALF_PUNCT_IN_CN = ",;:!?"

# 允许出现在"英文语境"判断中的全角标点（规则 ZC003 的目标集合）
FULL_PUNCT_IN_EN = "\uff0c\uff1b\uff1a\uff01\uff1f"

# 重复标点检测集合（ZC004）。省略号与破折号由专门规则处理。
DUPLICATE_PUNCT = "\uff0c\u3002\uff01\uff1f\uff1b\uff1a\u3001,.!?;:"

# 全角字母数字（ZC012）
_FULLWIDTH_ALNUM_RANGES = ((0xFF10, 0xFF19), (0xFF21, 0xFF3A), (0xFF41, 0xFF5A))


def is_han(ch: str) -> bool:
    """是否为汉字/假名等表意文字（不含标点、不含全角字母数字）。"""
    if not ch:
        return False
    code = ord(ch)
    return any(low <= code <= high for low, high in _HAN_RANGES)


def is_cjk_punct(ch: str) -> bool:
    """是否为中文标点（含全角标点）。"""
    if not ch:
        return False
    if ch in _CJK_PUNCT_SINGLE:
        return True
    code = ord(ch)
    return (
        0xFF01 <= code <= 0xFF0F      # ！＂＃＄％＆＇（）＊＋，－．／
        or 0xFF1A <= code <= 0xFF20   # ：；＜＝＞？＠
        or 0xFF3B <= code <= 0xFF40   # ［＼］＾＿｀
        or 0xFF5B <= code <= 0xFF65   # ｛｜｝～｟｠｡｢｣､･
        or 0x3001 <= code <= 0x303F   # 、。〈〉《》「」『』【】〔〕〖〗…
    )


def is_cn_context(ch: str) -> bool:
    """该字符是否构成"中文语境"（表意文字或中文标点）。"""
    return is_han(ch) or is_cjk_punct(ch)


def is_ascii_alnum(ch: str) -> bool:
    """是否为 ASCII 字母或数字。"""
    if not ch:
        return False
    return ch.isascii() and ch.isalnum()


def is_fullwidth_alnum(ch: str) -> bool:
    """是否为全角字母或数字。"""
    if not ch:
        return False
    code = ord(ch)
    return any(low <= code <= high for low, high in _FULLWIDTH_ALNUM_RANGES)


def to_halfwidth(ch: str) -> str:
    """把全角字母数字转成半角（NFKC 对这两类字符是安全的）。"""
    return unicodedata.normalize("NFKC", ch)
