# Agent Harness Lab 对话交接文档

本文档用于把当前对话的实验状态交给下一个对话。下一个对话应先阅读本文档，再继续实验，避免重复运行已经完成的模型任务或误判 GitHub 状态。

## 1. 项目身份

- 本地仓库：`D:\langgraph_learning\agent-harness-lab`
- GitHub 仓库：`https://github.com/nicaibei/agent-harness-lab.git`
- 当前分支：`main`
- 四项 train Recovery 重复评测已提交：`77e78b2 docs(evals): record train recovery repeat batch`；不要重复调用模型。
- usage 采集、自动范围判定、测试和文档随本次里程碑提交；全量离线回归 `92 passed`。最近工作以第 22 节为准。
- 本地最近记录的 `origin/main`：`e676de0`；仍有本地提交未推送，本次仅执行用户要求的本地提交。
- Git 状态是 2026-11-12 的本地核验记录，远端未重新联网确认；最新提交以 `git log` 和 `git status` 为准。

之前推送和远端查询因 GitHub 连接被重置或无法连接 443 失败。提交保存在本地；网络正常时可执行：

```powershell
cd D:\langgraph_learning\agent-harness-lab
git -c safe.directory=D:/langgraph_learning/agent-harness-lab push origin main
```

推送成功后再用 `git status --short --branch` 确认分支不再显示 `ahead`。

## 2. 用户学习要求

用户是初学者，项目目标是理解 Agent Harness，而不是只让模型完成代码任务。每次新实验必须遵守下面的流程：

### 个人教学和协作偏好

- 这是一个学习过程，不是把所有工作交给 Agent 后只看最终文件。每完成一部分，都要说明做了什么、为什么做、修改了什么，以及这一步能学到什么。
- 用户的设计经验还不多，所以主要设计由助手负责；用户提出的理解和方案需要被认真评价，明确指出正确、部分正确或错误，再给出完整标准答案。
- 不要一开始就埋头写代码。先讲概念和目标，再说明这一步属于 Baseline、Policy、Recovery、Replay 还是评测设计。
- 在写代码前让用户做一次设计判断，例如判断失败模式、控制变量、成功标准和证据边界；用户回答后再继续实现。
- 实现完成后要逐段解释关键类、方法、调用链、测试和运行结果，尤其解释 `run.json`、`diff.patch`、首次测试和最终测试之间的关系。
- 每个阶段安排一个小练习，例如修改一个规则、补一个测试或分析一条运行日志；不要只给结论。
- GitHub 提交代表用户已经理解这阶段内容。必须完成复盘并确认用户能解释主要结果后，才进入 commit/push。
- 实验开始前和结束后都要解释，不能只报告“成功”或“测试通过”。

1. 实验开始前说明目的、要研究的失败模式、故意设置的错误、Agent 应如何处理、控制变量、成功标准、是否调用 DeepSeek、是否消耗额度、是否需要租服务器。
2. 代码实施前让用户先表达设计理解；用户的回答无论正确、部分正确还是错误，都要给出完整标准答案和修正点。
3. 实验完成后解释实际发生了什么、修改了什么、首次和最终测试、Policy/Recovery 做了什么、能证明什么、不能证明什么，以及用户学到了什么。
4. 真实调用按当前授权规则执行：单个实验批次预计少于 10 次调用时默认授权；预计 10 次及以上时先询问用户。仍需在实验开始前说明用途、调用上限和资源消耗。
5. GitHub 提交前必须完成复盘。到达适合提交的里程碑时主动提醒用户；不要把本地 commit 误说成已经推送到 GitHub。
6. 不要埋头连续做很多实验。完成一个阶段后先解释结果，再继续下一阶段。
7. 当前所有实验都在 `agent-harness-lab`，不要切换到 `D:\langgraph_learning\deepagent` 做项目实验。
8. 普通小型 fixture 和当前实验不需要租服务器。只有项目很大、依赖安装困难、需要 GPU 或本机运行时间明显过长时，才提前告知用户考虑租服务器。

## 3. 已完成的 Harness 能力

项目已经从最小 Baseline 扩展到可观测的评测 Harness：

