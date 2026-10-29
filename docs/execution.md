# 本地独立研究执行

本接口只服务显式启动的 local mode；公共静态 reader 不探测或调用它。研究算法、native trace、gold、评分与历史 receipts 仍由各 `research/` 拥有。没有 provider、网络或任意命令入口。

## 接口与迁移 owner

`services.local.jobs.JOBS_MIGRATION_SQL` 是 CREATE 语句 tuple。Repository 的 migration owner 在版本2事务中逐句执行；JobManager不执行迁移，不改变user_version。表名前缀为 `execution_jobs / execution_attempts`，不写 canonical records。

```python
manager = JobManager(repo, project)
manager.registry()
manager.submit({"study":"observation-contract-study", "operation":"run",
                "parameters":{"operation":"search-pair", "model":"score-weighted",
                              "left":"revision", "right":"scope"}}, idempotency_key="operator-choice-1")
manager.list()
manager.get(job_id)
manager.cancel(job_id)
manager.retry(job_id, idempotency_key="explicit-retry-1")
manager.evidence(job_id)
manager.close()
```

所有输出位于 `repo.root/jobs/<job UUID>/attempt-<N>/`；客户端只传具名研究与公开参数。Replay只接受manager已拥有的成功run job ID，不接受路径/URL/argv。`get`附attempt元数据与已有result；`list`只给状态摘要。`evidence`分别投影Run、Analysis和Interpretation，缺失内容为not-recorded，不从分数推used。

异步状态为queued/preparing/running/succeeded/failed/cancelled/interrupted/indeterminate/blocked，另有cancel-requested过渡。submit幂等键同payload返回同job，不同payload拒绝；retry必须新幂等键，在同job下保留新attempt。实例持有OS排他lease，不能两个manager同时控制同data root。新实例取得lease后，把前实例未完成的本地执行标interrupted；外部提交未知标indeterminate且禁止自动重试。本registry不执行外部provider。

原生子进程只继承执行所需的固定 PATH / Python 配置与宿主的 `LD_LIBRARY_PATH`、`DYLD_LIBRARY_PATH`、`DYLD_FALLBACK_LIBRARY_PATH`。这些路径保持父子进程使用同一套 runtime 库，避免 SQLite 版本在执行与 replay 间漂移；其他环境变量（包括 provider 凭据）不自动传入。

关闭tab不终止任务；服务shutdown必须先manager.close，再repo.close。close终止本owner子进程组并等待cleanup。取消在确认进程退出后才终态cancelled；超时或服务退出保留partial文件，不伪造成功receipt。日志默认只记服务端状态，不复制研究prompt/secret；stdout/stderr不公开，结果保留原生研究内容。非零退出、result缺失/损坏、run后native核验失败都不得标成功。

## 能力矩阵与限制

registry为每owner列实际操作。inspect读取保存结果；prepare仅生成计划/能力说明；check-saved-results的证据含义由owner声明；run是真实本地计算；replay核本manager的native raw；packet携带公开选定研究数据。不能用统一verb推断所有研究都支持重跑。

P8 run调用既有adapter的analyze-model/search-pair；P9 run调用run-local并保留完整request/response/score。representation-use固定full/forward/scripted，revision-propagation保持native设置；两者允许显式limit用于小型运行，必须显示原计划与实际完成数，不能把有限执行称全protocol完成。task-relative-sufficiency重做有限枚举。C2C只读保存receipt并调用其纯verify_receipt核算，绝不新推理；decision-learning只读历史结果，不重新训练。

Run保存执行时plan/source identity；replay返回独立Analysis，指向原Run，不改原manifest。Interpretation默认not-recorded：任务成功不生成科学结论。P1无真实retriever，selected仅原生all材料；used unknown。C2C未保存的早期tensor仍缺失，不能提供虚假raw replay。

同源 HTTP、CLI 与 Lab 调用同一 JobManager；科学解释仍由作者明确保存，执行成功不提供公开发表权限。


| Owner | 实际广告操作 |
| --- | --- |
| observation-contract-study | inspect / prepare / run（具名有限模型）/ check-saved-results（精确重算）/ packet |
| conditional-contribution-study | inspect / prepare（含待绑定provider计划）/ run / replay / check-saved-results / packet |
| representation-use-study | inspect / prepare（native plan）/ run / replay / check-saved-results（compact summary校验）/ packet |
| revision-propagation-study | inspect / prepare（native plan）/ run / replay / check-saved-results（compact summary校验）/ packet |
| task-relative-sufficiency | inspect / prepare / run（枚举）/ check-saved-results / packet |
| c2c-cache-retraction-study | inspect（含execution-history）/ check-saved-results（保存receipt结构与算术）/ packet |
| decision-learning-study | inspect / packet；不重新训练 |

`JobManager.get(...)["result"]`为`ams-local-study-result/1`，source_bindings和plan_digest用于本次执行身份；Run附native_manifest与原生completion字段，partial计划保持其原生计数。Analysis指向原Run，replay保留original_manifest；Interpretation默认为not-recorded。P8的Evidence Inspector给实际finite trace；P1/P9给native request/delivered/response/score；P2保留native episode；C2C/decision历史缺raw不会补造。

