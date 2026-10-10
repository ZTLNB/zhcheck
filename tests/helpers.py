"""测试公共辅助。"""

from __future__ import annotations

import contextlib
import io
import os
import tempfile
from collections.abc import Sequence
from pathlib import Path

from zhcheck.cli import main
from zhcheck.config import Config, build_settings
from zhcheck.engine import AnalysisResult, analyze
from zhcheck.issues import Issue


def lint(
    text: str,
    *,
    mode: str = "auto",
    path: str = "a.md",
    config: Config = None,
    select: Sequence[str] = (),
    ignore: Sequence[str] = (),
) -> AnalysisResult:
    cfg = config or Config()
    if mode != "auto":
        cfg.mode = mode
    settings = build_settings(cfg, select, ignore)
    return analyze(text, display_path=path, relpath=path, settings=settings, config=cfg)


def issues_of(text: str, rule_id: str, **kwargs) -> list[Issue]:
    return [issue for issue in lint(text, **kwargs).issues if issue.rule_id == rule_id]


def ids(text: str, **kwargs) -> list[str]:
    return [issue.rule_id for issue in lint(text, **kwargs).issues]


def fixed(text: str, **kwargs) -> str:
    from zhcheck.fixer import apply_fixes, select_fixes

    result = lint(text, **kwargs)
    return apply_fixes(result.text, select_fixes(result.issues))


@contextlib.contextmanager
def working_directory(path: Path):
    previous = os.getcwd()
    os.chdir(str(path))
    try:
        yield path
    finally:
        os.chdir(previous)


@contextlib.contextmanager
def temporary_directory():
    with tempfile.TemporaryDirectory() as tmp:
        yield Path(tmp)


class FakeStdin:
    def __init__(self, payload: bytes) -> None:
        self.buffer = io.BytesIO(payload)


def run_cli(argv: Sequence[str], stdin: bytes = None) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    original_stdin = None
    if stdin is not None:
        import sys

        original_stdin = sys.stdin
        sys.stdin = FakeStdin(stdin)
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(list(argv))
    finally:
        if original_stdin is not None:
            import sys

            sys.stdin = original_stdin
    return code, out.getvalue(), err.getvalue()
