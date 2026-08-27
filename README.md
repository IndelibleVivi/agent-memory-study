# Agent Memory Study

一个关于 long-term memory、belief revision、prospective memory 与 cognitive architecture 的公开 research atlas / annotated reading room。

[打开 Reading Room](https://indeliblevivi.github.io/agent-memory-study/) · [阅读项目介绍 PDF](./publications/agent-memory-study-project-introduction.zh-CN.pdf) · [下载当前 main branch](https://github.com/IndelibleVivi/agent-memory-study/archive/refs/heads/main.zip) · [下载最近一次 tagged Zotero 包](https://github.com/IndelibleVivi/agent-memory-study/releases/latest/download/agent-memory-study-zotero.zip)

## 这里有什么

- 一组从唯一 canonical public data 生长的 source-linked materials；
- 一张 failure-surface 研究地图、一幅 data-driven research constellation，以及三条可自由进入和离开的 reading paths；
- 可按主题、failure surface、depth、标题或作者进入材料；
- 每份材料都明确标注 `noteDepth` 与 reading scope，并分开 source-backed paraphrase、paper-reported findings、evidence limits 与 editorial synthesis / inference；达到 `read` 的 entry 进一步展示 argument map、方法与监督、原文内部张力、为什么值得读，以及明确标成 `proposed-not-run` 的公开 protocol；已经执行的 public / synthetic test 则保留署名、method、environment、raw / derived result、controls、limitations 与可复核 artifact links；字段尚未整理时，reader 会诚实降级，不从空缺补写结论；
- 一个没有 backend、继续由 GitHub Pages 托管的静态 reader；唯一 analytics 是 Cloudflare Web Analytics 的 aggregate beacon，不使用 cookie 或 localStorage 识别、画像访客；
- 10 份按原许可随站提供的 PDF，另 9 份从 reader 直达 official full text；
- `main` 中的 RDF 会随 canonical materials 重建，并保持 stored PDF 与 official PDF link 的 delivery 边界。

这些札记是阅读导航，不是逐篇全文批注，也不代替原文。转述、问题和编辑判断不能冒充作者主张；需要引用时，请回到每条记录链接的 official source。

## 怎样链接到一页

GitHub Pages 没有 SPA rewrite，所以 reader 使用 query URL，而不是伪装成目录的 client-only path：

- material：`?material=a-tma-state-aware-memory`
- failure-surface thread：`?thread=retrieval-active-context`
- reading path：`?path=from-revision`

搜索与筛选也写入 query parameters；material、thread、path 使用 browser history，back / forward 可以恢复对应视图。

Cloudflare Web Analytics 只用于了解 visits、page views、referrers、国家/设备类别和 Web Vitals 等站点级信号。它不记录 query string，也没有接入 custom events，因此 `?material=`、`?thread=`、`?path=` 和筛选参数不会成为阅读行为追踪；当前 analytics 不能回答访客具体读了哪个 material 或 failure surface。

Constellation 是同一 canonical data 的 semantic projection：failure surfaces 使用固定语义 anchors，material
位置由它的 `failureSurfaces` membership 与 stable ID 派生；没有逐篇维护的第二份 layout truth。新增 material
会自动成为一颗星，跨 surface material 会成为 bridge。Desktop 使用可键盘进入的 SVG，mobile 使用同源 matrix；
坐标、连线、星环与亮度都不表示论文质量、重要性或阅读进度。

## PDF 怎样分发

这里采用 hybrid distribution，不把“网上能下载”冒充“可以再分发”。10 篇有明确的 `CC BY 4.0` 或 `CC BY-NC-SA 4.0` 许可，因此原样放在 `papers/`；其余 7 篇只链接作者、publisher 或 institutional repository 的 official full text。逐文件作者、来源与许可见 [THIRD_PARTY_NOTICES.md](./THIRD_PARTY_NOTICES.md)。

不要单独下载 `agent-memory-study.rdf`：其中 10 个 attachment 使用相对路径。请下载 `main` branch ZIP、解压后再导入 RDF；具体步骤与导入后应出现的结构见 [ZOTERO-IMPORT.md](./ZOTERO-IMPORT.md)。tagged Zotero ZIP 只在显式发版时更新，可能暂时落后于 `main`。Doyle 1979 只链接 MIT DSpace 的 official scan，本地 OCR derivative 不在 repo 或分享包里。

## 本地运行

直接打开 `index.html`，或启动一个静态 server：

```bash
python3 -m http.server 8080
```

然后访问 `http://localhost:8080/`。

Doyle 1979 close-read 所附的 public / synthetic static oracle 可直接复跑：

```bash
python3 research/doyle-tms-static-oracle/oracle.py
```

方法、解释边界与 checked-in raw stdout 见 [`research/doyle-tms-static-oracle/`](./research/doyle-tms-static-oracle/)；它不是 original TMS reproduction。

LongMemEval-V2 close-read 所附的 benchmark-metadata query / answer-evidence audit 需要一个包含三个 pinned revisions、当前位于 `2cc8c540…` 且 clean 的 official-code checkout：

```bash
PYTHONHASHSEED=0 python3 research/longmemeval-v2-boundary-audit/audit.py \
  --source-repo /path/to/LongMemEval-V2
```

fixed decision rules、runner、逐 case normalized output 与完整 built memory contexts 见 [`research/longmemeval-v2-boundary-audit/`](./research/longmemeval-v2-boundary-audit/)；它证明 source / postprocessing boundary，不是 benchmark reproduction。

同一材料的 alias / observable-order successor 目前停在 model-free pre-registration audit。checked selection、renderer
controls、runtime HOLD 与全部 public ledgers 可直接验证：

```bash
python3 research/longmemeval-v2-alias-order-preregistration/audit.py --verify-checked
```

从 exact current source 与已取得的三个 public metadata files 重建 selector / renderer evidence 的命令和 hashes 见
[`research/longmemeval-v2-alias-order-preregistration/`](./research/longmemeval-v2-alias-order-preregistration/)。它记录
`0/66` controller jobs，不是 controller、reader 或 benchmark result。

PM-Bench close-read 所附的 scorer-contract / released-log audit 可以先做无 source 的 checked-artifact 校验：

```bash
python3 research/pmbench-scoring-contract-audit/audit.py --verify-checked
```

要从 official source 重建 probes、64-run audit 与 report comparison，需要 clean checkout 固定在
`e1093c470c8981daf522d4ef047a7c3a71e077d7`，并使用新的 output directory：

```bash
python3 research/pmbench-scoring-contract-audit/audit.py \
  --source-repo /path/to/PMBench \
  --output-dir /tmp/pmbench-scoring-contract-rebuild
```

method、raw/derived separation、exact hashes、claim-by-claim verdict 与 limits 见
[`research/pmbench-scoring-contract-audit/`](./research/pmbench-scoring-contract-audit/)。它不调用模型、不生成新
trajectory，也不改变 released headline Set-F1；它证明的是锁定 revision 的 scorer contract 与 64 份 released
primary logs 的边界。

StateFuse close-read 所附的 interpretation-contract / semantic-reference audit 可以离线复核 checked artifacts：

```bash
python3 research/statefuse-interpretation-contract-audit/audit.py --verify-checked
```

完整 preregistration、exact official-source identity、synthetic contracts、raw/derived receipts 与复现入口见
[`research/statefuse-interpretation-contract-audit/`](./research/statefuse-interpretation-contract-audit/)。它不复现论文的
model 或 benchmark experiments，也不把 locked implementation behavior 倒推成 paper-time result。

FluctlightDB close-read 所附的 observation-binding / scoped-recall audit 也可在没有 upstream checkout 或 native
package 的环境里验证：

```bash
python3 research/fluctlightdb-observation-binding-audit/verify_checked.py
```

checked result 包含 unmodified official runs、identity-bearing paired controls、scope/negative controls 与 1,140 条
compact query rows；exact source、wheel、runtime identities 和 bounded claim ceiling 见
[`research/fluctlightdb-observation-binding-audit/`](./research/fluctlightdb-observation-binding-audit/)。它不复现论文
benchmarks，不隔离 provenance 单变量效应，也不把本地 SDK output finding 冒充 tenant、security 或 production claim。

## 通过 pull request 贡献

这个 repo 接受 source correction / version watch、新材料 + reading note、对已有 entry 的署名 perspective / critique，以及使用 public / synthetic fixtures 的可复核 test artifact。完整 evidence、attribution、privacy 与 schema contract 见 [CONTRIBUTING.md](./CONTRIBUTING.md)。

本站刻意不提供 browser-side annotate 功能：在没有登录、durable storage、review 与 provenance 的前提下，刷新即消失的输入状态不构成研究贡献。Agent Memory Study 是 study，不按藏书量、待读数或进度组织；GitHub `main` 只表示已经选择公开的同步状态，不能反向推断任何人的阅读或实验进度。

### 加一份新材料

1. 在唯一 canonical public source `data/materials.json` 增加一条连续编号的记录，并明确 `noteDepth`、`readingScope`、`failureSurfaces` 与 `editorialQuestion`；同时更新对应 `failureSurfaces[].materialIds`，让 atlas、filters 与 constellation 使用同一组双向 membership；`read` / `worked` 还必须满足 richer evidence schema；
2. 给 `pdf.delivery` 选择 `bundled` 或 `official`。只有存在明确 public redistribution license、逐文件 attribution 与 canonical source 时才能使用 `bundled`；
3. 如需更新 Zotero metadata，可从自己的 Zotero 导出 native RDF，但不要把 local-only notes、keys、tags 或路径带进 public data；
4. 运行：

```bash
python3 tools/build.py \
  --rdf-source /path/to/local-zotero-export.rdf
```

builder 会验证 public schema、private/publication boundary、approved-analytics boundary、GitHub Pages subpath asset URLs、exact PDF allowlist，重建唯一的 generated browser payload，并生成 hybrid `agent-memory-study.rdf`。不要手工编辑 `assets/materials-data.js`。需要生成可发布 ZIP 时再加：

```bash
python3 tools/build.py --package-output dist/agent-memory-study-zotero.zip
```

Public schema / boundary regression tests：

```bash
python3 -m unittest tools.test_build
```

## Content boundary

Bundled papers keep their file-level Creative Commons licenses; linked works remain subject to their original terms. Those licenses do not extend to the reader code or editorial notes, for which this repository currently grants no open-source or Creative Commons license. See [NOTICE.md](./NOTICE.md).
