# 本地研究环境：安装、运行与恢复

本地模式由明确启动的 Python 服务提供，同源 reader 使用 SQLite 与不可变文件。数据目录必须在 repo 外的本机磁盘；不支持把活动数据库放在网络盘或以同步盘代替数据库备份。公开网站不会自动发现或连接这个服务。

## 安装与启动

使用 Python 3.13、Node.js 26 和含 WAL-reset 修复的 SQLite（推荐 3.51.3+，还需要 FTS5）。Python 版本不决定实际绑定的 SQLite 版本，先检查：

```bash
python3 -c 'import sqlite3; print(sqlite3.sqlite_version)'
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -r services/local/requirements.txt
npm ci --prefix apps/reader
python3 -B tools/build.py --write-json
python3 -B tools/seo_build.py --output dist/site
python3 -m services.local --data-root /path/to/private-ams serve
```

打开终端打印的地址。`--port 8317` 是默认端口，`--port 0` 可让系统分配。服务绑定 `127.0.0.1`，严格核对 Host / Origin / 会话 token；不开放 CORS，不记录私人请求正文。每次服务重启更换会话 token，旧页面先保存未确认输入，再刷新取得新会话。

同一公开 Pages artifact 可以直接用于本地服务；服务按 build receipt 中的 base 挂载。也可单独构建 `--base / --output dist/local-site`，启动时传 `--site-root dist/local-site`。build 拒绝覆盖已有目录，重建请选择新目录。依赖锁定在 reader 的 `package-lock.json` 与 Python requirements；没有后台 npm 服务。

SQLite 使用 WAL、FULL synchronous、单进程串行 writer 和数据库事务。`command_id` / `idempotency_key` 可重送同一命令；相同键换内容会拒绝。更新须带 `expected_revision`，冲突返回数据库现值与被拒绝输入，不静默覆盖。未知提交状态不自动重试外部执行。

## CLI 与持久化

根目录 `./ams` 等价于 `python3 -m services.local`，使用当前 Python 环境。

```bash
./ams --data-root /path/to/private-ams new '一个尚未完成的问题'
./ams --data-root /path/to/private-ams capture '陌生概念或链接' --why '为什么现在想留下'
./ams --data-root /path/to/private-ams list
./ams --data-root /path/to/private-ams open thread:ID
./ams --data-root /path/to/private-ams export thread:ID --out /path/to/private-desk.json
./ams --data-root /path/to/private-ams import /path/to/private-desk.json
./ams --data-root /path/to/private-ams import /path/to/private-desk.json --confirm-digest sha256:DIGEST
./ams --data-root /path/to/private-ams doctor
```

最后一个 import 的 digest 必须来自刚才的实际 preview，不能手填占位符执行。原文件不覆盖。`request /operation --json /path/to/body.json` 调用同一个 dispatcher；`--get` 将 JSON 字段作为查询参数。CLI 的 job 提交等待终态并保留真实输出；一个 data root 同时只有一个 job owner。服务运行时使用网页执行任务，不再启动第二个 CLI job manager。

公开索引只是 cache。`index-rebuild` 从当前 compiler manifest 和准确 Git 版本重建，不改私人对象。旧公开 snapshots 保留，旧摘录不会因为索引更新而失去依据。

## 备份、升级与回退

```bash
./ams --data-root /path/to/private-ams backup /path/to/new-backup
./ams restore /path/to/new-backup /path/to/new-private-ams
./ams --data-root /path/to/new-private-ams doctor
```

备份用 SQLite backup API 获取一致状态；`ams-backup/2` 同时保存引用 blob、每个已结束 attempt 的原始输出、结果和日志，并校验文件 identity。先等待正在运行的任务结束，或明确停止任务；有未结束 attempt 时拒绝生成完整备份。普通笔记写入不影响数据库快照的一致性。备份与恢复目标必须在项目之外且是新目录，失败中间目录保留为 `.partial-*`，不能当作完整备份使用。

恢复校验数据库、blob、任务文件清单和已完成结果，再打开新目录；旧 `ams-backup/1` 仅在没有实验 attempt 时可恢复，有任务记录却没有原件的旧备份须从原数据目录重新生成。复制单独的活跃 `research.sqlite3` 不构成完整备份。`doctor` 检查数据库、合同、引用与 blob identity；任务的科学证据仍须从执行空间检查和 replay，不能用文件完整性代替研究验证。

升级前保留完整备份与可运行的上一版源码／依赖环境。当前数据库版本由 repository 管理，迁移在事务中进行。旧程序遇到更高 schema version 会拒绝写入；回退程序时使用升级前备份恢复到新目录，不能让旧版本直接改写新数据库。恢复后实际打开研究线、固定摘录和一次 job 记录，再决定使用哪一份目录。

停止服务使用 Ctrl+C；中断任务保留 attempt 与有限日志，重启后标为 interrupted，再由明确 retry 创建新 attempt。卸载只移除源码、虚拟环境与构建产物；私人数据目录由研究者单独保管和决定，不自动删除。

## 执行与发表边界

本地 jobs 复用各自的 native runner，区分 Run / Analysis / Interpretation 与保存的历史 receipt。[执行指南](execution.md)列出支持入口和不可提升的结论。启动服务不会调用模型、扫描私人语料、写 Zotero 或上传材料。

公开发表先得到可审查 preview / patch；应用、Git、build 和 site observations 分开保存。普通服务未配置 Git 写入能力，记录一个 delivery observation 不会执行部署。授权与失败恢复见[修订发表指南](revision-publication.md)。
