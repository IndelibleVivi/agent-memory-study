# 在 AMS 里写、接收与修订研究

先有值得留下的理解，再选择容器。跨材料推敲可以先在[研究案头](study-workspace.md)中进行；私人问题、笔记和导出不会自动成为公开内容。作者仍须选择可公开的论证、核对来源与署名，再进入 canonical。一个概念解释、例子或推导可以成为 `learning-note`；持续论述可以成为 `research-essay`。它们都无需实验、既有书目或固定章节。长期工作的判断方法见[AMS 怎样学习与生长](../study/programme/method.md)。

## 接住一份新材料

离线 helper 只比较公开研究体中已有的身份与显式引用，不请求网络、不推断论文结论：

```bash
python3 tools/author.py inspect 'https://arxiv.org/abs/2502.01736v1'
python3 tools/author.py inspect 'The Pain Axis'
python3 tools/author.py impact pain-axis
python3 tools/author.py impact retrieval-and-relevance --kind study
```

`inspect` 接受 URL、DOI、arXiv ID 或标题；输出区分身份匹配、版本候选、标题候选与未识别。标题接近不足以认定是同一篇论文，版本也仍需回原文核对。识别到来源后，返回的依赖信息与 `impact` 共用当前编译路径，因此也需要下述 Node.js 和 Markdown parser；不联网补齐身份或用旧 projection 兜底。

`impact SOURCE_ID` 保留原有 source 关系与地图字段；`--kind material|study|question|finding` 可以指定任一公开对象。它先编译当前 canonical，再调用与网页共用的 `ResearchMap.referenceGraph`，沿 reading、显式 ID、continuation 和已知内部正文链接反向查找，给出直接／间接条目、距离与最短引用路径。环和重复路径不会重复计算目标；领域、方向和共享主题不构成依赖。输出只是编辑检查范围，不验证支持强度，也不声明每个引用者都必须修改。该入口需要本项目的 Node.js 和 `tools/content-requirements.txt`；不会用过期 generated projection 兜底。

CLI 默认使用 PATH 中的 `node`；需要明确指定已安装的本地 runtime 时，可用 `AMS_NODE=/absolute/path/to/node`，该值必须是可执行文件。它不安装或启动远程服务。

阅读后判断它补充基础、改变机制解释、提供反例、开启旁支、修正来源身份，还是暂不采用。只把实际选择过的内容编入研究体。来源真源位于 `study/source-corpus/works/`、`revisions/`、`notes/`：作品身份、发布或观察 Revision 与 AMS 札记分别保存，不能用札记编辑日期产生论文新版。短小外部阅读也可先放文章的 `externalReadings`，不自动增加 Zotero 书目。`failure_surfaces` 可为空；有关联时在 source note 导航中填写 ID，反向 `materialIds` 由 compiler 生成。

## 从一篇轻量文章开始

下面命令在 repo 外生成一对带 draft 标记的文件，拒绝覆盖已有文件：

```bash
python3 tools/author.py new-study a-question-about-retrieval \
  --kind learning-note --title '一次检索留下的问题' \
  --out /tmp/ams-drafts
```

直接写 Markdown 也可以。发布前最小 metadata 是：

```json
{
  "id": "a-question-about-retrieval",
  "title": "一次检索留下的问题",
  "kind": "learning-note",
  "date": "2026-10-18",
  "byline": "Your public byline",
  "intro": "用一句话说明这篇内容的实际对象。",
  "bodyFile": "entries/a-question-about-retrieval.md"
}
```

完成真实正文、署名、日期、简介与来源核对后，移除 `draft` 字段，将 JSON 和 Markdown 放进 `study/entries/`。`bodyFile` 相对 `study/`，要随实际位置调整。Compiler 拒绝带 draft 标记的记录；不要把生成器的提示文字当作成稿提交。ID 发布后保持稳定，标题可以随理解修订。

正文支持普通 CommonMark、表格和代码块，禁止 raw HTML 与可执行链接。可以只有几段文字，不需要章节。`#` 主标题可有可无，网页详情只显示一个主标题。指向其他研究正文的 repo-relative Markdown links 在网页编译成对应 study route；其余公开文件链接继续指向原文件。章节锚点在网页按 `section-1`、`section-2` 顺序生成。

