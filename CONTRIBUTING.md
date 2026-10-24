# Contributing

Agent Memory Study 是一个开放的研究体。贡献可以让一个概念更可理解、一段推导更清楚、一项判断更可定位，也可以带来尚未收束的新问题。公开修改通过 pull request 提交；网页的个人接续与案头笔记只供本地保存，不自动成为公开贡献。跨材料整理、文件恢复和公私导出见[案头说明](docs/study-workspace.md)。

## 可以贡献什么

### 学习记录与研究论述

先写真实内容。`learning-note` 和 `research-essay` 的 Markdown 可以从名字、例子、定义或推导开始，无需先有实验或论文清单。最小 metadata、草稿与编译步骤见[作者指南](docs/authoring.md)。新材料可以补基础、修订解释、提出反例或开启旁支；不要仅为了填满领域或统一外观而创建文章。

### 1. Source correction / version watch

修正书目、source locator、作者勘误、正式发表信息、公开 code / data release 或论文版本变化。说明你检查的版本与日期，并把“外部资源现在存在”同“本站已复现其结果”分开。

### 2. 新材料与 reading note

- 优先链接 canonical / official source，不使用 mirror 代替来源身份；
- `pdf.delivery` 默认使用 `official`。只有 public redistribution license 已逐文件确认时，才能把原始 PDF 加入 `papers/`，并同步更新 `THIRD_PARTY_NOTICES.md` 与 exact allowlist；
- 如实填写 `noteDepth`: `abstract`、`skim`、`read` 或 `worked`。不要因为 note 写得流畅就提高 depth；
- `read` / `worked` entry 必须有 reading scope、`whyRead`、source-backed `argumentMap`、`evidenceLimits` 与明确标注的 `editorialInferences`。只有论文与实际阅读支持时才增加 `methodNotes`、`reportedFindings` 或 `sourceTensions`；不要为了 schema 发明不存在的方法、结果或矛盾；
- 如果提出未来测试，放入 `openProtocols` 并标成 `proposed-not-run`；没有真正值得运行的 protocol 就不加，不把阅读室变成实验待办；
- `worked` 只用于已经存在公开、可复核 artifact 的工作，不用于 private experiment、实现印象或尚未发布的测试；
- `failureSurfaces` 可以为空。有证据支持时，在 source 填入已有 surface ID；compiler 生成反向 `materialIds`，不双向手工维护。旧 constellation 由该关系生成，不需要逐篇坐标。领域／方向导航由 `study/map.json` 维护；
- leave holes visible。拿不准的 locator、数字或结论不要靠推测补齐。

## 星图、领域与 atlas membership

星图和三维研究体共用 `assets/research-map.js` 的纯数据模型。所有 study / material / question / finding 都是一个独立节点；边只来自明确的 typed ID 引用、readings 和 compiler 生成的内部链接，互相引用合并为一条边。不要添加仅为视觉服务的 edge、importance 或 rank，也不要把靠近理解为相似、支持或推荐。

- 保持已发布对象的 ID 稳定，正文深链接沿用它；
- 领域取对象的 `domains` 与 `study/map.json` 的显式成员，允许多重归属和未分类；主领域只决定布局位置，图下详情保留所有领域；
- 位置由 deterministic layout 生成，新增对象后自然重排，不手写 x/y；颜色和形状标示对象类型，光环用于选取和关联，不表示阅读深度或掌握度；
- 来源的 `noteDepth` 仍只在来源与书架中按原合同展示；
- 旧 failure-surface 地图仍由 source membership 生成。新增 surface 需要解释实际 failure boundary，并提供稳定 ID、label、question、tension；不能为了制造 bridge 增加分类；
- 不把当前材料数量或领域数量写成上限。空领域、未分类与没有显式关系的对象都是允许的状态。

修改模型运行 `node --test tools/test_research_map.cjs tools/test_research_sculpture.cjs`；修改交互运行 reader browser tests，包含桌面和手机的真实星图、搜索／筛选、选择、聚焦、缩放／平移、目录和正文路由。图形只使用代码，不能用一张背景图冒充可操作星图。

### 3. 对已有 entry 的 perspective / critique

不要覆盖站方原有判断，也不要把分歧改写成共识。通过 material 的 `contributions` 增加 `type: perspective` item，保留：

- contributor 明确选择的 public `byline` 与日期；
- `text`：贡献者自己的观点；
- `basis`：它依赖的论文段落、公开 artifact 或推理前提；
- `boundary`：它没有证明什么、哪些部分是 inference；
- 可选的 HTTPS source / artifact links。

