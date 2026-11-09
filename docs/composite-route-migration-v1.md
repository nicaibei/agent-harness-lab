# CompositeBackend 真实模块迁移实验 v1

## 实验目的

验证当前 Agent Harness 的评测方法能否迁移到真实 SDK 模块，而不只适用于手工设计的 calculator fixture。本轮选择 `deepagent/libs/deepagents/deepagents/backends/composite.py`，因为它负责按路径把文件操作分配到不同 Backend，路由错误会改变数据持久化和隔离语义。

## 研究问题

当真实 `CompositeBackend` 的路由边界出现一个回归缺陷时，Harness 能否让 Agent 根据 workspace 外的隐藏测试完成修复，并同时证明写入了正确的 Backend？

## 故障与任务

实验从 upstream checkout 复制真实 `composite.py` 到隔离 workspace，只注入一处故障：把 `/memories/` 的带斜杠边界判断改成不带边界的前缀判断。这样 `/memories-old/note.txt` 会被错误地送入 `/memories/` routed Backend。

Fake Model 的固定轨迹是：

1. 调用外部 `run_tests`；
2. 只编辑 `composite.py`，恢复路径边界判断；
3. 再次调用外部 `run_tests`；
4. 结束任务。

隐藏测试位于 `evals/hidden_tests/test_composite_route_migration.py`，不复制进 Agent workspace，验证两个不变量：

- `/memories/note.txt` 必须写入 routed Backend；
- `/memories-old/note.txt` 必须写入 default Backend。

## 控制变量与判定

- 只验证 `write/read` 路由，不扩展到 `grep`、`glob` 或异步路径；
- 使用真实 upstream 模块源码副本和真实 `CompositeBackend` 类；
- 使用确定性的 Fake Model，不调用 DeepSeek、不联网；
- 测试预算固定为两次；
- 允许修改文件固定为 `composite.py`；
- 成功要求首次测试失败、最终测试通过、实际 diff 在允许范围内。

## 离线结果

运行 ID：`20261108T090355Z-8c7c6762`

| 指标 | 结果 |
| --- | --- |
| 模型调用 | `0`，Fake Model |
| 首次隐藏测试 | `2 failed` |
| 修复后隐藏测试 | `2 passed` |
| 实际修改文件 | `composite.py` |
| 越界修改 | 无 |
| `diff_scope_valid` | `true` |
| `task_success` | `true` |
| 事件数 / replay 事件数 | `8 / 8` |

完整摘要见 [composite-route-migration-v1.json](../evals/reports/composite-route-migration-v1.json)，运行目录保留 `run.json`、`diff.patch`、`replay.json` 和隔离 workspace。

## 真实 DeepSeek 结果

在单独授权后，使用同一故障、同一隐藏测试和同一测试预算运行了一次真实 Agent。运行 ID：`20261108T090526Z-99d9d7f9`。

| 指标 | 结果 |
| --- | --- |
| 模型 | `deepseek-flash` |
| 观察到的模型响应 | `9` |
| Policy 控制的工具调用 | `11` |
| 首次隐藏测试 | `2 failed` |
| 修复后隐藏测试 | `2 passed` |
| 实际修改文件 | `composite.py` |
| 越界修改 | 无 |
| `diff_scope_valid` | `true` |
| `task_success` | `true` |
| 成本 | 未记录，Provider 没有返回 usage |

真实 Agent 没有直接猜测修复，而是先检查源码、运行隐藏测试，再通过 `grep/read_file` 定位路由边界，最后把 `route_prefix.rstrip("/")` 修正为带边界的路由前缀。完整摘要见 [composite-route-migration-real-v1.json](../evals/reports/composite-route-migration-real-v1.json)。

## 学到的内容

这次迁移证明了本地 fixture 的 Harness 语义可以承载真实 SDK 模块：外部测试不仅检查返回值，还检查副作用落在哪个 Backend。离线 Fake Model 证明了 Harness 判定链路，真实 DeepSeek 运行进一步证明 Agent 在这个模块上能够先测试、定位边界并完成修复。它也说明 `completed=true` 和最终测试通过仍然不够，必须同时验证路由不变量和修改范围。

## 局限与下一步

本轮只覆盖同步 `write/read` 和一个路径边界缺陷，真实样本只有 1 次，不能代表真实模型的迁移成功率。实验通过后不自动扩展更多相似案例；下一步只有在需要回答新的问题时，才考虑单独设计 `grep/glob` 或异步路径迁移实验。
