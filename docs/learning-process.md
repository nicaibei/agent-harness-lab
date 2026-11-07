# Agent Harness 学习过程记录

这份文档记录本项目的学习过程，而不只是列出已经提交的代码。每个阶段都按照下面的顺序整理：

1. 要解决的 Agent 失败模式；
2. 设计判断和选择理由；
3. 实现和调用链；
4. 测试或运行证据；
5. 本阶段需要真正掌握的概念；
6. 进入下一阶段前的复习问题。

项目的目标不是简单做出一个能调用模型的脚本，而是理解 Agent Harness 如何让模型在受控、可观察、可恢复的环境中完成代码任务。

## 学习主线

```text
Backend：文件和状态放在哪里？
    ↓
Baseline：Agent 能否完成一个最小 Issue-to-PR 任务？
    ↓
Policy：Agent 想调用的工具是否允许？
    ↓
Recovery：工具失败后应该重试、停止，还是交回模型？
    ↓
Checkpoint/Replay：如何保存中间状态并复现一次运行？
    ↓
Evaluation：如何比较不同 Harness 设计的效果？
```

需要一直保留的区分是：

| 组件 | 负责的问题 | 在本项目中的例子 |
| --- | --- | --- |
| Agent | 下一步应该做什么？ | 读取代码、修改测试、运行测试 |
| Tool | 模型可以请求哪一个具体动作？ | `read_file`、`write_file`、`run_tests` |
| Backend | 动作具体如何执行、数据放在哪里？ | `FilesystemBackend` |
| Middleware | 调用是否允许，失败后如何处理？ | Policy、Recovery |
| Runtime | 如何推进有状态的执行过程？ | LangGraph / Deep Agents graph |
| Checkpoint | 如何保存某个时刻的运行状态？ | `InMemorySaver` 和 `thread_id` |

## 阶段 0：建立实验环境

### 目标

先建立一个可以重复运行、可以保存结果的个人实验仓库，而不是直接从复杂 Agent 功能开始。仓库目录包含：

```text
agent-harness-lab/
├── agent_app/   # Agent 入口和任务编排
├── harness/     # Policy、Recovery、Replay 等 Harness 能力
├── evals/       # 任务定义和评测数据
├── examples/    # 可控的 toy 项目
├── tests/       # 单元测试和集成测试
└── docs/        # 学习笔记和实验报告
```

### 学到的概念

实验项目需要把“源项目”和“运行工作区”分开。源项目用于提供初始输入，每次 Agent 运行都复制到新的 `runs/<run-id>/workspace/` 中。这样一次运行的修改不会污染下一次运行，也可以对修改前后的文件做比较。

Backend 实验比较了 `StateBackend`、`FilesystemBackend` 和 `CompositeBackend`。学习重点不是记住三个类名，而是理解：文件工具提供操作接口，Backend 决定这些操作的存储和路径映射；Backend 不是 Agent 的权限策略，也不是操作系统沙箱。

### 证据

- [backend-experiment-report.md](backend-experiment-report.md) 记录 Backend CRUD、路径映射和 Composite 路由实验。
- [architecture.md](architecture.md) 记录 Deep Agents、LangChain Agent、LangGraph Runtime、Middleware 和 Backend 的职责边界。

## 阶段 1：Baseline Agent

### 目标

先确认最小链路闭合：给 Agent 一个 issue，它能在隔离副本中查看代码、修改文件、运行测试，并保存可以检查的结果。

基本链路是：

```text
Issue
  ↓
读取 evals/tasks.json
  ↓
创建隔离 workspace
  ↓
DeepSeek Agent 使用文件工具修改代码
  ↓
固定的 run_tests 工具运行 pytest
  ↓
保存 run.json 和 diff.patch
```

### 模型配置的学习

早期实验使用过 Qwen 的 OpenAI 兼容接口，后来切换到 DeepSeek。这个切换改变的是模型客户端配置，不改变 Harness 的核心接口：模型仍然通过 `ChatOpenAI` 兼容客户端接入，任务、工作区、测试工具、运行报告的结构保持一致。