可选字段应有实际用途才加：

- `readings` 引用已有 source ID，并给出 locator、takeaway、limit；`externalReadings` 记录官方文档、实现或论文线索的实际阅读范围。
- `domains`、`directionIds` 引用地图已有 ID；领域与方向可以交叉，不表示掌握度。首页分组的阅读入口由 `map.json` 的显式对象列表维护；可选 `notation` 只放正文已有依据的简短公式／技术表述，不制造测量结果。
- `continuation` 保存当前下一问、为什么值得继续及直接的 source / study 链接；`changes` 记录具体解释如何改变，不冒充个人学习历史。
- `takeaways`、`boundary`、`closing` 按内容需要填写，缺省不制造空栏目。

研究方案与实验沿既有三类合同：`editorial-synthesis-with-proposed-experiment` 只链接未执行协议；`editorial-synthesis-with-recorded-experiment` 链接真实 `resultsUrl`；`editorial-synthesis-with-deterministic-demo` 使用现有共用规则实现。不得把学习笔记套成假实验；实际运行结果只在原研究 artifact 中维护。

## 从私人案头继续成文

新 v3 案头在明确启动的本地环境中使用“整理成文、比较依据与修订”：先保存私人文稿，再生成带 base 的修订和选择性发表 preview。它不会自动改 Git，具体流程见[修订与发表](revision-publication.md)。

已有 v1/v2 案头保留离线 draft helper，不必重新抄写：

```bash
python3 tools/author.py draft-from-workspace \
  --input /path/to/ams-workspace.json \
  --slug a-question-about-retrieval \
  --title '一次检索留下的问题' --kind learning-note \
  --out /path/to/private-drafts
```

命令调用 `StudyDesk.parseWorkspace` 的同一验证，兼读案头 v1 / v2；不 fetch 来源或文件中的 URL。输出目录必须在 repo 外（包括解析 symlink 后的位置），两个目标文件都必须尚不存在。损坏、过大、未知对象或不合合同的案头会在写入前拒绝。

输出是一对明确标记私人工作材料和 `draft: true` 的 Markdown / JSON，保留问题、已有理解、继续位置、对象笔记、摘录用途／批注／章节、所据日期与版本限制，以及当前公开对象的署名和阅读范围。来源作者与本站札记署名分别保留；未核实的旧快照不变成可信原文，私人用途不生成支持声明或自动填入 `readings`。

它只接续写作，不能替代作者决定：逐段选择可公开的内容，复查当前原文、旧摘录和引用权利，补足论证、署名与简介；移除草稿标记并按上一节的 canonical 文件路径主动采用。不要把整个私人 draft 或案头原样放进 Git；compiler 拒绝 draft 是最后一道格式保护，不是隐私审查。

## 改变理解时，改哪里

先修改文章真正受影响的段落，核对相连来源的版本与阅读范围，再更新需要变化的结论、下一问或地图。新增说明不自动推翻旧 receipt；实验结论的改变要由对应研究证据支持。`author.py impact` 是显式关系索引，不替代编辑判断。

```bash
python3 -m pip install -r tools/content-requirements.txt
python3 -B tools/build.py --write-json
python3 -B tools/verify_reader.py
node tools/export_study.cjs --kind study --id retrieval-and-relevance --format markdown
```

`data/materials.json` 和 `assets/materials-data.js` 都由 `study/` 编译，stage 时一起检查；`tools/content.py --check` 和 `tools/build.py --check-drift` 只检查、不修复。新来源改变 Zotero inventory 时，按 [agent contract](../AGENTS.md) 用有 provenance 的 RDF source 同次生成；单纯更新文章无需写 Zotero。

改变页面、路由、编译链接或新交互时，继续执行 [网站说明](website.md) 中的真实浏览器与静态构建检查。私人草稿、输入、接续文件不进入 Git。公开研究包保留编辑日期／edition、正文和显式 ID 引用；普通正文链接与外部引用仍在正文／metadata 中，日期并非不可变版本；v2 JSON 包另带内容 revision，Git revision 记录仓库交付。