- Backend CRUD、路径映射、State/Filesystem/CompositeBackend 对比；
- 最小 Issue-to-PR Baseline，10 个 calculator 任务；
- DeepSeek OpenAI 兼容接口接入；
- Policy Middleware v1/v2：工具 allowlist、路径检查、敏感文件保护、删除保护、命令风险分类、工具调用预算；
- 基线测试门：要求 Agent 在第一次文件修改前先运行测试；
- Recovery Middleware：工具失败分类、有限重试、循环检测、终止事件和事件记录；
- Checkpoint/Replay：运行事件、内存 checkpoint 和 replay 汇总；
- 故障注入、Policy 拒绝、Recovery 负面案例；
- 外部隐藏测试：隐藏测试位于 workspace 外，Agent 只能通过 `run_tests` 工具看到结果；
- 跨文件 Recovery、文件级消融、跨文件负面案例；
- 仓库形态 fixture：配置文件、包目录、多个业务模块、分层隐藏测试；
- 正式评测矩阵和重复运行报告。

关键实现入口：

- `agent_app/baseline.py`：最小 Agent 运行入口和工具事件记录；
- `harness/policy.py`：Policy Middleware；
- `harness/recovery.py`：Recovery Middleware；
- `harness/checkpoint.py`：checkpoint 和 replay 汇总；
- `evals/real_recovery.py`：真实隐藏测试 Recovery runner、任务定义和运行产物保存；
- `evals/reports/`：正式汇总和重复实验报告；
- `examples/`：各种受控故障 fixture；
- `tests/`：离线和集成测试。

## 4. 当前正式评测统计

数据来自 `evals/reports/formal-evaluation-matrix-v1.json`：

| 实验组 | 当前结果 | 解释 |
| --- | --- | --- |
| Baseline | 14 次尝试、10 个任务、11 次成功、3 次基础设施失败 | 有效尝试成功率 100%；基础设施失败不能算模型代码失败 |
| 故障注入 | 4 个案例，3 个成功，1 个失败 | Middleware 重试和模型纠错已能区分 |
| 真实 Recovery | 24 次运行，24 次最终通过，20 次失败后恢复 | 最终通过不等于所有运行都发生了 Recovery |
| 跨文件消融 | 8 个变体，双文件都通过 2 个 | 证明跨文件任务必须同时修复相关文件 |
| 跨文件负面 | 2 个修改但最终失败 | 证明 diff 存在不等于修复正确 |

必须继续保持的判定规则：

- `completed=true` 只表示 Agent 调用正常结束；
- `tests_passed=true` 才表示最后一次隐藏测试通过；
- Recovery 成功需要首次测试失败、存在有效生产 diff、最后测试通过；
- `diff` 只证明文件发生变化，不能单独证明修改有效；
- Policy 拒绝、工具探索错误、测试失败和最终测试通过必须分别看事件和 `test_runs`；
- 不把 Baseline、Policy、Recovery、消融等不同实验合并成一个总体成功率。

## 5. 最近完成的配置异常实验

实验名称：配置文件异常 Recovery v1，任务 ID：`real-recovery-inventory-config`。

### 离线设计

新增 fixture：`examples/recovery_inventory_config_repo/`。

Python 模块已经正确，唯一故意错误是：

```json
{
  "tax_rate": 20,
  "currency": "USD"
}
```

系统约定 `tax_rate` 是小数税率，正确值应为 `0.2`。隐藏测试仍在 `evals/hidden_tests/test_inventory_repo.py`，workspace 外不可编辑。基线测试门开启，最多两次隐藏测试。

离线结果：目录层测试通过，配置层和服务层失败，即 `2 failed, 1 passed`；只把配置改回 `0.2` 后三项全部通过。离线阶段不调用 DeepSeek，不消耗额度，不需要租服务器。

### 第一次真实运行

运行 ID：`20261107T095602Z-fe966317`。

- 首次隐藏测试：`2 failed, 1 passed`；配置返回 `20.0`，服务总额变成 `420.0`；
- DeepSeek 只修改 `config/checkout.json`，把 `20` 改成 `0.2`；
- `inventory_app/settings.py`、`catalog.py`、`checkout.py` 没有进入 diff；
- 第二次隐藏测试：`3 passed`；
- `completed=true`、`tests_passed=true`、`execution_error=null`。

产物：

