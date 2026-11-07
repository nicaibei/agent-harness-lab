# 跨文件 Recovery fixture v2

## 实验目标

第一个跨文件任务是订单金额计算。本轮换成温度读数场景，检查跨文件 Recovery fixture 的行为是否能迁移到不同业务逻辑。先完成离线验证，再运行一次真实 DeepSeek；真实运行消耗一次模型调用额度，但不需要租服务器。

## 故意设置的错误

`examples/recovery_temperature_project/` 包含两个生产文件：

- `temperature_parser.py` 把数值加一，并把单位转成小写；
- `temperature_report.py` 没有执行华氏到摄氏的换算。

隐藏测试 `evals/hidden_tests/test_temperature_report.py` 同时检查解析契约和跨文件转换：

```text
parse_reading("32 F") == {"value": 32.0, "unit": "F"}
to_celsius(parse_reading("86 F")) == 30.0
to_celsius(parse_reading("20 C")) == 20.0
```

测试仍然位于 workspace 外，不能被 Agent 修改。

## 离线结果

离线测试先复制原始项目并确认隐藏测试失败，再同时修复 `temperature_parser.py` 和 `temperature_report.py`，确认隐藏测试通过。全量测试结果为 `44 passed`。

这证明第二个不同业务的跨文件 fixture 能复用现有测试工具、隔离 workspace 和隐藏测试机制。它还不能证明 DeepSeek 会在真实运行中修改两个文件，也不能说明跨文件恢复率。

## 与 v1 的控制变量

保持不变：基线测试门、隐藏测试在 workspace 外、最多两次测试、DeepSeek 模型配置和 Recovery 处理逻辑。

变化只有：业务领域和故障内容。v1 研究订单解析与税费，v2 研究温度解析与单位转换。这样真实运行后可以把差异主要解释为任务内容变化。

## 真实运行结果

真实运行目录：[20261107T070150Z-d2125766](../runs/recovery/20261107T070150Z-d2125766/)

```text
baseline_gate=true
第一次隐藏测试：2 failed
Policy 提前编辑拒绝：2 次
修改文件：temperature_parser.py、temperature_report.py
第二次隐藏测试：2 passed
completed=true
tests_passed=true
execution_error=null
```

DeepSeek 删除了解析器中错误的 `+ 1`，把单位规范化为大写，并在报告模块中加入 `(F - 32) * 5 / 9` 转换。`diff.patch` 同时包含两个生产文件，因此这次运行满足跨文件 Recovery 的四项证据。

日志再次出现一次 `ls /workspace` 探索路径错误。它属于工具探索错误，不属于隐藏测试失败；`test_run.success` 和最终 `tests_passed` 才是测试结果依据。

这次运行与订单任务都完成了失败后双文件修复，但样本仍只有两个真实跨文件任务，不能直接估计总体跨文件恢复率。

## 下一步

可以对两个任务做文件级消融：分别撤销其中一个文件的修改再运行隐藏测试，验证两个文件是否都对最终通过不可缺少。之后再增加负面跨文件案例，观察 Agent 修改多个文件后仍然失败时，评测器是否能清楚区分失败原因。
