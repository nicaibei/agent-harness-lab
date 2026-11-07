# 跨文件 Recovery 负面案例 v1

## 实验问题

如果 Agent 修改了多个生产文件，但隐藏测试仍然失败，评测器是否会把“有 diff”错误地算成成功？本轮用确定性的错误修复内容回答这个问题，不调用 DeepSeek。

## 案例设置

- `order-total`：解析器修复正确，但总价仍使用错误的加法；
- `temperature-report`：解析器修复正确，但 Fahrenheit 转换仍使用错误公式。

两个案例都修改两个生产文件，且不修改隐藏测试。

## 结果

| 任务 | 修改文件数 | 最终测试 | 分类 |
| --- | ---: | --- | --- |
| `order-total` | 2 | 失败 | `modified_but_failed` |
| `temperature-report` | 2 | 失败 | `modified_but_failed` |

完整结果见：

- [cross-file-negative-summary.json](../evals/reports/cross-file-negative-summary.json)
- [cross-file-negative-summary.md](../evals/reports/cross-file-negative-summary.md)

## 结论

评测器没有把修改文件数当成成功条件。只有最终隐藏测试通过，才可以判定任务成功；两个文件都有 diff 但测试失败时，应记录为“采取了修复行动但未完成任务”。

这两个案例是离线故障注入，不代表真实 DeepSeek 会产生同样的错误修复。下一步可以把负面条件接入真实模型对照，或先扩充统一评测集。
