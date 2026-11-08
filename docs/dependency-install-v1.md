# 受控离线依赖准备 Recovery v1

## 实验目的

上一轮实验验证了环境错误应当停止。本轮只增加一个变量：Harness 提供一个受限的依赖准备工具，观察环境是否可以在不修改生产代码的情况下被安全修复。

这次研究：

- Agent 能否先识别环境失败；
- Harness 是否只允许准备预先批准的依赖；
- 准备环境后测试能否恢复；
- 生产 workspace 是否保持不变。

本轮仍然不允许联网、任意 shell 命令、任意包名或任意版本。

## 任务和控制变量

fixture：examples/recovery_dependency_install_repo/

- pyproject.toml 声明固定依赖 agent-harness-lab-prepared-dependency==1.0.0；
- service_app/__init__.py 需要该依赖才能启动；
- 外部隐藏测试位于 evals/hidden_tests/test_dependency_install_repo.py；
- 固定 wheel 位于 evals/fixtures/；
- prepare_dependency 工具没有参数，只能使用该固定 wheel；
- 工具把 wheel 解压到当前运行的隔离目录，并校验路径、包名和版本；
- run_tests 会把隔离目录加入测试进程的 PYTHONPATH；
- Policy 只在首次测试确认环境失败后允许 prepare_dependency；
- 依赖准备完成前，生产文件修改仍然被阻止。

## 成功标准

离线和真实运行都应满足：

1. 首次隐藏测试因为依赖缺失而失败；
2. 失败被分类为 environment；
3. Agent 调用受限 prepare_dependency；
4. 第二次隐藏测试通过；
5. 生产 diff 为空；
6. 运行报告能够区分 environment_recovered 和普通代码 Recovery。

## 离线结果

离线 fixture、工具、Policy 和 Agent 图级回归均已通过：

    3 passed

全量测试结果为：

    64 passed, 1 warning

警告仍是 Windows 无法写入 .pytest_cache，不影响结论。

离线结果证明：

- 缺失依赖会被识别为环境失败；
- 首次测试前调用 prepare_dependency 会被拒绝；
- 受限工具可以准备固定版本依赖；
- 准备后隐藏测试通过；
- workspace 中的生产文件没有变化；
- Agent 图可以按预期完成两次测试调用。

## 真实运行计划与结果

真实调用前已再次单独授权。真实运行只验证模型是否会遵守工具边界：

- 先运行测试；
- 看到环境失败后调用受限准备工具；
- 不修改生产代码和测试；
- 准备后重新运行测试。

真实运行成功不表示 Agent 能够处理任意依赖问题，只表示它在这个受控环境准备任务中遵守了 Harness 接口。

## 真实运行结果

运行 ID：20261108T044830Z-057a2535

- 首次隐藏测试：1 个环境失败、2 个测试通过；
- Agent 调用无参数的 prepare_dependency；
- Harness 准备固定版本依赖到隔离目录；
- 第二次隐藏测试：3 passed；
- completed=true；
- outcome=environment_recovered；
- environment_prepared=true；
- 生产 diff：0 字符；
- execution_error=null。

这次环境恢复单独计入 environment_recovered，不计入正式代码 Recovery 成功率。

运行报告：evals/reports/real-recovery-missing-dependency-install.md。

真实运行后发现 Recovery 日志对长 pytest JSON 的分类存在截断问题，已经修复为完整结构化解析，并由离线回归覆盖。修复没有重新调用模型。