- `runs/recovery/20261107T095602Z-fe966317/run.json`
- `runs/recovery/20261107T095602Z-fe966317/diff.patch`
- [实验说明](config-recovery-v1.md)

### 两次重复运行

重复运行 ID：

- `20261107T100134Z-9f4eff5c`
- `20261107T100202Z-8eb54354`

三次合并结果：

- `3/3` 首次测试失败后最终通过；
- `3/3` 只修改 `config/checkout.json`；
- 三次 diff 均为 136 字符，内容完全相同；
- 三次都没有修改 Python 模块或隐藏测试；
- 每次都有一次 `ls` 探索工具错误，但没有影响业务测试修复。

重复报告：`evals/reports/repeat-real-recovery-inventory-config.md`。

这只能说明当前受控任务在当前模型配置下表现出初步稳定性，不能推断其他配置格式、复杂依赖或大型真实仓库的总体成功率。

## 6. 最近完成的项目启动错误实验

实验名称：项目启动错误 Recovery v1，任务 ID：`real-recovery-startup-import`。

新增 fixture：`examples/recovery_startup_repo/`。唯一故障是 `service_app/__init__.py` 导入不存在的 `service_app.configs`；正确模块是 `service_app.config`。`config.py`、`app.py` 和 `__main__.py` 都是正确的，隐藏测试在 workspace 外。

一次真实运行和两次有效重复都满足：首次 `2 failed, 1 passed`，最终 `3 passed`，只修改 `service_app/__init__.py`，三次 diff 都是 304 字符。有效运行 ID：

- `20261107T102823Z-e6225779`
- `20261107T103524Z-1109cb1b`
- `20261107T103640Z-ee3b3b33`

第一次重复调用 `20261107T103219Z-e6a6e914` 暴露了 Harness 缺陷：`real_recovery.py` 直接对每条 `run_tests` 消息执行 `json.loads`，非 JSON 消息导致报告保存前崩溃。现在已增加 `_parse_test_runs` 容错解析和离线回归测试；这次 Harness 失败不计入模型 Recovery 失败。

实验文档：`docs/startup-recovery-v1.md`；重复报告：`evals/reports/repeat-real-recovery-startup-import.md`。

## 7. 最近测试和 Git 状态

最近全量测试：

```text
57 passed
```

另有一个 `PytestCacheWarning`，原因是当前 Windows 环境无法写入 `.pytest_cache`；不是测试失败，也没有改变测试结论。

最近功能提交：

```text
2b4b0b3 feat(evals): add configuration recovery experiment
```

该提交包含配置 fixture、离线测试、真实运行报告、重复报告、正式矩阵更新和实验文档。它已经在本地 commit，但还没有推送到 GitHub。本交接文档也已本地提交；启动错误 fixture、解析容错修复和最新报告目前仍是未提交改动。

## 8. 最近完成的依赖环境实验

实验名称：第三方依赖环境错误 Recovery v1，任务 ID：real-recovery-missing-dependency。

本阶段选择“环境失败即停止”，不研究依赖安装能力。新增 fixture 声明一个执行环境中不存在的第三方包，隐藏测试输出 ENVIRONMENT_FAILURE 标记。Harness 现在会：

- 将结构化结果分类为 failure_class=environment；
- 让 Recovery 记录环境失败并停止重试；
- 让 Policy 在环境失败后拒绝 write_file、edit_file 和 delete；
- 在运行报告中保存 outcome、environment_blocked 和 test_failure_classes。

离线结果：

- 外部隐藏测试：2 passed, 1 failed；
- _run_hidden_tests 正确返回 failure_class=environment；
- 环境失败后的文件修改拒绝回归通过；
- 全量测试：62 passed，只有 Windows .pytest_cache 写入警告；
- 离线阶段没有调用 DeepSeek，也不需要服务器。

实验说明：docs/dependency-environment-v1.md。随后在用户授权下完成一次真实运行：completed=true、tests_passed=false、outcome=environment_blocked、environment_blocked=true、生产 diff 为 0 字符。该运行证明 Agent 遵守了环境失败停止边界，不计入正式 Recovery 成功率。

真实运行 ID：20261108T041536Z-8ac3139d。独立报告：evals/reports/real-recovery-missing-dependency.md。事后修正了真实运行器的 Middleware 顺序并增加离线回归，没有重复调用模型。

