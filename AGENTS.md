# Agent Memory Study — agent contract

本文件只记录这个 repo 的稳定工程边界。一般工作方式、交流风格和安全规则以调用环境中的更高层指令为准。

## Canonical 与 generated surfaces

- `study/` 是公开研究体的唯一作者真源：`programme/` 保存 thesis / 方法 / 方向正文，`entries/*.json` 指向 `bodyFile` Markdown，`source-corpus/works/`、`revisions/`、`notes/` 分别保存来源身份／版本／札记，`inquiries/`、`transfers/` 保存问题与实践判断；`map.json` / `catalog.json` 维护导航与次序。
- `schemas/core.schema.json`、`schemas/validate.py` 与 `packages/research-core/` 拥有 ams-core/2 合同及跨语言 canonical identity；修改须同步 Python/JS parity。`data/public-corpus.manifest.json` 仅含 metadata，`data/corpus/` 是 compiler 生成的固定版本与按需 shards，`data/route-inventory.json` 记录兼容路由；历史 revision 不覆写。`data/materials.json` 是兼容 reader / CLI shape 的 generated projection；`assets/materials-data.js` 是含保存结果的 browser projection；`agent-memory-study.rdf` 是书目 projection。不要手工编辑这些文件。`research/` 继续独立拥有方法、runner 和历史 receipts。
- `tools/content.py` 是唯一内容 compiler，禁 raw HTML、可执行链接、越界正文路径与 draft 标记。表格用 `markdown-it-py` 构建，无 browser Markdown parser。正文中的已知 study Markdown 链接转换为原 study route。
- `learning-note` / `research-essay` 只要求身份、署名、日期、简介与正文；不要求实验、来源数量、takeaways 或固定章节。领域 / 方向是可改导航，不是进度或成果等级。`failureSurfaces` 可为空，反向 membership 由 source 生成。
- 一般更新运行：

  ```bash
  python3 -m pip install -r tools/content-requirements.txt
  python3 -B tools/build.py --write-json
  python3 -B tools/verify_reader.py
  ```

- `tools/content.py --check` / `tools/build.py --check-drift` 只检查 drift，不修复。书目变化需要同次 `--rdf-source /path/to/zotero-source.rdf` 重建；单纯编辑文章无需重导 RDF。`--rdf-source` 接受经过验证的 native Zotero RDF 或明确 provenance 的 derived RDF；derived 不能称为 native export。
- `tools/author.py` 是 offline identity / explicit impact / 私人案头到草稿 helper，不 fetch 来源、不验证论点。`impact` 从当前 canonical 编译并调用 `research-map.js` 的唯一有向引用；保留旧 source 输出，任意公开对象用 `--kind`。`tools/research_context.cjs` 只连接既有 compiler / ResearchMap / StudyDesk，不维护第二份关系提取或案头校验。草稿只生成在 repo 外，拒绝覆盖；发布前逐段核对隐私、署名、引用权利与依据，完成正文后移除 draft。具体作者路径见 `docs/authoring.md`。

## 研究包、私人接续与本地研究

