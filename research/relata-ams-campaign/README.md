# Relata × AMS：下一轮可执行记忆研究准备包

**状态：研究准备与操作地图；未执行新的跨库 pilot、provider、模型、真人或账号操作。**

本目录是 Agent Memory Study（AMS）为跨 Relata × AMS 下一研究轮维护的公开研究准备包。它只拥有 AMS 侧的 estimand、材料交接条件、原生操作边界和验收要求，不复制 Relata 的共享 campaign 正文，也不把多个研究问题压成一个统一 runner、ontology 或总分。

共享方向由 Relata 维护：

<https://github.com/IndelibleVivi/Relata/blob/main/research/relata-ams-campaign.md>

配套文件：

- [future-author-handoff.md](future-author-handoff.md)：未来作者可据以冻结 P1 policy/writer、材料、访问顺序、family lineage、任务分布与终点。
- [native-operations.md](native-operations.md)：基于当前 AMS tracked 源码的操作地图、证据等级和未来系统实核清单。

## English summary

This package prepares, but does not run, a two-repository research campaign. It assigns separate estimands to the captured Relata-to-reader audit (P0), unknown future use (P1), correction propagation (P2), accepted-goal change under method failure (P3), a local-memory effect against an untreated checkpoint (P4a), task-start allocation policies (P4b), relationship-repair wording and human burden (P5), and probe/reflection writeback contamination (P6). P4 contains two distinct estimands: a local exposure effect and a task-start policy effect.

The package preserves evidence status instead of flattening every result into either a completed experiment or a mere proposal. Real SQLite FTS5 retrieval, the fitted small classifier, the saved C2C cache intervention, and the single-document KV native-cache validation remain distinct from AMS scripted controls. The P1 handoff freezes access, family lineage, task distribution, five reaccess states, budgets, and primary outcomes. The native-operations document records exactly what current tracked code performs and what must be verified in Relata, Hindsight, or another native system before any claim about dense retrieval, natural-language summaries, automatic freshness, or production writeback.

## 共同边界

- Relata 的共享 campaign 是方向与跨库接口的导航；AMS 不复制其全文。AMS 的 P0–P6 各自保留问题、样本单位、对照和证据责任。
- 本目录没有新增 provider、模型、真人或 raw 实验执行。Relata 的具名 P0 reader-only 后续有独立执行边界和私有记录；文中 AMS 命令是复验入口。
- 本轮边界：不新增 runner；不新增 adapter；不新增 JSON schema；不新增统一 ontology。已有 AMS runner、fixture 和 receipt 只作为理解与复用入口；跨库实现必须由未来作者在明确授权后完成并实核。
- 任务行、问题行、翻译、措辞、checkpoint、分支和重复任务不等于独立 family。P1 约 24 个新 family 是 pilot 起点，不是统计功效承诺。
- structured dictionary、固定记录、关键词分数、小型分类器参数、KV cache、embedding 向量和自然语言 summary 是不同对象。不能借“都是 memory representation”把它们互相替代。
- 当前测量对象不是人的理解、满意度或长期能力。只有明确设计和获准的真人研究才能报告人的下游任务与负担。

## 工作包地图

| 工作包 | 独立问题 | 主要单位 | 现有可复用入口 | 尚需的新证据 |
| --- | --- | --- | --- | --- |
| P0 | 已捕获的 Mem0→reader 字段是否被正确理解、保存和呈现？ | 一个 family；capture 为相关配对单位 | Relata 已捕获材料与离线字段审计 | 三臂固定 capture 的字段、来源、版本与 reading 绑定 |
| P1 | 未来用途未知时，哪些 memory 表示和取回途径支持当前任务？ | event family / lineage | AMS 表示执行器、真实 FTS5 诊断 | 新 family、五类 reaccess、真实检索与 reader 条件 |
| P2 | 更正怎样跨层传播、失效、重读或回流？ | event family × longitudinal episode | AMS revision-propagation 状态机 | 自然语言 revision、原生层操作与真实 writeback |
| P3 | 目标保持／改变 × 手段有效／失效时，行动怎样承接历史目标？ | accepted-goal transition | P2 的 revision 时间线与行动记录思路 | 目标接受、手段状态、行动、副作用与停止理由 |
| P4a | 在相同 checkpoint 上，局部 memory 处理是否改变下一任务？ | checkpoint / task family | P2 共同 precheckpoint；P1 reader outcome | 未处理参照、局部处理与匹配时间表 |
| P4b | 在 task start 分配 early / late / difficulty / never，策略差异是什么？ | task-start assignment | P4a 的未处理参照和 outcome vocabulary | 预先固定的分配器、分层与负担计数 |
| P5 | 关系修复正确性是否与熟悉表达混淆？人的后续任务和负担是否分别改变？ | relationship case / person | Relata captured repair cases | 2×2 材料、获准真人任务与独立负担测量 |
| P6 | probe 或 reflection 是否通过 writeback 污染后续状态？ | probe/reflection event × later task | P2 的 writeback 对照与旧影响定义 | 只读 probe、会写的 reflection、来源 lineage |

