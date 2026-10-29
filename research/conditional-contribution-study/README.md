# 条件信息贡献、真实检索与实际送达

Agent Memory Study editors · 2026-10-29 · 本地原生检索与 scripted/oracle 控制已执行；真实 provider 未执行。

[研究正文](../../study/entries/conditional-information-and-use.md) · [协议](protocol.md) · [完整逐 job 结果](sample-results.json) · [实际观察到下一设计](observation-chain.json)。独立四个构造 family、九个 case、864 jobs；**经验样本数 0**，不能把展开的条件当独立语义材料。

本目录真实复用 [experience-reuse](../experience-reuse-retrieval-study/study.py) 的 `rank/select`，执行 SQLite FTS5/BM25。它继续 [representation-use](../representation-use-study/README.md) 的 actual-delivery/receipt 边界与 [multilingual-use-policy](../multilingual-use-policy/protocol.md) 的条件贡献问题，但不复制或改写它们的结果，不把旧 equal-900 样本当本轮截断观察。writer、问题/世界、评分、消费者与新结果由本研究单独拥有。

## 运行

Python 3.11+ 标准库，sqlite3 必须有 FTS5；不自动换替身、安装依赖或调用网络。

```bash
python3 -B research/conditional-contribution-study/study.py --check
python3 -B -m unittest discover -s research/conditional-contribution-study -p 'test_*.py'
python3 -B research/conditional-contribution-study/study.py run --out /path/outside/repo/fresh-run
python3 -B research/conditional-contribution-study/study.py replay --out /path/outside/repo/fresh-run
python3 -B research/conditional-contribution-study/study.py run --out /path/outside/repo/fresh-run --resume
python3 -B research/conditional-contribution-study/study.py packet --output /fresh/path/research-packet.json
python3 -B research/conditional-contribution-study/study.py provider-plan
```

默认 `report` 重做本地真实检索及消费者，只向 stdout 输出。`--check`/`check` 比较公开结果，不是 raw replay；`replay` 不调用消费者，重新核排名、实际请求、delivery、评分与绑定。`--output` 原子排他发布；已存在拒绝，不能拿它静默覆盖结果。测试临时目录默认使用执行环境提供的 `AMS_P9_TEST_ROOT`（未设置时使用系统临时目录），不依赖私人固定路径。

raw run 只能在 repo 外。manifest 固定源码、corpus、protocol、provider 边界源码及原生 retriever 身份、SQLite 版本、settings和job清单。started 保存实际request/audit；receipt 保存原响应字符串、评分及身份。单 writer 的 flock 在进程退出时释放。关闭/中断后 `--resume` 保留旧 attempt，成功 job 不重跑；本地纯函数的未知尝试先封存 indeterminate，随后另建 attempt。损坏的已发布文件拒绝；未完整发布 manifest 的非空目录拒绝，使用新输出。staging 文件保留，不承诺掉电恢复或跨主机锁。

## 固定研究因素

四个family：complement（四世界XOR）、redundancy、revision（baseline/world-change/evidence-corruption）、methods（相同key不同条件）。development/diagnostic 在family层固定，所有材料均被设计者看过，不是held-out。

每case：empty/B/S/BS/duplicate/等byte sham × raw/compact × full/200-byte equal × top-k/unique-key × scripted/oracle。top-k=3；只有key进FTS索引，BM25分数越小越前，同分按插入顺序。full仅保证选择后的材料完整，不保证全语料。compact只是移除prose，不是自然语言摘要模型。sham在writer后按S的JSONL准确UTF-8长度填充，可能竞争排名，不叫无处理。

每row保留候选ID/key/content digest、实际score/rank、selected、top-k、policy、完整到场记录、截断、memory/request bytes、writer输入输出身份与used unknown。记录数、bytes与真实模型tokens分别讨论。

## 实际结果与范围

