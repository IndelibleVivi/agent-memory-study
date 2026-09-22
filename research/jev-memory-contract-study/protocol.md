# Jev-Mem：判断到状态变化的源码实验协议

Agent Memory Study editors · 2026-09-22

这是读过源码后设计的定向刻画（source-informed characterization），不是盲测或第三方 preregistration。问题是：**给定 admission、obsolete、contradiction 与 representation 判断，当前代码具体改变什么？** 本实验不评价模型是否能从自然语言中判断正确。

## 来源和执行对象

- 官方 [Jev-Mem](https://github.com/libingzheren/Jev-Mem/tree/81574eb23f3fd8d1a6c4d54a1e7d6f2dd539e9bb)，固定 commit `81574eb23f3fd8d1a6c4d54a1e7d6f2dd539e9bb`。fresh runner 拒绝不匹配或 dirty checkout；receipt 保存加载文件的内容摘要与函数 locator，用于重跑时确认代码身份。
- 相关论文是 [arXiv:2609.23986v1](https://arxiv.org/html/2609.23986v1)，作者 Dongming Jiang、Yi Li、Bingzhe Li；AMS material 为 `jev-mem-system-one-control`。论文阅读另有范围说明，本实验不把当前 commit 绑定为产生论文结果的版本。
- 原函数：`MemoryBuilder.build / consolidate / _store_jev_node`、`WritePolicy`、`find_candidates`、questions、typing/config、keyword 与 temporal helpers。真实后端为上游 `NetworkXGraphDB`、`NumpyVectorDB`，encoder 为上游 `MockEncoder`；TRG 和 builder 使用真实构造器并显式关闭 LLM。辅助模块可能只加载定义，文件出现不代表其所有函数都已执行。
- 替身：SDK 的 Noul/Choice/ChoiceAnswer 数据载体、scripted controller、拼接文本的 summary callback，以及一旦被调用就报错的 LLMController。源函数不重写，正常相对 import 解析到外部 checkout；SDK 的验证、网络、重试、置信度计算均不在范围内。

## 干预、控制和预期

`fixtures.json` 是原创合成文本与配置的真源；没有私人聊天、真实用户偏好或 benchmark 数据。每例重新构造空后端。`write_enabled=true`；关闭自动周期 consolidation，维护案例在两次真实 build 后显式调用一次 consolidate。该显式配置不是完整 shipped profile 重放。

| 组 | 对照 | source-informed 预期 |
| --- | --- | --- |
| Admission，3 例 | 关闭且 type 全零；开启且低分；开启且高分 | 分别写入、拒绝、写入；检查类型/准入记录和实际节点/向量成员 |
| Obsolete，2 例 | 同样两条记录、同样其余判断，只把 obsolete 从 0.05 改为 0.95 | 记录不同判断，节点、向量成员与关系拓扑相同 |
| Contradiction，1 例 | 高 contradiction、keep_separate | 保存两份 account，并增加 CONTRADICTS 关系 |
| Representation，4 例 | merge 无回调；merge 有回调；有回调但冲突；有回调但选择概率低 | 只有满足门槛且有回调的一例增加派生表示；仍保留来源 |

`obsolete` 的原问题有方向：新记录是否明确替代候选的旧事实。本文不把仅仅更近的时间当作正确的 supersession label。所有概率与选项是人为指定的干预，不是新模型推理。

写入案例的 `before` 是 build 之前的空状态；维护案例的 `before` 是两条 observation 已保存、consolidate 尚未执行的状态。两种案例的快照边界明确区分，不能拿“从空库写入两条记录”伪装成 consolidation 的副作用。

## 记录与判据

- 保存每例有效配置、原始 sequence、typed question ID 及给定返回值、build 返回类别、consolidation decisions、node 内容、原文、准入/类型信息、派生来源、关系和 summary callback 输入。
- 运行时保留真实 UUID；只在 receipt 中按创建顺序映射成 `n1/n2/n3`，包括嵌套 decision、父节点和 source-memory 引用。忽略 link UUID、内部 dedup hash、系统日志与未使用的 access timestamps；保留关系端点/类型/方向。没有把上游 EventNode 替换为自造类。
- `MockEncoder` 是词项哈希向量。向量成员观测来自真实 NumPy store，但未调用 query engine、真实语义 encoder、answerer、judge 或持久化 save/load。原文仍在本次内存对象中，不证明磁盘副本或以后任务中的表现。
- 逐例检查实际 Jev 写入 metadata，避免配置遗漏后落入 MAGMA 却报告成功；再检查准入对照、两条原记录保留、obsolete 分数留存、冲突边、summary 门槛和来源。任何逐例断言或跨例不变量失败都拒绝生成完成 receipt。
- fresh `--check` 重跑固定源码并比较整个规范化 JSON。`--verify-checked` 只复核 fixture 身份、输入、逐项断言与汇总，不执行 upstream；不能当作重跑。

## 实现修订记录

首份执行前草案计划用 stdlib 后端替身。执行准备发现现有隔离环境已具备 NumPy / NetworkX，因此在得到可接受结果前改为上游真实后端，移除 polyfill、后端重写和额外 MAGMA 案例。10 个核心干预保留。调试中纠正了 base config 未合并、consolidation 快照位置和嵌套 UUID 规范化；未通过断言的调试运行不进入结果。此记录保留方法变化，不将最终协议描述成未看过源码的预测。

## 结论上限

可以描述这些给定判断之后的函数级状态变化。不能据此估计 Jev 的语义准确率、校准、检索质量、实际回答收益、删除所有副本、参数遗忘或论文 benchmark 的有效性。跨 controller、真实自然语言与端到端任务比较仍是材料页的 `proposed-not-run` protocol。
