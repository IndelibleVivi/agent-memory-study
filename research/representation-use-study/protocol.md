# 原事件、概括与并存：消费端比较协议

Agent Memory Study editors · 2026-09-25 · **proposed-not-run**。

## 研究问题与分析单位

我们要估计的是：在给定事件和问题下，改变模型可见的记忆表示，会如何改变来源辨识、
适用判断与推论。它不估计“生物整合机制”的效果，也不检验 summary controller 的生成能力。
第一轮固定人工核对的概括，随后才另行研究概括生成错误。

既有记忆库可以提供真实材料与现状 baseline，但其 schema、切块、清理、索引和 encoder
不构成未来记忆架构的预先选型。适配器保留来源后，将同一批可核查案例交给不同表示条件；
一个现有系统上的检索差异，不能自动升级为目标架构的要求。

独立分析单位为完整事件组。每组含带时间、主体和来源的原创短事件、一次归纳机会及一条
有范围的纠正。同组的问题、位置排列、翻译和改写都保持绑定；报告组数和预测行数，不能将
后者当作独立样本量。开发组只用于确认材料清楚、parser 和预算可运行；冻结测试组后不按
测试表现改例子或阈值。具体样本量与运行模型仍未确定，不宣称统计功效已经建立。

## 比较与问题

| 表示条件 | 可见材料 | 必须单列的限制 |
| --- | --- | --- |
| 原事件 | 原始事件、来源、时间和明确纠正 | 需要从多段经历自行形成跨事件关系 |
| 概括替代 | 同一组事件的派生概括与适用范围 | 已删除的来源细节没有恢复义务 |
| 两者并存 | 原事件与概括，明确标注观察／推论及支持关系 | 额外长度与措辞竞争可能带来收益或损害 |

每组同时提出三类问题：

1. **历史来源**：谁在何时实际说过什么？A–B、B–C 的经历不能被答成“A 与 C 曾直接互动”。
2. **当前适用**：更正针对哪个对象、时间与用途？旧决定退出当前行动后，仍可作为历史事实辨认。
3. **跨事件推论**：哪些间接关系获得支持，哪些仍需暂缓？清楚区分原记录与派生结论。

为每个问题、每种表示分别预标 `sufficient / insufficient / conflicting`，同时保存支持文本
定位、可接受答案和可接受暂缓理由。概括臂缺失的细节首先进入信息可用性统计；在各臂共同
具备充分证据的子集上比较消费质量，并另报完整子集，避免筛选掩盖真实表示损失。

## 输入与输出控制

- 固定 answerer、system prompt、解码设置和回答 token 上限；记录实际输入 token 数、截断
  位置及最终可见证据。不得只报告配置上限。
- 同时报告完整材料比较和相同预算比较。预算不足时按预先写定的选取规则处理，不临时为
  某个方法保留答案；重新标记该实际输入的信息充分性。
- 对关键证据前／中／后的位置置换做组内配对；概括自身的位置也要记录。不能将三次排列
  当作三个独立事件，也不预设今天的模型必然复现旧论文的效应。
- 分开记录：候选出现、选入、最终送达、能够定位、恰当使用。未执行某一步就留空；
  `retrieved=true` 不等于使用成功，回答未逐字复述也不等于没有帮助。
- 首轮可以用结构化回答便于复核，但解析成功、引用ID合法都不算内容正确。保留原始回答，
  按冻结 rubric 核查语义；模型 judge 的标签必须单列来源，不冒充人工金标准。

## 更正与失败如何计数

更正后分别报告 changed、preserved，以及 preserved 内的相邻 boundary 子集；三者不可
直接相加。历史题与当前行动题分别评价，不以“禁止当前使用”自动取消历史可回答性。

报告来源辨识正确、适用判断正确、受支持推论、无支持来源归因、恰当暂缓、过度暂缓，
以及实际证据缺失。保留每组的配对转移和失败例，不压成一个总排名。推论增加而来源辨识
下降、并存无增益或概括压过原文，都可以反驳当前设计。

