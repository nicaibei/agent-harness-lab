# Backend 实验报告

## 实验目的

在不配置模型和 API Key 的情况下，验证 Deep Agents backend 的四个问题：

1. StateBackend 是否支持 write、read、edit、delete。
2. FilesystemBackend 的虚拟路径如何映射到真实目录。
3. CompositeBackend 如何按路径前缀选择 backend。
4. 越界路径和路由前缀恢复分别表现为什么。

## 运行方式

在 VS Code 集成终端中执行：

~~~powershell
cd D:\langgraph_learning\deepagent\libs\deepagents
uv run python ..\..\docs\experiments\backend_experiment.py
~~~

如果终端找不到 uv，使用已创建的虚拟环境：

~~~powershell
.\.venv\Scripts\python.exe ..\..\docs\experiments\backend_experiment.py
~~~

脚本使用一个最小 LangGraph 图承载实验。这样做是因为 StateBackend 需要在图执行上下文中读写 files state channel。

## 实验结果

| 实验 | 输入路径 | 实际 backend | 结果类型 | 结果 |
|---|---|---|---|---|
| State write | /state/demo.txt | StateBackend | WriteResult | 成功，返回原路径 |
| State read | /state/demo.txt | StateBackend | ReadResult | 成功，内容为 hello state |
| State edit | /state/demo.txt | StateBackend | EditResult | 成功，替换 1 次 |
| State read after edit | /state/demo.txt | StateBackend | ReadResult | 成功，内容为 hello backend |
| State delete | /state/demo.txt | StateBackend | DeleteResult | 成功，返回原路径 |
| State read after delete | /state/demo.txt | StateBackend | ReadResult | 失败，文件不存在 |
| Filesystem write | /filesystem/demo.txt | FilesystemBackend | WriteResult | 成功 |
| Filesystem read | /filesystem/demo.txt | FilesystemBackend | ReadResult | 成功 |
| Filesystem edit | /filesystem/demo.txt | FilesystemBackend | EditResult | 成功，替换 1 次 |
| Filesystem delete | /filesystem/demo.txt | FilesystemBackend | DeleteResult | 成功 |
| Filesystem 越界写入 | /../filesystem-escape.txt | FilesystemBackend | ValueError | 失败，Path traversal not allowed |
| Composite memory write | /memory/note.txt | StateBackend | WriteResult | 成功，返回 /memory/note.txt |
| Composite memory read | /memory/note.txt | StateBackend | ReadResult | 成功，backend 内部路径为 /note.txt |
| Composite memory edit | /memory/note.txt | StateBackend | EditResult | 成功，返回原路由路径 |
| Composite memory delete | /memory/note.txt | StateBackend | DeleteResult | 成功，返回原路由路径 |
| Composite workspace write | /workspace/note.txt | FilesystemBackend | WriteResult | 成功，返回 /workspace/note.txt |
| Composite workspace read | /workspace/note.txt | FilesystemBackend | ReadResult | 成功，backend 内部路径为 /note.txt |
| Composite workspace edit | /workspace/note.txt | FilesystemBackend | EditResult | 成功，返回原路由路径 |
| Composite workspace delete | /workspace/note.txt | FilesystemBackend | DeleteResult | 成功，返回原路由路径 |
| Composite memory 越界写入 | /memory/../memory-escape.txt | StateBackend | WriteResult | 成功；StateBackend 将其当作普通 key |
| Composite workspace 越界写入 | /workspace/../workspace-escape.txt | FilesystemBackend | ValueError | 失败，Path traversal not allowed |

FilesystemBackend 的虚拟路径 /filesystem/demo.txt 在本次运行中映射到临时根目录下的 filesystem/demo.txt，没有写入仓库目录。

## 关键结论

### 1. StateBackend 的 CRUD 依赖 LangGraph state

StateBackend 的文件不是直接写入磁盘，而是通过 LangGraph 的 files channel 读写。连续多次写入需要该 channel 使用 Deep Agents 的增量 reducer；实验因此复用了项目中的 FilesystemState。

StateBackend 可以完成 CRUD，但它本身不会像 FilesystemBackend 那样检查路径是否越界。对于 StateBackend，路径更接近 state 中的 key，而不是宿主机路径。

### 2. FilesystemBackend 的 virtual_mode 不是完整沙箱

virtual_mode=True 会把虚拟绝对路径映射到 root_dir，并阻止 .. 路径遍历。本次实验中的越界写入直接抛出 ValueError。

这属于路径规范化和 guardrail，不代表进程隔离、资源限制或网络隔离。FilesystemBackend 仍然直接操作指定的宿主文件系统。

### 3. CompositeBackend 会剥离并恢复路由前缀

对于 /memory/note.txt：

~~~text
外部路径       /memory/note.txt
选择 backend    StateBackend
内部路径       /note.txt
返回路径        /memory/note.txt
~~~

对于 /workspace/note.txt：

~~~text
外部路径       /workspace/note.txt
选择 backend    FilesystemBackend
内部路径       /note.txt
返回路径        /workspace/note.txt
~~~

因此，CompositeBackend 对调用者保持统一的虚拟路径，对具体 backend 传递去掉路由前缀的路径。

### 4. 路由不会自动增加安全能力

/workspace/../workspace-escape.txt 最终交给 FilesystemBackend，因此被拒绝；/memory/../memory-escape.txt 最终交给 StateBackend，因此被作为普通 state key 接受。

这说明安全行为取决于实际路由到的 backend。CompositeBackend 只负责分发和路径映射，不会替底层 backend 增加统一的路径检查。

## 与 Harness 工程的关系

这个实验验证了 Harness 的一个重要边界：

~~~text
Agent-facing tool
  → FilesystemMiddleware
  → BackendProtocol
  → 具体 backend 的存储和安全行为
~~~

Middleware 可以统一工具接口、权限规则和结果处理，但最终的数据生命周期、路径语义和执行隔离仍由 backend 决定。后续设计 Issue-to-PR Harness 时，需要把路径策略、工作区隔离和命令执行安全作为独立能力评测。

## 你在 VS Code 中完成后的检查

- [ ] 能运行脚本且不需要 API Key。
- [ ] 能解释为什么 StateBackend 必须在 LangGraph 图上下文中运行。
- [ ] 能指出 FilesystemBackend 越界时抛出 ValueError。
- [ ] 能说出 CompositeBackend 的内部路径是 /note.txt，返回路径仍带 /memory/ 或 /workspace/。
- [ ] 能解释为什么 StateBackend 接受 ../ key，而 FilesystemBackend 拒绝路径遍历。
- [ ] 将终端输出保存到自己的学习记录中，并写一句本实验最重要的结论。
