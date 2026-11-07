# 仓库形态 Recovery fixture v1

## 实验目标

单文件 fixture 适合验证一个函数的修复，但不能观察 Agent 是否能从配置文件、多个模块和分层测试中定位问题。本阶段在当前项目内创建一个小型仓库形态 fixture，不切换到外部仓库：它包含包目录、配置文件、`pyproject.toml`、配置层、目录层和服务层。

## 项目结构

```text
recovery_inventory_repo/
├── config/checkout.json
├── inventory_app/
│   ├── settings.py
│   ├── catalog.py
│   ├── checkout.py
│   └── __init__.py
├── pyproject.toml
└── README.md
```

隐藏测试位于 workspace 外的 `evals/hidden_tests/test_inventory_repo.py`，分成三个层次：

1. 配置层：读取 JSON 后保留 `0.2` 的小数税率；
2. 目录层：库存只有 2 件时，订单请求 3 件只能计算 2 件；
3. 服务层：最终金额应为 `20 * (1 + 0.2) = 24`。

## 故意设置的错误

- `settings.py` 把 `0.2` 错误放大为 `20`；
- `catalog.py` 忽略库存上限，按请求数量计算；
- `checkout.py` 把税率直接加到小计上。

三个错误互相影响，模型需要阅读模块之间的调用关系和配置文件。

## 离线结果

原始仓库形态 fixture 的隐藏测试失败，同时修复三个生产模块后通过。全量测试为 `54 passed`。这证明隔离 workspace、外部隐藏测试和分层模块结构可以接入现有 Harness。

它还不能证明 DeepSeek 能在真实运行中正确定位所有模块，也不能代表真实开源仓库的复杂度。本阶段没有调用 DeepSeek，也不需要租服务器。

## 真实运行结果

运行目录：[20261107T091935Z-160b0df4](../runs/recovery/20261107T091935Z-160b0df4/)

```text
第一次分层测试：3 failed
修改文件：inventory_app/settings.py、inventory_app/catalog.py、inventory_app/checkout.py
第二次分层测试：3 passed
completed=true
tests_passed=true
execution_error=null
```

DeepSeek 根据三层失败输出，分别修正了税率读取、库存上限和税率应用。这个运行证明模型能在当前仓库形态 fixture 中沿模块调用链完成一次真实恢复，但还不能代表真实开源仓库的复杂度。

## 下一步

可以增加配置异常或包级依赖错误，也可以开始准备一个规模更大的多模块 fixture。当前仍不需要租服务器。
