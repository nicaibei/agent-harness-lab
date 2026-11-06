# 真实模型隐藏评测与 Recovery v1

## 实验目标

离线故障注入已经证明测试语义可以区分 Middleware 重试和模型纠错。本阶段使用 DeepSeek，在工作区外运行隐藏测试，验证真实模型是否能根据真实 pytest 输出修改生产代码。

实验 fixture 是 `examples/recovery_python_project/title_utils.py`。初始实现只去除首尾空白并转小写，没有把内部空白转换成连字符。隐藏测试位于 `evals/hidden_tests/test_title_utils.py`，不会复制到 Agent workspace，也不能被文件工具修改。

## 第一次真实运行：测试前自行修复

运行目录：`runs/recovery/20261106T120044Z-3d3652b3/`

DeepSeek 先读取实现，直接修改 `title_utils.py`，然后第一次运行隐藏测试就得到：

```text
2 passed
```

这个结果证明：

- 模型可以在看不到隐藏测试源码的情况下理解任务并修复实现；
- 隐藏测试确实能验证 workspace 外的代码；
- diff 只修改了生产实现。

但它没有产生第一次失败，因此不能作为“测试失败后模型纠错”的证据。它暴露了一个评测设计问题：只在 prompt 中要求先测试，不能保证模型真的先测试。

## 基线测试门

Policy 新增可选配置：

```python
PolicyMiddleware(require_baseline_test=True)
```

启用后，任何 `write_file`、`edit_file` 或 `delete` 在第一次 `run_tests` 完成前都会被拒绝：

```text
模型请求 edit_file
  ↓
Policy deny: baseline test must run before file mutations
  ↓
模型请求 run_tests
  ↓
允许隐藏测试执行
  ↓
模型根据失败输出修改代码
```

这个门属于 Harness，因为它是跨工具、跨步骤的运行约束，不能依靠模型提示词保证。

## 第二次真实运行：先失败、后纠错

运行目录：`runs/recovery/20261106T121015Z-8c84a761/`

关键证据：

```text
Policy deny edit_file
  ↓
第一次隐藏测试：2 failed
  ↓
DeepSeek 修改 title_utils.py
  ↓
第二次隐藏测试：2 passed
```

运行结果：

| 字段 | 结果 |
| --- | --- |
| `completed` | `true` |
| `tests_passed` | `true` |
| 测试运行次数 | 2 |
| 第一次测试 | 失败，2 个隐藏测试失败 |
| 第二次测试 | 通过，2 passed |
| diff | 只修改 `title_utils.py` |
| Policy 拒绝次数 | 1 次，阻止提前编辑 |
| checkpoint 数量 | 17 |

这次满足真实纠错的最小证据：

```text
真实测试失败
  ↓
模型看到失败输出
  ↓
模型采取不同动作并修改生产代码
  ↓
再次测试通过
```

## 实验中发现的 Harness 缺陷

第二次运行还发现：`run_tests` 工具返回的是 JSON 字符串，而 Recovery 早期主要按 `ToolMessage` 分类。因此历史运行中的测试失败虽然正确交给了模型，但事件中把该工具结果记成了 `recovery_success`，没有准确记录 `recovery_failure`。

现在 `classify_failure()` 已经能识别原始 JSON 字符串中的 `{"success": false}`，隐藏测试工具也改为在执行时立即写入 `test_run` 事件。这个修复通过离线测试，但第二次历史运行保留原始事实，不回写历史日志。

## 验证结果

当前全量测试：

```text
37 passed
```

离线集成测试还证明了：基线测试门会阻止第一次写文件，初始隐藏测试失败，允许编辑后第二次隐藏测试通过。

## 学到的工程结论

1. Prompt 只能表达顺序要求，不能可靠保证执行顺序；跨步骤顺序应由 Harness 强制。
2. 隐藏测试能防止 Agent 通过修改测试文件伪造成功，但测试工具仍需要安全地把结果传回模型。
3. 第一次测试失败、后续动作变化和最终测试通过，三者共同构成真实纠错证据。
4. 事件日志的分类准确性和事件发生时机同样重要；事后补记测试事件会破坏严格时间顺序。
5. 真实模型实验会暴露离线假模型没有覆盖的边界，实验报告必须保留这些缺陷，而不是只记录成功结果。

## 当前限制

本轮只运行了一个真实 recovery fixture，不能代表 DeepSeek 在复杂跨文件任务上的平均纠错率。下一步可以增加两个不同类型的隐藏测试任务，并比较没有基线门、只有 Recovery、Policy 加 Recovery 三种配置。
