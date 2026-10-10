# Changelog

本文件记录 zhcheck 的版本变更，格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循[语义化版本](https://semver.org/lang/zh-CN/)。

## [Unreleased]

## [0.1.0] - 2026-10-10

首个可用版本。

### 新增

- 12 条内置规则，覆盖空格、标点、用词三类问题：
  - `ZC001` 中英混排缺空格
  - `ZC002` 中文语境使用半角标点
  - `ZC003` 英文语境使用全角标点
  - `ZC004` 重复标点
  - `ZC005` 省略号写法
  - `ZC006` 破折号写法
  - `ZC007` 括号与引号混用
  - `ZC008` 数字与单位缺空格（默认关闭）
  - `ZC009` 易混词与错别字，内置 157 条
  - `ZC010` 术语规范写法，内置 101 条
  - `ZC011` 中文语境多余空格
  - `ZC012` 全角字母数字
- Markdown 感知扫描：屏蔽代码块、行内代码、URL、邮箱、HTML 标签与注释、链接地址、front matter、分隔线、数学公式与脚注引用。
- 自动修复：`--fix` 迭代到收敛，`--dry-run` 预览改动。
- 输出格式：人类可读文本、`json`、GitHub Actions 注解。
- 输入来源：文件、目录、glob 表达式与标准输入。
- 配置：`.zhcheckrc.json`、`.zhcheckrc`、`zhcheck.json` 与 `pyproject.toml` 的 `[tool.zhcheck]` 段。`pyproject.toml` 依赖标准库 `tomllib`（Python 3.11 起提供），3.9 与 3.10 需安装可选依赖 `tomli`；缺少解析器时会输出配置警告，不会静默忽略。
- 忽略机制：`zhcheck-disable-file`、`zhcheck-disable-next-line`、`zhcheck-disable` 与 `zhcheck-enable`。
- 基线机制：`--write-baseline` 冻结存量问题，此后仅报告新增问题。
- 编码处理：自动探测 UTF-8（含 BOM）、GB18030 与 UTF-16，写回时保留原编码与换行符。
- 退出码：按 `error`、`warning`、`info` 三档阈值决定构建结果。

[Unreleased]: https://github.com/ZTLNB/zhcheck/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/ZTLNB/zhcheck/releases/tag/v0.1.0
