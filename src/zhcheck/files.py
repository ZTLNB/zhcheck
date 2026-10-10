"""文件收集与读取。"""

from __future__ import annotations

import glob
import os
from collections.abc import Sequence
from pathlib import Path

from .config import Config, is_target_file, should_prune_dir


def norm_rel(path: os.PathLike, cwd: os.PathLike) -> str:
    return os.path.relpath(str(path), str(cwd)).replace(os.sep, "/").replace("\\", "/")


def read_text(path: Path, encoding: str = "auto") -> tuple[str, str]:
    """读取文本，返回 (内容, 实际使用的编码)。默认按 BOM 与常见中文编码探测。"""
    data = path.read_bytes()
    if data.startswith(b"\xff\xfe") or data.startswith(b"\xfe\xff"):
        return data.decode("utf-16"), "utf-16"
    if data.startswith(b"\xef\xbb\xbf"):
        return data.decode("utf-8-sig"), "utf-8-sig"
    if encoding != "auto":
        return data.decode(encoding), encoding
    for candidate in ("utf-8", "gb18030"):
        try:
            return data.decode(candidate), candidate
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace"), "utf-8"


def write_text(path: Path, text: str, encoding: str) -> None:
    """写回文件，保留原编码与换行符（不做换行转换）。"""
    if encoding == "utf-8-sig":
        path.write_bytes(text.encode("utf-8-sig"))
    else:
        with path.open("w", encoding=encoding, newline="") as handle:
            handle.write(text)


def collect_targets(
    paths: Sequence[str],
    config: Config,
    cwd: Path,
) -> tuple[list[Path], list[str]]:
    """把命令行参数展开成待检查文件列表。

    显式给出的文件总是被检查（不受 include/exclude 影响）；目录与通配符
    则按配置中的 include/exclude 过滤。
    """
    files: list[Path] = []
    warnings: list[str] = []
    seen = set()

    def add(candidate: Path, explicit: bool) -> None:
        try:
            key = candidate.resolve()
        except OSError:
            key = candidate
        if key in seen:
            return
        if not explicit and not is_target_file(norm_rel(candidate, cwd), config):
            return
        seen.add(key)
        files.append(candidate)

    def walk(directory: Path) -> None:
        for root, dirs, names in os.walk(str(directory)):
            rel_root = norm_rel(root, cwd)
            pruned = []
            for name in sorted(dirs):
                child = rel_root + "/" + name if rel_root not in (".", "") else name
                if not should_prune_dir(child, config.exclude):
                    pruned.append(name)
            dirs[:] = pruned
            for name in sorted(names):
                add(Path(root) / name, explicit=False)

    for raw in paths or ["."]:
        candidate = Path(raw)
        if candidate.is_file():
            add(candidate, explicit=True)
            continue
        if candidate.is_dir():
            walk(candidate)
            continue
        matches = sorted(glob.glob(raw, recursive=True))
        if not matches:
            warnings.append("路径不存在，已跳过：%s" % raw)
            continue
        for match in matches:
            matched = Path(match)
            if matched.is_file():
                add(matched, explicit=True)
            elif matched.is_dir():
                walk(matched)

    files.sort(key=lambda item: norm_rel(item, cwd))
    return files, warnings
