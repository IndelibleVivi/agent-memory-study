# 范围与修订：模型写入之后，记忆还可用吗？

Agent Memory Study editors · 2026-11-07 · 探索性自然语言诊断协议，reader 调用前修订 v2。

## 一次 reader 前修订

最初冻结协议把超过450字符的记忆视为 workflow 失败。24次 writer 完成后，有6份为
454–506字符，而所有输出均为有效JSON。此时 reader 调用数为零。若把这些后续任务全部
计零，主要差异可能来自字符计数服从性，偏离适用判断问题。因此本版将字符超限改为
独立工程指标，所有原始记忆一字不改地进入 reader；不重新抽 writer、不挑选、不人工修补。
新 run 绑定前一 run 的全部 writer/canary 请求、响应和 source identity，原始协议、原始
source、最初的失败标记与未执行 reader 计划保留在原 run。本文不把这一调整称为完全预注册。
后续只改变了长度处理政策，没有修改材料、gold、writer prompt 或任务评分。实际长度和
严格450字符接受规则下的可用性须另报，不能声称实际长度相等。

## 要改变的判断

当历史中有部分撤回、时间条件、分支例外与尚未接受的提议时，把范围和修订关系显式写入
记忆，是否比同预算的普通 prose memory 更有用？完整原始历史是有竞争力的参照。
收益必须同时体现在被修订的任务和不应改变的相邻任务上；把所有行动都暂停不算解决。
如果普通摘要已经足够，或显式结构带来遗漏和过度推断，结果将削弱增加该结构的理由。

此前侧信息实验的主要用途是 explicit-rule sanity check。其预设噪声与编码表决定了许多
数值，不能据此回答这里的语言理解、压缩或范围恢复问题。本研究不要求出现正向效果。

## 材料、比较和分析单位

`natural-cases.json` 是 12 段独立原创合成历史和各 6 个任务的作者真源。它们不是随机抽样
的人类历史，也没有真实私人资料。自然语言消息只包含 id、时间、说话者、正文；评估方的
mechanism、gold、support、rationale 和 misconception 永远不进入模型输入。
每个任务有四个具体行动选项；正确选择与来源依据在调用前固定。包括当前修订、保留范围、
历史状态、复合条件、需要具体澄清的情况和普通可执行情形。两个稳定策略案例检验无谓复杂化。

| 条件 | writer 看见什么 | reader 看见什么 |
| --- | --- | --- |
| raw | 不调用 writer | 完整历史与一个后续任务 |
| prose | 完整历史，无任何后续任务或答案 | 模型生成的普通文字记忆与一个任务 |
| ledger | 同一完整历史，无任何后续任务或答案 | 模型生成的范围／修订记忆与一个任务 |

两种 writer 使用同一个 gpt-6.1-sol、共同的保存语义要求和450 Unicode字符的压缩目标，
差别是连续文字与逐项的对象／条件／结论／修订／来源组织方式。共同要求保存必要历史、
例外、时间、未决状态与来源；不把 prose 刻意写成忽略条件的弱基线。writer 输出上限
3072 tokens，reasoning=low。超字符目标单列；无有效输出仍计作该 workflow 失败，不偷偷
截断、人工修正、挑选最好一次或补写 gold。两种记忆各生成一次，随后供所有 reader 复用。

reader 分别为 gpt-6-luna 与 gpt-6.1-sol，reasoning=low、输出上限 1536 tokens。每个任务
单独调用，不让同组其他问题充当提示。每个 model × case × question × arm 只调用一次：
432 次 reader、24 次 writer；接口 canary 不属于实验样本。随机固定执行顺序只分散运行时段，
不是随机抽样。12 个历史是分析单位，72 个任务及两模型的回答不冒充更多独立历史。

这是两个实际压缩 workflow 的比较，不是控制所有因素后的“纯格式效应”：实际长度、
生成内容与 writer 错误都可能不同。报告实际 token、字符与成本，不声称等实际 token。
raw 没有压缩预算，其额外输入成本是参照的一部分；所有材料完整送达，不另加检索、
top-k、随机噪声或窗口截断。由此不能估计检索召回失败。

## 评分与能支持的解释

主指标为固定四选一的 task correctness，完整报告每个 model/arm、历史与任务种类，
以及 ledger 相对 prose 和 raw 的配对增减。缺失、HTTP 错误、incomplete、格式错误、
无效记忆均计入完整分母的失败，并另报技术状态；超字符目标按上面的reader前修订单列。
writer 失败不换别的输入顶替。
输出仅要求 choice、source IDs 和简短依据；自报依据不当作内部推理的证明，source IDs
不作为主分数，因为多个合法证据链未必等同于作者所列的最小支持集。

冻结 gold 后不根据模型答复改正确答案。若发现真实歧义，保留原分数并公开列出 contested
题目的敏感性分析，不能悄悄修题重跑。两模型、所有案例和失败全部披露。不给这个有意构造
的小样本计算伪总体发生率；不把任务行当作 iid 做显著性检验。

分析时逐个检查错误任务的原历史和两份实际生成记忆：区分可直接观察的遗漏、错误更新、
范围扩张与“关键事实在可见记忆中仍然答错”。缺少明确文本证据时标 unresolved。
raw 正确而压缩错误只是定位线索，不能单靠这一差异宣称找到内部因果机制。
两模型共享 writer，跨模型一致不构成独立 writer 复现；一次采样不估计运行波动。

若三臂接近满分，结论是这批任务未显示结构的增量，不再增加难度来追求差异；若有差异，
解释限定于这些原创建构、这次 writer 输出与指定 model alias，不推广为总体 benchmark。
本轮不研究在线记忆更新、后续自身输出回流、训练、权重遗忘、私人语料或真实工具操作。
旧离线 `protocol.md` 与 scripted/oracle receipts 保持原样；本研究是其中范围消费问题的
独立实际模型诊断，不宣称旧协议的全部三臂／预算／位置／跨事件推论矩阵已经完成。

## 执行与证据

先冻结 source identity、完整 corpus、配置与实际 request；两种 writer 生成后，冻结实际
记忆及 reader request，再进行 reader 调用。阶段前使用官方 `/responses/input_tokens`
计数，按最高 cache-write 输入费率和全部输出上限预留费用；整批上限 USD 10。
官方 Responses endpoint、standard tier、store=false，无 tools、无自动重试或 provider fallback。
store=false 不宣称零服务端保留。费率来源：
[Sol](https://developers.openai.com/api/docs/models/gpt-6.1-sol)、
[Luna](https://developers.openai.com/api/docs/models/gpt-6-luna)，核对日 2026-11-07。
模型 alias 的实际返回值与 usage 随 raw response 保存；alias 不是不可变 snapshot。

所有 raw request/response、来源绑定、启动意图与中断证据留在 repo 外。正式文件原子、排他
发布；已成功单元不重复调用，已启动但无 receipt 的单元保留为 unknown，不自动重试。
源码／协议／corpus 变化必须建立新 run。离线 replay 验证冻结请求、生成记忆与全部分数，
不触发 API；公开结果只保留聚合和定位，不替代本地 raw 审计。统一 verifier 只执行合同
测试和已保存 summary 核对，不运行模型。接口 canary 只验证格式，不使用研究题目。