Project-specific 评价可以进入，但被评价的 project、版本与证据必须公开、可链接、可独立理解；它只说明该公开 project 的行为，不能自动泛化成论文 reproduction 或所有系统的结论。private / proprietary implementation 不能作为 public research result 的隐藏证据。

### 4. Public test artifact

使用 `type: public-test`。artifact 必须是面向公开研究问题、可独立复核的研究材料，并明确记录：

- method 与 environment；
- public / synthetic fixture；
- raw result 与 derived result 的区别；
- controls、limitations 与可访问 artifact link；
- tested implementation / model / source 的公开 identity。

不提交以 private runtime、private data、内部 project 或不可检查实现为被测对象的结果。只提交“我们本地试过、看起来有效”不构成 public test artifact。

### 5. 共读专题与反例

共读既可引用 canonical materials，也可用可选 `externalReadings` 连接官方文档、实现和论文线索；每项提供 `label` / `kind` / `url` / `locator` / `takeaway` / `limit`。只阅读 README 就写 README 范围，不自动创建 `read` 材料或改 Zotero 书目。

未执行的研究可使用 `editorial-synthesis-with-proposed-experiment`，以 `artifactUrl` 链接公开协议，明确研究单位、比较、控制、指标与执行缺口。该类型不接受结果或场景控件字段，页面显示“研究方案尚未执行”。论文发现、编者推论、已执行观察分别署明；真实私人语料及其派生数据不随方案公开。浏览器验收覆盖方案状态、协议链接、直接打开、刷新与历史导航。

`editorial-synthesis-with-recorded-experiment` 用 `resultsUrl` 引用 `research/` 中已执行的 JSON；builder 将它生成到 browser payload 的 `recordedResults`，禁止在 canonical 复制结果。页面只展示 receipt，不训练或调用模型。学习实验必须公开输入、分组、反馈、拟合配置、参数、逐例预测、纠正作用域与限制；测试组新名称不等于新结构，标签预测不自动成为真实效用证据。

Jev 源码实验使用 `ams-jev-contract-results/1`：公开固定源码身份、执行函数、替身边界、指定判断、逐 case 的 before/after 与实际断言。调用前后快照里的节点和向量成员不等于真实持久化或语义检索结果。页面允许选择 case、阶段、检查原始 receipt 并下载同一结果；不把它归类为模型学习实验。

`study/entries/` 中这三类共读是有署名的跨源论述，不代替单篇札记。普通学习记录与研究 essay 使用自己的轻量合同。每个阅读连接要给 material ID、locator、借鉴点与边界；读者应能直接回原文，也能从材料页回专题。专题不要求服务特定项目，不因新增演示而提升关联材料的 depth。

首题“一条更正之后”的场景定义见 [`research/correction-scope-study/README.md`](research/correction-scope-study/README.md)。可提交使某条规则失败的公开 synthetic 反例；区分规则可见来源与独立工具 contract，不为制造胜者改写答案。新增演示机制需要相应的公开方法与可复跑实现，不能只填一份看起来已运行的结果。

修改现有场景或规则后，重建 browser payload，运行 `node --test tools/test_revision_study.cjs`，并用 `node research/correction-scope-study/run.js` 更新逐场景结果。保持新的 source / assumption / evidence 与结论可区分。

### 6. 把阅读带进设计

可在 material 的可选 `designTransfer` 中整理有依据的编者迁移建议：`byline`、`date`、`status`、`when`、`move`、`check`、`boundary`、`basis`。分别记录署名 / 整理日期、状态、适用情境、借用的做法、一个能反驳做法的对照、证据上限与已有札记 / 原文定位。不要复制一套通用项目清单到所有材料。

`status` 只允许 `proposed-not-run`。栏目里的 `check` 是新场景建议，已有论文结果和 public test 仍在原有证据层；真正执行后应按 `public-test` 合同独立提交结果，不能把这个栏目改成一份无方法的 PASS。整理日期不是重读全文、重新验证 upstream 或重新执行历史实验的日期。

栏目允许从 `skim` 形成待核验线索，但页面会明确提示该阅读范围。没有足够依据时可以不提供此字段，栏目隐藏；不能为了补齐页面而升级 depth。共读连接的借鉴点 / 边界直接取自 `studies.readings`，不在 material 再复制一份。

### 7. 持续的问题与可借用的判断

`questions` 是问题专题：当前判断、竞争解释、已执行证据和能改变认识的下一次观察。`findings` 是独立实践判断：适用情境、具体选择、不要怎样用、目标侧检查与证据上限。只整理有内容的条目，不给每篇材料机械填模板。引用关系由 canonical IDs 连接；完整字段与维护约定见[研究与实践维护说明](docs/research-practice.md)。

