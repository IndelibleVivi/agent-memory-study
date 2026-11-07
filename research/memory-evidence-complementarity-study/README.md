# Memory evidence complementarity: exact finite witnesses

研究日期：2026-11-05（Asia/Singapore）
署名：Cove · AI-assisted research
状态：**精确有限分析已执行；模型协议未执行。**

本研究问：固定任务、读者侧信息与候选池后，选材器需要看见什么，才能识别预算内的充分证据组合？它补充 AMS 对候选竞争、表示充分性和经验复用的研究，不提出新的平台、检索系统或 benchmark。

完整论证的 canonical source 是 [研究文章](../../study/entries/memory-evidence-complementarity.md)，元数据是 [entry JSON](../../study/entries/memory-evidence-complementarity.json)。本目录拥有方法、精确计算、结果和后续执行协议。

## 文件与证据等级

| 文件 | 内容 | 证据边界 |
| --- | --- | --- |
| [study.py](study.py) | 仅使用 Python 标准库的有限穷举和有理数计算 | 不调用模型、外部服务、检索器或上游代码 |
| [results.json](results.json) | 唯一脚本生成的可复核结果 | 作者构造的有限世界与配置；不是独立经验任务样本 |
| [receipt.json](receipt.json) | 实际执行命令、环境、退出状态及脚本/结果哈希 | 证明本次本地执行；哈希不构成可信执行证明 |
| [source-comparison.md](source-comparison.md) | 原始论文主张、报告结果与本研究推论的分栏比较 | 上游结果保留作者报告身份 |
| [protocol.md](protocol.md) | 具体输入、配对条件、观察量和失败判据 | Proposed, not run；没有模型结果 |

## 已执行的四组对象

### 1. 隐藏支持与低阶观测

候选全集 `U` 有 `n` 条；每个世界有一个隐藏三元支持 `T`，效用为 `F_T(S)=1[T⊆S]`。允许观察所有 `|S|≤2` 的效用，但其余可见信息在世界间相同。全部低阶 transcript 都是零。

若世界中的 `T` 均匀分布，预算为 `b` 条，任意遵守该观测限制的策略的平均成功率至多为 `choose(b,3)/choose(n,3)`。正文给出解析证明；脚本穷举候选选择核对计数。随机策略的结论来自对固定输出的计数取平均，不靠抽样仿真。

| `n` | `b` | 上界 | 完整支持 oracle |
| --- | --- | --- | --- |
| 6 | 2 | 0 | 0 |
| 6 | 3 | 1/20 | 1 |
| 6 | 4 | 1/5 | 1 |
| 8 | 3 | 1/56 | 1 |
| 8 | 4 | 1/14 | 1 |

这是观测接口的限制。节点文本、query-conditioned 特征或语义图边可能携带额外信息，因此不能只看图是 pairwise 的就套用此界。该界对均匀世界平均成立，也推出至少一个困难世界；不声称每个世界都具有同一个逐点上界。

### 2. 互补支持与局部正收益诱饵

六条候选分为支持 `T={s1,s2,s3}` 与诱饵 `D={d1,d2,d3}`，预算 3 条：

`F(S)=max(1[T⊆S], ε|S∩D|)`。

分别取 `ε=1/20,1/10,1/4`。每种取值枚举全部 64 个子集，检查单调性、一个明确的次模性反例、空集处三阶有限差分，以及三种确定性 package greedy 的结果。每步候选包按边际收益/条数、总收益、字典序排序。

单条与双条前瞻均选择三个诱饵，价值分别为 `3/20,3/10,3/4`；三条前瞻选择完整支持，价值为 1，与枚举最优值相同。随着 `ε→0`，前两种指定启发式的近似比趋近零。此结论不是一般算法下界，也不是对真实模型的运行结果。

### 3. 模块化正控制

五条候选固定权重为 `6/20,5/20,4/20,3/20,2/20`。预算 3 时，单条贪心取前三条，效用 `3/4`，等于枚举最优值。脚本也核对边际收益不随集合变化。该对照避免将结论写成“逐条选择总是失败”。

### 4. 替代充分集合与预算嵌套

候选为 `abcde`，最小充分集合族为 `{abc,de}`。选 `de` 已充分，但对 nominal `abc` 的 recall 为 0；选 `abd` 不充分，却比 `de` 覆盖更多支持并集中的条目。

脚本遍历 32 个候选池、预算 0–5 和所有预算内选择，核对 1,053 个配置中的嵌套关系：

`selected has support ⇒ pool has budget-feasible support ⇒ pool has support`。

七个显式示例行进一步给出描述性比例恒等式：`6/7 × 5/6 × 3/5 = 3/7`。这里的解码器被作者定义为“当且仅当选中完整支持才成功”。这不能直接变成 LLM 正确率上限；它也不是候选、预算、选择三个模块的因果效应分解。

## 复跑

在仓库根目录执行：

```bash
python3 -B research/memory-evidence-complementarity-study/study.py --check
```

若有意修改方法，先改脚本与正文，重新生成结果，再核对：

```bash
python3 -B research/memory-evidence-complementarity-study/study.py --write
python3 -B research/memory-evidence-complementarity-study/study.py --check
```

`--check` 重新计算全部对象后比较解析后的 JSON，不只检查保存文件的存在或哈希。脚本没有网络路径，没有第三方依赖，也不读取任何私有语料。`receipt.json` 记录本次实际执行，后续复跑不应冒充原 receipt 中的时间或环境。

整库的 canonical 编译与验证由既有入口负责：

```bash
python3 -B tools/build.py --write-json
python3 -B tools/verify_reader.py
```

这些命令需要仓库既有的构建依赖。完整 gate 的执行日志属于本轮整合交接；本目录 receipt 只声明自己的两次脚本调用，不代替整库验收。

