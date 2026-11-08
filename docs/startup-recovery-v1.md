# 项目启动错误 Recovery v1

## 实验目的

本实验研究项目在进入业务逻辑前就无法启动的失败模式。fixture 没有第三方依赖，`config.py`、`app.py` 和 `__main__.py` 本身正确，唯一故障是包入口 `service_app/__init__.py` 导入了不存在的 `service_app.configs`。正确模块名是 `service_app.config`。

它和配置异常 Recovery 的区别是：配置异常时程序可以启动但业务结果错误；本实验中包导入直接失败，`from service_app import load_settings` 和 `python -m service_app` 都不能执行。

## 实验控制

- 项目结构：`pyproject.toml`、包目录、配置模块、应用入口和模块入口。
- 外部隐藏测试：位于 `evals/hidden_tests/test_startup_repo.py`，workspace 外不可编辑。
- 基线测试门：真实运行时开启，文件修改前必须先运行隐藏测试。
- 测试预算：最多两次隐藏测试，分别用于首次失败和最终验证。
- 模型调用：当前只做离线验证，不调用 DeepSeek，不消耗额度。
- 服务器：不需要租服务器。

## 成功标准

离线和真实运行都应满足：首次测试显示 `2 failed, 1 passed`；Agent 只修复包入口；第二次测试为 `3 passed`；不修改隐藏测试、配置模块或应用模块。

## 真实运行结果

运行目录：[20261107T102823Z-e6225779](../runs/recovery/20261107T102823Z-e6225779/)

- 首次隐藏测试：`2 failed, 1 passed`，错误为 `ModuleNotFoundError: No module named 'service_app.configs'`；
- Agent 第一次尝试编辑时被基线测试门拒绝，先运行了隐藏测试；
- 测试失败后，Agent 修改了 `service_app/__init__.py`，把 `service_app.configs` 改成 `service_app.config`；
- `config.py`、`app.py`、`__main__.py` 和隐藏测试均没有修改；
- 第二次隐藏测试：`3 passed`；
- 运行结果：`completed=true`、`tests_passed=true`、`execution_error=null`。

证据文件：[run.json](../runs/recovery/20261107T102823Z-e6225779/run.json)、[diff.patch](../runs/recovery/20261107T102823Z-e6225779/diff.patch)。

## 重复运行与 Harness 修复

第一次重复调用 `20261107T103219Z-e6a6e914` 没有生成 `run.json`。原因是 Harness 直接假设每条 `run_tests` 工具消息都是 JSON，遇到非 JSON 消息时在保存报告前抛出 `JSONDecodeError`。这属于 Harness 的日志解析缺陷，不计入模型 Recovery 失败。

随后在 `evals/real_recovery.py` 增加了容错解析：无效消息会记录 `test_result_parse_error` 事件并保留运行产物，不再让整个实验崩溃；同时增加了离线回归测试。

补修后的两次有效重复运行：

- `20261107T103524Z-1109cb1b`
- `20261107T103640Z-ee3b3b33`

与第一次真实运行合并后，三次有效运行均满足：首次 `2 failed, 1 passed`、最终 `3 passed`、只修改 `service_app/__init__.py`，diff 均为 `304` 字符。重复报告：[repeat-real-recovery-startup-import.md](../evals/reports/repeat-real-recovery-startup-import.md)。

## 证据边界

这次真实运行和两次有效重复证明 DeepSeek 在这个受控包启动错误中能根据外部测试的导入错误修复正确入口，并且基线测试门阻止了测试前编辑。它不能代表复杂包结构、真实依赖安装或大型仓库的总体启动恢复率。正式 Recovery 汇总现在包含 24 次运行，其中 20 次属于失败后恢复。
