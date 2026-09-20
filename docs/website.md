# 阅读站点：构建、验收与发布

公开地址为 <https://indeliblevivi.github.io/agent-memory-study/>。`index.html` 是源码 shell；`data/materials.json` 是内容真源，`assets/materials-data.js` 是已有 browser projection。`assets/app.js` 负责全部正文和交互，`assets/seo.js` 负责共享 route/metadata。Python Playwright 只在构建、验收时使用，发布产物没有服务端 runtime。

## 从源码到页面

```text
data/materials.json → assets/materials-data.js
                              ↓
index.html + app.js + seo.js → build-time Chromium → dist/site/
                              同一个 renderer       HTML + sitemap + public assets
```

先使用自己的 Python 虚拟环境，安装既有测试依赖：

```bash
python3 -m pip install -r tools/browser-requirements.txt
python3 -m playwright install chromium
python3 -B tools/verify_reader.py
python3 -B tools/test_reader_browser.py
python3 -B tools/seo_build.py
python3 -B tools/test_static_reader.py
```

构建逐页加载本机 HTTP 上的真实 reader，禁止向外部 host 发请求，完成正文和 metadata 后捕获 HTML。站点仍保留既有 Cloudflare Web Analytics beacon；构建和验收不会发送访问数据。标题、描述、canonical、Open Graph、Twitter summary card 和 WebSite/WebPage JSON-LD 在静态 HTML 与浏览器切页时使用同一实现。论文作者不被标成札记作者，reading depth、原文结果、本站观察和未验证建议不因 SEO 改变。

首页和每份 material / study / question / finding 对应一个物理目录中的 `index.html`。当前内容生成 32 个阅读页面，另有真实的 `404.html`。构建按 canonical 数据枚举页面，新增内容无需维护第二份 URL 清单。sitemap 只列这些规范绝对地址，不写不可靠的 lastmod，也不收集搜索、practice、筛选和场景组合。

构建拒绝覆盖已存在的输出目录。重复构建时选择新的 `--output dist/site-next`，验收使用 `--site-root dist/site-next`；保留前一份 artifact 供比较。`--browser-executable` 可指定已安装的专用 Chromium，仅是本地环境选项。不要使用日常浏览器 profile。

复制范围仅含 tracked `assets/`、公开 `research/` 和 `docs/`、canonical 允许随站分发的 PDF、RDF、项目介绍 PDF、manifest 与两份 notices。原有 `.md` 证据/notice 地址仍作为 Markdown 文件提供，已有 GitHub evidence 链接保持不变。不会复制 `.git`、`tools/`、忽略文件或私人材料。

## 本地查看

源码预览继续支持 `python3 -m http.server 8080` 与 直接从文件打开 `index.html`，使用旧 query routes。

构建站点须挂载在 `/agent-memory-study/` 子路径，以与生产相同的 base path 检查 PDF、目录锚点与深链接。可把生成的 `dist/site/` 复制到一个本地预览目录下的 `agent-memory-study/`，从该预览目录启动 HTTP server，打开 `/agent-memory-study/`。`test_static_reader.py` 自动创建临时挂载并检查：全部页面的初始 HTML / 无 JS 内容 / 开启 JS 后的视图、资源链接、desktop / mobile、旧链接、场景、history、reload、目录、practice 导出、源码 file mode 与 404。

旧 query 详情链接仍被接收，并由浏览器通过 location replace 跳到相应的真实 HTML 页面（不多留一条 history entry）；这不是 HTTP 301。无 JavaScript 时，请使用新的物理详情链接。正文和普通阅读链接不依赖 JavaScript；搜索、星图交互、场景切换和导出需要它。非法物理地址由 GitHub Pages 返回 HTTP 404；query filter 状态沿用原 reader 语义。

## Pages 激活与交付

在这次静态构建启用前，Pages 使用 `main` 根目录的 branch build。启用准备好的 workflow 是独立账号操作，需获得发布授权。不要把 PR、构建成功或 HTML 文件存在称作已上线。

经授权后：

1. 在 repository Settings → Pages 将 Build and deployment Source 从 Deploy from a branch 改为 GitHub Actions。
2. 合并经过检查的源码 PR。`Reading Room validation` 在 main 验证源 reader、构建 artifact 并验证静态 reader，只有全部通过才上传和部署同一 `dist/site/`。
3. 在 Actions 核对该 main commit 的 `reader` 与 `deploy`；检查公开首页、四种详情类型、PDF、sitemap 和一个不存在的路径，分别确认正文/metadata、HTTP 200 与 404。

PR 运行只上传构建产物用于检查，不部署。手动触发也只有 `main` 可进入 deploy job。workflow 不自动修改 Pages 设置、Google Search Console、DNS 或 analytics 配置。

回退时优先以普通 revert commit 回退到已验证的静态实现，再经同一 workflow 部署。首次迁移若需完整恢复旧方式，应一并恢复迁移前源码（使用普通 revert，保留历史）和 Pages 的 `main` 根目录 branch source，并等待原 branch build 完成；只改设置或只回退源码不能证明恢复完成。回读线上页面和旧深链接后才确认。

项目位于 `github.io` 的子路径，爬虫规则由 origin 根部 `/robots.txt` 决定；本项目不发布容易误解的子目录 robots.txt。可将本项目的 `sitemap.xml` 提交到它自己的 Google URL-prefix property。验证所有权、Google 接收 sitemap、抓取、收录和实际排名是不同状态，不由构建成功推断。
