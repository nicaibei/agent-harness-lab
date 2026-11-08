# Agent Harness 工程师学习与求职项目计划 v2

> 更新时间：2026-11-08
> 当前执行版本：v2
> 目标周期：2026-11-08 至 2027-04-15
> 求职方向：Agent Harness Engineer、Agent Engineer、Agent Platform Engineer、AI Infrastructure Engineer、LLM Runtime Engineer
> 旗舰项目：Agent Harness Lab——面向代码任务的可观测、可恢复、可评测 Issue-to-PR Agent Harness

## 当前定位

这个项目的目标不是证明“模型能修改代码”，而是证明我能设计和验证 Agent Runtime 的控制层。

系统接收结构化 Issue，在隔离工作区内完成代码探索、文件修改、测试运行、失败恢复和结果交付。Harness 负责控制 Agent 的行为边界、运行状态和证据链：

    Issue
      ↓
    任务理解与计划
      ↓
    代码探索与文件修改
      ↓
    测试与失败分类
      ↓
    Policy 检查与预算控制
      ↓
    Recovery、Checkpoint、Interrupt、Resume
      ↓
    Diff、Trace、测试报告和任务总结

最终要能回答：

> 当 Agent 不可靠、工具失败、任务被中断或操作存在风险时，系统如何继续运行、停止运行、恢复运行，并证明最后的结果确实正确？

## 当前基线

项目已经超过原计划中“只建立 Baseline”的阶段：

| 能力或实验 | 当前状态 | 证据 |
|---|---|---|
| Baseline Issue-to-PR Agent | 已完成基础版本 | 10 个任务、14 次尝试 |
| Policy Middleware | 已完成 v1/v2 基础能力 | allowlist、路径、敏感文件、删除和命令风险保护 |
| Recovery Middleware | 已完成基础能力 | 错误分类、有限重试、循环检测、终止事件 |
| Checkpoint / Replay | 已完成基础能力 | 运行事件、内存 checkpoint、replay 汇总 |
| 隐藏测试和故障注入 | 已完成 | Agent 只能通过工具看到测试结果 |
| 跨文件 Recovery 和消融 | 已完成初版 | 双文件任务和负面案例 |
| 配置异常 Recovery | 已完成实验 | 3 次重复运行均最终通过 |
| 启动导入错误 Recovery | 已完成实验，待整理提交 | 3 次有效运行均最终通过 |
| 正式评测矩阵 | 已启动 | Baseline、Recovery、消融和负面案例报告 |

当前数据说明：

- Baseline：10 个任务、14 次尝试，11 次成功，3 次基础设施失败；
- 真实 Recovery：24 次运行最终测试全部通过，其中 20 次经历了失败后恢复；
- 跨文件消融：8 个变体，可以区分单文件修改和完整修复；
- 负面案例：有 diff 但最终测试失败，证明 diff 不能单独作为成功标准。

这些结果只代表当前受控任务，不能直接推广到大型真实仓库。后续计划要优先补齐任务难度、数据划分、成本延迟和环境错误证据。

## 面向简历的五条能力主线

1. **Agent Runtime 理解**：能解释 LangGraph State、Runtime、Tool、Middleware、Backend 和 Subagent 的边界与调用链。
2. **运行时控制与安全**：实现路径白名单、命令风险分级、敏感文件保护、审批和预算控制。
3. **故障恢复与状态管理**：区分工具、测试、环境和 Harness 错误，支持有限重试、循环检测、Checkpoint、Interrupt、Resume 和 Replay。
4. **可复现评测**：使用隐藏测试、重复运行、消融实验和 train/holdout，单独统计模型失败与基础设施失败。
5. **工程交付与解释能力**：提供 CLI、Trace、Docker/CI、架构图、评测报告和面试可讲解的失败案例。

## v2 阶段总览

