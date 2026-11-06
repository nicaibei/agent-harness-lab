# Policy Middleware v1

## 目标

Baseline 已经能够修改文件和运行测试，但原有约束主要来自工具设计和系统提示。Policy v1 把关键限制放到 Agent 的 `wrap_tool_call` 生命周期钩子中，使每次工具调用都先经过可测试的策略检查。

## 规则

1. 工具必须在 allowlist 中。当前允许文件读取、写入、编辑、搜索、目录查看、固定的 `run_tests` 和 todo 工具；未知工具以及 `execute` 不允许执行。
2. 文件路径使用虚拟 POSIX 路径。路径穿越、Windows 驱动器路径、空字节和非法路径在工具执行前拒绝。
3. `.env`、凭据、私钥和证书文件不允许访问。
4. `delete` 默认关闭，避免 Baseline Agent 删除工作区内容。
5. 单次运行最多允许 30 次工具调用。超出预算后返回结构化工具错误。
6. 每次 allow 或 deny 都写入 `run.json.events` 的 `policy_decision` 事件；事件只记录工具名、决策、原因和调用序号，不记录文件内容或密钥。

## 边界

Policy v1 约束 Agent 工具调用，不提供操作系统级沙箱。`FilesystemBackend` 的虚拟路径检查和本策略都不能替代进程、网络、资源或凭据隔离。当前 Baseline 没有开放任意 shell，因此命令风险只通过拒绝未知 `execute` 工具覆盖；真正的命令分级和人工审批应在引入受控执行工具后单独实现。

## 验证

`tests/test_policy.py` 覆盖策略对象的正常读取、路径穿越、敏感文件、删除、未知工具和预算耗尽；`tests/test_policy_integration.py` 使用离线假模型和真实 `create_deep_agent` 图，验证危险工具调用在执行边界被拦截，工作区不发生未授权变化。Baseline 任务回归还需确认策略不会阻断 Deep Agents 的正常文件工具调用。
