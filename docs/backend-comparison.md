# Deep Agents Backend 对比标准答案

Backend 决定文件等 Agent 数据由谁读写、保存在哪里，以及是否额外支持命令执行。选择 backend 时要同时看数据生命周期、运行环境和安全边界，不能只看它是否实现了同一套接口。

## 标准答案：五类后端怎么选

| Backend | 数据位置与生命周期 | 命令执行 | 适用场景 | 主要限制 |
|---|---|---|---|---|
| StateBackend | LangGraph Agent state；与当前 graph 或 thread 状态关联 | 不支持 | 临时文件、一次任务中的 scratch 数据、无需独立文件持久化的 Agent | 需要在 LangGraph graph 执行上下文中操作；跨线程共享应选 Store 等其他方案 |
| FilesystemBackend | 宿主机文件系统 | 不支持 | 可信的本地开发工具直接读写工作目录 | 直接访问文件系统；虚拟路径检查不是 sandbox 或进程隔离 |
| StoreBackend | LangGraph BaseStore；namespace factory 决定数据作用域 | 不支持 | 跨线程保留文件或 memory | namespace 必须按应用与用户正确隔离；通常需要可用的 Store 或 runtime |
| CompositeBackend | 自身不存储数据；按路径把请求交给其他 backend | 取决于默认 backend 的能力 | 临时文件走 state、memory 走 Store 等混合策略 | 路由只分发请求；不替代底层 backend 的权限控制或安全隔离 |
| SandboxBackend 或自定义 sandbox backend | 由具体隔离环境决定，常见为容器或远程执行环境 | 通常支持 | 在隔离环境中修改代码、运行测试或处理不可信任务 | SandboxBackendProtocol 只是能力接口；必须核实具体实现的隔离、网络、资源和凭据配置 |

LocalShellBackend 单独提醒：它实现了文件操作和命令执行接口，但在宿主机上用 shell 执行命令，没有沙箱隔离。它不能被归类为安全 sandbox。

## 面试回答模板

> 我会根据数据的生命周期和执行风险选 backend。单次运行的临时文件可以使用 StateBackend；需要线程间共享的记忆或文件可用 StoreBackend，并按用户或租户设计 namespace；本机可信开发工具可以考虑 FilesystemBackend。如果要把临时数据和长期数据分开存，可用 CompositeBackend 按路径前缀路由。若任务需要执行不可信代码，不能因为后端实现了执行协议就认为安全，必须使用经确认具有隔离能力的 sandbox 实现，并限制文件、网络、资源及凭据访问。

## 逐个理解

### StateBackend

- 文件数据保存在 LangGraph state 的 files channel 中。
- 对同一 graph 或 thread 的运行，数据随 state 更新，并受 checkpointer 配置影响。
- 它适合任务过程中的临时文件或短期上下文，不是自动跨线程共享的用户文件库。
- 直接在 graph 外调用通常不可行；要预置文件，可按 graph 输入约定传入 files state。

### FilesystemBackend

- 将操作映射到宿主机文件系统。
- virtual_mode=True 将虚拟路径锚定到 root_dir 并阻止常见路径遍历；这能改善路径语义和 guardrails，但没有操作系统级隔离。
- 应只用于可信的本地开发环境或经过妥善隔离的工作环境。不要让不可信 Agent 直接接触含有个人文件、密钥或系统配置的目录。
- virtual_mode=False 允许使用真实主机路径，访问边界更宽。

### StoreBackend

- 使用 LangGraph Store 保存文件数据。
- namespace factory 接收运行时并返回 namespace tuple；这个值决定数据共享或隔离范围。
- namespace 不能留给偶然默认值。多用户服务应把稳定的用户或租户身份纳入 namespace，并确认身份来自可信运行时上下文。
- 它解决跨线程数据保存问题；图状态恢复仍由 checkpointer 负责。

### CompositeBackend

