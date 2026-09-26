# Agent Memory Study — agent contract

本文件只记录这个 repo 的稳定工程边界。一般工作方式、交流风格和安全规则以调用环境中的更高层指令为准。

## Canonical 与 generated surfaces

- `data/materials.json` 是公开材料、阅读深度、failure-surface membership、evidence metadata、`studies` 共读专题、`questions` 问题专题与 `findings` 实践判断的 canonical source。
- `assets/materials-data.js` 和 `agent-memory-study.rdf` 是 generated projections；不要手工编辑。
- 需要重建 browser / Zotero artifacts 时，运行：

  ```bash
  python3 tools/build.py --rdf-source /path/to/zotero-source.rdf
  python3 -B -m unittest tools.test_build
  ```

- `--rdf-source` 可以接收经过验证的 native Zotero RDF，也可以接收明确标注 provenance 的 derived RDF。Derived
  projection 不能被称为 native Zotero export。

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

- `studies` 提供公共跨源文章、材料引用、scenario 与明确的演示边界；不要用专题自动提升 material `noteDepth`。
- `editorial-synthesis-with-proposed-experiment` 只承载跨源论述与未执行方案，`artifactUrl` 指向公开协议；不得包含 `resultsUrl`、`recordedResults`、`scenarios` 或 `policies`。页面标明未执行并提供方案入口，不制造可运行控件。私人语料、资源 inventory、标签与派生模型留在公开 repo 外。
- `research/multilingual-use-policy/casebook.py` 负责离线材料与 review sidecar 的合同校验和 HTML 生成；生成页面及私人输入/标注不入 Git。源码消息窗口可追溯不等于完整事件、情境充分或效用已确认；该工具不训练模型，不改变专题的未执行状态。其合成合同测试接入 `tools/verify_reader.py`；修改校准 UI 时运行 `tools/test_casebook_browser.py`，仅使用原创合成材料。
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
- `dist/` 是忽略的生成物，不入 Git。构建仅复制 tracked `assets/`、`research/`、`docs/`、canonical bundled PDF 和命名公开下载；不复制整个 checkout、工具或机器状态。构建/测试拦截非本机请求，不发送 analytics。
- 改动 renderer / routes / metadata / build 时，运行 `node --test tools/test_seo.cjs`、既有 reader 检查、`python3 -B tools/seo_build.py` 和 `python3 -B tools/test_static_reader.py`。后两项需要 `tools/browser-requirements.txt` 与 Chromium；不能把离线语法检查称作浏览器验收。
- 公共物理路径只对应 material / study / question / finding 与首页。query 兼容、source file mode、场景参数、history、目录锚点和导出必须保留。不要把访客查询写进 canonical、metadata 或 sitemap；不要把论文作者标成本站札记作者。
- `.github/workflows/reader-validation.yml` 的 PR 构建不部署，main 仅发布同一验证通过的 artifact。Pages 首次从 branch 切为 Actions 是账号/发布操作，需要对应授权；源码/CI通过不代表线上已切换。流程见 `docs/website.md`。