## 9. 最近完成的受控依赖准备实验

实验名称：受控离线依赖准备 Recovery v1，任务 ID：real-recovery-missing-dependency-install。

离线阶段完成了固定 wheel、受限 prepare_dependency 工具、Policy 前置失败门槛和 Agent 图级回归。全量测试为 65 passed。

随后在用户授权下完成一次真实运行：首次环境失败后调用受限准备工具，第二次隐藏测试 3 passed，completed=true、tests_passed=true、outcome=environment_recovered、environment_prepared=true、生产 diff 为 0 字符。

真实运行 ID：20261108T044830Z-057a2535。独立报告：evals/reports/real-recovery-missing-dependency-install.md。该结果是环境恢复成功，不计入正式代码 Recovery 成功率。

事后发现长 pytest JSON 被截断导致 Recovery 分类事件不完整，已修复完整结构化解析并增加离线回归，没有重复调用模型。

## 10. 最近完成的版本冲突离线实验

实验名称：单包精确版本冲突 Recovery v1，任务 ID：real-recovery-dependency-version-conflict。

设计为环境预加载 1.0.0、项目要求 2.0.0，Harness 只允许使用预置的 2.0.0 wheel。离线阶段没有调用模型。

全量测试为 69 passed，针对性 Agent 图回归为 4 passed。首次冲突能分类为 dependency_conflict，受限工具替换后最终测试通过，生产 diff 为空。

实验说明：docs/dependency-conflict-v1.md。真实模型运行尚未开始，也没有把该实验加入正式 Recovery 成功率。

用户随后授权完成一次真实运行：首次测试识别 dependency_conflict，Agent 调用受限 prepare_dependency 切换到固定 2.0.0，第二次测试 3 passed，completed=true、tests_passed=true、outcome=environment_recovered、environment_prepared=true、生产 diff 为 0 字符。运行 ID：20261108T051319Z-bffefc3d。独立报告：evals/reports/real-recovery-dependency-version-conflict.md。该结果不计入正式代码 Recovery 成功率。

## 11. 最近完成的 Checkpoint / Interrupt / Resume 离线实验

实验名称：Checkpoint / Interrupt / Resume v1，任务 ID：checkpoint-resume-v1。

在写文件之前配置 interrupt_on，第一次运行进入 waiting，暂停前没有生产 diff；使用同一个 thread_id resume 后，write_file 执行一次，测试通过，checkpoint 从 4 增加到 12，replay 记录 waiting、resumed、test_run 和 finished。运行 ID：20261108T053319Z-69a171fa。

实验说明：docs/checkpoint-resume-v1.md。该实验使用 Fake Model，没有调用 DeepSeek，也没有加入模型成功率。

## 12. 最近完成的 Checkpoint 跨进程恢复实验

实验名称：Checkpoint / Interrupt / Resume v2，任务 ID：checkpoint-resume-v2-process-restart。

当前环境没有 SQLite 或 Postgres Checkpointer，因此新增了不依赖第三方包的 FileCheckpointSaver。pause 进程在 write_file 前中断并退出，resume 进程重新创建 Agent、读取同一份 checkpoint-store.json，再使用相同 thread_id 恢复。

离线结果：运行 ID 为 20261108T061342Z-d7821869，paused=true、resumed=true、暂停前无副作用、checkpoint 从 4 增加到 12、最终测试通过，replay 记录 process_restarted、run_resumed、test_run 和 run_finished。实验使用 Fake Model，没有调用 DeepSeek。全量测试为 71 passed。

实验说明：docs/checkpoint-resume-v2.md。跨进程回归测试已经加入。

## 13. 已冻结运行产物 schema v1

新的 `run.json` 使用 `schema_version=run.v1`，新的 replay 使用 `schema_version=replay.v1`。统一字段包括 `completed`、`tests_passed`、`execution_error`、`test_runs`、`diff`、`events` 和 `replay`。Checkpoint v1 使用 `in-memory`，Checkpoint v2 使用 `file-json`；旧产物没有 schema 版本，继续按 legacy 处理。说明见 docs/run-artifact-schema-v1.md。

## 14. 最近完成的架构和源码核对

