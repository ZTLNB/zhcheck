# 贡献指南

感谢你有兴趣改进 zhcheck。本文档说明如何搭建开发环境、运行测试，以及提交改动的流程。

## 可以贡献什么

| 类型 | 难度 | 说明 |
| --- | --- | --- |
| 补充词表 | 低 | 向 JSON 词表追加条目，不需要写代码 |
| 报告误报与漏报 | 低 | 提供最小复现文本，这是最有价值的反馈 |
| 新增规则 | 中 | 实现检查函数、注册规则、补充测试与文档 |
| 改进文档 | 低 | 修正说明、补充示例 |
| 优化性能 | 中 | 面向超长文档的扫描效率 |

## 开发环境

需要 Python 3.9 或更高版本，无运行时依赖。

```console
$ git clone https://github.com/ZTLNB/zhcheck.git
$ cd zhcheck
$ python -m venv .venv
$ .venv/Scripts/activate     # Windows
$ source .venv/bin/activate  # macOS 与 Linux
$ pip install -e ".[dev]"
```

项目不引入第三方运行时依赖，请勿在 `dependencies` 中新增依赖。仅检查类工具可以放在 `dev` 额外依赖中。

## 运行测试与检查

```console
# 运行全部单元测试
$ python -m unittest discover -v

# 静态检查
$ ruff check src tests

# 用 zhcheck 检查仓库自己的文档（自举）
$ python -m zhcheck . --format text
```

提交前请确保三项全部通过。CI 会在 Python 3.9 至 3.13、Linux 与 Windows、macOS 上运行同一套检查。

## 新增词表条目

这是最容易参与的贡献方式。词表位于 `src/zhcheck/data/`：

- `confusables.json`：易混词与错别字。
- `terms.json`：技术术语的规范写法。

新增条目只需追加一行：

```json
{ "wrong": "帐号", "right": "账号", "severity": "error", "note": "金融与 IT 场景统一用「账号」" }
```

字段说明：

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `wrong` | 是 | 错误写法 |
| `right` | 是 | 规范写法 |
| `severity` | 否 | `error`、`warning` 或 `info`，缺省为 `error` |
| `note` | 否 | 语境说明，会在检查输出中展示 |

提交词表改动时请附上依据，例如《现代汉语词典》的推荐写法，或权威技术文档中的通用拼写。**语境依赖的条目请使用 `warning` 级别**，例如 `登陆` 在「台风登陆」中是正确的，不应判为错误。

## 新增规则

1. 在 `src/zhcheck/rules/` 下选择合适的模块（`spacing.py`、`punctuation.py` 或 `terms.py`）。
2. 实现检查函数，签名为 `(ctx: ScanContext) -> list[Issue]`。
3. 在模块的 `RULES` 元组中注册规则，ID 按 `ZC###` 顺序编号。
4. 在 `tests/` 下补充单元测试，至少覆盖正例、反例与自动修复结果。
5. 更新 `README.md` 中的规则列表。

检查函数必须遵守两条约定：

- **只在未被屏蔽的区间上报告问题**：用 `ctx.active(start, end)` 判断，避免误报代码块与 URL。
- **上下文判断使用 `is_cn_context` 而不是 `is_han`**：被中文标点包裹的片段（例如 `「...」`）同样属于中文语境。

```python
def check_something(ctx: ScanContext) -> list[Issue]:
    issues: list[Issue] = []
    for match in _RE_PATTERN.finditer(ctx.text):
        start, end = match.span()
        if not ctx.active(start, end):
            continue
        issues.append(
            ctx.emit(
                "ZC013",
                start,
                end,
                "问题描述",
                fixes=[Fix(start, end, "替换文本")],
            )
        )
    return issues
```

自动修复必须满足**幂等**要求：修复后的文本再次检查时，不应再产生同一规则的告警。若一轮修复会暴露新的可修复问题，命令行工具会自动迭代到收敛，但规则本身仍应避免自相矛盾。

## 提交信息与分支

- 分支命名：`feat/xxx`、`fix/xxx`、`docs/xxx`、`data/xxx`。
- 提交信息使用祈使句，首行不超过 72 个字符，例如 `feat: 新增全角标点周围空格规则`。
- 一个提交只做一件事。词表改动与代码改动请分开提交，便于审阅。

## 提交改动

```console
$ git checkout -b feat/my-change
$ git add .
$ git commit -m "feat: 新增某某规则"
$ git push origin feat/my-change
```

然后在 GitHub 上发起 Pull Request。请在描述中说明：

1. 要解决的问题与真实场景。
2. 改动前后的行为对比，附最小复现示例。
3. 是否可能引入误报，以及如何规避。

## 报告问题

报告误报或漏报时，请尽量提供：

- 触发问题的**最小文本片段**（不要只给截图，文本才能直接用于复现）。
- `zhcheck --version` 的输出。
- 相关配置文件内容（如果使用了 `.zhcheckrc.json`）。
- 期望行为与实际行为。

## 行为准则

请保持讨论聚焦于技术问题，尊重不同意见。评审意见针对代码与设计，而非个人。任何形式的骚扰与歧视都不被接受。

## 许可证

提交贡献即表示你同意以 [MIT 许可证](LICENSE) 授权你的改动。
