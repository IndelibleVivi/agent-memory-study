# 条件信息贡献与真实检索：协议 v1

Agent Memory Study editors · 2026-10-29。首次本地运行前固定，原创 development/diagnostic 构造；非盲法、非经验确认研究。无模型、真人或私人材料。本地 FTS5 是真实执行，scripted/oracle 是明确不同消费者；经验样本数 0。

## 目标与竞争预测

比较 S 对已有 B 的条件增量 `Y(B+S)-Y(B)`，另报告同一结果尺度的交互 `Y(B+S)-Y(B)-Y(S)+Y(empty)`。不能把交互与增量混名。无成本且可以忽略信息的理想解码器没有负信息价值；固定预算、检索排名、表示和实际消费者是另一组条件。

固定四个原创 family，变体生成前分组：complement 与 redundancy 为 development；revision 与 methods 为 diagnostic（同样被设计者看过，不称 held-out）。互补 family 穷举四个 x/y 世界，目标 XOR；重复 family 的两份材料都指同一事实；revision 区分旧/新有效时间；methods 中相同 key 对应 locked/open 两种操作。问题只提供操作类型、目标条件/时间和检索词，不包含世界答案或 scorer 标签。

六个条件 empty/B/S/BS/duplicate/sham；duplicate 是 B 加一份 B 的逐字内容副本，source ID 不同。sham 为 B 加一份与对应 S 的序列化 writer 输出等 UTF-8 bytes 的无信息材料；key 相同，可能竞争排名，故不把 sham 假装为“无处理”。raw writer 保留输入字段；compact 只去掉 prose 等说明，不调用模型且不接 query/gold。sham 在各 representation 之后构造并记录 exact bytes。

每条记录的检索 key 为 query 的精确英文词，真实调用既有 experience-reuse 的 FTS5 rank/select。排名只看 key，BM25 同分依原插入顺序；比较 top-k 与 unique-key 两种规则，固定 top-k=3。full 表示对选择后材料完整送达，不是全语料全知；equal 限 memory 200 UTF-8 bytes，按选材次序逐字节前缀，截断 UTF-8 丢不完整尾字符，消费者只解析完整 JSONL。diagnostic bytes 不是模型 tokens，request 总 bytes另记。不存在的字段不由 gold 补入；used 恒为 unknown。

## 两类干预

revision family 三种情形共享来源结构：baseline 世界 current=Friday，world-change 把有效状态和对应来源都改为Saturday并重新计算 gold；evidence-corruption 世界仍为Friday、只把送达来源改成Saturday，gold保持。两者分别报告任务正确性与有害证据响应；不能从观察到依赖就推成有益依赖。所有条件、政策、预算、表示与两消费者在首次运行前固定。没有事后按成功选择数据。

scripted reader 只读实际 request 的 memory/question，按显式字段完成 XOR、事实、时间与方法选择；缺失返回 abstain。oracle 明确额外得到 accepted answer，不与scripted公平排名。scorer 只在response之后读 evaluator，独立判 task_correct、response_status、unsupported和citation-membership；引用合法不证明支持或因果使用。失败/拒答/parse-error进入分母，不以删除失败改善结果。

## 执行、身份与恢复

每个 job 固定 case/arm/representation/delivery-mode/selection-policy/backend。run manifest绑定source、corpus、protocol、原生retriever、settings、parser/scorer、SQLite版本。每次attempt原子发布 started（含实际request/audit）、response receipt（含原响应字符串、评分与摘要绑定），目标已存在拒覆写。临时 staging 留作中断证据；已发布损坏必须拒绝。所有本地raw run写repo外。

resume不覆盖旧attempt。无完成receipt的started先标indeterminate；本地纯函数允许明确新attempt重算。任何外部provider提交未知，默认不重试，必须由操作者解析外部receipt后显式记录retry授权；mock测试覆盖这一点。单writer边界，拒绝并发lock；manifest未完整发布的非空目录拒绝恢复。replay不调用消费者，重新检查request/delivery/ranking/score与绑定；--check另重做本地真实FTS5和scripted计算，比对公开compact结果，不冒充raw replay。

## Provider 待执行合同

真实provider未授权、未选择账户或模型。本轮交付可执行的 injected JSON transport adapter，严格把固定messages/model/generation预算交给transport，区分429/拒答/context-overflow/parse失败/提交未知；只有明确authorized plan才能调用transport。默认没有network transport，CLI不发网。

provider-plan.json固定本地同一批scripted条件的精确请求材料（oracle排除）、cells和每request bytes，system/user prompt逐字保留，max_output_tokens=96，总输出token上界为cells×96；输入token、价格和费用上界必须在绑定实际provider/model/tokenizer后计量再授权。选择procedure为：用户选择可用provider → 固定exact model/revision与tokenizer → 计算输入总量和费用上限 → 新的不可变bound plan → 明确材料/费用授权 → 执行。当前计划status为awaiting-provider-binding-and-authorization；它是完整待绑定执行计划，不宣称模型/config已经冻结。mock只证明transport边界，不证明任何真实API兼容。

## 验收与研究范围

gold置换不改变writer/ranking/selected/delivery/request；改变预算或policy能追到实际送达变化。源码/协议变动后新run与raw replay。测试涵盖全条件、完整/截断、同key不同方法、等长sham、writer身份、世界与证据变更、source/rubric漂移、人review绑定、失败/重试/indeterminate、原子发布损坏拒绝、provider模拟边界。

报告按4个family分别给分子/分母、逐条件匹配的增量与交互，保留各stage，不给总体精度置信区间。至少从真实本地输出形成一个Observation→竞争解释→新DesignRevision的可加载链。该链是探索性研究判断，不自动成为已证明因果或人类采纳。P1旧equal-900结果及multilingual协议保持独立；本研究不改写它们、不把已有条件贡献思想当新理论。
