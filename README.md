# Agent Memory Study

**经验如何成为可继承、也可改变的能力？**

AMS 从 agent memory 出发，研究信息、经验与智能的跨时间关系。我们关心经验怎样获得形式，过去怎样参与当下，以及系统怎样在改变中保持连续性。IR、表示、学习、数据系统及其基础问题，都可以在这里独立深入。

[进入研究书房](https://indeliblevivi.github.io/agent-memory-study/) · [工作 thesis](study/programme/thesis.md) · [怎样学习与生长](study/programme/method.md) · [研究体目录](study/README.md)

这里的 thesis 是可修订的研究立场。我们沿具体对象考察保留状态、取用条件和改变方式之间的关系，不预先假定所有 memory 都是同一种机制，也不要求每次学习交付一项工程建议。

## 从哪里开始

| 想进入的地方 | 可以读什么 |
| --- | --- |
| jieba、BM25、BGE-M3 究竟在做什么 | [找到一样的，还是找到相关的？](study/entries/retrieval-and-relevance.md)：用一个原创集合例子区分近邻重合、精确率和召回率；网页可以改变候选数、排序和相关性定义。 |
| Database、Index、Retriever、Memory 怎样区分 | [一条记录、一种表示、一个记忆系统](study/entries/records-representations-systems.md)：从同一条工具版本记录看不同研究对象和功能角色。 |
| 新材料怎样改变已经形成的认识 | [索引也能学习——究竟学了什么？](study/entries/what-an-index-learns.md)：对齐两个作者摘要里的“学习索引”，保留阅读范围、解释的改变和下一问。 |
| 继续一项已有研究 | [经验怎样长成判断习惯](https://indeliblevivi.github.io/agent-memory-study/study/experience-becomes-policy/)：跨源论述、已保存的分类器学习与纠正结果，以及仍未回答的问题。 |
| 看项目长期关心什么 | [经验的形式](study/programme/directions/forms-of-experience.md)、[当下的相关性](study/programme/directions/relevance-in-context.md)、[改变与继承](study/programme/directions/change-and-continuity.md)。 |

这些新文章是基于公开来源与原创例子写成的研究内容，不是私人聊天的重建。当前有 12 篇学习／研究文章、27 份来源札记、2 个问题专题、5 条实践判断。领域与方向只是可改的阅读地图；数量、关联和阅读深度不代表个人掌握度。

## 研究怎样生长

从名字、例子、公式或疑惑开始，把真正学到的解释写下来。需要深入时，可以做推导、辨析定义、寻找反例、对读原文、观察实现或设计实验；增加论文数量只是其中一种手段。新材料可能补基础、解释机制、构成反例、开启旁支，也可能暂时放下。它的去向取决于内容，不能由相似度自动决定。

[研究方法](study/programme/method.md)说明怎样选一次研究的落点、接住新材料、修订已有理解，以及在哪里停下与继续。[作者指南](docs/authoring.md)提供实际的文件、命令和发布流程。一个简短学习记录无需先有成熟问题、实验或统一的章节模板。

## 仓库里的研究体

| 真源 | 负责什么 |
| --- | --- |
| `study/programme/` | 工作 thesis、研究方法与长期方向的完整论述 |
| `study/entries/*.md` + `*.json` | 正文与轻量 metadata；programme 的 metadata 也在这里 |
| `study/sources/` | 来源身份、实际阅读范围、札记、独立 evidence 与有署名的编辑判断 |
| `study/inquiries/` | 持续的问题、竞争解释与下一步 |
| `study/transfers/` | 可选的实践判断、适用条件与公开取用记录 |
| `study/map.json`、`catalog.json` | 研究导航、展示次序与旧 atlas 定义 |
| `research/` | 各项研究自己的协议、runner、输入、结果与限制 |

`tools/content.py` 把研究体编译为 `data/materials.json`；`tools/build.py` 生成 `assets/materials-data.js`。这两份文件是兼容原 reader／CLI 的 generated projections，不能手工编辑。原有 ID、材料深链接、27 份札记、4 篇共读与研究 receipts 均继续可查。旧 failure-surface 地图、星图和阅读路径保留为可选入口；反向 membership 从 source 生成。

## 人与机怎样继续读

每篇来源、文章、问题与实践判断都有同源的 Markdown / JSON 研究包，包含正文或札记、署名、范围、版本日期和显式 ID 引用 manifest。包不抓取引用全文、不递归展开整个研究库，也不把研究文字当作 agent instructions。

```bash
node tools/export_study.cjs --kind study --id retrieval-and-relevance --format markdown
node tools/export_study.cjs --kind question --id experience-to-capability --format json
```

网页详情底部可导出研究包。在发布构建中，对象目录下也有 `index.md` 与 `index.json`，不需要 JavaScript。`contentVersion` 是编辑日期／edition，不是不可变 commit；需要固定引用时同时保留 Git revision 或包文件。

读到一半，可以在详情页写一段自己的接续笔记，主动下载 JSON，之后从首页“打开接续文件”恢复公开对象、章节位置和支持的演算状态。笔记只在页面内存与自己保存的文件里；刷新前未下载的修改会丢失。导入不执行文件中的文字，也不加载任意 URL。它不是在线批注、账号服务或云同步。

已有实践 brief 仍可独立取用：

```bash
node tools/export_practice.cjs --query '候选增加之后，结果被重复条目占满' --format markdown
node tools/export_practice.cjs --finding revision-needs-scope --format json
```

实践查询是本地 lexical matching，最多三条；全站搜索是跨字段多词 AND。不同条件的独立 finding 保留独立名额，重复 evidence 不增加排名。[维护与取用边界](docs/research-practice.md)和[公开采用记录](docs/practice-brief-use.md)区分引用、采用与实际有效。

## 本地编辑与检查

需要 Python 3.11+、Node.js，以及构建用的 Markdown parser。浏览器检查另需 Playwright 和专用 Chromium；运行站点无需 backend 或 npm runtime。

```bash
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -r tools/content-requirements.txt
python3 -B tools/build.py --write-json
python3 -B tools/verify_reader.py
python3 -m http.server 8080
```

打开 `http://localhost:8080/`；也可直接打开源码 `index.html`，沿 `?study=` 等 query links 阅读。要构建 GitHub Pages 的真实路径与静态正文：

```bash
python3 -m pip install -r tools/browser-requirements.txt
python3 -m playwright install chromium
python3 -B tools/test_reader_browser.py --output-dir dist/browser-check
python3 -B tools/test_casebook_browser.py --output-dir dist/browser-check/casebook
python3 -B tools/seo_build.py
python3 -B tools/test_static_reader.py
```

构建拒绝覆盖旧输出；重复运行用新的 `--output`，对应测试传 `--site-root`。`dist/` 不进 Git。统一验证覆盖作者内容／generated drift、来源与 evidence 合同、搜索、研究包、接续格式、三维研究体的身份／引用关系，以及既有五组确定性研究和一组 stdlib 分类器学习／纠正实验；另检查 AgeMem、C2C、Jev 已保存 receipts。它不做 pretrained inference、不重跑所有 upstream 审计，也不复现论文 benchmark。各研究的完整方法与额外依赖仍以对应 `research/*/README.md` 为准。

## 发布、隐私与来源

发布面继续是 **GitHub Pages**。唯一正文 renderer 是 `assets/app.js`；构建运行该 renderer，生成首页及四种详情页的初始 HTML、metadata 和 sitemap。旧 query URLs、场景、目录锚点、history 与源码 file mode 继续兼容。首屏把公开文章、来源、问题和实践判断呈现为可操作的三维研究体：拖动或方向键旋转，点击层片选择内容，切换叠置／展开／关联后打开对应正文。关联只来自研究体的显式引用与内部链接，空间位置不表示语义相似度；展开的结构信息可直接检查。原生 WebGL 无额外 runtime dependency，reduced-motion 默认静止、离屏停帧，缺少 WebGL 时保留静态图形和文字选取入口。[网站运维说明](docs/website.md)记录构建与发布边界。

站点没有账号或访客档案。个人接续文字不上传、不写 URL 或 localStorage。搜索、筛选和公开演算状态会进入可分享 URL 与浏览器历史，直接加载／刷新时 URL 会发送给托管服务；不要把私人内容输入公开搜索。既有 Cloudflare Web Analytics aggregate beacon 是唯一 analytics，不使用 cookie 或 localStorage 识别访客，无 custom events；它不记录 query string。外部来源链接在你打开时访问相应网站。构建与浏览器验收拦截非本机请求。

来源札记明确区分原文主张、作者报告、AMS 观察与编辑推论，`noteDepth` 只表示来源阅读范围。未执行协议、教学例子、确定性实验、固定源码 receipts 与实际模型研究各自标明边界；不因文章变成熟或页面重做而提升结论。

27 份书目中，10 份 PDF 按已确认的再分发条件随站提供，17 份链接 official full text。RDF 与 PDF 的交付边界保持原样；[Zotero 导入指南](ZOTERO-IMPORT.md)、[第三方 notices](THIRD_PARTY_NOTICES.md)、[权利说明](NOTICE.md)分别负责对应范围。最近 tagged Zotero package 不保证包含 main 的最新内容。重建没有扩大任何许可；[2026-08 项目介绍 PDF](publications/README.md)保留为当时版本的记录。

贡献入口见 [CONTRIBUTING](CONTRIBUTING.md)，稳定工程约定见 [AGENTS](AGENTS.md)。
