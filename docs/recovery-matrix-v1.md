# 真实 Recovery 矩阵 v1

## 实验目标

在一个 `normalize_title` 任务成功后，再增加两个不同类型的隐藏评测任务，检查 Recovery 链路是否具有可迁移性：

- `fractional-tax`：修复税率计算中的比例逻辑；
- `parse-percent`：修复带 `%` 后缀的输入解析。

三个任务都使用 workspace 外的隐藏测试、同一个基线测试门和最多两次测试运行。隐藏测试不会复制到 Agent workspace，因此 Agent 不能修改测试来制造假成功。

## 运行矩阵

| 任务 | 首次测试 | 最后测试 | 失败后恢复 | Policy 拒绝 | 测试失败结果 | 测试 Recovery 事件 | diff |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: |
| `real-recovery-normalize-title`（测试前自行修复） | 通过 | 通过 | 否 | 0 | 0 | 472 |
| `real-recovery-normalize-title`（基线测试门） | 失败 | 通过 | 是 | 1 | 1 | 410 |
| `real-recovery-fractional-tax` | 失败 | 通过 | 是 | 1 | 1 | 234 |
| `real-recovery-parse-percent` | 失败 | 通过 | 是 | 1 | 1 | 327 |

汇总数据保存在：

- [recovery-matrix-summary.json](../evals/reports/recovery-matrix-summary.json)
- [recovery-matrix-summary.md](../evals/reports/recovery-matrix-summary.md)

对应运行证据：

- [normalize-title 基线门 run.json](../runs/recovery/20261106T121015Z-8c84a761/run.json)
- [fractional-tax run.json](../runs/recovery/20261106T123415Z-1a6d6c39/run.json)
- [parse-percent run.json](../runs/recovery/20261106T123510Z-ecc63577/run.json)

## 任务结果

### fractional-tax

第一次隐藏测试暴露：

```text
total_with_tax(100, 0.2) == 100.2
期望 120
```

DeepSeek 将实现从：

```python
return amount + tax_rate
```

修正为：

```python
return amount * (1 + tax_rate)
```

第二次测试 `2 passed`。

### parse-percent

第一次隐藏测试暴露：

```text
parse_percent("20%") == 20.0
期望 0.2
```

DeepSeek 增加了百分号分支，将百分数除以 100，同时保留小数输入：

```python
if text.endswith("%"):
    return float(text[:-1].strip()) / 100.0
return float(text)
```

第二次测试 `2 passed`。

## 学习结论

1. `normalize-title`、`fractional-tax` 和 `parse-percent` 都完成了真实的“先失败、后修复、再通过”链路，说明 Recovery 设计不只适用于一个字符串任务。
2. 每个真正恢复的运行都有一次 Policy 提前编辑拒绝；测试结果证明了首次失败。旧运行的事件日志是在 JSON 结果分类修复前生成的，所以“测试失败结果”和“测试 Recovery 事件”必须分开统计。
3. 四次运行最终都通过，但只有后三次属于失败后恢复，不能把“第一次就通过”与“失败后修复成功”混为一谈。
4. 三个任务都只修改了生产实现文件，隐藏测试没有进入 diff。

## 当前限制

样本仍然很小，三个任务都是单文件 toy 项目，且全部使用同一个模型和相同 Harness 配置。当前结果证明链路可迁移，不足以估计复杂仓库中的恢复率。

下一步可以增加跨文件 fixture，或做有无基线测试门的对照实验；对照实验需要保持任务和模型配置一致，避免把模型随机性误判为 Harness 效果。