本机运行目前足够完成这些实验，不需要租用服务器。只有当实验规模需要长时间批量运行、模型服务要求特定 GPU/网络环境，或本地额度和稳定性不足时，才需要单独评估租服务器。

### 关键实现

`agent_app/baseline.py` 中的 `run_task()` 完成以下工作：

1. 读取环境变量和任务配置；
2. 创建唯一 `run_id` 和隔离工作区；
3. 保存修改前的文本快照；
4. 创建只运行工作区内 pytest 的 `run_tests` 工具；
5. 调用 `create_deep_agent()` 组装模型、Backend、工具和 Middleware；
6. 收集模型消息和测试结果；
7. 对比前后快照生成统一 diff；
8. 计算 `completed`、`tests_passed`、`execution_error`，并写入 `run.json`。

### 结果解释

这几个字段不能混为一谈：

| 字段 | 应该如何理解 |
| --- | --- |
| `completed` | Agent 调用过程是否出现顶层执行异常 |
| `tests_passed` | 最后一次 `run_tests` 是否成功 |
| `execution_error` | 模型调用或图执行等顶层异常文本 |
| `diff` | Agent 对工作区实际造成的文本修改 |

例如 `completed=true`、`tests_passed=false`、`execution_error=null` 表示 Agent 正常结束，但没有把任务修到测试通过。这种结果不能算任务成功。

### Baseline 结果

10 个任务已经完成，三任务起始验证和十任务矩阵都保存了运行产物。成功运行通常满足：

```text
completed=true
tests_passed=true
execution_error=null
diff 非空且内容符合 issue
```

Baseline 的作用是提供比较基线。之后加入 Policy 或 Recovery 时，仍然要保留这些结果字段，否则无法判断增强后的 Harness 到底改善了什么。

### 本阶段掌握的概念

- Agent 是模型驱动的决策循环，不等于整个 Harness。
- 隔离工作区让一次运行的修改可以被审查和丢弃。
- `diff.patch` 说明 Agent 改了什么，`run.json` 说明 Agent 如何运行。
- 最小成功标准必须同时考虑执行状态、测试状态和修改内容。

## 阶段 2：Policy Middleware

### 目标和失败模式

Baseline 中模型可以请求工具，但模型的提示词不能构成可靠安全边界。Policy 解决的是：

> 模型想做的事情，是否允许执行？

入口是 `PolicyMiddleware.wrap_tool_call()`。它位于工具真正执行之前：

```text
模型生成 tool_call
  ↓
PolicyMiddleware.wrap_tool_call()
  ↓
检查 allowlist、路径、敏感文件、删除操作、预算和命令风险
  ├── allow：交给实际工具
  └── deny：返回 status=error 的 ToolMessage
```

### 已实现规则

- 工具 allowlist：未登记的工具默认拒绝；
- 路径穿越：拒绝 `..`、盘符、空字节等可能逃出虚拟工作区的路径；
- 敏感文件：拒绝 `.env`、私钥、凭据等文件；
- 删除操作：Baseline 阶段默认关闭 `delete`；
- 工具调用预算：超过 `max_tool_calls` 后拒绝新的调用；
- 命令风险：将命令分类为 `safe`、`review`、`dangerous`；
- 审批回调：`review` 命令只有获得审批才允许执行。

### 为什么这些规则属于 Middleware

路径、文件类型和预算规则会影响多个工具。把它们分别写进每个工具，会产生重复逻辑，也容易漏掉某个入口。Middleware 处在统一工具调用边界上，因此可以用一套规则观察和限制所有相关调用。

Policy 仍然不是操作系统沙箱。它约束的是 Agent 通过 Harness 发起的工具调用；进程隔离、网络隔离和凭据隔离需要更强的执行环境。

### 实验和证据

离线 Agent 图集成测试验证了：

- `read_file("/../outside.txt")` 被拒绝；
- `read_file("/.env")` 被拒绝；
- `delete("/safe.txt")` 被拒绝且文件保留；
- 预算为 1 时第一次读取允许，第二次读取被拒绝；
- 命令分类和审批回调可以区分安全、待审查和危险命令。

