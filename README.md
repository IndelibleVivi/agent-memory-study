# Agent Memory Study

一个围绕 agent memory、learning 与 cognitive architecture 的公开研究空间：读原文，检查实现，运行实验，把有依据的判断带回实践。

[打开 Reading Room](https://indeliblevivi.github.io/agent-memory-study/) · [阅读项目介绍 PDF](./publications/agent-memory-study-project-introduction.zh-CN.pdf) · [下载当前 main branch](https://github.com/IndelibleVivi/agent-memory-study/archive/refs/heads/main.zip) · [下载最近一次 tagged Zotero 包](https://github.com/IndelibleVivi/agent-memory-study/releases/latest/download/agent-memory-study-zotero.zip)

## 这里有什么

- 两个持续更新的问题专题：[旧经验，怎样继续帮助当前任务？](https://indeliblevivi.github.io/agent-memory-study/question/experience-to-capability/)与[经验怎样长成判断习惯？](https://indeliblevivi.github.io/agent-memory-study/question/experience-becomes-policy/)，连接已执行研究、竞争解释、当前判断与下一次会改变认识的观察；
- 五条可独立引用的实践判断，覆盖候选挤占、修订范围、来源撤回，以及[纠正后的保留范围](https://indeliblevivi.github.io/agent-memory-study/finding/correction-needs-retention-checks/)与[输出约束、参数更新和遗忘的区别](https://indeliblevivi.github.io/agent-memory-study/finding/output-guard-is-not-unlearning/)；可从[研究与实践入口](https://indeliblevivi.github.io/agent-memory-study/#inquiries)按问题查询，导出带署名、适用条件、证据和限制的 Markdown / JSON；[AMS 自身的取用记录](docs/practice-brief-use.md)说明一个实际采用决定，同时保留“已采用不等于已证明有帮助”的边界；
- 一组从唯一 canonical public data 生长的 source-linked materials；
- 一张 failure-surface 研究地图、一幅 data-driven research constellation，以及三条可自由进入和离开的 reading paths；
- 面向所有读者的共读专题：原文与精读互链、跨源论述、可亲手切换的场景对照、适用条件与失败反例；首题为[一条更正之后](https://indeliblevivi.github.io/agent-memory-study/?study=after-a-correction)，不要求读者有私人项目或把每次阅读转成代码；
- 新共读[没有再读那段往事，它为什么还是改变了选择？](https://indeliblevivi.github.io/agent-memory-study/study/experience-becomes-policy/)连接论文、Jev 官方接口文档、jevlike 开源说明与本站[学习和纠正实验](research/decision-learning-study/README.md)。页面可切换阶段、查看逐例预测和下载已执行结果；本机 runner 真正拟合小型分类器，浏览器只展示保存结果。给定结构化特征的标签预测不等于自然语言理解、真实效用或权重遗忘；
- [谁在管理记忆？快判断、慢推理与旧信息的退场](https://indeliblevivi.github.io/agent-memory-study/study/who-controls-memory/)专题沿着 Jev-Mem 的写入、关联、检索与维护，区分语义判断、实际状态变化和后续任务收益。配套[源码实验](research/jev-memory-contract-study/README.md)给定 controller responses，执行固定 upstream 函数，记录节点、索引成员、关系与派生摘要；页面可切换案例、调用前后并下载原始结果，不把给定判断下的变化称为 Jev inference、真实检索或模型遗忘；
- 可按主题、failure surface、depth、标题或作者进入材料；
- 每份材料都明确标注 `noteDepth` 与 reading scope，并分开 source-backed paraphrase、paper-reported findings、evidence limits 与 editorial synthesis / inference；达到 `read` 的 entry 展示 argument map 与为什么值得读，并按实际证据补充方法与监督、原文内部张力；尚未执行的公开 protocol 明确标成 `proposed-not-run`；已经执行的 public / synthetic test 则保留署名、method、environment、raw / derived result、controls、limitations 与可复核 artifact links；字段尚未整理时，reader 会诚实降级，不从空缺补写结论；
- 每篇现有材料都有“读完，可以怎样借用”：适用情境、可借用的做法、尚未执行的迁移对照、依据与边界；`skim` / `abstract` 显示初读线索提示，编者建议不改变阅读深度或历史测试结论；
- 阅读可以继续形成公开、可复跑的研究材料，例如 [TRUSTMEM 的同状态候选比较](research/trustmem-transition-study/README.md)：10 个原创结构化 transition、4 组配对控制和论文数字复核；它单独记录已执行结果，真实更新器 / LLM judge 的迁移对照仍是未执行建议，不把教学实验算作论文效果复现；
- [VerMem 的历史恢复与 verifier 边界](research/vermem-verifier-boundary-audit/README.md)直接执行固定官方代码的 12 个函数级样例：候选内 ID、合法长度与规则 `pass` 仍不足以单独证明任务归属或语义忠实；原始输入、返回值和外部源码复跑命令均公开，结论不扩展到完整 executor 或模型效果；
- [旧经验还在，为什么读不到？](research/experience-reuse-retrieval-study/README.md)把 experience reuse 的检索竞争做成 4 个原创场景、108 次 SQLite BM25 选择：重复条目会挤走旧经验，按 key 去重也可能漏掉不同的适用条件；每个排名、控制与复跑命令均公开，不把检索命中算作 agent 成功；
- [还没发生的事，能改变此刻的判断吗？](research/proactive-prefix-study/README.md)沿着 proactive trigger 的因果要求，用 3 个原创图场景、30 次精确分数传播说明未来如何经共享实体或归一化影响当前状态；保留前缀参照和负控制，不将它称为作者 GNN 的实现审计；
- [邻居没变，为什么分数过期了？](research/mosaic-score-dependency-study/README.md)对 MOSAIC 的公开评分式执行 9 个原创场景、27 组缓存处理：frontier 最大值和 previous community 都可能让远处节点的完整分数过期；保留全量参照、依赖补全与有效控制，不将公式实验称为作者实现或 benchmark 复现；
- [做过、做成、做对](research/agemem-reward-observation-audit/README.md)直接运行固定 AgeMem reward 模块的 16 个原创消息输入：失败维护消息、context reset 与语义利用代理分别暴露不同的评价边界；公开完整输入、返回值、配对控制和复跑命令，不把函数级测试称为真实 mutation 或训练复现；
- [来源删了，计算影响还在吗？](research/c2c-cache-retraction-study/README.md)受 C2C 启发，对固定 SmolLM2-135M-Instruct 执行 200 个原创 cache 干预输出：删去来源 slots 后，20 组配对仍有来源相关分布差异；记录重算、位置、mask 与数值控制，不将残余依赖称为成功恢复事实。[配套源码审计](research/c2c-source-contract-audit/README.md)直接检查固定 C2C aligner / projector 的函数级行为；两者均不复现论文 benchmark；
- [跨模型 prefill reuse 的分阶段 runner](research/kv-prefill-transfer/README.md)为 Qwen3-0.6B → 1.7B 准备串行采集、磁盘分块 ridge 与三分支评价；21项本地测试、完整256-token随机控制和公开数据准备已完成。真实1.7B单文档验证了native cache的精确磁盘交接，并记录了BF16分段/整段数值差与资源实测；跨模型 mapper 尚未拟合，论文现已收录为 [read 材料](https://indeliblevivi.github.io/agent-memory-study/?material=cross-model-kv-prefill-reuse)，不把 runner 或单模型检查当作迁移质量结果；
- 新增 [Cross-Model KV Cache Transfer](https://indeliblevivi.github.io/agent-memory-study/?material=cross-model-kv-prefill-reuse) 与 [The Pain Axis](https://indeliblevivi.github.io/agent-memory-study/?material=pain-axis) 两篇 `read` 材料：分别连接前缀状态交接与内部干预后的行动变化，保留作者结果、编者推论和未执行对照的边界；
- 一个没有 backend、继续由 GitHub Pages 托管的静态 reader；唯一 analytics 是 Cloudflare Web Analytics 的 aggregate beacon，不使用 cookie 或 localStorage 识别、画像访客；
- 27 份 canonical materials：10 份按原许可随站提供的 PDF，另 17 份从 reader 直达 official full text；
- `main` 中的 RDF 会随 canonical materials 重建，并保持 stored PDF 与 official PDF link 的 delivery 边界。

这些札记是阅读导航，不是逐篇全文批注，也不代替原文。转述、问题和编辑判断不能冒充作者主张；需要引用时，请回到每条记录链接的 official source。

## 怎样链接到一页

发布构建为首页和每份 material、study、question、finding 生成真实 HTML 文件；正文、标题、canonical 和分享 metadata 随初始响应一起返回，不需要等待 JavaScript 才能读文章。交互仍使用同一个 renderer。

- 问题专题：`question/experience-to-capability/`
- 实践判断：`finding/retrieval-candidate-competition/`
- 共读专题：`study/after-a-correction/`；场景保留 `?scenario=legacy&phase=after`
- material：`material/a-tma-state-aware-memory/`
- 按问题查询：`?practice=重复候选#practice`；failure-surface thread：`?thread=retrieval-active-context`；reading path：`?path=from-revision`

已有的 `?material=`、`?study=`、`?question=`、`?finding=` 链接继续可用，在发布站点由浏览器转成对应的物理路径。本地直接打开源码 `index.html` 或用简单 HTTP server 预览源码时，继续使用 query routes。仅阅读页面列入 [sitemap](https://indeliblevivi.github.io/agent-memory-study/sitemap.xml)；搜索、筛选和场景状态不生成重复索引页。构建、验收和发布边界见 [网站说明](docs/website.md)。

共读可通过 `externalReadings` 连接官方文档、实现与论文线索，逐项保留类型、阅读范围、来源和限制；这些引用不增加 bibliographic materials / Zotero counts，也不自动提升原材料的阅读深度。

第四个共读[概括之后，往事还记得准吗？](https://indeliblevivi.github.io/agent-memory-study/study/representation-and-use/)连接十三篇外部来源：四篇重点正文与附录／方法实读、一篇综述选读、八篇摘要核验。它将[原事件／概括／并存](research/representation-use-study/README.md)与[双语取用及跨语言纠正](research/multilingual-use-policy/README.md)分成两项研究协议。此类专题明确显示“研究方案尚未执行”，提供方法入口，不显示模拟实验控件或结果；当前没有这两项研究的效用或答案质量实验结果。资源与输入可用性诊断不能替代这些结果。

双语研究提供独立的[离线案例校准工具](research/multilingual-use-policy/README.md#离线案例校准工具)：用 Python 标准库检查来源窗口与回顾性情境，生成本地 HTML 并导出带审阅状态的 JSON。它不接入 reading room 的在线标注，也不训练模型；私人输入、生成页面与标注文件由使用者在 repo 外保存。

全部内容检索覆盖材料、共读（含跨源阅读）、问题专题与实践判断，支持空格分隔的跨字段多词匹配，并展示命中位置。实践入口另提供本地关键词匹配，接受带关键短语的中英文问题，最多返回三条相关判断；它不调用模型、embedding 或远端搜索，也不承诺理解任意自然语言。
搜索与筛选也写入 query parameters；material、study、question、finding、practice、scenario / phase、thread、path 使用 browser history，back / forward 可以恢复对应视图。

Cloudflare Web Analytics 收集 visits、page views、referrers、国家/设备类别和 Web Vitals 等 aggregate 信号，不使用 cookie 或 localStorage 识别、画像访客。它不记录 query string，本站也没有 custom events。公开的 material / study / question / finding 路径可以出现在 page-view 统计中；practice、搜索、筛选和 scenario / phase 参数不进入这些统计。这不等于知道某位访客读完了哪篇内容。

Constellation 是同一 canonical data 的 semantic projection：failure surfaces 使用固定语义 anchors，material
位置由它的 `failureSurfaces` membership 与 stable ID 派生；没有逐篇维护的第二份 layout truth。新增 material
会自动成为一颗星，跨 surface material 会成为 bridge。Desktop 使用可键盘进入的 SVG，mobile 使用同源 matrix；
坐标、连线、星环与亮度都不表示论文质量、重要性或阅读进度。

## 把判断带回正在做的事

网页的“研究与实践”入口可下载当前查询结果；每条判断页也可以单独导出。在本地 checkout，无需安装依赖：

```bash
node tools/export_practice.cjs --query '候选增加之后，结果被重复条目占满' --format markdown
node tools/export_practice.cjs --finding revision-needs-scope --format json --out /tmp/ams-brief.json
node tools/export_practice.cjs --query '增量更新之后，怎样检查保留范围' --format markdown
node tools/export_practice.cjs --finding output-guard-is-not-unlearning --format json
```

导出使用同一 canonical 内容和查询实现，保留 reader、材料与证据链接。匹配只在当前进程或浏览器运行，没有应用层查询日志或私人项目映射。网页查询写入可分享的 URL 和 browser history；直接打开或刷新时，该 URL 随页面请求交给静态托管服务。把 brief 放进目标项目原有的设计或测试流程即可，AMS 不自动修改其他 repo。

空查询先展示前三条判断；可用示例问题或关键词查找其他判断，也可以从问题专题与“全部内容”进入全部五条。每次查询仍最多返回三条，导出内容与当前结果一致。学习与纠正专题的两条新判断来自已执行的结构化实验，提出的是目标侧验收方法；尚无公开采用记录，不表示自然语言任务收益或遗忘效果已经成立。

研究专题与实践判断的结构、证据归属和修订方式见[维护说明](docs/research-practice.md)。实践建议保持 `proposed-transfer`；应用记录分别使用 `cited`、`adopted`、`rejected` 或 `inconclusive`，不自动晋级为效果证据。单篇的 `designTransfer` 继续保持 `proposed-not-run`。

本轮组织已有证据，没有新增真实模型 pilot 或 KV mapper 拟合。跨模型实验仍以[现有 runner 的执行状态](research/kv-prefill-transfer/README.md)为准；问题专题中的“下一问”不是实验结果。

## PDF 怎样分发

这里采用 hybrid distribution，不把“网上能下载”冒充“可以再分发”。27 份 canonical materials 中，10 篇有明确的 `CC BY 4.0` 或 `CC BY-NC-SA 4.0` 许可，因此原样放在 `papers/`；另 17 篇只链接作者、publisher、arXiv 或 institutional repository 的 official full text。逐文件作者、来源与许可见 [THIRD_PARTY_NOTICES.md](./THIRD_PARTY_NOTICES.md)。

不要单独下载 `agent-memory-study.rdf`：其中 10 个 attachment 使用相对路径。请下载 `main` branch ZIP、解压后再导入 RDF；具体步骤与导入后应出现的结构见 [ZOTERO-IMPORT.md](./ZOTERO-IMPORT.md)。tagged Zotero ZIP 只在显式发版时更新，可能暂时落后于 `main`。Doyle 1979 只链接 MIT DSpace 的 official scan，本地 OCR derivative 不在 repo 或分享包里。

## 本地运行

直接打开 `index.html`，或启动一个静态 server：

```bash
python3 -m http.server 8080
```

然后访问 `http://localhost:8080/`。

学习与纠正实验可以用 Python stdlib 重新拟合并核对保存结果：

```bash
python3 -B research/decision-learning-study/study.py --check
python3 -B -m unittest discover -s research/decision-learning-study -p 'test_*.py'
```

共读专题的 deterministic 演示可以无依赖复跑：

```bash
node research/correction-scope-study/run.js
node --test tools/test_revision_study.cjs
```

[方法、逐场景结果与反例](./research/correction-scope-study/README.md)说明全部前提。它演示规则如何消费来源与范围，不模拟 LLM、不计算总排名，也不改变各篇的 reading depth。浏览器与本地 runner 使用同一份 engine；页面不保存访客的阅读记录，场景由 URL 恢复。

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

Memora close-read 所附的 forgetting-metric / judge-binding audit 可用 reader-supplied exact paper 与 clean official
checkout 验证 checked artifacts；不需要 model、API key 或 memory backend：

```bash
PYTHONDONTWRITEBYTECODE=1 \
python3 research/memora-forgetting-contract-audit/verify_checked.py \
  --source /path/to/Memora \
  --paper-pdf /path/to/from-recall-to-forgetting-arxiv-2604.20006v1.pdf
```

artifact 将 paper-reported FAMA / Table 3、current official source behavior、30-file released-input census 与 synthetic
contract matrix 分层记录；exact source rebuild、raw receipts、aggregation identity 与 claim ceiling 见
[`research/memora-forgetting-contract-audit/`](./research/memora-forgetting-contract-audit/)。它不生成 judge verdict、
不运行四个 LLM 或六个 memory agents，也不把 current successor source 或缺少 eval reports 的 release 冒充
paper-time execution / Table 3 reproduction。

MEMPROBE close-read 所附的 fixed released-artifact audit 可直接复核 checked public receipts：

```bash
python3 research/memprobe-recovery-boundary-audit/verify_checked.py
```

frozen protocol、source-locked runner、完整 public-safe receipts 与分项 decision 见
[`research/memprobe-recovery-boundary-audit/`](./research/memprobe-recovery-boundary-audit/)。它只验证 exact release 内
可机械检查的 joins、stored historical score arithmetic、packet/store binding 与 stored attribution-stage reduction；
不是 MEMPROBE benchmark rerun，也没有重发 historical retrieval 或重跑 simulator、memory system、slot filler、judge
与 attribution model。

MNL close-read 所附的 promotion-cohort / coverage audit 也可先做 receipt-only 校验：

```bash
python3 research/mnl-promotion-cohort-audit/verify_checked.py --mode receipt-only
```

frozen protocol、exact-current-source runner、synthetic identity ledgers 与 raw / derived receipts 见
[`research/mnl-promotion-cohort-audit/`](./research/mnl-promotion-cohort-audit/)。它只验证锁定 current official source
在公开 synthetic fixtures 上的 batch promotion、cohort filtering、exact-subject top-1 与 evaluation-denominator
contracts；不复现 MNL paper experiments，也不把 net-positive survivor decision 解释成 full-cohort、per-item、
subgroup、held-out 或 deployment non-regression。

*Useful Memories Become Faulty When Continuously Updated by LLMs* close-read 所附的 exact-current released-row /
verifier-coverage / denominator / schedule-fixture audit 同样先做 receipt-only 校验：

```bash
PYTHONDONTWRITEBYTECODE=1 \
python3 research/faulty-memory-release-boundary-audit/verify_checked.py \
  --mode receipt-only
```

若要重新建立当前 invocation 的 source-bound evidence，需要 exact clean source commit 与 reviewed arXiv v1 PDF，
并把 fresh work root 放在有足够空间的位置：

```bash
PYTHONDONTWRITEBYTECODE=1 \
python3 research/faulty-memory-release-boundary-audit/verify_checked.py \
  --mode source-bound \
  --source /path/to/Memory-Collapse-Eval \
  --paper-pdf /path/to/useful-memories-become-faulty-arxiv-2605.12978v1.pdf \
  --work-root /external-disk/faulty-memory-source-bound-fresh
```

完整 protocol、两份 chronology-preserving review amendments、final receipts 与 claim ceiling 见
[`research/faulty-memory-release-boundary-audit/`](./research/faulty-memory-release-boundary-audit/)。它不调用 model、
API 或 agent environment，也不重跑论文实验；receipt-only 只证明 package/internal consistency，stored
comparison 不自证历史上的两次 process，fresh source-bound invocation 才执行自己的两棵 roots。

### VerMem 规则 verifier 的固定源码复跑

先按[实验说明](research/vermem-verifier-boundary-audit/README.md)在 repo 外准备固定 commit 的官方 checkout，再运行：

```bash
python3 -B research/vermem-verifier-boundary-audit/audit.py \
  --upstream /path/to/VerMem --check
```

该命令实际调用上游 `LocalVerifier`，比较 12 个 public synthetic cases 与已保存结果。它不执行 memory 状态更新、LLM 语义 verifier 或论文训练；五个接受反例不能换算为系统错误率。

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

## Reader 验证

`python3 -B tools/verify_reader.py` 校验 canonical、证据归属绑定、问题/判断引用、全站搜索、实践查询/导出与 generated payload，
并复跑五组无模型的确定性研究及一组 stdlib 小型分类器学习/纠正实验（含真实参数拟合），另检查 AgeMem、C2C 与 Jev 已保存 receipt 的输入绑定和内部一致性；
同时用原创合成案例检查离线 casebook 的来源、情境与 review 合同；这不等于运行双语 scorer 或确认真实材料的效用标签。
Jev 的完整源码复跑需要外部 pinned checkout，命令与替身范围见[实验说明](research/jev-memory-contract-study/README.md)；reader 入口只验证其保存 receipt。
C2C receipt 校验不加载权重或执行 inference，fresh run 见[实验说明](research/c2c-cache-retraction-study/README.md)。
跨模型 KV runner 需要 PyTorch 和固定外部源码，使用[独立验收命令](research/kv-prefill-transfer/README.md#先验收再使用真实权重)，不包含在该本地验证入口内。
AgeMem 官方模块的 fresh run 需要外部固定 checkout，见[复跑说明](research/agemem-reward-observation-audit/README.md#复跑)。真实浏览器测试与受限环境的验证边界见
[贡献指南](CONTRIBUTING.md#evidence-ownership-and-reader-checks)。
离线校准页另以 `python3 -B tools/test_casebook_browser.py --output-dir dist/browser-check/casebook` 检查合成材料的标注、确认、下载与重载；沿用上述 Playwright 环境，CI 也运行此检查。
Reading Room validation 检查源码与生成站点；PR 只生成可检查的 artifact，main 在全部检查通过后发布同一 artifact。仓库 Pages 需启用 GitHub Actions，首次切换与回退见 [网站说明](docs/website.md)。
