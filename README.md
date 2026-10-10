# zhcheck

**零依赖的中文内容规范检查与自动修复工具。**

[![CI](https://github.com/ZTLNB/zhcheck/actions/workflows/ci.yml/badge.svg)](https://github.com/ZTLNB/zhcheck/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue.svg)](pyproject.toml)

zhcheck 用一条命令找出中文内容里的排版与用词问题，并能自动修复其中大部分：

```console
$ zhcheck README.md
README.md
     3:8    error   ZC001  中文与英文/数字之间应留一个空格
        > 本项目的接口使用Python编写，性能约为原来的 2 倍。
     7:11   error   ZC009  疑似误用「帐号」，规范写法为「账号」
        > 注意: 请先登录你的帐号, 然后访问官网查看详情。
        ! 金融与 IT 场景统一用「账号」

共 2 个问题（2 error / 0 warning / 0 info），涉及 1 个文件，其中 2 个可自动修复。
提示：运行 zhcheck --fix 可自动修复其中 2 个问题。
```

## 目录

- [要解决的问题](#要解决的问题)
- [目标用户](#目标用户)
- [与现有工具的区别](#与现有工具的区别)
- [功能特性](#功能特性)
- [安装](#安装)
- [快速开始](#快速开始)
- [规则列表](#规则列表)
- [配置](#配置)
- [忽略机制](#忽略机制)
- [基线：让存量项目平滑接入](#基线让存量项目平滑接入)
- [持续集成](#持续集成)
- [退出码](#退出码)
- [贡献指南](#贡献指南)
- [路线图](#路线图)
- [许可证](#许可证)

## 要解决的问题

中文技术文档、产品文案与开源项目说明普遍存在同类问题，且人工校对难以穷尽：

1. **中英混排缺空格**：写 `使用Python编写`，而规范要求 `使用 Python 编写`。
2. **标点全半角混用**：中文语境用半角逗号冒号，英文语境又混入全角标点。
3. **标点写法不规范**：省略号写成 `...` 或 `。。。`，破折号写成 `--` 或单个 `—`。
4. **易混词与错别字**：`帐号` 与 `账号`、`按装` 与 `安装`、`其它` 与 `其他` 反复出现。
5. **术语写法不统一**：同一份文档里 `Github`、`github`、`GitHub` 三种写法并存。

这些问题单看很小，但会持续消耗读者信任与团队沟通成本。更麻烦的是，**它们无法靠一次人工校对解决**——只要文档还在增长，问题就会重新出现。zhcheck 的思路是把规范固化成可执行的规则，让机器在提交与构建阶段持续把关。

## 目标用户

| 用户 | 典型场景 |
| --- | --- |
| 开源项目维护者 | 在 CI 中检查 README 与文档，避免被读者指出低级排版错误 |
| 中文技术写作者 | 检查长文、教程、公众号文案的排版一致性 |
| 文档与本地化团队 | 统一术语写法，沉淀团队自己的词表 |
| Python 项目与数据团队 | 构建环境中不希望引入 Node.js 依赖链，却需要中文检查能力 |
| 内容运营 | 检查字幕、产品文案、i18n 文案等非 Markdown 纯文本 |

## 与现有工具的区别

中文排版检查并非空白领域，已有若干成熟工具。zhcheck 的差异在于**运行环境**与**接入方式**，而不是重新发明规则：

| 工具 | 生态 | 处理对象 | 定位 |
| --- | --- | --- | --- |
| pangu.js | Node.js | 任意文本 | 自动插入空格，只改不报错，无法作为门禁 |
| zhlint | Node.js | Markdown | 格式化与检查，规则通过配置声明 |
| lint-md | Node.js | Markdown | 基于 AST 的中文 Markdown 规范检查 |
| textlint | Node.js | 任意文本 | 可插拔的自然语言检查框架，需要自行组装规则 |
| **zhcheck** | **Python 标准库** | **任意文本与 Markdown** | **零依赖、可作 CI 门禁、支持存量基线** |

具体差异：

- **零依赖**：只用 Python 标准库。Python 项目的构建环境不必为了检查中文而引入 Node.js 工具链。
- **不依赖 AST**：处理 Markdown、纯文本、字幕、i18n 文案等任意文本。代价是无法做结构化检查，换来的是对语料的零假设。
- **报错而非静默替换**：默认只报告问题并给出精确到行列的位置，需要显式加 `--fix` 才会改写文件。
- **存量友好**：内置基线机制。老项目接入时先冻结历史问题，此后只拦截新增问题。
- **规则即数据**：易混词与术语表以 JSON 维护，新增词条只需提交一行数据，不必写代码。

## 功能特性

- **12 条内置规则**，覆盖空格、标点、用词三大类，每条可单独开关与调整严重级别。
- **Markdown 感知**：自动跳过代码块、行内代码、URL、邮箱、HTML 标签与注释、链接地址、YAML front matter、分隔线、数学公式与脚注引用。
- **自动修复**：可修复规则支持 `--fix`，并迭代到收敛（例如全角字母转半角后触发的中英混排空格会被一并修正）。
- **三种输出格式**：人类可读文本、`json`、以及 GitHub Actions 注解（`github`）。
- **多种输入**：文件、目录、glob 表达式，或从标准输入读取以便接入管道。
- **编码自动探测**：支持 UTF-8（含 BOM）、GB18030 与 UTF-16；写回时保留原编码与换行符。
- **精确退出码**：可按 `error`、`warning`、`info` 三档阈值决定是否让构建失败。

## 安装

需要 Python 3.9 或更高版本，无第三方依赖。

项目尚未发布到 PyPI，当前可从 GitHub Release 或源码安装：

```console
# 从 GitHub Release 安装 wheel
$ pip install https://github.com/ZTLNB/zhcheck/releases/download/v0.1.0/zhcheck-0.1.0-py3-none-any.whl

# 用 pipx 装成独立命令行工具
$ pipx install https://github.com/ZTLNB/zhcheck/releases/download/v0.1.0/zhcheck-0.1.0-py3-none-any.whl

# 从源码安装
$ git clone https://github.com/ZTLNB/zhcheck.git
$ cd zhcheck
$ pip install .
```

PyPI 发布正在准备中，届时可直接 `pipx install zhcheck`。

参与开发时安装开发依赖：

```console
$ git clone https://github.com/ZTLNB/zhcheck.git
$ cd zhcheck
$ pip install -e ".[dev]"
```

## 快速开始

```console
# 检查当前目录下所有 Markdown 与文本文件
$ zhcheck

# 检查指定文件或目录
$ zhcheck README.md docs/

# 自动修复
$ zhcheck . --fix

# 先看看会改什么，不写回文件
$ zhcheck . --fix --dry-run

# 从标准输入读取（常用于管道）
$ git diff --cached --name-only | zhcheck - --stdin-filename CHANGELOG.md

# 输出 JSON，供其他工具消费
$ zhcheck docs/ --format json

# 输出 GitHub Actions 注解，问题会直接标注在 PR 的 diff 上
$ zhcheck docs/ --format github

# 查看全部规则
$ zhcheck --list-rules

# 在当前目录生成配置模板
$ zhcheck --init
```

修复前后的对比：

```diff
- 本项目的接口使用Python编写,性能约为原来的 2 倍。
+ 本项目的接口使用 Python 编写，性能约为原来的 2 倍。

- 请先登录你的帐号,然后访问官网查看详情。。。
+ 请先登录你的账号，然后访问官网查看详情……
```

## 规则列表

| 规则 | 级别 | 分类 | 可修复 | 说明 |
| --- | --- | --- | --- | --- |
| ZC001 | error | 空格 | 是 | 中文与英文、数字相邻时缺少空格 |
| ZC002 | error | 标点 | 是 | 中文语境使用半角逗号、分号、冒号、问号、叹号 |
| ZC003 | warning | 标点 | 是 | 全角标点被纯英文或数字夹在中间 |
| ZC004 | error | 标点 | 是 | 重复标点，例如 `，，`、`。。`、`！！` |
| ZC005 | warning | 标点 | 是 | 省略号写成 `...` 或 `。。。` |
| ZC006 | warning | 标点 | 是 | 破折号写成 `--` 或单个 `—` |
| ZC007 | warning | 标点 | 是 | 包裹中文时使用半角括号或半角引号 |
| ZC008 | info | 空格 | 是 | 数字与单位之间缺少空格（默认关闭） |
| ZC009 | error | 用词 | 是 | 易混词与错别字，词表内置 157 条 |
| ZC010 | warning | 用词 | 是 | 术语大小写与写法不统一，词表内置 101 条 |
| ZC011 | info | 空格 | 是 | 中文之间出现连续多个空格 |
| ZC012 | warning | 标点 | 是 | 输入法误切换导致的全角字母或数字 |

ZC009 与 ZC010 的词表存放在 `src/zhcheck/data/` 下的 JSON 文件中，每条记录包含错误写法、规范写法、严重级别与可选的语境说明。

## 配置

配置按以下顺序查找，先找到的生效：`.zhcheckrc.json`、`.zhcheckrc`、`zhcheck.json`，以及 `pyproject.toml` 中的 `[tool.zhcheck]` 段。查找范围从当前目录逐级向上。

```json
{
  "include": ["**/*.md", "**/*.markdown", "**/*.txt"],
  "exclude": [".git/**", "node_modules/**", "**/.venv/**", "CHANGELOG.md"],
  "mode": "auto",
  "fail_on": "error",
  "rules": {
    "ZC008": { "enabled": true, "severity": "info" },
    "ZC011": { "enabled": false }
  },
  "confusables": { "登陆系统": "登录系统" },
  "terms": { "SpringBoot": "Spring Boot" },
  "exceptions": ["v\\d+\\.\\d+"]
}
```

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `include` | 字符串数组 | 目录遍历时纳入的文件 glob，支持 `**` |
| `exclude` | 字符串数组 | 排除的 glob，匹配到目录时整目录跳过 |
| `mode` | 字符串 | `auto`、`markdown` 或 `text`，默认按扩展名判断 |
| `fail_on` | 字符串 | 退出码阈值：`error`、`warning`、`info` 或 `none` |
| `rules` | 对象 | 按规则 ID 覆盖 `enabled` 与 `severity` |
| `disabled_rules` | 字符串数组 | 批量禁用规则 |
| `confusables` | 对象 | 追加或覆盖易混词，值为规范写法 |
| `terms` | 对象 | 追加或覆盖术语写法 |
| `exceptions` | 字符串数组 | 正则表达式，命中的文本片段不参与检查 |

命令行参数优先于配置文件。显式写在命令行上的文件总是被检查，不受 `include` 与 `exclude` 限制。

> **Python 3.9 与 3.10 的注意点**：读取 `pyproject.toml` 依赖标准库 `tomllib`，它自 Python 3.11 起才提供。在这两个版本上请改用 `.zhcheckrc.json`，或安装可选依赖 `tomli`（`pip install "zhcheck[toml]"`）。否则 zhcheck 会输出一条配置警告并忽略该配置节，而不是静默失效。

## 忽略机制

在文件中用指令精确控制检查范围，支持 HTML 注释与裸指令两种写法：

```markdown
<!-- zhcheck-disable-file ZC009 -->
<!-- zhcheck-disable-next-line ZC001 -->
<!-- zhcheck-disable ZC001,ZC002 -->
<!-- zhcheck-enable -->
```

- `zhcheck-disable-file`：整个文件禁用指定规则，不写规则 ID 表示禁用全部。
- `zhcheck-disable-next-line`：仅下一行禁用。
- `zhcheck-disable` 与 `zhcheck-enable`：成对使用，控制一段区间。

## 基线：让存量项目平滑接入

老项目直接接入检查器时，历史问题往往有成千上万条，会淹没真正需要关注的新增问题。基线机制解决这个矛盾：

```console
# 1. 首次接入：把当前全部问题写入基线文件
$ zhcheck . --write-baseline

# 2. 之后每次检查，历史问题被自动抑制
$ zhcheck .
未发现问题。

# 3. 新增的问题照常报错
$ zhcheck .
docs/new.md
    12:5    error   ZC001  中文与英文/数字之间应留一个空格

共 1 个问题（1 error / 0 warning / 0 info），涉及 1 个文件，其中 1 个可自动修复。
已按基线抑制 1247 个存量问题。
```

基线文件按「文件路径 + 规则 ID + 行内容指纹」记录，因此修改无关行不会导致基线失效。默认路径为 `.zhcheck-baseline.json`，可用 `--baseline` 指定，用 `--no-baseline` 临时忽略。

## 持续集成

GitHub Actions 示例，检出后即可运行，不需要安装任何依赖：

```yaml
name: zhcheck

on: [push, pull_request]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install zhcheck
      - run: zhcheck . --format github
```

配合 `--format github`，问题会以注解形式直接显示在 PR 的改动行上。

其他场景：

```console
# pre-commit 钩子
$ zhcheck $(git diff --cached --name-only --diff-filter=ACM)

# 只检查本次改动的文件，并把错误级别调高到 warning
$ zhcheck $(git diff --name-only HEAD~1) --fail-on warning
```

## 退出码

| 退出码 | 含义 |
| --- | --- |
| 0 | 未发现问题，或问题严重级别低于 `fail_on` 阈值 |
| 1 | 存在达到阈值的问题 |
| 2 | 用法错误或配置不合法 |

## 贡献指南

欢迎提交问题与改动，具体流程见 [CONTRIBUTING.md](CONTRIBUTING.md)。最容易上手的两类贡献：

1. **补充词表**：在 `src/zhcheck/data/confusables.json` 或 `terms.json` 中追加一条记录即可，不需要写代码。请附上依据，例如《现代汉语词典》的推荐写法。
2. **新增规则**：在 `src/zhcheck/rules/` 下实现检查函数并注册，同时补充单元测试与文档中的规则表。

本地开发：

```console
$ git clone https://github.com/ZTLNB/zhcheck.git
$ cd zhcheck
$ python -m unittest discover -v
$ python -m zhcheck . --fix --dry-run
```

项目自身也遵循自己定义的规范，CI 会检查仓库内的 Markdown 文档。

## 路线图

按优先级排列的后续方向：

- [ ] **全角标点周围的空格检查**：补一条规则，处理「中文（示例） 后续」这类全角标点两侧残留空格的问题。
- [ ] **术语一致性检查**：在同一份文档内检测同一概念的不同表述，而不仅是固定词表替换。
- [ ] **可选的模型辅助校对**：以插件形式接入大模型，用于识别规则难以覆盖的语义问题；保持默认关闭，不引入运行时依赖。
- [ ] **编辑器集成**：提供 VS Code 扩展与语言服务器，实现保存时检查与快速修复。
- [ ] **共享词表仓库**：把团队级术语表独立成可订阅的包，支持按行业分发。
- [ ] **更多语种**：抽象规则层，支持繁体中文与日文的排版规范。
- [ ] **性能优化**：面向超长文档的增量扫描与并行处理。

## 许可证

本项目基于 [MIT 许可证](LICENSE) 发布。
