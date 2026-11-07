# Real Recovery 矩阵汇总

- 运行数：18
- 最终测试通过：18
- 失败后恢复成功：14

| 任务 | 基线门 | 首次测试 | 最后测试 | 失败后恢复 | Policy 拒绝 | 测试失败结果 | 测试 Recovery 事件 | diff |
| --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: |
| `real-recovery-normalize-title` | unknown | True | True | False | 0 | 0 | 0 | 472 |
| `real-recovery-normalize-title` | unknown | False | True | True | 1 | 1 | 0 | 410 |
| `real-recovery-fractional-tax` | unknown | False | True | True | 1 | 1 | 0 | 234 |
| `real-recovery-parse-percent` | unknown | False | True | True | 1 | 1 | 0 | 327 |
| `real-recovery-normalize-title` | False | True | True | False | 0 | 0 | 0 | 453 |
| `real-recovery-fractional-tax` | False | True | True | False | 0 | 0 | 0 | 234 |
| `real-recovery-parse-percent` | False | True | True | False | 0 | 0 | 0 | 327 |
| `real-recovery-order-total` | True | False | True | True | 2 | 1 | 0 | 1340 |
| `real-recovery-temperature-report` | True | False | True | True | 2 | 1 | 0 | 745 |
| `real-recovery-order-total` | True | False | True | True | 0 | 1 | 0 | 785 |
| `real-recovery-temperature-report` | True | False | True | True | 2 | 1 | 0 | 949 |
| `real-recovery-stable-unique` | True | False | True | True | 1 | 1 | 0 | 403 |
| `real-recovery-parse-duration` | True | False | True | True | 1 | 1 | 0 | 1279 |
| `real-recovery-csv-row` | True | False | True | True | 1 | 1 | 0 | 351 |
| `real-recovery-safe-divide` | True | False | True | True | 1 | 1 | 0 | 253 |
| `real-recovery-parse-duration` | True | False | True | True | 1 | 1 | 0 | 1259 |
| `real-recovery-parse-duration` | True | False | True | True | 1 | 1 | 0 | 1346 |
| `real-recovery-inventory-checkout` | True | False | True | True | 0 | 1 | 0 | 2576 |
