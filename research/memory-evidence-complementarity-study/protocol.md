# Protocol: from hidden support to readable evidence

日期：2026-11-05 · Cove · AI-assisted research

**状态：Proposed, not run。** 本文件是后续 Agent 可以实施的实验协议，不是已执行结果。当前只有 [study.py](study.py) 的精确有限计算已运行。没有选择、调用或比较模型；没有产生 provider cost 或真实记忆任务效果。

## 1. 需要区分的解释

本协议区分四种解释，避免把每个失败都称为“检索不好”：

| 解释 | 预期观察 | 不能据此直接推出什么 |
| --- | --- | --- |
| 选择器没有区分世界的信息 | 完全相同的低阶 transcript 下，选择无法依赖隐藏支持；揭示任务语义后可改善 | 模型缺乏一般推理能力 |
| 语义已经可见，但组合没有被正确选择 | 完整语义条件低于支持 oracle，且 oracle 交给读者后能完成任务 | 所有 pairwise 图方法不可能有效 |
| 选择已完整，读者仍未正确应用 | 支持 oracle 的选择完整性为 1，但回答仍错误或弃答 | 候选生成或排序导致了这部分失败 |
| 测量把标准证据误当唯一证据 | 选择替代路线时 nominal recall 低或为零，支持完整性仍为 1 | recall 指标在任何用途上都没有价值 |

低阶界已经有解析证明，不需要重复支付模型调用来“证明定理”。模型阶段真正要研究的是：增加什么可读信息之后，选择能离开那个受限接口；完整证据交给某个读者之后，又有多少可用价值实现了。

## 2. 固定研究单位与预算

研究单位是一个**作者构造的世界及其配对条件**，不是一个独立的现实任务样本。第一轮限定三类结构：唯一三元支持、两个替代支持、模块化加法效用。实体重命名、候选排列、预算变化和重复 decoding 都是同一结构的变体，不得累加成独立任务数量。

主预算按候选条数计算。主设置为 `n=6,b=3`；预算敏感性只增加 `b=2,4`。保留渲染字符数、字节数和实际 tokenizer token 数作为观测，但不得称为 token-matched 或 token-budget 实验。若下一轮要研究 token 预算，应另行固定 tokenizer、完整请求计数规则、截断策略和每条候选的实际成本。

固定 reader 的系统提示、用户问题、已有侧信息和模型版本。只改变选择器可见信息或交给 reader 的已选候选。每次 selector/reader 请求使用独立上下文，不保留前一世界的回答、支持标签或反馈；无需建立长期记忆服务。

## 3. 材料 A：完全不透明的低阶接口

### 3.1 对外输入

主输入为六个等成本候选 ID，且没有内容或其他可区分特征：

```json
{
  "question": "Choose at most three candidate IDs to maximize the hidden set utility.",
  "candidate_ids": ["m01", "m02", "m03", "m04", "m05", "m06"],
  "cost_per_candidate": 1,
  "budget": 3,
  "known_family": "Exactly one unknown triple is sufficient; utility is one if all members of that triple are selected, otherwise zero.",
  "observed_utilities": {
    "empty": 0,
    "every_singleton": 0,
    "every_pair": 0
  },
  "output_contract": {"selected_ids": "array of distinct candidate IDs"}
}
```

私有 scorer 依次令 `T` 为六选三的全部 20 个三元组，返回 `1[T⊆S]`。`T` 不得进入 prompt、文件名、排序、候选元数据或调用顺序。低阶观测可以压缩成上面的说明，也可以展开为全部 22 个集合（空集、6 个 singleton、15 个 pair）；两种渲染必须分开标记，不能混作同一种输入。

### 3.2 最小实现与泄漏检查

对于同一个输入 payload 和固定输出 `S`，直接在本地对全部 20 个支持评分。若 `|S|=3`，总成功数必须恰好为 1；若 `|S|<3`，必须为 0。无需把完全相同的 prompt 调用 20 次。若做多个 decoding seed，每个输出单独计算该计数；它们不是 20 个新的研究任务。

在提交任何模型请求之前，序列化 selector-visible payload 并取 SHA-256。全部隐藏世界的该哈希应完全相同。检查 renderer、日志字段和工具响应只暴露协议允许的内容。固定支持信息只能在 scorer 一侧存储。

