# Agent Harness 评测汇总

- 运行尝试数：14
- 任务数：10
- 全部尝试成功率：78.6%
- 有效尝试数：11
- 有效尝试成功率：100.0%

## 失败分类

| 分类 | 次数 |
| --- | ---: |
| `model_error` | 3 |
| `success` | 11 |

## 每个任务的主要结果

`latest_valid_attempt` 排除了模型、初始化和损坏产物问题，用于观察 Agent 任务表现。

| 任务 | 尝试数 | 最新有效分类 | 测试通过 | diff 字符数 |
| --- | ---: | --- | --- | ---: |
| `calculator-add-floats` | 2 | `success` | True | 263 |
| `calculator-add-negative-mixed` | 3 | `success` | True | 277 |
| `calculator-add-rejects-text` | 1 | `success` | True | 702 |
| `calculator-divide-fraction` | 1 | `success` | True | 271 |
| `calculator-divide-negative` | 1 | `success` | True | 338 |
| `calculator-divide-zero-numerator` | 1 | `success` | True | 319 |
| `calculator-multiply` | 1 | `success` | True | 773 |
| `calculator-subtract-floats` | 1 | `success` | True | 285 |
| `calculator-subtract-negative` | 1 | `success` | True | 266 |
| `calculator-subtract-zero` | 2 | `success` | True | 276 |
