#!/usr/bin/env python3
"""Reading-room browser checks. Default: real HTTP/navigation on a Pages-like subpath.

--offline-render is a labelled DOM-only fallback for navigation-restricted hosts.
It does NOT test browser history, reload, HTTP serving, CDN or deployed Safari.
"""
from __future__ import annotations
import argparse
import functools
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import tempfile
import threading
from urllib.parse import parse_qs, urldefrag, urlparse

from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *_):
        pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--offline-render', action='store_true')
    parser.add_argument('--browser-executable')
    parser.add_argument('--output-dir', type=Path)
    args = parser.parse_args()
    data = json.loads((ROOT / 'data/materials.json').read_text())
    evidence = {'mode': 'offline-dom' if args.offline_render else 'http-e2e', 'checks': [],
                'skipped': ['HTTP navigation, reload and browser back/forward'] if args.offline_render else [],
                'errors': []}
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        (root / 'agent-memory-study').symlink_to(ROOT, target_is_directory=True)
        output = args.output_dir or root / 'evidence'
        output.mkdir(parents=True, exist_ok=True)
        server = ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(QuietHandler, directory=root))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f'http://127.0.0.1:{server.server_port}/agent-memory-study/'
        html = (ROOT / 'index.html').read_text()
        html = re.sub(r'<script\b[^>]*>.*?</script>', '', html, flags=re.S)
        html = re.sub(r'<link\b[^>]*>', '', html)
        html = html.replace('</head>', '<style>' + (ROOT / 'assets/styles.css').read_text() + '</style></head>')
        app = (ROOT / 'assets/app.js').read_text()
        offline_app = app.replace('window.location', 'window.__AMS_TEST_LOCATION').replace('window.history', 'window.__AMS_TEST_HISTORY')
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(executable_path=args.browser_executable, args=['--no-sandbox'])
                try:
                    for width, height in [(1440, 1000), (390, 844), (320, 740)]:
                        context = browser.new_context(viewport={'width': width, 'height': height}, reduced_motion='reduce')
                        # No third-party requests or analytics during tests.
                        context.route('**/*', lambda r: r.continue_() if urlparse(r.request.url).hostname == '127.0.0.1' else r.abort())
                        page = context.new_page()
                        page.on('pageerror', lambda error: evidence['errors'].append(str(error)))
                        def go(query=''):
                            if args.offline_render:
                                page.set_content(html)
                                page.evaluate('''url => {
                                  window.__AMS_TEST_LOCATION = new URL(url);
                                  window.__AMS_TEST_HISTORY = {};
                                  for (const method of ['pushState', 'replaceState']) {
                                    window.__AMS_TEST_HISTORY[method] = (s,t,u) => {
                                      window.__AMS_TEST_LOCATION = new URL(u, window.__AMS_TEST_LOCATION);
                                    };
                                  }
                                }''', base + query)
                                for name in ['materials-data.js', 'revision-study.js', 'reading-search.js']:
                                    page.add_script_tag(content=(ROOT / 'assets' / name).read_text())
                                page.add_script_tag(content=offline_app)
                            else:
                                target = base + query
                                previous_document = urldefrag(page.url).url
                                response = page.goto(target, wait_until='domcontentloaded')
                                if response is None:
                                    # Fragment-only navigation stays in the loaded document.
                                    # A new document must still provide an HTTP 200 response.
                                    assert previous_document == urldefrag(target).url, (page.url, target)
                                    assert urldefrag(page.url).url == previous_document, page.url
                                    assert urlparse(page.url).fragment == urlparse(target).fragment, page.url
                                else:
                                    assert response.status == 200, response.status
                            expect(page.locator('h1:visible')).to_have_count(1)
                        def current_url():
                            return page.evaluate('window.__AMS_TEST_LOCATION.href') if args.offline_render else page.url
                        def layout(label):
                            document_width, viewport_width, header_width, header_client_width = page.evaluate('''() => {
                              const header = document.querySelector('.site-header');
                              return [
                                document.documentElement.scrollWidth,
                                document.documentElement.clientWidth,
                                header.scrollWidth,
                                header.clientWidth,
                              ];
                            }''')
                            assert document_width <= viewport_width + 1, (
                                label, 'document', viewport_width, document_width
                            )
                            assert header_width <= header_client_width + 1, (
                                label, 'header', header_client_width, header_width
                            )
                        def record(name):
                            evidence['checks'].append({'width': width, 'check': name, 'passed': True})

                        go()
                        expect(page.locator('#reading-entry a')).to_contain_text('一条更正之后')
                        if width <= 390:
                            expect(page.locator('#menu-button')).to_be_visible()
                            expect(page.locator('#search')).to_be_visible()
                        layout('home'); record('home entry and layout')
                        for material in data['materials']:
                            go('?material=' + material['id'])
                            expect(page.locator('#material-title')).to_have_text(material['title'])
                            expect(page.locator('#material-findings li')).to_have_text(material.get('reportedFindings', []))
                            section = page.locator('#paper-ams-evidence')
                            if material.get('amsEvidence'):
                                expect(section).to_be_visible()
                                expect(section.locator('a').first).to_have_attribute('href', material['amsEvidence']['artifactUrl'])
                                for finding in material['amsEvidence']['findings']:
                                    assert finding in section.inner_text()
                                    assert finding not in page.locator('#paper-findings').inner_text()
                                section.locator('summary').click()
                                expect(section.locator('details')).to_have_attribute('open', '')
                            else:
                                expect(section).to_be_hidden()
                            layout(material['id']); record('material ownership/layout: ' + material['id'])
                            if width in (1440, 390) and material['id'] == 'statefuse-conflict-preserving-memory':
                                page.locator('#paper-ams-evidence').screenshot(path=str(output / f'ams-evidence-{width}.png'))

                        go('?q=%E4%B8%80%E6%9D%A1%E6%9B%B4%E6%AD%A3%E4%B9%8B%E5%90%8E#library')
                        expect(page.locator('#material-index [data-result-kind=study]')).to_have_count(1)
                        expect(page.locator('#material-index [data-result-kind=material]')).to_have_count(0)
                        page.locator('#material-index a[data-route=study]').click()
                        expect(page.locator('#study-title')).to_have_text('一条更正之后')
                        page.locator('#study-scenario').select_option('legacy')
                        assert page.evaluate('document.activeElement.id') == 'study-scenario'
                        page.locator('#study-phase-after').click()
                        assert page.evaluate('document.activeElement.id') == 'study-phase-after'
                        expect(page.locator('.study-output')).to_have_count(4)
                        expect(page.locator('#study-phase-after')).to_have_attribute('aria-pressed', 'true')
                        query = parse_qs(urlparse(current_url()).query)
                        assert query['scenario'] == ['legacy'] and query['phase'] == ['after'], query
                        layout('study after'); record('search to study, scenario, phase, focus and share state')
                        if not args.offline_render:
                            page.go_back()
                            expect(page.locator('#study-phase-before')).to_have_attribute('aria-pressed', 'true')
                            expect(page.locator('#study-scenario')).to_have_value('legacy')
                            page.go_back()
                            expect(page.locator('#study-scenario')).to_have_value('corrected')
                            page.go_back()
                            expect(page.locator('#search')).to_have_value('一条更正之后')
                            expect(page.locator('#material-index [data-result-kind=study]')).to_have_count(1)
                            page.go_forward()
                            expect(page.locator('#study-title')).to_be_visible()
                            record('real browser back/forward restores search and scenario')
                        go('?study=after-a-correction&scenario=legacy&phase=after')
                        expect(page.locator('#study-scenario')).to_have_value('legacy')
                        expect(page.locator('#study-phase-after')).to_have_attribute('aria-pressed', 'true')
                        if not args.offline_render:
                            page.reload(wait_until='domcontentloaded')
                            expect(page.locator('#study-phase-after')).to_have_attribute('aria-pressed', 'true')
                            record('direct share URL and real reload')
                        else:
                            record('direct state render (not navigation)')

                        go('?q=TRUSTMEM+Yang#library')
                        expect(page.locator('#material-index [data-result-kind=material]')).to_have_count(1)
                        expect(page.locator('#material-index a[data-route=material]').first).to_contain_text('TRUSTMEM')
                        expect(page.locator('.search-match-label')).to_contain_text('作者')
                        page.locator('#search').fill('<img src=x onerror=alert(1)>')
                        expect(page.locator('#empty-state')).to_be_visible()
                        expect(page.locator('img[src=x]')).to_have_count(0)
                        page.locator('#clear-filters').click()
                        page.locator('#depth-filter').select_option('read')
                        assert parse_qs(urlparse(current_url()).query)['depth'] == ['read']
                        expected = sum(m['noteDepth'] == 'read' for m in data['materials'])
                        expect(page.locator('#material-index [data-result-kind=material]')).to_have_count(expected)
                        layout('filtered search'); record('multifield query, empty state, text safety and filter URL')
                        if width in (1440, 390):
                            page.screenshot(path=str(output / f'search-{width}.png'))
                        for query in ['?material=missing', '?study=after-a-correction&scenario=missing&phase=bad',
                                      '?thread=retrieval-active-context', '?path=from-revision', '#%', '#missing[bracket]']:
                            go(query); layout(query)
                        record('invalid and legacy routes render')
                        context.close()
                finally:
                    browser.close()
            assert not evidence['errors'], evidence['errors']
            evidence['passed'] = True
        except Exception as error:
            evidence['passed'] = False
            evidence['failure'] = str(error)
            raise
        finally:
            server.shutdown(); server.server_close()
            (output / 'browser-check.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2))
        print(json.dumps({'mode': evidence['mode'], 'passed': evidence['passed'],
                          'checks': len(evidence['checks']), 'skipped': evidence['skipped']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
