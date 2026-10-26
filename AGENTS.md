# Agent Memory Study — agent contract

本文件只记录这个 repo 的稳定工程边界。一般工作方式、交流风格和安全规则以调用环境中的更高层指令为准。

## Canonical 与 generated surfaces

- `study/` 是公开研究体的唯一作者真源：`programme/` 保存 thesis / 方法 / 方向正文，`entries/*.json` 指向 `bodyFile` Markdown，`sources/`、`inquiries/`、`transfers/` 分别保存来源、问题与实践判断；`map.json` / `catalog.json` 维护导航与次序。
- `data/materials.json` 是旧 reader / CLI shape 的 generated projection；`assets/materials-data.js` 是含保存结果的 browser projection；`agent-memory-study.rdf` 是书目 projection。不要手工编辑这些文件。`research/` 继续独立拥有方法、runner 和历史 receipts。
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

## 研究包与个人接续

- `assets/study-packets.js` 是 browser、`tools/export_study.cjs` 和静态 `index.md` / `index.json` 的唯一研究包实现。包包含当前对象和直接引用 manifest，不递归抓取全文；编辑日期不是 immutable revision。论文作者与札记署名不可混同。
- `assets/study-desk.js` 负责原创集合演算、`ams-continuation/1` 与 `ams-workspace/2` 合同及其页面内状态／有限历史；继续兼读实际已保存的 `ams-workspace/1` 并迁移为 v2。近邻集合、相关性标签与排序是教学设定，不运行 embedding 或 ANN，不是论文或用户学习结果。
- `assets/index-study.js` 是 `ordered-index` 原创教学演算的唯一计算实现：固定唯一整数键、OLS 位置预测、误差校准、局部二分、相邻键核对与显式全区间回退。`StudyDesk.exerciseState` 按 canonical exercise 类型归一化接续／案头状态，禁止从导入文件自定类型；演算四字段可进入公开 URL，私人文字不得进入。修改时运行 `tools/test_index_study.cjs`、StudyDesk／SEO tests 与 source/static browser checks；`tools/index_browser_checks.py` 共用真实交互验收。比较次数不等于时间性能，教学拟合不升级为论文复现或模型研究。
- 私人接续只保存在页面内存和用户主动下载的文件。不得进入 canonical、analytics、URL、localStorage、repo 或构建。导入限制大小与字段，仅恢复已知公开对象；文字按文本使用，不执行指令、不请求文件中的 URL。刷新未保存内容会丢失，界面必须说明。
- 研究案头最多 24 个已知公开对象、每对象 12 条摘录、2 MiB UTF-8 文件；所有被接受状态须能按实际 JSON 下载格式保存。导入先完整验证再显式打开，未知对象／重复对象或摘录身份／无效值拒绝且不改变已有工作。私有 `basis` 是受限惰性文字；旧／新字段检查只用 textContent，正文只 render 当前 canonical HTML，不执行导入 HTML。日期不替代内容身份，比较也不认证来源。摘录保留独立 basis／日期／anchor，确认对象当前依据不得改写既有摘录；私人用途不提升公开支持关系。
- 文字编辑、摘录、选材、导入与 rebase 共用 StudyDesk history；最多 20 次变更／8 MiB 页面内历史，大文件可减少步数，不保存到文件。焦点内连续文字输入合为一步；dirty 按整个状态与最近文件检查点比较，局部单篇保存不得清除其他对象、摘录或案头文字的改动。
- 自动捕获正文位置或演算状态同样须原子接受；容量拒绝须显示反馈、保留已有案头与 history，不能阻断导航或导出。单篇文件可保存当前文章状态，但捕获失败不得因此将整个案头标记已保存。
- `StudyPackets.collection` 是 browser / `tools/export_study.cjs --select` / `--workspace` 的唯一公开选材 projection。只从已知 kind / id 重建当前公开包，不 spread 私人输入，不带案头名称、问题、笔记、摘录记录／用途／批注或旧快照；`ams-study-collection/1` 中仍保留各对象的 packet / attribution / scope。私人 JSON 与 Markdown 出口明确标记且留用户侧。
- 改动上述行为运行 `tools/test_study_packets.cjs`、`tools/test_study_desk.cjs`、`tools/test_export_study.cjs`（已接入统一验证）与 reader browser tests，覆盖导出／导入、恶意及过大文件、历史与页面内接续。

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
- 新增小型 deterministic study 时接入 `tools/verify_reader.py`，同步 README / CONTRIBUTING 的验证范围；该入口校验 canonical / generated data、evidence、search 与已列入的五组确定性研究和一组 stdlib 分类器训练/纠正实验，另检查 AgeMem、C2C 与 Jev 已保存 receipt。Receipt 校验不算 upstream 重跑或模型 inference；该入口不运行全部外部源码审计或论文 benchmark。

- `materials[].designTransfer` 是可选的编者建议，必须有署名、整理日期、适用情境、具体做法、未执行对照、依据与边界；`status` 固定为 `proposed-not-run`。它不改变 `readingScope`、`noteDepth`、paper-reported findings 或既有 public-test receipts。
- `skim` / `abstract` 的该栏目必须显示初读范围提示。字段缺失时隐藏栏目，避免空白模板被当成研究结果；不要为满足统一外观补写没有依据的建议。
- material 页的共读连接直接使用 `studies.readings` 的 takeaway / limit / locator，不另设重复的连接文案来源。

