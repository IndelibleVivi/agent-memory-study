# Agent Memory Study

一个关于 long-term memory、belief revision、prospective memory 与 cognitive architecture 的公开阅读空间。

[打开 Reading Room](https://indeliblevivi.github.io/agent-memory-study/) · [下载 metadata-only Zotero RDF](./agent-memory-study.rdf)

## 这里有什么

- 15 份 source-linked materials；
- 每份材料的一段 `skim` reading map：它在解决什么、留下来的东西、编者问题（人机共读）；
- 一个没有 backend、CDN、analytics 或 tracking 的静态 reader；
- 可以一次导入 15 条书目的 Zotero RDF。

这些札记是阅读导航，不是逐篇全文批注，也不代替原文。转述、问题和编辑判断不能冒充作者主张；需要引用时，请回到每条记录链接的 official source。

## 为什么没有 PDF

公开 repo 刻意采用 link-only distribution。不同论文与扫描件的再分发许可并不相同，尤其是 publisher PDF 与本地生成的 OCR derivative；所以这里不复制 PDF，也不把私有 Zotero attachments、keys、tags 或本机路径放进 git。

`agent-memory-study.rdf` 只含书目 metadata，不含 attachments。下载后，在 Zotero 里选择 `File → Import…` 即可一次导入 15 条记录；再用记录中的 URL 访问原文，或在自己的 library 里另行保存合法副本。

## 本地运行

直接打开 `index.html`，或启动一个静态 server：

```bash
python3 -m http.server 8080
```

然后访问 `http://localhost:8080/`。

## 加一份新材料

1. 在 `data/materials.json` 增加一条连续编号的记录，并明确 `noteDepth` 与 `editorialQuestion`；
2. 如需更新 Zotero 导入文件，从自己的 Zotero 导出 native RDF，但不要把 attachments 或 local-only notes/tags 带进 public data；
3. 运行：

```bash
python3 tools/build.py \
  --rdf-source /path/to/local-zotero-export.rdf
```

builder 会验证公开数据边界，重建 `assets/materials-data.js`，并生成 metadata-only `agent-memory-study.rdf`。PDF 被 `.gitignore` 明确排除。

## Content boundary

Bibliographic facts and linked source documents remain subject to their original terms. The reader UI and editorial notes are published for viewing, but this repository currently grants no open-source or Creative Commons license. See [NOTICE.md](./NOTICE.md).