已完成 `docs/architecture.md` 与 `docs/source-notes.md` 的源码证据补充：记录 `create_deep_agent()` 从 model/profile/backend 解析，到 Filesystem、SubAgent、Summarization、Skills、Memory、HumanInTheLoop 和自定义 middleware，再到 `create_agent(checkpointer=..., store=...)` 的组装链。源码依据是 `D:\langgraph_learning\deepagent` 当前 checkout，没有修改上游仓库。

## 15. 正式评估集 v1

已建立 `evals/formal_tasks.json` 和 `evals/formal_task_manifest.py`。当前有 30 个唯一任务：train 16 个，holdout 14 个；覆盖 Baseline、Recovery、跨文件、仓库集成、环境、Runtime 和 Policy 安全 strata。校验器要求 fixture 不跨 train/holdout，所有 evaluator 和预期文件路径存在。说明见 `docs/formal-evaluation-set-v1.md`。

这只是任务清单和 split 冻结，不代表 30 个任务已经用统一 runner 完成真实模型评测。已增加 `evals/formal_runner.py`，它可以生成不调用模型的执行计划、运行离线 Harness node，或在明确授权后执行一个 train 模型任务，并保持 `run.v1` 产物和独立实验分母。

离线执行入口已经验证：Checkpoint v1/v2 和 6 个 Policy 安全 node 共 8 个任务，`8/8` 通过，`model_calls=0`。这只是 Harness 回归证据，不计入模型成功率。

真实模型冒烟运行已完成三个 train 任务：`calculator-add-floats`（`20261108T073634Z-282eb3b6`，5 passed，10.817s）、`calculator-subtract-negative`（`20261108T074306Z-583d14dc`，5 passed，10.030s）和 `calculator-divide-fraction`（`20261108T081509Z-d73a68d7`，5 passed，10.558s）。三个 diff 都只改预期测试文件；第三个摘要为 `evals/reports/formal-model-calculator-divide-fraction-v1.json`。没有记录 token/cost，因此不能计算成本，也不能把这三次冒烟结果外推为完整 Baseline 成功率。

## 17. 真实 SDK 模块迁移验证 v1

已完成真实模块迁移验证：从 `D:\langgraph_learning\deepagent` 复制 `deepagents/backends/composite.py` 到隔离 workspace，注入一个 `/memories/` 路由边界缺陷。离线 Fake Model 运行验证了 Harness 判定链路；随后在单独授权后完成一次真实 DeepSeek 运行，运行 ID 为 `20261108T090526Z-99d9d7f9`，首次测试 `2 failed`，DeepSeek 通过 `grep/read_file` 定位后修改 `composite.py`，第二次测试 `2 passed`，只修改预期文件，`diff_scope_valid=true`，观察到 9 个模型响应，成本未记录。workspace 外隐藏测试验证 `/memories/` 进入 routed Backend、`/memories-old/` 留在 default Backend。完整说明见 `docs/composite-route-migration-v1.md`，离线摘要见 `evals/reports/composite-route-migration-v1.json`，真实摘要见 `evals/reports/composite-route-migration-real-v1.json`。

## 18. 下一个阶段建议

按以下顺序进入正式评测：

1. 为 formal manifest 实现统一离线 runner，先覆盖路径、任务状态和产物保存；
2. 先跑本地 Harness 回归，确认 Baseline、Policy、Recovery、Checkpoint 的结果不会混组；
3. 设计成本、延迟、工具调用次数和人工介入率字段；
4. 只在需要真实模型指标时运行 DeepSeek；少于 10 次调用的批次按当前授权规则直接执行，10 次及以上先询问；
5. 分别生成 train 和 holdout 报告，不提前做 Harness 自动优化；
6. 复盘失败样本后，再决定是否增加多包依赖或并发恢复实验。

当前不要把 holdout 用于 Prompt 或 Policy 调参，也不要把离线 Harness 通过率写成真实模型成功率。

## 19. 当前 FilesystemMiddleware 权限迁移实验

已新增真实 SDK 模块权限迁移实验：从 `D:\langgraph_learning\deepagent\libs\deepagents\deepagents\middleware\filesystem.py` 复制源码到隔离 workspace，注入 `_permission_error()` 的直接权限检查缺陷，隐藏测试位于 workspace 外，允许修改的文件只有 `filesystem.py`。