跨进程恢复通过工作目录process.json的PID与OS进程出生时间核对前owner子进程组，避免只按复用PID杀进程。worker先保存身份，等待owner launch ack才开始研究；没有ack自行退出。close终止本owner并join，未完成输出仍保留。当前注册表完全本地，不接provider执行；indeterminate状态的模拟测试只证明禁止自动重试，不声称真实provider语义已实现。

验证命令：`python3 -B -m unittest services.local.test_jobs services.local.test_studies -v`。测试使用真实Repository迁移、小型native运行和故障注入，不改研究源码或历史结果。完整界面与恢复检查见[验收指南](acceptance.md)，后端测试不替代整条用户流程。

## Lab 用户工作流与固定依据

`apps/reader/src/lab.tsx`导出`LabView({catalogue,link,desk})`，复用当前WorkspaceAdapter与DeskStore。local且jobs已启用时才读取`/studies`和`/jobs`；public/file模式只读取明确选择的公开保存结果、协议与原生复验说明，不探测本机服务。P8显示声明模型、pair、步数/成本界限与实际区分trace；P9显示真实原生cells及candidate/rank/score/selected、实际送达、response和score。部分执行默认先看已记录cells，可明确包括未执行计划；family、executor、arm、送达预算分开筛选，不把同family任务数当独立样本。

研究选择可先于 registry 返回；表单操作始终由当前研究实际支持的能力确定。支持本地计算的研究默认 `run`，历史检查研究默认 `inspect`；切换研究本身不提交任务。

提交`POST /jobs {plan,idempotency_key}`等待回执；HTTP acknowledgement丢失时保留同一key与参数，禁止自动新attempt。选择历史job后通过`GET /job?id=`恢复，关闭页面不取消任务。取消、明确retry、owned-source-job raw replay分别调用原有接口；indeterminate不显示自动retry。表单/Observation草稿在异步错误时保留；未保存Observation草稿和失败时的当前输入可主动下载；刷新仍会丢弃未保存草稿，Lab没有额外浏览器持久化。

`POST /job/snapshot {id}`由`ExperimentViewService(repo,project,jobs).snapshot(id)`处理，不需新migration。它只在用户明确固定成功的真实run时，先核验native raw及源identity，再把当时绑定的code/protocol/dataset、执行config、result和inspection保存为private CAS Artifacts与canonical Run。rubric_ref指向实际拥有原生评分器的study.py；没有单独绑定protocol文档的有限runner，protocol_ref也明确指向该执行源码，config标明这一范围，不临时捏造执行时文档。已有快照按job/attempt固定复用，检查CAS完整性；重开不是fresh raw replay。原生raw后来缺失时，原canonical bytes仍可保留，新的raw核验必须拒绝。inspect、prepare和历史receipt不能制造新Run。

执行器的 Analysis 仅在确有原生 raw 验证时单独保存并指向 Run；P8 有限计算没有独立 Analysis receipt 时保持未记录。作者也可明确保存分析文本，记录方法、结果、适用范围和引用的 Observation，这不等于执行器完成了 raw 验证。Interpretation 不由 job 成功自动生成。Lab用户显式写Observation的statement、scope、预期/实际与locator，basis_refs绑定Run实际结果Artifacts；可同时提出含两个竞争解释、诊断对照与未解决问题的Design，status保持proposed-not-run。Observation/Design同一`/units`原子保存后，再将精确`{run_ref,observation_ref,design_ref?}`追加到当前`session.payload.lab_links`并保存`next`。若案头保存失败，已提交科学记录和原commands保留，同一保存可恢复连接，不谎报整条已落盘。没有当前案头时才创建新的实验接续。

历史 inspect / check 可显式调用 `POST /job/history-snapshot {id}`，固定当时的 receipt 和 source bytes 为 Artifact，返回 `new_execution=false`，不制造新 Run。由此保存的 Observation 以非空 `basis_refs` 固定历史依据；作者 Analysis 可以 `run_refs=[]`，但必须引用实际 Observation。接续使用 `{basis_ref,observation_ref,design_ref?,analysis_ref?}`，重开仍能看到固定历史字节。缺失的早期 raw 保持缺失；新的分析版本保留旧版并通过 expected revision 检查。

Design schema当前没有typed basis字段，连接由现有Session的精确lab_links持有，Design正文同时保留可读Observation/Run身份；未另造规范。继续空间展示这些记录的正文、固定版本和下一步，Lab 可重开已连接的 Observation/Design。

P9 prepare展示原生冻结provider计划中的真实cells/prompts、request bytes与output cap；provider、model revision、tokenizer、input token count和fee cap未绑定，authorized=false，没有live执行按钮。诊断bytes不是provider tokens。C2C保留float32阈值失败、same-shape/precision诊断及早期raw缺失；只读历史不等于本次模型运行。所有研究的used仍为unknown。

Focused检查：`python3 -B -m unittest services.local.test_experiment_views -v`；React focused tests位于`apps/reader/test/lab.test.ts`，由 npm test 和统一 verifier 执行。全 App 的历史检查、Observation → Design → Analysis → 有界文稿修订与恢复由 tools/test_local_reader.py 检查。
