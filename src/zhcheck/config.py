"""配置加载与规则开关解析。"""

from __future__ import annotations

import fnmatch
import json
import os
import re
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .rules import RULES_BY_ID, rule_ids
from .textscan import MODE_AUTO, MODE_MARKDOWN, MODE_TEXT

CONFIG_FILENAMES = (".zhcheckrc.json", ".zhcheckrc", "zhcheck.json")
VALID_MODES = (MODE_AUTO, MODE_MARKDOWN, MODE_TEXT)
VALID_FAIL_ON = ("error", "warning", "info", "none")

DEFAULT_CONFIG: dict[str, Any] = {
    "include": ["**/*.md", "**/*.markdown", "**/*.txt"],
    "exclude": [
        ".git/**",
        "node_modules/**",
        "**/.venv/**",
        "**/venv/**",
        "**/dist/**",
        "**/build/**",
        "**/__pycache__/**",
        "**/site-packages/**",
    ],
    "mode": MODE_AUTO,
    "fail_on": "error",
    "rules": {},
    "disabled_rules": [],
    "confusables": {},
    "terms": {},
    "exceptions": [],
}


class ConfigError(Exception):
    """配置不合法。"""


@dataclass
class Config:
    include: list[str] = field(default_factory=lambda: list(DEFAULT_CONFIG["include"]))
    exclude: list[str] = field(default_factory=lambda: list(DEFAULT_CONFIG["exclude"]))
    mode: str = MODE_AUTO
    fail_on: str = "error"
    rules: dict[str, dict[str, Any]] = field(default_factory=dict)
    disabled_rules: list[str] = field(default_factory=list)
    confusables: dict[str, str] = field(default_factory=dict)
    terms: dict[str, str] = field(default_factory=dict)
    exceptions: list[str] = field(default_factory=list)
    source: str | None = None
    config_dir: str | None = None
    warnings: list[str] = field(default_factory=list)


def _coerce_str_list(value: Any, key: str) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple)) and all(isinstance(item, str) for item in value):
        return list(value)
    raise ConfigError("配置项 %s 应为字符串或字符串数组" % key)


def _coerce_str_map(value: Any, key: str) -> dict[str, str]:
    if value is None:
        return {}
    if isinstance(value, dict) and all(
        isinstance(k, str) and isinstance(v, str) for k, v in value.items()
    ):
        return dict(value)
    raise ConfigError("配置项 %s 应为「字符串 -> 字符串」映射" % key)


def _coerce_rules(value: Any) -> dict[str, dict[str, Any]]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ConfigError("配置项 rules 应为对象")
    result: dict[str, dict[str, Any]] = {}
    for rule_id, options in value.items():
        if rule_id not in RULES_BY_ID:
            raise ConfigError("未知规则 ID：%s（可用：%s）" % (rule_id, ", ".join(rule_ids())))
        if isinstance(options, bool):
            options = {"enabled": options}
        if not isinstance(options, dict):
            raise ConfigError("规则 %s 的配置应为对象或布尔值" % rule_id)
        entry: dict[str, Any] = {}
        if "enabled" in options:
            entry["enabled"] = bool(options["enabled"])
        if "severity" in options:
            severity = str(options["severity"]).lower()
            if severity not in ("error", "warning", "info"):
                raise ConfigError("规则 %s 的 severity 只能是 error/warning/info" % rule_id)
            entry["severity"] = severity
        result[rule_id] = entry
    return result


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ConfigError("无法读取配置文件 %s：%s" % (path, exc)) from exc
    except ValueError as exc:
        raise ConfigError("配置文件 %s 不是合法 JSON：%s" % (path, exc)) from exc
    if not isinstance(data, dict):
        raise ConfigError("配置文件 %s 的顶层应为对象" % path)
    return data


def _load_toml_module():
    """返回可用的 TOML 解析模块。

    标准库 ``tomllib`` 自 Python 3.11 起提供；3.9 与 3.10 上回退到可选依赖
    ``tomli``。两者都没有时返回 ``None``，此时 ``pyproject.toml`` 配置无法读取，
    调用方必须给出明确提示而不是静默忽略。
    """
    try:
        import tomllib

        return tomllib
    except ImportError:  # pragma: no cover - Python 3.9/3.10
        pass
    try:
        import tomli  # type: ignore[import-not-found]

        return tomli
    except ImportError:  # pragma: no cover - Python 3.9/3.10 且未安装 tomli
        return None


