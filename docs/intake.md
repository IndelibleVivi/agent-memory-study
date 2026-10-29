# 带进来、辨认与实际阅读

本地服务先保存一次遭遇，再决定材料身份、阅读或研究用途。public reader仍是临时/file模式；本服务不授权公网探测本机，也不运行输入文本中的指令。

## 接口与migration

Repository v4 迁移逐句执行四个 tuple：`INTAKE_MIGRATION_SQL`、`IDENTITY_MIGRATION_SQL`、`ACQUISITION_MIGRATION_SQL`、`CONNECTORS_MIGRATION_SQL`。服务不自行建表或改变版本。canonical Capture.input继续为string；blob/context/return_when、取得attempt、身份决定/redirect和connector record版本保存在repo外private操作表，未伪装成新canonical schema。

```python
captures = CaptureService(repo, project, public_records=known_public_entities)
identities = IdentityService(repo, public_records=known_public_entities)
acquisition = AcquisitionService(repo, public_records=known_public_entities)
```

public_records只能来自compiler已知精确实体，不从导入文件任意解析URL。CLI与UI应调用这些相同service，不绕过Repository写表。所有写动作要显式idempotency_key；重复键同payload返回原receipt，换payload拒绝。更改attention或confirm要携带Capture的expected_revision。

## Capture保存ack与停驻

`capture(text,channel='manual',why_now='',context_refs=(),idempotency_key=...)`只要求有界非空输入。没有title、来源、领域、问题也合法；context refs若给出须可解析到精确snapshot。返回capture和真正commit后的ack，才可显示“已保存在本地”。相同材料再次带入用新key，保留新遭遇与理由。

`capture_bytes(label,selected_bytes,media_type=...,idempotency_key=...)`先存Capture，再创建选定文件plan并接受bytes。服务器从不把label当本机路径打开。`batch([...],batch_key=...)`逐项处理，失败不回滚已成功项，最多100项。`get(id)`返回Capture和私有details，`list()`列当前遭遇；`attention(id,state,expected_revision=...,return_when=...,idempotency_key=...)`独立保存active/resting/waiting/closed和可空的重开条件。它不是证据真值或永久有用性标签；没有清零目标或自动提醒。

## 身份候选、确认与版本

`parse_identifier`只用明确namespace规则：完整DOI、arXiv family与可选vN、GitHub完整40位commit。URL只规范scheme/host，不删query或fragment、不重排有意义参数；credential-bearing URL拒绝。GitHub分支/tag/仓库名不是fixed commit或稳定repo身份，必须由选定connector返回真实repository ID与完整commit，再明确确认。题名、词项相近不自动合并。

`resolve(capture_id)`返回解析依据、零个/一个/多个候选和unresolved/candidates/conflicted，不能取双exact alias的第一项。原有明确决定保留在details与decision历史里；resolve不是自动接受。

`confirm(capture_id,title=...,expected_revision=...,idempotency_key=...,work_ref=None,identifiers=(),publisher_version=None,new_work=False)`是明确人审动作。单一已确认alias可复用既有Work；多个冲突必须给精确work_ref或显式new_work保留独立身份。重复Capture不抹去不同缘由，也不默认制造重复Work。没有可靠publisher版本时只是metadata身份，`snapshot_captured=false`，不冒充取得了原文。

显式identifiers和publisher_version同样经过allowlist校验，不能借手工字段传入假DOI、语义题名alias、别的arXiv family或mutable Git ref；edition须绑定已确认family或选定fixed commit locator。命名规则校验不认证来源真实性。

arXiv v2/v3与完整Git commit形成固定SourceRevision。同一publisher版重用原精确ref，metadata-only变化不制造内容新版；后来重新打开v2可取得原v2 snapshot，不用v3替换。无publisher版本的网页只有实际取得新字节时才建立observed snapshot，保留旧版；它不是出版社edition或语义修正判定。bytes相同重用该内容snapshot，Artifact/取得时间仍独立记录。

`merge(work_refs,target_ref,reason=...,idempotency_key=...)`和`split(work_refs,reason=...,idempotency_key=...)`只改变当前redirect决策；旧Work/Revision/引用不重写。双alias冲突、暂时混同与后来分开都可恢复，历史决定保留。

## 获取计划与明确执行

`plan_file(capture_id,filename=...,media_type=...,max_bytes=...,idempotency_key=...)`只记选定文件metadata；`execute_file(plan_id,selected_bytes,idempotency_key=...)`才接受原bytes。未知类型也可保存Artifact；超限保留有界原始prefix与partial receipt，不宣称完整原件。Capture一直保留。默认8MiB，可显式选择1 byte至32MiB预算。

`plan_url(capture_id,url,max_bytes=...,idempotency_key=...)`不联网。`execute_url(plan_id,allowed_hosts=(),idempotency_key=...)`默认host集合为空，因此不fetch。调用方须把用户明确许可转换为本次精确 host 集合；每个redirect及final URL重新检查。默认transport只做GET，不带cookie/auth，不上传材料，不绕过访问限制。

transport开始前先commit started attempt；中断后重入同key只返回indeterminate，不自动GET。明确检查后重试用新key。真实URL请求不在本轮测试中执行：测试使用注入/recorded transport，包括跨host redirect、HTTP失败、网络异常、字节预算和KeyboardInterrupt。允许host不等于所有来源均可信或原文完整，保存requested/final URL、status、取得时间、bytes及分发限制。

receipt携带实际保存bytes的digest、保存/收到的byte length及obtained_range；HTTP 206保留Content-Range并标partial，即使没有超预算也不能标fulltext。超限只保留prefix，不把该prefix的digest称为完整远端文件hash。

