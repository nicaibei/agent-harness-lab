# Fault Injection 评测汇总

- 案例数：3
- 最终成功：3
- Middleware 自动重试：1
- 模型纠错：2

| 案例 | 类型 | 动作变化 | 测试通过 | diff | 最终成功 |
| --- | --- | --- | --- | ---: | --- |
| `transient-timeout` | `middleware_retry` | False | None | 0 | True |
| `wrong-argument` | `model_correction` | True | None | 0 | True |
| `test-failure` | `model_correction` | True | True | 51 | True |