任何违反这个精确计数的结果，都优先说明 scorer、预算解析、隐藏信息隔离或世界权重有误。它不是模型打破数学界的证据。

## 4. 材料 B：可读的三元连接

### 4.1 一个完整输入实例

任务规则只允许根据给定记录推出结论；未建立连接时应输出 `unknown`。所有实体和校验码为本轮原创的无外部含义字符串。固定 reader 问题为：

> 根据记录，设备 N0 的校验码是什么？只使用可追溯的连接。无法建立完整连接时输出 unknown。

完整候选池：

| ID | 记忆内容 | 固定世界中的角色 |
| --- | --- | --- |
| m01 | 设备 N0 使用控制表 L0。 | 支持 1 |
| m02 | 控制表 L0 指向出口节点 V0。 | 支持 2 |
| m03 | 出口节点 V0 的校验码是 Q7。 | 支持 3 |
| m04 | 设备 N8 使用控制表 L8。 | 干扰条目 |
| m05 | 控制表 L5 指向出口节点 V5。 | 干扰条目 |
| m06 | 出口节点 V8 的校验码是 Q2。 | 干扰条目 |

此世界的真值为 `Q7`，最小支持为 `{m01,m02,m03}`。在 scorer 的封闭语义下，缺少任一支持条目都不能从所选记录完整推出答案。真实模型仍可能猜中 `Q7`，所以**正确字符串与证据充分必须分开打分**。

selector 的自然语言指令为：

> 为回答问题选择最多三条记忆。输出 JSON：`{"selected_ids":[...]}`。仅列出提供的 ID，不重写记忆，不添加未提供的事实。

reader 只收到原问题和实际选中的原始记忆文本，输出 JSON：`{"answer":"...","cited_ids":[...]}`。记录引用是可见行为，不据此宣称因果使用。不得要求或保存私有思维链。

### 4.2 平衡支持位置与文本线索

在六个候选位置中放置支持的全部 20 个三元组合；每个世界使用三个预先固定的候选展示次序，共 60 个渲染。它们是一个模板的平衡变体，不是 60 个独立任务。具体 permutation 清单在实现时先写入固定 fixture 文件，再运行条件比较。

每个配对世界复用相同实体名、文本、query、候选池与 budget。实体别名和校验码可作为一次性生成的固定材料，但生成种子与词表必须保存。不得让支持条目总是有更短 ID、特殊语气或固定位置。固定校验码备选值至少有两个；不得仅因只有一个候选包含答案形字符串，就把模型猜对解释为完整推理。

### 4.3 三个信息条件

| 条件 | selector 可见信息 | reader 可见信息 | 作用 |
| --- | --- | --- | --- |
| `low-order-only` | 材料 A 的不透明 ID 与低阶效用 transcript | 与当前世界一致的已选原始文本及原问题 | 规定的信息接口基线 |
| `full-semantics` | 原问题与全部候选文本 | 同上 | 检查任务语义能否使选择识别完整支持 |
| `support-oracle` | 本地程序直接选真实支持，不调用 selector | 同上 | 分离选择不足与读者应用不足 |

`full-semantics` 与 `low-order-only` 本来就在信息量上不同；这是要研究的干预，不能称为同信息量的模型能力比较。两者使用相同 reader 输入规则和最终条数预算。`support-oracle` 不是可部署检索器，也不能混入 learned-system 排名。

可选地增加 `full-semantics + declared structure`：在原问题中明示“按设备→控制表→出口节点→校验码连接”。这测试任务说明带来的收益；它必须标为增加了指导性侧信息，不能并入原 `full-semantics` 条件。

## 5. 材料 C：替代充分路径

固定问题仍为设备 N0 的校验码，五条候选如下：

| ID | 记忆内容 |
| --- | --- |
| a | 设备 N0 使用控制表 L0。 |
| b | 控制表 L0 指向出口节点 V0。 |
| c | 出口节点 V0 的校验码是 Q7。 |
| d | 设备 N0 的备用索引是 W0。 |
| e | 备用索引 W0 记载的设备校验码是 Q7。 |

在该封闭规则中，`K={{a,b,c},{d,e}}`，两条路线均有效且一致。不得额外写入优先级或“只允许主路径”的规则；否则会改变最小支持族。

先用本地指定的 selector 重现以下七行，再让模型在同样的 pool/budget 上选择。表中 `selected` 是 sanity fixture，模型阶段不把它暴露给 selector。