`inspect(capture_id)`返回该遭遇的plans/attempts/extractions。`cancel(plan_id,idempotency_key=...)`持久取消plan，保留已有原件和receipts；当前GET可能直到返回/15秒transport timeout后才观察到取消，已返回bytes仍按原预算保留并标cancelled。取消后的新执行被拒绝；明确重试须新plan和新key。已完成执行的原key仍返回原receipt，不能被取消改写。

URL host许可是受信任local API的明确执行输入，不来自网页内容。公开站不能调用此接口；main的权限/Origin检查仍须保护它。这里不发现账号、读取浏览器登录态、扫描库或打开任意本机路径。

## 原件、Extraction与ReadActivity

`extract(artifact_ref,source_revision_ref=None,parser='text-utf8',coverage='unknown',idempotency_key=...)`对原source-manifestation Artifact使用具名parser：text-utf8、text-utf8-lines、可选已安装pypdf。提取输出不能递归冒充新原件以提升coverage。不会安装包或运行OCR。PDF parser不可用、坏格式或扫描件无文字时blocked，原Artifact保持。原bytes、输出文本、extractor/config/version各自记录；换parser不改变publisher edition。

没有SourceRevision时仍可产生带`representation_of`的文本Artifact，状态available-unbound；canonical Extraction等待绑定实际SourceRevision，不能用Capture冒充source_revision。非source snapshot的reading/excerpt通过representation_of绑定，source版继续用source_revision_ref。不同parser输出可共享同一CAS bytes，但有独立提取receipt。partial原件不得标fulltext；下载全文也不会创建ReadActivity。

`read_activity(target_ref,representation_ref,extent,method=...,receipt_ref=...,actor=...,idempotency_key=...)`只在明确选择/声明/实际Agent delivery时调用。human-selected检查片段确实存在于准确表示；manual-declaration是人的声明，不认证理解。Agent必须使用agent-delivered与agent actor，receipt Artifact中的target_ref/representation_ref/extent/delivered_text必须和实际表示相符；没有receipt不得借滚动/open事件升级阅读。

`reanchor(excerpt_ref,new_representation_ref)`只给同一对象identity的exact/ambiguous/missing候选，不修改旧excerpt及其原target/basis。当前selector和extent沿canonical string/字符串数组，尚未扩展为PDF区域或W3C selector对象。

`compare(old_artifact_ref,new_artifact_ref)`比较明确选择的两个Artifact：返回原bytes是否相同、各自精确SourceRevision及有界UTF-8 diff；二进制不伪造文本diff。它不判定语义修正，也不自动替换引用。

所有提取文本和导入内容均为数据。UI须textContent/安全reader呈现，不innerHTML执行源HTML，不依据包中instructions运行工具。

## 只读connector与研究候选

`ZoteroConnector.decode(recorded_response,selected_keys,attachments=False,annotations=False)`仅解码明确选择的records，要求真实library Last-Modified-Version与integer item version。item key不是BibTeX citation key，record version不推断paper edition。attachment/annotation是独立显式选择；不返回本机path、tags或private notes。

`GitHubConnector.decode(repository_response,commit_response,requested_ref=...,observed_at=...)`要求真实repo integer ID、完整commit和blob SHA，保留mutable ref与观测时间，API patch只称返回片段，不冒充完整源码diff。两个connector均无live transport或writeback，本轮只验证原创recorded fixtures。

`record_observation`持久保存选定cursor/receipt；`capture_connector(receipt,idempotency_key=...)`逐选定record创建Capture与私有metadata链接，不自动确认、取附件或阅读。metadata进入后仍走相同explicit confirm路径。调用方可在已有授权时提供真实只读 transport，不能把fixture测试称live通过。

`context_links(capture_id,changed_public=None)`从当前compiler公共metadata给出有source fragment/locator/方法身份的有界lexical候选；不调用embedding或模型，也不自动变support/contradiction。changed_public只接受已知kind/id，通过固定本机research_context桥调用共享ResearchMap引用关系；formal scope通过P6已接受关系查询，导航membership不产生impact。结果是复核/对读入口，不能据此宣布理论等价、矛盾或旧结论失效。

已确认新版有predecessor时，返回新旧精确ref与structural-review-candidate，并从旧版查询正式关系的review paths。该范围只说明哪些旧依据值得复核，`semantic_conflict=false`不替代阅读或判断。

## 验证与集成边界

```bash
python3 -B -m unittest services.local.test_intake services.local.test_identity services.local.test_acquisition services.local.test_connectors -v
```

使用已有含schema依赖的Python环境。测试临时文件默认位于系统临时目录；宿主可用`AMS_P4_TEST_ROOT`指定已存在的scratch目录。最终记录只报告实际检查。覆盖陌生概念、多次Capture/Work复用、歧义/merge/split、版本保留、metadata-only、未知bytes/超限/提取失败、同bytes不同parser、明确阅读、旧quote重定位、GET权限/redirect/断网/中断、实际shared ReferenceGraph和fixture connector版本合同。

继续空间的 Capture 卡片复用这些 same-origin API：可以在同一次遇见中选择本机原件，先检查 file plan，再明确确认接受文件字节；原来的问题、身份与捕获理由保持。取得后可用已安装的 pypdf 提取文字、标记实际阅读片段并固定摘录。CLI 的 request 入口调用同一 dispatcher，完整路径与失败恢复见[验收指南](acceptance.md)。IdentityDecision／AcquisitionAttempt 等操作表只作私人状态，不宣传为正式交换协议。

P5的既有Observation可通过`capture(text,context_refs=[exact_observation_ref],...)`显式带入，按Repository精确引用验证；本服务不复制或重跑研究receipt。P6入口为context_links返回的正式review paths及具名候选，是否建RelationProposal/ChangeSet仍须通过P6明确操作。
