# 单包精确版本冲突 Recovery v1

## 实验目的

本实验研究环境已经存在依赖，但版本与项目要求不一致的失败模式。

上一轮实验研究“依赖缺失”。本轮只改变一个变量：

- 环境预加载版本 1.0.0；
- 项目精确要求版本 2.0.0；
- Harness 只能把环境切换到预先批准的 2.0.0。

这次不研究多包传递依赖、网络安装或通用版本求解。

## 任务和控制变量

fixture：examples/recovery_dependency_conflict_repo/

- pyproject.toml 要求 agent-harness-lab-conflict-dependency==2.0.0；
- 环境预加载版本位于 evals/fixtures/preloaded_conflict_dependency_v1/；
- 批准的 2.0.0 wheel 位于 evals/fixtures/；
- 外部隐藏测试位于 evals/hidden_tests/test_dependency_conflict_repo.py；
- 生产代码和测试均已正确；
- 首次测试通过 PYTHONPATH 只看到 1.0.0；
- prepare_dependency 只能替换到固定的 2.0.0 wheel；
- 不允许联网、任意 shell、任意包名、任意版本或修改生产文件。

## 成功标准

离线和真实运行都应满足：

1. 首次隐藏测试失败并分类为 dependency_conflict；
2. Agent 调用受限 prepare_dependency；
3. 预加载 1.0.0 被隔离目录中的 2.0.0 替换；
4. 第二次隐藏测试通过；
5. 生产 diff 为空；
6. 报告区分 environment_recovered 和普通代码 Recovery。

## 离线结果

版本冲突 fixture、受限替换工具、Policy 分类和 Agent 图级链路均已通过：

    69 passed, 1 warning

其中针对性冲突回归为：

    4 passed

离线结果证明：

- 1.0.0 与项目要求 2.0.0 的冲突能被单独识别；
- 受限工具能校验并准备固定 2.0.0；
- 准备完成后隐藏测试通过；
- workspace 中生产文件没有变化；
- Agent 图可以按“首次冲突、准备依赖、最终测试”的顺序运行。

警告仍是 Windows 无法写入 .pytest_cache，不影响测试结论。

## 真实运行计划与结果

真实调用前已单独授权，目的只验证模型是否遵守：

- 先运行测试；
- 看到 dependency_conflict 后调用受限 prepare_dependency；
- 不修改生产代码、测试或 metadata；
- 准备 2.0.0 后重新运行测试。

真实运行成功不表示 Agent 能处理任意版本冲突，只表示它在这个固定单包实验中遵守了 Harness 边界。

运行 ID：20261108T051319Z-bffefc3d

- 首次隐藏测试：1 个 dependency_conflict 失败、2 个测试通过；
- Agent 调用无参数的 prepare_dependency；
- Harness 准备固定 2.0.0 并替换预加载的 1.0.0；
- 第二次隐藏测试：3 passed；
- completed=true；
- outcome=environment_recovered；
- environment_prepared=true；
- 生产 diff：0 字符；
- execution_error=null。

独立报告：evals/reports/real-recovery-dependency-version-conflict.md。
