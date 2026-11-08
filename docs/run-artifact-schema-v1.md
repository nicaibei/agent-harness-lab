# Run Artifact Schema v1

## 目的

从本次提交开始，新的 Agent 运行产物使用版本化的 `run.v1` envelope。它把任务结果、测试证据、事件轨迹、diff 和 replay 放进可比较的固定边界，避免把 `completed`、最后一次测试或 diff 单独当成成功标准。

历史 `run.json` 没有 `schema_version` 的记录继续保留，评测工具把它们视为 legacy artifact；本 schema 不改写历史运行目录。

## 文件关系

每个运行目录可以包含：

| 文件 | 约定 |
| --- | --- |
| `run.json` | 主运行记录，版本为 `run.v1` |
| `diff.patch` | 与 `run.json.diff` 相同的统一 diff 文本 |
| `replay.json` | `replay.v1` 的事件汇总副本 |
| `checkpoint.json` | 可选的 checkpoint 摘要 |
| `checkpoint-store.json` | 仅跨进程实验使用的持久化 checkpoint 原始存储 |

## `run.json` 顶层字段

必需字段：

| 字段 | 类型 | 语义 |
| --- | --- | --- |
| `schema_version` | string | 固定为 `run.v1` |
| `run_id` | string | 一次运行的唯一标识 |
| `task_id` | string | 任务定义标识 |
| `scenario` | string | 运行场景，例如 baseline 或 recovery |
| `completed` | boolean | Agent 生命周期是否正常结束 |
| `tests_passed` | boolean | 最后一次已解析测试结果是否通过 |
| `execution_error` | string or null | Harness、模型或执行阶段异常 |
| `test_runs` | array | 工具返回的测试结果 JSON 字符串，按调用顺序保存 |
| `diff` | string | 生产工作区统一 diff；空字符串表示没有生产 diff |
| `events` | array | 按时间顺序排列的 `event.v1` 事件 |
| `replay` | object | `replay.v1` 的无副作用汇总 |

常见可选字段包括 `started_at`、`finished_at`、`model`、`base_url`、`outcome`、`baseline_gate`、环境恢复字段和 `checkpoint`。实验可以增加场景字段，但不能改变上述字段的含义。

Checkpoint 实验历史上使用过 `production_diff`；从 schema v1 开始，评测统一读取 `diff`。旧字段可以保留用于阅读，但不再作为机器判定入口。

## 事件约定

每个事件至少包含：

```json
{
  "schema_version": "event.v1",
  "event": "test_run",
  "timestamp": "2026-11-08T06:13:48.700919+00:00"
}
```

事件名称由场景扩展，当前稳定名称包括：`run_started`、`workspace_created`、`agent_started`、`policy_decision`、`test_run`、`recovery_retry`、`recovery_success`、`recovery_failure`、`environment_failure_detected`、`run_waiting`、`process_restarted`、`run_resumed`、`agent_finished`、`diff_created`、`checkpoint_summary` 和 `run_finished`。事件专属字段放在同一个对象中，未知字段必须被读取方忽略。

## `replay.v1`

`replay_events()` 只读取事件，不调用模型、工具或测试。返回字段固定为：

| 字段 | 语义 |
| --- | --- |
| `schema_version` | 固定为 `replay.v1` |
| `mode` | 固定为 `events-only` |
| `event_count` | 事件总数 |
| `event_names` | 事件名称顺序 |
| `policy_denials` | Policy 拒绝次数 |
| `recovery_retries` | Recovery 重试次数 |
| `test_runs` | 测试事件次数 |
| `completed` | 最后一个 `run_finished` 的生命周期结果 |
| `tests_passed` | 最后一个 `run_finished` 的测试结果 |

## 判定规则

- `completed=true` 只表示运行正常结束，不表示任务正确。
- `tests_passed=true` 只表示最后一次测试通过。
- 代码任务成功必须同时检查最终测试、生产 `diff`、失败分类和 Policy/环境状态。
- Recovery 成功、环境恢复和普通 Baseline 成功必须分组统计。
- Replay 是证据汇总，不会重新执行运行，也不能替代真实测试。

## 版本策略

`run.v1` 只允许增加场景可选字段，不改变必需字段含义。需要改变类型、删除字段或改变判定语义时创建 `run.v2`，并为评测聚合器增加显式迁移逻辑。
