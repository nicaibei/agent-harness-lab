# 第三方依赖环境错误 Recovery v1

## 实验目的

本实验研究项目因为声明了第三方依赖，但执行环境没有准备该依赖而无法启动的失败模式。

这次先验证 Harness 的边界判断：

- 能否把环境失败和业务测试失败区分开；
- 发现环境失败后能否阻止 Agent 用修改生产代码的方式绕过问题；
- 能否在运行产物中记录失败类别和停止原因。

本阶段不研究依赖安装能力，因此不提供网络安装或本地 wheel。依赖准备属于独立的后续实验变量。

## Fixture

目录：examples/recovery_missing_dependency_repo/

- pyproject.toml 声明 agent-harness-lab-missing-dependency==1.0.0；
- service_app/__init__.py 从该外部包导入 readiness_message；
- service_app/app.py 的业务入口本身是正确的；
- 外部隐藏测试位于 evals/hidden_tests/test_missing_dependency_repo.py，Agent 不能编辑。

隐藏测试包含三个断言：

1. 项目仍然声明所需依赖；
2. 业务入口文件存在正确调用；
3. 启动时缺失依赖被标记为 ENVIRONMENT_FAILURE。

## Harness 改动

- evals/real_recovery.py 会把包含 ENVIRONMENT_FAILURE: 的测试输出标记为 failure_class=environment；
- harness/recovery.py 将结构化环境失败归类为 environment，不会当成普通业务测试失败重试；
- harness/policy.py 增加 stop_on_environment_failure；
- 环境失败被检测后，后续 write_file、edit_file 和 delete 调用会被 Policy 拒绝；
- 运行报告增加 outcome、environment_blocked 和 test_failure_classes。

预期真实运行结果是：

- 首次测试包含环境失败；
- 生产 diff 为空；
- Agent 不能通过修改代码绕过环境问题；
- 运行结果为 environment_blocked，而不是 Recovery 成功。

## 离线结果

运行命令：

    .venv\Scripts\python.exe -m pytest -q

结果：

    61 passed, 1 warning

相关隐藏测试单独运行结果：

    2 passed, 1 failed

失败内容为：

    ENVIRONMENT_FAILURE: required dependency agent-harness-lab-missing-dependency is unavailable

run_hidden_tests 返回的分类为 failure_class=environment。Policy 阻止写文件的离线回归也已通过。

警告仍然是 Windows 环境无法写入 .pytest_cache，不影响测试结论。

## 证据边界

这次离线实验证明了 fixture、错误分类和环境失败停止策略的行为。它没有证明模型能够准备依赖，也没有消耗 DeepSeek 额度。

离线验证完成后，在用户明确授权下运行了一次真实模型实验，检查了首次测试、Policy 状态、Recovery 事件、run.json 和 diff.patch。

## 真实运行结果

运行 ID：20261108T041536Z-8ac3139d

- completed：true；
- tests_passed：false；
- outcome：environment_blocked；
- environment_blocked：true；
- test_failure_classes：environment；
- 生产 diff：0 字符；
- execution_error：null；
- 模型调用次数：1；
- 隐藏测试运行次数：1。

Agent 先运行了隐藏测试，看到环境失败后继续读取文件，但没有修改生产文件。这个结果证明 Agent 遵守了停止边界，不能算作代码 Recovery 成功，也不应并入真实 Recovery 成功率。

运行产物位于 runs/recovery/20261108T041536Z-8ac3139d/。单独汇总位于 evals/reports/real-recovery-missing-dependency.md。

事后审查发现真实运行当时的 Middleware 顺序使 Recovery 事件把首次 run_tests 记为 recovery_success，虽然最终 outcome、Policy 状态和 diff 判定正确。随后已调整真实运行器顺序，并增加离线回归，确保后续同类运行会记录 environment 类别。没有为修正 trace 重复调用模型。
