#!/usr/bin/env python3
"""Build static reading pages with the existing client renderer (Python Playwright)."""
from __future__ import annotations
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
from urllib.parse import urlparse
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
BASE_PATH = '/agent-memory-study/'


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *_):
        pass


def build(output: Path, executable: str | None = None):
    from playwright.sync_api import sync_playwright, expect
    if output.exists():
        raise ValueError('Output already exists; select a fresh --output directory to preserve previous artifacts.')
    data = json.loads((ROOT / 'data/materials.json').read_text())
    routes = [('', {})] + [(f'{kind}/{item["id"]}/', {kind: item['id']})
        for kind, key in [('material', 'materials'), ('study', 'studies'), ('question', 'questions'), ('finding', 'findings')]
        for item in data.get(key, [])]
    # Preserve tracked public research/docs referenced by reading notes, plus canonical PDFs.
    assets = subprocess.check_output(['git', 'ls-files', '-z', 'assets', 'research', 'docs'], cwd=ROOT).decode().split('\0')
    # seo.js may be untracked during authoring; it is an explicit source dependency.
    files = set(filter(None, assets)) | {'assets/seo.js', 'site.webmanifest', 'NOTICE.md',
        'THIRD_PARTY_NOTICES.md', 'agent-memory-study.rdf',
        'publications/agent-memory-study-project-introduction.zh-CN.pdf'}
    files.update(item['pdf']['url'] for item in data['materials'] if item['pdf']['delivery'] == 'bundled')
    source = (ROOT / 'index.html').read_text()
    source = source.replace('<html lang="zh-CN">', '<html lang="zh-CN" data-static-reader="true">')
    source = source.replace('<head>', f'<head>\n    <base href="{BASE_PATH}">', 1)
    with tempfile.TemporaryDirectory(prefix='ams-static-') as temporary:
        stage = Path(temporary) / 'agent-memory-study'
        stage.mkdir()
        for relative in sorted(files):
            destination = stage / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / relative, destination)
        for path, _ in routes:
            destination = stage / path / 'index.html'
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(source)
        server = ThreadingHTTPServer(('127.0.0.1', 0), partial(QuietHandler, directory=temporary))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        origin = f'http://127.0.0.1:{server.server_port}'
        pages, urls = {}, []
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(executable_path=executable)
                try:
                    context = browser.new_context(viewport={'width': 1440, 'height': 1000}, reduced_motion='reduce')
                    context.route('**/*', lambda r: r.continue_() if r.request.url.startswith(origin + '/') else r.abort())
                    page = context.new_page()
                    errors = []
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    for path, query in routes:
                        response = page.goto(origin + BASE_PATH + path, wait_until='load')
                        assert response.status == 200
                        expect(page.locator('h1:visible')).to_have_count(1)
                        expect(page.locator('link[rel="canonical"]')).to_have_count(1)
                        assert page.locator('h1:visible').inner_text().strip(), path
                        assert urlparse(page.url).path == BASE_PATH + path, page.url
                        urls.append(page.locator('link[rel="canonical"]').get_attribute('href'))
                        # Browser captures the real renderer, including hidden/view state and head metadata.
                        page.locator('noscript').evaluate("node => { node.textContent = '正文与阅读链接无需 JavaScript；搜索、星图交互、场景切换和 brief 导出需要启用 JavaScript。'; }")
                        pages[path] = page.content()
                    if errors:
                        raise RuntimeError(f'Renderer errors: {errors}')
                finally:
                    browser.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
        if len(set(urls)) != len(routes):
            raise ValueError('Duplicate canonical URLs')
        output.mkdir(parents=True)
        for relative in sorted(files):
            destination = output / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(stage / relative, destination)
        for path, html in pages.items():
            destination = output / path / 'index.html'
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(html)
        (output / '.nojekyll').write_text('')
        namespace = 'http://www.sitemaps.org/schemas/sitemap/0.9'
        ET.register_namespace('', namespace)
        sitemap = ET.Element(f'{{{namespace}}}urlset')
        for url in urls:
            ET.SubElement(ET.SubElement(sitemap, f'{{{namespace}}}url'), f'{{{namespace}}}loc').text = url
        ET.ElementTree(sitemap).write(output / 'sitemap.xml', encoding='utf-8', xml_declaration=True)
        (output / '404.html').write_text(f'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex"><title>页面不存在 · Agent Memory Study</title>
<link rel="stylesheet" href="{BASE_PATH}assets/styles.css"></head>
<body><header class="site-header"><a class="site-mark" href="{BASE_PATH}">Agent Memory Study</a></header>
<main id="main-content"><h1>这里没有这篇内容。</h1><p>地址可能有误，也可能已经改变。可以回到书房继续找。</p>
<p><a href="{BASE_PATH}">回到阅读书房 →</a></p></main></body></html>''')
    print(f'Built {len(routes)} reading pages + 404; {len(files)} public assets; {len(urls)} sitemap URLs: {output}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'dist/site')
    parser.add_argument('--browser-executable')
    args = parser.parse_args()
    build(args.output, args.browser_executable)


if __name__ == '__main__':
    main()