- `assets/study-packets.js` 是 browser、CLI 与静态 Markdown 的唯一研究包实现；compiler 生成 JSON v2 的固定 revision 和直接引用 manifest。包不递归抓全文；论文作者、札记署名与编辑日期不可混为内容 identity。
- `apps/reader/src/desk-store.ts` 拥有当前多案头状态与 20 步 / 8 MiB 全局页面历史；`adapters.ts` 区分 ephemeral 和明确启动的 local mode。`assets/study-desk.js` 保留原创集合演算、exercise normalization 和已有 continuation v1 / workspace v1/v2 的真实兼容消费者；当前文件写出 workspace v3，不维护第二套活跃编辑界面。
- `assets/index-study.js` 是 ordered-index 演算的唯一计算实现；保留固定整数键、OLS、误差校准、局部二分和全区间回退。演算字段可进公开 URL，私人文字不得进入。`tools/index_browser_checks.py` 以独立 bisect 对照检验真实交互；比较次数不等于性能，教学拟合不升级为论文复现。
- Public mode 不探测 localhost，私人内容只在页面和主动下载的文件中，不进 canonical、analytics、URL、storage、repo 或构建。Local mode 只能由用户明确启动，`services/local/` 单应用服务拥有同源 HTTP / CLI、SQLite、不可变原件和 job。数据 root 必须在 repo 外、同机文件系统；备份一致、恢复只写新目录。配置、升级和恢复见 `docs/local-workspace.md`。
- `services/local/repository.py` 是唯一持久写入口：commands 带期望 revision 和稳定幂等 identity，单位事务先验证全部 graph 再接受。公开 DB 索引只是 cache；不可从 DB 回写公开真源。HTTP token 由每次启动生成，不从请求接受权限提升；Host/Origin/大小限制不可旁路。
- 每个案头最多 24 个对象／每对象 12 条摘录／2 MiB payload；v3 完整 JSON 限 32 MiB／512 个私有记录版本，包含所用 public snapshots 和文件字节。接受的 ephemeral 状态必须可保存。导入完整校验、先预览后确认，不能执行文字、HTML 或任意 URL。未知旧依据保留为待核对观察；当前正文不冒充旧快照。独立 excerpt basis 不随对象 rebase 改写。
- 连续文字编辑以焦点合并历史；dirty 按全状态和该案头最近 JSON 检查点计算。Markdown 不作恢复 checkpoint。自动位置／演算捕获和大文件拒绝保留现有状态／历史、明确反馈、不中断导航与导出。断线或 CAS 冲突可导出 `ams-uncommitted-input/1`，不能把未 ack 写成已保存。
- `StudyPackets.collection` 是 browser / `tools/export_study.cjs --select|--workspace` 唯一公开选材 projection；只从已知 ID 重建当前公开包，不 spread 私人输入。案头名称、问题、批注、用途、摘录与旧快照不得混入公开包。
- `services/local/jobs.py` 只调度登记的研究原生 adapters，不另写科学算法；attempt、输入、取消／恢复和 raw evidence 各自留存。Run、Analysis、Interpretation 和 Observation 分开。provider plan 不授予真实调用、费用或私人材料实验。
- `arguments.py` 保持 ReferenceGraph 与正式 EvidenceRelation 的区别、AND 前提／OR 替代 warrant 及同 scope 检查。正式接受来自 human 或可解析的可信委托；不得相信请求自称授权。`revisions.py` 分开 review/application/publication；逐 owner apply-unit/receipt 不承诺 DB/Git 全局事务，no-change 是显式结果。
- `publication.py` / `authoring.py` 只为所选可公开内容生成 closure、compiler preview 与带 base patch；默认 HTTP 不提供 Git 写入／部署入口。Git 已应用、site 未构建与公开未激活各有状态。私人预览、patch、运行资料留在 repo 外；新 public source 必须单独审阅。
- 改动这些合同用 `python3 -B tools/verify_reader.py`；UI / 恢复用 `--browser` 完成 public、portable、真实 local service 与失败路径。`docs/intake.md`、`docs/execution.md`、`docs/revision-publication.md` 分别拥有对应用户路径。

## Zotero：CLI / local API first

普通 inventory、collection、search、citation metadata 和 BibTeX 工作默认使用可用的 `Zotero` skill 及其
stdlib-only helper，不要为了这些操作驱动 Zotero GUI、Finder 或 Computer Use。

从该 skill 的 `SKILL.md` 解析当前 `<plugin-root>`，不要把某台机器的 plugin cache 绝对路径写进 repo。第一步始终是：

```bash
python3 <plugin-root>/skills/zotero/scripts/zotero.py status --json
```

常用 read-only 路径：

