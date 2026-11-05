# Baseline Agent 运行记录

本文记录最小 Issue-to-PR Baseline Agent 的一次完整验证。验证目标是确认：给定任务 ID 后，Harness 能读取任务、创建隔离工作区、调用 Qwen 修改代码、运行 pytest，并保存可复查的 `run.json` 与 `diff.patch`。

## 验证范围

本次使用 `evals/tasks.json` 中的三个计算器任务：

| 任务 ID | 任务要求 | 运行结果 |
|---|---|---|
| `calculator-add-floats` | 为 `add(1.25, 2.5) == 3.75` 增加测试 | 成功 |
| `calculator-subtract-negative` | 为 `subtract(3, 8) == -5` 增加测试，必要时才修改实现 | 成功 |
| `calculator-divide-fraction` | 为 `divide(1, 4) == 0.25` 增加测试，必要时才修改实现 | 成功 |

任务都使用同一个源项目 `examples/tiny_python_project/`。Agent 每次运行都会复制一份新的工作区，因此三个任务之间不会共享修改。

## 执行链路

命令入口由 `pyproject.toml` 中的 `agent-harness` 脚本指向 `agent_app.baseline:main`。例如：

```powershell
uv run agent-harness --task-id calculator-add-floats
```

一次运行按下面的顺序执行：

1. `main()` 根据任务 ID 读取 `evals/tasks.json`，取出对应的 issue 文本。
2. `run_task()` 加载 `.env`，检查源项目目录和 pytest 文件，并生成 UTC 时间加随机后缀组成的 `run_id`。
3. 源项目被复制到 `runs/<run_id>/workspace/`。复制时排除缓存和版本控制目录；随后 `_snapshot_files()` 保存修改前的文本文件快照。
4. Harness 创建 Qwen 模型客户端，使用 DashScope 的 OpenAI 兼容接口；通过 `FilesystemBackend(root_dir=workspace, virtual_mode=True)` 把文件操作限制在该工作区，并额外提供 `run_tests` 工具。
5. Agent 先检查现有实现和测试，按 issue 做最小修改，再调用 `run_tests`。该工具只执行工作区内的 `python -m pytest -q`，每个任务最多允许两次测试运行。
6. Agent 返回后，Harness 收集最终消息和 `run_tests` 的 `ToolMessage`，解析最后一次测试结果。`completed` 表示 Agent 调用过程是否出现执行错误，`tests_passed` 表示最后一次测试运行是否成功。
7. Harness 再次快照工作区，用 `_build_diff()` 生成统一 diff，并把同一份内容写入 `diff.patch` 和 `run.json` 的 `diff` 字段。即使 Agent 执行异常，也会尽量保存运行记录。

概念上的数据流是：

```text
task-id
  -> evals/tasks.json
  -> issue 文本
  -> runs/<run-id>/workspace/
  -> create_deep_agent(Qwen + FilesystemBackend + run_tests)
  -> 文件修改与 pytest
  -> before/after 快照
  -> diff.patch + run.json
```

## 三次成功运行

| 任务 ID | `run_id` | `completed` | `tests_passed` | `execution_error` | 测试输出 | diff |
|---|---|---:|---:|---|---|---|
| `calculator-add-floats` | `20261105T065422Z-83adadc7` | `true` | `true` | `null` | `5 passed in 0.07s` | 修改 `test_calculator.py`，新增 `test_add_float_inputs` |
| `calculator-subtract-negative` | `20261105T070213Z-d1386853` | `true` | `true` | `null` | `5 passed in 0.06s` | 修改 `test_calculator.py`，新增 `test_subtract_returns_negative` |
| `calculator-divide-fraction` | `20261105T070349Z-ee213abe` | `true` | `true` | `null` | `5 passed in 0.05s` | 修改 `test_calculator.py`，新增 `test_divide_one_by_four` |

三次运行的 `run.json` 都记录了相同的模型和服务配置：模型为 `qwen3.6-plus`，Base URL 为 `https://dashscope.aliyuncs.com/compatible-mode/v1`。每次 `test_runs` 都只有一次成功的 `run_tests` 调用，退出码为 `0`。

### `calculator-add-floats`

