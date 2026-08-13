# Contributing

Agent Memory Study 是一间公开 study room，不是未读材料仓库，也不是论文排行榜。贡献应当让一条研究判断更可定位、更可反驳或更可复核。本站不提供 browser-side annotation editor；没有账号、持久化与 provenance 的输入框刷新即失效，也无法支持可靠审阅。请通过 pull request 提交 durable contribution。

## 可以贡献什么

### 1. Source correction / version watch

修正书目、source locator、作者勘误、正式发表信息、公开 code / data release 或论文版本变化。说明你检查的版本与日期，并把“外部资源现在存在”同“本站已复现其结果”分开。

### 2. 新材料与 reading note

- 优先链接 canonical / official source，不使用 mirror 代替来源身份；
- `pdf.delivery` 默认使用 `official`。只有 public redistribution license 已逐文件确认时，才能把原始 PDF 加入 `papers/`，并同步更新 `THIRD_PARTY_NOTICES.md` 与 exact allowlist；
- 如实填写 `noteDepth`: `abstract`、`skim`、`read` 或 `worked`。不要因为 note 写得流畅就提高 depth；
- `read` / `worked` entry 必须有 reading scope、`whyRead`、source-backed `argumentMap`、`evidenceLimits` 与明确标注的 `editorialInferences`。只有论文与实际阅读支持时才增加 `methodNotes`、`reportedFindings` 或 `sourceTensions`；不要为了 schema 发明不存在的方法、结果或矛盾；
- 如果提出未来测试，放入 `openProtocols` 并标成 `proposed-not-run`；没有真正值得运行的 protocol 就不加，不把阅读室变成实验待办；
- `worked` 只用于已经存在公开、可复核 artifact 的工作，不用于 private experiment、实现印象或尚未发布的测试；
- 映射到一个或多个现有 `failureSurfaces`，并同步更新对应 surface 的 `materialIds`。builder 会要求双向 membership 完全一致；constellation 由这组关系自动生成，不需要另交逐篇坐标。只有跨材料问题结构本身改变时，才修改 atlas taxonomy；
- leave holes visible。拿不准的 locator、数字或结论不要靠推测补齐。

### 3. 对已有 entry 的 perspective / critique

不要覆盖站方原有判断，也不要把分歧改写成共识。通过 material 的 `contributions` 增加 `type: perspective` item，保留：

- contributor 明确选择的 public `byline` 与日期；
- `text`：贡献者自己的观点；
- `basis`：它依赖的论文段落、公开 artifact 或推理前提；
- `boundary`：它没有证明什么、哪些部分是 inference；
- 可选的 HTTPS source / artifact links。

Project-specific 评价可以进入，但被评价的 project、版本与证据必须公开、可链接、可独立理解；它只说明该公开 project 的行为，不能自动泛化成论文 reproduction 或所有系统的结论。private / proprietary implementation 不能作为 public research result 的隐藏证据。

### 4. Public test artifact

使用 `type: public-test`。artifact 必须是 paper-facing、system-agnostic、可独立复核的公开研究材料，并明确记录：

- method 与 environment；
- public / synthetic fixture；
- raw result 与 derived result 的区别；
- controls、limitations 与可访问 artifact link；
- tested implementation / model / source 的公开 identity。

不提交以 private runtime、private data、内部 project 或不可检查实现为被测对象的结果。只提交“我们本地试过、看起来有效”不构成 public test artifact。

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

`data/materials.json` 是唯一 canonical public content source；`assets/materials-data.js` 由 builder 生成，不能手工维护。网页贡献也必须保持 static、no-backend、no-analytics、no-tracking，不引入需要登录却没有 durable authority 的 annotation state。

运行：

```bash
python3 tools/build.py
python3 -m unittest tools.test_build
```

builder 会检查 schema、publication boundary、no-tracking contract、GitHub Pages subpath asset URLs、RDF attachment modes 与 bundled PDF exact allowlist，再从 canonical JSON 重建 browser payload。
