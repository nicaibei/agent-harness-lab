# Baseline 第一版失败分析

本文记录 Baseline 阶段目前观察到的失败，不把模型不可用、运行环境不可写和 Agent 任务失败混为一类。当前 10 个任务已经定义完成，最新有效运行记录全部成功；失败案例来自早期 Qwen/DashScope 运行、一次本机目录权限问题和一次 DeepSeek 模型 ID 配置错误。

## 失败分类

| 时间 | 任务 | 失败层级 | `completed` | `tests_passed` | 主要证据 |
|---|---|---|---:|---:|---|
| 2026-11-05 05:41 UTC | `calculator-add-floats` | 模型连接 | `false` | `false` | `OpenAIConnectionError: Connection error.`；无测试调用，空 diff |
| 2026-11-05 07:20 UTC | `calculator-add-negative-mixed` | 本机运行目录权限 | 无运行记录 | 无运行记录 | 创建 `runs/<run-id>` 时 `WinError 5: Access denied` |
| 2026-11-05 07:22 UTC | `calculator-add-negative-mixed` | 模型配额 | `false` | `false` | `OpenAIPermissionDeniedError: 403 Free quota exhausted`；无测试调用，空 diff |
| 2026-11-05 07:35 UTC | `calculator-add-negative-mixed` | DeepSeek 模型 ID | `false` | `false` | `OpenAIInvalidRequestError: 400`；服务只接受 `deepseek-flash` 或 `deepseek-v4-pro` |

三次早期 Baseline 运行记录在 [baseline-run.md](baseline-run.md) 中，十任务结果在 [baseline-10-task-run.md](baseline-10-task-run.md) 中。这里的失败案例说明，当前结果字段能区分“Agent 已运行但失败”和“Agent 尚未开始”，但运行目录创建失败时还不能保存结构化记录。

## 案例一：连接失败

运行目录：`runs/20261105T054145Z-ceb2fcbd/`

这次运行已经完成工作区复制并进入 `agent.invoke()`，但模型连接失败。Harness 捕获异常并写入：

```text
execution_error = OpenAIConnectionError: Connection error.
completed = false
tests_passed = false
test_runs = []
diff.patch = empty
```

它没有修改文件，也没有执行 pytest。这个案例属于外部模型服务连接失败，不能归因于 Agent 的代码修改能力。

## 案例二：运行目录权限失败

第一次运行新增任务时，`run_task()` 在创建 `runs/<run-id>/workspace/` 前收到 Windows `WinError 5: Access denied`。当时没有生成 `run.json`，因为异常发生在运行目录建立和报告保存之前。

这个案例暴露出一个 Harness 级缺口：如果工作区初始化失败，CLI 只能返回错误文本，任务没有统一的结构化结果。后续需要让运行器在可用位置记录 `setup_error`，或者至少在汇总器中把 CLI 启动失败纳入运行矩阵。

提升本机执行权限后，目录创建恢复正常，说明这不是任务内容或模型配额导致的失败。

## 案例三：免费额度耗尽

运行目录：`runs/20261105T072204Z-136fb6b1/`

工作区已经创建成功，但第一次模型请求被 DashScope 拒绝：

```text
OpenAIPermissionDeniedError: Error code: 403 - Free quota exhausted.
```

该运行的结果是：

- `completed = false`
- `tests_passed = false`
- `execution_error` 保存完整的 403 错误摘要
- `test_runs = []`
- `diff.patch` 为空

这不是本机 CPU、内存或 GPU 不足，也不是租用云服务器可以解决的问题。当前 Baseline 通过 DashScope 远程 API 调用模型，需要可用的付费额度、关闭仅免费额度模式，或更换已授权的模型配置后才能继续进行新增任务的端到端验证。

## 案例四：DeepSeek 模型 ID 不匹配

运行目录：`runs/20261105T073544Z-9dd1f075/`

DeepSeek Key 和 Base URL 都有效，但 `.env` 中配置了 `DeepSeek-V4.1-Flash`。服务返回：

```text
The supported API model names are deepseek-flash, deepseek-v4-pro,
but you passed DeepSeek-V4.1-Flash.
```

请求在模型调用阶段失败，没有执行工具或测试，`diff.patch` 为空。将配置改为 `deepseek-flash` 后，同一任务在 `runs/20261105T073653Z-743842e9/` 成功完成。

## 当前任务覆盖状态

`evals/tasks.json` 现在包含 10 个任务：

- 8 个边界行为或回归测试任务；
- 1 个需要修改 `calculator.py` 并补测试的实现任务；
- 1 个新增 `multiply` 函数并补测试的任务。

这 10 个任务仍然主要集中在一个很小的计算器项目中，因此它们适合作为 Baseline 稳定性和运行产物验证，不足以代表跨文件真实仓库、失败恢复或权限安全评测。下一批任务需要单独加入故障注入、跨模块修改和受控拒绝场景。

## 恢复条件与下一步

后续实验的前置条件已经满足：

1. DeepSeek API Key、模型 ID 和 Base URL 已验证可用。
2. 本机项目目录已经可以创建新的 `runs/<run-id>` 子目录。
3. 十个任务的最新有效记录已经按 `completed`、`tests_passed`、`execution_error`、`diff` 汇总。
4. DeepSeek 任务已经验证 `run.json.events`；历史 Qwen 运行没有事件字段。

Baseline 阶段可以结束，下一步进入 Policy Middleware 的路径白名单、命令风险和预算限制实验。

在额度恢复前，可以继续完成离线工作：完善事件日志 schema、补充任务元数据、设计失败分类测试，以及把架构和源码笔记归档到个人仓库。
