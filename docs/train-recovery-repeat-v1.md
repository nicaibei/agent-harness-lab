# Train Recovery 重复批次 v1

## 目的和实验内容

为四个已有 train Recovery 任务各补一次真实 DeepSeek 运行，检查已知故障能否再次修复，并观察基线测试门在真实轨迹中的作用。沿用冻结 fixture，不新建故障，不调 Prompt、Policy 或 evaluator，不运行 holdout。本批次是 4 次 Agent 任务运行，不能等同为 4 次 provider API 请求。

故障分别是 CSV 字段顺序及空白处理错误、去重丢失原始顺序、除零异常未处理，以及时长单位换算不完整。预期流程是读取源码、执行外部隐藏测试、仅修复允许的实现文件、再次测试。

## 成功标准和控制变量

成功必须同时满足：Agent 正常结束、首次隐藏测试失败、最终隐藏测试通过、有效 diff 非空且只涉及 manifest 允许文件。隐藏测试位于 workspace 外，两个测试轮次由工具预算约束。四次运行使用相同 runner、模型名 `deepseek-flash` 和开启的 baseline gate，未在批次中改变配置；运行时源码基线是 `f1b39e6`。

没有冻结完整依赖版本或全部模型参数，源码与 evaluator 哈希是在事后核验时补录；因此不能宣称严格重现实验或与历史运行完全同配置。

## 结果

| 任务 | 首次隐藏测试 | 最终隐藏测试 | 实际修改 | runner 耗时 | 工具尝试 / 拒绝 |
| --- | --- | --- | --- | ---: | ---: |
| CSV 解析 | 2 failed | 2 passed | `row.py` | 16.079s | 6 / 1 |
| 稳定去重 | 1 failed, 1 passed | 2 passed | `unique.py` | 16.706s | 6 / 1 |
| 安全除法 | 1 failed, 1 passed | 2 passed | `safe_math.py` | 15.036s | 6 / 1 |
| 时长解析 | 1 failed, 1 passed | 2 passed | `duration.py` | 16.876s | 6 / 1 |

四项均满足本轮成功标准，均无预期文件集合外的改动。总计 24 次 Policy 工具决策，20 次允许、4 次拒绝；8 次隐藏测试，4 次首次失败和 4 次最终通过。平均任务耗时 16.174s，范围 15.036–16.876s；这不是模型请求的独立耗时，也不足以报告 P95。

## 实际轨迹与关键发现

四次运行的决策序列相同：

1. `ls` 和 `read_file` 探索实现。
2. 首次测试之前尝试 `edit_file` 或 `write_file`。
3. Policy 返回 `baseline test must run before file mutations`，拒绝该修改。
4. Agent 调用 `run_tests`，隐藏测试暴露原始故障。
5. Agent 再次修改允许的实现文件。
6. 第二次 `run_tests` 通过，Agent 结束。

所以本轮观察到的是 4 次违规流程尝试都被 gate 拦截，而非模型主动遵守先测后改。拒绝发生在 handler 执行前；后续允许的修复范围合规，不能把拒绝次数直接计作已执行越界修改。

Recovery 将拒绝分类为 `policy`，将失败的测试工具结果分类为 `tool_error`。`recovery_terminal` 表示当前工具结果不再做自动重试，Agent 图仍可继续下一轮决策；本轮自动重试数是 0。真正修改实现的是模型，Policy 负责限制执行顺序。

## 修改内容与测试边界

- CSV：恢复 name/score 字段顺序，并去除空白。
- 稳定去重：用 seen 集合和结果列表保留首次出现顺序。
- 安全除法：分母为 0 时返回 `None`。
- 时长解析：将仅处理首个 token 的实现改为遍历单位片段；同时添加秒单位、输入类型和非法输入处理等额外行为。

时长解析的 diff 为 1507 字符，明显大于另外三个任务。隐藏测试仅覆盖 `1h 30m` 和 `45m`，因此其通过只证明这两项断言成立，不能证明新增行为正确，也不能用 diff 更大来代表修复质量更高。本轮保留模型产物，不替模型修改答案，也不扩大隐藏测试后重算结果。

## 产物与计量限制

每次运行保留 `run.json`、`diff.patch`、`replay.json` 和 workspace。四份 `formal-repeat-real-recovery-*-v1.json` 保存 runner 摘要；[批次证据](../evals/reports/formal-train-recovery-repeat-v1.json) 进一步保存完整测试输出、diff、事件、范围判定和原始产物 SHA-256，方便查看被忽略的本地 runs 之外的证据。

`formal_runner` 的 `model_calls_requested=1` 只表示启动一次 Agent 任务。当前 runner 未采集实际模型请求次数和 token usage，不能断言 provider 没有返回这些信息；成本保持未知，不把未知写作 0。这里的 6 次工具尝试包括被 gate 拒绝的一次，不能称为 6 次成功执行。

本批次不覆盖原有 24 次 Recovery 矩阵，不混入两个 SDK 迁移实验，不宣称总体成功率提升，也不使用 holdout 进行调参。历史相同任务曾有成功记录，但缺少完整配置快照，因此只作为背景，不能直接合成同配置稳定性统计。

## 学到什么与下一步

这个实验展示了模型修复能力和 Harness 控制能力的区别：模型完成代码修改，Harness 强制保留修改前的失败证据。已观察到的 gate 拒绝也说明只看最终测试会漏掉重要的中间行为。

自测题：为什么四次都有 Policy 拒绝，最终仍可判定任务成功？标准答案：被拒绝的修改未执行；随后 Agent 运行测试，在允许文件中完成修复，最终隐藏测试通过。仍须单独记录违规尝试，不能称模型全程遵守了流程。

下一步先补齐实际模型请求/token 采集和自动 diff 范围判定，再选择有新验证目标的 train 任务。不为凑样本立即重复调用；holdout 的历史样本已被看过，未来应诚实区分历史验证集与真正未见的新测试集。