| 行 | pool | budget | 指定 selected | 预期层次 |
| --- | --- | --- | --- | --- |
| 1 | abcde | 3 | de | 替代路径有效，nominal abc recall 为 0 |
| 2 | abcde | 3 | abd | 并集 recall 为 3/5，但没有完整路径 |
| 3 | abcde | 3 | abc | 标准路径有效 |
| 4 | bcde | 3 | de | 标准路径已不完整，替代路径仍可用 |
| 5 | abd | 3 | abd | 候选池没有任何完整支持 |
| 6 | abc | 2 | ab | 候选池有完整支持，但预算不允许 |
| 7 | abcde | 2 | ab | 存在预算可行的 de，实际选择却错失 |

记录 `pool_has_support`、`pool_has_budget_feasible_support`、`selected_has_support`、nominal `abc` recall 和并集 recall。所有指标由明确的支持族计算，不调用模型评审。若回答正确但没有完整支持，单列为 `correct_without_annotated_support`，调查猜测、内部知识、生成材料遗漏或评分问题，不能将它计作经过验证的证据使用。

## 6. 局部诱饵与模块化正控制

这两个对象沿用已执行的 [study.py](study.py) 定义，先作为纯本地控制，不需要模型。

三元支持加诱饵：`F(S)=max(1[T⊆S],ε|D∩S|)`，`ε∈{1/20,1/10,1/4}`，`b=3`。预期单条/双条 package greedy 取三个诱饵，三条前瞻取支持。全子集 utility table 已保存在结果文件。

模块化正控制：五条候选权重为 `6/20,5/20,4/20,3/20,2/20`，`b=3`。逐条贪心与穷举最优都为 `3/4`。若实现连这个控制也不能通过，应先修复算法或 cost contract，不解释高阶条件中的失败。

若要让模型与 value oracle 交互，须明确它每轮允许查询多大集合、是否可以查看已选集合的条件边际、总查询预算以及全部工具响应。允许在一个已有两条支持的集合上查询第三条的条件边际，已经是三条集合信息，不能仍标为“仅双条效用”。

这里的软诱饵收益不是材料 B 的自然语言正确率。两者解释不同，不将 `3ε` 当作读者答题分数，也不把三条前瞻的局部成功外推为通用算法结论。

## 7. 主要观察量与分析计划

### 7.1 主要观察量

主要观察量为 `selected_has_support`。在同一套固定三元世界上，报告 `full-semantics` 与 `low-order-only` 的配对差，以及两者到 `support-oracle` 的差。各结构分别报告，不用简单总平均掩盖替代路径和唯一支持的不同性质。

次要观察量：

- 预算合规、重复 ID、未知 ID、格式错误、弃选数量；
- 每个候选的被选择频率，及其对展示顺序/别名的敏感性；
- `pool_has_support` 与 `pool_has_budget_feasible_support`；
- nominal recall、union recall 和支持完整性的分歧行；
- reader 答案正确性、`unknown`、引用有效性及 `correct_without_annotated_support`；
- 请求字节、token、模型版本、延迟、调用次数和实际费用（若执行）；
- 全集合效用查询数及所查询集合的最大大小（若使用 value oracle）。

格式错误按失败保留，不静默重试直到成功。若预先允许一次修复格式，修复轮须作为单独条件，保留两次响应与额外成本。

reader 的答案标签随世界保存为 `y`，不在实体重命名后继续硬编码示例中的 `Q7`。至少分开报告以下四个量：

- `latent_exact_match = (answer == y)`：只比较该世界真值，与是否选中支持无关；
- `supported_completion = selected_has_support and (answer == y)`：完整支持与正确答案同时成立；
- `appropriate_abstention = (not selected_has_support) and (answer == "unknown")`：在本协议封闭支持语义下，没有足够记录时的弃答；
- `correct_without_annotated_support = (not selected_has_support) and (answer == y)`：答案碰巧正确、背景推得、支持标注遗漏或选择过程传递了额外信息的待审计行。

这些量不可合并成一个未加说明的 accuracy。支持完整但弃答、答案错误以及格式错误也分别保留；不得用 appropriate abstention 的增加掩盖 supported completion 的减少。