| 对照 | 实际本地输出 |
| --- | --- |
| XOR full/top-k | B或S单独暂缓，BS四世界均正确；重复B与等长sham不能替代y |
| XOR equal/raw | BS第二条不完整到场，scripted暂缓 |
| XOR equal/compact | 相同必要字段两条完整到场，回答正确 |
| redundancy | B、S、BS均正确，S相对B增量0；交互为−1，不是“噪音负价值” |
| revision | world-change重算gold后Saturday正确；corruption同输出Saturday但gold仍Friday，错误 |
| same-key methods | top-k完整保留open/locked方法，unique-key只留首条open，锁门任务暂缓 |

`aggregates`按family/representation/mode/policy/backend/arm保留planned/successful/task_correct/abstain分母；`contrasts`按同case与同因素匹配，分别报告 `increment_S_given_B` 和 `interaction`。oracle额外拿到gold，仅作为边界对照；不与scripted公平排名。task_correct和citation-membership分别计，`unsupported_answer`仅指这份world合同下的错误作答，不是自然语言支持判断器。

[observation-chain.json](observation-chain.json)固定真实raw请求/响应/评分、局部receipt相对路径和digest，比较raw/compact到场记录，列出表示损失、送达损失与消费失败三种解释，再提出尚未执行的padding×budget设计。它是探索性研究判断，非自动因果认定。

## 稳定接口

`adapter.py` 提供 `describe_capabilities / validate_plan / execute`，operations与实际dispatch一致：

- `report-local`：真实FTS5+本地消费者；
- `run-local`：`out`、可选 `resume/limit`，写repo外raw；
- `replay`：`out`，核既有raw，不调用消费者；
- `check-sample`：重算对照公开sample；
- `provider-plan`：逐cell固定prompt和材料的待绑定计划；
- `packet`：corpus/protocol/sample/provider-plan，只读数据。

样例 `{"operation":"run-local","out":"/path/outside/repo/new-run","limit":2}`。未知操作/字段拒绝；平台job与注册由集成层拥有。instrument envelope含schema、原plan、科学source绑定与result。原生纯函数为writer/materials/prepare/scripted/gold/score；writer不接问题或gold，scripted只接固定messages，oracle的extra information显式不同。原生retriever漂移会使run校验失败。

## Provider 的准确状态

[provider-plan.json](provider-plan.json)含 **432 个精确cell**、逐字system/user messages、输入bytes、delivery digest、每cell输出上界96 tokens、总输出上界41472 tokens；不包含oracle。来源限原创corpus。

**provider、model revision、tokenizer、输入token数与费用上限仍未绑定，authorized=false。** 这是真实未决前置，不应标成已经冻结某模型。它没有阻断本地研究；也不能把bytes换算成虚构价格。下一步按协议选择实际provider/model/tokenizer，计量全部真实输入与费用上限，形成新不可变bound plan，再获得明确授权。

`provider.py` 是可执行的 injected-json-transport 边界，不是某个未经核对的真实HTTP API。它不读取key、不带网络transport、不查账户；接入实际服务还需其经官方文档核对的wire mapper。`execute_cell` 只接受完整已授权binding，交给注入transport后保存request/response及digest。模拟验收覆盖成功、拒答、parse失败、429、context overflow、tokenizer变更、超时提交unknown及显式重试；unknown默认阻断再次transport。人工review helper绑定content/rubric，但本轮无人工审阅数据。

## 验证及交付边界

24项测试覆盖上述因素、gold隔离、原生排名、sham、重试/中断、损坏/源身份/评分变化、原子发布、锁、输出边界与provider模拟。实际raw-final完整执行864 jobs，随后raw replay与独立local recomputation一致。无providerlive、真人或私人材料。公开结果只有有限构造含义，不报告总体成功率精度、语义摘要收益或真实模型因果使用。

独立source/结果/CLI/packet/文章完整；metadata注册、统一verifier、Lab UI及Observation→案头接续由主线程集成，未在本目录宣称完成。
