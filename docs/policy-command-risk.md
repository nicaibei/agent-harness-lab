# Policy 命令风险与审批实验

## 为什么要做命令策略

文件路径策略只能保护文件工具。只要 Harness 将命令执行工具暴露给 Agent，就还需要判断命令本身的风险。命令策略不能只看模型提示，而要在命令工具执行前检查。

## 当前风险分类

| 风险级别 | 示例 | Policy 行为 |
|---|---|---|
| `safe` | `pytest`、`python -m pytest -q` | 直接允许 |
| `review` | `pip install requests`、普通 `git` 命令 | 调用审批回调；没有批准就拒绝 |
| `dangerous` | `del safe.txt`、`rm -rf workspace`、管道、重定向 | 直接拒绝 |

命令分类在 `classify_command()` 中完成。空命令、解析失败、Shell 操作符和破坏性命令默认按危险处理。这个“默认拒绝”是因为命令执行的潜在影响通常大于读取一个普通文件。

## 审批链路

```text
Agent 生成 run_command
  -> classify_command(command)
  -> safe: 直接执行
  -> review: 调用 approval_callback
       -> true: 执行
       -> false 或没有回调: 返回结构化拒绝
  -> dangerous: 直接返回结构化拒绝
```

本轮没有开放真实任意 Shell。集成测试使用一个不会修改宿主机的假 `run_command` 工具，只验证 Policy 是否在工具执行之前做出正确决定。这是学习和设计阶段的刻意边界。

## 你需要掌握的工程结论

1. 风险分级不是“允许/禁止”二元开关，而是允许、需要人审、直接拒绝三种路径。
2. 审批回调是 Harness 与外部审批系统之间的接口；将来可以接 CLI 确认、Web UI 或人工队列。
3. 策略拒绝要记录风险级别和原因，否则无法分析 Agent 是误触发危险命令，还是缺少审批。
4. 当前分类器是保守的最小版本，不能替代真正的容器沙箱、网络隔离和操作系统权限控制。

## 验证

- 单元测试：[tests/test_policy.py](../tests/test_policy.py)
- Agent 图集成测试：[tests/test_policy_commands_integration.py](../tests/test_policy_commands_integration.py)
- 策略实现：[harness/policy.py](../harness/policy.py)

本轮完整测试结果：19 passed。