## P0：capture 与字段审计

**问题。** Relata 已捕获的 Mem0 输出进入 reader 时，原始字段、派生字段、缺失字段和 reader 消费字段是否被分清？固定 capture 的三种表示是否能被同一 reader 稳定读取，而不把展示便利误当成 memory 原生结构？

**AMS 侧 estimand。** 固定同一 captured artifact，只改变 reader 可见的三臂表示，估计字段保真、可追溯性、无关确定断言和任务完成差异。三臂名称与顺序必须来自 incoming capture manifest；本准备包不猜测其实现命名。

**边界。** P0 是字段与表示审计，不重新调用 Mem0，不证明 Relata 原生写回、后台更新或未来用途。捕获时的系统版本、capture 时间、字段 digest 和 reader adapter 身份必须绑定。若三臂只是同一 capture 的不同渲染，不能称为三套记忆策略或三个独立样本。

**依赖。** P0提供可复用的暴露诊断方法；实际captures和响应保持私有。P1/P2可独立准备材料与操作地图，不以P0完成为前置；它不替P1决定family，也不替P2决定correction truth。

## P1：未知未来用途

**问题。** 在作者尚不知道未来题目、但知道声明中的用途分布时，raw、关键词、dense、自动 summary 或 summary 加 iterative revisit 等表示/取回策略，能不能让必要证据到达 reader 并支持任务完成？

**AMS 侧 estimand。** 在固定 source、writer、policy、family lineage 和实际可见 access 的条件下，比较两种 history 状态（fixed / updated）× 两种声明任务集（current / expanded）以及预声明 retrieval 条件。主要终点是任务完成，以及“没有证据却给出确定答案”的 unsupported definite answer 计数。两套 common 问题保持配对；expanded 新增题单列，不能把问题分布改变称为同一处理的纯效应。

**必须单列的 reaccess 状态。** `current`、`missing`、`denied`、`known-stale`、`unknown-stale` 是五种不同状态。missing 不是 denied，denied 不是“没有相关记忆”，known-stale 也不是 unknown-stale。每种状态都要有独立可见证据和错误处理；不能把它们合成一个 insufficient 标签。

**取回与预算。** 候选池必须大于 top-k 返回数，并加入 scope distractor 与 near-duplicate distractor，使“没有进入候选”“进入候选但未选中”“选中但未送达”和“送达但未正确使用”可分别观察。equal reader budget 限制实际交给读者的材料；equal pipeline cost 限制检索、排序、summary、重算与 reader 的总计算/调用预算。两者是不同的匹配条件，不能只匹配其中一项后宣称公平。

**开发材料。** 现有 P1 的 8 个 event families、64 cases、320 question rows 是 development/diagnostic 材料，不是 heldout。见过固定summary删除规则的作者，不能再被算作独立未来出题者。约 24 个新 family 是 pilot 起点，不是 power calculation。

**依赖。** P1 可复用 AMS 现有 scripted reader、FTS5 诊断和 byte-budget 机制，但真实 BM25 结果只来自独立 key-only 实验，dense/auto summary 尚未实现。详见 [future-author-handoff.md](future-author-handoff.md)。

## P2：更正传播

**问题。** 一条更正进入 source/canonical 后，index、summary、delivered context、action 和 next memory write 分别在何时、以什么可见状态改变？

**AMS 侧 estimand。** 在共同 pre-revision checkpoint 和相同外生 task timeline 上，比较 append-latest、显式版本、依赖重算、source reread 等操作，在同步延迟、单层 stale、单层修复、retention 和 writeback on/off 条件下的 current action 与合法历史答案。