```bash
python3 <plugin-root>/skills/zotero/scripts/zotero.py inventory
python3 <plugin-root>/skills/zotero/scripts/zotero.py collections
python3 <plugin-root>/skills/zotero/scripts/zotero.py search "paper title or DOI" --json
python3 <plugin-root>/skills/zotero/scripts/zotero.py export-bibtex --out /path/to/references.bib
```

如果 local API 未启用，只有在用户已经授权操作 Zotero、并确认可以重启而不丢失未保存状态时，才运行：

```bash
python3 <plugin-root>/skills/zotero/scripts/zotero.py enable --restart
```

边界：

- Zotero item key 与 BibTeX citation key 是不同标识；不要混用。
- 默认只读取 bibliography metadata。只有用户明确要求 PDF、attachment path 或 indexed full text 时，才调用
  `children`、`file-url` 或 `fulltext`。
- `import-bibtex`、`import-ris` 和 connector save 会修改 Zotero library。用户未明确要求写入时，先确认 exact
  source、record 和 destination；不要用 GUI 绕过这个 write gate。
- GUI 只留给 CLI/local API 无法完成的 UI-only 工作，例如人工 PDF annotation 或用户明确要求的 native
  import/export。GUI window 异常时，不要反复 reopen、kill、重启或把 Finder 抢到前台；继续使用可用的 CLI/local
  API，或者准确报告 blocker。
- Native RDF 与 local-API-derived RDF 必须保留不同 provenance。若使用 derived RDF，先在 repo 外生成并标记为
  derived，再交给 `tools/build.py --rdf-source`；不要让临时源文件、profile path、collection/item key、private
  note、tag 或本地 attachment path 进入 public diff。
- `ZOTERO-IMPORT.md` 是 reader 将公开 `agent-memory-study.rdf` 导入 Zotero 的用户指南，不是从私人 Zotero
  library 生成公开 artifacts 的 agent authority。

## Publication closure

- Builder 必须报告预期的 material、bundled PDF 与 official-link counts；RDF 与 browser payload 应由同一次
  canonical build 生成。
- Stage 前检查 generated diff，确认公开 RDF 不含 `file://`、本地绝对路径、private Zotero keys、private notes
  或未经选择的 tags。
- 只 stage 本次公开变更需要的明确路径；private working continuity 与临时 Zotero source 留在 repo 外。

## 共读专题

