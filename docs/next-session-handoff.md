# Agent Harness Lab 对话交接文档

本文档用于把当前对话的实验状态交给下一个对话。下一个对话应先阅读本文档，再继续实验，避免重复运行已经完成的模型任务或误判 GitHub 状态。

## 1. 项目身份

- 本地仓库：`D:\langgraph_learning\agent-harness-lab`
- GitHub 仓库：`https://github.com/nicaibei/agent-harness-lab.git`
- 当前分支：`main`
- 最近功能里程碑提交：`2b4b0b3 feat(evals): add configuration recovery experiment`
- `origin/main` 仍在：`bd7e9d1 feat(evals): add repository-shaped recovery fixture`
- 交接文档会作为紧随其后的本地 docs 提交；两个本地提交都尚未推送成功。

最近两次 `git push origin main` 都因连接 GitHub 的网络错误失败：一次是 connection reset，一次是无法连接 `github.com:443`。这不是提交失败，也不是 API Key 或 GitHub 权限错误。下一次网络正常时，先执行：

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
4. 每次新的真实 DeepSeek 调用都要先明确用途并请求用户授权；已有一次授权不自动覆盖后续新的调用。
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

## 13. 下一个阶段建议

下一步独立实验建议做“允许离线安装依赖”或“版本冲突 Recovery v1”，不要把它和本次环境停止实验合并。应按以下顺序：

1. 先说明这个实验要区分业务逻辑错误、包启动错误和依赖/环境错误；
2. 设计一个提供本地 wheel 或受控版本集合的离线 fixture；
3. 明确依赖安装是否属于 Agent 能力，还是 Harness 的环境准备能力；
4. 先验证离线安装、错误分类和安全边界；
5. 解释离线结果后，再单独请求一次 DeepSeek 真实运行授权；
6. 真实运行后读取 `run.json` 和 `diff.patch`，检查是否发生了正确的恢复；
7. 必要时重复运行，最后更新矩阵和文档；
8. 完成复盘后再提醒是否适合下一次 GitHub 提交。

当前不要把第三方依赖错误与配置错误或包导入错误混在同一个 fixture 中，否则无法判断模型修复了哪一类失败。

## 14. 下一个对话的开场提示

可以直接把下面这句话发给下一个对话：

> 请先阅读 docs/next-session-handoff.md。我们在 D:/langgraph_learning/agent-harness-lab 上做 Agent Harness 学习实验。先检查本地提交和未提交的实验改动，复盘启动 Recovery 和第三方依赖环境停止实验，再解释下一步允许离线安装依赖或版本冲突 Recovery v1 的目的、失败模式、控制变量、成功标准和是否需要服务器；新的真实模型调用必须先请求单独授权。
