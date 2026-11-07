# MemSkill：技能库、控制器与“最佳状态”的配对问题

- 研究日期：2026-11-05（Asia/Singapore）
- 文档性质：原始论文比较、固定版本源码研究、独立机制推论
- 执行状态：已完成静态源码核查；未训练模型、未执行 provider、未复现论文性能
- 适用项目：AMS；Relata 可引用状态与来源边界，但不把这份共享核查计作独立验证

## 1. 这份研究增加了什么

MemSkill 最值得继续研究的地方，不只是“模型学会使用和改写记忆技能”。固定版本的实现同时演化两种会互相影响的状态：共享技能库，以及选择技能的控制器。实现中的阶段快照保存技能库及其阶段奖励；常规回退恢复技能库，而控制器保持当前状态。因此，被重新组合出的系统并不是产生那次历史奖励的完整历史系统。

这产生一个可以精确提出、又不需要先运行模型才能成立的问题：**“最佳技能库”是相对于哪一个控制器、哪一个任务分布和哪一种评估状态而言的？** 历史上表现最好的库与当前控制器配对，不能仅由历史排名推出仍然最优。这个命题是关于状态和估计对象的推论，尚不是 MemSkill 已发生负迁移或实现存在错误的证据。

它可以为 AMS 已有的经验复用、学习与更正研究增加一个较窄但有辨识力的研究对象：**部分状态回退后的兼容性**。既有的“经验是否已经变成策略”“存储变更与规则变更有何差别”，在这里获得了具体的可核查实现。后续实验可以比较库的主效应、控制器的主效应与二者交互，而不再把性能变化统称为“记忆学习”。

本研究已接入[经验怎样进入规则与参数](../../study/entries/experience-becomes-policy.md)及[经验到能力的问题专题](../../study/inquiries/experience-to-capability.json)，为既有判断增加状态配对条件；没有替换原研究或宣称首次发现负迁移。固定源码通过研究文章的 `externalReadings` 与本目录回执定位，不新增 Zotero 书目。

## 2. 原始资料与证据边界

### 2.1 身份、版本和固定源码

论文为 Haozhen Zhang 等人的 **MemSkill: Learning and Evolving Memory Skills for Self-Evolving Agents**。arXiv v1 发布于 2026-02-02，本文阅读的论文为 **v2，2026-05-24**。

