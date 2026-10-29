# 复跑本地研究的三条接续路径

这些示例使用原创合成材料与仓库已有公开研究，不读私人目录、不调用模型或远端服务，也不执行项目 Git、push 或部署。它们检验产品怎样保存、连接与恢复证据；交互通过不构成模型收益、科学新发现或真人研究结果。

先按[本地环境指南](local-workspace.md)安装已锁定依赖，按[网站构建指南](website.md)生成同一 React reader。Python 环境还需已有的 `tools/browser-requirements.txt` 和 Chromium。PDF 文字层使用本地依赖 `pypdf`；不安装 OCR。

```bash
python3 -B tools/seo_build.py --output dist/acceptance-site
python3 -B tools/test_local_reader.py \
  --site-root dist/acceptance-site \
  --output-dir /path/to/new-acceptance-evidence
```

输出位置可选，私人 runtime 始终在 source checkout 外；若输出目录位于 checkout，脚本另在系统临时目录创建 runtime。每次运行使用新的数据目录，原证据不覆盖成另一份运行。服务是实际 `python -m services.local ... serve --port 0` 子进程，按终端打印的地址访问，支持 Pages base prefix；API 仍为同源 `/api`。测试只允许本机网络，遇到外部请求或页面错误会失败。`--browser-executable` 可显式指定已有测试浏览器，不启动日常 Chrome profile。

`results.json` 保存各故事的实际 exact refs、job 身份、恢复检查和边界；screenshots 与启动日志留在同一输出目录。原件、案头、备份、日志都是私人验收资料，不加入公开 source 或站点。失败会保留已发生的状态和页面证据；修复后用新的输出目录复跑。

## 一次陌生来件，从部分阅读走向有限问题

在「带进来」写一句尚未理解的话，例如“future questions、multilingual 与 representation 中，相同观察还能回答 XOR 吗？”先保存 Capture，再明确命名这份原创示例；没有注册标识时，不把它冒称为 DOI／arXiv 论文。

在同一次来件的「原件与实际阅读」中选择一个真实本机 PDF，先看文件计划，再确认取得。测试生成一份有真实 xref、两页和可选文字的原创 PDF，包含：

> A partial reading is not a complete observation of every future question.

选择 PDF 文字层提取，明确 coverage 为 partial，记录刚读到的片段。原 bytes、Extraction 和 ReadActivity 分开；保存双页文件不等于读了全文。提取文字可以留到案头，词项候选关联仍是阅读入口，不升级成正式支持。

随后对读 [PR7 未来问题文章](../study/entries/future-questions-and-memory.md)、[多语言经验研究论述](../study/entries/experience-becomes-policy.md)和[表征与使用](../study/entries/representation-and-use.md)，保存固定摘录、私人批注、两处比较和下一问。在实验空间明确提交 P8 future-access 的固定状态对，检查实际区分序列及其获准行动；有限构造不推广为模型收益。停驻后重启服务，旧 refs、摘录与私人旁注应保持。

## 保留旧依据，再复核正式关系与发表选择

示例为原创旧／新 scope、固定旧 quote、两个必要前提及替代 warrant。旧 excerpt 保留原 target、representation、selector；新版本不回填旧 quote。Review 可以选择已明确引用的历史 snapshot，而不是只允许当前 head。

当前公开的[表征研究](../study/entries/representation-and-use.md)已经区分 executed scripted/oracle 与尚未执行的 provider 比较，应可明确 checked-unchanged，不造新正文 revision。其他确有修改的私有文稿先保存有 base 的提议，逐项接受，再由 DB owner 原子应用；旧 base 移动时保留提议与当前文本，另行决定。

候选关系先接受成正式关系，再组合 AND 前提与 OR 完整 warrant。范围、定位、理由和独立性判断各自明确；来源多不等于独立，撤回一个理由不自动判 claim 为假。

选择文章 metadata、正文及允许分发的附件，填写真实许可依据与署名，检查 paths、bytes、digest 和闭包。下载的 patch 带确切 base，可审查后另行应用；普通 HTTP 没有 Git 写入 gate。Repository、build、site 观察独立。Synthetic local bare push 后 build 失败和旧 site 保留的 owner 回归由 `services.local.test_publication` 覆盖；这不代表真实外部发布。

## 从 C2C 历史失败，走到有界分析修订

在实验空间选择 C2C，明确执行历史 inspect。查看 retained float32 原阈值失败、same-shape 与 precision diagnostics，再「固定历史检查依据」。这一步保存实际历史 Artifact，不创建新的 Run，也不补回早期未保存的完整 tensors。

留下有范围的 Observation，提出三个竞争解释：数值精度／kernel 路径、shape／position／任务范围改变，以及仍待识别的语义机制。诊断 Design 写清怎样控制变量，状态保持 proposed-not-run。再实际核查已保存 receipt；算术／合同检查不是模型重跑。

独立撰写 Analysis，绑定 Observation、方法与限制；历史分析允许没有 run_refs，但不能没有精确的依据。修改分析保存同一身份的新 revision，旧分析仍可读。带着该固定 Analysis 创建私人文稿时，明确保留依据；把解释缩到现有控制能支持的范围，保留 missing raw 和未解决问题。Observation、Design、Analysis、作者文稿不会自动成为已接受 Interpretation。

## 故障与恢复检查

脚本还实际演练：

- 两个 tab 打开同一 base，先后提交不同输入，第二份发生 CAS 冲突；两份输入及历史都保留，再明确选择如何继续。
- Chromium Input domain 的 composition／commit 进入真实 React textarea，中文保存重开不丢字；这不是对全部操作系统输入法的认证。
- 服务已 commit 而 HTTP ack 丢失，页面显示未确认；导出 `ams-uncommitted-input/1`，恢复连接后先预览再显式导入，不把未知提交标作已保存。
- 实际 kill／restart 同一 data root，会话 token 更新，旧 token 拒绝；固定依据、quote、note、正式理由和私人 manifest 保留。
- CLI request 等待一条真实低成本 native job 到终态，然后完整 backup，恢复到新 data root，doctor、固定摘录与 native evidence 均再打开检查。活动 attempt 的备份策略见本地指南。
- 私人案头包含合成 canary，公开选材与所提供 public artifact 的全部 bytes 不含该标记；本地可恢复不表示获得公开权利。

Job lease、中断 raw、missing blob、unknown provider、cancel 等 owner 级故障由既有 jobs／repository tests 覆盖，不靠本脚本重复所有矩阵。公共静态/no-JS、旧 routes、地图、字体、性能与更广视口检查仍由其他 reader suites 拥有；统一入口是 `python3 -B tools/verify_reader.py --browser`。