**解释单位。** changed、preserved 与 preserved 内的 boundary 不能相加；historical 与 changed/preserved 可以重叠，也不相加。持续错误与修好后再现的旧影响分列。重现场景要求同 query identity、同 expected-answer phase 的“先错→至少一次修好→再错”，且后错绑定修订前合法答案与 source/support；任意新错误不算旧影响。

**时间。** valid time、observed time、commit/accept time、exposure time 分别记录。revision 已提交不等于 reader 已看见；来源当时是否可见、后来是否被允许再次读取，也要有 access 证据。

**负控制。** 无覆盖权的新消息、另一 scope 的消息、仍合法的历史查询都应保持负控制。若它们被错误改变，更新扩散不能因为主更正项答对而被接受。

**writeback 与自然 stale。** writeback on/off 是预先安排的压力对照，关闭写回后的分支不能与开启分支在下一次 write 之后重新匹配为同一输入。后续输出是 mediator，不是配平变量。自然 stale delivery 与 writeback 造成的旧影响要分列；preset revisit 不是自然发生率。

**待实核。** manual/automatic 与 single/batch freshness 必须留给 pinned Hindsight 或目标系统的原生操作验证；AMS 当前没有这些 runtime 结果。结构化版本字典或固定 summary 不能称为 dense index 或自然语言 summary。

**依赖。** P2 向 P3、P4a 与 P6 提供时间线、checkpoint 和旧影响测量的复用语义，但三个下游问题各有独立 estimand，不能默认共享同一因果结论。

## P3：历史目标约束下的行动

固定当前请求和工具状态，正交安排目标保持／改变 × 旧手段有效／失效；另含提议未接受、明确否决、引用他人计划。平衡来源、时间与长度，普通条件不暴露 `accepted=true`、gold goal 或答案化文件名。

比较 raw retrieval、plan summary、忠实来源和自动 intent index；错误但非空标签与完全无匹配标签分别测试。主要终点为任务完成和约束违背。区分实际输入是否充分、工具能否取得证据、行动是否满足完整历史；真歧义允许多个合法行动。目标复述只在独立fork上测，不能代替行动或证明内部理解。正确复述却行动错误、标签屏蔽关键来源、只增加询问却降低完成率，都可否定相应主张。

## P4a：未处理 reference policy 下的局部暴露效果

先用未受该记忆处理的统一reference policy生成checkpoint，事前标记困难与非困难；从同一checkpoint随机分配正确记忆、长度近似无关材料、无记忆，再比较单次暴露与持续驻留。估计只针对该reference policy可到达状态。无需把checkpoint限定为修订前状态；一般任务同样适用。

记忆正确性预先核对，区分新信息、冗余信息、范围不符信息；互补条目成组干预。主要终点为任务成功和总成本。操作同时改变多层时只估计整体处理效果。后续writeback是中介，不能重新匹配为相同历史。

## P4b：task-start 策略效果

在任务开始时分配early、fixed-late、difficulty-triggered或never策略，冻结触发信号与观察窗口。所有assigned trajectories进入分母，没触发也属于合法策略结果；不能事后只挑困难轨迹比较，因为困难可能被记忆处理改变。

在线controller只能使用当时允许的信号；gold-aware效用仅作离线诊断。任务成功、违约、总调用、构建／查询／修复成本分别报告。P4a的局部效果不直接回答P4b的整体策略问题。强无记忆控制同样好、触发太晚或成本超过收益，都是有效反例。

## P5：关系修复与人的后续负担

**问题。** Relata 中的关系修复，其正确性与表达熟悉度是否被混淆？正确/不正确的修复与熟悉/不熟悉的表达，在人的后续任务和任务负担上分别产生什么差异？

**研究对照。** 预固定 2×2 材料条件：repair correctness ∈ {correct, incorrect} × expression familiarity ∈ {familiar, unfamiliar}。若修复正确性是作者编写的刺激，测它对人的后续影响，不能把刺激正确率当作新发现；真实系统修复能力需另一项行为研究。熟悉度不能由相似度分数或模型自评代替。人的 downstream task success 与 burden 分开报告，不能把“读起来顺畅”当成“关系已修好”。

