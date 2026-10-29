# 本地整理成文、论证复核与选择发表

继续空间的「整理成文、比较依据与修订」使用 `ReviewView`，连接固定依据、作者草稿、逐项审阅与公开选择。轻量文稿不必先有 claim；接受一个关系不会替作者判断论点为真。公开 reader 可以读取固定快照，保存、应用和发表准备需要本地服务。选择发表不会自动执行 Git、build 或部署。

## 日常路径

1. 从案头带着依据进入，或选择公开／私有精确快照。比较面板展示各自固定正文和范围；旧摘录仍绑定原 target、representation 和 selector。
2. 创建札记、随笔、判断或问题线索，或选择维持、缩窄、解释修订、需要实验、暂不确定。正文和开放问题可以保存为案头编辑停点。需要实验须写竞争解释与诊断对照，只创建 proposed Design，不生成 Run。
3. 保存 ChangeSet 后逐项接受、拒绝或暂停，原子应用只含已接受项。界面显示 base、拟改文字与冲突时当前版本。冲突不覆盖新版本、不丢提议；checked-unchanged 不造目标 revision 或空 Git commit。
4. 候选关系先明确范围、绑定、位置和理由，再单独接受为正式关系。AND 选择必要前提；OR 选择完整 AND warrant。撤回更新支持检查，保留旧关系及替代 warrant。共享上游与独立性声明另列，来源数量不证明独立。
5. 对完成的 Entry 明确选择 metadata、正文、结果和附件，以及各自许可依据、授权和署名。预览显示真实路径、bytes 和 digest，可下载公开投影、私人 manifest 与有 base 的可应用 patch。私人 manifest、ChangeSet 和内部 refs 不进入公开投影。
6. 仓库、build、site 分别确认与记录。记录观察不执行网络验证；仓库可见不等于站点更新。

异步失败保留输入。未知 ack 的原操作用同一 idempotency key 重试，确认前不能替换正文；明确 4xx 校验拒绝后可修正重提。编辑停点等待真实保存 ack；连接、冲突和容量问题显示在页面，还可下载草稿与待确认命令。保存仍使用既有 DeskStore。

## owner、schema 与可信授权

`arguments.py`、`revisions.py`、`publication.py` 分别拥有论证、owner apply 与选择交付；`authoring.py` 的 `ReviewAuthoringService` 组合这些服务，不复制科学算法。compiler 拥有 PublicCorpusManifest，research 拥有原生结果。实体引用精确 `kind/id/revision`，public records 由 Repository 缓存并参与跨实体校验。

```python
service = ReviewAuthoringService(repo, project, public_records)
arguments = ArgumentService(repo, public_records, review_authorizer=None)
revisions = RevisionService(repo, project, public_records,
                            review_authorizer=None)
publication = PublicationService(repo, project, public_records,
                                 review_authorizer=None, execution_gate=None)
```

Repository v3 执行 `ARGUMENTS_MIGRATION_SQL`、`REVISIONS_MIGRATION_SQL`、`PUBLICATION_MIGRATION_SQL`，服务不设第二个 migration owner。本轮无需新表。既有私人操作表保存独立 definitions `OperationalApplyUnit`、`OperationalApplyReceipt`、`PublicationDelivery`，schema 分别为 `ams-operational-apply-unit/1`、`ams-operational-apply-receipt/1`、`ams-publication-delivery/1`。实际写入与恢复读取调用 `check_structure`，不只 fixture 校验；它们不替代 canonical ChangeSet 和 PublicationManifest。

可信本地 human 动作默认可审阅。agent/service 或请求 delegation 必须经过 host callback `review_authorizer(actor, operation, target_ref, requested_delegation_ref)`，返回真实可解析的精确 grant ref，并保存进 Review。callback 应验证操作和目标边界，拒绝时抛错。导入文件中的 actor/delegation 不能自行建立授权。复核授权与生产 Git/deploy 的 gate 独立。

## HTTP 与组件接口

Application 已分发以下 same-origin 接口：

| 接口 | 输入与结果 |
| --- | --- |
| `GET /api/authoring/catalogue` | 可选 refs、标题、范围、public/editable、只读 Git base |
| `POST /api/authoring/open` | `target_ref` → 固定正文、当前私有 head、关系、bundle、影响候选 |
| `POST /api/authoring/create` | `kind/title/body/byline/intro/scope/basis_ref?/idempotency_key` → 私有作者对象；Entry 无需 claim |
| `POST /api/authoring/propose` | `base_ref/decision/body/scope/explanation/open_question/metadata/idempotency_key` → ChangeSet；公开改写先建私有副本 |
| `POST /api/authoring/publication` | `entry_ref/public_id/base_commit/rights/include_metadata/include_text/attachments/idempotency_key` → 私人 manifest + preview |
| `POST /api/authoring/patch` | `manifest_ref` → 可应用 patch，不写项目 Git |
| `POST /api/argument/{propose,accept,reject,bundle,withdraw,impact,status}` | 对应 ArgumentService，formal review 保留真实授权和理由 |
| `POST /api/revision/{create,review,pause,apply,prepare-git,record-git}` | 对应 RevisionService；`apply` 为 `apply_db` |
| `GET /api/revision/units?id=…` | owner 单位与 receipt 恢复 |
| `POST /api/publication/{prepare,preview,projection,delivery,deliveries}` | 原生选择、预览、投影、独立交付观察 |
| `GET /api/publication/site` | 最后已记录 active receipt，不是在线核验 |

