#!/usr/bin/env python3
"""Public reader interaction, visual breakpoints, legacy routes and state recovery."""
import argparse
import json
import platform
import re
import subprocess
import time
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
from reader_browser_support import ROOT,serve,observe,ready,fits,download,import_file
from index_browser_checks import check_index_exercise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--site-root',type=Path,default=ROOT/'dist/site')
    parser.add_argument('--output-dir',type=Path,default=ROOT/'dist/browser-check')
    parser.add_argument('--browser-executable')
    args=parser.parse_args();args.output_dir.mkdir(parents=True,exist_ok=True);site=args.site_root.resolve()
    if not site.exists():subprocess.run(['node','apps/reader/build.mjs','--base','/agent-memory-study/','--output',str(site)],cwd=ROOT,check=True)
    data=json.loads((ROOT/'data/materials.json').read_text());report={'errors':[],'external':[],'checks':[],'scale':{}}
    try:
        with serve(site) as base,sync_playwright() as p:
            browser=p.chromium.launch(executable_path=args.browser_executable)
            for width in (1440,1024,768,390,320):
                page=browser.new_page(viewport={'width':width,'height':1000},reduced_motion='reduce');observe(page,base,report)
                page.goto(base);ready(page);expect(page.get_by_role('navigation',name='四个研究空间')).to_be_visible();fits(page)
                assert page.locator('.catalogue-rows>li').count()==30
                page.screenshot(path=str(args.output_dir/f'explore-{width}.png'),full_page=True)
                page.get_by_role('button',name='星图',exact=True).click();expect(page.locator('#constellation-plot svg')).to_be_visible()
                nodes=page.locator('[data-map-node]');assert 1<=nodes.count()<=160
                expect(page.locator('.research-view')).to_have_attribute('data-motion','still')
                page.locator('#constellation').scroll_into_view_if_needed();fits(page);page.screenshot(path=str(args.output_dir/f'map-{width}.png'))
                page.get_by_role('button',name='完整星图',exact=True).click();expect(nodes).to_have_count(sum(len(data[k]) for k in ('materials','studies','questions','findings')))
                page.get_by_role('button',name='筛选',exact=True).click();page.locator('#map-query').fill('NO_SYNTHETIC_MATCH');expect(page.locator('#map-empty')).to_be_visible()
                page.locator('#map-query').fill('');page.get_by_role('button',name='列表',exact=True).click();expect(page.locator('#constellation-list')).to_be_visible()
                page.get_by_role('button',name='图',exact=True).click();svg=page.locator('#constellation-plot svg');svg.focus();page.keyboard.press('ArrowRight');page.keyboard.press('Enter');expect(page.locator('#constellation-reading')).to_be_visible()
                page.get_by_role('button',name='研究体',exact=True).click();expect(page.locator('#continuity-sculpture')).to_be_visible()
                sculpture=page.locator('#continuity-sculpture');sculpture.focus();page.keyboard.press('ArrowRight');page.keyboard.press('Enter');expect(page.locator('#sculpture-open')).to_have_attribute('href',re.compile('/(?:study|material|question|finding)/'))
                # Loss of the actual graphics context preserves ordinary reader links.
                page.locator("#continuity-sculpture canvas").evaluate("canvas=>canvas.dispatchEvent(new Event('webglcontextlost',{cancelable:true}))")
                expect(sculpture).to_have_attribute("data-renderer","fallback");expect(page.locator("#sculpture-open")).to_be_visible()
                # Repeated mount/unmount must not reveal the private desk or retain global listeners.
                page.get_by_role('button',name='文章',exact=True).click();expect(sculpture).to_have_count(0);expect(page.locator('.desk-main')).to_have_count(0)
                page.goto(base+'study/what-an-index-learns/');ready(page);expect(page.locator('#study-title')).to_be_visible();fits(page)
                assert page.locator('.study-essay').bounding_box()['y']<900
                page.screenshot(path=str(args.output_dir/f'reader-{width}.png'))
                report['checks'].append({'width':width,'layout_map_list_filters_keyboard_remount_reader':True});page.close()
            page=browser.new_page(viewport={'width':390,'height':844},reduced_motion='reduce');observe(page,base,report)
            check_index_exercise(page,base+'?study=what-an-index-learns',lambda note:report['checks'].append(note))
            page.goto(base+'?study=after-a-correction&scenario=corrected&phase=after');ready(page);expect(page.locator('#study-phase-after')).to_have_attribute('aria-pressed','true');expect(page.locator('.study-output')).to_have_count(len(next(s for s in data['studies'] if s['id']=='after-a-correction')['policies']))
            page.locator('#study-phase-before').click();page.go_back();expect(page.locator('#study-phase-after')).to_have_attribute('aria-pressed','true')
            for id in ('experience-becomes-policy','who-controls-memory'):
                page.goto(base+'study/'+id+'/?phase=after');ready(page);expect(page.locator('#study-phase-after')).to_have_attribute('aria-pressed','true')
                page.locator('#study-scenario').focus();page.locator('#study-scenario').select_option(index=1);expect(page.locator('#study-scenario')).to_be_focused()
                receipt=json.loads(download(page,lambda:page.get_by_role('button',name='下载实验结果 JSON').click()))
                original=next(row for row in data['studies'] if row['id']==id)
                assert receipt==json.loads((ROOT/original['resultsUrl']).read_text())
                page.reload();expect(page.locator('#study-phase-after')).to_have_attribute('aria-pressed','true');fits(page)
            page.goto(base+'?study=representation-and-use');ready(page);expect(page.locator('#study-lab')).to_contain_text('尚未执行');expect(page.locator('#study-lab select,#study-lab button')).to_have_count(0)
            page.goto(base+'?path='+data['atlas']['readingPaths'][0]['id']);ready(page)
            expect(page.locator('.catalogue-rows>li')).to_have_count(len(data['atlas']['readingPaths'][0]['materialIds']))
            for key,collection in [('domain','domains'),('direction','directions')]:
                page.goto(base+'?'+key+'='+data['room'][collection][0]['id']);ready(page);assert page.locator('.catalogue-rows>li').count()>0
            page.goto(base);ready(page);search=page.get_by_label('搜索正文、作者与问题',exact=True);search.fill('memory');search.press('Enter');page.wait_for_function('new URL(location.href).searchParams.get("q")==="memory"');expect(page.locator('.filter-row [role=status]')).not_to_contain_text('正在');assert page.locator('.catalogue-rows>li').count()>0
            search.fill('<img src=x onerror=window.SEARCH_BAD=true>');search.press('Enter');expect(page.locator('.catalogue-rows>li')).to_have_count(0);assert page.evaluate('window.SEARCH_BAD') is None
            page.goto(base+'?space=library&practice=scope');ready(page);expect(page.locator('.practice-view>section').first).to_be_visible();assert 1<=page.locator('.practice-view>section').count()<=3
            brief=json.loads(download(page,lambda:page.get_by_role('button',name='Brief JSON ↓').click()));assert brief
            page.goto(base+'study/retrieval-and-relevance/');ready(page)
            para=page.locator('.study-essay p').first;quote=para.inner_text();para.evaluate('node=>{const range=document.createRange();range.selectNodeContents(node);const selection=getSelection();selection.removeAllRanges();selection.addRange(range);node.dispatchEvent(new KeyboardEvent("keyup",{bubbles:true,key:"Shift"}))}')
            page.get_by_role('button',name='摘到案头',exact=True).click();page.get_by_role('link',name='打开案头 →').click();expect(page.locator('.excerpt-card').first).to_contain_text(quote)
            page.get_by_label('这段摘录的批注').fill('SYNTHETIC_QUOTE_COMMENT');page.get_by_label('这段摘录的用途').select_option('contrast')
            page.get_by_label('下次从哪里继续',exact=True).fill('回到有限观察的反例');page.get_by_label('下次从哪里继续',exact=True).blur()
            page.get_by_role('button',name='撤销',exact=True).click();expect(page.get_by_label('下次从哪里继续',exact=True)).to_have_value('')
            page.get_by_role('button',name='重做',exact=True).click();expect(page.get_by_label('下次从哪里继续',exact=True)).to_have_value('回到有限观察的反例')
            saved=download(page,lambda:page.get_by_role('button',name='下载私人案头',exact=True).click());page.reload();import_file(page,saved);expect(page.get_by_label('这段摘录的批注')).to_have_value('SYNTHETIC_QUOTE_COMMENT')
            page.locator('.public-selection summary').click();public=download(page,lambda:page.get_by_role('button',name='公开选材 JSON ↓').click());assert b'SYNTHETIC_QUOTE_COMMENT' not in public
            # Bad import cannot change the current desk.
            before=page.locator('.desk-main').inner_text();page.locator('.thread-list input[type=file]').set_input_files({'name':'bad.json','mimeType':'application/json','buffer':b'{"schema":"bad"}'})
            expect(page.locator('.notice')).to_contain_text('支持');assert page.locator('.desk-main').inner_text()==before
            page.goto(base+'study/ams-thesis/');ready(page);page.evaluate('document.documentElement.style.fontSize="200%"');fits(page);page.screenshot(path=str(args.output_dir/'reader-390-font200.png'))
            report['checks'].append('legacy routes, filters/search safety, real saved receipts, excerpt/comment/history/import, private canary, 200% text')
            page.close()
            # Synthetic 10k metadata only: no body bundle or fabricated research result.
            large=browser.new_page(viewport={'width':1440,'height':1000},reduced_motion='reduce');observe(large,base,report)
            # Render the expanded fixture through the same server tree first:
            # mutating only bootstrap would deliberately corrupt hydration.
            script=r"""import fs from 'node:fs'; import path from 'node:path'; import {pathToFileURL} from 'node:url';
              const html=fs.readFileSync(path.join(process.argv[1],'index.html'),'utf8');
              const boot=JSON.parse(html.match(/window\.__AMS_BOOTSTRAP__=(.*?);<\/script>/s)[1]);
              const first=boot.graph.nodes.find(n=>n.key==='study/ams-thesis'),meta=boot.catalogue.find(n=>n.id==='ams-thesis');
              boot.catalogue=Array.from({length:10000},(_,i)=>({...meta,id:i?'synthetic-'+i:meta.id,title:i?'Synthetic metadata '+i:meta.title}));
              boot.graph.nodes=boot.catalogue.map(m=>({...first,id:m.id,key:'study/'+m.id,title:m.title}));
              boot.graph.edges=Array.from({length:9999},(_,i)=>[0,i+1]);boot.graph.references=[];
              const {render}=await import(pathToFileURL(path.resolve('apps/reader/.build/server.mjs')));
              const start=html.indexOf('<div id="root">'),end=html.indexOf('</div><script>window.__AMS_BOOTSTRAP__=')+6;
              const result=html.slice(0,start)+'<div id="root">'+render(boot)+'</div>'+html.slice(end);
              process.stdout.write(result.replace(/window\.__AMS_BOOTSTRAP__=(.*?)<\/script>/s,()=> 'window.__AMS_BOOTSTRAP__='+JSON.stringify(boot).replaceAll('<','\\u003c')+'</script>'));
            """
            expanded=subprocess.run(['node','--input-type=module','-e',script,str(site)],cwd=ROOT,text=True,stdout=subprocess.PIPE,check=True).stdout
            large.route(base,lambda route:route.fulfill(status=200,content_type='text/html; charset=utf-8',body=expanded))
            requests=[];large.on('request',lambda request:requests.append(request.url))
            started=time.perf_counter();large.goto(base);ready(large)
            expect(large.locator('.filter-row [role=status]')).to_have_text('10000 个公开对象')
            expect(large.locator('.catalogue-rows>li')).to_have_count(30);initial_ms=round((time.perf_counter()-started)*1000)
            large.get_by_role('button',name='再展开 30 项',exact=True).click();expect(large.locator('.catalogue-rows>li')).to_have_count(60)
            started=time.perf_counter();large.get_by_role('button',name='星图',exact=True).click();expect(large.locator('[data-map-node]')).to_have_count(160)
            graph_ms=round((time.perf_counter()-started)*1000);fits(large)
            assert not any('/reader-data/study/' in url or '/data/corpus/revisions/' in url for url in requests),requests
            large.get_by_label('选择局部引用范围').select_option('study/synthetic-9999');expect(large.locator('[data-map-node]')).to_have_count(2)
            report['scale']={'metadata':10000,'initial_visible_rows':30,'expanded_rows':60,'max_graph_nodes':160,'initial_ms':initial_ms,'graph_ms':graph_ms,'host':platform.platform(),'cpu':platform.machine(),'body_or_receipt_eager_requests':0}
            large.screenshot(path=str(args.output_dir/'map-synthetic-10000.png'));large.close()
            # Inspect actual platform fonts: Chinese text must be provided by the
            # bundled faces, without requiring an installed system CJK family.
            fonts=browser.new_page();observe(fonts,base,report);fonts.goto(base+'study/ams-thesis/');ready(fonts);fonts.evaluate('document.fonts.ready')
            cdp=fonts.context.new_cdp_session(fonts);cdp.send('DOM.enable');cdp.send('CSS.enable')
            document=cdp.send('DOM.getDocument');node=cdp.send('DOM.querySelector',{'nodeId':document['root']['nodeId'],'selector':'article h1'})
            used=cdp.send('CSS.getPlatformFontsForNode',{'nodeId':node['nodeId']})['fonts']
            assert used and all(font['isCustomFont'] for font in used),used
            report['fonts']=used;fonts.close();browser.close()
        assert not report['errors'] and not report['external'],report
    finally:(args.output_dir/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print('PASS: public interactions, legacy state, receipt identity, 5 viewports, map/sculpture, and private recovery')

if __name__=='__main__':main()