**边界。** 本轮没有真人执行、伦理批准或招募。未来触发真人研究前，需要独立授权、材料审查、任务说明、负担测量和停止规则。同一关系、翻译、措辞变体不增加独立 person-case 数。

**独立设计。** Relata owns人与互动研究；vignette回放不等于参与者自己的关系承接。保留明确约定、从未达成约定、确实缺上下文三类，区分重复询问负担和必要澄清。形成性12–16人是材料起点，确认样本需按方差和聚类另定；本轮没有收集人。

## P6：probe/reflection 与 writeback 污染

**问题。** 一次 probe 或 reflection 读取当前 memory 后，是否通过自动写回产生新的派生记忆，再改变后续任务？

**AMS 侧 estimand。** 同一checkpoint分配无probe、检索、反思、自然任务、长度近似sham，与writeback on/off交叉。分别记录active context、持久文本、index/derived、access counts、cache和后台维护；阻断不到的层保留unknown。若 reflection 输出被写回，后续错误需要绑定 reflection 产生的新对象、旧来源和后续 delivery，不能仅凭时间顺序称为污染。

**边界。** 读取本身不能写成持久变化；仅出现新节点也不能证明其影响了行动。必须观察后续任务或明显回流，并保留没有 writeback 的对照。后台 reflection、异步刷新、批量整理与自动保存是否真实存在，必须由目标系统 native check 确认。

**依赖。** 复用 P2 的 writeback、common precheckpoint、exogenous schedule 与旧影响定义；P1 的 reader outcome 可用于表达后续效果，但不能把 probe 当作独立 family。

## 证据状态：不统一降格，也不统一升级

| 证据 | 当前状态 | 本轮不可宣称 |
| --- | --- | --- |
| AMS representation-use | 真实 stdlib 执行，7,680 个 saved forward control requests；scripted/latest/abstain/oracle consumers | 自然语言模型结果、真实 tokens、dense/summary 效果 |
| AMS experience-reuse retrieval | 真实 SQLite FTS5 BM25，4 个原创场景、108 次选择；只索引 key | 已接入 P1、value retrieval、dense/ANN、agent 收益 |
| AMS decision-learning | 真实小型 OVR logistic 与 tree 拟合，结构化标签 | pretrained encoder、自然语言理解、真实效用 |
| AMS C2C retraction | 固定 SmolLM2 的 200 个已保存 forward/cache 干预输出 | C2C benchmark、权重遗忘、长期隐私擦除 |
| AMS KV prefill transfer | 随机闭环与一篇 pretrained target 的 256-token native 磁盘验证 | pretrained 跨模型迁移质量、端到端加速 |
| AMS revision propagation | 真实 deterministic 状态机，2,592 个 scripted/oracle episodes | LLM、真人、自然发生率 |
| Relata P0 capture | Relata拥有既有capture audit与reader-only后续；AMS本目录仅方法交接 | AMS重新验证Mem0、公开raw结果或独立语义calibration |

真实 FTS5、参数拟合、C2C 单次模型干预和 KV native 验证保留各自证据身份。它们不能被 P1/P2 的 scripted 状态机械降格，也不能被借来支持不相关的 memory 主张。

## 版本与发布状态

当前 evidence snapshot 为 `research/executable-memory-experiments` 分支的 `383ac14`。该 commit 不在 `origin/main` 祖先链上；**PR8 内容属于该分支，不应称为 main 已合并或已部署。PR7 是另一项独立工作，同样未合并。**

本目录新增文档不改变既有P1/P2 source identity；文档不是新运行的receipt。

## 验收入口

本准备包不新增 runner。已有 P1/P2 源码未改变时，可复用上一轮已通过的检查：

```bash
python3 -B -m unittest discover -s research/representation-use-study -p 'test_*.py'
python3 -B research/representation-use-study/study.py check-sample
python3 -B -m unittest discover -s research/revision-propagation-study -p 'test_*.py'
python3 -B research/revision-propagation-study/study.py check-sample
git diff --check
```

统一验证沿用项目已有开发环境：

```bash
python3 -B tools/verify_reader.py
```

开发依赖见根README与 `tools/content-requirements.txt`。本目录只新增方法文档，不改变canonical研究文章、网站renderer或已保存的实验结果。没有重跑大矩阵、pretrained inference或人的研究。