## 与双语评分研究的关系

本研究先固定提供给 answerer 的表示，回答“拿到这些信息以后怎样用”。
[双语使用策略](../multilingual-use-policy/protocol.md)先固定候选，回答“哪些材料值得送入”。
两边各自通过材料和测量检查后，再串联；一次端到端失败不能凭最终答案定位到某个部件。
事件切分也另设对照：固定消费者，只改变切块方式；连续切段与跨段事件归属分别输出。

## 当前执行边界

没有运行 answerer、controller、翻译模型、judge 或真实记忆实验；没有任何收益、显著性或
样本量充足性结论。运行时不得接入私人 live memory 写路径；公开输入使用原创材料。
从私人经历提炼公开案例需要另行明确选取和公开范围，不能仅改名字就当作已匿名化。

## 2026-10-23 离线执行附录（WP1–WP3 development）

上文的自然语言模型比较仍为 **proposed-not-run**；以下公开 fixture 和已执行结果仅验证
离线测量链，为 **scripted/oracle controls**。它没有完成模型 tokenizer、provider、翻译、
judge 或真人检查，也不是 blinded confirmatory evaluation。开发结果不能据此解释 agent 收益。

`corpus.py` 固定八个独立 event families：scope、authority、time、agreement、provenance、
relations、conflict、unknown。先以 family 分 development（前四组）和 diagnostic（后四组），
再生成 fixed/updated history × current/expanded task sets 的 2×2 与两个原话变体，共 64 cases。
current task set 包含当前决定与相邻 scope boundary 两题；expanded 保持这两题不变，并加入
第一日历史、正式接受、来源时间、逐字原话、直接关系、间接关系六种未来用途，共八题。
因此总计 320 question rows。scope 是独立题目控制，不以 scope 改名冒充任务用途扩展。
所有 wording、问题、顺序和三表示变体留在同一个 group；两 split 都已公开，不能用 diagnostic
名称暗示盲测或将 320 question rows 当作独立样本。

`truth(events, question)` 是 latent event-state interpreter。它在相同时间的合法决定冲突时
允许 clarify 或 abstain；没有适用决定时允许询问 scope 或暂缓。`writer(events, arm)` 不接收
问题或 gold。固定 summary 删除 actor、逐字措辞以及第五日之前被合法新决定替代的旧条目，
保留决定的 scope、time、authority、accepted 与关系种类；不训练或评价 summary 生成。
三臂均列出 candidate / selected / delivered；prefix truncation 后只有完整 JSONL records
满足 evidence obligations。历史/来源损失、缺少完整 negative inventory 与明确冲突分别计数。
这些 obligation 是保守的可检查 sufficient certificate，不宣称涵盖所有自然语言可推理路径。

`scripted` 用独立 reader 读取最终 JSONL，拿不到 latent state 或 accepted set；`latest` 故意
忽视 scope、authority、acceptance 与生效日期，是有已知反例的弱控制；`abstain` 固定暂缓，
在信息充分的可答题上有反例。`oracle` 的额外 gold 明确写入 request，是 extra-information
bound；预算只约束 memory field，不限制 oracle extra information，不能纳入公平胜者排序。
所有结果均为 structured exact-label scoring，非 semantic judge、LLM 或 human results。

