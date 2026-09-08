# 旧经验还在，为什么读不到？

Agent Memory Study editors · 2026-09-08

这份可复跑的阅读实验接续 Hu、Long 与 Wang 的 [*When Continual Learning Moves to Memory*，arXiv v1](https://arxiv.org/abs/2604.27003v1)。原文在 frozen LLM agent 上研究经验表示、检索组织与跨任务迁移；这里把其中一个问题缩小到可直接检查的检索阶段：**旧条目没有删除，有限的返回位置仍可能被相似条目占满；但按 key 去重，也可能筛掉内容不同的必要经验。**

这是 AMS 原创的有限 synthetic witnesses，使用 SQLite FTS5 的 BM25。没有执行作者的 ReMe 实现、Qwen-Plus、AgentGym、任务环境或论文 benchmark。返回目标条目仅表示检索命中，不表示 agent 会使用它、答对问题或避免遗忘。

## 亲自运行

需要 Python 3，且其 `sqlite3` 编译时启用了 FTS5；本次执行为 Python 3.13.3 / SQLite 3.53.4，macOS arm64。无需安装 pip 包、下载模型、联网或提供 API key。

```bash
python3 -B research/experience-reuse-retrieval-study/study.py
python3 -B research/experience-reuse-retrieval-study/study.py --check
python3 -B -m unittest discover -s research/experience-reuse-retrieval-study -p 'test_*.py'
```

第一条实际重建 12 个检索池并输出 108 次选择；第二条重新执行并与 [results.json](results.json) 对比。对比涵盖排名、保留计数与选择结果，排除 SQLite version 字段；分数保存到小数点后 12 位，版本差异若改变这些结果仍会报错。环境若不含 FTS5，会由 SQLite 明确报错，不自动切换检索器。

[fixtures.json](fixtures.json) 是完整原创输入与显式 relevance labels；[study.py](study.py) 是唯一 runner；[test_study.py](test_study.py) 含 8 项行为测试。没有从私人项目、聊天或作者 trajectory 取样。

## 改变了什么，固定了什么

四个场景各有 3 条旧记忆；添加数量取 0、2、4。每次在同一池上先计算一次完整排名，再分别执行三个选择策略，返回条数上限取 1、3、5：

| 策略 | 如何填充返回位置 | 可能丢掉什么 |
| --- | --- | --- |
| `top-k` | 按原始排名直接截取 | 排名靠后的必要经验 |
| `unique-key` | 每个完全相同的 key 只取第一个，继续向后扫描 | 相同 key 下的不同条件或方法 |
| `unique-key-value` | 仅合并 key 与 value 都逐字相同的条目，继续向后扫描 | 仍无法识别改写后的语义重复 |

检索只索引 key，采用 FTS5 默认 tokenizer；fixture 的空格词查询按 AND 匹配。使用 [SQLite 官方 BM25](https://sqlite.org/fts5.html#the_bm25_function) 的默认参数（k1=1.2、b=0.75），分数越小越靠前，同分按插入顺序。value 不参与打分；相关性标签只用于选择后的 hit 计算，三个选择策略均看不到标签。

“预算”在这里严格指**最多返回多少条记录**。去重策略会扫描更深的排名，不是等计算成本或等 token 的比较；不会补造不存在的记录来凑满预算。三种策略不删除存储记录、不改写 value，也不重算各自的索引。增长前后 BM25 的语料统计会变化；结果另存旧匹配项之间的相对次序，当前 12 个池中该次序均保持不变，因此这些排出例子可以定位到新增候选占位，而不是旧条目间排名翻转。

## 实际结果

以下取返回预算 3、添加 2 条之后。“命中”表示保留了 fixture 指定的必要旧经验。

| 场景 | 原始 top-k | 按 key 去重 | 按 key + value 去重 |
| --- | --- | --- | --- |
| 完全重复的放置经验挤入清洗问题 | 未命中 | 命中 | 命中 |
| 同量增加无关卧室经验（控制） | 命中 | 命中 | 命中 |
| 同一 key、不同措辞的放置经验 | 未命中 | 命中 | 未命中 |
| 相同“room search”key，下有开门与上锁两种情况 | 命中 | 未命中 | 命中 |

第一例中，必要清洗经验的原始排名随添加 0 / 2 / 4 条重复记录变为 **2 / 4 / 6**。预算 3 在添加 2 条时漏掉它；扩大到 5 只推迟到添加 4 条时再漏掉。旧记忆始终为 **3/3 保留**。同量无关增长的目标排名始终为 2。

第四例在**尚未添加任何新条目时**，按 key 去重就已漏掉上锁房间所需的“找钥匙并解锁”条件。两条 key 完全相同、分数相同，先插入哪条就留下哪条。测试翻转顺序后结果随之改变：该策略没有识别哪一个条件适用。按 key + value 精确去重保留了两种情况，但第三例表明，它也无法消除同一意思的不同措辞。

这些是构造的反例和控制，不能汇总为真实错误率、总体性能排名或“去重算法优胜率”。108 次选择共享四个场景，并非 108 个独立任务样本。

## 回到论文：不要只挑最大的增益

原文的 FWT 是“先经历来源任务、再经历目标任务”的最终成功率，减去**同一 memory 配置只经历目标任务**的 scratch 成功率。它不是零样本迁移，也不是相对于无记忆 agent 的提升。无记忆结果用于划分 baseline-success / baseline-fail，另行定义 RR / NL。

| 原文条件 | Scratch 成功率 | 跨任务后成功率 | FWT |
| --- | --- | --- | --- |
| ALFWorld A→B，Raw（Table 3） | 80.5% | 71.0% | −9.5 pp |
| ALFWorld A→B，Insight（Table 3） | 65.5% | 72.0% | +6.5 pp |
| BabyAI A→B，Cond-Agg（Table 5） | 46.0% | 55.0% | +9.0 pp |
| BabyAI A→B，Cond-Ind（Table 5） | 32.0% | 47.0% | +15.0 pp |

因此 Raw 与 Insight 的 FWT 相差 16 pp，最终成功率却只差 1 pp；Cond-Ind 的迁移增益更大，最终成功率仍低于 Cond-Agg。上述为论文报告的两次运行均值，本站没有重跑这些任务；不能从表内均值推断统计显著性。

Appendix C 还明确说明，周期检索会改变训练时的行动和积累下来的 memory pool。因此 Cond-Ind / Cond-Step 不能单凭最终差异隔离“评测时多检索几次”的效果。本文小实验为每个池复用相同排名，隔离的是**返回策略**；也没有回答真实 agent 的训练和检索反馈问题。

## 怎样借走这个问题

检查一个实际记忆系统时，可以把问题具体化为：旧经验是否还在、它排第几、哪些记录实际进入 context、重复发生在 key 还是内容、必要的适用条件是否被合并掉。先查看这些中间结果，再决定是否需要去重、改 key 或改变检索时机。

这只是由论文和本次有限反例支持的诊断建议。固定真实任务池，对照 retriever、保留实际 context，并结合 agent 成功率与旧任务回测，仍是**未执行的迁移研究**。本实验没有测试语义去重、embedding retrieval、concentration across queries、自然语言理解、延迟或实际 token 成本。
