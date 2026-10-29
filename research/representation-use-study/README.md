# 概括之后，往事还记得准吗？

Agent Memory Study editors · 2026-09-25 · **离线控制已实现；自然语言比较：proposed-not-run**。

[进入跨源共读](https://indeliblevivi.github.io/agent-memory-study/study/representation-and-use/) ·
[原事件／概括／并存的比较协议](protocol.md) ·
[双语记忆使用策略的独立问题](../multilingual-use-policy/README.md)

这项研究追问：概括是否帮助新推论，同时保住历史来源和当前适用范围？目前交付论文串读、可检验协议与 stdlib 离线 scripted/oracle controls；
没有生成模型输出、参与者数据或模型效果数字。文献的实际阅读范围
与定位统一由 `study/entries/representation-and-use.json` 的 `externalReadings` 维护，页面展示同一来源。

现有 [Jev 源码实验](../jev-memory-contract-study/README.md)看到了指定判断下原节点与派生
节点并存；[学习与纠正实验](../decision-learning-study/README.md)看到了给定特征空间内的
参数变化。前者未测回答收益，后者未测自然语言语义识别。本协议提出两者尚未回答的消费端问题。

原事件、概括和并存三臂同时测来源辨识、当前适用与跨事件推论。概括删除的信息单列为
表示损失，不能要求模型凭空补回；信息充分时的错误、信息不足时恰当暂缓，以及无依据编造
分别计数。完整输入和固定预算比较分别报告，位置置换仍属于同一个事件组。

新论文不会因为在共读中被引用就自动加入 bibliographic materials / Zotero，也不改变
既有材料的 `noteDepth`、paper findings 或历史 receipts。生物记忆和模型内部表示提供
问题与评价方法，不直接证明某种 agent memory 设计有效。

自然语言比较执行前仍需固定 answerer 的具体模型与版本、真实 tokenizer、输入预算及运行资源。
下方离线 fixture 已固定原创事件、gold、信息充分性与 diagnostic byte budget，验证工程链路；
它不替代上述模型实验选择。开发结果后的协议修订保留为探索性记录。

## 离线 executable diagnostics（2026-10-23）

现在新增 WP1–WP3 的 stdlib 离线 pipeline。上文关于自然语言 answerer 的未执行边界继续有效；
这里的 `sample-results.json` 只报告原创 synthetic fixture 的 **scripted/oracle controls**，
没有模型调用或私人材料。完整执行定义和限制见 [protocol 执行附录](protocol.md#2026-10-23-离线执行附录wp1wp3-development)。

从 repo 根执行，无需安装依赖。先检查实际 job 清单（不创建 run、不调用 backend）：

```bash
python3 -B research/representation-use-study/study.py dry-run \
  --modes full equal --orders forward --budget 900
```

默认三位置，共 23,040 planned offline requests；`--orders forward` 是 7,680 requests。
64 cases、320 question rows 来自 **8 event families**，不是 320 个独立事件。两种措辞、2×2
历史/task set、各问题和排列都绑定 family；current task set 含当前行动与相邻 scope boundary
两题，expanded 保留这两题并加入六种历史、来源与关系用途（共八题）。common queries
保持配对，新增用途单列；不能将任务分布变化解释为 matched treatment effect。所有输入公开，仅供 development/diagnostic。
`UTF-8 bytes` 是 exact diagnostic unit，**不是模型 tokens**。equal budget 只限制 memory，
每条 receipt 另存完整 request bytes，provider token budgeting 未验证。预算恰好送达 record 的
closing `}`、仅缺终止换行时仍计 complete，与消费者解析一致；实际 memory 不补换行，缺 closing
`}` 或截断 UTF-8/JSON 的 record 仍计 incomplete。

复现已保存的单位置 compact sample（将示例路径换成容量足够的外部卷新目录；raw 包含数万个
小文件，不建议写系统盘 temporary directory）：

```bash
python3 -B research/representation-use-study/study.py run \
  --out /path/to/external-evidence/ams-representation-sample --modes full equal --orders forward --budget 900
python3 -B research/representation-use-study/study.py replay \
  --out /path/to/external-evidence/ams-representation-sample \
  --check-report research/representation-use-study/sample-results.json
```

`verify` 与 `replay` 都验证身份、artifact digests、actual delivery 与 score，且不调用 backend。
manifest 保留 exact Python runtime；resume 要求一致。replay 可在相同 source 下跨 Python patch
重算；公开 sample 的 portable identity 排除 runtime 与 run ID，不能据此声称两个本地执行环境相同。
console report 较长，可用 `--report /tmp/new-report.json` 写入一个新文件。公开汇总不含 raw
experiment dirs；raw JSON requests/responses、启动记录与逐条分数都在用户指定 output。
不要把真实输入、receipt dirs 或其他私人资料复制进本目录。

可用 `--backends scripted latest abstain oracle`、`--orders forward reverse rotate` 和
`--modes full equal`；每 arm 是 raw / summary / coexistence。`oracle` 在 request 中显式得到
gold，只是额外信息上界。scripted reader 拿不到 gold；latest 和 abstain 各有已知失败对照。
引用合法不代表使用，`used=unknown`。报告 full task set 与 all-arms-sufficient 子集，并按
family、task set、common/added questions 与 history transition 保留计数；每 bucket 有 planned、
executed、scored denominators 和 outcome statuses，quality 只聚合 scored responses。充分性子集
由 planned delivery 独立确定，不筛掉失败任务。acceptable 与 task_correct 各自报告。

验证中断恢复时，保留同一 settings：

```bash
python3 -B research/representation-use-study/study.py run \
  --out /path/to/external-evidence/ams-representation-resume --modes full --orders forward --fail-once --limit 2
python3 -B research/representation-use-study/study.py run \
  --out /path/to/external-evidence/ams-representation-resume --modes full --orders forward --fail-once --resume
python3 -B research/representation-use-study/study.py verify --out /path/to/external-evidence/ams-representation-resume
python3 -B research/representation-use-study/test_study.py
```

`--limit` 只限制本次新 attempt 数，不改变 manifest。成功 job 不重跑；失败/timeout/refusal/
parse_failure/interrupted 与 retry_of 保留。中断不代表从未执行；启动记录存在而 receipt
缺失时，先封存 outcome unknown 再 retry。identity、文件或 request 改变会拒绝 resume；需
新 output，不能改旧 raw receipts。run 不支持多个并发 writer。完整性不等于可信签名。
测试覆盖拒绝 corrupt/foreign receipts、预算边界、原话损失、2×2、gold 与 backend 隔离、
失败、各 artifact 真实写入中途、发布前/后以及 request-only 窄窗口恢复。统一 reader 验证可调用以上 `test_study.py`；本目录不修改
root verifier 或其他 study 的 historical receipts。

artifact 采用同目录 staging：先写 `.name.<uuid>.pending` 并 fsync，再用 hard link 原子发布正式
路径；目标已存在时拒绝，保持 no-overwrite。发布前中断只留下 staging，正式路径不存在；
发布后中断时正式路径已完整。成功发布清理 staging；中断 staging 留在原地，不解析/执行其中
内容，并在 interrupted receipt 的 `incomplete_artifacts` 中绑定原始 bytes。部分 UTF-8 也按 bytes
保存和核对。request、started、response、receipt、manifest 和 `--report` 都使用同一发布路径。

resume 不补造缺失的 request/started 正式文件：旧 attempt 保留原状，只新增 interrupted receipt；
尚未发布 request 时该 receipt 的 request 为 null。随后新 attempt 重新开始并引用 retry_of。
成功 receipt 已发布后即使清理 staging 前中断，job 仍完成，不重跑 backend。已正式发布的损坏
JSON 或 digest 不符仍拒绝，不能被当作未完成写入吞掉。完整 manifest 尚未发布的启动中断
不构成可信 run：保留该目录/staging，使用新 output；不从半个 manifest 推断 settings 或执行任务。
这里验证的是进程中断下的原子发布，不承诺突然掉电、文件系统损坏或跨主机并发恢复；output
文件系统必须支持同目录 hard link，run 继续限定 single writer。

统一验证也可运行快速、无 backend 的 saved-summary check：

```bash
python3 -B research/representation-use-study/study.py check-sample
```

它校验 portable identity、汇总守恒与正负 controls；它不是 raw receipt replay，不替代上面的
完整 reproduction。测试使用系统 temporary directory，不依赖固定机器路径。


已保存 sample 的 full/forward（每臂 320 question rows、8 families）中，scripted reader
在 raw/coexistence 各有 320 latent-gold 一致回答，summary 为 240；naive latest 在 raw
为 204，always-abstain 在充分且 gold 允许回答的材料上出现 248 次过度暂缓。各臂共同充分子集为 170 rows，
scripted 三臂均为 170/170。这里包括合理的 clarify/abstain gold；不能把这些计数称为自然语言
模型准确率、agent 收益或独立样本统计功效。sample 的 900-byte forward 设置保留了 raw
所需信息，full/equal 结果相同；更小预算的截断损失由 regression tests 单独验证。

`over_abstain`（scorer v2）要求实际 evidence 为 sufficient、gold 允许 answer、response 却
clarify/abstain。conflict/unknown gold 本来需要暂缓：reason mismatch 仍会使 task_correct
和充分/冲突材料下的 acceptable 为 false，但不计过度暂缓。截断后 insufficient 的适当暂缓
可 acceptable；不扩大 latent gold accepted set，也不计 over_abstain。
