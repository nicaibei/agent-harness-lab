# 真实依赖准备运行报告：real-recovery-missing-dependency-install

运行 ID：20261108T044830Z-057a2535

## 结果

| 字段 | 值 |
|---|---|
| completed | true |
| tests_passed | true |
| outcome | environment_recovered |
| environment_blocked | false |
| environment_prepared | true |
| test_failure_classes | environment |
| 隐藏测试运行次数 | 2 |
| 模型调用次数 | 1 |
| 生产 diff | 0 字符 |
| execution_error | null |

Agent 的有效行为链是：

1. 首次运行隐藏测试；
2. 得到缺失依赖的 environment 失败；
3. 调用无参数的 prepare_dependency；
4. Harness 解压固定版本的批准 wheel 到隔离目录；
5. 再次运行隐藏测试；
6. 得到 3 passed，且没有修改生产 workspace。

这证明 Agent 在一个受控依赖准备任务中使用了 Harness 提供的环境工具。它不证明 Agent 能够处理任意依赖安装、网络源、版本求解或复杂冲突。

本次结果单独计为 environment_recovered，不计入正式代码 Recovery 成功率。

运行产物：

- runs/recovery/20261108T044830Z-057a2535/run.json
- runs/recovery/20261108T044830Z-057a2535/diff.patch

事后审查发现，原有 Recovery 日志会因截断过长的 pytest JSON 而漏掉环境分类。已改为完整解析结构化 JSON、只截断文本匹配，并增加 environment_failure_detected 事件。相关离线回归通过，没有重复调用模型。
