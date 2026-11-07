# 扩展任务集 v1

## 实验目标

原来的 10 个 Baseline 任务都来自同一个计算器项目，适合作为稳定性对照，但不能覆盖不同业务错误。本阶段新增 4 个单文件 Recovery fixture，并把已有 2 个跨文件 fixture 纳入统一任务清单。

## 任务类型

| 类型 | 任务 | 关注的错误 |
| --- | --- | --- |
| `structured_text` | `csv-row` | 字段顺序、空白和整数转换 |
| `sequence_logic` | `stable-unique` | 去重后保持首次出现顺序 |
| `error_handling` | `safe-divide` | 零除数返回约定值 |
| `unit_parsing` | `parse-duration` | 小时、分钟单位换算 |
| `cross_file_contract` | `order-total`、`temperature-report` | 两个生产文件之间的数据契约 |

每个任务都声明：项目目录、workspace 外隐藏测试、预期修改文件、难度和真实重复次数目标。清单位于 [expanded_tasks.json](../evals/expanded_tasks.json)，由 `evals/task_manifest.py` 校验。

## 离线结果

四个新任务都满足：原始 fixture 的隐藏测试失败，写入正确实现后隐藏测试通过。任务清单测试确认 6 个任务 ID 唯一、路径存在、类别完整、重复目标合法。当前全量测试为 `52 passed`。

离线准备阶段没有调用 DeepSeek；随后已授权运行 4 个新任务各 1 次，4 次都首次测试失败、最终测试通过，并且各自只修改了预期的生产文件。真实 Recovery 汇总在这批首轮运行后是 15 次运行、15 次最终通过、11 次失败后恢复。随后对 `parse-duration` 重复两次，三次运行都恢复成功，diff 字符数为 1259 到 1346，探索工具错误出现 2 次。继续重复仍然不需要租服务器。

## 设计边界

扩展任务数量本身不等于评测质量提升。后续重复时必须保持模型、基线门、测试预算和提示词不变，并记录每次首次测试状态、最终测试、diff、事件和运行成本。`parse-duration` 的三次结果说明：最终结果可以稳定，但中间修复策略和探索错误仍然存在随机性。