问题保持 `open`，判断保持 `proposed-transfer`。如已取用，在 `applications` 记录 `cited` / `adopted` / `rejected` / `inconclusive`、日期、公开链接、决定、观察与限制。引用与采用不证明收益；没有对照不要写因果归因。私人项目的 PR、日志与实现不因发生取用就获得公开授权。负反馈、拒绝采用和缩小范围同样欢迎。

## 声音与证据怎样分开

- quotation、source-backed paraphrase、paper-reported result、source audit 与 editorial inference 必须可区分；逐字引用必须有精确 locator；
- `sourceTensions.observation` 记录原文内部可定位的差异，`implication` 才是编者解释；
- `editorialInferences` 必须说明它是 editorial，并在 `boundary` 写清论文缺失了哪项验证；
- contributor voice 只存在于带 `byline` 的 `contributions`，不混入论文作者或本站既有 editorial voice；
- 保留合理分歧，不要求一条 entry 收束成唯一结论。

## Public / privacy boundary

不要提交 private project architecture、非公开实现检查或运行证据、内部版本标识、prompt、session、routing evidence、private names、private continuity、local filesystem path、private export、Zotero key / tag 或 chat locator。不要用化名包装 private project finding。

不要提交 OCR derivative、论文全文截图或未确认再分发权利的 PDF。贡献者应只提交自己有权公开的文字、fixture 与 artifact，并在 pull request template 中明确希望采用的 public byline。仓库当前没有给 reader code 或 editorial notes 授予 open-source / Creative Commons license；maintainer 会在 merge 前确认 attribution 与 publication permission，不把一次 pull request 默认为权利转让。

## Canonical source 与验证

`study/` 是唯一作者真源；`data/materials.json` 和 `assets/materials-data.js` 都由 compiler / builder 生成，不能手工维护。网页贡献也必须保持 static、no-backend；Cloudflare Web Analytics 的 aggregate beacon 是唯一获准的 analytics，不得加入 custom events、visitor profiles、其他 tracking vendor，或需要登录却没有 durable authority 的 annotation state。

运行：

```bash
python3 -m pip install -r tools/content-requirements.txt
python3 tools/build.py --write-json
python3 -m unittest tools.test_content tools.test_author tools.test_build
```

builder 会检查 schema、publication boundary、approved-analytics boundary、GitHub Pages subpath asset URLs、RDF attachment modes 与 bundled PDF exact allowlist，再从研究体生成兼容 JSON 与 browser payload。

## Evidence ownership and reader checks

`reportedFindings` is reserved for paper-reported findings. Keep AMS executions,
recalculations and synthetic experiments in the optional `amsEvidence` block,
with an existing public research `artifactUrl` and a matching bylined `public-test`
contribution. `observations`, `findings`, `methods` and `reasoning` preserve their
separate roles. The builder checks binding and normalized verbatim duplication,
including long statements wrapped by extra copy; it does not check the truth or
semantic attribution of a sentence, so editorial source review remains required.
A `worked` entry must have an attributed `public-test` artifact. Moving an existing
result between sections does not change its reading depth or historical receipts.

The reader verification entry also checks the offline casebook's source/context and
content/rubric-bound review-sidecar contracts with original synthetic fixtures. Reviews use
`ams-memory-reviews/2`; legacy or changed-material sidecars require the explicit
`rebind-reviews` command documented in the [casebook guide](research/multilingual-use-policy/README.md).
Rebinding preserves prior review provenance and requires fresh confirmation; it does not certify labels.
Private casebooks, generated
review HTML and labels stay outside the repository. This is contract validation, not
a multilingual scorer or answerer experiment; the study remains proposed-not-run.

The [representation-use runner](research/representation-use-study/README.md) adds an offline
execution contract with original event families, independent gold, three representation arms,
actual delivered payloads and bound request/response/score receipts. Its scripted and oracle
controls are development diagnostics. Keep family counts separate from question, language,
position and repeat counts; expose the actual budget unit, and retain `used=unknown` unless
a declared intervention supports a narrower influence claim. The local validation entry
tests run identity, corruption rejection, write interruption, retries and replay without
provider/model calls. Publish complete artifacts atomically without replacing existing files;
preserve interrupted evidence and retry in a new attempt. A damaged published artifact must
still fail validation. Source/protocol identity changes require a fresh sample run and raw replay.
Do not promote these controls into model effectiveness, human validation or a paper benchmark.

