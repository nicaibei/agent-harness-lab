# Checkpoint / Interrupt / Resume v2

## 实验目的

验证任务在进程 A 中断后，进程 B 能否从同一个 thread 的持久化 checkpoint 继续执行。

v1 只验证了同一进程里的 InMemorySaver。v2 增加进程重启变量，研究更接近真实运行时的恢复能力。

## 实现

当前环境没有安装 SQLite 或 Postgres Checkpointer，因此没有新增第三方依赖。Harness 增加了 FileCheckpointSaver：

- 基于 LangGraph InMemorySaver 的存储结构；
- checkpoint、channel blobs 和 pending writes 使用 JSON-plus 序列化；
- 二进制序列化结果使用 Base64 保存；
- 不使用 pickle；
- 进程 B 启动时从 checkpoint-store.json 重新加载。

实验 runner：evals/checkpoint_resume.py

- pause 阶段创建 workspace、启动 Agent 并在 write_file 前中断；
- pause 阶段保存 pause.json 和 checkpoint-store.json 后退出；
- resume 阶段创建新的 Agent 和新的 FileCheckpointSaver；
- resume 阶段使用相同 thread_id 发送 approve；
- 恢复后执行 write_file、run_tests 并保存最终产物。

## 成功标准

1. 进程 A 进入 waiting；
2. 进程 A 退出前没有生产 diff；
3. 进程 B 能加载 checkpoint；
4. 恢复后写入只执行一次；
5. 最终测试通过；
6. checkpoint 数量增加；
7. replay 记录 process_restarted、run_resumed、test_run 和 run_finished。

## 离线结果

运行 ID：20261108T061342Z-d7821869 的跨进程验证结果：

- paused：true；
- resumed：true；
- side_effects_before_resume：false；
- checkpoint 数量：4 → 12；
- tests_passed：true；
- production diff：505 字符；
- replay test_runs：1；
- replay 状态顺序：run_started → workspace_created → run_waiting → process_restarted → run_resumed → test_run → run_finished；
- checkpoint-store.json：约 43 KB。

跨进程回归测试和 v1 测试共 4 passed。全量测试结果为 71 passed，只有 Windows .pytest_cache 写入警告。

## 证据边界

这次证明了单机文件型 checkpoint 的跨进程恢复。它还没有证明多进程并发写入、跨机器存储、数据库事务、崩溃中途的原子恢复或真实模型中断后的行为。FileCheckpointSaver 是实验实现，不能直接当作生产存储后端。

