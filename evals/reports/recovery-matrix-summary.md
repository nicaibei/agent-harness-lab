# Real Recovery 矩阵汇总

- 运行数：5
- 最终测试通过：5
- 失败后恢复成功：3

| 任务 | 基线门 | 首次测试 | 最后测试 | 失败后恢复 | Policy 拒绝 | 测试失败结果 | 测试 Recovery 事件 | diff |
| --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: |
| `real-recovery-normalize-title` | unknown | True | True | False | 0 | 0 | 0 | 472 |
| `real-recovery-normalize-title` | unknown | False | True | True | 1 | 1 | 0 | 410 |
| `real-recovery-fractional-tax` | unknown | False | True | True | 1 | 1 | 0 | 234 |
| `real-recovery-parse-percent` | unknown | False | True | True | 1 | 1 | 0 | 327 |
| `real-recovery-normalize-title` | False | True | True | False | 0 | 0 | 0 | 453 |
