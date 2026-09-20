#!/usr/bin/env python3
"""Verify initial HTML, hydration and navigation of an already-built Pages artifact."""
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
import threading
from urllib.parse import urlparse, parse_qs
from xml.etree import ElementTree as ET
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--site-root', type=Path, default=ROOT / 'dist/site')
    parser.add_argument('--browser-executable')
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'dist/static-reader-check')
    args = parser.parse_args()
    site = args.site_root.resolve()
    urls = [n.text for n in ET.parse(site / 'sitemap.xml').iter('{http://www.sitemaps.org/schemas/sitemap/0.9}loc')]
    data = json.loads((ROOT / 'data/materials.json').read_text())
    assert len(urls) == 1 + sum(len(data[k]) for k in ('materials','studies','questions','findings'))
    assert len(set(urls)) == len(urls)
    assert not any(urlparse(u).query or urlparse(u).fragment for u in urls)
    checks, errors = [], []
    with tempfile.TemporaryDirectory() as directory:
        (Path(directory) / 'agent-memory-study').symlink_to(site, target_is_directory=True)
        class Handler(SimpleHTTPRequestHandler):
            def log_message(self, *_): pass
            def send_error(self, code, message=None, explain=None):
                if code != 404: return super().send_error(code, message, explain)
                content = (site / '404.html').read_bytes()
                self.send_response(404); self.send_header('Content-Type','text/html'); self.end_headers(); self.wfile.write(content)
        server = ThreadingHTTPServer(('127.0.0.1',0),partial(Handler,directory=directory))
        thread = threading.Thread(target=server.serve_forever,daemon=True); thread.start()
        origin = f'http://127.0.0.1:{server.server_port}'
        base = origin + '/agent-memory-study/'
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(executable_path=args.browser_executable)
                try:
                    for enabled in (False, True):
                        context = browser.new_context(java_script_enabled=enabled,viewport={'width':1440,'height':1000},reduced_motion='reduce',accept_downloads=True)
                        context.route('**/*',lambda r:r.continue_() if r.request.url.startswith(origin+'/') or r.request.url.startswith('file:') else r.abort())
                        page = context.new_page(); page.on('pageerror',lambda e:errors.append(str(e)))
                        for canonical in urls:
                            response = page.goto(origin + urlparse(canonical).path,wait_until='load'); assert response.status == 200
                            expect(page.locator('h1:visible')).to_have_count(1)
                            assert len(page.locator('main').inner_text()) > 500
                            expect(page.locator('link[rel=canonical]')).to_have_attribute('href',canonical)
                            expect(page.locator('meta[name=description]')).to_have_count(1)
                            assert page.title() == page.locator('meta[property="og:title"]').get_attribute('content')
                            initial_title = page.locator('h1:visible').inner_text()
                            if not enabled:
                                refs = page.locator('a[href], link[href], script[src]').evaluate_all("nodes => nodes.map(n => n.href?.baseVal ? new URL(n.href.baseVal,document.baseURI).href : n.href || n.src).filter(Boolean)")
                                for ref in refs:
                                    u = urlparse(ref)
                                    if u.netloc != urlparse(origin).netloc: continue
                                    assert u.path.startswith('/agent-memory-study/'), ref
                                    target = site / u.path.removeprefix('/agent-memory-study/')
                                    assert target.is_file() or (target / 'index.html').is_file(),ref
                            checks.append({'url':canonical,'javascript':enabled,'heading':initial_title})
                        if enabled:
                            for width in (1440,390,320):
                                page.set_viewport_size({'width':width,'height':900})
                                page.goto(base+'?study=after-a-correction&scenario=legacy&phase=after',wait_until='load')
                                assert urlparse(page.url).path.endswith('/study/after-a-correction/')
                                expect(page.locator('#study-scenario')).to_have_value('legacy')
                                expect(page.locator('#study-phase-after')).to_have_attribute('aria-pressed','true')
                                page.locator('#study-phase-before').click(); page.go_back()
                                expect(page.locator('#study-phase-after')).to_have_attribute('aria-pressed','true')
                                page.reload(); expect(page.locator('#study-scenario')).to_have_value('legacy')
                                page.goto(base+'question/experience-to-capability/',wait_until='load')
                                page.locator('#inquiry-practice a[data-route=finding]').first.click()
                                expect(page.locator('#inquiry-title')).to_have_text(data['findings'][0]['title'])
                                page.reload(); expect(page.locator('#inquiry-title')).to_have_text(data['findings'][0]['title'])
                                page.goto(base+'material/a-tma-state-aware-memory/',wait_until='load')
                                toc = page.locator('#article-toc a').last
                                if toc.is_visible():
                                    target_hash = urlparse(toc.get_attribute('href')).fragment
                                    toc.click()
                                    assert urlparse(page.url).path.endswith('/material/a-tma-state-aware-memory/')
                                    assert urlparse(page.url).fragment == target_hash
                                    assert page.locator('#'+target_hash).evaluate('e=>Math.abs(e.getBoundingClientRect().top)<250'), target_hash
                                page.locator('a.site-mark').click()
                                expect(page.locator('#atlas-view')).to_be_visible()
                                assert urlparse(page.url).path == '/agent-memory-study/'
                                page.goto(base+'?practice=重复候选#practice',wait_until='load')
                                assert parse_qs(urlparse(page.url).query)['practice'] == ['重复候选']
                                page.reload(); expect(page.locator('#practice-query')).to_have_value('重复候选')
                                expect(page.locator('link[rel=canonical]')).to_have_attribute('href',urls[0])
                                with page.expect_download() as event:
                                    page.locator('#practice-export').get_by_role('button',name='下载 JSON',exact=True).click()
                                brief = json.loads(Path(event.value.path()).read_text())
                                assert brief['findings'][0]['id'] == 'retrieval-candidate-competition'
                                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
                                checks.append({'width':width,'legacy_study_history_reload_toc_home_practice_download':True})
                            page.goto((ROOT/'index.html').as_uri()+'?material=pm-bench',wait_until='load')
                            expect(page.locator('#material-title')).to_contain_text('PM-bench')
                            checks.append({'source_file_mode':True})
                        response=page.goto(base+'material/does-not-exist/',wait_until='load');assert response.status==404
                        expect(page.locator('meta[name=robots]')).to_have_attribute('content','noindex')
                        expect(page.locator('h1')).to_have_text('这里没有这篇内容。')
                        context.close()
                    assert not errors, errors
                finally: browser.close()
        finally: server.shutdown();server.server_close();thread.join()
    args.output_dir.mkdir(parents=True,exist_ok=True)
    (args.output_dir/'results.json').write_text(json.dumps({'passed':True,'checks':checks,'errors':errors},ensure_ascii=False,indent=2)+'\n')
    print(f'PASS: {len(urls)} initial HTML pages + hydration, 3 viewports, legacy routes/history, TOC, practice export, source file mode and 404')

if __name__ == '__main__': main()
