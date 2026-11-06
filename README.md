# Agent Harness Lab

面向 Agent 开发工程师和 Agent Harness 工程师的长期实践项目。

本项目以 Deep Agents 为参考，逐步实现一个面向真实代码仓库的 Issue-to-PR Agent Harness：

~~~text
Issue
  -> 读取代码
  -> 制定任务计划
  -> 修改文件
  -> 运行测试
  -> 分析失败并恢复
  -> 输出 diff、日志和评测结果
~~~

## 当前进度

- [x] Backend CRUD、路径映射和 CompositeBackend 路由实验
- [x] 最小 Issue-to-PR Baseline（10 个任务已完成）
- [x] Policy Middleware v1/v2
- [x] Recovery Middleware v1
- [x] Checkpoint/Replay v1（内存 checkpoint、工具边界恢复、事件 replay）
- [x] 离线评测与失败分类 v1
- [x] 故障注入与 Recovery 纠错评测 v1
- [ ] 任务评测集和对比实验

## 目录结构

~~~text
agent-harness-lab/
├── agent_app/   # Agent 应用入口和任务编排
├── harness/     # Context、Policy、Recovery、Replay 等 Harness 能力
├── evals/       # 任务集、运行器和评测报告
├── tests/       # 单元测试和集成测试
├── docs/        # 架构笔记、实验记录和设计决策
└── pyproject.toml
~~~

## 学习原则

每个新能力都要回答三个问题：

1. 它解决了哪一种 Agent 失败模式？
2. 如何用实验或测试证明它有效？
3. 为什么它应该属于 Harness 层，而不是普通 Tool 层？

完整的阶段复盘和学习过程记录见 [docs/learning-process.md](docs/learning-process.md)。

可以用下面的命令从已有 `runs/` 产物生成评测汇总：

~~~powershell
python -m evals.report --runs-dir runs --output-dir evals/reports
~~~

## 当前实验

Backend 实验位于：

- docs/backend_experiment.py
- docs/backend-experiment-report.md

该实验不依赖模型或 API Key，验证 StateBackend、FilesystemBackend 和 CompositeBackend 的存储、路径和路由行为。

## 运行最小 Baseline

Baseline 通过 DeepSeek 的 OpenAI 兼容接口调用模型。先在 DeepSeek 控制台创建 API Key，并确认账号可以使用要配置的模型。准备 Python 3.11+ 和 uv 后，在仓库根目录运行：

~~~powershell
uv sync --all-groups
Copy-Item .env.example .env
~~~

首次运行前编辑仓库根目录的 .env，填入你自己的 DeepSeek API Key 和模型 ID：

~~~dotenv
DEEPSEEK_API_KEY=your-deepseek-api-key
DEEPSEEK_MODEL=deepseek-flash
DEEPSEEK_BASE_URL=https://api.deepseek.com
~~~

之后每次只需运行：

~~~powershell
uv run agent-harness --task-id calculator-add-floats
~~~

默认 Base URL 使用 DeepSeek 官方 OpenAI 兼容接口。如果你的账号使用代理或兼容网关，请将 DEEPSEEK_BASE_URL 设置为对应地址。DEEPSEEK_MODEL 必须填写该账号可用的模型 ID。

本地 .env 已加入 .gitignore，不会被 Git 跟踪。不要把真实 API Key 写进 .env.example 或提交到仓库。

Agent 会把 toy 项目复制到 runs/<run-id>/workspace/，在副本中工作。它只能使用 Deep Agents 文件工具和固定的 pytest 工具，不接收任意 shell 命令。每次运行生成 diff.patch 和 run.json。

Baseline 运行现在接入了 Policy 和 Recovery Middleware：工具调用必须通过 allowlist，文件路径拒绝路径穿越和敏感文件，删除与未知工具默认拒绝，单次运行最多允许 30 次工具调用；暂时性工具错误会有限重试，参数错误和测试失败会交回 Agent，重复调用会被阻断。策略和恢复事件都会写入 `run.json.events`。这些机制属于工具调用级保护和恢复控制，不等同于操作系统沙箱。

默认任务项目位于 examples/tiny_python_project/。10 条可重复任务定义在 evals/tasks.json。本机无 API Key 时仍可运行离线测试：

~~~powershell
uv run pytest
~~~
