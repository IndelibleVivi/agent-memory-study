# P1 future-use：未来作者交接

**用途。** 本文件把 P1 从“已有 scripted control”推进到可由另一作者独立审阅和实施的未来用途设计。它不是结果，不新增 schema，也不要求复用 AMS 的统一 runner。共享方向见 [Relata campaign](https://github.com/IndelibleVivi/Relata/blob/main/research/relata-ams-campaign.md)。

## 1. 先固定研究问题，再选材料

建议保留的核心问题：

> 当未来问题的分布只能按声明给出、作者不能查看具体 held-out 题目时，不同 memory 表示与取回路径是否仍然把当前任务所需的证据送达 reader，并减少无证据的确定回答？

分析单位为独立 event family / lineage。一个 family 可包含事件、来源、纠正、多个问题、翻译、措辞、checkpoint 和重复测量；这些都不增加独立 `n`。

### 声明分布与对抗反例分开

必须准备两类材料，并在结果中分列：

1. **declared future-task distribution**：按预先声明的用途比例抽样，代表预期的 current、historical、provenance、relation、scope-change 等用途。
2. **adversarial counterexamples**：专门包含 near duplicate、scope distractor、missing、denied、known-stale、unknown-stale 或证据刚好不足的难例。

对抗集可以拒绝不稳健的方案，但它的计数不是自然分布错误率。若把它与声明分布合并成一个平均分，难例会被抽样比例操控，读者也无法知道方案在预期用途中的行为。

## 2. Policy 与 writer 冻结

在任何 held-out 题目进入 reader 之前，冻结以下对象并记录身份：

- source pack：原始记录、来源、时间、scope、授权状态和版本。
- writer：raw、固定 summary、coexistence 或其他已声明表示的实际变换代码或人工模板。
- policy：哪些记录进入候选、如何排序、top-k、如何截断、如何安排 revisit。
- reader access：实际可见材料、system prompt、answer format、decoding 或 deterministic parser。
- evaluator：gold、accepted deferral、unsupported definite answer 和 task completion 规则。

“冻结”不是只写一句配置名称。应保留 source/code/template digest；每一次 writer 或 policy 改动建立新版本，旧结果的 source identity 不因此静默更新。

### 现有 AMS 中的对应入口

- [corpus.py](../representation-use-study/corpus.py#L18)（L18 起）：现有 family 构造；L90 起为 writer 与固定 summary 删除规则。
- [corpus.py:64](../representation-use-study/corpus.py#L64)：独立于writer输入的 latent gold（同一作者化研究，非独立验证）。
- [study.py:48](../representation-use-study/study.py#L48)：settings 与 budget 身份。
- [study.py:71](../representation-use-study/study.py#L71)：candidate、selected、delivered 和 request 的实际记录。
- [study.py:158](../representation-use-study/study.py#L158)：completion、unsupported answer、over-abstain 与 citation 有效性。

这些入口说明已有合同长什么样；新 family 不应直接改写旧 sample 的 identity。

## 3. 谁能看什么

未来用途研究最容易在材料准备阶段失去盲性。最低要求如下：

| 角色 | 可以看 | 不应看 | 必须留下什么 |
| --- | --- | --- | --- |
| source author | 原始 source、允许公开的时间/来源/scope | held-out 问题、gold、evaluator 阈值 | source version 与来源授权 |
| writer/policy author | source 和允许的用途声明；可为通用规则编写 writer | 具体 held-out 题、答案位置、删除规则之外的评分秘密 | writer/policy digest、可见字段、修改历史 |
| future-question author | 声明用途、题目所需的完整允许source、dev examples | writer内部删除规则、处理臂输出和已评价回答 | 题目产生时间、实际可见source与独立性限制 |
| operator | 冻结后的完整材料与运行需求 | 不应参与调参或改 gold | actual access、运行参数、异常 |
| evaluator | gold、冻结 response 与 rubric | 不应在看到 response 后改 accepted set | scorer version 与评分时间 |

访问记录应该是实际事件，而不是事后声明。最低限度记录：

- 角色或 pseudonymous reviewer ID；
- 看到的是 source、writer code、具体 future question、gold 还是 summary response；
- 第一次 access 的时间与版本；
- 是否发生修改，以及修改后是否建立新 identity。

现阶段无需新 JSON schema；可由运行日志、签名 review record 或受控目录权限实现。没有实际 access receipt，不要宣称“独立未来作者”。

### 何时给 source 与 future question

推荐顺序：

1. 固定 source pack 与 source digest。
2. writer/policy 作者在看不到 held-out questions 和 gold 的条件下完成通用规则。
3. 冻结 writer/policy，并检查其是否只读取允许字段。
4. future-question 作者依据声明的用途分布准备题目；若需要独立盲性，则其不得查看 writer 的删除规则或已评价 response。
5. 题目形成后依据完整governing source核对允许行动与支持合同，在看reader结果前冻结rubric；保持writer与出题作者的访问记录。
6. operator在writer输出完成后才把future questions和冻结material交给reader；evaluator随后读取response与冻结合同。

任何角色先看 eval set 再改 writer，都会破坏题目的未来性。可以保留 dev set，但不能再把同一集合称为 held-out。

## 4. 条件矩阵

### History × task set

| 条件 | source/history | 问题集 | 解释 |
| --- | --- | --- | --- |
| fixed × current | 修订前 | 当前行动与 scope boundary | 基线当前用途 |
| fixed × expanded | 修订前 | 当前题加历史、来源、关系、措辞等新增题 | 新增用途与 common 题分开 |
| updated × current | 含正式修订 | 当前行动与 scope boundary | 修订对当前行动的影响 |
| updated × expanded | 含正式修订 | 当前题加新增题 | 历史题与当前题分别评价 |

current 与 expanded 共有的 anchor 题必须逐字或语义身份一致，保持配对。expanded 的 added questions 单列。tasks expanded 造成的任务分布变化不是一个 matched treatment：不能把所有 common 与 added rows 混在一起做“只改了 task set”的因果结论。

### 表示/取回条件

至少考虑以下可区分条件，但不要为凑数量创建同机制的重复标签：

1. **no history**：没有历史 memory，只有当前任务。
2. **full raw**：允许完整原始记录进入候选或 reader，清除 raw 路径本身的明显瓶颈。
3. **BM25**：真实词项检索，固定 tokenizer、索引字段、参数、返回数和 equal-cost 规则。
4. **dense**：固定 encoder、revision、向量/距离、索引和 threshold；没有真实实现时不能执行或命名。
5. **auto summary**：由冻结的生成过程产生 summary；人工固定 summary 不能替代。
6. **summary + iterative revisit**：限制初始 summary 的可见信息，再按当前问题触发有次数上限的 source revisit。

dense 与 BM25 不是同一对象的两种名字；auto summary 不是固定字段删除的同义词；“summary + revisit”也不是“给更多 top-k”。每个条件必须有独立的成本记录。

## 5. Candidate、selected、delivered

新 P1 必须显式区分四个阶段：

1. **candidate pool**：当前任务下可进入检索/选择的记录集合。
2. **top-k selected**：从 candidate 中选出的有限条目。
3. **delivered**：实际进入 reader 的文本或结构化记录，可能继续被 byte/token/行数预算截断。
4. **used / outcome**：reader 的回答与任务结果；引用合法不等于因果使用，`used` 默认 unknown。

候选项数必须大于最终 top-k。这样才实际形成候选竞争；当全部候选都能送达时，结果不能评价拥挤检索库中的选择能力。

建议候选池至少包含：

- 必需证据；
- 部分支持证据；
- 同一主题但 scope 不同；
- near duplicate / paraphrase；
- 完全无关但词汇相似；
- 已知 stale 的旧版本；
- 当前状态无法确认的 unknown-stale；
- 被拒绝访问的 denied 记录；
- 当前确实没有记录的 missing case。

保留完整 ranking 或至少保留必需要素的 rank。selected 后不得再用 gold 重排；delivered 后不得悄悄把 missing 记录凭空补回。

## 6. 五种 reaccess 状态

| 状态 | 可见事实 | 正确行为示例 | 不能声称 |
| --- | --- | --- | --- |
| current | 当前版本、scope、authority 和有效时间一致 | 可使用该记录回答当前任务 | 记录存在就证明 reader 使用了它 |
| missing | 指定来源重访明确返回对象不存在／不可取得，保留访问证据 | 有范围地暂缓或询问 | 没检索到就证明系统缺少记忆 |
| denied | 存在目标对象，但当前调用被授权规则拒绝 | 说明无法访问，避免用旧副本替代 | denied 等于 missing 或等于记录被删除 |
| known-stale | 系统已知版本/有效期已失效，能绑定旧来源 | 不把旧值作为当前答案；必要时说明旧记录 | stale 记录一定导致错误，或任何错误都来自 stale |
| unknown-stale | 作者世界中来源已陈旧，但reader缺少当前性信号；保留world与reader view隔离 | 明确不确定性，重新取得证据 | 没有新版本就自动是 fresh；旧线索就自动是 stale |

五类都可以导致 `insufficient` 情形，但证据身份不同。报告可按共同 outcome 汇总，底层类别仍须保留；否则无法诊断 denied 的授权问题、missing 的覆盖问题或 unknown-stale 的版本问题。

changed、preserved 与 boundary 三者不可相加；boundary 已包含在 preserved 内。historical 题与这些集合可以重叠，也不相加。

## 7. Family lineage 与独立样本

以下变化不增加独立 family：

- 中英文翻译、自然混写、同义措辞；
- current/expanded 两个任务集；
- fixed/updated 两个 history；
- forward/reverse/rotate 等位置；
- 多次 checkpoint 或重复任务；
- 同一事件在 Relata 与 AMS 的镜像；
- 同一 source 派生出的不同 summary；
- 同一个 family 的多个问题或候选。

一个 family 应有一条可追溯的事件 lineage。两个 family 只有在 source events、关系与 gold 形成独立因果单位时才可分别计数。若两个“family”只是同一事件的改名，应合并。

### 现有 8 个 family 的限制

现有 P1 有 8 个 family、64 cases、320 question rows。它们是公开 development/diagnostic materials，不是 held-out；一个已查看固定 summary 删除规则的作者 不能再以“未来作者”身份生成同族 held-out 题。约 24 个新 family 可作为 pilot 起点，用以检查材料、access、预算和失败模式；若需要 effect interval 或 power，应另做样本量设计，不能把 24 当作充分样本自动声明。

## 8. 预算与成本

### Equal reader budget

比较进入 reader 的实际材料预算。必须记录真实 tokenizer 和真实单位；若只能提供 UTF-8 bytes，就写 UTF-8 bytes，不能叫 tokens。reader 的 system prompt、question、format 与输出上限也要固定或分别报告。

### Equal pipeline cost

比较从 source 到 reader 的总成本：

- indexing/encoding；
- retrieval/candidate generation；
- summary generation or revisit；
- reranking/dedup；
- reader calls；
- 重算、缓存和后台维护；
- 人工整理或复核。

equal reader budget 不保证 equal pipeline cost；equal pipeline cost 也不保证 reader 看到相等内容。两者要作为不同分析出现。若一个方法在两种 matching 下都无可比条件，结果只能描述实际资源路径，不能排名。

## 9. 主要与次要终点

### 主要终点

1. **task completion**：按冻结任务 rubric 判断是否确实完成任务。
2. **unsupported definite answer**：没有证据或证据不足时仍给出确定答案。它独立于 completion，不能由总体 accuracy 掩盖。

### 必须分列的次要诊断

- 正确 deferral 与 over-abstain；
- 必要证据在 candidate、selected、delivered 各阶段的到场；
- scope distractor 与 near duplicate 挤占；
- stale / denied / missing 的误用；
- citation 可定位性，但保持 `used=unknown`；
- 实际 reader budget 与 pipeline cost；
- 按 family、history、task set、common/added 和声明的用途类别保留分母。

不要用一个综合 quality score 替代这些不同错误。primary outcome 一旦冻结，不能因其他策略在次要指标上好看而改写。

## 10. 最小原始示例

以下只用于说明 lineage 和 reaccess，不是 fixture 或 schema：

> 原始记录 A：第 1 日，负责人接受“旧客户端使用 `--format`”。
>
> 更正 B：第 3 日，负责人说“新版客户端从第 4 日起使用 `--output`；旧客户端仍使用 `--format`”。
>
> 未来题 C：第 5 日，维护旧客户端应使用什么参数？
>
> 未来题 D：第 5 日，维护新版客户端应使用什么参数？
>
> 未来题 E：第 2 日，当时已接受什么参数？

C、D、E 都属于同一 lineage，不增加独立 `n`。若另有 denied 版本，应独立说明“当前调用无权查看新版来源”，不能把它当作 missing。只检索到A而没见B首先是delivered evidence不足，不能直接标missing；来源重访返回not-found才记录missing。B的接受状态不明是authority uncertainty，不自动等于stale；unknown-stale要求作者世界已有更新而reader没有当前性信号。

## 11. 交接验收清单

未来作者在运行前应能回答：

- [ ] 独立 family 与 lineage 清单是否固定？
- [ ] held-out questions 是否在 writer/policy freeze 后产生？
- [ ] 实际 access 是否有记录，而非口头声明？
- [ ] fixed/updated × current/expanded 是否只由已声明因素改变？
- [ ] common anchor 是否配对，added questions 是否单列？
- [ ] candidate pool 是否大于 top-k，并含 scope/duplicate distractors？
- [ ] 五种 reaccess 是否各有可见证据？
- [ ] reader budget 与 pipeline cost 是否分别记录？
- [ ] no-history 与 full-raw 是否作为解释基线保留？
- [ ] primary task completion 与 unsupported definite answer 是否冻结？
- [ ] declared distribution 与 adversarial counterexamples 是否分表？
- [ ] 约 24 个 pilot family 是否仅写作 pilot，而非 power 保证？

任一否定项都意味着 P1 还没有可执行的未来作者合同。可以继续做 development，但不能把它包装成独立 held-out 结果。
