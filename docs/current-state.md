# 当前源码与交付状态

下一代实现位于 `next/ams` 集成分支，已完成本地统一验收，仍是待 PR 审查的源码候选；本文件不表示已合并 main、部署或上线。

- 内容真源已迁移到 `study/source-corpus/` 的 Work / Revision / Note；旧 material aliases、研究方法与历史 receipts 保留。当前目录有 27 份来源札记、15 篇研究文章、2 个问题与 5 条判断。
- `apps/reader/` 是新的四空间与共享 reader；`tools/seo_build.py` 调用 Node prerender。公开静态与明确启动的 Python / SQLite 本地环境共用前端，事实域分开。
- 公共文件保留 continuation v1、workspace v1/v2 导入，写出 workspace v3。活动 DB 为 repository v4；完整 backup2 包含原件与已结束 attempt 的原始证据，升级回退必须用对应版本与完整备份。
- 有限可区分性 instrument 与条件贡献研究各有原生实现。P9 本地 FTS5 / oracle controls 不等于自然语言 provider 结果；provider 准备计划未绑定真实账号或执行。
- 修订发表可以生成私有 preview / patch；默认本地服务不授予 Git 写入或站点激活。三个事实轴分别记录。

2026-10-30，本地统一 `verify_reader.py --browser` 通过：454 个 Python tests、134 个 Node tests，以及独立 public / static / local / casebook 浏览器流程；50 个阅读页面加 404，49 个对象正文。覆盖五种视口、200% 字号、10,000 项 metadata、三条完整研究接续与真实进程／备份恢复。检查使用原创合成材料和公开内容，不代表真人研究、provider 效果或作者的视觉接受。

下一集成门是 Linux CI 与 PR 审查。发布状态只在实际发生后更新；部署流程见[网站运维](website.md)，备份与升级见[本地环境](local-workspace.md)。
