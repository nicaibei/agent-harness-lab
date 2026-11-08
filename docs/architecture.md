# Deep Agents 架构标准答案

这份笔记用于建立整体心智模型，也可以作为面试时的口头答案。理解 Deep Agents 时，先分清运行时、Agent 抽象和 Harness 三层，再追踪一次请求如何从组装走到执行。

## 一分钟标准答案

> Deep Agents 是构建在 LangChain Agent 抽象和 LangGraph 运行时之上的 Harness。LangGraph 负责图执行、状态、checkpoint、streaming 和 interrupt；LangChain 的 create_agent 负责模型与工具之间的 Agent 循环；Deep Agents 的 create_deep_agent 则组装一套偏向长任务的默认能力，例如 middleware、文件工具和 backend、subagent、skills、memory 及模型 profile。
>
> Middleware 参与模型调用或工具调用的生命周期，可以调整模型请求、工具集合和状态，也可以把工具接入 Agent；工具本身是模型选中后才执行的具体能力。文件工具通过统一的 BackendProtocol 访问不同存储实现。运行时把模型回复和工具结果写回状态并继续循环，直到 Agent 返回最终答案或被 interrupt。Checkpoint 保存某个线程的图状态；Backend 决定文件或记忆内容放在哪里，两者是相关但不同的持久化机制。

## 三层架构

~~~text
Deep Agents
  Harness：默认 middleware、subagent、backend、skills、memory、profiles
  └─ 使用 LangChain Agent 抽象
       └─ LangGraph Runtime：图执行、state、checkpoint、streaming、interrupt
~~~

| 层 | 主要职责 | 在仓库中的入口 |
|---|---|---|
| LangGraph | 执行有状态图；提供 checkpoint、streaming、interrupt 等运行时能力 | Deep Agents 将 checkpointer、store 等传给图构造流程 |
| LangChain Agent | 管理模型与工具之间的循环：准备模型请求、执行被选中的工具、把结果交还模型 | langchain.agents.create_agent |
| Deep Agents | 提供带有明确默认配置的 Agent Harness；组织 middleware、backend、subagent 等 | deepagents.graph.create_deep_agent |

重点：Deep Agents 不是另造一个与 LangGraph 平行的运行时。它在 LangChain Agent 和 LangGraph 提供的能力之上增加一套可配置的 Harness。

## 构造阶段发生什么

应用调用 create_deep_agent 时，代码大致会：

1. 解析模型及适用的 harness profile。
2. 解析文件工具等能力使用的 backend。
3. 组装主 Agent 的 middleware。
4. 建立默认通用 subagent，并处理调用者提供的 subagent。
5. 合并系统提示、工具、状态 schema、上下文等配置。
6. 调用 LangChain 的 create_agent，传入 middleware、tools、checkpointer、store 等配置，得到可运行的 Agent graph。

因此，看到一个默认能力时，要问它是在 create_deep_agent 的哪一步接入的；看到执行或恢复能力时，再确认它由哪个运行时或后端负责。

## `create_deep_agent()` 实际组装链

基于当前 Deep Agents 源码 checkout，关键符号之间的调用关系是：

~~~text
create_deep_agent()
  -> resolve_model() / _harness_profile_for_model()
  -> 默认 backend：StateBackend()
  -> FilesystemMiddleware(backend, permissions)
  -> SubAgentMiddleware / AsyncSubAgentMiddleware（按 subagents 配置）
  -> SummarizationMiddleware + PatchToolCallsMiddleware
  -> SkillsMiddleware / MemoryMiddleware / HumanInTheLoopMiddleware（按参数）
  -> _apply_excluded_middleware() / _apply_custom_middleware()
  -> langchain.agents.create_agent(
       model, tools, middleware, state_schema, context_schema,
       checkpointer, store, debug, name, cache,
     )
~~~

这里的关键边界是：`create_deep_agent()` 负责组装和配置，`create_agent()` 负责把模型、工具和 middleware 交给 LangGraph 图运行时；它本身不实现某个文件 backend，也不负责把 checkpoint 内容序列化到具体数据库。

源码证据入口：`libs/deepagents/deepagents/graph.py` 的 `create_deep_agent()`、`deepagents/middleware/filesystem.py` 的 `FilesystemMiddleware._create_tools()` 与 `wrap_model_call()`、以及 `deepagents/backends/protocol.py` 的 `BackendProtocol` 和 `SandboxBackendProtocol`。

## 一次运行的执行链路

下面是概念链路；具体 hook 顺序由当前 middleware 组合和 LangChain Agent 实现决定。