离线运行 ID：`20261110T061159Z-2a38231f`。首次隐藏测试为 `2 failed, 1 passed`，Fake Model 恢复后为 `3 passed`；只修改 `filesystem.py`，无越界文件，`completed=true`、`tests_passed=true`、`diff_scope_valid=true`、`task_success=true`。完整说明见 `docs/filesystem-permission-migration-v1.md`，摘要见 `evals/reports/filesystem-permission-migration-v1.json`。

真实 DeepSeek 评测已完成一次，运行 ID：`20261111T060031Z-dc32d18f`。首次隐藏测试为 `2 failed, 1 passed`，Agent 先探索并运行测试，再通过 `grep/read_file` 定位权限判断，第二次测试为 `3 passed`；只修改 `filesystem.py`，无越界文件，`completed=true`、`tests_passed=true`、`diff_scope_valid=true`、`task_success=true`。观察到 10 个模型响应和 11 个 Policy 记录的工具调用，Provider 未返回 usage，因此成本不可用。完整说明见 `docs/filesystem-permission-migration-v1.md`，真实摘要见 `evals/reports/filesystem-permission-migration-real-v1.json`。该结果只作为一个真实 SDK 迁移样本，不并入普通 Recovery 成功率。

## 20. 正式评测 split 审计

已完成正式任务集的统一 runner 审计。train 共 16 个任务，其中 14 个模型任务、2 个离线 Runtime 任务；holdout 共 14 个任务，其中 8 个模型任务、6 个离线 Security 任务。离线结果分别为 train `2/2`、holdout `6/6`，模型调用均为 `0`。这证明 split、execution mode 和离线 target 边界一致，不代表模型任务成功率。说明见 `docs/formal-split-audit-v1.md`，产物见 `evals/reports/formal-split-audit-v1.json` 及四个 split 计划/执行报告。

四项真实 train Recovery 重复评测随后已在明确授权下完成，详见下一节。不要再因旧的待授权记录重复运行。

## 21. train Recovery 重复批次 v1

四次运行：CSV `20261111T131603Z-97e74293`、稳定去重 `20261111T131631Z-1397a50f`、安全除法 `20261111T131706Z-64557ad5`、时长解析 `20261111T131739Z-7bc2a503`。均使用 formal runner，首次隐藏测试失败、第二次 `2 passed`，只修改各自允许实现文件，事后范围审计和恢复判定均为成功。

关键观察：4 次均试图在首次测试前修改文件，均被 baseline gate 拒绝。每次 6 次工具尝试，5 次允许、1 次拒绝；平均 runner 耗时 16.174s；没有自动 Recovery 重试。拒绝的尝试未执行，不等于已发生越界修改，也不能声称模型主动先测后改。

报告：`evals/reports/formal-train-recovery-repeat-v1.json` 保存完整测试输出、diff、事件和派生判定；复盘：`docs/train-recovery-repeat-v1.md`。四份 `formal-repeat-real-recovery-*-v1.json` 保留原 runner 摘要。报告与复盘已提交为 `77e78b2`；原始 `run.json` 保留在本地 runs 中。

计量限制：`model_calls_requested=1` 是一次 Agent 任务调用，不是实际 provider 请求数；实际请求、token 和成本没有被 runner 采集。时长解析 diff 为 1507 字符，添加的秒单位、类型检查等行为未被两条隐藏断言覆盖。一次新增重复不足以证明稳定性，也没有配对对照可以估计成功率提升。

下一步优先补实际 usage 和自动范围判定，再跑有明确新增验证目标的模型任务。原正式矩阵不自动重算；本轮没有运行 holdout。现有 holdout 含历史上已检查和运行的 fixture，不能称为完全未见测试集。

## 22. 模型 usage 与自动范围判定 v1（2026-11-12）

已完成 `harness/usage.py`、`harness/file_scope.py`，接入 Baseline、real Recovery 和 formal runner。新的 `run.v1` 可增加 `model_usage` 和 `file_changes`；formal 摘要自动输出 changed/unexpected files、`diff_scope_valid` 与 `task_success`。空文件和二进制修改也纳入哈希比较。公开函数签名没有变化，旧报告不补填。

