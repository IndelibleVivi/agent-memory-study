# 评分缓存依赖：执行前协议

Agent Memory Study editors · 2026-09-12

依据 [MOSAIC arXiv v1](https://arxiv.org/abs/2607.16211v1) §§3.3–3.4、4.3，检验 Eq. (1) 的完整分数能否只按原图的 changed nodes / neighbors 失效。协议在本次 runner 首次执行前写定；这是已读公式后设计的定向反例与控制，不是盲测或第三方 preregistration。

## 固定输入与方法

- 四个原创抽象节点 a、b、c、d；association graph 为 a ↔ b、c ↔ d。两对节点分属 left / right communities，均固定 centrality 1/4。这是该规则图在均匀 teleportation 下的 PageRank 值，但实验不运行 PageRank 或 Leiden。
- 使用原文权重 α=1/2、β=3/10、γ=1/5；importance 是人为给定的正整数。检验完整评分及其缓存，不声称重建论文未详细给出的 importance 生成程序。
- `frontier` 每次都从 unresolved 状态与 prerequisite edges 重建。所有处理都正确移除退出节点、计算新进入节点，不借 stale frontier 制造结果。
- `full`：当前 frontier 全量评分；`graph-dirty`：只重算 Δ 及其有向边接收者，以及新进入 frontier 的节点；`dependency-aware`：另比较当前 frontier 最大 importance 与 previous community，任一变化时重算当前 frontier。
- 每场景从独立的 fresh before-state cache 开始；所有 treatment 使用相同 before / after 输入与字典序 tie-break。用 Fraction 保存精确分数，比较全部分数、排序与最终选择。
- `previous` 的改变是明确的 controller-context 干预，不伪装为自动生成的完整 dialogue trace。节点状态是否改变单独记录。

## 九个定向场景

| 场景 | 干预 | 待检验的预期 |
| --- | --- | --- |
| remote-max-change | 远处 c 的 importance 10→20 | a 邻居不变但归一化分母变；只按图失效可能留下 stale score / choice |
| remote-frontier-exit | 最大 importance 的 c 退出 frontier | a 分母变；即使 top-1 相同，也应检测 stale score |
| previous-community-change | previous b→d，节点状态不变 | continuity term 改变；需要 context 失效 |
| distant-nonmax-change | 非 frontier 的 d importance 2→3 | 不改变 a 的任何评分依赖；应保持一致 |
| own-nonmax-change | a importance 8→6，最大值仍为 10 | Δ 包含自身，应正确重算 a |
| no-change | 完全相同输入 | 全部缓存可复用且结果一致 |
| previous-same-community | previous b→a，community 不变 | pointer 变化不自动意味着 continuity term 变化 |
| prerequisite-unlock-max | d resolved 后解锁 importance=20 的 c | 所有处理都正确加入 c；a 仍可能因新分母留下 stale score |
| prerequisite-unlock-nonmax | d resolved 后解锁 importance=4 的 c | 分母不变；正确处理 eligibility 已足够 |

## 结论与否证条件

如果 `graph-dirty` 在任一固定反例中与 `full` 的 score 不一致，说明在本输入合同下，原图邻域不足以覆盖完整 Eq. (1) 的依赖。只有选择也不同，才报告 stale choice。若 `dependency-aware` 不能与全量结果一致，不得称其修复本实验。

控制必须确认合法局部变化能被处理、无关变化不会污染 a、相同 community 不产生假变化、新旧 frontier 正确维护。全部 inputs 和逐场景 outputs 随结果公开；不筛掉反直觉结果。

不运行 LLM、embedding、检索器、冲突检测器、作者源码或 benchmark；不测 latency。重算节点数不代表端到端复杂度，runner 自身会扫描全图和 frontier。该有限实验不证明 NCS 对局部函数无效，不证明 MOSAIC 实际缓存或 theorem 的所有实现均失败，不验证 Theorems 1–2。可用动态依赖或分项缓存等不同实现满足正确性，本次不比较其效率。
