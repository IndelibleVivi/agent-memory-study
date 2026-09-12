# Agent Memory Study — agent contract

本文件只记录这个 repo 的稳定工程边界。一般工作方式、交流风格和安全规则以调用环境中的更高层指令为准。

## Canonical 与 generated surfaces

- `data/materials.json` 是公开材料、阅读深度、failure-surface membership、evidence metadata 与 `studies` 共读专题的 canonical source。
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
- `assets/revision-study.js` 是 browser 与 Node runner 共用的唯一规则实现。规则选择不得接收 `environment` 答案；工具检查发生在建议形成之后。
- 场景、policy 或 engine 变化时，运行 `node --test tools/test_revision_study.cjs` 与 `node research/correction-scope-study/run.js`，同步已执行的 `research/correction-scope-study/results.json`。
- 修改 routes / renderer 后实际验证 desktop / mobile、直接打开 study URL、scenario / phase、history 与旧 material / atlas 路径。共读是公开阅读入口，不接入 private project mapping、账号或持久化访客记录。

## 阅读到设计

- 本站已执行观察与结果放入可选 `amsEvidence`，绑定同一署名的 `public-test` 和既有 `research/` artifact；`reportedFindings` 只承载 paper-reported findings，不把本站结果重复放入 paper-only sections。
- 新增小型 deterministic study 时接入 `tools/verify_reader.py`，同步 README / CONTRIBUTING 的验证范围；该入口校验 canonical / generated data、evidence、search 与已列入的五组本地研究，不运行全部外部源码审计或论文 benchmark。

- `materials[].designTransfer` 是可选的编者建议，必须有署名、整理日期、适用情境、具体做法、未执行对照、依据与边界；`status` 固定为 `proposed-not-run`。它不改变 `readingScope`、`noteDepth`、paper-reported findings 或既有 public-test receipts。
- `skim` / `abstract` 的该栏目必须显示初读范围提示。字段缺失时隐藏栏目，避免空白模板被当成研究结果；不要为满足统一外观补写没有依据的建议。
- material 页的共读连接直接使用 `studies.readings` 的 takeaway / limit / locator，不另设重复的连接文案来源。
