# 研究与实践入口的维护

本入口把持续的问题、已有证据与有范围的实践判断连接起来。内容仍由 `data/materials.json` 维护；页面与可下载 brief 是 projections，研究结果继续留在原有 `research/` artifacts。

```mermaid
flowchart LR
  M[材料与精读] --> Q[问题专题 questions]
  E[已执行 research artifacts] --> Q
  E --> F[实践判断 findings]
  Q <--> F
  F --> B[网页与 Markdown / JSON brief]
  B --> D[目标项目自己的设计与测试]
  D --> A[经选择公开的取用记录]
  A --> F
```

箭头表示引用与反馈关系，不是自动抓取或跨 repo 写入。目标项目保有采用决定与公开范围；站点没有 backend、访客持久化或私人项目映射。

## 各层负责什么

| 层 | 内容与状态 | 不承载什么 |
| --- | --- | --- |
| material | 原文、阅读范围、paper findings、独立 AMS evidence；可选单篇 `designTransfer` 保持 `proposed-not-run` | 不因被专题引用就提升阅读深度 |
| study | 跨源共读、规则演示或已执行实验的逐例展示 | 不自动变成真实 agent 实验 |
| question | `open`；当前判断、竞争解释、证据、下一次怎样比较与改主意 | 不把下一问写成已执行结果 |
| finding | `proposed-transfer`；有依据的建议及目标侧检查 | 不因已有机制实验就声称目标项目收益 |
| application | `cited`、`adopted`、`rejected` 或 `inconclusive`；具体公开决定、观察和限制 | 不把引用、采用、有效与因果收益混同 |

## Canonical 字段

`questions[]` 使用稳定 `id`、`title`、`question`、`intro`、`judgment`、`byline`、`updated`、`status`，以及：

- `explanations[]`: `title` / `text`，保留竞争解释和负面可能；
- `evidence[]`: `label` / `url` / `observation` / `limit`，指向公开且可检查的材料；
- `materialIds`、`studyIds`、`findingIds`，连接已有内容；
- `nextTest`: `question` / `comparison` / `success` / `reviseWhen` / `boundary`，分别说明下一问、比较、观察指标、如何改主意与尚未执行的范围。

`findings[]` 使用稳定 `id`、`title`、`byline`、`updated`、`status`，以及 `questionIds`、`materialIds`、`triggers`、`claim`、`when`、`action`、`avoid`、`validation`、`limit`、`evidence` 和 `applications`。`questionIds` 可为空；相连时与 question 的 `findingIds` 双向一致。无取用记录时 `applications` 是空数组，页面明确显示尚无公开记录。

每份 application 有 `title`、`status`、`date`、`url`、`decision`、`observation`、`limit`。它记录有内容的决定，不要求读者额外填使用日报。证据与取用链接允许公开 HTTPS 或 repo-relative 文件路径；不接受私人路径和隐藏依据。日期使用 `YYYY-MM-DD`，更新日期不表示重读论文或重跑实验。

## 查询与导出

[assets/practice.js](../assets/practice.js) 同时服务浏览器与 [tools/export_practice.cjs](../tools/export_practice.cjs)。按本地关键词与文本重合检索，最多返回三条；英文按完整词匹配并忽略常见功能词，中文使用短语与相邻双字重合。一条 finding 只占一个名额，其 evidence 数量不增加候选或排名。不同条件条目保持独立，ID 相同才是同一 canonical 对象。

```bash
node tools/export_practice.cjs --query '来源删除后缓存还有影响吗' --format markdown
node tools/export_practice.cjs --finding revision-needs-scope --format json
```

导出保留完整范围和证据，而不只给一条命令式建议。URL 转为可携带的公开链接，读者可以脱离本地 checkout 回查。空结果如实为空；当前覆盖有限，不意味着该问题没有研究。网页查询写入可分享 URL 与 browser history，直接加载/刷新时 URL 随页面请求发送给静态托管服务；查询模块自身不联网，也不建立应用层日志。全站“全部内容”搜索继续采用 `assets/reading-search.js` 的空格多词 AND 匹配，不混成另一套语义搜索。

## 修订与验证

新增观察时先检查它属于原研究结果、目标侧观察还是编辑判断。更新对应 canonical 段落、日期和依据；不要改写历史 receipt，不为新措辞重跑无关模型，不将失败反馈删成成功叙事。

```bash
python3 -B tools/build.py
python3 -B tools/verify_reader.py
python3 -B tools/test_reader_browser.py --output-dir /tmp/ams-browser-check
```

纯问题/判断更新不改变 Zotero 书目，但 browser payload 仍由 builder 生成；若同时改书目，按 repo 约定用明确 provenance 的 RDF source 同次重建 RDF。统一校验检查引用、证据字段、查询、导出和本地研究（含小型分类器实际拟合）。浏览器测试检查真实 HTTP 子路径、直接链接、查询/下载、history 与桌面/手机布局。自动校验不判断自然语言结论是否真实，编辑者仍需逐项核对原证据。

本轮的具体采用记录见 [AMS 的实践 brief](practice-brief-use.md)。真实模型 pilot 和跨模型 KV 拟合未在这轮运行；已执行范围见 [KV runner](../research/kv-prefill-transfer/README.md) 和专题各自引用的研究说明。

## 从材料到学习实验

「经验怎样长成判断习惯？」继续使用 question → study → research artifact 的引用结构。论文材料保持既有阅读深度；共读的 `externalReadings` 单独记录产品文档、独立实现和论文线索的实际阅读范围。外部引用不增加 Zotero 书目数。

共读支持三种明确的研究载体：`editorial-synthesis-with-deterministic-demo` 在页面调用 revision engine；`editorial-synthesis-with-recorded-experiment` 通过 `resultsUrl` 指向已执行结果。Builder 读取该 JSON 并生成 `recordedResults`，保证 file mode、browser 与静态 HTML 使用同一结果。不要在 canonical 或 renderer 手抄实验数字。实验变化先改 runner / protocol / results，再重建页面投影。

`editorial-synthesis-with-proposed-experiment` 将跨源论述接到尚未执行的公开协议，只提供 `artifactUrl`，禁止结果及演示控件字段。页面用“下一项研究”入口与未执行状态，不展示空结果表。当前[表示与取用专题](../research/representation-use-study/README.md)连接十三篇外部来源与两项协议；各项的阅读范围由 canonical `externalReadings` 维护。只有实际执行并具备可检查的公开 artifacts 后，才按相应结果合同改成 recorded 类型；私人 inventory 和训练数据不进入这一转换。

学习与纠正实验的标签、模型参数和逐例输出属于本站研究，不写入任何论文的 `reportedFindings`。生成标签下的准确率只表示对该定义的符合；新任务族名字、重复初始化和更多预测行都不自动增加独立任务或证明现实迁移。实践建议仍需适用条件与目标侧验证。

该专题现在关联 `correction-needs-retention-checks` 与 `output-guard-is-not-unlearning`，分别提出纠正后的保留范围检查，以及输出约束、参数更新和来源遗忘的分层验收。两条判断直接引用既有实验的结果、协议或实现，保持 `proposed-transfer`；空 `applications` 明确表示尚无公开取用记录。添加解读和建议不修改历史 receipt，也不将目标侧检查写成已执行研究。

实践入口的空查询仍展示 canonical 前三条，查询最多返回三条。新增判断通过示例查询、所属问题专题与全站搜索进入；维护时同步示例和数量文案，避免把“本次返回三条”写成“全站只有三条”。完整依据和限制在详情及 Markdown / JSON 导出中保持一致。
