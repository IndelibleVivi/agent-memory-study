# 双语记忆使用策略，能怎样从反馈中学习？

Agent Memory Study editors · 2026-09-25 · **研究设计：proposed-not-run**。

[研究协议](protocol.md) · [表示与消费的共读](https://indeliblevivi.github.io/agent-memory-study/study/representation-and-use/) ·
[已有结构化学习实验](../decision-learning-study/README.md)

这一研究把问题从显式条件特征推进到自然语言：同一种使用条件换成中文、英文或自然混写时，
判断能否保持；条件真正改变时，又能否随之改变。中文反馈纠正后，还要检查英文／混写的
同范围判断与原本正确的邻近范围。

当前没有训练多语言 scorer，也没有证据证明模型已学会某位使用者的偏好。协议明确分开
公开原创诊断、私人真实材料的可用性检查，以及需要情境化反馈的个人取用研究。
静态 reading room 不连接私人记忆服务；原始记忆、标签、向量、小头权重和可反推内容的
逐例输出都不属于公开网站 artifacts。

拟议实现先使用冻结的多语言 encoder，将参数学习限定在独立小头。固定候选比较多数类、
cosine 阈值、保存反馈案例近邻和正则化线性头；更复杂的 attention 结构只在明确要回答
表示或容量问题时追加。模型复杂度、CPU 资源和数据规模均不是成绩保证。

官方 [multilingual E5 small model card](https://huggingface.co/intfloat/multilingual-e5-small)
给出 384 维表示、512-token 输入边界与 query/passage 使用方式；这些支持候选选型，
不证明在混写、否定、作用范围或私人效用标签上可靠。不得直接沿用不同编码器空间的旧权重。

运行环境和预算尚未批准为执行配置。后续真实执行需要单独记录模型 revision、输入身份、
训练和测试分组、实际 token 长度、截断、计时、峰值内存与 raw/derived 输出。
目前没有可下载的训练权重或结果 receipt；本文不是已经完成的模型实验。

## 离线案例校准工具

[`casebook.py`](casebook.py) 是本目录的 stdlib CLI，把一个**架构无关**的真实案例
JSON 检查并渲染成完全离线、无需服务的 HTML 人工校准界面。它只做材料校准：不训练模型、
不计算准确率、不联网、无 telemetry、无浏览器本地存储，也不写回任何源文件。这里的三项
实验（跨语言条件不变性、条件真正改变时的敏感性、中文反馈纠正后的范围传递）**仍未执行**；
本工具只是准备用于澄清 rubric 的少量人工校准卡，不产生效用真值，也不把结果升级成
训练 gold。

```bash
python3 -B research/multilingual-use-policy/casebook.py validate        --casebook cases.json [--reviews reviews.json]
python3 -B research/multilingual-use-policy/casebook.py review-template --casebook cases.json [--out reviews.json]
python3 -B research/multilingual-use-policy/casebook.py render          --casebook cases.json --out review.html [--reviews reviews.json]
python3 -B research/multilingual-use-policy/casebook.py check-reviews   --casebook cases.json --reviews reviews.json
python3 -B -m unittest discover -s research/multilingual-use-policy -p 'test_*.py'
```

方括号表示可选参数，不是 shell 命令的一部分。浏览器验收使用仓库既有
[`tools/browser-requirements.txt`](../../tools/browser-requirements.txt) 与 Chromium：

```bash
python3 -B tools/test_casebook_browser.py --output-dir dist/browser-check/casebook
```

它只使用原创合成案例，检查三种视口的编辑、确认、修改后退回草稿、下载／重载、筛选与纯文本展示。

### 数据合同

Casebook 顶层为 `{schema:"ams-memory-casebook/1", dataset_id, cases:[...]}`。每个 case 含
`case_id`／`group_id`（非空字符串）、`split:"exploration"`（本轮不划训练集）、`memory`
（`id`、`text`、`source_refs` 证据 id 列表）、`source`、`context`、`representations` 与
`correction_candidate`。顶层或 case 允许额外 `diagnostics`，原样保留。

- `source.coverage` 取 `resolved-message-window` / `quoted-excerpts` / `unresolved`；
  `complete_conversation` 固定为 `false`。已解析窗口的 `sequence_verified` 可以为 `false`；
  `true` 仅表示适配器核对了导出顺序／时间，不证明有效分支或完整事件。引用片段与未解析为 `false`。`evidence` 只表示**关联消息窗口**，不是完整对话，
  不得据此推断完整对话；时间可为 `null`，`role` 可为 `unknown`。合法的 partial 来源案例
  （例如 `unresolved`）留在材料池，不被整体拒绝。`coverage` 非 `unresolved` 时，
  `memory.source_refs` 至少引用一条证据，`validate` 会拒绝悬空 id。
- `context.text` 可为 `null`；`kind` 取 `retrospective-next-user` / `missing` / `constructed`，
  与有无文本必须一致。`kind:"missing"` 时 `text` 为 `null`、`refs` 为空。`context` 的
  `recipient`／`purpose`／`known_information`／`already_selected`／`budget_tokens` 按固定值，
  不用字符串长度伪装 token 预算。
- `representations` 为 `episodes`（原消息窗口）、`summary`（与 `memory.text` 相同的概括）、`coexistence`（并存）。
  适配器**必须**用 `casebook.build_episodes(evidence)` 与
  `casebook.build_coexistence(episodes, summary)` 构造这两个字段（episodes 按
  `id | role | time | text` 逐条、按顺序、`time` 缺失记 `unknown`），`validate` 会确定性核对。
- `correction_candidate.status` 取 `unreviewed` / `none`，`evidence_ids` 引用证据 id；它只是
  检索线索，**不等于真实纠正标签**。

review sidecar 为 `{schema:"ams-memory-reviews/1", dataset_id:同, reviews:[...]}`，每条含
`case_id`、`status`（`unreviewed`／`draft`／`confirmed`）、`reviewer`、`reviewed_at`、
`context_sufficient`、`label`（`null`／`useful`／`not-useful`／`insufficient-context`）与
`rationale`。sidecar 可以只包含被选中的部分 case；`dataset_id` 必须与 casebook 相同，
未知 case 与重复 case 会被拒绝。

### 视图含义与标注规则

HTML 为每个 case 呈现：**原消息**（`source.evidence` 关联窗口）、**派生 memory**、
**三种表示**（原事件／概括／并存并排）、**回顾性情境**（由下一条历史 user 消息构成）与
**纠正候选**（检索线索）。可切换 case、按 case/group/文本搜索、按 `source.coverage` 或
有无 `context` 过滤。所有数据以 `textContent` 呈现；嵌入 JSON 会转义 `<`，避免
`</script>` 注入。

初始标注一律为 `unreviewed`、`label=null`，没有默认 `useful` 或自动 `confirmed`。`useful` /
`not-useful` 的确认要求情境文本非空且 `context_sufficient=true`；`insufficient-context` 要求
`context_sufficient=false`，可在 `context` 缺失时确认。已确认（`confirmed`）必须主动选择，
并带上 `reviewer`、`reviewed_at`、非空 `rationale` 与 `label`；未审阅的 case 不自动带任何
标签。**缺情境与未审阅绝不能合并**：`insufficient-context` 是已审阅的结论，`unreviewed`
是尚未判断。编辑任一标注字段立即将状态改为 draft 并清空旧确认时间，必须再次明确确认；直接下载也保留合法草稿。查看者可在页面保存 `draft` 并下载独立 reviews JSON，再由 `check-reviews`
核查；`render --reviews` 可导入已有 sidecar 并保留状态供续审。

模型提出的标注只记 `draft`，`reviewer` 明确写出模型身份。人工复核应另存一份 sidecar，
保留原始模型草稿，并改写为实际审阅者身份；`confirmed` 表示所列审阅者主动确认，
本工具不认证身份，也不自动证明 owner 接受或标签已成为 gold。

### 边界

- `check-reviews` 只输出 aggregate（case/group 总数、状态与标签 counts）；不输出任何 raw
  text，也不导出逐 case 标签或训练 gold。相同 `group_id` 表示相关样本，**不等于独立样本**。
- 生成物路径由调用者指定；private 输入与生成的 HTML／reviews JSON 必须留在 repo 外，不入
  Git，公开仓库不包含真实记忆、标签或本地路径。
- 情境以 `kind` 区分回顾性历史消息、构造情境与缺失。回顾性重建可以包含有限前文；
  它并不证明当时生产系统已经拥有该派生记忆。
- 原导出的混合文本字段可能包含 thinking 或工具结果；适配器须明确选择用户可见消息，
  保留说话者、引用层级和 fiction／现实范围。结构校验不检查摘要是否忠实。
- 若概括含目标时点之后的信息、错归说话者或缺失关键附件，应在理由中单列材料问题。
  尤其是未来信息泄漏：修复来源和时间范围之前，不将这类拒绝直接作为普通效用负例或计算效用成绩。
- 本工具与存储架构无关：只读入/输出上述 JSON，不驱动任何 memory 服务、不接入私人 live
  memory 写路径，也不修改 `protocol.md`。