usage 使用 LangChain 模型回调，优先标准 `usage_metadata`，回退 provider token metadata，不重复叠加；后续模型异常仍保留此前观察值。`model_invocations` 是回调调用数，不是底层 HTTP 重试数。完整/部分/缺失数据分别标记，金额没有价格依据仍为 null。

用户设计判断：未授权空文件不算成功（正确）；只有部分响应 usage 却想报完整 token（已纠正：应标 partial，只报观察小计）。复盘文档为 `docs/usage-and-scope-v1.md`，完整离线回归 `92 passed in 96.04s`，本轮没有真实模型运行。单次未来的真实冒烟只为验证 provider usage 链路，不重复原四项实验，也不回填历史成本。

代码、测试和文档随本次里程碑提交；离线证据见 `evals/reports/usage-and-scope-offline-v1.json`。本次没有执行推送，不能把本地提交说成 GitHub 已同步。下一阶段可用一个 train 任务验证真实 usage 链路；价格表、真实 token 和底层请求计数仍不应声称已经验证。

## 23. 真实 usage 冒烟（2026-11-13）

一次 DeepSeek `real-recovery-csv-row` 任务已完成，运行 ID `20261113T051810Z-3e4b0c24`。首次隐藏测试 2 项失败，最终 2 项通过；仅修改 `row.py`，`diff_scope_valid=true`、`task_success=true`。Agent 首次尝试编辑被基线测试 Policy 拒绝，随后测试并修复；事件记录 `recovery_retries=0`，不能宣称中间件自动重试。

回调观察到 8 次调用和 8 次响应，全部带有效 usage：输入 28529、输出 748、总计 29277 tokens，状态为 `complete`。摘要与原始记录一致；底层 HTTP 次数和金额未知。详见 `docs/usage-smoke-csv-row-v1.md` 和 `evals/reports/formal-usage-smoke-csv-row-v1.json`；原始 `runs/` 被忽略，不要重跑以补证据。本次是单个 train 冒烟，不代表整体成功率。

## 24. 缓存用量与费用估算离线实验（2026-11-13）

新增缓存命中/未命中采集和显式价格区间估算，详见 `docs/cache-pricing-offline-v1.md`。用户提供的价格文本保存在 `evals/reports/deepseek-flash-price-reference-20261113.json`；后来核对了官方页面当前费率，但未核实历史有效期，不可自动作为可执行价格区间。使用完整缓存明细、匹配模型和覆盖整个运行的显式价格区间才能估算；估算与实际账单分开，跨时段和缺失明细不输出完整金额。完整离线回归 `98 passed`。

该离线阶段没有调用真实模型；之后完成的一次真实验证见第 25 节。更早的 CSV 冒烟未记录缓存明细，不能回填。

## 25. 真实缓存用量冒烟（2026-11-13）

真实 DeepSeek CSV 运行 `20261113T053833Z-4577c333`：6 次模型响应均采集到缓存明细，输入 22269，其中命中 20480、未命中 1789；输出 563，总计 22832 tokens。首次隐藏测试 2 项失败、最终 2 项通过，仅修改允许的 `row.py`，任务成功；先测试再修改，Policy 拒绝和 Recovery 自动重试均为 0。证据见 `docs/cache-usage-real-smoke-v1.md` 和 `evals/reports/formal-cache-smoke-csv-row-v1.json`。

已查阅英中官方价格页，中文账户页面显示人民币。按本次空闲时段及当前中文页面价格，条件估算为 0.0044506 元；页面未注明历史有效期。平台用量刷新前后增量 6 次请求和 22832 tokens，与本次记录一致；金额按分显示且为当日聚合，不能核对单次精确扣费。原 CSV 冒烟没有缓存明细，不得回填。

## 26. 下一个对话的开场提示

可以直接把下面这句话发给下一个对话：

> 请先阅读 docs/next-session-handoff.md。我们在 D:/langgraph_learning/agent-harness-lab 上做 Agent Harness 学习实验。当前已推送 Checkpoint v1/v2、run.v1 产物 schema、架构源码笔记和 30 任务 train/holdout manifest。下一步先说明实验目的、失败模式、控制变量、成功标准和资源使用；少于 10 次真实模型调用按当前授权规则执行，10 次及以上先询问。