这些测试使用真实的 `create_deep_agent` 图和 `FilesystemBackend`，只把模型响应替换成离线假模型，因此不消耗 API 额度，也能证明 Middleware 已经接入真实调用链。

## 阶段 3：Recovery Middleware

### 目标和失败模式

Policy 解决“能不能执行”，Recovery 解决“工具执行失败之后怎么办”。关键问题不是对所有错误都重试，而是先分类：

```text
工具调用
  ↓
成功？
  ├── 是：返回结果
  └── 否：判断失败类别
          ├── 暂时性错误：有限重试
          ├── Policy 或预算错误：停止重复
          ├── 参数或业务错误：把错误交回模型
          ├── 测试失败结果：让模型分析并修改代码
          └── 相同请求循环：阻断
```

### 已实现行为

| 失败类型 | Recovery 行为 | 原因 |
| --- | --- | --- |
| 超时、连接重置、临时不可用 | 在上限内重试 | 下一次调用可能恢复 |
| Policy 拒绝、预算耗尽 | 不重试 | 重复相同请求不会改变策略结果 |
| 参数错误或普通工具异常 | 交回模型 | 需要模型生成不同参数或采取新动作 |
| `success=false` 的测试结果 | 交回模型 | 测试失败需要诊断和代码修改 |
| 相同工具和参数重复过多 | 阻断 | 防止 Agent 循环消耗资源 |

### 事件日志

Recovery 记录：

```text
recovery_failure
recovery_retry
recovery_success
recovery_terminal
recovery_loop_blocked
```

例如第一次超时、第二次成功的证据是：

```text
recovery_failure → recovery_retry → recovery_success
```

参数错误后由模型改参数的证据是：

```text
recovery_failure → recovery_terminal → recovery_success
```

这里第二次成功不是 Middleware 原样重试的结果，而是模型看到错误后发出了不同的调用。这才是“模型纠错”的最小证据。

### 当前测试证明的行为

- 暂时性 `TimeoutError` 可以有限重试；
- 错误参数不会被 Recovery 无限重复执行；
- 模型可以根据工具错误改用正确参数；
- 测试工具返回失败结果后，模型可以再次调用并得到成功结果；
- 失败和恢复事件会写入事件列表。

## 当前学习检查点

进入 Checkpoint/Replay 设计前，需要能够回答：

1. `read_file("/../outside.txt")` 应该由 Policy 还是 Recovery 处理？为什么？
2. 工具第一次发生 `TimeoutError`、第二次成功时，Recovery 事件顺序是什么？
3. `completed=true`、`tests_passed=false`、`execution_error=null` 说明了什么？
4. 为什么测试失败后要把结果交给模型分析，而不是让 Recovery 无限重跑测试？

这些问题分别检查：执行前控制、失败分类、运行结果解释和模型纠错边界。

## 阶段 4：Checkpoint/Replay v1

### 目标和设计判断

这一阶段解决两个问题：Agent 中途暂停后能否从同一条线程继续，以及运行结束后能否不重新调用模型就复盘过程。

第一版使用 LangGraph 的 `InMemorySaver` 验证真实 graph checkpoint，使用事件日志摘要实现无副作用 Replay。内存 checkpointer 适合实验，但不能跨进程恢复；Replay 读取历史记录，不能等同于再次调用模型的 rerun。

暂停点选择在“模型已经生成工具调用、工具还没有执行”之后。这样可以看到模型的决定，同时证明文件或外部工具副作用尚未发生；恢复后使用同一个 `thread_id` 继续执行。

### 实现和证据

`harness/checkpoint.py` 提供两个能力：

- `summarize_checkpoints()` 读取当前线程的 checkpoint 数量和最新 ID；
- `replay_events()` 只遍历事件并生成运行摘要，不调用模型、工具或工作区。

