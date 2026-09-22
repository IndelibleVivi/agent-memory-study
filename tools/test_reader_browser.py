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
                                for name in ['materials-data.js', 'revision-study.js', 'reading-search.js', 'practice.js', 'seo.js']:
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

                        # The two newest practice findings, shared by the direct
                        # question -> finding hop and the practice-desk checks.
                        new_findings = [item for item in data['findings']
                                        if item['id'] in ('correction-needs-retention-checks',
                                                          'output-guard-is-not-unlearning')]
                        assert len(new_findings) == 2

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
                        go('#inquiries')
                        expect(page.locator('#question-index a[data-route=question]')).to_have_count(len(data['questions']) * 2)
                        expect(page.locator('#practice-results .practice-result')).to_have_count(3)
                        page.locator('#question-index a[data-route=question]').first.click()
                        expect(page.locator('#inquiry-title')).to_have_text(data['questions'][0]['title'])
                        expect(page.locator('#inquiry-next')).to_contain_text('尚未运行真实模型 pilot')
                        layout('question dossier'); record('question entry, current judgment, evidence and next test')
                        if width in (1440, 390):
                            page.screenshot(path=str(output / f'question-{width}.png'))
                        page.locator('#inquiry-practice a[data-route=finding]').first.click()
                        expect(page.locator('#inquiry-title')).to_have_text(data['findings'][0]['title'])
                        expect(page.locator('#inquiry-applications')).to_contain_text('已采用')
                        expect(page.locator('#inquiry-applications')).to_contain_text('不证明真实开发效率')
                        layout('finding'); record('question to finding, scope, evidence and adopted boundary')
                        if width in (1440, 390):
                            page.screenshot(path=str(output / f'finding-{width}.png'))
                        if not args.offline_render:
                            for label, suffix in [('下载 JSON', 'json'), ('下载 Markdown', 'md')]:
                                with page.expect_download() as download_event:
                                    page.get_by_role('button', name=label, exact=True).click()
                                download = download_event.value
                                destination = output / f'finding-{width}.{suffix}'
                                download.save_as(destination)
                                content = destination.read_text()
                                assert 'retrieval-candidate-competition' in content
                                assert 'Agent Memory Study editors' in content
                                assert '不证明真实开发效率' in content
                                assert 'https://' in content
                                if suffix == 'json':
                                    assert len(json.loads(content)['findings']) == 1
                            page.go_back()
                            expect(page.locator('#inquiry-title')).to_have_text(data['questions'][0]['title'])
                            page.go_forward()
                            expect(page.locator('#inquiry-title')).to_have_text(data['findings'][0]['title'])
                            record('finding Markdown/JSON downloads and real history')
                        for kind, records in [('question', data['questions']), ('finding', data['findings'])]:
                            for item in records:
                                go('?' + kind + '=' + item['id'])
                                expect(page.locator('#inquiry-title')).to_have_text(item['title'])
                                if not args.offline_render:
                                    page.reload(wait_until='domcontentloaded')
                                    expect(page.locator('#inquiry-title')).to_have_text(item['title'])
                                layout(kind + ' direct ' + item['id'])
                        record('all question/finding direct links, reload and layout')
                        if not args.offline_render:
                            # The new findings hang off the second question; check
                            # question -> finding hopping, exact export and real
                            # back/forward for each of them.
                            for item in new_findings:
                                go('?question=experience-becomes-policy')
                                expect(page.locator('#inquiry-practice')).to_contain_text(item['title'])
                                page.locator(
                                    f'#inquiry-practice a[data-route=finding][href*="{item["id"]}"]'
                                ).first.click()
                                expect(page.locator('#inquiry-title')).to_have_text(item['title'])
                                expect(page.locator('#inquiry-use')).to_contain_text(item['action'])
                                expect(page.locator('#inquiry-use')).to_contain_text(item['validation'])
                                expect(page.locator('#inquiry-evidence')).to_contain_text(item['evidence'][0]['observation'])
                                expect(page.locator('#inquiry-evidence')).to_contain_text(item['evidence'][0]['limit'])
                                expect(page.locator('.inquiry-heading')).to_contain_text(item['byline'])
                                expect(page.locator('.inquiry-heading')).to_contain_text(item['updated'])
                                with page.expect_download() as download_event:
                                    page.locator('#inquiry-use').get_by_role('button', name='下载 Markdown').click()
                                destination = output / f'finding-{item["id"]}-{width}.md'
                                download_event.value.save_as(destination)
                                content = destination.read_text()
                                for token in [item['title'], item['byline'], item['updated'], item['limit'],
                                              item['evidence'][0]['observation'], item['evidence'][0]['limit']]:
                                    assert token in content, (item['id'], token)
                                page.reload(wait_until='domcontentloaded')
                                expect(page.locator('#inquiry-title')).to_have_text(item['title'])
                                page.go_back()
                                expect(page.locator('#inquiry-title')).to_have_text(
                                    next(q['title'] for q in data['questions'] if q['id'] == 'experience-becomes-policy'))
                                page.go_forward()
                                expect(page.locator('#inquiry-title')).to_have_text(item['title'])
                            record('question to new finding, exact export and real history')
                        go('#library')
                        page.locator('#search').fill('jevlike')
                        page.locator('#material-index a[data-route=study]').click()
                        expect(page.locator('#study-title')).to_have_text('没有再读那段往事，它为什么还是改变了选择？')
                        expect(page.locator('#decision-summary tbody tr')).to_have_count(4)
                        expect(page.locator('#decision-cases tbody tr')).to_have_count(12)
                        expect(page.locator('.decision-support')).to_contain_text('288/288')
                        page.locator('#study-phase-after').click()
                        expect(page.locator('#decision-summary')).to_contain_text('仅改记录')
                        expect(page.locator('#decision-summary')).to_contain_text('96/276')
                        assert page.evaluate('document.activeElement.id') == 'study-phase-after'
                        page.locator('#study-scenario').select_option('export-ordinary-all-known')
                        expect(page.locator('.study-scenario-description')).to_contain_text('普通')
                        assert page.evaluate('document.activeElement.id') == 'study-scenario'
                        layout('recorded experiment'); record('cross-source search, executed result, phase, case and focus')
                        if not args.offline_render:
                            page.go_back()
                            expect(page.locator('#study-scenario')).to_have_value('export-sensitive-base')
                            page.go_back()
                            expect(page.locator('#study-phase-before')).to_have_attribute('aria-pressed','true')
                            page.go_forward()
                            page.reload(wait_until='domcontentloaded')
                            expect(page.locator('#study-phase-after')).to_have_attribute('aria-pressed','true')
                            with page.expect_download() as download:
                                page.locator('#decision-download').click()
                            saved=json.loads(Path(download.value.path()).read_text())
                            assert saved == json.loads((ROOT/'research/decision-learning-study/results.json').read_text())
                            record('recorded experiment history, reload and exact result JSON export')
                        page.locator('#study-lab').scroll_into_view_if_needed()
                        page.screenshot(path=str(output/f'decision-learning-{width}.png'))
                        go('?study=experience-becomes-policy&scenario=export-ordinary-all-known&phase=after')
                        expect(page.locator('#study-scenario')).to_have_value('export-ordinary-all-known')
                        expect(page.locator('#study-phase-after')).to_have_attribute('aria-pressed','true')
                        go('?question=experience-becomes-policy')
                        expect(page.locator('#inquiry-practice a[data-route=finding]')).to_have_count(2)
                        for item in new_findings:
                            expect(page.locator('#inquiry-practice')).to_contain_text(item['title'])
                        expect(page.locator('#inquiry-practice')).to_contain_text('具体迁移方法仍需在目标系统验证')
                        page.locator('#inquiry-practice a[data-route=study]').filter(has_text='没有再读那段往事').click()
                        expect(page.locator('#decision-summary')).to_be_visible()
                        record('new study direct URL, question link and honest findings state')
                        contract = json.loads((ROOT/'research/jev-memory-contract-study/results.json').read_text())
                        first, last = contract['cases'][0], contract['cases'][-1]
                        go('?study=who-controls-memory&scenario='+last['id']+'&phase=after')
                        expect(page.locator('#study-scenario')).to_have_value(last['id'])
                        expect(page.locator('#contract-state h3')).to_have_text('调用后的快照')
                        expect(page.locator('#contract-comparison')).to_contain_text(
                            f"存储节点 {len(last['before']['stored_ids'])} → {len(last['after']['stored_ids'])}")
                        page.locator('#study-scenario').select_option(first['id'])
                        expect(page.locator('.study-scenario-description')).to_have_text(first['intervention'])
                        assert page.evaluate('document.activeElement.id') == 'study-scenario'
                        page.locator('#study-phase-before').click()
                        expect(page.locator('#contract-state h3')).to_have_text('调用前的快照')
                        assert page.evaluate('document.activeElement.id') == 'study-phase-before'
                        page.locator('#contract-observations summary').click()
                        expect(page.locator('#contract-observations pre')).to_contain_text(first['id'])
                        layout('source contract case and expanded receipt')
                        if not args.offline_render:
                            page.go_back()
                            expect(page.locator('#contract-state h3')).to_have_text('调用后的快照')
                            page.reload(wait_until='domcontentloaded')
                            expect(page.locator('#study-scenario')).to_have_value(first['id'])
                            with page.expect_download() as download:
                                page.locator('#contract-download').click()
                            assert json.loads(Path(download.value.path()).read_text()) == contract
                        page.locator('#study-lab').scroll_into_view_if_needed()
                        page.screenshot(path=str(output/f'jev-contract-{width}.png'))
                        go('?material=jev-mem-system-one-control')
                        page.locator('#material-studies a[data-route=study]').filter(has_text='谁在管理记忆').click()
                        expect(page.locator('#contract-download')).to_be_visible()
                        record('Jev source contract deep link, case, phase, focus, raw receipt, history and exact export')
                        go('?material=continual-learning-experience-reuse')
                        page.locator('#material-inquiries a[data-route=question]').first.click()
                        expect(page.locator('#inquiry-title')).to_have_text(data['questions'][0]['title'])
                        page.locator('.inquiry-materials a[data-route=material]').first.click()
                        expect(page.locator('#material-title')).to_contain_text('When continual learning')
                        record('material/question reciprocal links')
                        go('#practice')
                        problem = '候选增加之后，结果被重复条目占满'
                        page.locator('#practice-query').fill(problem)
                        page.locator('#practice-query').press('Enter')
                        expect(page.locator('#practice-results a[data-route=finding]').first).to_contain_text('旧经验还在')
                        assert '[object Object]' not in page.locator('#practice-results').inner_text()
                        assert parse_qs(urlparse(current_url()).query)['practice'] == [problem]
                        assert page.evaluate('document.activeElement.id') == 'practice-query'
                        layout('practice query'); record('natural problem query, match explanation, focus and URL')
                        if width in (1440, 390):
                            page.screenshot(path=str(output / f'practice-{width}.png'))
                        if not args.offline_render:
                            with page.expect_download() as download_event:
                                page.locator('#practice-export').get_by_role('button', name='下载 JSON').click()
                            destination = output / f'query-{width}.json'
                            download_event.value.save_as(destination)
                            brief = json.loads(destination.read_text())
                            assert brief['query'] == problem
                            assert brief['findings'][0]['id'] == 'retrieval-candidate-competition'
                            page.reload(wait_until='domcontentloaded')
                            expect(page.locator('#practice-query')).to_have_value(problem)
                            expect(page.locator('#practice-results .practice-result')).to_have_count(len(brief['findings']))
                            record('query export matches visible results and reload')
                        page.locator('#practice-query').fill('火星天气 superconductivity')
                        page.locator('#practice-query').press('Enter')
                        expect(page.locator('#practice-results')).to_contain_text('没有找到相关判断')
                        expect(page.locator('#practice-export button')).to_have_count(0)
                        page.locator('#practice-examples button').nth(1).click()
                        expect(page.locator('#practice-results a').first).to_contain_text('新说明出现')
                        page.locator('#practice-examples button').nth(2).click()
                        expect(page.locator('#practice-results a').first).to_contain_text('来源对象消失')
                        record('honest no-match state and working example queries')
                        # Two new practice findings must be reachable through the
                        # practice desk in both languages, from the example chips
                        # and from typed keyword queries, not just full sentences.
                        assert '只整理了这三条' not in page.locator('#practice').inner_text()
                        for idx, item in enumerate(new_findings):
                            page.locator('#practice-examples button').nth(3 + idx).click()
                            expect(page.locator('#practice-results a').first).to_contain_text(item['title'])
                        for query, finding_id in [('纠正 增量 保留范围', 'correction-needs-retention-checks'),
                                                  ('输出约束 参数 遗忘', 'output-guard-is-not-unlearning'),
                                                  ('correction retention', 'correction-needs-retention-checks'),
                                                  ('guard unlearning', 'output-guard-is-not-unlearning')]:
                            page.locator('#practice-query').fill(query)
                            page.locator('#practice-query').press('Enter')
                            # Lexical top-3 contract: the target ranks first and
                            # the visible set never exceeds three findings.
                            target_title = next(item['title'] for item in data['findings']
                                                if item['id'] == finding_id)
                            expect(page.locator('#practice-results a').first).to_contain_text(
                                target_title)
                            result_count = page.locator('#practice-results .practice-result').count()
                            assert 1 <= result_count <= 3, (query, result_count)
                        record('new findings discoverable from examples and keyword queries')
                        for text, kind in [('旧经验，怎样继续帮助当前任务？', 'question'), ('新说明出现，不代表旧范围已经失效', 'finding')]:
                            go('#library')
                            page.locator('#search').fill(text)
                            expect(page.locator('#material-index [data-result-kind=' + kind + ']')).to_have_count(1)
                            page.locator('#material-index a[data-route=' + kind + ']').first.click()
                            expect(page.locator('#inquiry-title')).to_have_text(text)
                        record('global search to new content kinds')
                        for query in ['?material=missing', '?study=after-a-correction&scenario=missing&phase=bad',
                                      '?question=missing', '?finding=missing', '?thread=retrieval-active-context', '?path=from-revision', '#%', '#missing[bracket]']:
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
