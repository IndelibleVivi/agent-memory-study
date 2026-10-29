#!/usr/bin/env python3
"""Real offline casebook UI tests with original synthetic data; no private inputs."""
import argparse
import copy
import json
from pathlib import Path
import sys
import tempfile

from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'research/multilingual-use-policy'))
import casebook
from test_casebook import sample_casebook, MALICIOUS


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--browser-executable')
    parser.add_argument('--output-dir', type=Path)
    args = parser.parse_args()
    checks = []
    errors = []
    network = []
    with tempfile.TemporaryDirectory(prefix='ams-casebook-browser-') as tmp:
        work = Path(tmp)
        out = args.output_dir or work
        out.mkdir(parents=True, exist_ok=True)
        book = sample_casebook()
        book['cases'][0]['memory']['text'] = MALICIOUS
        book['cases'][0]['representations']['summary'] = MALICIOUS
        book['cases'][0]['representations']['coexistence'] = casebook.build_coexistence(
            book['cases'][0]['representations']['episodes'], MALICIOUS)
        # A long ID checks narrow-screen wrapping without using a real identity.
        book['cases'][0]['group_id'] = 'synthetic-long-group-' + '0123456789' * 8
        assert not casebook.validate_casebook(book)
        html = work / 'review.html'
        html.write_text(casebook.render_html(book, casebook.template_reviews(book)))
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=args.browser_executable)
            try:
                for width, height in [(1440, 1000), (390, 844), (320, 740)]:
                    context = browser.new_context(viewport={'width': width, 'height': height}, accept_downloads=True)
                    context.route('http**://**', lambda route: (network.append(route.request.url), route.abort()))
                    page = context.new_page()
                    page.on('pageerror', lambda err: errors.append(str(err)))
                    page.goto(html.as_uri())
                    expect(page.locator('#counts')).to_contain_text('3 unreviewed')
                    assert page.locator('img, b').count() == 0, 'Source HTML must be plain text'
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
                    checks.append(f'{width}: loaded offline, escaped source, no horizontal overflow')

                    # A change downloaded without an explicit save must be a valid draft.
                    page.locator('input[name="label-case-1"][value="useful"]').check()
                    with page.expect_download() as download:
                        page.locator('#download').click()
                    first = json.loads(Path(download.value.path()).read_text())
                    assert not casebook.validate_reviews(first, book)
                    r = next(r for r in first['reviews'] if r['case_id'] == 'case-1')
                    assert r['status'] == 'draft' and r['reviewed_at'] is None
                    checks.append(f'{width}: direct edit/download is valid draft')

                    page.locator('input[name="cs-case-1"][value="true"]').check()
                    page.locator('#detail input[type=text]').fill('Synthetic reviewer')
                    page.locator('#detail textarea').fill('Original fixture: context and memory inspected.')
                    page.get_by_role('button', name='确认', exact=True).click()
                    expect(page.locator('[data-review-status]')).to_have_text('confirmed')
                    page.locator('#detail textarea').fill('Changed judgement; reconfirmation required.')
                    expect(page.locator('[data-review-status]')).to_have_text('draft')
                    expect(page.locator('.status-line')).to_contain_text('reviewed_at=null')
                    page.get_by_role('button', name='确认', exact=True).click()
                    with page.expect_download() as download:
                        page.locator('#download').click()
                    reviewed = json.loads(Path(download.value.path()).read_text())
                    assert not casebook.validate_reviews(reviewed, book)
                    checks.append(f'{width}: confirmation invalidated by edits and explicitly restored')

                    page.locator('#ctx').select_option('missing')
                    expect(page.locator('#detail h2')).to_have_text('case case-2')
                    page.locator('input[name="label-case-2"][value="useful"]').check()
                    page.locator('input[name="cs-case-2"][value="true"]').check()
                    page.locator('#detail input[type=text]').fill('Synthetic reviewer')
                    page.locator('#detail textarea').fill('Must reject missing context.')
                    page.get_by_role('button', name='确认', exact=True).click()
                    expect(page.locator('.form-msg')).to_contain_text('无法确认')
                    page.locator('input[name="label-case-2"][value="insufficient-context"]').check()
                    page.locator('input[name="cs-case-2"][value="false"]').check()
                    page.get_by_role('button', name='确认', exact=True).click()
                    expect(page.locator('[data-review-status]')).to_have_text('confirmed')
                    page.locator('#q').fill('nonexistent-case')
                    expect(page.locator('#detail')).to_have_text('没有可显示的 case。')
                    page.locator('#q').fill('')
                    page.locator('#ctx').select_option('all')
                    page.locator('#case-list button').last.focus()
                    page.keyboard.press('Enter')
                    expect(page.locator('#detail h2')).to_have_text('case case-3')
                    expect(page.locator('#detail h3').filter(has_text='构造情境')).to_have_count(1)
                    checks.append(f'{width}: filters follow selection, missing context rejected, keyboard and constructed context work')
                    page.screenshot(path=str(out / f'casebook-{width}.png'), full_page=True)

                    # Downloaded confirmations survive CLI-style render/reload.
                    reloaded = work / f'reloaded-{width}.html'
                    reloaded.write_text(casebook.render_html(book, reviewed))
                    page.goto(reloaded.as_uri())
                    expect(page.locator('[data-review-status]')).to_have_text('confirmed')
                    expect(page.locator('#detail textarea')).to_have_value('Changed judgement; reconfirmation required.')
                    checks.append(f'{width}: reviewed sidecar reload preserved')

                    # Same IDs with changed material may not silently reuse a confirmation.
                    changed = copy.deepcopy(book)
                    changed['cases'][0]['context']['text'] = 'Changed synthetic task; inspect again.'
                    assert casebook.validate_reviews(reviewed, changed)
                    rebound = casebook.rebind_reviews(reviewed, changed)
                    assert rebound['reviews'][0]['history'][0]['review']['status'] == 'confirmed'
                    stale_html = work / f'stale-{width}.html'
                    stale_html.write_text(casebook.render_html(changed, rebound))
                    page.goto(stale_html.as_uri())
                    expect(page.locator('[data-review-status]')).to_have_text('stale')
                    expect(page.locator('#detail')).to_contain_text('content-and/or-rubric-changed')
                    with page.expect_download() as download:
                        page.locator('#download').click()
                    stale_download = json.loads(Path(download.value.path()).read_text())
                    assert not casebook.validate_reviews(stale_download, changed)
                    assert stale_download['reviews'][0]['status'] == 'stale'
                    assert stale_download['reviews'][0]['history'] == rebound['reviews'][0]['history']
                    page.locator('#detail textarea').fill('Reinspected changed task and current rubric.')
                    expect(page.locator('#detail')).to_contain_text('需要重新审阅：')
                    expect(page.locator('[data-review-status]')).to_have_text('draft')
                    page.get_by_role('button', name='确认', exact=True).click()
                    expect(page.locator('[data-review-status]')).to_have_text('confirmed')
                    with page.expect_download() as download:
                        page.locator('#download').click()
                    reconfirmed = json.loads(Path(download.value.path()).read_text())
                    assert not casebook.validate_reviews(reconfirmed, changed)
                    r = reconfirmed['reviews'][0]
                    expect(page.locator('#detail')).not_to_contain_text('需要重新审阅：')
                    assert r['stale_reason'] is None and r['history'] == rebound['reviews'][0]['history']
                    assert r['case_payload_digest'] == casebook.case_payload_digest(changed['cases'][0])
                    assert r['rubric_version'] == casebook.RUBRIC_VERSION
                    reconfirm_html = work / f'reconfirmed-{width}.html'
                    reconfirm_html.write_text(casebook.render_html(changed, reconfirmed))
                    page.goto(reconfirm_html.as_uri())
                    expect(page.locator('[data-review-status]')).to_have_text('confirmed')
                    checks.append(f'{width}: stale history/download, active reconfirmation and reload preserve binding')

                    context.close()
            finally:
                browser.close()
        assert not errors, errors
        assert not network, network
        report = {'status': 'passed', 'checks': checks, 'page_errors': errors, 'network_requests': network,
                  'scope': 'Original synthetic fixtures; real file:// UI and downloads, not private case review or model evaluation.'}
        (out / 'casebook-browser.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
        print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()