| 阶段 | 时间 | 核心问题 | 必须交付 |
|---|---|---|---|
| A. 重新基线与源码补课 | 2026-11-08 至 2026-11-15 | 是否真正理解底层 Runtime？ | 架构图、调用链、源码笔记、状态报告 |
| B. Harness 可靠性加固 | 2026-11-16 至 2026-12-07 | 能否分开模型、环境和 Harness 失败？ | 依赖/环境实验、错误分类、产物 schema、回归测试 |
| C. 正式评测基线 | 2026-12-08 至 2027-01-15 | Harness 效果能否重复测量？ | 30-50 个任务、train/holdout、安全和 Recovery 划分 |
| D. 可运行 Agent Runtime | 2027-01-16 至 2027-02-15 | 中断、预算和长任务如何稳定交付？ | CLI、Interrupt/Resume、Trace、预算、Docker/CI 初版 |
| E. 受控 Harness 优化 | 2027-02-16 至 2027-03-15 | 修改 Harness 是否改善 holdout？ | 3 轮优化、候选 diff、指标、回滚和安全回归 |
| F. 求职交付与开源准备 | 2027-03-16 至 2027-04-15 | 能否让第三方复现并理解项目？ | 稳定仓库、演示、报告、答辩稿、简历材料 |

阶段 A 和 B 是当前最重要的补齐。阶段 E 必须等阶段 C 的评测基线稳定后再开始。

## 当前优先事项

### 阶段 A：重新基线与源码补课

- 阅读 ARCHITECTURE.md、create_deep_agent()、filesystem、subagents、summarization、permissions Middleware 和 Backend；
- 写 docs/architecture.md 与 docs/source-notes.md；
- 画出 create_deep_agent() 调用链；
- 解释 run.json、diff.patch、首次测试和最终测试分别证明什么；
- 复盘配置 Recovery 与启动 Recovery。

通过标准：能够解释模型调用、工具调用、Backend 执行和 Harness 控制分别发生在哪一层。

### 阶段 B：Harness 可靠性加固

- 设计一个离线可复现的第三方依赖缺失或版本冲突 fixture；
- 将业务逻辑、工具、Policy、依赖环境、Harness 存储、超时和预算错误分开分类；
- 固定 run.json、diff.patch、事件和 test_runs 的 schema；
- 记录任务版本、代码版本、模型配置、测试命令和运行时间；
- 确保非 JSON 消息、部分输出和异常退出不会导致报告保存崩溃；
- 验证 Recovery 不会绕过 Policy，也不会无限重试。

通过标准：至少五类失败有稳定分类，且每类都有离线回归或明确的证据边界。

## 从实验走向工程竞争力

### 阶段 C：正式评测基线

先完成 30-50 个任务，划分 train、holdout、security、recovery、cross_file 和 long_context。每个任务必须有隐藏测试、成功判定、失败分类、预期 diff 范围和可重复运行记录。

指标包括最终测试通过率、Recovery 成功率、有效运行成功率、基础设施失败率、无效修改率、Policy 违规率、人工介入率、工具调用次数、P95 延迟、模型成本和 Replay 可复现率。

判定规则保持不变：

- completed=true 不等于修复成功；
- tests_passed=true 只表示最后一次隐藏测试通过；
- Recovery 成功必须满足首次测试失败、存在有效生产 diff、最后测试通过；
- diff 不能单独证明修改正确；
- 不把不同实验组和基础设施失败混成一个成功率。

### 阶段 D：可运行 Agent Runtime

交付稳定 CLI、统一 Trace、任务状态、Interrupt/Resume、Checkpoint 恢复、步数/时间/成本预算、失败后安全终止、Docker 和基础 CI。面试官应能运行一次任务、观察事件、注入失败、中断恢复并查看最终判定。

### 阶段 E：受控 Harness 优化

只允许优化 system prompt、工具描述、规划模板和少量 Middleware 参数。候选方案必须先通过 train、安全回归和成本门槛，再用 holdout 验证。禁止修改隐藏测试、任意业务代码、holdout 决策或绕过 Policy。

每轮保存候选 diff、配置、指标、保留/丢弃原因和失败案例。优化没有改善也要记录，不能只保留成功结果。

## 求职交付和硬性约束

最终仓库应包含 README、架构图、Agent Run 流程图、评测报告、安全设计、Recovery 失败案例、可复现实验说明、CLI、Docker/CI 和统一运行产物。

准备四个面试案例：

1. 为什么 Policy 不能只依赖 Prompt；
2. 为什么最终测试通过比 completed=true 更重要；
3. 一次 Recovery 失败以及如何区分模型、环境和 Harness 根因；
4. 一次消融实验如何证明跨文件任务不能只看 diff。

约束：

