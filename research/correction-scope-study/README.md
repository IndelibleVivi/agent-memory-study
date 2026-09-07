# 一条更正之后

Agent Memory Study editors · 2026-09-08 · 原创跨源共读与 deterministic 规则演示。

[进入共读专题](https://indeliblevivi.github.io/agent-memory-study/?study=after-a-correction)；材料、串读与场景的 canonical source 是 [`data/materials.json`](../../data/materials.json) 的 `studies`。此目录没有第二份场景真值。

这项演示把阅读中的问题缩到一个可检查的条件：来源被更正、撤回或限定在不同版本时，一条派生建议会怎样变化。它帮助读者比较设计选择，不产生论文、系统或模型排名。

## 阅读依据与借鉴边界

- [Doyle, A truth maintenance system](https://hdl.handle.net/1721.1/5733)：从 justification 与替代支持提出问题。本演示只有正向、扁平来源，没有实现完整 TMS、nonmonotonic dependencies 或 dependency-directed backtracking。
- [StateFuse 札记与原文入口](https://indeliblevivi.github.io/agent-memory-study/?material=statefuse-conflict-preserving-memory)：借鉴将冲突保持为可检查状态的阅读问题。没有实现或检验 StateFuse 算子。
- [Useful Memories Become Faulty, v1](https://arxiv.org/html/2605.12978v1)：§4.1、Tables 2–3 与 Appendix F.4 提醒读者区分派生经验、episode summary 和原始证据。这里没有 LLM consolidation，也不测 update schedule 的因果效应。
- [Recuris, v1](https://arxiv.org/html/2608.24876v1)：§§2.2–2.3 将调用经验与当前任务连接；Table 2、Appendix E 限制组件效果的外推。这里没有自动诊断、working-state evolution、Meta-Agent 或 validation gate。

跨源连接是编者判断，不是四篇论文共同验证过的架构。Recuris 仍标记为 `read`；本演示不会自动改变任何材料的 `noteDepth`。

## 实验单位与四种规则

虚构命令 `export-json` 接受一个 JSON 输出参数。每个 fixture 显式给出当前任务版本、按收到顺序排列的初始来源、一次添加 / 撤回事件，以及独立的工具 contract。来源包含 `id`、`scope`、`flag`；版本标签与撤回权威均已由 fixture 给定，规则不从自然语言推断。

| 规则 | 消费的证据 | 无建议意味着什么 |
| --- | --- | --- |
| `none` | 不读取经验 | 任务未完成；没有模拟 LLM 的先验补全 |
| `frozen` | 最初第一条说明，不处理更新 | 初始没有说明就没有建议 |
| `latest` | 事件处理后全局最后一条有效说明 | 无有效说明则暂缓 |
| `scoped` | 事件处理后、匹配任务版本的全部有效说明 | 缺支持或多个不同参数时暂缓 |

`select()` 不接收 `environment`。`run()` 先形成建议，再由独立工具 contract 检查参数。一致为 `accepted`，不符为 `mismatch`，无建议为 `abstained`；暂缓不算完成任务。撤回来源保留在历史里，但不再支持 `latest` / `scoped`。来源数组的顺序是明确的接收顺序，不是相关性评分。

七个场景分别是稳定环境、当前版本更正、仍在旧版上的任务、撤回唯一来源、撤回替代支持之一、当前范围内冲突、错误版本标签。每个场景比较事件前后和四条规则，共 56 个确定性输出。环境 contract 在每个场景的前后保持不变，改变的是 memory 所见证据；“更正”场景在事件之前已有错误记忆。

## 本地复跑

使用 Node.js（无第三方依赖、无网络与模型调用）：

```bash
node research/correction-scope-study/run.js > /tmp/correction-scope-results.json
node --test tools/test_revision_study.cjs
```

浏览器与 Node 使用同一份 [`assets/revision-study.js`](../../assets/revision-study.js)。[`results.json`](results.json) 是执行 runner 保存的逐场景结果；可将本地输出与它逐项比较。测试检查当前版本更正、旧版本保护、替代支持、冲突、错误标签、fixture 不变性，以及改变工具答案不会偷偷改变规则建议。

## 已观察到什么

- 当前版本更正后，固定经验继续给出错误参数，处理事件的两条规则改用正确参数。
- v2 新说明没有撤回 v1；全局最近规则仍会误导旧版任务，按范围规则保留旧版建议。
- 撤回一份来源后，另一份独立支持仍能成立。
- 当前范围存在冲突时，按范围规则暂缓，固定经验在这个特定场景反而正确。
- 错误版本标签会使按范围规则采纳错误建议。它可以展示依据，不能因此证明依据为真。

这些输出来自有意构造、非盲选的教学场景。没有总分、显著性、真实错误率、模型效用、预算匹配、延迟或生产可靠性结论；“不读经验”也不代表真实 no-memory agent。想把判断带进项目，需要另行加入真实任务、解析 / 标注错误、恢复证据与人工裁决成本，并比较现有方法。

## 怎样提出反例

在 contribution 中说明你改变了哪个假设，分别给出规则可见来源、工具真实 contract 和预期行为；先以现有场景说明可观察差别。场景与文章只修改 canonical JSON，运行 builder 后检查 browser projection，重跑此 runner 更新结果。不要用改写 expected contract 来让某个规则获胜。

这是 AMS 原创材料，没有新增许可授权；论文和第三方代码继续按各自权利边界处理。