`ReviewView({desk,catalogue,link})` 自带 CSS，经继续空间 `?space=continue&tool=review` 接入，不增加永久空间。`payload.review_target_ref` 指定上下文，`payload.review_editor` 保存编辑停点，不进入公开 URL。新稿可明确选择固定 basis_ref，保留 Analysis → Entry 的作者依据；选择器包含当前对象和案头已经显式引用的历史版本，不扫描全部私人历史。

## 论证与逐 owner 应用

`propose(fields,idempotency_key=...)` 只建 RelationProposal；accept/reject 保存原候选与 Review。bundle 核对同一固定结论、scope 和已接受关系。support_status 沿显式 accepted supports/derives 检查上游、撤回与循环，展示尚存理由、共享上游，不计算自然语言真值。impact 只沿正式关系产生复核候选；同 domain、导航和未接受 proposal 不产生依赖。

ChangeSet review/application/publication 三轴独立。create、review、apply_db 和作者编排支持幂等，同 key 不同 payload 拒绝。`apply_db(id,item_ids,expected_revision=...,idempotency_key=...,actor=...)` 在同一个 Repository 事务中检查全部 base，写全部目标、ChangeSet、typed unit 和 receipt。一个冲突阻止该 DB unit 其他写入；禁止改保留身份或重绑旧 excerpt。public corpus 的 no-change 只记录复核，其他公开写入需 Git owner。相等替换归为 no-change，旧 accepted 快照不改。

prepare_git 保存精确 base 与 before/after bytes，路径限 study/research/docs；record_git_unit 核对实际 commit ancestry 和文件字节。跨 DB/Git 没有分布式事务；DB 已应用不被后续 Git 失败抹掉。恢复保留原 key 和原计划，不因 ChangeSet 已前进而创建新单位。

## 选择、patch 与交付恢复

每项为 `entity_ref/artifact_ref/public_path/rights/reviewed_digest/release_review`，rights 包含 basis、license_or_permission、attribution。Artifact 已明确 public-candidate/public，实际 blob 长度与 digest 必须匹配。Entry body 同时兼容 compiler 的 `study/entries/*.md` 和旧 `entries/*.md`，不会重复 prepend study。metadata 采用 allowlist，依赖缺失拒绝，不自动扫描或发表私有库。

作者生成 release Entry、Artifacts、Manifest、关联 ChangeSet publication_refs 与幂等 ack 在一个 DB 事务完成。release 私有 exact release_of 和旧 ChangeSet/unit 保留，公开投影不带私人 payload。prepare 是选择而非交付成功。

scan_public 检查所交全部 bytes 中声明的 canary、本地路径和实际 private root；它不是通用秘密识别。真实 build 后仍须检查完整产物。patch 支持 UTF-8、无末尾换行和 Git binary patch，headers 只有可移植的已选路径；`git apply --check` 可审查，生成不应用。

默认 execution_gate=None，execute_selection 拒绝 Git 写入。可信 gate 必须绑定具体 project/base/digests/remote；普通导入或审阅没有此权限。授权后检查干净树，写已审字节、显式 stage、commit，无变化为 checked-unchanged。remote 只接受已配置名称，不接受 URL、path 或 option。

执行先持久保存 preparing，commit 后先保存 committed 再 push，push 失败显式续同一个 commit。commit 成功 ack 丢失时，reconcile_commit 核对父 base、路径和字节再恢复，不再造 commit。record_delivery 是 operator-supplied observation；active site 需要匹配成功 build 的 source commit、artifact digest、部署 ID、URL 和核验时间。新 build 失败不清除旧 active receipt。

## 验证与当前边界

```bash
python3 -B -m unittest services.local.test_arguments services.local.test_revisions services.local.test_publication services.local.test_authoring schemas.test_core -v
cd apps/reader
npm run typecheck
```

使用已有 schema/browser 依赖，无需安装新包。focused `test/review.test.ts` 覆盖 exact refs、未知 ack 与明确 4xx、轻量文稿、诊断条件、正式 AND/OR 和交付确认；由 npm test 和统一 verifier 执行。

真实 Repository 与隔离 HTTP/React 验收包含：P0 当前公开范围 checked-unchanged；C2C 保留 float32 失败与 missing raw 的有界解释修订；v2/v3 scope 负控制、AND/OR 与旧摘录不重绑。另测 bounded delegation、原子冲突、丢 ack、rights/闭包/canary、二进制 patch、Git base/commit 恢复，以及 synthetic repo/local bare remote 的实际 push 后 build 失败、旧 site stub 保留。browser 检查 1440/390/320、键盘和保存重开；owned-module harness 不等于全 App 发布验收。

真实项目 Git、外部 provider、私人真人实验、账号和生产部署均未执行。全 App 接续由[统一验收](acceptance.md)检查；源码通过、构建通过、仓库可见、站点 active 是分别成立的事实。