- 没有稳定 Baseline、任务集和隐藏测试之前，不做自动优化；
- 不把配置、导入、依赖和业务逻辑错误混在一个 fixture 中；
- 不把基础设施失败计入模型代码失败；
- 不用 diff 单独判定成功；
- 每个新模块必须有失败案例、测试和文档；
- 每次实验保存代码版本、配置、结果摘要和原始运行产物；
- 没有证据支持的指标不进入简历；
- 暂不扩展复杂 Web UI 和多 Agent。

## 接下来两周

### 2026-11-08 至 2026-11-15

- [ ] 完成 docs/architecture.md；
- [ ] 完成 docs/source-notes.md；
- [ ] 画出 create_deep_agent() 调用链；
- [ ] 复盘配置与启动 Recovery；
- [ ] 检查启动 Recovery 改动、测试和报告；
- [ ] 暂不启动新的真实 DeepSeek 调用。

### 2026-11-16 至 2026-11-29

- [x] 设计并实现依赖缺失 fixture；
- [x] 完成离线失败和环境错误分类；
- [x] 增加环境失败后的 Policy 停止策略和 Recovery 分类；
- [x] 增加 Harness 自身失败的回归测试；
- [x] 完成受控离线依赖准备 fixture 和 Agent 图级回归；
- [x] 完成一次真实环境准备运行并保存独立报告；
- [x] 完成单包版本冲突 fixture 和离线 Agent 图级回归；
- [x] 完成一次版本冲突真实运行并保存独立报告；
- [x] 完成 Checkpoint / Interrupt / Resume v1 离线实验；
- [x] 完成 Checkpoint 跨进程恢复 v2 离线实验；
- [ ] 固定运行产物 schema 的最终版本；
- [ ] 复盘环境停止与环境准备两个实验的边界；
- [ ] 评估是否需要多包传递依赖实验；

## 项目最终表达

> 我不仅会调用模型构建 Agent，还能设计 Agent 的运行时控制、权限边界、故障恢复、状态管理和评测系统，并用可复现实验证明这些机制在什么条件下改善了可靠性、可运营性和工程可用性。

---

## 附录：原始计划草案

以下原始章节保留作历史参考。后续执行以本页 v2 的阶段、时间、验收标准和约束为准。


## 1. 总目标

基于 Deep Agents 和 LangGraph，构建一个可以处理真实代码 Issue 的 Agent Harness。系统能够分析任务、读取代码、修改文件、运行测试、处理失败、生成 diff，并提供权限控制、人工审批、断点恢复、Replay、Trace 和评测能力。

最终成果不是一个简单的聊天机器人，而是一套能够证明以下能力的工程系统：

- 理解 Agent Runtime、Middleware、Backend 和状态管理；
- 设计长任务 Agent 的上下文、权限、恢复和成本控制；
- 构建可复现的 Agent 评测集和实验流程；
- 用真实数据证明 Harness 对成功率、稳定性、安全性和成本的影响；
- 能够阅读、扩展并向开源 Agent 项目贡献代码。

## 2. 项目定位

### 2.1 核心场景

用户提交一个 GitHub Issue 或结构化任务，Agent 在隔离工作区中完成：

```text
Issue
  ↓
任务理解与计划
  ↓
代码仓库分析
  ↓
文件修改
  ↓
测试运行
  ↓
失败诊断与恢复
  ↓
权限检查与人工审批
  ↓
Checkpoint / Replay / Trace
  ↓
Diff、测试报告和任务总结
```

### 2.2 Harness 的核心模块

第一版只实现三个核心模块，避免范围失控：

1. **Policy Middleware**：文件白名单、命令风险分级、审批和预算限制。
2. **Recovery Middleware**：失败分类、重试、替代策略和循环检测。
3. **Checkpoint/Replay**：事件记录、任务中断、恢复和历史重放。

Deep Agents 已经提供的上下文压缩、文件化输出和子 Agent 能力先作为底座使用，理解问题后再做增强。

## 3. 时间规划总览