Baseline 现在把 `run_id` 作为 `thread_id` 传给 `create_deep_agent()`，并保存 `checkpoint.json`、`replay.json`。离线 Agent 图测试证明：暂停时工具没有执行，`Command(resume=...)` 恢复后工具执行一次，checkpoint 数量增加。Replay 测试证明事件可以单独重建 Policy 拒绝、Recovery 重试、测试次数和最终状态。

本阶段全量测试结果为 `28 passed`。测试过程中有一个 Windows 下 pytest 缓存目录权限警告，不影响测试通过，也不是本次逻辑失败。

### 本阶段掌握的概念

- `thread_id` 决定恢复的是哪一条运行线程；
- Checkpoint 保存状态，事件日志保存过程，工作区快照保存文件状态；
- Replay 和 rerun 的目标不同，Replay 不应再次调用 DeepSeek；
- `InMemorySaver` 先证明机制，跨进程持久化需要后续单独设计。

实验报告见 [checkpoint-replay-v1.md](checkpoint-replay-v1.md)。

## Checkpoint v1 的持久化取舍

Checkpoint v1 先使用 `InMemorySaver` 证明机制，不立即增加 SQLite 等依赖。是否需要跨进程持久化，应由后续评测和恢复场景的实际需求决定。

## 阶段 5：评测与失败分类 v1

### 目标和设计判断

这一阶段把 `runs/` 中的运行产物转成可比较的证据。评测器逐个读取 `run.json`，只在内存中保存短摘要，完整日志和 diff 继续保留在磁盘。

报告同时保存全部尝试和每个任务的 `latest_valid_attempt`。模型连接、额度、模型 ID 等基础设施问题单独分类，不覆盖 Agent 真正开始执行后的任务结果。

### 实现和证据

`evals/report.py` 目前支持 `success`、`test_failure`、`model_error`、`setup_error`、`agent_error` 和 `invalid_artifact` 分类，并输出 JSON 和 Markdown 报告。

现有 14 次运行的结果是：11 次成功、3 次模型服务错误；全部尝试成功率为 78.6%，排除基础设施错误后的有效尝试成功率为 100%，10 个任务的最新有效结果全部成功。

这组结果不能说明 Recovery 已经具备真实代码纠错能力，因为目前没有有效的测试失败运行。下一步是加入受控故障注入任务，再比较模型是否能根据错误修正工具参数或代码。

实验报告见 [evaluation-v1.md](evaluation-v1.md)。

## 阶段 6：故障注入与 Recovery 纠错评测 v1

### 目标和设计判断

十个计算器任务都成功，不能证明 Agent 有纠错能力，因为没有有效的测试失败。阶段 6 使用离线假模型主动制造三类失败：暂时性超时、错误参数和失败测试结果。

超时案例只验证 Recovery 自动重试；错误参数和测试失败案例要求模型看到错误后生成不同动作。测试失败案例还必须同时检查工作区 diff 和后续测试结果，避免把“改过文件”误判成“改对了”。

### 实现和证据

`evals/fault_injection.py` 运行四个确定性案例并生成 JSON、Markdown 报告。结果为：

- 1 个 Middleware 自动重试案例；
- 3 个模型采取不同动作的案例；
- 3/4 最终成功；
- 错误参数案例的第二次参数不同；
- 一个测试失败案例产生 diff 且第二次测试通过；
- 一个负面案例产生 diff 但第二次测试仍失败。

本轮全量测试结果为 `34 passed`。四个案例中，2 个模型修复成功，1 个模型改变动作但仍失败。由于使用假模型，结果证明的是 Harness 对失败的处理语义，不代表真实模型在开放式任务中一定能修复代码。

实验报告见 [fault-injection-v1.md](fault-injection-v1.md)。

## 下一阶段：真实任务中的纠错对比

负面故障注入和一个真实隐藏评测已经证明评测器能区分“采取过修复动作”和“最终修复成功”。阶段 7 之后继续增加真实隐藏评测任务，比较 Baseline、Recovery 和完整 Harness 在测试失败后的恢复率。

## 阶段 7：真实 DeepSeek 隐藏评测与基线测试门 v1

### 目标和设计判断

