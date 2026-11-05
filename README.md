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
- [ ] 最小 Issue-to-PR Baseline
- [ ] Policy Middleware
- [ ] Recovery Middleware
- [ ] Checkpoint 和 Replay
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

## 当前实验

Backend 实验位于：

- docs/backend_experiment.py
- docs/backend-experiment-report.md

该实验不依赖模型或 API Key，验证 StateBackend、FilesystemBackend 和 CompositeBackend 的存储、路径和路由行为。
