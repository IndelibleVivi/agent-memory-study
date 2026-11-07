# AMS 原生操作与证据边界

**用途。** 本文件区分当前 tracked AMS 代码真正执行的操作、只存在于 scripted control 的操作，以及未来 Relata/Hindsight 或生产系统必须实核的 native 行为。它不创建 API，不推断未读私有实现。

共享方向见 [Relata campaign](https://github.com/IndelibleVivi/Relata/blob/main/research/relata-ams-campaign.md)。本文件只拥有 AMS 侧操作地图。

## 1. Evidence snapshot

- branch：`research/executable-memory-experiments`
- HEAD：`383ac14`
- merge state：该 HEAD 不在 `origin/main` 祖先链中
- PR8：属于当前 branch 内容，**未合并到 main，也未部署**
- PR7：独立工作，**未合并**

因此，本文记录的 P1/P2 证据属于准备分支，不是 main 已发布能力。源码以后变化时，本文 anchors 需要重新核对；既有 receipt 的 source identity 也不能静默沿用。

## 2. 证据等级

| 路径 | 原生/控制程度 | 已执行内容 | 允许的解释 |
| --- | --- | --- | --- |
| [representation-use-study](../representation-use-study/README.md) | stdlib deterministic control | 7,680 个 forward saved requests；raw/summary/coexistence；scripted/latest/abstain/oracle | 预算、送达、评分、恢复和负控制合同 |
| [experience-reuse-retrieval-study](../experience-reuse-retrieval-study/README.md) | 真实 SQLite FTS5 | 4 场景、12 池、108 次选择 | key-only BM25 返回竞争，不是 P1 集成结果 |
| [decision-learning-study](../decision-learning-study/README.md) | 真实本地拟合 | 小型 OVR logistic 与 tree；固定结构化特征 | 给定标签与表示下的学习/纠正，不是 NL 效用 |
| [c2c-cache-retraction-study](../c2c-cache-retraction-study/README.md) | 真实固定模型干预 | 固定 SmolLM2 的 200 个已保存 outputs | 本次计算中的 retained-cache 来源依赖 |
| [kv-prefill-transfer](../kv-prefill-transfer/README.md) | 真实随机闭环 + 单篇 pretrained native cache | 256-token target 磁盘读回与 full/split 数值差 | native cache 交接；不证明跨模型迁移质量 |
| [revision-propagation-study](../revision-propagation-study/README.md) | deterministic transition control | 2,592 episodes，真实状态演进与 replay | typed-event 传播、单层干预与 writeback 对照 |

这些等级不能互相替代。P1 的 scripted 结果不能证明 dense retrieval；FTS5 结果不能证明 NL summary；C2C cache 依赖不能证明文本 memory 撤回；KV native validation 不能证明 pretrained mapper 有用。

## 3. P1 当前实际操作

### 3.1 可见状态与操作

| 操作 | 源码锚点 | 实际可见/产生 | 是否可 fork | 写回 | 后台层 |
| --- | --- | --- | --- | --- | --- |
| 构造 event family | [corpus.py](../representation-use-study/corpus.py#L18)（L18 起） | typed events、wording、fixed/updated | 是，fixture 可深复制 | 无 | unknown |
| 生成表示 | [corpus.py:90](../representation-use-study/corpus.py#L90) | raw、固定 summary、coexistence records | 是 | 仅派生材料，不改 source | 无模型 summary controller |
| 解析 latent truth | [corpus.py:64](../representation-use-study/corpus.py#L64) | accepted answer / defer / conflict | 是 | 无 | 无 |
| 顺序控制 | [study.py:71](../representation-use-study/study.py#L71) | forward/reverse/rotate 后的 material order | 是 | 无 | 无 |
| candidate/selected | [study.py](../representation-use-study/study.py#L72)（L72 起） | candidate IDs；selected 目前等于排序后的全部 materials | 是 | 无 | 无独立 retriever |
| byte-prefix delivery | [study.py:76](../representation-use-study/study.py#L76) | actual fragments、complete/incomplete、memory bytes | 是 | 无 | 无 |
| scripted consumer | [study.py:114](../representation-use-study/study.py#L114) | 只读最终 JSONL，不接收 gold | 每 job 独立 | 无 | 无 |
| oracle consumer | [study.py:151](../representation-use-study/study.py#L151) | request 明确带 gold，作为上界 | 是 | 无 | 无 |
| scoring | [study.py:158](../representation-use-study/study.py#L158) | correctness、acceptable、over-abstain、citation | 否，评分只读 response | 无 | 无 |
| run/resume/replay | [study.py:275](../representation-use-study/study.py#L275) | request/started/response/receipt | 新 attempt；不覆写旧输出 | 无 | 无 |

关键事实：

- 当前 P1 的 `candidate_ids` 是 writer 输出列表，不是 BM25/dense 检索候选。
- top-k 选择尚未实现；`selected_ids` 目前是 material order 的全集。
- delivery budget 只截断序列化 memory prefix。
- `900` 是 UTF-8 bytes，不是模型 tokens；provider token budget 未验证。
- summary 是固定字段保留/删除规则，不是 summary model。

### 3.2 可复用的真实 FTS5

[experience-reuse-retrieval-study/study.py:14](../experience-reuse-retrieval-study/study.py#L14) 使用真实 SQLite FTS5：

```sql
CREATE VIRTUAL TABLE memories USING fts5(key)
SELECT rowid, bm25(memories) AS score ...
```

它只索引 `key`；`value` 不参与打分，budget 是返回记录条数。适合作为未来 adapter 的行为参照，不能直接宣称现有 P1 已有 BM25 candidate/top-k。

### 3.3 未来要实核什么

- BM25 的具体 tokenizer、索引字段、参数、scope filter、dedup 和返回数量。
- dense encoder 的 exact model revision、向量池化、归一化、距离、索引、threshold 与 ANN 参数。
- summary 是人工、模板、生成模型还是混合；其输入范围、版本和失败处理。
- reader tokenizer、system prompt、最大输入/输出、真实预算单位和 provider counting。
- candidate 在哪一步产生，selected 是否可能被 gold 重排。
- reaccess 的 current/missing/denied/known-stale/unknown-stale 是否有原生状态，还是得由 access log 重建。

## 4. P2 当前实际操作

### 4.1 Operations

| 层/操作 | 源码锚点 | 当前可见状态 | 可 fork | 写回 | 后台层 |
| --- | --- | --- | --- | --- | --- |
| prerevision checkpoint | [study.py:91](../revision-propagation-study/study.py#L91) | store/index/summary、writes、delivered | 是，每 branch deep copy | 不写 canonical | 无 |
| store creation | [study.py:50](../revision-propagation-study/study.py#L50) | events、tombstones、source/content identity、retention | 是 | 构造派生 store | 无 |
| extract / resolve | [study.py:19](../revision-propagation-study/study.py#L19) | recommendation label + support IDs | 纯函数 | 无 | 无 |
| materialize | [study.py:59](../revision-propagation-study/study.py#L59) | per-query rows、source identity、expiry | 是 | 中间派生 rows | 无 |
| index refresh | [study.py](../revision-propagation-study/study.py#L123)（L123 起） | scheduled task number、materialized index | 是 | 分支内 state | 无 async worker |
| summary sync | [study.py:135](../revision-propagation-study/study.py#L135) | index-derived copy | 是 | 分支内 summary | 无模型 summary |
| stale injection | [study.py:120](../revision-propagation-study/study.py#L120) | fault_injection before/after | 是 | 指定层 | 无 |
| matched repair | [study.py:142](../revision-propagation-study/study.py#L142) | single-layer before/after | 是 | 指定层 | 无 |
| delivery | [study.py](../revision-propagation-study/study.py#L151)（L151 起） | actual row、query、source_identity、expiry | 是 | 否 | 无 |
| action | [study.py:75](../revision-propagation-study/study.py#L75) | label + citations，默认 used=unknown | 是 | 否 | 无 |
| main-only writeback | [study.py](../revision-propagation-study/study.py#L190)（L190 起） | action-derived memory record | 是 | 写入 branch writes | 无 |
| read-only probes | [study.py](../revision-propagation-study/study.py#L151)（L151 起） | 六类历史/边界 probe，不写回 | 是 | 无 | 无 |
| retention ablation | [study.py:55](../revision-propagation-study/study.py#L55) | tombstone vs delete | 是 | 分支内 store | 无 |
| focused writeback | [study.py:237](../revision-propagation-study/study.py#L237) | writeback on/off 两次 run | 是 | on 有 10 writes | 无 |

### 4.2 各操作在层上的作用与限制

- **append-latest**：只看较新接收记录，忽略 scope/project/authority/有效期；是已知弱 policy。
- **versions**：使用显式 supersedes、scope、authority 和双时间，但不重算 rule 的 upstream premise。
- **dependencies**：在 versions 基础上重算规则依赖，并由 source identity/expiry 触发失效。
- **source-reread**：消费时重新读取 canonical；仍可能暴露下层 summary 或 premise 限制。
- **tombstone/delete**：tombstone 保留原文与撤销记录；delete 删除 superseded 条目。两者都保留运行快照，delete 不是隐私擦除。
- **writeback on/off**：focused contrast 只覆盖 fact-replacement/versions/delay=1/tombstone 的预设 pressure；不能估计自然回流率。

结构化 records、dict、graph 或 typed IDs 不等于 dense vector 或 NL summary。P2 的 summary 只是 index rows 的 copy，必须明确标注为 deterministic materialization，不能借“summary”之名升级为自然语言摘要。

### 4.3 共同 checkpoint 与外生时间线

所有 branch 从同一 pre-revision checkpoint 深复制；revision 在 task 1 前进入 canonical，scheduler delay 0/1/3 对应 task 1/2/4 刷新。延迟是离散 task 数，不是 wall latency 或 tokens。

分支的第一次 action 可以比较；一旦 main action 被写回，后续状态就是该分支的中介结果。不能在 writeback 后把分支重新匹配为同一输入，也不能用后续输出反向“配平”初始处理。

### 4.4 stale、reappearance 与负控制

- `version_stale_delivered` 表示实际 delivery 的 source identity 落后于完整 canonical，或支持已过期。
- stale 不等于错误；无关的新消息可以 stale 但结果正确。
- `errors_given_stale` 只在 stale delivery 条件下计数。
- old influence reappearance 要求同 query identity、同 expected-answer phase 内先错、后至少一次修好、再错；后错还必须绑定修订前合法答案和旧 source/support。
- arbitrary later error 另计 `any_error_after_repair`。
- changed 与 preserved 来自不向consumer暴露的作者gold；boundary 是 preserved 子集；changed、preserved 与 boundary 三者不可相加；historical 与这些集合重叠，也不可相加。
- 无覆盖权新消息、另一 project/scope 消息、合法历史查询是负控制；错误变化表示传播过宽。

### 4.5 时间与 access

未来 native 设计至少要保留：

- valid time：事实在世界/规则中有效的时间；
- observed time：系统首次看见记录的时间；
- commit time：存储提交时间；acceptance time另记用户／authority接受时间，二者不等价；
- exposure time：reader 实际看见或再次读取的时间；
- access result：allowed / denied / missing，不能由内容为空推断。

追溯更正可以改变“按现在证据过去是什么为真”，不能抹掉“当时记录了什么”。historical 与 current 必须分别评分。

## 5. Relata / Hindsight native 验证清单

以下均未在 AMS 当前 tracked 源码中实现；标题只列需要实核的类别，不推测具体 API：

| 类别 | 必须在目标系统核实 | 不能预填写 |
| --- | --- | --- |
| source capture | 精确 commit、模型/服务 revision、source IDs、字段类型、捕获时间、digest | “Mem0 默认返回某字段” |
| reader projection | 哪些字段实际进入 reader、是否截断、是否重排、是否重新摘要 | capture JSON 的所有字段都可见 |
| index refresh | manual/auto、single/batch、scheduled/runtime、失败重试 | fixture 的 scheduler 等于产品刷新机制 |
| freshness | 何时检测 freshness、谁能读 stale/unknown、是否自动 invalidate | 新版本写入即所有层立即 fresh |
| writeback | 是否自动保存、保存什么对象、由哪个 task 触发、是否覆盖旧值 | action output 一定自动写回 |
| background work | 是否有异步 consolidation/reflection、锁、队列、重启行为 | deep-copied Python state 等于后台服务 |
| dense/vector | 实际 encoder、向量库、距离、索引、持久化与权限 | recommendation dictionary 或 typed tags 是 dense index |
| NL summary | 生成者、prompt、输入范围、能见时机、来源绑定 | index dict 的 copy 是自然语言 summary |
| denied/access | 授权拒绝、租户/scope 隔离、审计记录 | 空结果表示 denied 或 missing |
| version exposure | commit/accept 与 reader exposure 是否分开 | observed_time 可由 valid_from 推出 |

manual/automatic 与 single/batch freshness 是未来 pinned Hindsight 验证项。当前 AMS 没有这些 runtime results；如果将来只在文档或 fixture 中模拟，也不得升级为产品事实。

## 6. 跨工作包交接

- **P0** 先提供 captured field manifest 和 allowed reader view；P1/P2 不得从 capture 的存在推断原生写入。
- **P1** 提供 candidate/selected/delivered funnel 与 reader outcome；P2 可复用 outcome 词汇，但不能复用 P1 family 样本。
- **P2** 提供共同 precheckpoint、外生 timeline、stale/writeback/reappearance 语义；P3/P4a/P6 各自拥有 estimand。
- **P3** 需要 accepted-goal 与 method-failure 的原生观察；不能只从回复文本推断。
- **P4a** 需要由untreated reference policy产生的共同checkpoint；P4b 需要独立 task-start assignment receipt。
- **P5** 的 repair correctness、expression familiarity、human task 和 burden 分开记录；不得由机器“熟悉度”代替人的负担。
- **P6** 的 probe 读取、reflection 输出、writeback 与后续 delivery 分开；只有绑定 lineage 的后续任务污染才可这样命名。

这些交接可以共享公开材料格式和 evidence vocabulary，但不需要统一 runner。一个统一 runner 会把“检索差异”“预算截断”“写回中介”“人类负担”提前压成同一实现。

## 7. 可复验命令

当前 P1/P2 source 未改动，可复用上一轮已经通过的合同检查：

```bash
python3 -B -m unittest discover -s research/representation-use-study -p 'test_*.py'
python3 -B research/representation-use-study/study.py check-sample
python3 -B -m unittest discover -s research/revision-propagation-study -p 'test_*.py'
python3 -B research/revision-propagation-study/study.py check-sample
```

独立证据入口：

```bash
python3 -B research/experience-reuse-retrieval-study/study.py --check
python3 -B research/decision-learning-study/study.py --check
python3 -B research/c2c-cache-retraction-study/study.py --verify-checked
```

统一入口使用项目已声明的开发环境运行：

```bash
python3 -B tools/verify_reader.py
```

开发依赖与常规安装入口见根README；保存摘要核验、完整raw replay与fresh模型执行是不同证据。

不要在大矩阵条件未改变时重跑 P1/P2 raw replay；`check-sample` 只验证 saved-summary identity 与守恒，不替代今后 source/protocol 改变后的 fresh raw replay。