| 阶段 | 时间 | 主要目标 | 关键产出 |
|---|---|---|---|
| 阶段 0 | 2026-11-02 至 2026-11-15 | 理解 Deep Agents Harness | 架构图、调用链图、源码笔记、最小实验 |
| 阶段 1 | 2026-11-16 至 2026-11-30 | 建立 Baseline Agent | 可运行 Agent、10 个任务、运行日志 |
| 阶段 2 | 2026-12-01 至 2027-01-15 | 实现三个 Harness 模块 | Policy、Recovery、Checkpoint/Replay |
| 阶段 3 | 2027-01-16 至 2027-02-15 | 建立正式评测 | 30-50 个任务、指标、Baseline 对比 |
| 阶段 4 | 2027-02-16 至 2027-03-15 | 实现 Harness 自动优化 | train/holdout、三轮优化实验 |
| 阶段 5 | 2027-03-16 至 2027-04-15 | 产品化和求职准备 | CLI、API、演示、报告、简历材料 |

## 4. 阶段 0：理解 Deep Agents

**时间：2026-11-02 至 2026-11-15**

### 学习顺序

1. `libs/ARCHITECTURE.md`
2. `libs/deepagents/deepagents/graph.py`
3. `libs/deepagents/deepagents/middleware/filesystem.py`
4. `libs/deepagents/deepagents/middleware/subagents.py`
5. `libs/deepagents/deepagents/middleware/summarization.py`
6. `libs/deepagents/deepagents/middleware/permissions.py`
7. `libs/deepagents/deepagents/backends/`
8. `examples/better-harness/README.md`
9. `libs/deepagents/tests/unit_tests/`

### 必须回答的问题

- `create_deep_agent()` 如何组装模型、工具、Middleware 和 Backend？
- Deep Agents 与 LangChain Agent、LangGraph Runtime 的边界是什么？
- Tool 和 Middleware 的职责有什么区别？
- Middleware 在模型调用和工具调用的哪些阶段运行？
- 文件读写最终由哪个 Backend 执行？
- 主 Agent 和 Subagent 如何隔离上下文和状态？
- 消息历史什么时候压缩或 offload？
- Checkpoint、Interrupt 和 Resume 如何配合？
- 权限控制为什么不能只依赖 Prompt？

### 阶段产出

- `docs/architecture.md`：三层架构和运行链路；
- `docs/source-notes.md`：源码阅读笔记；
- 一张 `create_deep_agent()` 调用链图；
- 一个最小实验：读取文件、修改文件、运行测试；
- 一份 Agent Run 事件日志；
- 一次上游 Issue 或测试的阅读记录。

### 阶段验收

能够不看资料解释一次请求从用户输入到最终响应的完整路径，并说明每个 Harness 能力放在 Middleware、Backend 或 Runtime 的原因。

## 5. 阶段 1：建立 Baseline Agent

**时间：2026-11-16 至 2026-11-30**

### 项目仓库

建立独立仓库：`agent-harness-lab`。

Deep Agents 原仓库保留为上游学习代码，个人项目只依赖它，不把整个上游仓库改成个人项目。

建议结构：

```text
agent-harness-lab/
├── agent_app/
├── harness/
├── evals/
├── docs/
├── tests/
├── pyproject.toml
└── README.md
```

### Baseline 功能

- 接收结构化 Issue；
- 读取代码文件；
- 修改文件；
- 执行项目测试；
- 生成 Git diff；
- 保存结构化运行日志；
- 返回成功、失败和失败原因。

### 第一批任务

准备 10 个小型 Python Issue：

- 3 个单文件 Bug；
- 2 个跨文件修改；
- 2 个需要补充测试；
- 2 个测试失败后修复；
- 1 个权限或危险命令场景。

### 阶段验收

- 至少 5 个任务可以重复运行；
- 至少 3 个任务成功完成；
- 每个任务都有结构化结果；
- 运行日志能够还原主要工具调用；
- README 能说明启动、运行和评测方式。

## 6. 阶段 2：实现 Harness 核心能力

**时间：2026-12-01 至 2027-01-15**

### 6.1 Policy Middleware

实现：

- 工作区路径白名单；
- 禁止访问工作区之外的文件；
- Shell 命令风险等级；
- 高风险命令人工审批；
- 单任务最大步数、时间和预算；
- 拒绝策略的结构化日志。

测试场景：

- 访问工作区外文件；
- 删除命令；
- 安装依赖命令；
- 超出预算；
- 审批拒绝后继续任务。

### 6.2 Recovery Middleware

实现：

