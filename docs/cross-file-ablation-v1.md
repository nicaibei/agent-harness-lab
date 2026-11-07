# 跨文件 Recovery 文件级消融 v1

## 实验问题

完整运行的 `diff.patch` 同时包含两个文件，只能证明模型改了两个文件。为了进一步判断两个文件是否都对测试通过有贡献，本轮不调用模型，而是对两个真实跨文件 fixture 做文件级消融：分别只保留一个文件的修复，再与两个文件都修复的结果比较。

## 消融矩阵

每个任务运行四种状态：

```text
initial      原始错误代码
first-only   只修复第一个生产文件
second-only  只修复第二个生产文件
both         同时修复两个生产文件
```

任务包括：

- `order-total`：订单解析和含税总价；
- `temperature-report`：温度解析和华氏转摄氏。

## 结果

| 任务 | initial | first-only | second-only | both |
| --- | --- | --- | --- | --- |
| `order-total` | 失败 | 失败 | 失败 | 通过 |
| `temperature-report` | 失败 | 失败 | 失败 | 通过 |

矩阵共 8 次隐藏测试，预期矩阵全部符合。完整结果见：

- [cross-file-ablation-summary.json](../evals/reports/cross-file-ablation-summary.json)
- [cross-file-ablation-summary.md](../evals/reports/cross-file-ablation-summary.md)

## 结论

在这两个 fixture 中，任意一个文件单独修复都不足以通过隐藏测试，两个文件同时修复才通过。这比单独检查 diff 文件列表提供了更强的“两个文件都参与结果”的证据。

但这仍然不是因果证明的终点：任务数量很少，修复内容是人工定义的，且没有测试模型在错误文件组合上的搜索行为。下一步仍需要负面跨文件案例和重复真实运行。

## 工程实现

`evals/cross_file_ablation.py` 在临时 workspace 中复制 fixture，只写入指定文件的正确版本，再调用同一个 workspace 外隐藏测试工具。实验不调用 DeepSeek，因此不消耗额度，也不需要租服务器。
