# Checkpoint / Interrupt / Resume v1

## 实验目的

验证长任务在写文件前被中断时，Harness 是否能够保存状态、等待审批并从同一个 thread 继续，而不是重新开始或产生提前副作用。

这次实验研究的是任务生命周期管理，不是模型修复能力。

## 任务和控制变量

实验 runner：evals/checkpoint_resume.py

- 使用 tiny_python_project；
- Fake Model 生成一次 write_file 调用和一次 run_tests 调用；
- write_file 之前配置 interrupt_on；
- 第一次 invoke 只允许进入 waiting 状态；
- 使用相同 thread_id 发送 approve resume；
- 恢复后执行一次 write_file，再执行一次 run_tests；
- 使用 InMemorySaver 保存 checkpoint；
- 不调用 DeepSeek，不联网，不需要服务器。

## 成功标准

1. 第一次运行包含 __interrupt__；
2. 暂停前 workspace 没有生产 diff；
3. 暂停前 checkpoint 已保存；
4. 恢复后 write_file 只执行一次；
5. 最终测试通过；
6. 恢复后的 checkpoint 数量增加；
7. replay 记录 waiting、resumed、test_run 和 finished。

## 离线结果

运行 ID：20261108T053319Z-69a171fa

- paused：true；
- resumed：true；
- side_effects_before_resume：false；
- checkpoint 数量：4 → 12；
- tests_passed：true；
- production diff：505 字符，内容是预期的 calculator 文档变化；
- replay test_runs：1；
- replay 状态顺序：run_started → workspace_created → run_waiting → run_resumed → test_run → run_finished。

runner 回归测试和既有 checkpoint 测试共 3 passed。全量测试将在提交前再次运行。

## 证据边界

这次证明了单进程、内存 checkpoint 和单次审批下的中断恢复行为。它还没有证明进程重启后的持久化恢复、跨机器恢复、并发任务隔离或真实模型在中断后的行为。

