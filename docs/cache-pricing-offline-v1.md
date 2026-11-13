# 缓存用量与费用估算 v1

## 目的与实验边界

真实 CSV 冒烟采集到了 token 总量，但未保存缓存命中明细；用户提供的 DeepSeek 价格表显示命中与未命中价格不同。本轮研究两类失败：缺失明细被误算为零，以及错误模型、价格时段或历史价格被自动套用。

本轮使用 Fake Model 和手工构造的回调数据，不调用 DeepSeek、不使用 API 额度。合成数字和合成费用只验证实现，不是实际账单。原有 CSV 任务和历史报告保持不变。

## 标准答案与采集

输入总量为 1000，其中明确记录命中 600、未命中 400，才可按这两部分分别估价；只有总量或只有命中数时，本实现不猜测另一部分。多个响应有任何一轮缺失明细，状态是 `partial` 或 `unavailable`，不能计算完整任务费用。

`ModelUsageRecorder` 在每轮 `LLMResult.llm_output.token_usage` 或消息的 `response_metadata.token_usage` 中寻找 DeepSeek 风格的 `prompt_cache_hit_tokens` 和 `prompt_cache_miss_tokens`。两数必须都是非负整数、相加等于该轮输入总量，并与所用 usage 总数一致。如果多份有效原始明细或标准 `cache_read` 相互冲突，则舍弃该轮缓存明细。没有保存原始提示词或密钥。

`cache_usage_status` 及 `responses_with_cache_usage` 独立于总 token 的完整性；`observed_cache_tokens` 是已观察响应的小计，未观察到时为 null。即使 `token_usage_status=complete`，缓存明细仍可能不完整。当前只接受明确的命中和未命中两个字段；标准 `cache_read` 单独存在时不反推未命中。是否能在真实 DeepSeek 响应中取到字段仍需单独验证。

## 估算与价格来源

`harness/pricing.py` 使用 Decimal 按价格配置声明的币种（例如 USD 或 CNY）计算估算；正式 runner 的 `cost_estimate.amount/currency` 与实际账单字段 `cost` 分开。只有完整的总量和缓存明细、匹配的模型、有效币种以及覆盖整个运行的显式价格区间同时存在，才返回 `estimated`。实际扣费仍为未知，`cost` 保持 null。时间、模型、缓存明细或价格不满足要求时返回原因，不计算确定金额。

用户提供的价格文本保存在 `evals/reports/deepseek-flash-price-reference-20261113.json`；随后已查阅官方页面核对当时显示的价格，但页面未注明历史生效时间。它不能直接作为 `--pricing` 文件使用，不自动应用于过去或未来的运行。高峰、非高峰、中国公共假日和历史价格变更需要由价格配置提供者先核实；本实现不自动判断节假日或拆分跨时段运行。区间含开始时间、不含结束时间；运行结束恰好落在区间边界也会拒绝估算。

要选择一个经核实且覆盖整个运行的单价区间，`--run-model TASK --pricing PATH` 可以显式传入 JSON，格式如下。以下数值和时间仅是离线格式示例，不证明某个真实时段的价格：

```json
{
  "id": "example-only",
  "source": "offline-example",
  "model": "example-model",
  "currency": "USD",
  "valid_from": "2026-11-13T05:00:00+00:00",
  "valid_until": "2026-11-13T06:00:00+00:00",
  "hit_per_million": "0.003",
  "miss_per_million": "0.15",
  "output_per_million": "0.6"
}
```

模型名称要求精确匹配，价格以十进制字符串提供，时间必须含时区。区间是否真实适用由配置提供者负责核实；估算不会验证供应商账单、网络重试、其他服务或折扣。

## 验证和学习要点

完整离线回归 `98 passed`；包括真实 `ChatOpenAI` 响应转换的离线构造、缓存明细缺失及冲突、美元/人民币估算、价格范围和模型匹配、正式 runner 区分估算与账单。未做真实模型调用。

用量采集、价格选择和费用核对是三步：先观察数据，再选择有证据的价格，最后与账单对账。`complete` 是关于已记录数据的完整性声明，不代表供应商账单完整。Agent 任务的一次执行也可能产生多次模型请求，不能用一次任务的价格代替实际 token 计算。

2026-11-13 的 CSV 冒烟只保留总 token，没有缓存明细；它的精确估算仍不可用。此前根据用户提供费率给出的区间只是以价格历史适用为前提的条件推算，不是历史账单。

后续一次真实缓存字段冒烟已完成，结果及账单精度限制见 `docs/cache-usage-real-smoke-v1.md`。
