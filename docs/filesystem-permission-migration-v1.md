# FilesystemMiddleware 权限迁移实验 v1

## 实验目的

验证 Harness 能否迁移到真实 SDK 的 `FilesystemMiddleware`，并在隐藏测试位于 workspace 外时恢复文件权限边界。目标是区分“Agent 完成调用”与“权限行为正确且修改范围合规”。

## 失败模式与故障注入

实验从 `D:/langgraph_learning/deepagent/libs/deepagents/deepagents/middleware/filesystem.py` 复制真实源码到隔离 workspace，只注入一处权限检查缺陷：将 `_permission_error()` 中的直接权限判断替换为恒假条件。这样受保护路径可能被错误放行。

隐藏测试检查三个行为：

- 读取 `/secrets/key.txt` 必须被拒绝；
- 写入 `/secrets/key.txt` 必须被拒绝；
- 写入 `/workspace/note.txt` 必须允许。

隐藏测试不在 Agent workspace 内，允许修改的文件只有 `filesystem.py`。

## 控制变量与成功标准

- 使用真实 `FilesystemMiddleware` 源码副本和真实 `FilesystemBackend`；
- 只验证读写权限边界，不扩展到其他 middleware 或操作系统权限；
- 测试最多运行两次；
- 首次测试必须失败，修复后最终测试必须通过；
- 实际 diff 必须只包含 `filesystem.py`，且不能修改隐藏测试或其他 evaluator-owned 文件；
- `completed`、`tests_passed`、`diff_scope_valid` 和 `task_success` 分开记录。

## 离线结果

运行 ID：`20261110T061159Z-2a38231f`。

| 指标 | 结果 |
| --- | --- |
| 模型 | Fake Model |
| 模型调用 | 0 次外部模型调用 |
| 首次隐藏测试 | `2 failed, 1 passed` |
| 修复后隐藏测试 | `3 passed` |
| 实际修改文件 | `filesystem.py` |
| 越界修改 | 无 |
| `completed` | `true` |
| `tests_passed` | `true` |
| `diff_scope_valid` | `true` |
| `task_success` | `true` |

修复只恢复了 `_check_fs_permission(...) == "deny"` 的直接检查。Harness 记录了首次测试失败、Recovery 编辑、最终测试通过和 diff 范围检查；运行产物保留在对应 `runs/migration-permissions/<run_id>/` 目录。

## 真实评测状态

真实 DeepSeek 运行尚未完成。执行命令被自动安全审查阻止，因为它会把新的真实 `FilesystemMiddleware` 源码发送到外部模型服务。当前离线结果不能替代真实模型结果，也不计入真实模型 Recovery 成功率。

## 学习结论与限制

本实验说明权限迁移的成功判定必须同时看隐藏行为、最终测试和修改范围；只看 `completed=true` 或 diff 都不够。离线 Fake Model 证明 Harness 的判定链路和外部隐藏测试设计可用，但不能证明 DeepSeek 能自行定位该真实模块问题。当前样本只有一个故障和一次离线运行，不能外推到其他权限规则或大型仓库。
