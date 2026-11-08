# Agent Harness 正式评测矩阵 v1

不同实验保留自己的分母，不计算一个混合成功率。

| 实验组 | 样本数 | 主要结果 |
| --- | ---: | --- |
| Baseline | 14 次尝试 / 10 个任务 | 11 次成功；基础设施失败 3 次；有效成功率 100.0% |
| 故障注入 | 4 个案例 | Middleware 重试 1；模型纠错成功 2；失败 1 |
| 真实 Recovery | 24 次运行 | 最终通过 24；失败后恢复 20；测试前编辑 3 |
| 跨文件消融 | 8 个变体 | 双文件通过 2；其他变体失败 6；矩阵符合预期 True |
| 跨文件负面 | 2 个案例 | 修改但失败 2；分类符合预期 True |

## 判定规则

- 任务成功：`completed=true and final tests_passed=true`。
- Recovery 成功：`first test fails, a valid production diff exists, and final test passes`。
- 负面结果：`production diff exists but final hidden tests fail`。
- 统计原则：groups keep separate denominators and are not merged into one success rate。

## 当前结论

Baseline、真实 Recovery、跨文件消融和负面案例已经形成可复查的证据链。当前数据适合说明 Harness 机制和评测口径，仍不足以推断大型真实仓库中的总体恢复率。