## 问题专题与实践 brief

- `questions` 将已有证据组织为当前判断、竞争解释与下一问；`findings` 提供独立可引用的有范围建议。两者引用 material / study / research artifacts，不复制结果真源，不改变 `noteDepth`、`amsEvidence` 或历史 receipt。
- `questions.status` 为 `open`，`findings.status` 为 `proposed-transfer`；`applications` 分开记录引用、采用、不采用与无定论，不自动证明有效或升级 suggestion。公开采用记录必须有可检查的公开对象、决定、观察、限制和链接；私人目标项目与日志不进入 canonical。
- `assets/practice.js` 是 browser 与 `tools/export_practice.cjs` 共用的唯一 query / brief / Markdown 实现。每个 finding 占一个候选名额，重复 evidence 不增加排名；不同条件的独立 finding 不按标题/主题合并。查询模块无网络、无持久化（页面 query URL / history 的边界见 README）；这是本地 lexical matching，不宣称 semantic retrieval。
- 详情与导出保留署名、日期、适用条件、反例、目标侧检查和 evidence 限制。全站搜索仍用 `assets/reading-search.js` 的跨字段 AND；复合 filters 必须由同一篇引用 material 满足。
- 改动上述合同后运行 `python3 -B tools/verify_reader.py`；修改 UI 时运行 `tools/test_reader_browser.py`，覆盖 question / finding / practice 深链接、下载、回退、旧 material / study / atlas、desktop / mobile。维护规则见 `docs/research-practice.md`。

## 静态阅读站点

- `assets/app.js` 是唯一正文 renderer；`assets/seo.js` 统一生成 source / browser / build-time 的 route URLs 和 metadata。`tools/seo_build.py` 使用已有 Python Playwright 执行该 renderer，生成独立的 `dist/site/`，不维护第二份文章 HTML。
- `dist/` 是忽略的生成物，不入 Git。构建仅复制 tracked `assets/`、`research/`、`docs/`、canonical 引用的研究正文、明确的 reader assets、canonical bundled PDF 和命名公开下载；不复制整个 checkout、工具或机器状态。构建/测试拦截非本机请求，不发送 analytics。
- 改动 renderer / routes / metadata / build 时，运行 `node --test tools/test_seo.cjs`、既有 reader 检查、`python3 -B tools/seo_build.py` 和 `python3 -B tools/test_static_reader.py`。后两项需要 `tools/browser-requirements.txt` 与 Chromium；不能把离线语法检查称作浏览器验收。
- 静态捕获删除非活动／hidden 内容，`reader-shell.js` 从 `index.html` 派生，供 hydration 恢复同一 shell；不得维护第二份正文模板。`research-map.js` 是星图与三维研究体共用的唯一 graph / membership 真源，提供纯 deterministic domain layout；`constellation.js` 管理 SVG 星图的页面内状态，`continuity-sculpture.js` 管理三维 layout / projection 与原生 WebGL；每道环带绑定已知公开对象，边只来自显式 ID 引用及 compiler 的内部链接，空间位置不代表相似度。保留鼠标／触摸拖动、键盘、正文入口、静态 fallback、暂停、reduced-motion、视口与页面可见性停帧；`tools/test_research_map.cjs` 与 `tools/test_research_sculpture.cjs` 接入统一验证。静态 snapshot 移除 JS 操作面与环带 labels，不能留下无作用的控制。
- 公共物理路径只对应 material / study / question / finding 与首页。query 兼容、source file mode、场景参数、history、目录锚点和导出必须保留。不要把访客查询写进 canonical、metadata 或 sitemap；不要把论文作者标成本站札记作者。
- 星图 `#constellation` 独立于 legacy disclosure，桌面／手机都保留 SVG、列表、对象详情及真实正文链接。搜索／类型／领域筛选、相机、选取和暂停只在页面内存；不写 URL、storage 或 canonical。选取与 hover 不制造关系；静态 snapshot 移除控制，保留星点与相关对象的普通链接。修改时运行既有 reader browser / static tests。
- `assets/fonts/` 是经许可分发的字体子集及完整 OFL notices，源 TTF 不入仓库。可选 `tools/build_fonts.py` 读取公开正文／界面字符串离线重建；普通构建不依赖 fontTools。新增缺失字形先确认 fallback，再按字体 README 重建；不要引入远程字体请求。

- `.github/workflows/reader-validation.yml` 的 PR 构建不部署，main 仅发布同一验证通过的 artifact。`reader` runner 固定在当前 Playwright 支持的 Ubuntu 版本；升级 OS / browser dependency 时核对版本支持并跑完整浏览器与静态检查，不直接换回浮动镜像。Pages 使用既有 Actions 发布面；修改 Pages account 设置仍是独立授权操作，源码/CI通过不代表本次 artifact 已上线。流程见 `docs/website.md`。