- `studies` 是编译后的文章集合，来自 `study/entries/`；以下三类共读保留各自 scenario / artifact 边界，不把它们的字段要求施加给普通学习文章。任何专题都不自动提升 material `noteDepth`。
- `editorial-synthesis-with-proposed-experiment` 只承载跨源论述与未执行方案，`artifactUrl` 指向公开协议；不得包含 `resultsUrl`、`recordedResults`、`scenarios` 或 `policies`。页面标明未执行并提供方案入口，不制造可运行控件。私人语料、资源 inventory、标签与派生模型留在公开 repo 外。
- `research/multilingual-use-policy/casebook.py` 负责离线材料与 review sidecar 的合同校验和 HTML 生成；生成页面及私人输入/标注不入 Git。源码消息窗口可追溯不等于完整事件、情境充分或效用已确认；该工具不训练模型，不改变专题的未执行状态。其合成合同测试接入 `tools/verify_reader.py`；修改校准 UI 时运行 `tools/test_casebook_browser.py`，仅使用原创合成材料。
- Review 使用 `ams-memory-reviews/2`，绑定 canonical case 内容 digest 与 `rubric_version`。改变被审材料或 rubric 后不得沿用 confirmed；旧 sidecar 或不匹配内容只能显式 `rebind-reviews` 到新文件，保留旧审阅并标 stale，再主动确认。Digest 只判断内容身份，不认证审阅者或标签效用。
- `research/representation-use-study/` 拥有离线事件、gold、三臂执行器及运行证据，保持本研究内的单一实现；未有第二个真实消费者前不抽取跨研究框架。实际送达输入、response 和 score 必须绑定；完整 artifact 原子发布且不覆写，中断证据保留，resume 另建 attempt；已发布的损坏文件仍须拒绝。`used` 默认 unknown。诊断预算明确计数单位，不冒充 provider token。Scripted/oracle 控制与完整自然语言研究状态分开，公开仅用原创合成数据，运行目录留在 repo 外。修改该路径须运行其 unittest 与 `tools/verify_reader.py`；source/protocol identity 变化须新跑 sample 并 raw replay。不自动执行模型/API 或私人材料实验。
- `research/revision-propagation-study/` 是纵向修订传播、延迟调度、单层干预与再写入的唯一实现；原 `correction-scope-study` 继续拥有单次更正的网页规则演示。分支共享修订前 checkpoint 与外生任务安排，后续输出是各自中介，不能重新匹配成相同历史。历史／preserved／boundary probes 只读；持续错误与修好后的再现分别计数。源码或实验语义变化须运行该目录 unittest、`check-sample` 与新的 raw run/replay；原始 run 留在 repo 外，公开汇总不替代 raw 重放。统一 verifier 接入合同与 compact summary 检查，不运行模型；删除消融不代表隐私删除。
- `externalReadings` 允许共读引用官方文档、开源实现与论文线索，必须保留类型、阅读范围与限制；不自动变成 Zotero 书目。`editorial-synthesis-with-recorded-experiment` 的 `resultsUrl` 指向已执行 `research/` JSON；`recordedResults` 仅由 builder 投影，不进入 canonical。录制结果展示与 `revision-study.js` 的实时规则演示分开。
- `research/decision-learning-study/study.py` 是学习实验唯一训练/评价实现；网页不重新训练。修改实验后用 `--check` 重算并运行该目录 unittest，更新公开方法/结果；自然语言、agent 收益与权重遗忘不能由结构化标签预测代替。
- Jev 共读使用 `ams-jev-contract-results/1` 保存固定源码的给定判断对照；页面按 case 与 before/after 展示节点和原始 receipt，不重新运行源码。完整复跑需要外部 pinned checkout；本地 reader 入口只校验保存结果。不要把内存 graph/vector 的成员变化写成真实持久化、语义检索或 Jev inference。
- `assets/revision-study.js` 是 browser 与 Node runner 共用的唯一规则实现。规则选择不得接收 `environment` 答案；工具检查发生在建议形成之后。
- 场景、policy 或 engine 变化时，运行 `node --test tools/test_revision_study.cjs` 与 `node research/correction-scope-study/run.js`，同步已执行的 `research/correction-scope-study/results.json`。
- 修改 routes / renderer 后实际验证 desktop / mobile、直接打开 study URL、scenario / phase、history 与旧 material / atlas 路径。共读是公开阅读入口，不接入 private project mapping、账号或持久化访客记录。

## 阅读到设计

- 本站已执行观察与结果放入可选 `amsEvidence`，绑定同一署名的 `public-test` 和既有 `research/` artifact；`reportedFindings` 只承载 paper-reported findings，不把本站结果重复放入 paper-only sections。
- 新增小型 deterministic study 时接入 `tools/verify_reader.py`，同步 README / CONTRIBUTING 的验证范围；该入口校验 canonical / generated data、evidence、search 与已列入的有限与确定性研究、FTS5 条件贡献控制和一组 stdlib 分类器训练/纠正实验，另检查 AgeMem、C2C 与 Jev 已保存 receipt。Receipt 校验不算 upstream 重跑或模型 inference；该入口不运行全部外部源码审计或论文 benchmark。

- `materials[].designTransfer` 是可选的编者建议，必须有署名、整理日期、适用情境、具体做法、未执行对照、依据与边界；`status` 固定为 `proposed-not-run`。它不改变 `readingScope`、`noteDepth`、paper-reported findings 或既有 public-test receipts。
- `skim` / `abstract` 的该栏目必须显示初读范围提示。字段缺失时隐藏栏目，避免空白模板被当成研究结果；不要为满足统一外观补写没有依据的建议。
- material 页的共读连接直接使用 `studies.readings` 的 takeaway / limit / locator，不另设重复的连接文案来源。