TOML_MODULE = _load_toml_module()

# 在没有 TOML 解析器时，用它做一次廉价的文本探测，以便给出可操作的提示
_TOOL_SECTION_RE = re.compile(r"^[ \t]*\[tool\.zhcheck\]", re.MULTILINE)


def _mentions_tool_zhcheck(path: Path) -> bool:
    try:
        return bool(_TOOL_SECTION_RE.search(path.read_text(encoding="utf-8", errors="replace")))
    except OSError:
        return False


def _read_pyproject(path: Path) -> dict[str, Any] | None:
    module = TOML_MODULE
    if module is None:
        return None
    try:
        with path.open("rb") as handle:
            data = module.load(handle)
    except (OSError, ValueError):
        return None
    section = data.get("tool", {}).get("zhcheck")
    return section if isinstance(section, dict) else None


def _apply(config: Config, raw: dict[str, Any], source: str) -> Config:
    for key in raw:
        if key not in DEFAULT_CONFIG:
            raise ConfigError("配置文件 %s 含未知字段：%s" % (source, key))

    if "include" in raw:
        config.include = _coerce_str_list(raw["include"], "include")
    if "exclude" in raw:
        config.exclude = _coerce_str_list(raw["exclude"], "exclude")
    if "exceptions" in raw:
        config.exceptions = _coerce_str_list(raw["exceptions"], "exceptions")
    if "disabled_rules" in raw:
        disabled = _coerce_str_list(raw["disabled_rules"], "disabled_rules")
        unknown = [rid for rid in disabled if rid not in RULES_BY_ID]
        if unknown:
            raise ConfigError("disabled_rules 含未知规则：%s" % ", ".join(unknown))
        config.disabled_rules = disabled
    if "mode" in raw:
        mode = str(raw["mode"]).lower()
        if mode not in VALID_MODES:
            raise ConfigError("mode 只能是 auto/markdown/text，当前为 %s" % mode)
        config.mode = mode
    if "fail_on" in raw:
        fail_on = str(raw["fail_on"]).lower()
        if fail_on not in VALID_FAIL_ON:
            raise ConfigError("fail_on 只能是 error/warning/info/none，当前为 %s" % fail_on)
        config.fail_on = fail_on
    if "rules" in raw:
        config.rules.update(_coerce_rules(raw["rules"]))
    if "confusables" in raw:
        config.confusables.update(_coerce_str_map(raw["confusables"], "confusables"))
    if "terms" in raw:
        config.terms.update(_coerce_str_map(raw["terms"], "terms"))
    config.source = source
    return config


def find_config(start: Path | None = None) -> Path | None:
    """从 start 目录逐级向上查找配置文件。"""
    current = Path(start or Path.cwd()).resolve()
    for directory in [current, *current.parents]:
        for name in CONFIG_FILENAMES:
            candidate = directory / name
            if candidate.is_file():
                return candidate
        pyproject = directory / "pyproject.toml"
        # 没有 TOML 解析器时也要返回路径，交给 load_config 给出提示，
        # 否则配置会被静默忽略——这正是 0.1.0 在 Python 3.9/3.10 上的缺陷
        if pyproject.is_file() and (
            _read_pyproject(pyproject) is not None or _mentions_tool_zhcheck(pyproject)
        ):
            return pyproject
    return None


def _toml_unavailable_hint(path: Path) -> str:
    return (
        "检测到 %s 中的 [tool.zhcheck] 配置节，但当前 Python %d.%d 没有可用的 TOML 解析器"
        "（标准库 tomllib 自 3.11 起提供），该配置已被忽略。"
        "请改用 .zhcheckrc.json，或安装 tomli（pip install tomli），或升级到 Python 3.11 以上。"
        % (path, sys.version_info[0], sys.version_info[1])
    )


