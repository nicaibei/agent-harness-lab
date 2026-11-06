# Fault Injection 评测汇总

- 案例数：4
- 最终成功：3
- 最终失败：1
- Middleware 自动重试：1
- 模型采取修复动作：3
- 模型修复成功：2

| 案例 | 类型 | 动作变化 | 测试通过 | diff | 最终成功 |
| --- | --- | --- | --- | ---: | --- |
| `transient-timeout` | `middleware_retry` | False | None | 0 | True |
| `wrong-argument` | `model_correction` | True | None | 0 | True |
| `test-failure` | `model_correction` | True | True | 51 | True |
| `unresolved-test-failure` | `model_correction_failed` | True | False | 61 | False |
