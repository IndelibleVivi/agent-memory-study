# WP4 / E2：修订在多层记忆中的传播

Agent Memory Study editors · 2026-10-23 · 原创 development/diagnostic scripted controls。

本研究在固定结构化语义下追踪十次任务的状态演进，不推断自然语言识别、模型收益或生产错误率。
它不替换旧 correction-scope study，也不修改 representation-use study 的历史 receipts。

独立单位是九个原创 event families：事实替换、scope 缩小、临时例外到期、承诺撤销、上游前提纠正、
authority conflict，加上新消息无覆盖权、另一项目新消息、稳定未修订三个 controls。每条事件有
valid_from/valid_to 和 observed_time；gold 根据查询的 valid_time/observed_time 独立解释事件，
同样的 valid_time 在修订被观察前后可有不同答案。未来事件不倒灌旧 observation。没有改名、翻译
或重复任务扩充独立样本量；全部公开，不是 blinded confirmatory evaluation。

四条 policy：append-latest 取同 key 最新接收的记载，故意忽略 scope/project/authority/有效期；
versions 使用显式 supersedes、scope、authority、双时间，但不重算 rule 的上游前提；dependencies
在此基础上重算规则，并按 source identity/到期失效旧缓存与自身写回；source-reread 每次消费
canonical 来源重新解释。answerer 只接收实际 delivery 的 recommendation，没有 gold 参数。
三 oracle 控制分别在 extraction、retrieval、最终 context 注入独立 gold 的额外信息，显式标记，
不能作为公平 policy 胜者。oracle-extraction 仍可能被后续 stale summary 阻塞。

所有分支从同一 prerevision checkpoint 深复制。修订在任务一之前进入 canonical；scheduler
延迟 0/1/3 个任务，对应在任务 1/2/4 刷新 index/summary。dependencies 可因 source identity
或有效期提早失效重算；source-reread 消费时再读。延迟是离散任务数，recomputation 是实现调用
计数，不是 wall latency 或 tokens。主链与只读 probes 的重算成本分开保存。

每组合十二分支：natural，四个 store/index/summary/delivered stale injections，各自只修复
同一指定层的 matched repair，以及三个 oracle controls（共用 summary fault）。stale 在任务一
植入共同 checkpoint 的旧层；repair 在任务二直接只替换目标层，保存紧邻的 before/after，
后续正常传播另计。故障、修复和自然传播共享外生任务时间表，但输出和写回是各臂真实中介，
不能重新匹配成相同历史。delivered fault 是显式固定旧 delivery 的 synthetic fault；其 repair
释放该固定并只在任务二提供修正 context，以后仍暴露下层状态。

每次任务：canonical→index→summary→retrieval/delivered→action→memory write。另执行六个
只读 probes：preserved archive、相邻 beta scope boundary、历史 valid=0/observed=0、
valid=2/observed=1、valid=2/observed=2，以及 valid=0/observed=2 的按当前证据回看。
事实替换是 valid_from=0/observed=2 的 retrospective correction；旧观察时确实记为 blue，
但按现在证据 valid=0 的值已更正为 red。承诺撤销在 observed=2 先获知，valid_from=3 才生效，
两种时间控制都会改变可判定答案，而不是装饰字段。只有 main action 写入下一轮，不让 probes 污染分支。
预设任务 5/8 检索自身第一条 output write，是 synthetic pressure/control，不是自然发生率。
focused paired contrast 对同一 fact-replacement/versions/delay1/tombstone episode 关闭写回，
区分 index 持续错误和首次修好后旧 output 的回流。它不增加 family 数。

retention 独立消融：tombstone 保留原文和有 scope/valid-time 的撤销记录；delete 删除被新权威
修订 supersede 的旧条目。后者可能丢失合法历史和未覆盖 scope，不称隐私删除。两者都保留本次
运行的审计快照，不能声称 erased。

报告 1/3/10 个任务内的全 probes，changed/preserved 由独立当前 gold 与修订前合法目标（独立 gold；不是 policy checkpoint 的实际错误回答）的回答集
比较；boundary 是 preserved 子集，historical 与这些集合重叠，不可相加。planned/executed/scored
按 episode/family 计，probe rows 另列。version_stale_delivered 表示实际 delivery 的 source identity
落后于完整 canonical，或引用支持已到期；它不是错误的同义词（无关新消息可有 stale 但正确结果）。
errors_given_stale 的分母只含 stale deliveries。reappearance 要求同 query identity 和相同 expected-answer phase 内 main 先错、后至少修好一次、
再错；后一次还必须匹配修订前合法推荐，且绑定旧 source version 或旧 support。任意新错误只计
any_error_after_repair，不称旧影响再现；合法 valid-time 阶段变化重新计序列。持续错误另列。
该计数本身不证明每一错误的因果来源，focused writeback 对照负责
辨别预设 output 回流。used 始终 unknown，citation 不是 causal-use 证明。

manifest 绑定 fixture/source/protocol/scorer/settings。raw output 只写入新目录，各 episode 保存
started、完整 branch snapshots、delivery/action/write/score 与 digest receipt。whole-episode 完成
后写 completion；中断/partial 不覆盖也不续写，保留原目录并在新 output 原子重跑整轮。
verify/replay 先检查 digest 和身份，再重放确定性状态转移并从冻结 action 重新计分；这是脚本
状态机 replay，不是 provider hidden-state replay。摘要在 repo，原始实验目录留在 repo 外。
