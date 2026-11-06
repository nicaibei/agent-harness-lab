# Policy 拒绝场景集成实验

## 实验目的

Policy 单元测试只能说明策略对象返回了拒绝结果。本实验进一步把策略接入真实的 `create_deep_agent` 图，使用离线假模型发出工具调用，验证危险调用在工具执行前被拦截，工作区没有发生未授权变化。

## 实际链路

```text
假模型生成 AIMessage(tool_calls)
  -> create_deep_agent
  -> AgentMiddleware.wrap_tool_call
  -> PolicyMiddleware 判断
  -> 允许：FilesystemBackend 执行
  -> 拒绝：返回 status=error 的 ToolMessage
  -> Agent 继续收到策略错误
```

测试没有调用 DeepSeek API，因此不消耗额度，也不依赖网络。它使用真实的 `FilesystemBackend` 和 Agent graph，只把模型响应替换成确定的离线响应。

## 场景与结果

| 场景 | 模型请求 | 结果 | 工作区影响 |
|---|---|---|---|
| 路径穿越 | `read_file("/../outside.txt")` | 拒绝，原因是路径不在 workspace allowlist | 无变化 |
| 敏感文件 | `read_file("/.env")` | 拒绝，原因是敏感文件不可访问 | 无变化 |
| 删除操作 | `delete("/safe.txt")` | 拒绝，原因是 delete 被 Baseline policy 禁用 | `safe.txt` 保留 |
| 预算耗尽 | 第一次读取允许，第二次读取超过 `max_tool_calls=1` | 第一次 allow，第二次 deny | 只执行一次读取 |

每个拒绝结果都是 `ToolMessage(status="error")`，并通过回调记录 `decision=deny`、工具名、原因和调用序号。预算场景还证明了策略不是在第一次调用前就整体关闭，而是允许预算内调用并在超限的那一次停止。

## 你需要掌握的工程结论

1. Prompt 中写“不要访问工作区外文件”不是执行边界；Policy 在工具调用钩子中拒绝，模型无法绕过这个检查直接执行工具。
2. `FilesystemBackend` 负责文件如何读写，Policy Middleware 负责本次调用是否被允许，两者是不同职责。
3. 拒绝必须返回结构化工具错误并记录事件，Agent 才能看到失败原因，Harness 也才能统计违规尝试。
4. 路径检查、敏感文件检查和预算检查可以组合在一个策略入口，但错误原因要保持具体，否则后续失败分析无法区分问题类型。
5. 这仍然不是操作系统沙箱。策略覆盖的是 Agent 工具调用；进程隔离、网络隔离和凭据隔离需要更强的执行环境。

## 验证位置

- 单元策略测试：[tests/test_policy.py](../tests/test_policy.py)
- Agent 图集成测试：[tests/test_policy_integration.py](../tests/test_policy_integration.py)
- 策略实现：[harness/policy.py](../harness/policy.py)

本轮完整测试结果：14 passed。
