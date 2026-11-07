# Cross-file Recovery 文件级消融汇总

- 矩阵符合预期：True

| 任务 | 变体 | 修改文件 | 测试结果 | 预期结果 |
| --- | --- | --- | --- | --- |
| `order-total` | `initial` | 无 | False | False |
| `order-total` | `first-only` | order_parser.py | False | False |
| `order-total` | `second-only` | order_total.py | False | False |
| `order-total` | `both` | order_parser.py, order_total.py | True | True |
| `temperature-report` | `initial` | 无 | False | False |
| `temperature-report` | `first-only` | temperature_parser.py | False | False |
| `temperature-report` | `second-only` | temperature_report.py | False | False |
| `temperature-report` | `both` | temperature_parser.py, temperature_report.py | True | True |
