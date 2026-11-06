# 故障注入评测 v1

## 实验目标

10 个计算器任务全部成功，但它们没有提供有效的测试失败案例。因此本阶段用离线假模型和确定性工具主动制造失败，区分：

```text
工具暂时失败 → Recovery 重试
参数错误 → 模型改变参数
测试失败 → 模型采取修复动作并重新测试
```

实验不调用 DeepSeek，也不需要租服务器。所有结果都可以重复运行。

## 三个案例

### 1. transient-timeout

工具第一次抛出 `TimeoutError`，第二次返回成功。

结果：

```text
recovery_failure
→ recovery_retry
→ recovery_success
```

工具调用参数始终是 `value=x`，动作没有变化，说明这是 Middleware 自动恢复，不是模型纠错。

### 2. wrong-argument

模型第一次调用：

```json
{"value": "wrong"}
```

工具返回参数错误后，模型第二次调用：

```json
{"value": "correct"}
```

两次工具参数不同，最终调用成功。这里的恢复来自模型改变策略，Recovery 只负责把终止错误交回模型，没有盲目重复第一次调用。

### 3. test-failure

第一次测试工具返回：

```json
{"success": false, "exit_code": 1, "output": "1 failed"}
```

模型随后调用 `apply_fix` 修改工作区，再调用测试工具并得到：

```json
{"success": true, "exit_code": 0, "output": "1 passed"}
```

这次产生了 `fixed.txt` 的 diff，且最后测试通过。因此它同时满足：

```text
第一次失败
→ 模型采取不同动作
→ 工作区产生 diff
→ 后续测试通过
```

## 结果汇总

| 案例 | 恢复类型 | 动作变化 | diff | 最终成功 |
| --- | --- | --- | ---: | --- |
| `transient-timeout` | Middleware 重试 | 否 | 0 | 是 |
| `wrong-argument` | 模型纠错 | 是 | 0 | 是 |
| `test-failure` | 模型纠错 | 是 | 51 字符 | 是 |

报告文件：

- [fault-injection-summary.json](../evals/reports/fault-injection-summary.json)
- [fault-injection-summary.md](../evals/reports/fault-injection-summary.md)

重新运行：

```powershell
python -m evals.fault_injection --output-dir evals/reports
```

## 学到的工程结论

1. 超时重试证明 Recovery 的错误分类和上限有效，不能证明模型会纠错。
2. 参数发生变化是模型纠错的重要证据，因为第二次调用不是 Middleware 对原请求的复制。
3. diff 只能证明工作区发生变化；只有 diff 与后续测试通过结合，才能说明修改可能起到了作用。
4. 测试失败结果是一个正常返回的工具结果，不等于工具抛出异常；Recovery 必须把两者区分开。
5. 离线故障注入适合验证 Harness 语义，真实模型实验仍需要后续单独进行。

## 当前限制

本轮使用确定性的假模型响应，证明的是 Harness 能否正确处理三类失败，不代表 DeepSeek 在开放式任务中一定会采取相同的修复动作。下一步可以增加失败后仍未修复的案例，以及跨文件真实修复任务。
