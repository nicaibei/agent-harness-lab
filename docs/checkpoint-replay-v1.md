# Checkpoint/Replay v1 实验记录

## 实验目标

Baseline、Policy 和 Recovery 已经能保存最终结果、限制工具调用并处理部分失败。本阶段继续解决两个问题：

1. Agent 在运行中途暂停后，能否从同一条线程继续执行；
2. 运行结束后，能否不重新调用模型或工具，只根据事件日志复盘过程。

## 设计判断

本轮采用两个互补的机制：

| 机制 | v1 选择 | 目的 |
| --- | --- | --- |
| Runtime checkpoint | LangGraph `InMemorySaver` | 验证真实 Agent graph 的状态保存和恢复 |
| Replay | 事件日志摘要 | 无副作用地复盘已经发生的运行 |

使用 `InMemorySaver` 是有意的学习取舍。它不需要新增数据库依赖，适合离线测试，但不能在进程退出后恢复。之后若需要跨进程恢复，再评估 SQLite 或其他持久化 checkpointer。

Replay 先做成事件重放，而不是再次调用模型。再次调用模型属于 rerun，模型可能选择不同工具、产生不同文本，不能作为确定性的历史复盘。

## 为什么暂停在工具边界

模型调用前后确实会改变 Agent 状态，但模型调用本身受网络和模型输出影响，暂停在这个位置不容易单独证明副作用是否已经发生。

本轮暂停在：

```text
模型已经生成 tool_call
  ↓
checkpoint 保存当前 graph 状态
  ↓
工具还没有执行
  ↓
恢复后审批并执行工具
```

这样可以同时观察模型的决定和工具副作用之间的边界。测试在暂停后确认工具调用次数为 0，在恢复后确认工具只执行一次。

## 实现位置

### Checkpoint 摘要

`harness/checkpoint.py` 中的 `summarize_checkpoints()` 从 checkpointer 读取当前线程的元数据，并生成 JSON 安全的摘要：

- `thread_id`：运行线程 ID；
- `checkpoint_count`：当前线程保存的 checkpoint 数量；
- `latest_checkpoint_id`：最新 checkpoint 标识；
- `persistence`：v1 标记为 `in-memory`。

`agent_app/baseline.py` 为每次运行创建一个 `InMemorySaver`，并使用：

```python
run_config = {"configurable": {"thread_id": run_id}}
```

同一个 `run_id` 同时关联运行目录和 LangGraph 线程，因此运行报告、工作区和 checkpoint 可以对应起来。

Baseline 现在额外保存：

```text
runs/<run-id>/checkpoint.json
runs/<run-id>/replay.json
```

`run.json` 也保留 `checkpoint` 和 `replay` 字段，方便只读取一个文件进行分析。

### 事件 Replay

`replay_events()` 只遍历已经保存的事件，不调用模型、不调用工具、不修改工作区。它重建：

- 事件顺序；
- Policy 拒绝次数；
- Recovery 重试次数；
- 测试运行次数；
- 最终 `completed` 和 `tests_passed` 状态。

因此 Replay 回答的是“这次运行记录显示发生了什么”，而不是“重新运行一次后会发生什么”。

## 实际调用链

```text
create_deep_agent(checkpointer=InMemorySaver())
  ↓
agent.invoke(..., config={thread_id: run_id})
  ↓
模型生成 record_step 工具调用
  ↓
interrupt_on 暂停，写入 checkpoint
  ↓
Command(resume={"decisions": [{"type": "approve"}]})
  ↓
同一 thread_id 恢复
  ↓
工具执行一次，模型返回 finished
```

## 验证结果

新增的 `tests/test_checkpoint_replay.py` 包含两个离线场景：

1. Replay 对包含 Policy、Recovery、测试和结束事件的列表生成摘要，证明它不需要执行副作用；
2. Agent graph 在工具边界暂停，确认暂停时工具未执行，恢复后同一线程完成并产生更多 checkpoint。

当前全量测试结果：

```text
28 passed
```

测试运行同时出现一个 Windows 环境警告：pytest 无法写入已有 `.pytest_cache` 目录。它不影响测试结果，也不是本次 Checkpoint/Replay 逻辑产生的失败；后续可单独清理目录权限或调整缓存位置。

## 学到的工程结论

1. `thread_id` 是恢复同一条 LangGraph 运行的关键标识，不能每次恢复时重新生成。
2. Checkpoint 保存运行状态，事件日志保存可观察过程，工作区快照保存文件状态；三者不能互相替代。
3. Replay 和 rerun 的目标不同。Replay 要求无副作用和可解释，rerun 允许重新决策并可能得到不同结果。
4. v1 的 `InMemorySaver` 只证明机制，不提供跨进程持久化能力。
5. 在工具执行前暂停可以验证“决定已经产生但副作用还未发生”的安全边界。

## 小练习

进入下一阶段前，可以用自己的话回答：

1. 如果恢复时换了一个新的 `thread_id`，为什么不能继续原来的 Agent 状态？
2. 为什么 `replay.json` 不应该再次调用 DeepSeek？
3. 如果 `checkpoint_count` 增加，但 `diff.patch` 为空，说明了什么？

下一步可以在不改变 Replay 语义的前提下，评估持久化 checkpoint，或开始比较 Baseline、Policy、Recovery 和 Checkpoint/Replay 组合的评测指标。
