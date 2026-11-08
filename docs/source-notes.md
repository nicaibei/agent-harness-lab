# Deep Agents 源码阅读标准答案

这份笔记把“看过几个文件”变成一条可重复的源码追踪路线。目标不是背实现细节，而是能从公开入口解释：能力在哪里组装、运行时如何调用、具体实现在哪里落地。

源码证据基于 `D:\langgraph_learning\deepagent` 当前 checkout，阅读对象是 `libs/deepagents`。仓库版本变化时，应重新核对下面的符号和 middleware 顺序；这里记录的是职责和调用边界，不把行号当成公共 API。

## 本次源码核对结果

| 结论 | 源码证据 | 对 Harness 设计的影响 |
|---|---|---|
| Agent 组装入口是 `create_deep_agent()` | `deepagents/graph.py`：解析 model/profile/backend，组装 middleware，最后调用 `create_agent()` | Policy、Recovery 和运行配置应作为 middleware 或 graph 参数接入 |
| 文件工具由 middleware 暴露 | `deepagents/middleware/filesystem.py`：`FilesystemMiddleware._create_tools()`、`wrap_model_call()` | 工具可见性、参数和权限在 middleware 边界控制 |
| 文件实际存储由 backend 决定 | `deepagents/backends/protocol.py`：`BackendProtocol` 的读写契约；State/Filesystem/Store 实现不同生命周期 | 不能把工具权限误认为 backend 或操作系统沙箱 |
| `execute` 是能力接口，不是安全保证 | `SandboxBackendProtocol` 与 `FilesystemMiddleware` 的 `supports_execution()` | 需要单独验证执行环境、命令策略和人工审批 |
| Checkpoint 与文件存储分离 | `create_deep_agent()` 将 `checkpointer` 传入 `create_agent()`；backend 另行处理文件 | Interrupt/Resume 和文件持久化必须分别测试 |

### 组装顺序的最小证据链

```text
create_deep_agent
  -> FilesystemMiddleware(backend=...)
  -> SubAgent/Summarization/PatchToolCalls middleware
  -> Skills/Memory/HumanInTheLoop（按配置）
  -> 自定义 middleware 插入和排除规则
  -> create_agent(..., checkpointer=..., store=...)
```

这条链解释了为什么本项目把 Policy、Recovery、Checkpoint 和 Replay 放在 Harness 层：它们跨越多个工具调用或图步骤，不能可靠地塞进单个业务工具。

## 阅读路线

按下面顺序读，每个文件先看入口和类型，再按关键符号跳转，不需要从第一行顺序读到最后一行。

| 顺序 | 文件 | 先回答的问题 |
|---|---|---|
| 1 | [libs/ARCHITECTURE.md](../libs/ARCHITECTURE.md) | 仓库把 runtime、Agent abstraction、Harness 分成什么职责？ |
| 2 | [graph.py](../libs/deepagents/deepagents/graph.py) | create_deep_agent 如何把模型、tools、middleware、backend、subagent 和 LangGraph 配置组装起来？ |
| 3 | [filesystem middleware](../libs/deepagents/deepagents/middleware/filesystem.py) | 文件工具如何暴露给模型，调用前后有哪些处理？ |
| 4 | [backend protocol](../libs/deepagents/deepagents/backends/protocol.py) | 各种 backend 必须支持什么操作，成功或失败怎么表达？ |
| 5 | [state.py](../libs/deepagents/deepagents/backends/state.py)、[filesystem.py](../libs/deepagents/deepagents/backends/filesystem.py)、[store.py](../libs/deepagents/deepagents/backends/store.py) | 相同的文件操作如何落到不同存储介质？ |
| 6 | [composite.py](../libs/deepagents/deepagents/backends/composite.py) 与 [sandbox.py](../libs/deepagents/deepagents/backends/sandbox.py) | 如何按路径组合不同后端，如何构建基于执行环境的后端？ |
| 7 | libs/deepagents/tests 中相应 middleware 或 backend 单元测试 | 代码承诺的可观察行为是什么，边界情况如何处理？ |

## 按文件写出的标准答案

### 1. graph.py：Harness 的组装入口

**标准答案：** create_deep_agent 是 Deep Agents 的主要构造入口。它解析模型、backend 和 profile，组装主 Agent 与 subagent 的 middleware 和工具配置，再把模型、系统提示、tools、middleware、state schema、checkpointer、store 等参数交给 LangChain 的 create_agent。返回值是可运行的 Agent graph；Deep Agents 还会附加相关运行配置和元数据。

**读代码时重点找：**

- create_deep_agent 的函数签名与参数文档：有哪些公开扩展点。
- backend 如何解析并传给文件、memory、skills 等 middleware。
- FilesystemMiddleware、subagent middleware、summarization middleware 等如何加入主栈。
- caller-provided middleware 如何参与组装。
- 最终的 create_agent 调用：哪些配置交给底层 Agent 或 runtime。

**理解边界：** graph.py 主要回答“如何组装”。某个文件工具具体怎样解析参数，不必在这里找；某个 checkpoint 如何保存，也不是它自己实现的。

### 2. middleware/filesystem.py：把文件能力接入 Agent

**标准答案：** FilesystemMiddleware 使用一组基于 backend 的文件工具，为模型提供列目录、读、写、编辑、搜索等能力。它会根据 backend 能力决定是否暴露可选工具，并在工具边界处理权限、参数错误和过大的返回内容。backend 提供统一的文件操作，middleware 负责 Agent 看到和调用这些操作的方式。