## 问题专题与实践 brief

- `questions` 将已有证据组织为当前判断、竞争解释与下一问；`findings` 提供独立可引用的有范围建议。两者引用 material / study / research artifacts，不复制结果真源，不改变 `noteDepth`、`amsEvidence` 或历史 receipt。
- `questions.status` 为 `open`，`findings.status` 为 `proposed-transfer`；`applications` 分开记录引用、采用、不采用与无定论，不自动证明有效或升级 suggestion。公开采用记录必须有可检查的公开对象、决定、观察、限制和链接；私人目标项目与日志不进入 canonical。
- `assets/practice.js` 是 browser 与 `tools/export_practice.cjs` 共用的唯一 query / brief / Markdown 实现。每个 finding 占一个候选名额，重复 evidence 不增加排名；不同条件的独立 finding 不按标题/主题合并。查询模块无网络、无持久化（页面 query URL / history 的边界见 README）；这是本地 lexical matching，不宣称 semantic retrieval。
- 详情与导出保留署名、日期、适用条件、反例、目标侧检查和 evidence 限制。全站搜索仍用 `assets/reading-search.js` 的跨字段 AND；复合 filters 必须由同一篇引用 material 满足。
- 改动上述合同后运行 `python3 -B tools/verify_reader.py`；修改 UI 时运行 `tools/test_reader_browser.py`，覆盖 question / finding / practice 深链接、下载、回退、旧 material / study / atlas、desktop / mobile。维护规则见 `docs/research-practice.md`。

## 静态阅读站点与交付

- `apps/reader/src/` 是唯一 React/TypeScript renderer 与四空间界面，`assets/seo.js` 拥有 route URLs / metadata。`tools/seo_build.py` 调用 Node `apps/reader/build.mjs`，server/client 共用组件；旧 `index.html` / `assets/app.js` / `assets/styles.css` 已退役，不恢复平行路径。
- `dist/` 忽略、不入 Git。构建只复制明确公开 allowlist、canonical 正文和获准 PDF，不复制 checkout、工具运行状态或私人目录；hash 命名的 JS/CSS/font 与页面同一构建。首页仅 metadata，正文按需；portable 含离线正文和 no-JS book，仍是同一 React renderer。
- 公共路径对应 material / study / question / finding 与首页；保留旧 query、场景、history、目录锚点、公开包与 portable file reader。访客查询不进入 canonical、metadata 或 sitemap，论文作者不能标成札记作者。no-JS 正文与普通链接成立，隐藏无作用的操作控件。
- `research-map.js` 是星图和研究体的唯一身份／显式引用／导航布局 owner；`constellation.js` 与 `continuity-sculpture.js` 保留原生 SVG/WebGL。React wrappers 负责 mount/unmount、observer 与 animation 清理，保留拖动、触摸、键盘、正文、列表、静态替代、暂停、reduced-motion 和离屏停帧。位置不代表相似度，hover 不制造关系；地图状态只留页面。
- `assets/fonts/` 是已许可 OFL 子集与完整 notices；TTF 不入 Git。`tools/build_fonts.py` 从公开内容和 UI 字符离线重建，普通构建不依赖 fontTools，不请求远程字体。
- `.github/workflows/reader-validation.yml` 是主要 CI owner，只调用 provider-neutral `tools/verify_reader.py --browser`。Ubuntu / Python / Node 与浏览器版本固定；CI SQLite 编译在隔离目录并验证 Python 实际绑定，不覆盖系统库。改 runtime/dependency 须检查官方支持并实际验证。
- PR 构建不部署；main 只发布同一验证通过的 artifact。Pages account 配置、merge 与上线是独立授权，源码／测试／commit 不表示激活。`docs/current-state.md` 拥有 candidate / live 状态；构建和操作流程见 `docs/website.md`。
