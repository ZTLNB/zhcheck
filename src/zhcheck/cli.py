"""命令行入口。"""

from __future__ import annotations

import argparse
import contextlib
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from . import __version__
from . import baseline as baseline_mod
from .config import (
    Config,
    ConfigError,
    Settings,
    build_settings,
    dumps_default_config,
    load_config,
)
from .engine import AnalysisResult, analyze
from .files import collect_targets, norm_rel, read_text, write_text
from .fixer import apply_fixes, select_fixes
from .issues import SEVERITY_ORDER, Summary
from .report import build_summary, format_github, format_json, format_rules, format_text
from .textscan import MODE_AUTO, MODE_MARKDOWN, MODE_TEXT

EXIT_OK = 0
EXIT_ISSUES = 1
EXIT_USAGE = 2

# 修复一轮后可能暴露新的可修复问题（例如全角字母转半角后触发中英混排空格规则），
# 因此反复修复直到收敛；上限用于防御规则之间互相"打架"造成死循环。
MAX_FIX_PASSES = 5


@dataclass
class FileRun:
    path: Path | None
    encoding: str
    result: AnalysisResult
    changed: bool = False
    writes: int = 0
    extra: list[str] = field(default_factory=list)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="zhcheck",
        description="零依赖的中文内容规范检查与自动修复工具。",
        epilog="示例：zhcheck README.md docs/ --fix --format text",
    )
    parser.add_argument("paths", nargs="*", help="要检查的文件或目录（默认当前目录）；用 - 从标准输入读取")
    parser.add_argument(
        "--config",
        metavar="PATH",
        help="指定配置文件（默认向上查找 .zhcheckrc.json / pyproject.toml）",
    )
    parser.add_argument("--format", choices=("text", "json", "github"), default="text", help="输出格式")
    parser.add_argument("--mode", choices=(MODE_AUTO, MODE_MARKDOWN, MODE_TEXT), help="覆盖解析模式")
    parser.add_argument("--fix", action="store_true", help="自动修复可修复的问题")
    parser.add_argument("--dry-run", action="store_true", help="与 --fix 配合：只列出将修改的文件，不写回")
    parser.add_argument(
        "--select",
        action="append",
        default=[],
        metavar="RULES",
        help="只启用指定规则（逗号分隔，可重复）",
    )
    parser.add_argument(
        "--ignore",
        action="append",
        default=[],
        metavar="RULES",
        help="禁用指定规则（逗号分隔，可重复）",
    )
    parser.add_argument(
        "--fail-on", choices=("error", "warning", "info", "none"), help="退出码阈值，默认取配置"
    )
    parser.add_argument("--baseline", metavar="PATH", default=".zhcheck-baseline.json", help="基线文件路径")
    parser.add_argument("--no-baseline", action="store_true", help="忽略基线文件")
    parser.add_argument("--write-baseline", action="store_true", help="把当前全部问题写入基线文件后退出")
    parser.add_argument("--encoding", default="auto", help="文件编码，默认 auto 自动探测")
    parser.add_argument("--stdin-filename", default="<stdin>", help="标准输入对应的文件名，用于判断解析模式")
    parser.add_argument("--list-rules", action="store_true", help="列出全部规则后退出")
    parser.add_argument("--init", action="store_true", help="在当前目录生成 .zhcheckrc.json 模板后退出")
    parser.add_argument("--no-color", action="store_true", help="禁用彩色输出")
    parser.add_argument("--quiet", action="store_true", help="只输出汇总")
    parser.add_argument("--version", action="store_true", help="显示版本号")
    return parser


def _configure_stdout() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            with contextlib.suppress(ValueError, OSError):  # pragma: no cover
                reconfigure(errors="backslashreplace")


def _read_stdin(encoding: str) -> str:
    data = sys.stdin.buffer.read()
    if encoding != "auto":
        return data.decode(encoding, errors="replace")
    for candidate in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return data.decode(candidate)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _fix_to_convergence(
    text: str,
    *,
    display_path: str,
    relpath: str,
    settings: Settings,
    config: Config,
) -> tuple[str, AnalysisResult, int]:
    """反复应用自动修复直到收敛，返回 (最终文本, 最终分析结果, 修复处数)。"""

    def run_analysis(payload: str) -> AnalysisResult:
        return analyze(
            payload,
            display_path=display_path,
            relpath=relpath,
            settings=settings,
            config=config,
        )

    result = run_analysis(text)
    current = text
    total = 0
    for _ in range(MAX_FIX_PASSES):
        fixes = select_fixes(result.issues)
        if not fixes:
            break
        updated = apply_fixes(current, fixes)
        if updated == current:
            break
        total += len(fixes)
        current = updated
        result = run_analysis(current)
    return current, result, total


def _severity_failure(summary: Summary, fail_on: str) -> bool:
    if fail_on == "none":
        return False
    threshold = SEVERITY_ORDER[fail_on]
    return any(
        getattr(summary, level) > 0
        for level, order in SEVERITY_ORDER.items()
        if order >= threshold
    )


