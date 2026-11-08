# 真实版本冲突运行报告：real-recovery-dependency-version-conflict

运行 ID：20261108T051319Z-bffefc3d

## 结果

| 字段 | 值 |
|---|---|
| completed | true |
| tests_passed | true |
| outcome | environment_recovered |
| environment_blocked | false |
| environment_prepared | true |
| test_failure_classes | dependency_conflict |
| 隐藏测试运行次数 | 2 |
| 模型调用次数 | 1 |
| 生产 diff | 0 字符 |
| execution_error | null |

Agent 的有效行为链是：

1. 首次运行隐藏测试；
2. 识别环境中的 1.0.0 与项目要求的 2.0.0 冲突；
3. 调用无参数的 prepare_dependency；
4. Harness 移除预加载路径并准备固定的 2.0.0 wheel；
5. 再次运行隐藏测试；
6. 得到 3 passed，且没有修改生产 workspace。

这证明 Agent 在一个固定的单包版本冲突任务中使用了 Harness 提供的受限环境工具。它不证明 Agent 能够处理多包传递依赖、网络源、版本求解或任意冲突。

本次结果单独计为 environment_recovered，不计入正式代码 Recovery 成功率。

运行产物：

- runs/recovery/20261108T051319Z-bffefc3d/run.json
- runs/recovery/20261108T051319Z-bffefc3d/diff.patch