第一次真实运行中，DeepSeek 在测试前就修复了代码，因此只证明了隐藏测试有效，没有证明失败后的纠错。为保证实验顺序，Policy 增加了可选的 `require_baseline_test`：第一次隐藏测试完成前，文件修改工具会被拒绝。

### 实现和证据

隐藏测试位于 workspace 外，Agent 只能看到 `run_tests` 的输出。第二次真实运行先产生一次 Policy 拒绝，然后第一次隐藏测试返回 `2 failed`，模型修改 `title_utils.py`，第二次测试返回 `2 passed`，最终 `completed=true`、`tests_passed=true`。

这是真实纠错的最小证据链。实验还暴露了原始 JSON 工具结果的 Recovery 分类缺陷，已经补充字符串 JSON 分类和即时测试事件记录；历史运行不回写。

本阶段全量测试结果为 `37 passed`。实验报告见 [real-recovery-v1.md](real-recovery-v1.md)。

## 阶段 8：真实 Recovery 矩阵 v1

### 目标和设计判断

为了确认真实纠错不是单个任务的偶然现象，又增加了 `fractional-tax` 和 `parse-percent` 两个单文件隐藏评测任务。它们继续使用 workspace 外测试、基线测试门和两次测试预算，保持实验条件一致。

### 实现和证据

四次真实运行中，第一次 `normalize-title` 在测试前自行修复，后三次都先失败后恢复：

```text
真实运行：4
最终测试通过：4
首次失败后恢复成功：3
```

`fractional-tax` 将错误的加法改为按比例计算，`parse-percent` 将 `20%` 转为 `0.2`。后三次运行都有一次 Policy 提前编辑拒绝、一次 Recovery failure/terminal、一次生产代码 diff 和第二次测试通过。

本阶段全量测试结果为 `41 passed`。实验报告见 [recovery-matrix-v1.md](recovery-matrix-v1.md)。

### 本阶段掌握的概念

- 第一次通过和失败后恢复是两种不同的能力证据；
- 多个任务都满足相同事件链，才能初步说明 Harness 行为具有可迁移性；
- 4/4 最终成功不能直接等同于 3/3 恢复成功，统计口径必须保留首次测试状态。

## 下一阶段：基线测试门对照实验

阶段 9 已完成一个固定 fixture 的 A/B 对照：关闭基线门时模型先修改后测试，开启基线门时先失败再修复。实验报告见 [baseline-gate-ablation-v1.md](baseline-gate-ablation-v1.md)。下一步应在更多 fixture 上重复对照，减少模型随机性带来的误判。

## 阶段 9：基线测试门 A/B 对照 v1

### 目标和设计判断

固定同一个 `normalize-title` 任务，只改变 `require_baseline_test`：A 组关闭，B 组开启。这样研究的是 Harness 执行顺序，而不是业务逻辑。

### 结果

A 组第一次测试直接通过，说明模型先修改了代码；B 组第一次测试失败，模型随后修改代码，第二次测试通过。两组最终都成功，但只有 B 组提供了“失败后纠错”的可观察证据。

本次对照说明：基线测试门主要提升实验的可观察性和顺序保证，不是直接保证模型修复正确。实验还保留了一次与业务无关的 `ls` 路径错误，证明日志需要继续区分工具探索错误和测试失败。

## 下一阶段：扩展对照矩阵

在更多 recovery fixture 上重复有门/无门对照，再讨论基线门对恢复率的影响。当前样本不足以做统计结论。

阶段 9 的扩展对照已覆盖 `fractional-tax` 和 `parse-percent`，两个任务都复现了无门时先修改、有门时先失败后修复的顺序差异。实验报告见 [baseline-gate-ablation-v2.md](baseline-gate-ablation-v2.md)。下一步进入跨文件 fixture。

## 阶段 10：跨文件 Recovery fixture 离线验证

### 目标和设计判断

单文件任务只能证明 Agent 修正一个局部实现。本阶段先构造一个需要同时修改 `order_parser.py` 和 `order_total.py` 的任务，观察测试工具、基线门和 diff 记录是否能承载跨文件修复。为了避免把 Harness fixture 验证误认为模型能力，本轮暂不调用 DeepSeek。

