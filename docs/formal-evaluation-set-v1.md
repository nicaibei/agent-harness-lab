# Formal Evaluation Set v1

## 目的

把已有实验整理成第一版可重复评估集，并明确 train 与 holdout 的边界。清单是评估入口，不等于所有任务都已经用真实模型重复运行。

任务清单位于 [formal_tasks.json](../evals/formal_tasks.json)，由 [formal_task_manifest.py](../evals/formal_task_manifest.py) 校验。

## 任务组成

当前 v1 有 30 个唯一任务：

| split | 数量 | 内容 |
| --- | ---: | --- |
| `train` | 16 | 10 个 calculator Baseline，4 个单文件 Recovery，2 个 Checkpoint 任务 |
| `holdout` | 14 | 5 个跨文件/仓库 Recovery，3 个环境任务，6 个 Policy 安全任务 |

覆盖的 strata：`baseline`、`recovery`、`cross_file`、`repository_integration`、`environment`、`runtime`、`security`。

## 防泄漏规则

- 同一个 `project` 不能同时出现在 train 和 holdout；
- 每个任务有唯一 ID、固定 fixture、固定 evaluator 和预期文件集合；
- holdout 任务不用于 Prompt、Policy 或 Recovery 参数优化；
- 安全、环境和 Runtime 任务保留独立 strata，不与普通代码修复成功率混合；
- `status=validated_offline` 只表示 Harness 离线回归通过，不表示真实模型成功率。

## 当前证据边界

- Baseline 的 10 个 calculator 任务已有历史真实运行记录；
- 9 个 Recovery fixture 已有至少一次真实运行记录，部分任务有重复运行；
- 3 个环境任务已经分别完成环境停止、受限准备和版本冲突真实运行；
- Checkpoint v1/v2 和 Policy 任务是离线验证；
- 目前还没有用统一 runner 对 30 个任务跑出同一批次的可比模型指标。

因此本文件完成的是“任务集和 split 冻结”，不是最终评测报告。下一步应实现统一 manifest runner，在不改变 split 的前提下分别运行 Baseline、Policy/Recovery 增强版本，并记录成本、延迟、工具调用次数和 `run.v1` 产物。
