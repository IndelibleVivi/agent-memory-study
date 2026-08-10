# Agent Memory Study

一个关于 long-term memory、belief revision、prospective memory 与 cognitive architecture 的公开阅读空间。

[打开 Reading Room](https://indeliblevivi.github.io/agent-memory-study/) · [下载当前 main branch](https://github.com/IndelibleVivi/agent-memory-study/archive/refs/heads/main.zip) · [下载最近一次 tagged Zotero 包](https://github.com/IndelibleVivi/agent-memory-study/releases/latest/download/agent-memory-study-zotero.zip)

## 这里有什么

- 16 份 source-linked materials；
- 每份材料都明确标注 `noteDepth` 与 reading scope：它在解决什么、留下来的东西、编者问题（人机共读）；
- 一个没有 backend、CDN、analytics 或 tracking 的静态 reader；
- 9 份按原许可随站提供的 PDF，另 7 份从 reader 直达 official full text；
- `main` 中的 RDF 可以一次导入 16 条书目、9 份 stored PDF 与 7 个 official PDF link。

这些札记是阅读导航，不是逐篇全文批注，也不代替原文。转述、问题和编辑判断不能冒充作者主张；需要引用时，请回到每条记录链接的 official source。

## PDF 怎样分发

这里采用 hybrid distribution，不把“网上能下载”冒充“可以再分发”。9 篇有明确的 `CC BY 4.0` 或 `CC BY-NC-SA 4.0` 许可，因此原样放在 `papers/`；其余 7 篇只链接作者、publisher 或 institutional repository 的 official full text。逐文件作者、来源与许可见 [THIRD_PARTY_NOTICES.md](./THIRD_PARTY_NOTICES.md)。

不要单独下载 `agent-memory-study.rdf`：其中 9 个 attachment 使用相对路径。请下载 `main` branch ZIP、解压后再导入 RDF；具体步骤与导入后应出现的结构见 [ZOTERO-IMPORT.md](./ZOTERO-IMPORT.md)。tagged Zotero ZIP 只在显式发版时更新，可能暂时落后于 `main`。Doyle 1979 只链接 MIT DSpace 的 official scan，本地 OCR derivative 不在 repo 或分享包里。

## 本地运行

直接打开 `index.html`，或启动一个静态 server：

```bash
python3 -m http.server 8080
```

然后访问 `http://localhost:8080/`。

## 加一份新材料

1. 在 `data/materials.json` 增加一条连续编号的记录，并明确 `noteDepth` 与 `editorialQuestion`；
2. 给 `pdf.delivery` 选择 `bundled` 或 `official`。只有存在明确 public redistribution license、逐文件 attribution 与 canonical source 时才能使用 `bundled`；
3. 如需更新 Zotero metadata，可从自己的 Zotero 导出 native RDF，但不要把 local-only notes、keys、tags 或路径带进 public data；
4. 运行：

```bash
python3 tools/build.py \
  --rdf-source /path/to/local-zotero-export.rdf
```

builder 会验证公开数据边界、exact PDF allowlist，重建 browser payload，并生成 hybrid `agent-memory-study.rdf`。需要生成可发布 ZIP 时再加：

```bash
python3 tools/build.py --package-output dist/agent-memory-study-zotero.zip
```

## Content boundary

Bundled papers keep their file-level Creative Commons licenses; linked works remain subject to their original terms. Those licenses do not extend to the reader code or editorial notes, for which this repository currently grants no open-source or Creative Commons license. See [NOTICE.md](./NOTICE.md).
