# AMS · 2026-11 研究接续与复现交接

2026-11-13 · Cove · AI-assisted research

本轮的完整论述由两篇 canonical 文章承担：[经验留下什么：事前价值、学习与保持沉默](../study/entries/experience-value-and-silence.md)与[历史怎样留下继续更新的能力](../study/entries/history-and-update-sufficiency.md)。本文记录研究基线、知识变化、来源版本、执行边界和可继续的技术工作。它不是另一个内容真源；数值与实验方法以各研究目录为准。

## 1. 仓库实际走到了哪里

研究开始时核对了公开 `main`、README、AGENTS、programme、方向、来源札记、持续问题、文章与 research 实现。只读 main 会遗漏已经完成但尚未合并的研究：

| 研究起点 | 本轮核对的 commit | 对本轮的意义 |
| --- | --- | --- |
| `main` | `196880924ae501dd8103bdcb4c03e5c27c7df8ed` | 已部署研究体的基线与原学习器 |
| `next/ams`，PR #9 | `a618ecde843774442773577e318b776f9c63d417` | 含未来问题与有限充分性论述、较新的阅读／本地系统组织 |
| `research/executable-memory-experiments`，PR #8 | `d610c184040565267f6048186d3ffd17cae4f750` | 含 11 月 5–7 日侧信息、互补证据、状态配对和真实 writer/reader 的最新研究 |

本轮分支 `research/experience-value-renewal` 从第三条起步。这样直接继承最近的研究结果，并避免把前端迁移与本轮论证修改混成一次合并。三个起点都没有改变原 `decision-learning-study/study.py`。未来问题文章在另一条分支，理论正文引用其固定 GitHub 版本，不假装它已存在于当前 baseline。

向 `next/ams` 接入时，应迁移本文列出的 canonical 内容与研究目录，并按该分支自己的 compiler 重新生成。它已有 Work/Revision/Note 的 source-corpus 合同，不能用本分支的 generated payload 覆盖它。本轮没有改写 source inventory，也没有将全文 PDF 纳入仓库。

## 2. 哪些知识是旧积累，哪些是本轮新增

| 对象 | 原有知识 | 本轮实际推进 | 仍不能推出 |
| --- | --- | --- | --- |
| 条件效用 | reader 侧信息可反转用途次序；正文和选择渠道可分别传信息 | 复算外部真实输出；分开曝光效应、事前保留、机会结构与实际替代成本 | 一条跨任务、跨 reader 的永久用途分数 |
| 学习器 | 旧 288 个测试向量在训练支持内；纠正有保留损伤 | 1024 向量干预找到 verified 捷径；案例顺序补入未识别的标签优先级 | 现实发生率；自然语言泛化；840 个类别分歧都是行动失败 |
| 历史压缩 | 有限问题族下的全类可接受答案交集；后处理不能恢复已丢区别 | 增加共同续串与递归可更新性；精确概率见证；增长状态与预测过细的双向反例 | 开放个人记忆的通用最小状态或容量公式 |
| 自然语言 | 真实 writer/reader 已暴露选择题泄漏，并做去线索任务 | 把该历史结果纳入本轮基线，避免用结构化实验覆盖它 | 本轮新增了 LLM 行动实验 |
| 持续学习 | 案例、规则、参数、guard 与来源影响分别检查 | 对齐新训练工作的反馈／信用分配，区分连续任务与能力迁移 | 单次成功证明长期学习；judge 使用痕迹等于因果贡献 |
| 研究论点 | 继承关系追踪来源、载体、取用和改变 | 在核心段落增加未来任务、事件延续、损失与更新要求 | 继承关系本身就能决定最优压缩或保留 |

最明确的分歧是研究次序。原学习文章主要把下一步放在“从正确字段走向原始文本”。本轮证明在字段已经正确时，训练支持与 tie-break 仍能制造错误的规则。因此先补充机制层的干预与正负组合留出，再研究语言识别，能避免把两种错误压成同一个 NLP 分数。

## 3. 来源、版本与实际读到哪里

下表记录 primary sources。它不将检索到标题等同于精读，也不将论文作者结果等同于 AMS 复现。除特别列出的归档复算，未重跑上游训练或 benchmark。

