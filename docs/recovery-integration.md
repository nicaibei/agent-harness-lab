# Recovery Agent 图集成实验

## 实验目的

Recovery 单元测试可以验证重试循环，但还需要确认它在 `create_deep_agent` 的真实工具调用链中工作。本实验使用离线假模型和一个“第一次超时、第二次成功”的工具，验证 middleware 能在 Agent 图内完成恢复。

## 运行结果

```text
Agent 生成 flaky_tool
  -> 第一次工具调用抛出 TimeoutError
  -> Recovery 分类为 transient
  -> recovery_retry
  -> 第二次工具调用成功
  -> Agent 收到成功 ToolMessage
```

事件顺序固定为：

```text
recovery_failure -> recovery_retry -> recovery_success
```

这说明 Recovery 的重试不是在 Agent 外面重新启动整个任务，而是在工具调用 middleware 中重新执行同一个暂时失败的调用。对于 Policy 拒绝、参数错误和预算耗尽，Recovery 不会重复执行，因为这些错误不是通过重试就能解决的。

## 你需要掌握的工程结论

1. Recovery 处理的是“工具已经开始执行但暂时失败”的情况；它不替模型修改错误参数。
2. 重试必须有上限，否则网络故障可能无限消耗时间和费用。
3. 事件顺序使我们能判断系统是否真的重试过，而不是只看最后一个成功结果。
4. 真正的代码纠错还需要下一轮模型调用读取失败信息、生成新的工具参数或修改代码；这和同一个工具调用的瞬时重试是两种不同的恢复。

本轮集成测试不调用 DeepSeek，也不执行真实 Shell。

另外一个集成场景让第一次工具调用使用错误参数。Recovery 将参数错误作为 terminal error 返回给模型，不自动重复同一调用；假模型随后生成修正参数，第二次调用成功。这个事件顺序是：

```text
recovery_failure -> recovery_terminal -> recovery_success
```

这才是“模型纠错”的最小证据：第一次失败和第二次成功使用了不同的工具参数，而不是 middleware 盲目重试相同请求。

测试结果也可以触发同一条恢复链。`run_tests` 返回 `{"success": false, ...}` 时，Recovery 会把它分类为 `tool_error`，把失败输出交回模型；模型随后用 `fix=true` 的不同参数再次请求，得到 `{"success": true, ...}`。这证明 Harness 可以区分“工具调用成功返回了失败结果”和“工具本身抛出异常”。
