# 跨文件 Recovery fixture v1

## 实验目标

前面的 `fractional-tax` 和 `parse-percent` 都只需要修改一个生产文件。本轮先在离线环境增加一个跨文件任务，检查 Harness 是否能保留同样的失败与修复语义：当一个业务错误分布在两个生产文件中时，隐藏测试仍然在 workspace 外执行，模型仍然必须先看到失败，再修改代码。

本轮先用离线测试验证 fixture 和 Harness 接入，再运行一次真实 DeepSeek。真实运行消耗了一次模型调用额度，但不需要租服务器。

## 故意设置的错误

`examples/recovery_order_project/` 包含两个生产文件：

- `order_parser.py` 把 `quantity` 和 `unit_price` 交叉写入；
- `order_total.py` 用加法代替数量乘单价，并把税率直接相加。

隐藏测试 `evals/hidden_tests/test_order_total.py` 同时检查解析结果和含税总价。测试文件不复制到 Agent workspace，不能通过修改测试制造假成功。

正确结果应当是：

```text
parse_order("3 x 10.00") == {"quantity": 3, "unit_price": 10.0}
total_with_tax(..., 0.2) == 36.0
```

## 离线验证

离线测试执行了两次隐藏评测：

1. 复制初始项目，两个测试失败；
2. 同时修复 `order_parser.py` 和 `order_total.py`，两个测试通过。

全量测试结果：`43 passed`。

这证明了 fixture 的初始失败和最终成功，也证明测试工具能处理跨文件 workspace。它还不能证明 DeepSeek 会自动修改两个文件，更不能证明真实模型的跨文件恢复率。

## 预期真实调用链

```text
创建隔离 workspace
  ↓
Policy 拒绝第一次编辑
  ↓
第一次隐藏测试失败
  ↓
DeepSeek 读取失败输出
  ↓
修改 order_parser.py 和 order_total.py
  ↓
第二次隐藏测试通过
  ↓
检查 diff 是否同时包含两个生产文件
```

真实运行前需要保持基线门、模型、提示词和两次测试预算不变。唯一新增变量是任务从单文件变成跨文件；这样才能把结果差异解释为任务结构变化，而不是 Harness 配置变化。

## 真实运行结果

真实运行目录：[20261107T052728Z-a1313c18](../runs/recovery/20261107T052728Z-a1313c18/)

```text
baseline_gate=true
第一次隐藏测试：2 failed
Policy 提前编辑拒绝：2 次
修改文件：order_parser.py、order_total.py
第二次隐藏测试：2 passed
completed=true
tests_passed=true
execution_error=null
```

这次运行提供了完整的跨文件 recovery 证据：模型先看到两个文件共同造成的失败，再同时修复两个生产文件，最后通过隐藏测试。`diff.patch` 是判断跨文件修复是否真实发生的关键证据。

日志还记录了一次模型探索阶段的 `ls /workspace` 路径错误。它没有阻止任务完成，不能与隐藏测试失败混为一谈。`recovery_success` 只表示工具调用正常返回；测试是否通过要看 `test_run.success` 和最终的 `tests_passed`。

## 下一步

下一步可以重复一个不同业务的跨文件任务，或开始整理 Baseline、Policy、Recovery、Checkpoint/Replay 的统一评测表。提交 GitHub 前应先复盘本次真实运行，并确认报告中的运行 ID、首次测试状态和两个文件 diff 都能解释清楚。