- 工具错误分类；
- 可重试错误和不可重试错误判断；
- 指数退避或有限重试；
- 测试失败后的修复提示；
- 替代工具或替代策略；
- 重复操作和循环检测；
- 最大恢复次数。

测试场景：

- 命令返回非零退出码；
- 文件路径错误；
- 测试失败；
- 相同工具调用重复出现；
- 重试次数耗尽。

### 6.3 Checkpoint 和 Replay

实现：

- 每一步事件记录；
- 工具输入和输出摘要；
- 当前任务状态保存；
- 中断后恢复；
- 历史运行重放；
- 两次运行的事件差异对比。

### 阶段验收

- 三个模块分别有单元测试；
- 至少 5 个故障场景可以被检测或恢复；
- 能演示一次危险操作被拒绝；
- 能从中断状态继续任务；
- 能 Replay 一次完整运行；
- 完成一份架构设计文档。

### 上游贡献

12 月开始关注 Deep Agents 的 Issue 和测试，优先尝试：

- 文档修正；
- 测试补充；
- Windows 兼容性修复；
- 小型 Bug 修复。

不要在没有理解现有设计前修改核心公共 API。

## 7. 阶段 3：建立正式评测系统

**时间：2027-01-16 至 2027-02-15**

### 评测集

先准备 30-50 个任务，再根据执行成本扩展到 50-100 个。分组如下：

- `train`：允许用于 Prompt 和 Harness 优化；
- `holdout`：只用于最终验证；
- `security`：路径、命令和权限测试；
- `recovery`：测试失败、工具失败和中断；
- `long_context`：长输出、跨文件和复杂任务。

### 指标

- 任务成功率；
- 测试通过率；
- 工具调用次数；
- 平均和 P95 运行时间；
- Token 和成本；
- 自动恢复成功率；
- 人工介入率；
- 权限违规率；
- 无效修改率；
- Replay 可复现率。

### 对比实验

至少运行三个版本：

1. 原始 Baseline Agent；
2. 加入 Policy、Recovery、Checkpoint/Replay 的 Agent；
3. 经过优化的 Harness Agent。

不能提前编造结果。所有提升数字都必须来自固定任务集和可复现实验。

### 阶段验收

- 评测任务可重复运行；
- train 和 holdout 严格分离；
- 报告中包含失败案例，而不只展示成功案例；
- 能解释每个指标的定义和局限；
- 完成第一版评测报告。

## 8. 阶段 4：Harness 自动优化

**时间：2027-02-16 至 2027-03-15**

参考 `examples/better-harness` 实现外层优化 Agent：

```text
读取 train 失败案例
  ↓
分析失败原因
  ↓
生成候选 Prompt / Tool / Middleware 修改
  ↓
运行 train
  ↓
指标改善则保留，否则丢弃
  ↓
使用 holdout 验证
```

第一版只允许修改：

- system prompt；
- 工具描述；
- 规划模板；
- 少量 Middleware 参数。

暂时不允许外层 Agent 任意修改整个代码库，避免无法分析因果关系。

### 阶段验收

- 至少 3 轮候选优化；
- 每轮保存候选 diff、指标和保留/丢弃原因；
- holdout 没有被用于训练决策；
- 至少展示一个优化前后的失败案例；
- 安全测试没有因优化而退化。

## 9. 阶段 5：产品化和求职材料

**时间：2027-03-16 至 2027-04-15**

### 工程交付

- 稳定 CLI；
- 简单 API；
- 统一事件和 Trace 格式；
- Docker 启动方式；
- GitHub Actions；
- 基础配置和错误提示；
- 中英文 README；
- 运行示例和故障排查文档。

### 展示材料

- 一张系统架构图；
- 一张 Agent Run 流程图；
- 一份评测报告；
- 一份失败案例分析；
- 一份安全设计文档；
- 一个 3 分钟演示视频；
- 一份项目答辩稿；
- 一段英文项目介绍。

### 简历表达

最终简历描述必须使用真实数据，格式可以参考：

> 基于 Deep Agents 和 LangGraph 构建可恢复的 Issue-to-PR Agent Harness，设计 Policy、Recovery、Checkpoint/Replay Middleware，并建立包含 train/holdout/security 集的代码任务评测系统；通过可复现实验验证 Harness 对任务成功率、工具调用效率和故障恢复能力的影响。

