# Baseline 十任务运行报告

本报告记录 Baseline 任务集扩展到 10 个任务后的最新有效运行结果。每个任务都从 `examples/tiny_python_project/` 的干净副本开始，运行器保存独立的 `run.json` 和 `diff.patch`。

## 结果矩阵

| 任务 ID | `run_id` | 模型 | `completed` | `tests_passed` | `execution_error` | 测试运行次数 | diff | 事件数 |
|---|---|---|---:|---:|---|---:|---:|---:|
| `calculator-add-floats` | `20261105T065422Z-83adadc7` | `qwen3.6-plus` | `true` | `true` | `null` | 1 | 276 字符 | 历史记录 |
| `calculator-subtract-negative` | `20261105T070213Z-d1386853` | `qwen3.6-plus` | `true` | `true` | `null` | 1 | 279 字符 | 历史记录 |
| `calculator-divide-fraction` | `20261105T070349Z-ee213abe` | `qwen3.6-plus` | `true` | `true` | `null` | 1 | 281 字符 | 历史记录 |
| `calculator-add-negative-mixed` | `20261105T073653Z-743842e9` | `deepseek-flash` | `true` | `true` | `null` | 1 | 277 字符 | 7 |
| `calculator-subtract-floats` | `20261105T074214Z-98aa7c64` | `deepseek-flash` | `true` | `true` | `null` | 1 | 285 字符 | 7 |
| `calculator-divide-negative` | `20261105T074257Z-9fa846bd` | `deepseek-flash` | `true` | `true` | `null` | 1 | 338 字符 | 7 |
| `calculator-divide-zero-numerator` | `20261105T074341Z-d434b73d` | `deepseek-flash` | `true` | `true` | `null` | 1 | 319 字符 | 7 |
| `calculator-add-rejects-text` | `20261105T074423Z-4ae90f63` | `deepseek-flash` | `true` | `true` | `null` | 1 | 702 字符 | 7 |
| `calculator-multiply` | `20261105T074508Z-b3f2e6e6` | `deepseek-flash` | `true` | `true` | `null` | 1 | 773 字符 | 7 |
| `calculator-subtract-zero` | `20261105T074552Z-c8963e09` | `deepseek-flash` | `true` | `true` | `null` | 1 | 269 字符 | 7 |

按每个任务的最新有效记录统计：

- 10/10 `completed=true`；
- 10/10 `tests_passed=true`；
- 10/10 `execution_error=null`；
- 10/10 生成了非空 diff；
- 每个任务都只使用了一次 `run_tests`。

## 修改类型

八个任务只新增了边界或回归测试，验证 Agent 能理解已有实现并保持最小修改。`calculator-add-rejects-text` 同时修改了 `calculator.py` 和测试文件，增加数值类型检查；`calculator-multiply` 增加了函数、测试导入和测试用例，验证了实现变更与测试变更可以在同一隔离工作区内完成。

## 模型切换

最初三个任务使用 Qwen，并保留原运行记录。新增七个任务使用 DeepSeek 的 OpenAI 兼容接口：

```dotenv
DEEPSEEK_MODEL=deepseek-flash
DEEPSEEK_BASE_URL=https://api.deepseek.com
```

第一次使用 `DeepSeek-V4.1-Flash` 时，服务返回 400，并明确要求使用 `deepseek-flash` 或 `deepseek-v4-pro`。修正模型 ID 后，`calculator-add-negative-mixed` 重跑成功；失败记录保留在失败分析文档中。

## Baseline 验收判断

十任务运行已经满足阶段 1 的核心验收条件：任务集达到 10 个、至少 3 个任务成功、每个有效运行都有结构化结果和 diff、DeepSeek 下的事件日志已经在新增任务中验证。任务仍然是小型计算器项目，不能代表真实跨模块仓库的复杂度；下一阶段应把 Policy Middleware 的安全测试和更复杂的故障场景作为新的独立实验。