The [revision-propagation study](research/revision-propagation-study/README.md) owns a separate
longitudinal experiment: canonical/index/summary/context snapshots, delayed updates, isolated
branches and output writeback. Keep interventions on one declared layer, preserve the common
pre-revision checkpoint and exogenous task schedule, and treat later branch outputs as mediators.
Report persistent error separately from recurrence after an observed correction. Read-only
history/preserved/boundary probes must not write into the main trajectory. Event families, episodes
and repeated tasks have separate denominators; scheduled replay of early output is a synthetic
pressure condition, not a measured frequency in real systems. Tombstone/delete comparisons do not
establish privacy erasure. Changes require its unittest suite, saved-summary check and a fresh
raw run/replay when experiment semantics change; run directories stay outside Git.

Reader changes should pass:

```bash
python3 -B tools/verify_reader.py
python3 -m pip install -r tools/browser-requirements.txt
python3 -m playwright install chromium
python3 -B tools/test_reader_browser.py --output-dir dist/browser-check
python3 -B tools/test_casebook_browser.py --output-dir dist/browser-check/casebook
```

The first command uses only local public/synthetic data, including actual fitting of a
small stdlib classifier; it downloads no pretrained models or external data. It
checks both generated projections without rewriting them, validates authoring, study packets, public selected collections, local continuation and workspaces, shared constellation/sculpture relations and domain layout and question/finding
references, lexical query and portable brief contracts, and the existing
RDF, freshly reruns the five small deterministic studies and the decision-learning
experiment (including classifier fitting and correction), and checks the saved
AgeMem reward, C2C cache-retraction and Jev source-contract receipts for fixture binding and internal consistency.
The [Jev source experiment](research/jev-memory-contract-study/README.md) requires a
pinned external checkout for fresh execution; the reader command verifies the saved receipt only.
C2C receipt checks do not load model weights or perform inference; see its
[experiment guide](research/c2c-cache-retraction-study/README.md). The AgeMem receipt check
does not execute upstream AgeMem; a fresh run requires the pinned external
checkout described in its [audit guide](research/agemem-reward-observation-audit/README.md).
The [cross-model KV runner](research/kv-prefill-transfer/README.md) has separate
PyTorch and pinned-upstream tests. It is not part of this local command;
random-model checks and the saved single-target native-cache control do not
establish pretrained transfer quality or reading depth. The native control and
chunk-length diagnostic have their own commands and receipt in that guide.
The command does not rerun all external-source audits or any paper benchmark. The second test path serves
this checkout under `/agent-memory-study/` and checks real browser navigation,
search, question/finding links, practice query and Markdown/JSON downloads, shared scenario state, reload and back/forward on desktop and mobile
viewports. All third-party browser requests, including analytics, are blocked.

The casebook browser check uses only original synthetic fixtures and opens generated
HTML directly as a local file. It checks editing, explicit confirmation, invalidation after
edits, JSON download/reload, filters, text escaping, keyboard use and three viewport
sizes, including stale review migration, download and explicit reconfirmation. It does not
read private material or certify human acceptance of labels.

On hosts that prohibit browser navigation, `--offline-render` is an explicitly
labelled DOM/interaction fallback. Its receipt lists HTTP, reload and history as
unverified; CI never uses that flag. CI validates on PRs without deployment. The existing main workflow deploys the exact
verified artifact through GitHub Pages; it does not change account settings. Repository
settings still determine whether its status is a required merge check.

Search indexes selected reader-visible fields from materials, studies, questions and findings, never
arbitrary JSON keys or URLs. Space-separated terms use AND matching across fields;
exact titles rank first. A study, question or finding matches combined filters only when one of its
referenced materials satisfies all of them. The study does not inherit that
material's reading depth. Keep these semantics in `assets/reading-search.js`, shared
by the browser and its Node tests, rather than adding a second search truth.

实践查询与全部内容搜索是不同用途：前者按 curated triggers 与文字重合返回最多三条判断，后者保持跨字段 AND 语义。首页的展示条数与总数应区分；新增判断时检查示例查询、所属专题与全站搜索的入口，不把前三条默认结果当成完整目录。维护 `assets/practice.js` 时保留重复证据与不同条件条目的控制；网页和 CLI 必须共用实现，不维护另一份手写 Markdown 真源。运行 `node --test tools/test_practice.cjs` 可单独检查查询与导出；改动页面入口时用 `tools/test_reader_browser.py` 检查真实查询、跳转与下载。

### Static reader pages

Routing and rendering changes also need `node --test tools/test_seo.cjs`, a fresh
`python3 -B tools/seo_build.py` artifact and `python3 -B tools/test_static_reader.py`.
These checks cover initial HTML, hydration, nested links, legacy query URLs,
scenario/history, table-of-contents anchors, practice export and source file mode.
Use the existing pinned browser dependency; see [website operations](docs/website.md)
for build, preview and the separate Pages activation boundary. Generated pages are
not hand-edited or committed.