~~~text
用户输入
  ↓
LangGraph 将输入交给 Agent graph，准备并传递状态
  ↓
Middleware 整理模型请求
（例如注入工具说明、调整工具集合、压缩上下文）
  ↓
模型返回文字，或请求调用工具
  ↓
若有工具调用：Agent 执行被选中的工具
  ├─ 普通工具：执行自己的业务逻辑
  └─ 内置文件工具：FilesystemMiddleware → BackendProtocol → 具体 backend
  ↓
工具结果作为消息或状态交回 Agent
  ↓
模型继续处理；循环到最终答复，或由 interrupt 暂停等待外部处理
  ↓
LangGraph 根据配置保存图状态或 checkpoint
~~~

工具与 middleware 的差别是关键：模型选择某个工具后，工具才执行；middleware 可以在模型调用前后、工具执行前后等阶段参与流程，也可以修改请求或状态。把策略检查、重试、预算控制这类跨工具或跨步骤的逻辑放在 Harness 层，通常比把所有逻辑塞进某一个工具更合适。

## Middleware、Tool、Backend 的职责边界

| 组件 | 回答的问题 | 例子 |
|---|---|---|
| Middleware | Agent 的生命周期中应如何处理请求、状态或工具调用？ | 让文件工具进入模型请求；在调用前执行权限判断；处理过长的上下文 |
| Tool | 模型选中后可以执行哪项具体操作？ | read_file、write_file、业务查询工具 |
| Backend | 这项文件或执行操作由哪个实现完成，数据存在哪里？ | state、LangGraph Store、本地文件系统、sandbox |

FilesystemMiddleware 同时提供文件工具、调用 backend，并处理与这些工具有关的权限及结果整理。它不是文件本身的存储介质。BackendProtocol 统一不同后端的文件操作契约；只有实现 SandboxBackendProtocol 的后端才提供 execute 能力。这个协议表示能力接口，本身不保证实现有安全隔离。

## 两种需要分开理解的持久化

| 数据 | 负责机制 | 典型范围 |
|---|---|---|
| 对话、Agent state、interrupt 或 checkpoint 信息 | LangGraph checkpointer | 通常按 thread 恢复；是否跨进程保存取决于所用 checkpointer |
| 文件、memory 或 artifacts | Deep Agents backend | 由具体 backend 决定；可在图 state、本地文件或 Store 中 |

StateBackend 将文件放进 Agent state，因此与图状态及 thread 生命周期关联；它不能简单等同于一个跨线程共享的文件库。StoreBackend 通过命名空间使用 LangGraph Store，适用于跨线程持久数据；命名空间如何按用户或应用隔离由调用者设计。Checkpoint 和 Store 或 backend 可以组合使用，但解决的问题不同。

## 从哪里读代码

- [libs/ARCHITECTURE.md](../libs/ARCHITECTURE.md)：仓库维护者写的整体架构地图。
- [graph.py](../libs/deepagents/deepagents/graph.py)：create_deep_agent 如何组装 graph。
- [filesystem middleware](../libs/deepagents/deepagents/middleware/filesystem.py)：文件工具如何被创建、过滤并连接到 backend。
- [backend protocol](../libs/deepagents/deepagents/backends/protocol.py)：后端契约、操作结果类型及命令执行能力协议。
- [backends](../libs/deepagents/deepagents/backends/)：具体存储、路由和 sandbox 实现。

## 面试自测

**问：Deep Agents、LangChain 和 LangGraph 分别负责什么？**
答：LangGraph 提供有状态图运行时；LangChain create_agent 组织模型与工具的 Agent 循环；Deep Agents 在其上组装面向长任务的 Harness 默认能力。

**问：为什么文件系统能力既需要 middleware 又需要 backend？**
答：middleware 把文件操作作为 Agent 可用工具接入，并处理工具请求中的提示、权限和结果；backend 提供这些操作的实际存储或执行实现。两者分离后，工具体验可以复用不同的存储后端。

**问：checkpointer 和 StoreBackend 有什么不同？**
答：checkpointer 保存图的线程状态以便恢复运行；StoreBackend 把文件数据放在 Store 的命名空间中，供不同线程或运行共享。前者保存运行状态，后者保存由 backend 管理的数据。

**问：把 filesystem 工具放进 middleware 是不是就安全了？**
答：不是。权限规则只约束相应的文件工具路径；能否安全执行命令取决于具体 backend。LocalShellBackend 在宿主机执行命令，没有沙箱隔离。安全边界要由真正隔离的执行环境、权限策略和必要的人工审批共同建立。