- default 处理没有命中路由的路径。
- routes 将路径前缀映射到指定 backend；匹配最长前缀，交给 backend 前会剥掉路由前缀，结果路径再映射回统一路径。
- 典型设计是临时工作文件放在 StateBackend，而 /memories/ 放在 StoreBackend。
- 路由负责选后端，不会自动给操作加密、隔离用户或限制后端能力。
- execute 的可用性与执行位置要结合 middleware 的能力判断和 composite 默认 backend 来检查，不能仅凭某一条文件路由推断。

### Sandbox 能力与 LocalShellBackend

- SandboxBackendProtocol 表明后端提供命令执行相关接口。协议的名字不是隔离保证。
- BaseSandbox 提供基于执行命令和文件上传的常见文件操作实现；实际隔离由具体子类及其部署环境提供。
- LocalShellBackend 的命令运行在本机宿主系统上。其 virtual_mode 只约束文件 backend 的路径解析，不限制 shell 命令可访问的主机路径。
- 对 coding Agent，优先选择一次性或可销毁的隔离环境，限制网络和资源，并避免注入不必要的凭据。对敏感操作再使用权限策略或人工审批。

## 一个混合配置示例

下面的配置让普通路径走 StateBackend，/memories/ 路径走持久化 Store。它展示的是路由思路，不代表 namespace 配置适合所有部署：

~~~python
from deepagents.backends import CompositeBackend, StateBackend, StoreBackend

backend = CompositeBackend(
    default=StateBackend(),
    routes={
        "/memories/": StoreBackend(
            namespace=lambda rt: (
                rt.server_info.user.identity,
                "filesystem",
            )
        )
    },
)
~~~

调用侧将这个 backend 传给 create_deep_agent。路由的实际隔离效果仍依赖 Store 的 namespace 身份是否可信，以及具体 Store 的访问控制。

## 不要混淆的四件事

| 常见说法 | 更准确的理解 |
|---|---|
| “用了 StateBackend，文件就永久保存了。” | 文件存在于 Agent state；跨进程恢复取决于 checkpoint 配置，跨线程共享要看其他存储方案。 |
| “设置 virtual_mode=True 就是 sandbox。” | 它提供虚拟路径语义和路径遍历限制，不提供进程隔离。 |
| “实现了 SandboxBackendProtocol 就安全。” | 这只表明具有相关操作能力；隔离要由具体实现和部署配置证明。 |
| “CompositeBackend 是安全代理。” | 它按路径分发操作，不会替代底层 backend 的安全控制。 |

## 为 Issue-to-PR Agent 选择后端

你的目标是让 Agent 在代码仓库中分析 Issue、修改文件并运行测试。可以把选择拆成两类：

1. **工作区与命令执行**：使用明确隔离、可回收的 sandbox 或 worktree 环境来读写代码和运行测试。评估其网络策略、挂载范围、资源上限、环境变量和凭据暴露面。
2. **Agent 运行状态和持久数据**：用 LangGraph checkpointer 支持运行恢复；用 StateBackend 保存任务过程内的临时数据；只有确实要跨任务或跨线程共享的 memory 才放入 StoreBackend，并明确 namespace 设计。

这样能把“任务运行状态”“临时文件”“长期记忆”和“代码执行环境”分开建模，每一层都能单独测试和评估。

## 自测题

1. 哪种 backend 适合当前线程的临时文件？它依赖什么运行上下文？
2. 为什么 StoreBackend 的 namespace 会影响多用户数据隔离？
3. CompositeBackend 是如何把 /memories/notes.md 路由到对应后端的？
4. FilesystemBackend 的虚拟路径检查和容器隔离有什么区别？
5. 如果 backend 实现 SandboxBackendProtocol，你还要验证哪些安全属性？
6. LocalShellBackend 为什么不能用来执行不可信的 Issue 代码？

**参考要点：** State 与 graph 或 thread state 关联；Store namespace 决定数据分区；Composite 根据前缀选择后端并改写传入路径；路径规范化不是进程隔离；协议不保证 sandbox 强度；LocalShellBackend 在本机运行任意命令。
