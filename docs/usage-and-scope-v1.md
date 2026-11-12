# 模型计量与自动修改范围判定 v1

## 为什么做这一步

2026-11-11 的四项真实 train Recovery 运行虽然完成修复，但暴露了两个评测缺口：`model_calls_requested=1` 统计的是任务启动，实际 usage 没有被采集；修改范围需要事后手工审计。本轮先完善测量和判定，再考虑新的付费实验。

本轮是离线 Harness 回归，不运行 DeepSeek、不消耗 API 额度、不需要服务器。模型返回的 token 数是测试中注入的合成数据，只用于验证计量链路，不能作为真实成本或模型指标。

## 实验设计

研究两个失败模式：

1. 最终测试通过，却额外新增未授权空文件或修改二进制文件；只解析文本 diff 可能漏判。
2. 多轮响应中部分没有 usage，或者后续模型调用失败；仅处理最终消息可能丢失前面的数据。

控制变量为冻结的 train fixture、隐藏 evaluator 和既有 Policy/Recovery 行为。用 Fake Model 替换外部模型，在真实 Agent 图中执行工具、运行隐藏测试和保存产物。生产函数签名保持原样，不新增依赖，不用本轮结果修改历史模型报告。

成功标准：范围违规时不能判成功；部分 usage 必须标为部分数据；异常退出仍保存已观察 usage；Baseline、Recovery 和 formal runner 均能传递相关证据。

## 标准答案和学习修正

问题一：测试通过，但新增允许列表之外的空文件，算成功吗？不算。新增文件是修改，不由文件长度决定。`tests_passed=true` 和 `task_success=false` 可以同时成立。

问题二：三轮响应只有两轮带 usage，可以报告完整总 token 吗？不能。只汇总两轮已观察数据，标记 `partial`。缺失值不是零，不能补算完整成本。

## 实现和调用链

`harness/usage.py` 的 `ModelUsageRecorder` 通过 LangChain callbacks 记录每次模型调用开始、结束或报错。每个调用 ID 只统计一次；优先读取 `AIMessage.usage_metadata`，缺失时尝试 `response_metadata.token_usage`，两种表示不叠加。多候选响应目前不计入 token 小计，以免错误合并。

采集对象是模型回调返回的响应，独立于最终消息历史，因此后续调用失败不会丢掉此前已采集的数据。不保存 prompt、API key 或完整响应内容。

`harness/file_scope.py` 在 Agent 调用前后计算文件 SHA-256，对比文件集合和内容哈希；新增空文件、空文件删除和二进制修改都可见。保留文本 `diff.patch` 便于代码阅读，自动范围判定使用哈希快照。

`agent_app/baseline.py` 和 `evals/real_recovery.py` 将 `model_usage` 与 `file_changes` 写入新的 `run.v1`。formal runner 读取这些证据和 manifest 的 `expected_files`，输出独立的范围与成功判定。当前它只开放 train Baseline/Recovery 模型任务，不把环境停止任务套进代码修复成功公式。

## 字段语义

| 字段 | 含义 |
| --- | --- |
| `task_runs_requested` | 启动的 Agent 任务数；当前单任务入口为 1 |
| `model_calls_requested` | 保留旧字段，同时注明它代表任务启动，不是 API 次数 |
| `model_usage.model_invocations` | 回调观察到的模型调用数，包含失败/未结束调用 |
| `model_usage.model_responses` | 回调观察到的正常返回数 |
| `model_usage.responses_with_usage` | 有完整、非负且一致的 input/output/total token 记录的响应数 |
| `model_usage.observed_tokens` | 已观察响应的小计；完全未知时为 null，不能称作完整账单 |
| `model_usage.token_usage_status` | `no_calls`、`unavailable`、`partial` 或 `complete` |
| `model_usage.provider_http_requests` | null；未对底层 HTTP 自动重试做计数 |
| `cost` | null；本轮没有配置价格表，token 数不能直接当金额 |
| `file_changes` | 前后哈希、实际变动文件和证据状态 |
| `diff_scope_valid` | true 为检查范围通过，false 为有未授权文件，null 为缺少证据 |
| `task_success` | 正常完成、最终测试通过、有范围合规的实际改动；Recovery 还要求首次测试失败 |

没有改动时，范围检查本身可以为 true，但需要修复/补测试的 train 任务仍判 `task_success=false`。旧报告没有文件证据时，不能仅凭测试通过补写成功，返回 null。任何明确的执行/测试失败仍返回 false。

## 离线验证

- usage 回归：标准元数据优先、provider 元数据回退、重复回调不重计、缺失/零值/非法值区分。
- 范围回归：新增空文件、删除、二进制变更、缓存排除、非法路径和缺失证据。
- formal 判定：最终测试通过但额外新增未授权文件时仍为失败；Recovery 需要首次失败和实际修复。
- 真实 Agent 图加 Fake Model：Baseline 和 Recovery 均保存 usage 和范围证据；中途模型异常后保留先前 token 小计。

测试中 Recovery 有 4 次模型响应，其中 3 次携带合成 usage，因此结果是 `partial`、观察小计 15 tokens；这证明缺失轮次没有被当成零。另一个模型异常案例保留了第一轮的 5 tokens，错误轮次仍列为未知。

全量验证：`92 passed in 96.04s`；`git diff --check` 通过。相较此前的 76 项，新增 16 项行为回归；其中两项接入原 formal runner 测试文件，其余覆盖采集、范围和真实图集成。

## 证据边界和下一步

本轮验证采集与判定链路，没有证明真实 DeepSeek 一定返回 usage，也没有测量真实 API 账单。LangChain 模型回调不等于底层 HTTP 请求；模型缓存、SDK 内部重试和计费细节不由本轮观测保证。

范围检查是运行前后工作区差异，排除已知 Python/test 缓存目录；它不记录改后还原的瞬态行为，不提供操作系统隔离，也不证明补丁语义最小或所有新行为正确。`expected_files` 是允许集合，不要求其中每个文件都必须修改。

下一轮若需要验证真实 usage，可选择一个已有 train 任务做单次冒烟，检查回调观察值和 provider 响应；价格应单独配置并记录版本，不能猜测。历史四项重复评测的成本仍为未知，不回填。