def _emit(args: argparse.Namespace, runs: Sequence[FileRun], summary: Summary, color: bool) -> None:
    results = [run.result for run in runs]
    if args.format == "json":
        sys.stdout.write(format_json(results, summary))
    elif args.format == "github":
        sys.stdout.write(format_github(results))
    elif args.quiet:
        sys.stdout.write(
            "%d 个问题（%d error / %d warning / %d info）\n"
            % (summary.total, summary.error, summary.warning, summary.info)
        )
    else:
        sys.stdout.write(format_text(results, summary, color=color))


def main(argv: Sequence[str] | None = None) -> int:
    _configure_stdout()
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.version:
        sys.stdout.write("zhcheck %s\n" % __version__)
        return EXIT_OK

    if args.list_rules:
        sys.stdout.write(format_rules())
        return EXIT_OK

    if args.init:
        target = Path(".zhcheckrc.json")
        if target.exists():
            sys.stderr.write("配置错误：%s 已存在，未覆盖。\n" % target)
            return EXIT_USAGE
        target.write_text(dumps_default_config(), encoding="utf-8")
        sys.stdout.write("已生成 %s\n" % target)
        return EXIT_OK

    cwd = Path.cwd()
    try:
        config = load_config(args.config, start=cwd)
        if args.mode:
            config.mode = args.mode
        if args.fail_on:
            config.fail_on = args.fail_on
        settings: Settings = build_settings(config, args.select, args.ignore)
    except ConfigError as exc:
        sys.stderr.write("配置错误：%s\n" % exc)
        return EXIT_USAGE

    for warning in config.warnings:
        sys.stderr.write("配置警告：%s\n" % warning)

    use_stdin = "-" in args.paths
    runs: list[FileRun] = []

    if use_stdin:
        text = _read_stdin(args.encoding)
        result = analyze(
            text,
            display_path=args.stdin_filename,
            relpath=args.stdin_filename,
            settings=settings,
            config=config,
        )
        runs.append(FileRun(path=None, encoding="utf-8", result=result))
    else:
        targets, warnings = collect_targets(args.paths, config, cwd)
        for warning in warnings:
            sys.stderr.write("%s\n" % warning)
        if not targets:
            sys.stderr.write("未找到可检查的文件。\n")
            return EXIT_OK
        for path in targets:
            try:
                text, encoding = read_text(path, args.encoding)
            except (OSError, UnicodeDecodeError) as exc:
                sys.stderr.write("无法读取 %s：%s\n" % (path, exc))
                continue
            result = analyze(
                text,
                display_path=str(path),
                relpath=norm_rel(path, cwd),
                settings=settings,
                config=config,
            )
            runs.append(FileRun(path=path, encoding=encoding, result=result))

    # 基线抑制
    baseline_path = None if args.no_baseline else args.baseline
    suppressed = 0
    if baseline_path and not args.write_baseline:
        baseline_data = baseline_mod.load(baseline_path)
        suppressed = baseline_mod.suppress([run.result for run in runs], baseline_data)

    # 自动修复
    if args.fix:
        for run in runs:
            if not any(issue.fixable for issue in run.result.issues):
                continue
            fixed_text, final_result, writes = _fix_to_convergence(
                run.result.text,
                display_path=run.result.display_path,
                relpath=run.result.relpath,
                settings=settings,
                config=config,
            )
            if fixed_text == run.result.text:
                continue
            run.changed = True
            run.writes = writes
            if run.path is None:
                sys.stdout.write(fixed_text)
                run.result.issues = []
                continue
            if not args.dry_run:
                write_text(run.path, fixed_text, run.encoding)
                run.result = final_result
            else:
                run.result.issues = []

    summary = build_summary([run.result for run in runs], suppressed=suppressed)

    if args.write_baseline:
        if not baseline_path:
            sys.stderr.write("配置错误：--write-baseline 不能与 --no-baseline 同时使用。\n")
            return EXIT_USAGE
        baseline_mod.save(baseline_path, baseline_mod.build([run.result for run in runs]))
        sys.stdout.write(
            "已写入基线 %s（记录 %d 个问题，涉及 %d 个文件）。\n"
            % (baseline_path, summary.total, summary.files)
        )
        return EXIT_OK

    if args.fix:
        changed = [run for run in runs if run.changed and run.path is not None]
        if args.dry_run:
            for run in changed:
                sys.stdout.write("[dry-run] 将修改 %s（%d 处）\n" % (run.result.relpath, run.writes))
        elif changed:
            for run in changed:
                sys.stdout.write("已修改 %s（%d 处）\n" % (run.result.relpath, run.writes))
            sys.stdout.write("\n")
        if use_stdin:
            # 标准输入模式下把修复结果直接交给下游管道，不再输出报告
            return EXIT_OK

    _emit(args, runs, summary, color=not args.no_color and sys.stdout.isatty())

    if args.dry_run:
        return EXIT_OK
    return EXIT_ISSUES if _severity_failure(summary, config.fail_on) else EXIT_OK


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
