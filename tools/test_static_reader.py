#!/usr/bin/env python3
"""Verify every public route, no-JS text, hydration, local links and file reader."""
import argparse
import json
from pathlib import Path
from urllib.parse import urlparse,unquote
from xml.etree import ElementTree as ET
from playwright.sync_api import sync_playwright,expect
from reader_browser_support import ROOT,serve,observe,ready,fits,download,import_file


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--site-root',type=Path,default=ROOT/'dist/site')
    parser.add_argument('--output-dir',type=Path,default=ROOT/'dist/static-reader-check')
    parser.add_argument('--browser-executable')
    args=parser.parse_args();site=args.site_root.resolve();args.output_dir.mkdir(parents=True,exist_ok=True)
    data=json.loads((ROOT/'data/materials.json').read_text());receipt=json.loads((site/'build-receipt.json').read_text())
    rows=[(kind,item) for kind,field in [('material','materials'),('study','studies'),('question','questions'),('finding','findings')] for item in data[field]]
    urls=[n.text for n in ET.parse(site/'sitemap.xml').iter('{http://www.sitemaps.org/schemas/sitemap/0.9}loc')]
    assert len(urls)==len(rows)+1==len(set(urls))==len(receipt['routes'])
    assert all(not urlparse(url).query and not urlparse(url).fragment for url in urls)
    report={'errors':[],'external':[],'routes':[],'portable':[],'missing_links':[]}
    try:
        with serve(site) as base,sync_playwright() as p:
            browser=p.chromium.launch(executable_path=args.browser_executable)
            nojs=browser.new_context(java_script_enabled=False,viewport={'width':1440,'height':1000});static=nojs.new_page();observe(static,base,report)
            live=browser.new_page(viewport={'width':1440,'height':1000});observe(live,base,report)
            static.goto(base);expect(static.locator('h1')).to_have_count(1)
            for kind,item in rows:
                assert static.locator(f'a[href$="/{kind}/{item["id"]}/"]').count(),item['id']
            for kind,item in rows:
                route=f'{kind}/{item["id"]}/';response=static.goto(base+route);assert response.status==200
                expect(static.locator('article h1')).to_have_text(item['title']);initial=static.locator('article').inner_text();semantic=static.locator('article').evaluate("node=>{const copy=node.cloneNode(true);copy.querySelectorAll('[data-interactive],button,input,select,textarea').forEach(n=>n.remove());return copy.textContent.replace(/\\s+/g,' ').trim()}");headings=static.locator('article h2').all_text_contents();assert len(initial)>80
                expect(static.locator('button:visible,input:visible,select:visible,textarea:visible')).to_have_count(0)
                expect(static.get_by_role('link',name='研究包 JSON ↓')).to_be_visible()
                for href in static.locator('a[href],link[href],script[src]').evaluate_all('(nodes)=>nodes.map(n=>n.href||n.src).filter(Boolean)'):
                    if not href.startswith(base):continue
                    target=site/unquote(urlparse(href).path.removeprefix('/agent-memory-study/'))
                    if not target.is_file() and not (target/'index.html').is_file():report['missing_links'].append({'route':route,'href':href})
                live.goto(base+route);ready(live);expect(live.locator('article h1')).to_have_text(item['title'])
                assert live.locator('article h2').all_text_contents()==headings,route
                assert live.locator('article').evaluate("node=>{const copy=node.cloneNode(true);copy.querySelectorAll('[data-interactive],button,input,select,textarea').forEach(n=>n.remove());return copy.textContent.replace(/\\s+/g,' ').trim()}")==semantic,route
                assert live.title()==live.locator('meta[property="og:title"]').get_attribute('content')
                assert live.locator('link[rel=canonical]').get_attribute('href') in urls
                if kind=='material':assert '来源作者' in initial and item['readingScope'] in initial
                if kind=='finding':assert item['claim'] in initial and item['limit'] in initial
                packet=json.loads((site/route/'index.json').read_text());assert packet['schema']=='ams-study-packet/2' and packet['id']==item['id']
                assert (site/route/'index.md').stat().st_size>100
                report['routes'].append(route)
            response=live.goto(base+'does-not-exist/');assert response.status==404;expect(live.locator('h1')).to_contain_text('没有')
            expect(live.locator('meta[name=robots]')).to_have_attribute('content','noindex')
            static.goto((site/'portable/index.html').as_uri());expect(static.locator('.offline-book article')).to_have_count(len(rows))
            expect(static.locator('button:visible,input:visible,select:visible,textarea:visible')).to_have_count(0)
            static.locator('#root a[href="#offline-study-ams-thesis"]').first.click();assert static.url.endswith('#offline-study-ams-thesis')
            for mode,url in [('http',base),('file',(site/'portable/index.html').as_uri())]:
                page=browser.new_page(viewport={'width':390,'height':844});observe(page,base,report);page.goto(url);ready(page)
                page.get_by_role('button',name='＋ 带进来').click();page.get_by_label('遇见了什么？').fill('SYNTHETIC_PRIVATE_CANARY');page.get_by_role('button',name='留在案头 →').click();expect(page.locator('dialog')).to_have_count(0)
                page.get_by_role('link',name='探索 Explore',exact=True).click();page.get_by_role('button',name='再展开 30 项',exact=True).click();page.get_by_role('link',name='找到一样的，还是找到相关的？',exact=True).first.click()
                expect(page.locator('#study-title')).to_be_visible();page.get_by_role('button',name='＋ 留在案头',exact=True).click();page.get_by_role('link',name='打开案头 →').click()
                saved=download(page,lambda:page.get_by_role('button',name='下载私人案头',exact=True).click());pack=json.loads(saved);assert pack['public_records'] and b'SYNTHETIC_PRIVATE_CANARY' in saved
                page.reload();expect(page.locator('.desk-items')).to_have_count(0);import_file(page,saved);expect(page.locator('.desk-items')).to_contain_text('找到一样的')
                page.locator('.public-selection summary').click()
                for format in ('JSON','Markdown'):
                    public=download(page,lambda:page.get_by_role('button',name=f'公开选材 {format} ↓',exact=True).click());assert b'SYNTHETIC_PRIVATE_CANARY' not in public
                fits(page);assert 'SYNTHETIC' not in page.url;assert page.evaluate('localStorage.length')==0
                page.screenshot(path=str(args.output_dir/f'{mode}-desk-390.png'));report['portable'].append({'mode':mode,'fixed_basis_restored':True,'private_canary_filtered':True});page.close()
            browser.close()
        # Scan actual public files, not just the bootstrap used above.
        for file in site.rglob('*'):
            if file.is_file() and file.suffix in ('.json','.js','.html','.md','.xml','.css'):
                assert b'SYNTHETIC_PRIVATE_CANARY' not in file.read_bytes(),file
        assert not report['missing_links'] and not report['errors'] and not report['external'],report
    finally:(args.output_dir/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(f'PASS: {len(rows)} routes, no-JS/hydration parity, links, packets, 404, portable file and public/private separation')

if __name__=='__main__':main()
