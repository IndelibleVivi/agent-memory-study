# 阅读站点：构建、验收与发布

公开地址为 <https://indeliblevivi.github.io/agent-memory-study/>，继续使用 GitHub Pages 和已有 Actions workflow。`study/` 是内容真源，`index.html` 是唯一源码 shell；`assets/app.js` 负责全部正文与交互，`assets/seo.js` 统一 route / metadata。Python Playwright 与 Markdown parser 只用于构建和检查，发布产物没有 backend runtime。

## 从研究体到页面

```mermaid
flowchart TD
  S[study/ 正文与 metadata] --> C[content.py + build.py]
  R[research/ 原始研究 receipts] --> C
  C --> J[data/materials.json 兼容 projection]
  C --> B[assets/materials-data.js browser projection]
  B --> V[index.html + app.js + seo.js]
  V --> P[本机 Chromium 执行同一 renderer]
  P --> H[dist/site/ 静态 HTML + sitemap]
  V --> D[研究包 shared projection]
  D --> M[每页 index.md / index.json]
```

在自己的 Python virtual environment 安装依赖：

```bash
python3 -m pip install -r tools/content-requirements.txt -r tools/browser-requirements.txt
python3 -m playwright install chromium
python3 -B tools/build.py --write-json
python3 -B tools/verify_reader.py
python3 -B tools/test_reader_browser.py --output-dir dist/browser-check
python3 -B tools/test_casebook_browser.py --output-dir dist/browser-check/casebook
python3 -B tools/seo_build.py
python3 -B tools/test_static_reader.py
```

构建只请求本机 HTTP，捕获 renderer 生成的正文与 metadata，然后删除非活动／hidden 内容，避免文章初始 HTML 混入首页和另一份来源栏。`reader-shell.js` 从原始 `index.html` 派生，用于开启 JS 时恢复完整交互 shell；它不是第二份手工维护的文章模板。静态捕获里的 3D canvas 恢复为 SVG fallback，启用 JS 后才初始化 WebGL，保证无 JS 时也有完整封面。

首页和每份 material / study / question / finding 对应真实的 `index.html`。当前 27 份来源、12 篇文章、2 个问题、5 条判断共生成 47 个阅读页面，另有 `404.html`；总数按 canonical 枚举。详情目录还生成 `index.md` / `index.json`，通过页面研究包入口读取。构建期、CLI、browser 的包使用同一实现；不嵌入引用的论文全文或重复保存实验 receipt。

构建拒绝覆盖已存在的输出。重复构建用 `--output dist/site-next`，验收传 `--site-root dist/site-next`。`--browser-executable` 可指定专用 Chromium，不使用日常浏览器 profile。`dist/` 忽略，不提交。

复制范围包含 tracked `assets/`、公开 `research/` 和 `docs/`，明确的 reader 依赖、canonical 引用的正文、允许分发的 PDF、RDF、历史项目介绍 PDF、manifest 与 notices。不会复制整个 checkout、`.git`、`tools/`、private drafts、个人接续或机器状态。

## 预览与路由

源码可通过 `python3 -m http.server 8080` 或直接打开 `index.html` 阅读，使用 query routes。构建站点须挂载在 `/agent-memory-study/`：将产物放入预览根目录下的 `agent-memory-study/` 后从预览根目录启动 HTTP server。静态测试自动创建这一临时挂载。

公开路径有 `study/<id>/`、`material/<id>/`、`question/<id>/`、`finding/<id>/`。旧 `?study=` 等链接通过 browser location replace 转到相应物理页面，不是 HTTP 301。没有 JS 时直接使用物理路径；正文、普通阅读链接与静态研究包可读。源码 file mode 保留 query links。

首页 `?domain=` / `?direction=` 选择阅读分组，`?q=` 与 filters 用于搜索；旧 `?thread=` / `?path=` 自动展开 atlas 入口。已有场景 `scenario` / `phase` 保留。检索集合演算用 `k` / `ranking` / `need`，只作用于相应学习文章。Browser history 可恢复这些公开状态，sitemap 和 canonical 不收录查询／场景变体。

标题、description、canonical、Open Graph 与 JSON-LD 由同一 SEO module 生成。论文作者不被标成札记作者；展示、导出或索引不改变阅读深度与证据状态。

## 动态与私人接续

首屏 `continuity-sculpture.js` 是无外部依赖的 WebGL 曲面，表达延续与改变，不编码数据。Reduced-motion 默认静止，也可主动播放／暂停；离开视口或标签页停止 animation frame。WebGL 缺失或 context lost 时呈现 SVG。它不妨碍正文、搜索或路由。

接续笔记只存在页面内存及主动下载的文件，不上传或写入 URL / localStorage。导入最多 128 KB，恢复已知对象、受支持的 anchor 与演算，文本不执行。刷新前未下载的修改会丢失。公开研究包与个人接续是两个独立出口，不把个人文字带入共享包。

站点保留既有 Cloudflare aggregate beacon，不加 custom events 或其他 tracking。构建与测试拦截非本机请求；在线打开外部来源链接按用户操作发生。公开查询写入 URL 与 browser history，直接加载／刷新时 URL 会发给静态托管服务。完整使用边界见 [README](../README.md)。

## 发布与回退

现有 `.github/workflows/reader-validation.yml` 在 PR 和 main 运行同一组检查。PR 不部署；main 只有全部通过后，才上传并由独立 `deploy` job 发布同一 artifact。2026-10-18 的 Pages read-only 检查确认 `build_type: workflow`；本次无需切换账号设置。

源码完成、commit、push、CI 通过和 Pages 上线是不同状态。交付时核对目标 commit 的 `reader` / `deploy`，再读取公开首页、详情、sitemap 和一个不存在的路径。不要从本机构建成功推断线上已更新。

回退使用普通 revert commit，经过同一 workflow 重新发布，再核对线上页面和旧链接。不改写共享历史；Pages account settings、DNS、Search Console 与 analytics 配置不属于普通源码发布。

项目在 `github.io` 子路径，robots 规则由 origin 根部负责。保留公开 `google-site-verification` 标签；sitemap 列出物理阅读页，不虚构 lastmod。验证所有权、接受 sitemap、抓取、收录和排名分别核实。
