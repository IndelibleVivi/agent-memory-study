# Agent Memory Study

一个关于 long-term memory、belief revision、prospective memory 与 cognitive architecture 的公开 research atlas / annotated reading room。

[打开 Reading Room](https://indeliblevivi.github.io/agent-memory-study/) · [下载当前 main branch](https://github.com/IndelibleVivi/agent-memory-study/archive/refs/heads/main.zip) · [下载最近一次 tagged Zotero 包](https://github.com/IndelibleVivi/agent-memory-study/releases/latest/download/agent-memory-study-zotero.zip)

## 这里有什么

- 16 份 source-linked materials；
- 一张先于材料目录出现的 failure-surface 研究地图，以及三条可自由进入和离开的 reading paths；
- 可按主题、failure surface、depth、标题或作者进入材料；
- 每份材料都明确标注 `noteDepth` 与 reading scope，并分开 source-backed paraphrase、paper-reported findings、evidence limits 与 editorial synthesis / inference；当前两份 `read` entry 进一步展示 argument map、方法与监督、原文内部张力、为什么值得读，以及明确标成 `proposed-not-run` 的公开 protocol；字段尚未整理时，reader 会诚实降级，不从空缺补写结论；
- 一个没有 backend、CDN、analytics 或 tracking 的静态 reader；
- 9 份按原许可随站提供的 PDF，另 7 份从 reader 直达 official full text；
- `main` 中的 RDF 可以一次导入 16 条书目、9 份 stored PDF 与 7 个 official PDF link。

这些札记是阅读导航，不是逐篇全文批注，也不代替原文。转述、问题和编辑判断不能冒充作者主张；需要引用时，请回到每条记录链接的 official source。

## 怎样链接到一页

GitHub Pages 没有 SPA rewrite，所以 reader 使用 query URL，而不是伪装成目录的 client-only path：

- material：`?material=a-tma-state-aware-memory`
- failure-surface thread：`?thread=retrieval-active-context`
- reading path：`?path=from-revision`

搜索与筛选也写入 query parameters；material、thread、path 使用 browser history，back / forward 可以恢复对应视图。

## PDF 怎样分发

这里采用 hybrid distribution，不把“网上能下载”冒充“可以再分发”。9 篇有明确的 `CC BY 4.0` 或 `CC BY-NC-SA 4.0` 许可，因此原样放在 `papers/`；其余 7 篇只链接作者、publisher 或 institutional repository 的 official full text。逐文件作者、来源与许可见 [THIRD_PARTY_NOTICES.md](./THIRD_PARTY_NOTICES.md)。

不要单独下载 `agent-memory-study.rdf`：其中 9 个 attachment 使用相对路径。请下载 `main` branch ZIP、解压后再导入 RDF；具体步骤与导入后应出现的结构见 [ZOTERO-IMPORT.md](./ZOTERO-IMPORT.md)。tagged Zotero ZIP 只在显式发版时更新，可能暂时落后于 `main`。Doyle 1979 只链接 MIT DSpace 的 official scan，本地 OCR derivative 不在 repo 或分享包里。

## 本地运行

直接打开 `index.html`，或启动一个静态 server：

```bash
python3 -m http.server 8080
```

然后访问 `http://localhost:8080/`。

## 通过 pull request 贡献

这个 repo 接受 source correction / version watch、新材料 + reading note、对已有 entry 的署名 perspective / critique，以及使用 public / synthetic fixtures 的可复核 test artifact。完整 evidence、attribution、privacy 与 schema contract 见 [CONTRIBUTING.md](./CONTRIBUTING.md)。

本站刻意不提供 browser-side annotate 功能：在没有登录、durable storage、review 与 provenance 的前提下，刷新即消失的输入状态不构成研究贡献。Agent Memory Study 是 study，不按藏书量、待读数或进度组织；GitHub `main` 只表示已经选择公开的同步状态，不能反向推断任何人的阅读或实验进度。

### 加一份新材料

1. 在唯一 canonical public source `data/materials.json` 增加一条连续编号的记录，并明确 `noteDepth`、`readingScope`、`failureSurfaces` 与 `editorialQuestion`；`read` / `worked` 还必须满足 richer evidence schema；
2. 给 `pdf.delivery` 选择 `bundled` 或 `official`。只有存在明确 public redistribution license、逐文件 attribution 与 canonical source 时才能使用 `bundled`；
3. 如需更新 Zotero metadata，可从自己的 Zotero 导出 native RDF，但不要把 local-only notes、keys、tags 或路径带进 public data；
4. 运行：

```bash
python3 tools/build.py \
  --rdf-source /path/to/local-zotero-export.rdf
```

builder 会验证 public schema、private/publication boundary、no-tracking contract、GitHub Pages subpath asset URLs、exact PDF allowlist，重建唯一的 generated browser payload，并生成 hybrid `agent-memory-study.rdf`。不要手工编辑 `assets/materials-data.js`。需要生成可发布 ZIP 时再加：

```bash
python3 tools/build.py --package-output dist/agent-memory-study-zotero.zip
```

Public schema / boundary regression tests：

```bash
python3 -m unittest tools.test_build
```

## Content boundary

Bundled papers keep their file-level Creative Commons licenses; linked works remain subject to their original terms. Those licenses do not extend to the reader code or editorial notes, for which this repository currently grants no open-source or Creative Commons license. See [NOTICE.md](./NOTICE.md).