运行记录：[run.json](../runs/20261105T065422Z-83adadc7/run.json)，补丁：[diff.patch](../runs/20261105T065422Z-83adadc7/diff.patch)。

Agent 保留了 `calculator.py` 不变，只在 `test_calculator.py` 中加入：

```python
def test_add_float_inputs() -> None:
    assert add(1.25, 2.5) == 3.75
```

五个测试全部通过，说明既有实现已经支持该浮点输入，任务只需要补充行为覆盖。

### `calculator-subtract-negative`

运行记录：[run.json](../runs/20261105T070213Z-d1386853/run.json)，补丁：[diff.patch](../runs/20261105T070213Z-d1386853/diff.patch)。

Agent 检查后判断现有 `subtract(left, right)` 已经执行 `left - right`，所以没有修改实现，只加入：

```python
def test_subtract_returns_negative() -> None:
    assert subtract(3, 8) == -5
```

五个测试全部通过，验证了负数结果和“只在必要时修改实现”的任务要求。

### `calculator-divide-fraction`

运行记录：[run.json](../runs/20261105T070349Z-ee213abe/run.json)，补丁：[diff.patch](../runs/20261105T070349Z-ee213abe/diff.patch)。

Agent 判断既有 `divide(left, right)` 已经使用浮点除法，并保留 `calculator.py` 不变，只加入：

```python
def test_divide_one_by_four() -> None:
    assert divide(1, 4) == 0.25
```

五个测试在第一次运行即通过，退出码为 `0`。

## 运行产物字段

每个 `runs/<run_id>/run.json` 都包含以下 Baseline 关心的结果字段：

| 字段 | 含义 | 本次三次成功运行 |
|---|---|---|
| `completed` | Agent 调用及产物保存流程没有捕获到执行错误 | 全部 `true` |
| `tests_passed` | `test_runs` 最后一次记录的 `success` 为 `true` | 全部 `true` |
| `execution_error` | Agent 调用异常或工作区消失时保存的错误文本 | 全部 `null` |
| `diff` | 修改前后文本快照生成的统一 diff | 每次均只有一个测试新增 |
| `test_runs` | `run_tests` 工具返回的 JSON 字符串列表 | 每次一次，退出码 `0` |
| `final_response` | Agent 最后一条消息 | 均说明修改内容和测试通过 |
| `events` | 按时间排列的运行生命周期事件 | 由后续运行写入；这三次历史运行产生于事件字段加入之前 |

`diff.patch` 是 `run.json` 中 `diff` 字段的独立文件副本，方便直接用补丁工具或代码审查工具查看。当前三次成功运行都没有修改生产实现，diff 只新增对应的回归测试。

后续运行还会在 `run.json.events` 中记录 `run_started`、`workspace_created`、`agent_started`、`test_run`、`agent_finished`、`diff_created` 和 `run_finished` 等事件，为失败分析和 Replay 提供时间顺序依据。

## 失败连接案例

在成功的 `calculator-add-floats` 重跑之前，曾有一次相同任务的连接失败：

- 运行目录：`runs/20261105T054145Z-ceb2fcbd/`
- `execution_error`：`OpenAIConnectionError: Connection error.`
- `completed`：`false`
- `tests_passed`：`false`
- `test_runs`：空列表
- `diff.patch`：空文件

这次失败发生在模型调用阶段，Agent 没有机会修改文件或运行测试。Harness 仍然写出了 `run.json` 和空的 `diff.patch`，所以失败可以被区分为“执行错误”，而不是被误报成测试失败。随后同一任务重跑成功，说明当前 Baseline 已经完成一次可重复的三任务验证，但连接稳定性仍应在后续丰富事件日志和失败分析时单独观测。

## Baseline 结论

本次验证证明了最小链路已经闭合：

```text
Issue
  -> 隔离工作区
  -> Qwen 读取和修改文件
  -> 固定 pytest 工具
  -> 生成 diff.patch
  -> 生成 run.json
```

三个任务均满足 `completed=true`、`tests_passed=true`、`execution_error=null`，并生成了非空的测试补丁。当前 Baseline 可以作为后续 Policy、Recovery 和 Checkpoint/Replay 实验的行为基线；这些扩展应保留本报告中定义的运行结果字段，以便比较引入 Harness 能力前后的差异。