full 与 equal 模式分别报告。equal 默认 memory budget 为 900 **UTF-8 bytes**，不是 model
tokens；完整 canonical request bytes 另计，包含 system、question、memory、generation 与 oracle
extra information。forward/reverse/rotate 为 deterministic 位置控制；rotate 把第一条移到末尾。
选择与截断不看问题/gold，partial UTF-8 字符丢弃，partial JSONL record 不算可用证据。
报告全任务、各臂同时 `sufficient` 子集、每 family 计数及 fixed→updated 的 changed/preserved
与相邻 scope boundary 配对；boundary 是 preserved 的子集，不能相加。新增用途与共同题目
分别报告，任务集的总体分布差异不构成 matched treatment effect。冲突不混入
all-arms-sufficient 子集；该子集由 planned delivery 决定，与 backend 是否成功无关。
每 bucket 的 planned/executed/scored denominators 与 outcome statuses 分列，quality 只聚合
成功解析的 scored responses，不把 failed/refusal/timeout 当作答错。`acceptable` 允许证据不足时有范围的暂缓；`task_correct` 则单列 latent
gold 一致性，防止以大量 abstain 冒充任务成功。citation validity 只检查完整送达的公开事件 ID，
不证明使用，`used` 始终为 unknown。

scorer v2 的 `over_abstain` 只计：实际送达证据为 `sufficient`、latent gold 至少允许一个
`answer`，而 response 选择 clarify/abstain。gold 本来要求 conflict/unknown deferral 时，
理由不匹配仍令 `task_correct=false`，且在充分/冲突材料下 `acceptable=false`，但不计
过度暂缓；实际截断为 insufficient 时，有范围的暂缓可 acceptable，也不计 over-abstain。
这一区分不扩大 gold accepted set；错误 answer 的 exact-label 判断继续独立。

每个 run 的 manifest 冻结 protocol/dataset/backend/parser/scorer/tokenizer/settings/source
identity，并分配 run ID。每 attempt 保存 request、启动意图、原始 response、receipt 与内容
digest。启动意图以后中断，一律作为 outcome unknown 的 interrupted attempt 保存，可能已运行；
request 刚写入而尚未写启动意图的窄窗口也按此处理。resume 验证当前真源与所有已有 artifacts，
成功 job 不再调用 backend，失败另增 attempt 并引用 retry_of；任何源、预算、数据或 scorer
变化需新 output。不得在同一 output 同时运行两个 executor。receipt digest 与 run ID 用于
完整性及身份校验，不是签名或抵御能重写整个目录的攻击者的可信证明。

Artifact 发布使用同目录独占 staging + file fsync + hard link（目标存在即拒绝），正式路径
只有完整文件或不存在。成功后移除 staging，中断时保留 `.name.<uuid>.pending` 的原始 bytes，
包括可能截断的 UTF-8。request/started/response/receipt 与 manifest/report 都采用此路径。
receipt 写入中途不产生截断的正式 receipt；resume 对缺失正式文件的 attempt 封存 interrupted，
其 `incomplete_artifacts` 绑定保留 staging，不修改旧 request/started/response 或 staging。
若 request 尚未发布，interrupted receipt 的 request 为 null；新 attempt 独立执行。已发布完整
successful receipt 后即使 staging cleanup 未完成也不再执行该 job。已正式发布的损坏 JSON、
foreign/source/settings 不符及 digest corruption 仍拒绝，不借恢复路径忽略它们。

无完整已发布 manifest 的非空目录视为未初始化失败：不从 staging 推断权限/settings，不执行
backend；保留目录，换新 output。此实现验证 process interruption，不承诺 power-loss durability
或损坏文件系统恢复，需要 output 文件系统支持同目录 hard links；不新增并发 writers 支持。

manifest 记录 exact Python runtime；resume 严格绑定。portable experiment identity 排除 runtime
和随机 run ID，以便相同 source 的跨 Python patch 汇总核对；raw manifest 仍保留本地 runtime，
不把 portable identity 当成执行环境同一性的证明。

verify/replay 只从冻结 response 重算分数与报告，不调用 backend，不声称恢复隐藏 provider
状态。当前没有 provider adapter；未来只能在明确授权后定义 exact imported request/response
receipt，并保留不同 evidence kind，不能将现有 control labels 改称模型结果。raw runs 留在 repo
外，公开 `sample-results.json` 仅为紧凑汇总，可按 README 重现核对。
