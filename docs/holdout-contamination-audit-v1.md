# Holdout Contamination Audit v1

## 目的和判定标准

本审计检查 formal task manifest v1 的 14 个 holdout 是否仍能支持“未见任务”或无偏泛化声明。证据范围包括 manifest、已保存的 `runs/**/run.json`、正式评测摘要、文档，以及直接绑定的离线 pytest target。只做只读检查，没有运行模型或重新执行 evaluator。

如果任务 fixture 已被真实 Agent 运行并将轨迹/结果保存供 Harness 开发者复盘，或 evaluator 本身是仓库公开测试并已运行，就把任务标为历史暴露。Agent 当次运行看不到 workspace 外 evaluator，并不能让数据对设计 Harness、挑任务或解读结果的人重新变成盲测。

审计基线是提交 `eb65cff9a83a1a01407f20ac9958e8f6ec72563b`。清单 SHA-256 为 `f3ba5750a6c03f03cf64c97e1f674b7bba0c4a692ecc89dac9c4efabc9d4a47f`。结构化证据见 `evals/reports/holdout-contamination-audit-v1.json`。

## 结论

| 类别 | 任务数 | 历史证据 | 判定 |
| --- | ---: | --- | --- |
| 跨文件 Recovery | 2 | 有 4 个真实运行目录，两个 fixture 和测试反馈曾进入评测报告 | 历史暴露 |
| 仓库集成 | 3 | 有 7 个真实运行目录，包含单次和重复任务 | 历史暴露 |
| 环境故障 | 3 | 三个任务均有真实运行目录和独立报告 | 历史暴露 |
| Policy 安全 | 6 | evaluator 直接指向仓库中的 `tests/test_policy.py`，六项已离线执行 6/6 | 公开且已执行 |

8 个模型任务至少运行过 14 次真实 Agent 任务：Order Total 2 次、Temperature Report 2 次、Inventory Checkout 1 次、Inventory Config 3 次、Startup Import 3 次、Missing Dependency 1 次、Dependency Install 1 次、Dependency Version Conflict 1 次。6 个安全任务重用公开 pytest 测试，不构成独立隐藏 holdout。

因此，14 个任务都不能再作为完全未见的盲测集来证明泛化。它们仍然有价值：可以保留为 `formal-evaluation-set-v1` 历史回归集，比较一个明确冻结的 Harness 版本在这些已知任务上的结果；应避免把它们用于未来 Prompt、Policy 或 Recovery 调参，并避免将其结果描述为独立 holdout 成绩。

## 逐项暴露证据

| 任务 | 暴露证据 | 运行数 | 处理建议 |
| --- | --- | ---: | --- |
| `real-recovery-order-total` | `runs/recovery` 中有运行记录；结果见 recovery matrix 报告 | 2 | 保留为历史 Recovery 回归 |
| `real-recovery-temperature-report` | `runs/recovery` 中有运行记录；结果见 recovery matrix 报告 | 2 | 保留为历史 Recovery 回归 |
| `real-recovery-inventory-checkout` | `runs/recovery` 中有运行记录；结果见 recovery matrix 报告 | 1 | 保留为历史仓库集成回归 |
| `real-recovery-inventory-config` | 运行目录、Recovery matrix 和重复运行报告 | 3 | 保留为历史配置回归 |
| `real-recovery-startup-import` | 运行目录、启动 Recovery 和重复运行报告 | 3 | 保留为历史启动回归 |
| `real-recovery-missing-dependency` | 真实运行目录及 `real-recovery-missing-dependency` 报告 | 1 | 保留为历史环境停止回归 |
| `real-recovery-missing-dependency-install` | 真实运行目录及 `real-recovery-missing-dependency-install` 报告 | 1 | 保留为历史受限准备回归 |
| `real-recovery-dependency-version-conflict` | 真实运行目录及 `real-recovery-dependency-version-conflict` 报告 | 1 | 保留为历史版本冲突回归 |
| `policy-path-traversal-deny` | evaluator 是公开的 `tests/test_policy.py::test_denies_path_traversal_before_handler`，离线执行已记录 | 0 model | 改称公开安全回归 |
| `policy-sensitive-file-deny` | evaluator 是公开的 `tests/test_policy.py::test_denies_sensitive_file`，离线执行已记录 | 0 model | 改称公开安全回归 |
| `policy-delete-deny` | evaluator 是公开的 `tests/test_policy.py::test_denies_delete`，离线执行已记录 | 0 model | 改称公开安全回归 |
| `policy-unknown-tool-deny` | evaluator 是公开的 `tests/test_policy.py::test_denies_unknown_tool_and_budget_exhaustion`，离线执行已记录 | 0 model | 改称公开安全回归 |
| `policy-pytest-allow` | evaluator 是公开的 `tests/test_policy.py::test_classifies_commands_by_execution_risk`，离线执行已记录 | 0 model | 改称公开安全回归 |
| `policy-install-needs-approval` | evaluator 是公开的 `tests/test_policy.py::test_requires_and_records_approval_for_review_commands`，离线执行已记录 | 0 model | 改称公开安全回归 |

## 限制与后续

此次审计以当前留存的 run 目录和跟踪文档为证据。被删除或从未保存的历史活动无法恢复；所以结论采用保守分类，不将缺少记录当作没有暴露。

本轮不改动 manifest、不改变历史 split、不重新运行旧任务，也不创建新任务。v1 清单保持可复现；报告中的结论只限制它的“未见盲测”用途，不否定既有运行记录。

新的未见评测应使用独立版本化的 v2：在冻结待测 Harness 后再确定任务及 evaluator；限制 evaluator 源码和参考修复对 Harness 调参者的访问；Agent workspace 不包含 evaluator；评测版本、manifest、任务源码和 evaluator 哈希应在首次运行前固定；每个模型任务按成功测试、修改范围和无异常综合判定；离线安全测试与真实模型任务分层报告。若继续使用同一批熟悉的 fixture，就诚实报告为历史回归，而不是重新命名为盲测。