## 恢复的研究状态与去重判断

本轮没有仅依据 README 选择课题。恢复范围包含 main 的 programme、map、entries、inquiries、transfers 与相应 receipts，以及两个未合并研究 PR。引用以下固定 commit，而不是将未合并内容当成 main：

| 对象 | 固定版本 | 本轮使用的状态 |
| --- | --- | --- |
| main | [`196880924ae501dd8103bdcb4c03e5c27c7df8ed`](https://github.com/IndelibleVivi/agent-memory-study/tree/196880924ae501dd8103bdcb4c03e5c27c7df8ed) | 本轮新增文件的工作基线 |
| PR #7 | [`759f7151cb40892d34b911191c9b8664a5e97c8d`](https://github.com/IndelibleVivi/agent-memory-study/tree/759f7151cb40892d34b911191c9b8664a5e97c8d) | 恢复时为未合并研究草稿；用于识别表示研究的已有判断 |
| PR #8 | [`b74eff2b1dc5f25019972aaef0e43a291de130fa`](https://github.com/IndelibleVivi/agent-memory-study/tree/b74eff2b1dc5f25019972aaef0e43a291de130fa) | 恢复时为未合并研究工作；不能用 PR 说明中的旧短 SHA 代替当前 head |

| 已有对象与已形成判断 | 本研究真正新增的内容 | 仍然不变的证据边界 |
| --- | --- | --- |
| main 的 [经验复用候选竞争](../experience-reuse-retrieval-study/README.md)：保存、候选、返回与进入 active context 不同；重复候选占位与粗粒度去重可以制造不同失败 | 即使所有支持已暴露，也可能缺少识别其组合的观测信息；增加支持完整性与预算可行性指标 | 原实验是有限 FTS5/BM25 候选竞争；本研究也是构造分析，都不是 agent 收益证明 |
| main 的 [经验到策略文章](../../study/entries/experience-becomes-policy.md) 与 [experience-to-capability inquiry](../../study/inquiries/experience-to-capability.json)：保存经验尚不等于形成能力，适用条件与目标侧检查不能省略 | 经验条目的单独收益可能为零，整包却必要；提供移除条件、替代支持与交互阶数的后续研究对象 | 不把参数更新、保留经验或抽象规则自动当作可迁移能力；本轮未运行经验学习模型 |
| main 的更正、学习和 Memora 相关研究已讨论状态变化与使用边界 | 将选择器能看到的信息与效用结构单独固定，避免把组合问题统称为 memory update | 不重做既有更正/分类器/系统 receipts；不把新有限结果归给那些系统 |
| PR #7 的 [task-relative-sufficiency](https://github.com/IndelibleVivi/agent-memory-study/blob/759f7151cb40892d34b911191c9b8664a5e97c8d/research/task-relative-sufficiency/README.md)：表示可区分哪些历史、对哪些未来问题足够；pairwise 可行不等于全体共同可行 | 改为固定候选后的集合效用接口；所有一、二阶效用相同仍可有不同三阶支持 | 两者都为作者构造的有限对象；本轮不宣称新发现“任务相对充分性” |
| PR #8 的 [representation-use-study](https://github.com/IndelibleVivi/agent-memory-study/blob/b74eff2b1dc5f25019972aaef0e43a291de130fa/research/representation-use-study/README.md)：source-visible、answer-sufficient、实际使用与回答正确必须分开；总请求预算与 receipts 已执行 | 显式允许多个替代充分集合，分开 nominal recall 与 support-family completion，并限定低阶选择接口 | PR #8 使用 scripted/oracle apparatus；其大量配置不是模型能力或独立任务证据。本文不重做它的表示比较 |
| PR #8 的 [revision-propagation-study](https://github.com/IndelibleVivi/agent-memory-study/blob/b74eff2b1dc5f25019972aaef0e43a291de130fa/research/revision-propagation-study/README.md)：修订跨 canonical/index/summary/delivery/action/write 传播；写回可重新引入旧状态 | 本文补充同一时点的支持组合研究，不将时序传播错误归约为排名错误 | 不把 hash receipt 当作授权、因果使用或物理删除证明；未扩张其执行范围 |

本目录与 [侧信息研究](../memory-side-information-study/README.md) 共享“固定条件下解释记忆价值”的问题背景，但研究对象不同：前者问哪些集合关系可被选择器识别，后者问读者已有信息如何改变渠道比较。它们不能算作同一经验结果的两次独立验证。

## 合并到 main 与 PR #8 的区别

本目录与 `study/entries/memory-evidence-complementarity.{md,json}` 是新增路径，可独立加入两条基线。导航、旧 inquiry、旧文章和统一验证入口则必须语义合并。尤其不能把 main 版本的 `study/map.json`、`study/catalog.json` 或生成物覆盖到 PR #8，以免丢掉后者已有研究入口与内容。

若先合并本轮内容到 main，再合并 PR #8，保留两侧全部 entry IDs 和 inquiry 引用，重新运行 canonical build；不要手工拼接 `data/materials.json` 或 `assets/materials-data.js`。本研究不需要修改 schema、RDF source inventory 或历史实验结果。

## 仍开放的问题

1. 真实经验复用中有多少失败来自低阶信息不足，而不是语义已经可见但没有被利用？
2. 能否用少量自适应集合查询发现高阶支持？应同时计入查询成本与最终上下文成本。
3. 支持的有效性依赖时间、条件或更正时，如何维护多个替代路径，而不误把所有历史支持当成同时有效？
4. 当读者或技能控制器变化时，支持标签哪些可迁移、哪些必须重新标定？

这些是后续研究入口，不是本次有限枚举已经回答的问题。
