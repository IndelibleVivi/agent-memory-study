# Jev 判断之后，记忆改变了吗？

Agent Memory Study editors · 2026-09-22

**10 个给定判断的源码案例已执行并复跑一致。** `obsolete` 高低对照保留相同的两条原记录和两个向量成员；有摘要回调且满足门槛的 `merge` 新增一个派生节点，同时保留两个来源。这说明当前维护动作的执行边界，不能用来评价 Jev 模型是否判断正确。

[进入共读专题](https://indeliblevivi.github.io/agent-memory-study/study/who-controls-memory/) · [论文精读](https://indeliblevivi.github.io/agent-memory-study/material/jev-mem-system-one-control/) · [完整结果](results.json) · [输入](fixtures.json) · [协议与修订](protocol.md) · [runner](study.py)

## 哪些行为实际运行了

固定官方 [Jev-Mem commit 81574eb](https://github.com/libingzheren/Jev-Mem/tree/81574eb23f3fd8d1a6c4d54a1e7d6f2dd539e9bb) 的 builder、policy、候选生成、consolidation，以及原始 NetworkX 图存储和 NumPy 向量存储。Jev 输出由 scripted controller 提供；encoder 是上游 MockEncoder；摘要回调仅拼接两段文本。SDK 数据载体与 LLM 构造边界被隔离，源码函数未改写；替身范围完整记录在 receipt 与协议中。

这是非破坏性维护的定向对照。概率从 fixture 输入，不是实测预测；英文文本只是控制路径的载荷，不构成英文或中文理解评价。运行不需要 API 凭据、模型权重或服务调用。

| 给定干预 | 调用前 → 后的节点数 | 观察 |
| --- | --- | --- |
| Admission 关闭，四类 type 都为 0 | 0 → 1 | 仍写入；准入问题未被询问 |
| Admission 开启，低分 / 高分 | 0 → 0 / 0 → 1 | 拒绝不留 node/vector 痕迹；允许时记录准入结果 |
| Obsolete 0.05 / 0.95 | 2 → 2 / 2 → 2 | 两份正文与向量仍在；判断值不同，关系拓扑相同 |
| Contradiction 0.95 | 2 → 2 | 两个 account 留存，并有 CONTRADICTS 关系 |
| Merge，无摘要回调 | 2 → 2 | 记录选择，未生成新表示 |
| Merge，有回调且满足门槛 | 2 → 3 | 新增 n3；来源是 n2、n1，原记录仍在 |
| Merge，但冲突高 / 选择概率低 | 2 → 2 / 2 → 2 | 回调未被调用，也未生成 summary |

写入例的快照包住一次 build；维护例先保存两条 observation，再比较一次 consolidate。向量成员仍存在，仅表明本次真实 NumPy store 中没有移除；没有执行语义 query 或磁盘 save/load。`merge` 回调返回的串接文本不是摘要质量结果。

## 怎样复跑

只检查已保存的公开 receipt，Python 标准库即可：

```bash
python3 -B research/jev-memory-contract-study/study.py --verify-checked
python3 -B -m unittest discover -s research/jev-memory-contract-study -p 'test_*.py'
```

这两个命令不加载 upstream，也不代表重做源码执行。完整 fresh run 需要独立的 upstream checkout，以及 NumPy、NetworkX、tqdm。实测环境为 Python 3.12、NumPy 2.5.3、NetworkX 3.6.1；不需要 typesafe-sdk、FAISS 或 sentence-transformers。

```bash
git clone https://github.com/libingzheren/Jev-Mem /path/to/Jev-Mem
git -C /path/to/Jev-Mem checkout 81574eb23f3fd8d1a6c4d54a1e7d6f2dd539e9bb
python3 -B research/jev-memory-contract-study/study.py \
  --source-dir /path/to/Jev-Mem --check
```

更新实验时，用同一命令的 `--write` 代替 `--check` 生成结果，再重跑 `--check`。缺失 FAISS / SentenceTransformer 的上游 warning 与这里刻意使用的 NumPy store / MockEncoder 相符，不表示发生了在线 fallback。运行不安装依赖。

receipt 的 source hashes 用于确认加载文件，fixture hash 绑定公开干预；UUID 仅在结果呈现时统一映射，端点方向和来源关系保留。输出数组顺序、实际输入和断言都可复核；单元测试会篡改保存结果，确认错误分支、伪造删除、错位输入和来源丢失会被拒绝。

## 怎样理解它

非破坏性整理可以帮助保留历史证据；想让旧事实退出当前任务的使用范围，还要有明确的读取规则与后续验证。这个实验没有观察实际误答，也没有实现另一套遗忘策略。Jev 本身的语义判断、日期/作用域理解、停止决策和端到端收益，需要独立的真实 controller 比较。

论文的 LoCoMo 数字属于作者报告。这里不复现 benchmark，也不把当前代码当作论文运行版本；源码、给定判断的执行、真实模型质量和后续任务收益分别保留证据身份。