def load_config(explicit: str | None = None, start: Path | None = None) -> Config:
    config = Config()
    if explicit:
        path = Path(explicit)
        if not path.is_file():
            raise ConfigError("配置文件不存在：%s" % explicit)
        if path.name == "pyproject.toml":
            section = _read_pyproject(path)
            if section is None:
                if _mentions_tool_zhcheck(path):
                    raise ConfigError(_toml_unavailable_hint(path))
                raise ConfigError("%s 中缺少 [tool.zhcheck] 配置节" % explicit)
            _apply(config, section, str(path))
        else:
            _apply(config, _read_json(path), str(path))
        config.config_dir = str(path.parent.resolve())
        return config

    found = find_config(start)
    if found is None:
        return config
    if found.name == "pyproject.toml":
        section = _read_pyproject(found)
        if section is None:
            if _mentions_tool_zhcheck(found):
                config.warnings.append(_toml_unavailable_hint(found))
            return config
        _apply(config, section, str(found))
    else:
        _apply(config, _read_json(found), str(found))
    config.config_dir = str(found.parent.resolve())
    return config


@dataclass
class Settings:
    """单次运行生效的规则开关与严重级别。"""

    enabled: dict[str, bool] = field(default_factory=dict)
    severity: dict[str, str] = field(default_factory=dict)

    def is_enabled(self, rule_id: str) -> bool:
        return self.enabled.get(rule_id, True)

    def severity_of(self, rule_id: str, default: str) -> str:
        return self.severity.get(rule_id, default)


def build_settings(
    config: Config,
    select: Sequence[str] = (),
    ignore: Sequence[str] = (),
) -> Settings:
    settings = Settings()
    for rule in RULES_BY_ID.values():
        settings.enabled[rule.id] = rule.enabled_by_default
        settings.severity[rule.id] = rule.severity

    for rule_id, options in config.rules.items():
        if "enabled" in options:
            settings.enabled[rule_id] = options["enabled"]
        if "severity" in options:
            settings.severity[rule_id] = options["severity"]

    for rule_id in config.disabled_rules:
        settings.enabled[rule_id] = False

    if select:
        wanted = _validate_rule_selection(select, "--select")
        for rule_id in settings.enabled:
            settings.enabled[rule_id] = rule_id in wanted
    if ignore:
        unwanted = _validate_rule_selection(ignore, "--ignore")
        for rule_id in unwanted:
            settings.enabled[rule_id] = False

    return settings


def _validate_rule_selection(values: Sequence[str], flag: str) -> set:
    known = set(rule_ids())
    selected = set()
    for value in values:
        for item in str(value).replace(";", ",").split(","):
            item = item.strip().upper()
            if not item:
                continue
            if item not in known:
                raise ConfigError("%s 含未知规则：%s" % (flag, item))
            selected.add(item)
    return selected


def _match_parts(pattern_parts: Sequence[str], path_parts: Sequence[str]) -> bool:
    if not pattern_parts:
        return not path_parts
    head = pattern_parts[0]
    if head == "**":
        for index in range(len(path_parts) + 1):
            if _match_parts(pattern_parts[1:], path_parts[index:]):
                return True
        return False
    if not path_parts:
        return False
    if not fnmatch.fnmatchcase(path_parts[0], head):
        return False
    return _match_parts(pattern_parts[1:], path_parts[1:])


def _norm(path: str) -> str:
    return path.replace(os.sep, "/").replace("\\", "/")


def match_glob(pattern: str, relpath: str) -> bool:
    """支持 ``**`` 的 glob 匹配；不含 ``/`` 的模式按文件名匹配。"""
    pattern = _norm(pattern).strip("/")
    if not pattern:
        return False
    if "/" not in pattern:
        pattern = "**/" + pattern
    return _match_parts(pattern.split("/"), _norm(relpath).split("/"))


def match_any(patterns: Sequence[str], relpath: str) -> bool:
    return any(match_glob(pattern, relpath) for pattern in patterns)


def should_prune_dir(relpath: str, exclude: Sequence[str]) -> bool:
    """判断遍历时是否可以整目录跳过。"""
    probe = _norm(relpath).rstrip("/") + "/__zhcheck_probe__"
    return match_any(exclude, probe)


def is_target_file(relpath: str, config: Config) -> bool:
    if match_any(config.exclude, relpath):
        return False
    return match_any(config.include, relpath)


def dumps_default_config() -> str:
    payload = {
        "include": DEFAULT_CONFIG["include"],
        "exclude": DEFAULT_CONFIG["exclude"],
        "mode": DEFAULT_CONFIG["mode"],
        "fail_on": DEFAULT_CONFIG["fail_on"],
        "rules": {"ZC008": {"enabled": True, "severity": "info"}},
        "confusables": {"登陆系统": "登录系统"},
        "terms": {"SpringBoot": "Spring Boot"},
        "exceptions": [],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