| 来源 | 固定版本／阅读范围 | 本轮使用方式与边界 |
| --- | --- | --- |
| [What Is This Memory Useful For?](https://arxiv.org/html/2611.03930v1) | 2611.03930v1；主方法、结果、screen、writer blindness、S3/S7、长度与公开复现附录 | 正式执行官方 headline/fixed-context 脚本；二次分析已保存输出，执行与输入身份在研究包 |
| [Rate-Limited Filtering](https://arxiv.org/html/2611.02361v1) | 2611.02361v1；递归规则、parser 模型、Bayes 与 remapping、reader 成本、理论附录 | 完成独立推导与精确见证；未取得文中提及的作者 theory 源码，不声称代码复现 |
| [Memory-Centric Continual Learning](https://arxiv.org/html/2610.29357v1) | 2610.29357v1；正文，§§3–4、Eq.4.2、Table3及实验解释 | 核对最优 frontier、经验／容量／读写预算的定义；scaling exponents 未被本轮估计 |
| [RoutePrism](https://arxiv.org/pdf/2609.34160v1) | 2609.34160v1，55页PDF；正文关键方法、干预表、局限及选读附录 | 读取原 PDF 及方法限定；具体章节与边界见 utility 包的 source-notes；未运行上游 |
| [异构提供者 MemAgent](https://arxiv.org/html/2609.32521v1) | 2609.32521v1；§4、Eq.2、§5、A.2–A.4、B.2 | 区分可训练 reward 与因果归因，保留经验复用和留出划分；未运行训练 |
| [UMA](https://aclanthology.org/2026.emnlp-main.1299.pdf) | EMNLP 2026 出版PDF，25页；架构、嵌套采样、reward、结果消融、局限与raw工具 | 使用 session 信用分配和原文通道的机制；未执行作者源码 |
| [MemoryArena](https://arxiv.org/html/2602.16313v2) | 2602.16313v2，2026-09-17；主文、B/C，官方源码 `6cd9de14b71915e39ac742a20dc33785e14b6aab` | 只读任务／feedback／memory 生命周期与评价实现；并未复现 ICML 分数 |
| [Learning to remember 综述](https://link.springer.com/article/10.1007/s44336-026-00044-1) | Springer，2026-11-09，Vicinagearth 3:15；框架、演化／评价和相关引文 | 用作来源发现与同名消歧；其分类不作为独立实验证据或新的 AMS 架构 |
| [Latent learning](https://arxiv.org/html/2509.16189v3) | 2509.16189v3，2025-12-23；§§4–6，oracle retrieval与ICL消融 | 扩展到非目标经验的未来使用；OpenReview出版PDF未完成读取，论文结论按此 arXiv 版本 |
| [When to Remember, When to Abstain](https://arxiv.org/pdf/2610.07100v1) | 2610.07100v1，7页全文；A–E rubric、coverage、calibration与跨judge | 说明来源支持与未来用途分离；校准阈值推导为 AMS 分析，无新 judge 或人类实验 |

原始理论的阅读与公式定位由[理论正文](../study/entries/history-and-update-sufficiency.md)及其[externalReadings](../study/entries/history-and-update-sufficiency.json)维护，包括 PSR、causal states、输入输出过程和 predictive rate–distortion。Nerode 原始扫描件未成功取得，不冒称读完原始证明；右同余论证在正文独立推导。

两份通过公开 PDF 读取、未再分发的内容身份：

```text
RoutePrism v1 PDF:
b054634ad1ca82fcbdd0852643364e287aee6889c269e42a035791971f057f82
When to Remember, When to Abstain v1 PDF:
8aef5b85ff566847651b9819aaae10f167f8fc8c7cafc01c1460ea6d4063da01
```

### 几个会改变解释的阅读细节

**构建顺序与事件时间。** RoutePrism 的对象是保持源内容和时间戳的处理路径变化。一个有意义的“先取消、后重新预约”事件序列不能随意交换再要求答案不变。后续在 AMS 使用此方法时，必须先定义保持任务真值的允许排列。源成员变化、最终编译上下文变化与随机 reader 的回答变化也各有可能，不能只数单次回答不同。

**写入的支持性。** Abstain 论文的 support rubric 允许多信号支持的推论，不仅是逐字蕴含；golden-facts 未用于 coverage，覆盖事实每次由 judge 生成，过滤后的 coverage 还需 lexical attribution。不同类别使用不同 extractor。因而这项研究给出局部类别策略的证据，不能证明 values 在所有模型或用户上天然难以保存，更不能把支持率等同于真实人格准确度。其 100 个交叉验证 folds 反复使用同一批人设，不是 100 批独立样本。

**可达到边界与实际算法。** MCCL 的最优 frontier 在固定模型、任务分布、经验生成过程与政策族中定义。只要新预算允许保留旧政策，最优错误不会增大；这个集合包含关系并不识别任何幂律指数。本文因此保留它为可检验假说。实际系统的非单调曲线可以反映取用／维护失败，不能直接反驳理想 frontier，也不能借 frontier 的单调性替实际系统作保证。

**行动 benchmark 的反馈。** 固定 MemoryArena 源码中，`run_math.py` 的 reward 配置与实际 memory-entry 内容需要一起核对；`run_travel.py` 将 judgement 写入 observation，并给无记忆分支累积反馈。`memory/server.py` 的 initialize 创建相应对象，持久 provider 是否清理还需要各自后端审计。`formal_reasoning_env/eval.py` 分开最终子任务成功与中间进度。以上是明确的只读定位，不声称已经证实泄漏、污染或计分错误。

## 4. 已执行研究及可复现路径

### A. 原学习器的新支持审计

所有输入都是由原 feature 函数接受的原创有限构造；共 1024 个合法向量，没有真实用户样本。runner 导入原训练与评价实现，没有复制一个新的学习器。历史 fixtures、parameters 和 `results.json` 保持不变。

```bash
python3 -B research/decision-learning-study/study.py --check
python3 -B research/decision-learning-study/support_audit.py --repo . --check
python3 -B -m unittest discover -s research/decision-learning-study -p 'test_*.py'
```

新增[协议](../research/decision-learning-study/support-audit-protocol.md)声明：全域枚举后才增加字段消融与顺序控制，未追认预注册。完整 `support-results.json` 绑定 runner、原实现与 fixtures 的 hash，并保留逐向量 gold/prediction、配对与支持统计。类别变化与 selection 变化分别报告。

### B. 精确递归状态见证

```bash
python3 -B research/recursive-sufficiency-study/study.py --check
```

runner 的实际入口与结果合同以该目录 README 为准。有限输入、分数运算和 source digest 可复跑；证明的无限时域部分在正文逐步给出，有限枚举只核对具体见证，不以有限测试冒充无限证明。这里不使用语言模型、神经训练或模拟现实发生率。

### C. 官方 Utility 输出复算

```bash
python3 -B research/task-conditioned-utility-study/check_saved.py --check
```

该入口只校验公开 compact 结果、代数约束和保存身份，不能从 compact summary 重建未随仓库发布的原始行或 bootstrap。完整重分析按[README](../research/task-conditioned-utility-study/README.md)获取固定版本输入后运行官方脚本和独立 `reanalyze.py`。输入散列不符时失败；不自动换最新版，也不发起推理请求。

官方仓库固定为 `386ac65a8b5fc46414abdd2755375f2a52d4d3b8`，HF follow-up 固定为 `332cd047e9093a948606c4251bf5b294b0664762`。公开包保存官方日志、独立数值、完整推导和图。原始模型文本与第三方源码 clone 不进入 AMS。

固定源码与内容地址 prompt versions 支持任务盲写的设计；fixed-context 归档的 2,216 rows 之 inference `code_sha` 全为 unknown。因此，该版本固定认证的是本轮使用的分析代码和核对的设计，不能独立认证每一次历史推理调用都执行了这一 commit。

加性诊断只检验归档 cell 值能否精确写成 `a_memory+b_task`。二部图偶环交替和的非零见证否定这个表示，却没有识别语义 memory×task 因果交互；位置变化和二元结果机会结构仍是解释。70,638 个重叠四环不能作为独立实验数。该数学附节保留为可复核的小结果，不担当本轮主要经验结论。

## 5. 可以直接继续的研究协议

协议一随后按下述边界执行了固定切分的离线诊断；协议二、三仍未执行。它们各自回答不同问题，无须同时启动。

### 协议一：先识别规则，再测试语言识别

**问题。** 学习器能否在打破 verified 共现之后，同时保留新的正向使用机会与拒绝过期候选的能力？

**输入与划分。** 继续使用原 feature 函数。先冻结 gold 规则、冲突优先级和成本；按特征组合划分，不按新名称或文本表面划分。至少留出一组 useful 向量及与它相邻的 expired/missing-precondition/harmful 向量。对 v1 的 irrelevant verified/sensitive 做配对；v2 中这些字段有作用，需另定义适用不变性。不要把全体未见向量都放在负类。

**当前域的限制。** v1 的四个 useful 向量具有完全相同的前八位任务相关条件，仅 verified/sensitive 两位不同。留出十维正例只能测试 nuisance 取值及支持迁移，不能证明学会新的有效条件组合。若把整个 nuisance 等价轨道留出，训练就没有正例；真正的新正向核心需要另行声明任务合同。原 depth=4 树也不能完整表达八个必要条件的合取：正例叶最多确认四位，总有未确认位可翻成同叶的负例。补充反例不能自动解除这个容量限制。

**已执行的接续。** [固定切分诊断](../research/decision-learning-study/transfer-study.md)保持十个特征和原学习预算，以 sensitive=0 的原训练行拟合，以 sensitive=1 的全部512个向量评价；其中包含两个未见正例及相邻负例。补充32条反馈的两臂保持条数与类别直方图一致，比较原标签重复与规则选取的反例。协议在本次拟合前固定，但既有全域审计已公开全部向量的结果，因此不是独立盲测或预注册确认。v2 分组仅检查冻结 v1 政策面对新规则的失配，不冒充已经学会新规则。

小头的类别正确从171/512升至312/512，两个正例均召回，错误选入仍为4条harmful加15条其它无用候选；verified翻转仍使19/256对改变选择。最近案例和树也未同时满足全正例召回、零错误注入。后续不能把分类解释改善当成选择规则已经修好；同数量、同类别控制只固定这些监督计数，不固定信息覆盖或逐向量权重。运行 `python3 -B research/decision-learning-study/transfer.py --check` 重算独立结果；该入口已接统一验证。

**比较。** 原案例、原规则学习器、原小头，外加显式 oracle rule 和恒定拒绝。预算与选材在拟合前固定，不从测试结果挑选参数或追加材料；确定性重放与修复偏离协议的实现须单独说明。若增加 counterexamples，要设 equal-count 标签数据控制，并保留增加前模型。

**验收。** 分开 action utility 与四类解释标签；报告 positive recall、false injection、verified invariance、冲突组合和纠正后 preserved/boundary。顺序的全局最好／最差需要证明或精确求界；本次逐案例独立 tie envelope 与两种实际全局顺序分列，不假装各案例的极值可由同一顺序同时达到。任何常数拒绝可取得的高分都不能作为学习成功；标签不一致但动作一致也不能全计为行动损害。

**再接语言。** 冻结通过结构探针的决策器，比较 gold features、从文本抽取的 features 和端到端方法。若只有文本抽取版退化，才有证据将差距定位到识别；如果 gold-feature 版已失败，应继续解决决策规则。

### 协议二：在 reader 与任务变化下学习何时沉默

**问题。** 一次调用门控学到的是稳定的净增益条件，还是固定 reader／测试分布的机会结构？

**材料。** 从原创合成或明确许可的公开经历形成 task-blind memories；冻结 writer prompt、原始来源、memory IDs 与内容 hash。未来任务由独立流程生成，先冻结其可回答性、当前权威来源、范围与目标。负任务必须包含真正应该沉默的情况；正任务必须依赖过去且无明显问题线索。

**配对干预。** 同一写入前状态、同一当前任务分别运行 no-memory、真实记忆、同位置等长无关材料、当前可替代证据。位置在任务内配对随机化；完整实际 messages、工具返回、预算、终止与技术失败分别保存。实际 agent 互动可以从共同 checkpoint 分叉；不能要求干预后每一步仍走同一轨迹。

对随机 reader，预先固定独立重复与各臂的配对方案。平均增量使用全部重复估计，救回率和破坏率注明属于哪种配对；一次错→对不直接成为稳定的有益标签。若共享随机种子可用，说明实际是否达成共同随机性；不把温度零当作绝对确定的保证。

**学习条件。** gate 只看部署可见状态。比较全调用、全沉默、成功频次监督、配对增量监督和可见条件规则。若用离线选择日志，记录可用行动、实际行动与行为政策概率；没有 overlap 的行动不能由逆概率加权恢复。模型自报置信度单独校准，不借用 gold。

先按 source history、memory ID 与生成模板族划分训练、阈值校准和测试；共享 writer 输出及其改写只能在同一侧。测试前冻结 gate、阈值、成本与要报告的失效子群，测试反馈不得回流。换 reader 的共同测试用于迁移评价，不能反向调整门控。若任务生成使用LLM，还需保存生成请求与gold审阅，检查题面是否已泄露答案。

**泛化。** 固定门控，分别只换 reader、只换任务分布、再同时改变；报告共同任务和新增任务。至少分别统计 `P(Y0=1)`、救回率、破坏率、弃答、可调用机会数、token/latency/cost 和按预先成本计算的净收益。Bootstrap 按独立历史或任务族聚类，重复请求不扩大独立 n。

**验收。** 预先给出可接受的帮助遗漏与错误注入范围。与最强简单基线比较，CI 和失效子群同时报告；无收益、全沉默胜出、只在原 reader 成立都属于有效研究结果。技术失败不能记成语义错误，也不能从分母无声删除。

**长期保留另开干预。** 若要声称 storage policy 改善，必须让保留／丢弃改变后续真实库内容并经历相同外生任务计划，记录竞争、被挤出的条目、维护成本与回源。仅训练调用门不完成这一主张。

### 协议三：把更新充分性从数学带到语义

**问题。** 模型压缩是否丢失当前无收益、但会改变未来更新的证据？

**材料。** 先构造两类共享当前答案的历史，区别在支持强度或规则不确定性；独立冻结一个共同事件续串，使正确更新之后的决定分开。同时加入预测状态不同、但在允许续串内动作始终相同的正面合并控制。

**比较。** 完整历史、仅当前答案、紧凑可更新状态、同预算普通摘要、可回源策略。writer 不看指定续串或后续题；任务族和容许续串必须在评价定义中公开。另设可识别模板与新语义表述分层，避免把 oracle 状态构建伪装成语言理解。

**验收。** 先报告当前答案无差异，再报告新证据之后的条件行动差异、弃答、误合并和回源成本。若 compact state 由研究者手填，主张仅限 reader 能消费它；若模型自行生成，必须保存实际输出并单列其缺失。有限故事任务不代表开放个人记忆；用户目标漂移和语义冲突需要另行定义，不能默认一个固定自动机已覆盖它们。

## 6. 集成与验证合同

本轮沿用 `study/` canonical、`externalReadings`、既有 inquiry 和 programme，没有新增分类体系、来源库或交互控件。正文修订发生在旧论证真正受影响的段落，历史结果单独保留。`tools/author.py inspect/impact` 用于查身份与显式引用；它不认证科学结论。

```bash
python3 -m pip install -r tools/content-requirements.txt
python3 -B tools/build.py --write-json
python3 -B tools/verify_reader.py
```

统一入口新增支持审计与递归见证的重算，以及 Utility compact receipt 检查。后者不是论文重跑。浏览器与 static 检查沿既有工具执行，页面没有新增模型调用路径。不要手工复制 `data/materials.json` 或 `assets/materials-data.js` 到另一个研究分支，必须在目标 canonical 上重建。

初轮 Chat 执行已通过 canonical 构建、`tools/verify_reader.py` 全入口、两篇文章的 public collection 导出，以及 staged diff 格式检查。统一入口重算支持审计与递归见证，并检查 Utility 保存结果；它没有重跑原始模型推理。该次运行环境为 Python 3.12.14、Node 24.22.1。完整 PR 工作流另在其固定的 Python 3.13、Node 22 和 Chromium 环境验收。

新增两个研究对象暴露原地图的固定数量断言与网格裁切。对象数量现在从 canonical 集合计算；spread 按网格及环带外缘等比适配，关系视图缩小 5% 以避开临界倾角裁切。投影、拾取与交互结构未改，原视口边界断言保留，增加增长与临界倾角回归。这是内容集成所需的小修复。

初轮 Chat 环境的 Chromium 启动被 socket 限制阻止（`Operation not permitted`），当时未声称本地浏览器／静态站点通过。后续本地 Codex 接续已实际通过 canonical 构建、统一验证（362 项 Python tests、105 项 Node tests）、202 项真实 HTTP browser checks（零 skip），以及静态构建和159项静态检查。静态产物有53个阅读页、404页与380个公开assets；新诊断报告及结果文件已核对进入产物。原学习／纠正、支持审计源码与 receipts 保持不变；新增诊断完整重算，未新增 LLM/API 调用。

远端完整工作流的结果以对应 commit 的 Reading Room validation 为准。研究状态与发布状态分开：分支、commit、draft PR 的建立不表示已合入 main，也不表示 GitHub Pages 已部署。

## 7. 真正需要研究者决定的方向

已有支持审计与理论见证足以先做上述低成本机制研究，无须先选择一个通用 Agent Memory 产品架构。更长线的决定是主评价对象：持续完成既定任务，还是在任务和自我理解改变时仍能重新解释经历。前者可以接受较窄的充分状态，后者必须给来源可回访、未知规律与目标变化留下空间。

这不是现在就能用一条指标解决的取舍。本轮更倾向于把**可更新性**设为下一条主线：它能同时检验有限状态论证的边界、旧学习器的真实迁移、压缩的未来损失与沉默的适用范围。原有检索、修订、参数与 cache 研究继续保持独立，不必为这项选择改造全部 AMS。