2026-11-07 补充：[选择渠道的有限见证](../memory-side-information-study/README.md)说明，selector 可能通过身份、顺序或选中的正文传递未交付观察的作用。故上面的待审计行还须核对 selector 输入与 reader 实际消息；不能仅因 ID 单独无预测力或已隐藏 ID 就排除这种机制。它不改变材料 A 的不透明界：只要全部世界的 selector 可见输入仍完全相同，selector 就不能取得区分这些世界的信息。若扩展了输入，必须重述界的适用条件，不把效果直接归于已选正文的支持完整性。本协议仍未进行模型执行。

### 7.2 统计与推广边界

对穷举世界报告精确计数和配对差，不为穷举标签本身添加抽样置信区间。若模型 decoding 是随机的，可对固定任务集上的运行随机性给出区间，并明确它不表示对真实任务分布的泛化不确定性。多种候选顺序、别名和重复调用不升级为独立研究任务。

不能从 `P(E_pool)P(E_budget|E_pool)P(E_selected|E_budget)` 的分解直接宣称某模块“解释了多少增益”。因果比较需要在同一世界中替换单一环节。例如固定候选池和 reader，只替换 selector；或固定最终选择和 reader，只改变其中某一条桥接证据。每个干预都保留反事实输入，而不是只保存总分。

## 8. 失败条件与停止解释的规则

| 观察 | 必须先处理的问题 | 此时禁止的解释 |
| --- | --- | --- |
| 不透明输入的所有世界哈希不同 | 找出 support、顺序、元数据或 renderer 泄漏 | 这是纯低阶界实验 |
| `n=6,b=3` 同一个输出在 20 个世界中不恰好成功一次 | 检查 hidden support 列表、解析、预算和评分 | 模型突破成功率上界 |
| 原始文本 oracle 也答不对 | 检查任务规则、答案歧义、渲染和 reader 使用 | 问题一定在 candidate generation |
| 未完整支持却答对很多 | 检查猜测、答案先验、替代支持遗漏与评分 | 选中支持是该模型正确率的已证实必要条件 |
| 某语义 pairwise 方法胜过低阶基线 | 核查它额外看到的文本、查询与训练知识 | 数学界否定了 pairwise 架构 |
| 有替代路径却只标注 abc | 修正支持族或收窄任务规则 | nominal recall 就是任务充分性 |
| token/字符长度差异很大 | 保留测量并限定为 slot budget；必要时另做长度控制 | 同 token 成本的效果比较 |
| 正控制失败或保存结果不能重算 | 修复本地实现，暂停外部执行 | 高阶互补已解释全部失败 |

这些规则用于界定结果可解释性，不构成新的 provider 授权流程。本轮没有进行外部执行；任何后续执行遵循当时仓库和调用环境已有的授权边界。

## 9. 给下一位 Agent 的精确实施委托

1. 先在本目录内新增一个独立的 `fixtures.py` 或同等小文件，实现材料 A/B/C 和正控制的固定输入。不要改动现有 `study.py` 的已记录结果来混入模型分数。
2. 保存固定 fixtures、模板版本、支持族、pool/budget、显示顺序和 source-free 的原创实体词表。隐藏支持只出现在 scorer 对象中；分开导出 selector-visible payload 及其哈希。
3. 完成本地闭环：验证所有隐含支持、预算嵌套、20 个世界的透明度限制、七行替代支持 fixture 和模块化控制。先给出这一层的结果，不需要 provider。
4. 在执行外部调用前写清模型标识、版本/日期、temperature/seed、系统提示、每种条件调用数、预算上限、解析和格式失败规则。新文件标记 `proposed`，不得提前填入结果。
5. 若当时已有授权和可用执行条件，再运行配对 selector/reader。每次调用保留输入、输出、模型 metadata、时间与成本；不保存私人用户语料，不要求模型隐藏思维链。
6. 用确定性 scorer 计算支持与 recall 指标，并按每个世界保存的 gold code `y` 分别计算 `latent_exact_match`、`supported_completion`、`appropriate_abstention` 和 `correct_without_annotated_support`。不要把示例 `Q7` 当作全体世界的固定答案，也不要把这四项混成一个 accuracy；公开解释不将引用直接当作使用。
7. 分别交付方法、结果、实际执行 receipt、失败行和明确未执行的条件。文章只在出现新的证据后修订；没有结果时保留本协议的未执行状态。

该委托是一次小型研究执行，不要求建立新的 schema、网站、评测平台或通用 agent framework。
