# Formal Evaluation Split Audit v1

## 实验目的

检查冻结的 30 个正式任务是否能被统一 runner 正确分成 train 和 holdout，并确认 Runtime/Security 任务在没有模型调用时可以独立执行。这个实验验证的是评测基础设施边界，不是模型成功率。

## 失败模式

- train 与 holdout 任务被错误混合；
- 需要模型的任务被误当成离线任务；
- Runtime 或 Security 任务没有绑定离线 pytest 节点；
- 离线通过率被错误写成真实 Agent 成功率。

本轮没有注入业务代码故障，因为研究对象是 manifest 和 runner 的分组契约；故障由 split、execution mode 或 offline target 配置错误来代表。

## 控制变量与成功标准

- 使用冻结的 `evals/formal_tasks.json`；
- 分别生成 train、holdout 计划；
- 只执行 manifest 明确标记为 `harness_offline` 的 pytest 节点；
- 不调用 DeepSeek，不修改 fixture、Policy 或 Prompt；
- 计划数量、执行模式、离线目标和 `model_calls=0` 必须与预期一致。

## 结果

| 项目 | 结果 |
| --- | --- |
| train 任务数 | 16 |
| train 模型任务 | 14 |
| train 离线任务 | 2 |
| train 离线结果 | `2/2` 通过 |
| holdout 任务数 | 14 |
| holdout 模型任务 | 8 |
| holdout 离线任务 | 6 |
| holdout 离线结果 | `6/6` 通过 |
| 离线模型调用 | `0` |

产物：

- `evals/reports/formal-train-plan-v1.json`
- `evals/reports/formal-holdout-plan-v1.json`
- `evals/reports/formal-offline-train-v1.json`
- `evals/reports/formal-offline-holdout-v1.json`

## 结论

统一 runner 正确保持了 train/holdout 的任务边界，并把 Runtime/Security 任务限制在离线 Harness 回归。离线结果只能证明 Harness 回归通过，不能证明 14 个 train 模型任务或 8 个 holdout 模型任务的真实成功率。

下一步应在明确的外部模型数据授权下，分批运行 train 模型任务；holdout 继续保持冻结，不用于 Prompt 或 Policy 调参。