- [arXiv 身份与版本历史](https://arxiv.org/abs/2602.02474)
- [v2 完整 HTML](https://arxiv.org/html/2602.02474v2)
- [官方实现仓库](https://github.com/ViktorAxelsen/MemSkill)
- 固定 commit：`f65b797338033f4f9c34822f1810f9c2747e6022`，提交时间 2026-10-01T15:00:10Z。
- 核查回执：[固定版本与文件摘要回执](memskill-source-receipt.json)，列出下载 URL、字节数和 SHA-256。完整上游源码快照保留为核查工作材料，不纳入本次研究交付。

**版本限制：源码 commit 晚于论文 v2。** 本文说明该 commit 实际呈现的控制流程；不能把这些代码自动认定为论文全部表格的实验版本。脚本中的模型、数据和 API 参数仍有占位值，因此代码存在本身不提供一份完整的论文复现实验配置。

### 2.2 阅读覆盖

论文重点覆盖 §3 的学习与演化机制、§4.3 的分布转移、§4.4 的消融、附录 B.2 的演化与回退、B.3 的分组、B.4 的技能选择，以及附录 C/D 的技能与提示。源码重点覆盖训练、操作库、控制器、执行器、设计器、ALFWorld 数据处理、记忆构建、评估、检查点保存与载入。

这里的“已核查”有三种不同含义：

| 类型 | 本文允许的陈述 | 本文不据此推断的事项 |
|---|---|---|
| 作者实验报告 | 论文在其设定中报告了性能、消融和迁移结果 | 本轮已复现；所有新任务都会获益 |
| 固定版本源码观察 | 指定文件与控制流保存、读取或恢复了哪些状态 | 这些分支在作者每次实验都触发；该行为造成性能损失 |
| 独立机制推论 | 某历史配对的奖励不能直接识别另一个配对的奖励 | 真实效应符号、大小或统计显著性 |

本轮没有取得实际训练轨迹、作者 checkpoint 全集、完整评估缓存及数据生成清单，因此不能据此宣称已经完成数据污染审计或负迁移实验。

## 3. “记忆学习”实际包含哪些状态

把运行状态记为

\[
S=(B,\theta,E,M,D,O,G,Q),
\]

其中，\(B\) 为共享技能库，\(\theta\) 为控制器参数，\(E\) 为记忆执行器，\(M\) 为当前构建出来的具体记忆，\(D\) 为设计器及其分析状态，\(O\) 为优化器状态，\(G\) 为随机状态，\(Q\) 汇集数据采样、缓存与运行配置。这个记号用于定位干预对象，不是建议为 AMS 增加新 schema。

| 状态 | 源码中的对应物 | 改变它会改变什么 | 主要来源 |
|---|---|---|---|
| 共享技能库 \(B\) | `OperationBank`，技能描述、指令及更新类型 | 可供选择的记忆处理动作及其语义 | [operation_bank.py](https://github.com/ViktorAxelsen/MemSkill/blob/f65b797338033f4f9c34822f1810f9c2747e6022/src/operation_bank.py) |
| 控制器 \(\theta\) | `PPOController` 及可训练参数 | 根据会话和当前记忆状态给技能分配选择概率 | [controller.py](https://github.com/ViktorAxelsen/MemSkill/blob/f65b797338033f4f9c34822f1810f9c2747e6022/src/controller.py) |
| 记忆执行器 \(E\) | `LLMExecutor` | 执行被选择的技能，生成具体 JSON 记忆变更 | [executor.py, L33–125](https://github.com/ViktorAxelsen/MemSkill/blob/f65b797338033f4f9c34822f1810f9c2747e6022/src/executor.py#L33-L125) |
| 具体记忆 \(M\) | `MemoryBank` | 当前有哪些事实、经验、约束及文本可被检索 | [memory_bank.py](https://github.com/ViktorAxelsen/MemSkill/blob/f65b797338033f4f9c34822f1810f9c2747e6022/src/memory_bank.py) |
| 设计器 \(D\) | `SkillDesigner` / 交互设计器与失败案例 | 增加或修改共享技能，从而改变后续动作集合 | [designer.py](https://github.com/ViktorAxelsen/MemSkill/blob/f65b797338033f4f9c34822f1810f9c2747e6022/src/designer.py), [interactive_designer.py](https://github.com/ViktorAxelsen/MemSkill/blob/f65b797338033f4f9c34822f1810f9c2747e6022/src/interactive_designer.py) |
| 下游行动模型 | ALFWorld rollout 中消费检索结果的 LLM | 将具体记忆用于行动选择 | [main.py, L838–950](https://github.com/ViktorAxelsen/MemSkill/blob/f65b797338033f4f9c34822f1810f9c2747e6022/main.py#L838-L950) |

“技能库”与“具体记忆”在这里不是同一层。一个技能可以被许多任务重复使用；它执行后写入的某一条记忆则属于那次构建出来的 `MemoryBank`。库变更可能影响多个后续记忆构建过程，不能用删除某条 episodic memory 来完整撤销。

冻结也需要说清对象。检查的训练路径把 Adam 用于 controller 参数；`LLMExecutor` 是被调用的执行组件，未进入这个优化器。文本编码路径中可以看到 `eval()` / `no_grad()` 或 NumPy 编码。这支持“该训练过程直接优化控制器，不通过这一优化器更新执行器或编码器”的描述。它不证明某远程模型别名永远对应相同权重，也不意味着最终行动过程对技能变化不敏感。[controller.py, L678–787](https://github.com/ViktorAxelsen/MemSkill/blob/f65b797338033f4f9c34822f1810f9c2747e6022/src/controller.py#L678-L787)

## 4. 阶段回退与完整检查点是两个不同操作

### 4.1 阶段快照存什么

`EvolutionSnapshot` 包含阶段标识、`operation_bank_dict`、平均奖励、演化结果和分析案例。它没有控制器权重、优化器、具体 MemoryBank 或 RNG 字段。`SnapshotManager` 根据严格更大的奖励更新最佳索引；相同奖励属于没有改进的情况。训练器调用 `add_snapshot` 时传入当前技能库及阶段平均奖励。

- [designer.py：EvolutionSnapshot 与 SnapshotManager，L233 起](https://github.com/ViktorAxelsen/MemSkill/blob/f65b797338033f4f9c34822f1810f9c2747e6022/src/designer.py#L233)
- [trainer.py：阶段评分与 snapshot，L1295–1354](https://github.com/ViktorAxelsen/MemSkill/blob/f65b797338033f4f9c34822f1810f9c2747e6022/src/trainer.py#L1295-L1354)

阶段奖励来自 `self.stage_rewards` 的末段；配置采用最后四分之一，并可使用窗口为 5 的移动平均。它是训练期间积累的任务奖励，不是这个分支中新建的一套独立验证集成绩。其用途是驱动演化与回退的在线控制信号。将它称为“held-out 最优”的证据会改变估计对象。

### 4.2 普通常规回退恢复什么

在非新最佳的普通演化路径中，代码用 `OperationBank.from_dict(...)` 恢复历史最佳库，并重新关联操作编码器。该分支没有加载历史控制器。随后可能使用最佳阶段的分析案例继续设计技能，并保留失败案例池的一部分状态。

- [trainer.py：回退及再次演化，L1388–1435](https://github.com/ViktorAxelsen/MemSkill/blob/f65b797338033f4f9c34822f1810f9c2747e6022/src/trainer.py#L1388-L1435)

因此，这个操作更接近

\[
(B_t,\theta_t) \longmapsto (B_{i^*},\theta_t)
\]

而不是

\[
(B_t,\theta_t) \longmapsto (B_{i^*},\theta_{i^*}).
\]

这个区分是可核查的实现事实。设计者完全可能希望保留训练进步而只撤销技能变更；是否合理取决于兼容性和实际结果，不能把“部分恢复”直接等同于缺陷。

其中 `θ_{i*}` 只能作为一个确实保存的匹配历史 checkpoint 的记号。阶段平均奖励可能跨 controller 更新，并不由某个固定 `θ_{i*}` 独自产生；阶段 bank snapshot 本身也不能恢复这个 controller。历史训练阶段、具体保存状态和重新评估后的静态配对需要分别记录。

### 4.3 提前停止分支先退出，最后保存当前状态

当演化次数或没有改进的次数达到停止条件时，早停分支在执行普通库回退之前 `break`。因此，早停并不自动走上述 `OperationBank.from_dict` 分支。

训练结束部分写入日志和当前操作集合；这里没有统一恢复历史最佳配对的结尾。`main.py` 在 `trainer.train(...)` 返回之后调用 `save_checkpoint("final")`，因此 final 导出保存的是那时的当前系统状态。早停分支跳过正常 epoch 尾部的 checkpoint 逻辑，但 main 仍保存 final。

- [trainer.py：早停，L1362–1383](https://github.com/ViktorAxelsen/MemSkill/blob/f65b797338033f4f9c34822f1810f9c2747e6022/src/trainer.py#L1362-L1383)
- [trainer.py：训练结束，L1530–1566](https://github.com/ViktorAxelsen/MemSkill/blob/f65b797338033f4f9c34822f1810f9c2747e6022/src/trainer.py#L1530-L1566)
- [main.py：训练后 final 保存，L1080–1099](https://github.com/ViktorAxelsen/MemSkill/blob/f65b797338033f4f9c34822f1810f9c2747e6022/main.py#L1080-L1099)

这意味着至少三个不同的评估候选应当被明确命名：当前 final 状态；将历史最佳库接到当前控制器后的状态；历史最佳阶段所对应、实际保存的边界 checkpoint 配对（该配对未必曾单独评分）。不能把三者的成绩或文件名互换。

### 4.4 完整 checkpoint 确实包含控制器和优化器

以上结论不适用于完整 checkpoint 的保存/载入。完整保存函数包括 controller、optimizer、当前库、新操作名称与偏置计数、配置、RNG、snapshot manager、designer 状态、阶段奖励和日志。载入函数在相应 skip flags 未启用时恢复这些内容。

- [trainer.py：完整保存，L1730–1766](https://github.com/ViktorAxelsen/MemSkill/blob/f65b797338033f4f9c34822f1810f9c2747e6022/src/trainer.py#L1730-L1766)
- [trainer.py：完整载入，L1792–1833](https://github.com/ViktorAxelsen/MemSkill/blob/f65b797338033f4f9c34822f1810f9c2747e6022/src/trainer.py#L1792-L1833)

所以准确结论是：**演化用阶段快照和普通库回退没有恢复控制器；完整 checkpoint 有控制器恢复能力。** 任何“MemSkill 恢复从不包含 controller”的表述都超出了源码证据。

## 5. 形式化：历史优选不能识别新配对的价值

用

\[
R(B,\theta;\mathcal D,\psi)
\]

表示在分布 \(\mathcal D\) 与其余固定条件 \(\psi\) 下，由技能库和控制器组成的系统表现。\(\psi\) 包含执行器、行动模型、编码器、token 预算、记忆构建及检索协议。

若固定某个实际保存的阶段边界状态，可以定义其表现为

\[
R(B_i,\theta_i;\mathcal D_i,\psi_i)
\]

但实现中的阶段奖励并不等于对这一静态配对的独立评估：它聚合训练过程末段的任务反馈，期间 controller 可以继续更新，还可能经过窗口平滑。应当把实际阶段得分记录为那段训练轨迹的观测，而不是指定给单个 \(\theta_i\)。这个得分既不单独识别 \(B_i\) 的普遍质量，也不直接估计

\[
R(B_i,\theta_t;\mathcal D_{\mathrm{test}},\psi_{\mathrm{test}}).
\]

关键原因不是抽象的“系统复杂”，而是有具体的相互作用路径：技能文本改变操作编码；控制器根据这些表示、会话和具体记忆选择技能；执行结果改变后续记忆状态；新的状态再次影响路由。一个在旧控制器下被少用的技能，换到新控制器后可能被过度使用；一个新技能也可能依赖已经学到的路由方式才能获得收益。这些都是竞争解释，尚未被本轮观察区分。

最小可区分设计是两个库和两个兼容控制器的四格干预。令 \(R_{ij}=R(B_i,\theta_j)\)，则

\[
I=R_{11}-R_{01}-R_{10}+R_{00}
\]

测量在预先定义的分布与预算下、采用加性尺度时的库×控制器交互。\(I\ne0\) 说明“库的效应不随控制器变化”这一假设不成立；它本身不是负迁移。负迁移需要另行定义，例如固定 \(\theta_1\) 后 \(R_{11}<R_{01}\)，并报告不确定性、任务范围及有意义的效应阈值。

还要区分两个事实：按训练奖励选择历史最佳状态可能具有选择偏差；在固定的独立测试集上比较四个保存状态则可以回答更清晰的泛化问题。前者是选择规则的性质，后者是可执行的实验设计。

## 6. ALFWorld：经验如何进入记忆，反馈如何回流

### 6.1 最终评估的可见构建路径

检查 `main.py` 的 ALFWorld 评估路径，记忆可从缓存载入；若需要重建，则从 `train_data` 分块并构建 MemoryBank。下游 rollout 使用 `test_data`。检索 query 来自 initial observation 与 objective，保留了任务类型、game file、objective、query、memory index 等记录。检查的这个分支没有把 test trajectories 显式送入记忆构建函数。

- [main.py, L838–950](https://github.com/ViktorAxelsen/MemSkill/blob/f65b797338033f4f9c34822f1810f9c2747e6022/main.py#L838-L950)

这支持一个有限的来源描述：**这条代码路径打算用训练经验构建记忆，再在测试任务中使用。** 它不足以证明实际输入文件、预建缓存、checkpoint 选择及任务模板全部无重叠。缓存的来源和构建参数必须由执行 receipt 补充，而不能从 `train_data` 这个变量名推断。

### 6.2 训练 A/B 分组并非始终严格互斥

ALFWorld processor 按任务类型组织 game file 记录。样本足够时，A/B 先联合采样再拆分，能保持该次采样的 game file 互斥。样本不足时，代码会对 B 的候选及抽样方式做回退；在剩余集合为空的分支中重新使用全体，可能产生 A/B 重叠或重复样本。默认同类型概率与训练脚本显式参数也可能不同。

- [src/data_processing/alfworld.py, L1–115](https://github.com/ViktorAxelsen/MemSkill/blob/f65b797338033f4f9c34822f1810f9c2747e6022/src/data_processing/alfworld.py#L1-L115)

这是训练 support/query 划分的源码边界。**它不是本轮已观察到测试泄漏。** 如果研究问题是“从先前任务形成技能后，能否帮助真正的新任务”，应当输出每次实际 A/B ID、是否重复、任务模板与文件来源；随后按有重叠/无重叠和任务类型分别分析。仅改一个抽样参数不足以证明新颖性。

processor 的块单元是完整轨迹；过长轨迹不在该路径内进一步切成较小片段。因此 token 预算和轨迹长度也可能改变可获得的经验量，不能把 chunk size 的名义数字当作已经严格固定的信息预算。

### 6.3 A 构建具体记忆，B 的结果进入训练与设计器

训练中可以看到新建 MemoryBank、用 A 构建记忆、在 B 上运行任务并收集奖励。失败案例携带 query、任务类型与 game file、成功目标、轨迹、memory、检索结果、预测和分数，进入设计器/阶段奖励流程。

- [trainer.py, L1940–2170](https://github.com/ViktorAxelsen/MemSkill/blob/f65b797338033f4f9c34822f1810f9c2747e6022/src/trainer.py#L1940-L2170)

B 在这里是训练反馈的一部分。它不应在写作中被描述为从未影响 controller 或 designer 的最终独立测试集。更有解释力的实验应在训练分组之外另留完整任务或模板组作为最终评估，直到状态选择完成才使用。

### 6.4 经验语料与脚本参数仍需实际运行清单

`alfworld_replay.py` 区分 train、eval_in_distribution、eval_out_of_distribution，并记录专家轨迹、初始观察和目标；分别对应 train、valid_seen、valid_unseen 文件。README 也描述这些文件。代码的专家 replay 可以运行到预设最大步骤并报告失败；实际生成的数据覆盖仍需输出清单确认。

- [alfworld_replay.py](https://github.com/ViktorAxelsen/MemSkill/blob/f65b797338033f4f9c34822f1810f9c2747e6022/alfworld_replay.py)
- [README.md, L161–164](https://github.com/ViktorAxelsen/MemSkill/blob/f65b797338033f4f9c34822f1810f9c2747e6022/README.md#L161-L164)

所检查训练脚本使用如 A=40–60、B=5、同类型概率=1、Contriever、技能 K=3 等设置；评估脚本则包括 Qwen embedding、K=5、chunk=512、overlap=64、max steps=50、ICL=1。论文附录对训练/评估 K、不同数据集的演化频率也有设定。这些是需要固定的配置差异，不是本轮已经证明影响结果的混杂项。[train_alfworld.sh](https://github.com/ViktorAxelsen/MemSkill/blob/f65b797338033f4f9c34822f1810f9c2747e6022/train_alfworld.sh), [eval_alfworld.sh](https://github.com/ViktorAxelsen/MemSkill/blob/f65b797338033f4f9c34822f1810f9c2747e6022/eval_alfworld.sh), [论文附录 B](https://arxiv.org/html/2602.02474v2)

## 7. 与论文发现的关系

作者的消融与迁移实验说明，这个方法的收益不能只归于“保存更多文本”。论文报告控制器、设计器及技能增加/修改的组合有不同表现；也报告从 LoCoMo 学到的库向 HotpotQA 设置迁移的结果。但这些实验并不自动等价于对同一组 \(B_0,B_1,\theta_0,\theta_1\) 进行配对四格干预。

例如，移除 controller 后改成随机技能选择，同时移除一个行为机制；移除 designer 后保留初始 primitives，又改变了可选择的技能集合。它们对于方法总体解释有价值，但不能独立告诉我们“旧库在新 controller 下是否更好”，也不能识别库与控制器在某一保存阶段的兼容性。

本轮新增的研究不与这些消融竞争复述。它提出一个更具体的识别问题：保持其余条件不变时，库的效应是否因控制器而反转？如果会，阶段选择和最终评估应记录系统配对，不能只记录技能文本与历史平均奖励。

成本也应保留计量范围。论文中记忆构建的 token/API 开销比较不等同于包含训练、设计器演化和所有奖励评估的生命周期总成本。若 AMS 把“学习如何记忆”写成成本转移，应明确是哪一类调用被前置、摊销或排除。[论文 §4.4 及成本表、附录 B](https://arxiv.org/html/2602.02474v2)

## 8. 可进入 AMS 的论点、修订和问题

### 8.1 可作为本轮判断的内容

1. 应当把可学习的记忆系统至少拆分为共享处理规则、规则选择机制与规则作用后的具体记忆，以便定位更正和回退究竟改变了哪一层。
2. 阶段历史奖励描述一段训练轨迹及其当时条件，不一定对应单个静态配对；仅恢复其中一部分状态，不继承历史表现保证。
3. 经验复用的评估单位可能需要是“库×控制器”，而非孤立的库。是否必须如此，应由配对实验判断。
4. 对使用反馈选择技能库的训练流程，训练 A/B 角色、最终测试角色和缓存来源应分别记录。变量名与文件目录并不能完成这项证明。

以上 1–4 是基于源码的研究判断，不是新增性能结论。

### 8.2 已接入的研究位置

| 研究对象 | 本次增补 | 证据关系 |
|---|---|---|
| [经验进入规则与参数](../../study/entries/experience-becomes-policy.md) | 区分技能库和选择技能的 controller；部分回退后仍需重新评价配对 | 本文 §3–5 的源码与推论 |
| [经验到能力](../../study/inquiries/experience-to-capability.json)与[经验到策略](../../study/inquiries/experience-becomes-policy.json) | 加入配对变化的竞争解释、静态 evidence 和研究文章入口；问题仍开放 | 固定实现与未执行四格干预 |
| [状态配对研究文章](../../study/entries/memskill-state-pairing.md) | 区分论文与源码版本、阶段平均奖励与静态配对，以及三种保存／回退路径 | 本文 §2、§4–5 |
| [配对迁移协议](memskill-negative-transfer-protocol.md) | 四格分别重建 MemoryBank，保留状态兼容、数据来源与模型执行前置条件 | 未执行设计，不构成新的性能证据 |


## 9. 需要后续区分的竞争解释

| 解释 | 可观察预期 | 单靠什么仍然不能区分 |
|---|---|---|
| 技能文本本身更有效 | 新库在旧、新 controller 下都改善，库主效应方向相同 | 仅比较历史阶段均值 |
| 控制器学到了更好的路由 | 新 controller 在两个固定库下都改善 | 只比较最终系统与初始系统 |
| 特定库与 controller 共同适应 | 四格交互，可能出现库排名反转 | 仅 controller 随机消融 |
| 训练采样和噪声造成“最佳阶段” | held-out 配对排名不稳定，训练赢家未必领先 | 单个训练阶段奖励 |
| 缓存或具体记忆来自不同状态 | 相同 B/θ 但不同缓存构建来源导致差异 | 不带来源的缓存文件名 |
| 任务分布发生变化 | ID 与 OOD 的效应方向不同，且与模板/类别有关 | 把所有任务合并成一个总分 |

完整的可实施方案在 [memskill-negative-transfer-protocol.md](memskill-negative-transfer-protocol.md)。本文不要求现在继续训练，不建议先重写系统；最经济的下一步是确认是否存在可配对的完整 checkpoint 和可追溯经验语料。

## 10. 证据声明

本轮贡献是一份固定版本机制研究，以及从部分回退推导出来的可检验兼容性问题。我们没有证实 MemSkill 出现性能伤害、数据污染或负迁移，也没有把作者的实验数值转换成本项目的复现结果。这里的分析若被两个仓库使用，仍然只有一份共享来源核查。运行时效果、效应范围和最佳导出策略都留待预注册的配对实验回答。