## 10. 每周执行节奏

建议每周投入 25-30 个有效小时，不要求每天固定时长。

| 时间 | 任务 |
|---|---|
| 周一 | 阅读源码、明确本周一个问题 |
| 周二 | 设计接口和实验 |
| 周三 | 编码核心功能 |
| 周四 | 补测试和处理失败 |
| 周五 | 跑评测、分析数据 |
| 周六 | 写文档、整理 GitHub、做面试题 |
| 周日 | 复盘、提交 Git、安排下周 |

每周必须更新：

```text
docs/progress.md
docs/decisions/
evals/reports/
```

每周记录四件事：

- 本周完成了什么；
- 哪些任务失败；
- 失败的根因是什么；
- 下周只解决哪一个主要问题。

## 11. 并行能力线

### Python 和工程基础

- 异步编程和并发控制；
- 类型系统和数据模型；
- pytest、mock 和集成测试；
- 包管理和项目发布；
- Git、Docker 和 CI；
- 队列、超时、重试和资源限制；
- 文件权限、进程隔离和沙箱。

### Agent Runtime

- LangGraph State；
- Checkpoint；
- Interrupt 和 Resume；
- Streaming；
- Middleware 生命周期；
- Tool Calling；
- Subagent 上下文隔离；
- 长上下文和消息压缩。

### 评测和研究能力

- 任务集设计；
- train/holdout 划分；
- 失败分类；
- 成本和延迟统计；
- 消融实验；
- 可复现运行；
- 评测结果的局限性分析。

### 面试准备

从 2027 年 1 月开始，每周至少完成：

- 1 道 Python 编程题；
- 1 个 Agent 系统设计问题；
- 1 个项目模块的口头讲解；
- 1 次失败案例复盘。

2027 年 3 月开始准备针对字节、小米及其他大厂的项目介绍、系统设计和行为面试。

## 12. 硬性约束

- 2027 年 1 月前不做复杂 Web UI；
- 没有稳定 Baseline 和评测集之前不做自动优化；
- 没有稳定单 Agent 之前不扩展复杂多 Agent；
- 不把整个 Deep Agents 上游仓库改成个人项目；
- 不使用没有实验依据的指标；
- 不同时维护多个主项目；
- 每个新模块必须有失败案例和测试；
- 每次实验必须保存配置、代码版本和结果摘要；
- 任何 API 或安全策略调整都要写设计决策记录。

## 13. 当前两周行动清单

### 第 1 周

- [ ] 阅读 `libs/ARCHITECTURE.md`；
- [ ] 阅读 `deepagents/graph.py` 中的 `create_deep_agent()`；
- [ ] 阅读 filesystem、subagents、summarization、permissions Middleware；
- [ ] 阅读 Backend 协议和 State/Filesystem Backend；
- [ ] 画出三层架构图；
- [ ] 记录一次最小 Agent Run；
- [ ] 创建 `agent-harness-lab` 仓库并写 README 初版。

### 第 2 周

- [ ] 选择一个小型 Python 测试仓库；
- [ ] 设计 10 个 Issue 任务；
- [ ] 实现 Baseline 的文件读取和修改；
- [ ] 接入测试运行；
- [ ] 保存 Git diff 和运行日志；
- [ ] 完成至少 3 个成功任务；
- [ ] 写出第一版失败分析。

## 14. 最终验收标准

到 2027 年 4 月投递前，项目至少应具备：

- 可运行的 Issue-to-PR Agent；
- Policy、Recovery、Checkpoint/Replay 三类 Harness 能力；
- 30-100 个可重复评测任务；
- train/holdout/security 数据划分；
- Baseline 与增强版本的对比实验；
- 真实的成功率、恢复率、成本和延迟数据；
- 至少一次上游开源贡献；
- CLI、Docker 和基础 CI；
- 架构图、演示视频、评测报告和失败案例；
- 能用 5 分钟解释设计、取舍、指标和局限；
- 能回答为什么某项能力应该放在 Harness，而不是普通 Tool 或业务代码中。

最终项目的核心表达是：

> 我不仅会调用模型构建 Agent，还能设计 Agent 的运行时、上下文、权限、恢复、评测和优化机制，并用可复现实验证明这些机制确实改善了 Agent 的可靠性和工程可用性。
