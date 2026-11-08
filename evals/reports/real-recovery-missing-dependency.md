# 真实环境错误运行报告：real-recovery-missing-dependency

运行 ID：20261108T041536Z-8ac3139d

## 结果

| 字段 | 值 |
|---|---|
| completed | true |
| tests_passed | false |
| outcome | environment_blocked |
| environment_blocked | true |
| test_failure_classes | environment |
| 隐藏测试运行次数 | 1 |
| 模型调用次数 | 1 |
| 生产 diff | 0 字符 |
| execution_error | null |

Agent 首先运行隐藏测试，得到缺失第三方依赖的环境错误；随后读取了项目文件，没有修改生产代码。Harness 最终把运行标记为 environment_blocked。

这不是代码 Recovery 成功。该运行不计入正式 Recovery 成功率，也不计入最终测试通过率。

运行产物：

- runs/recovery/20261108T041536Z-8ac3139d/run.json
- runs/recovery/20261108T041536Z-8ac3139d/diff.patch

事后审查发现该次运行使用旧的 Middleware 顺序，trace 中首次 run_tests 被 Recovery 记录为 recovery_success；最终 outcome、Policy 状态和空 diff 判定仍然正确。随后已调整顺序并增加离线回归，未重复调用模型。