### 故障和调用链

初始 parser 交换了数量和单价，total calculator 又使用了错误的加法和税率逻辑。隐藏测试在 workspace 外，分别检查解析字典和最终总价。预期链路是：

```text
基线门拒绝提前编辑
  ↓
隐藏测试失败
  ↓
模型看到失败输出
  ↓
修改两个生产文件
  ↓
隐藏测试通过
```

### 离线结果

测试先确认原始项目失败，再写入两个正确的生产文件并确认测试通过。全量测试为 `43 passed`。新增 fixture 接入了 `RECOVERY_CASES`，真实运行命令使用 `--case order-total`。

### 本阶段能证明什么

真实运行 `20261107T052728Z-a1313c18` 首次隐藏测试为 `2 failed`，随后 DeepSeek 同时修改了两个生产文件，第二次测试为 `2 passed`。这证明了本次运行中的跨文件纠错链路。它不能估计跨文件 recovery 的总体成功率，因为样本只有一个真实任务；还需要不同业务 fixture 重复实验。

本次运行还帮助区分了两个日志概念：`test_run.success=false` 表示隐藏测试断言失败；`recovery_success` 表示测试工具本身正常返回，不等同于测试通过。另有一次 `ls /workspace` 探索路径错误，属于工具探索失败，不属于业务测试失败。

实验报告见 [cross-file-recovery-v1.md](cross-file-recovery-v1.md)。

## 阶段 11：第二个跨文件 Recovery fixture 离线验证

### 目标和设计判断

一个真实订单任务只能证明一次跨文件恢复。本阶段换成温度读数任务，保持基线门、隐藏测试位置、测试预算和模型配置不变，只改变业务错误。这样可以先验证跨文件 fixture 的可迁移性，再进行第二次真实模型调用。

### 故障和离线证据

`temperature_parser.py` 错误地改变数值并把单位小写，`temperature_report.py` 没有执行华氏转摄氏。隐藏测试同时检查两个文件之间的数据契约和转换结果。离线测试确认原始项目失败、同时修复两个文件后通过，全量测试为 `44 passed`。

本阶段仍然不能证明 DeepSeek 的真实跨文件恢复能力；它只证明新的任务输入和评测工具准备正确。真实运行后要继续检查首次失败、双文件 diff、最终通过和事件日志四项证据。

实验报告见 [cross-file-recovery-v2.md](cross-file-recovery-v2.md)。

### 真实运行结果

运行 `20261107T070150Z-d2125766` 使用同一个基线门和两次测试预算。第一次隐藏测试为 `2 failed`，Policy 拒绝两次提前编辑；DeepSeek 同时修改 `temperature_parser.py` 和 `temperature_report.py`，第二次隐藏测试为 `2 passed`。这与订单任务的证据链一致，说明跨文件 Recovery 的 Harness 语义在第二个业务场景中也成立。

本次运行仍包含一次 `ls /workspace` 的探索路径错误。它被记录为工具错误，但没有改变隐藏测试结果。两个真实跨文件任务都成功，只能说明当前两个 fixture 完成了恢复，不能直接计算总体恢复率。

## 学习和工程纪律

每完成一个阶段，都先做以下复盘，再决定是否提交 GitHub：

1. 用自己的话解释本阶段解决的失败模式；
2. 指出关键入口和调用链；
3. 说明测试证明了什么，不能证明什么；
4. 分析一个真实运行事件或 `run.json`；
5. 完成一个小练习，例如修改策略阈值、补充测试或判断日志；
6. 确认文档、代码和测试一起形成可复查的里程碑。

GitHub 提交代表一个可以解释的学习里程碑。当前已经具备的里程碑是：Baseline 十任务、Policy v1/v2、Recovery v1、Checkpoint/Replay v1、离线评测、故障注入、真实隐藏评测和 Recovery 矩阵 v1。下一次提交前应先完成本阶段复习，再决定是否进入基线测试门对照实验。