**读代码时重点找：**

- FilesystemMiddleware.__init__：默认 backend、tools allowlist、权限和结果大小配置。
- _create_tools 及各工具的创建函数：模型实际看到的工具名、参数和回调。
- wrap_model_call 相关方法：模型请求中有哪些工具会被过滤，提示如何补入。
- 权限检查与结果格式化代码：调用 backend 前后分别做了什么。
- supports_execution 和 execute 工具：命令执行只对支持相应协议的 backend 可用。

**容易混淆的点：** “模型能看到工具”不等于“调用一定成功”；“文件路径权限”不等于“shell 被隔离”。权限规则适用于中间件管理的内置文件工具，执行命令的安全要看实际 backend。

### 3. backends/protocol.py：稳定的能力契约

**标准答案：** BackendProtocol 把文件读取、写入、编辑、删除、列目录、glob、grep 等操作及其结果结构统一起来。每种实现可以采用不同的存储方式，但调用方可依赖同一套类型和方法。SandboxBackendProtocol 扩展了命令执行能力；它描述接口能力，不自动证明实现具有隔离。

**读代码时重点找：**

- BackendProtocol 中的抽象方法和共同属性。
- ReadResult、WriteResult、GrepResult、GlobResult 等结果类型。
- SandboxBackendProtocol 与 ExecuteResponse：执行命令能力的契约。
- 错误如何以结构化结果返回，哪些方法兼容同步与异步调用。

先读协议再读实现，可以避免把某个 backend 的细节误认为所有 backend 的行为。

### 4. Backend 实现：相同接口、不同生命周期与风险

| 文件 | 标准理解 |
|---|---|
| backends/state.py | 将文件数据放进 LangGraph 的 files state channel；在 graph 执行上下文内读写，与线程状态关联。 |
| backends/filesystem.py | 直接读写宿主文件系统；virtual_mode=True 提供虚拟路径和路径遍历防护，但不是进程或操作系统层面的沙箱。 |
| backends/store.py | 通过 LangGraph BaseStore 保存文件；调用者提供 namespace factory 来决定数据隔离范围，适合跨线程持久数据。 |
| backends/composite.py | 按路径前缀路由到不同 backend，未匹配路径走默认 backend；它组合能力，不替底层 backend 建立安全隔离。 |
| backends/sandbox.py | BaseSandbox 基于 execute 与文件上传能力派生多种文件操作；具体隔离强度由具体 sandbox 实现和配置决定。 |
| backends/local_shell.py | 本机文件系统加本机 shell。虽然实现执行协议，但明确没有沙箱或进程隔离；不能把它用于执行不可信代码。 |

## 推荐的阅读动作

### 动作一：从公开入口追到实现

拿一个具体问题，例如“Agent 的 read_file 如何读取文件”，按调用关系写出：

~~~text
create_deep_agent()
  → 组装 FilesystemMiddleware
  → middleware 创建 read_file 工具
  → 工具回调调用 BackendProtocol 对应操作
  → 具体 backend 返回 ReadResult
  → middleware 将结果变成工具消息
  → Agent 继续下一轮模型调用
~~~

每一步都到源码里找一个符号或方法作证据。不要只根据目录名猜职责。

### 动作二：做对照阅读

选 StateBackend 和 FilesystemBackend，围绕同一组问题对照：

1. 数据放在哪里？
2. 是否需要 LangGraph 执行上下文？
3. 路径如何解析？
4. 哪种错误会返回给调用者？
5. 生命周期和安全限制是什么？

再拿 StoreBackend 补充“跨线程持久化”和 namespace 设计。最后读 CompositeBackend，看路由如何改变路径。

### 动作三：用测试核对理解

找到相应测试，不要先问“它测试了哪些私有函数”，而要问：

- 用户可以观察到的结果是什么？
- 错误输入是否有稳定的错误响应？
- 权限拒绝是否阻止实际操作？
- 路由前后的路径是否符合公开约定？
- 异步与同步接口是否保持一致？

测试是理解行为的证据，源码是实现细节的证据；两者不一致时，应继续查清楚，而不是凭印象下结论。

## 一道源码追踪练习

**题目：** 用户让 Agent 修改项目文件并运行测试。你要解释源码中“读文件、改文件、执行命令、保存状态”分别由谁负责。

**标准答案：**

- create_deep_agent 负责装配 Agent graph 及其工具和 middleware。
- FilesystemMiddleware 负责将读写等文件操作作为模型可调用工具接入，并处理工具请求的权限和返回值。
- 文件工具将数据操作交给当前 backend；具体 backend 决定文件存储位置和文件操作实现。
- execute 能否提供取决于 backend 是否支持执行能力；真正是否安全取决于执行环境是否隔离。
- LangGraph 管理 Agent state 和运行时 checkpoint；checkpoint 可支持按配置恢复线程运行。文件是否跨线程保存则由 backend 的生命周期和存储方式决定。

## 读完后的验收清单

- [x] 能用一分钟解释三层架构。
- [x] 能从 create_deep_agent 追到 create_agent。
- [x] 能说明 middleware、tool、backend 的职责边界。
- [x] 能说出至少三类 backend 的数据位置、生命周期和主要限制。
- [x] 能解释 checkpointer 与 Store 或 backend 的区别。
- [x] 能指出 LocalShellBackend 不提供安全隔离。
- [x] 能从一个公开行为定位到相应源码和测试。
