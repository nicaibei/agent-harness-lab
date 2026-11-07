# 配置文件异常 Recovery v1

## 实验目的

本实验把错误限制在仓库配置文件：`config/checkout.json` 中的 `tax_rate` 被写成 `20`，而系统约定它是小数税率，正确值应为 `0.2`。Python 模块已经正确，因此可以观察 Agent 是否能根据测试输出定位配置，而不是盲目修改业务代码。

## 实验控制

- 项目结构：保留 `config/`、`inventory_app/` 和项目元数据，模拟仓库形态任务。
- 隐藏测试：继续放在 workspace 外，Agent 只能通过 `run_tests` 获得结果。
- 基线测试门：开启。文件修改前必须先运行一次测试。
- 测试预算：最多两次隐藏测试，分别用于首次失败和最终验证。
- 离线阶段：不调用 DeepSeek，不消耗额度。
- 服务器：不需要租服务器。

## 离线结果

初始配置让设置层、服务层测试失败，目录层测试保持通过；只把 `tax_rate` 改回 `0.2` 后，三层隐藏测试全部通过。这个结果证明 fixture 确实只把配置数值作为待修复变量，实验设计没有混入 Python 逻辑故障。

## 成功标准

真实运行必须同时满足：首次测试失败、diff 修改 `config/checkout.json`、三个 Python 模块没有无关修改、第二次测试通过，并且 `run.json` 中 `completed=true`、`tests_passed=true`、`execution_error=null`。

## 真实运行结果

运行目录：[20261107T095602Z-fe966317](../runs/recovery/20261107T095602Z-fe966317/)

- 首次隐藏测试：`2 failed, 1 passed`；失败原因是配置返回 `20.0`，服务总额变成 `420.0`。
- DeepSeek 只修改了 `config/checkout.json`，把 `tax_rate` 从 `20` 改为 `0.2`。
- `inventory_app/settings.py`、`catalog.py` 和 `checkout.py` 均没有进入 diff。
- 第二次隐藏测试：`3 passed`。
- 运行结果：`completed=true`、`tests_passed=true`、`execution_error=null`。

补丁证据：[diff.patch](../runs/recovery/20261107T095602Z-fe966317/diff.patch)，结构化日志：[run.json](../runs/recovery/20261107T095602Z-fe966317/run.json)。

## 重复运行结果

同一任务又运行了两次，模型、fixture、基线门和测试预算都没有改变。三次运行合并结果为：

- `3/3` 首次测试失败后最终通过；
- `3/3` 只修改 `config/checkout.json`；
- 三次 diff 都是 `136` 个字符，内容相同；
- 三次都没有修改 Python 模块或隐藏测试。

重复运行报告：[repeat-real-recovery-inventory-config.md](../evals/reports/repeat-real-recovery-inventory-config.md)。这说明该受控任务目前表现稳定，但三次样本仍然太少，不能推断其他配置格式或大型仓库的稳定性。

## 证据边界

这次真实运行和两次重复证明 DeepSeek 在这个受控配置异常中都完成了基线测试、定位配置并通过最终测试；它们不能代表不同配置格式、复杂依赖或大型真实仓库中的总体配置修复率。正式 Recovery 汇总现在包含 21 次运行，其中 17 次属于失败后恢复。
