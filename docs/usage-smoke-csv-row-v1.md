# 真实 usage 冒烟：CSV Recovery v1

## 目的与设计

2026-11-13 运行一次已存在的 train 任务 `real-recovery-csv-row`，检验真实 DeepSeek 响应能否通过 LangChain callback 被 `ModelUsageRecorder` 记录，并核对正式 runner 的文件范围和任务成功判定。它不是新增模型能力评测，也不是成功率估计。

固定 CSV fixture、隐藏测试、Policy 和 Recovery 配置。任务缺陷是把 `name, score` 的字段顺序赋反，且未清理空格。成功需要首次隐藏测试失败、Agent 正常结束、最终隐藏测试通过、有实际修改且只修改允许的 `row.py`。usage 是否完整单独判断。

## 实际过程

运行 ID：`20261113T051810Z-3e4b0c24`。Agent 读取源码后，先尝试 `edit_file`，被要求先运行基线测试的 Policy 拒绝；随后首次隐藏测试 2 项失败。Agent 调整字段赋值顺序并对两个字段执行 `strip()`，第二次隐藏测试 2 项通过。前后文件快照显示只修改 `row.py`，没有未授权文件；正式 runner 判定 `task_success=true`。

此前 `ls /workspace` 也曾报路径不存在。Recovery 事件记录了该工具错误、策略拒绝及测试失败，但本次 `recovery_retries=0`：Agent 根据工具反馈自行继续，不能把这次成功解释成中间件自动重试的效果。Policy 拦截的是一次修改前的尝试，不等于文件已经越界修改。

## 计量结果

正式摘要与原始 `run.json` 的 `model_usage` 一致：1 次 Agent 任务，回调观察到 8 次模型调用、8 次正常响应、0 次模型错误；8 个响应均包含有效 `usage_metadata`，因此标记 `complete`。观察到的输入、输出和总 token 分别为 28,529、748 和 29,277。正式 runner 记录耗时 30.038 秒。

`complete` 只表示本次已观察的响应均有完整 usage，不表示已核对供应商账单；LangChain 回调数不等于底层 HTTP 请求数，也不覆盖 SDK 内部重试。未配置价格表，金额仍为未知，不能按 token 猜测或填零。旧运行没有 usage，不回填数据。

## 证据与局限

- 可提交摘要：`evals/reports/formal-usage-smoke-csv-row-v1.json`。
- 本地原始产物：`runs/recovery/20261113T051810Z-3e4b0c24/`，该目录被 Git 忽略。
- 原始 `run.json` SHA-256：`41bd8c74e35920fe9c52d48219f07fae467bfc0c7615be1ad351a300f138dde6`。
- 原始 `diff.patch` SHA-256：`e1993cd1acb74335a0f255fd4352fb04f2e0f72533d264db98c4983ca19fe835`。
- 范围检查是运行前后文件快照，不记录修改后恢复的瞬态行为，也不提供操作系统隔离。
- 只有一个简单 train fixture 的真实样本，不能证明其他任务都能完整采集 usage，也不能外推成功率、稳定性或复杂仓库效果。

## 学习要点

Agent 任务、模型响应和底层 HTTP 请求是不同层级。每次模型继续处理工具结果时可能再次接收此前上下文，所以一次任务的输入 token 可以远大于源码本身。只有所有观察到的响应都有合法 usage 时，才能把这些响应的汇总标为完整；部分响应缺失时只能报告观察小计。

测试反馈解释了故障：原实现尝试把 `Alice` 转成整数，表明字段被赋反；第二个用例还要求去除空格。Policy 则在 Agent 写入之前强制获得基线测试结果，使失败前后的比较有依据。测试通过和修改范围合规需要同时成立，才能满足本任务成功标准。
