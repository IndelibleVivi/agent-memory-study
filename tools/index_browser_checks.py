"""Actual index interaction; Python bisect independently checks displayed results."""
from bisect import bisect_left
import json
from urllib.parse import parse_qs,urlparse
from playwright.sync_api import expect
from reader_browser_support import download,import_file,fits


def check_index_exercise(page,url,record):
    page.goto(url);expect(page.locator('#index-summary')).to_be_visible()
    def select(field,value):
        page.locator('#index-'+field).focus();page.locator('#index-'+field).select_option(value);expect(page.locator('#index-'+field)).to_have_value(value)
        expect(page.locator('#index-'+field)).to_be_focused()
    def query(value):
        page.locator('#index-query').fill(str(value));page.locator('#index-query').press('Enter')
        page.wait_for_function('value=>new URL(location.href).searchParams.get("query")===String(value)',arg=value)
        expect(page.locator('#index-query')).to_have_value(str(value))
        expect(page.locator('#index-query')).to_be_focused()
    def result(position=None,fallback=None):
        expect(page.locator("#index-summary")).to_be_visible()
        keys=[int(v) for v in page.locator('.index-records li strong').all_text_contents()]
        q=int(page.locator('#index-query').input_value());expected=bisect_left(keys,q)
        assert keys and keys==sorted(set(keys))
        if position is not None:assert expected==position
        expect(page.locator('#index-summary .index-metrics dd').nth(2)).to_have_text(str(expected))
        if fallback is not None:expect(page.locator('#index-summary')).to_have_attribute('data-fallback',str(fallback).lower())
        return keys
    select('dataset','uniform');query(70);assert len(result(6,False))==8
    path=page.locator('.index-prediction');assert path.get_attribute('clip-path')=='url(#index-plot-clip)'
    ys=[float(pair.split(',')[1]) for pair in path.get_attribute('d').split('L')[-3:]];assert ys[0]>ys[1]>ys[2] and ys[2]<0
    expect(page.locator('#index-repair')).to_be_disabled();select('mutation','insert');assert len(result(10,True))==12
    expect(page.locator('.index-guard')).to_contain_text('条件不成立');old=page.locator('.index-formula').inner_text()
    select('repair','rebound');result(10,False);assert page.locator('.index-formula').inner_text()==old
    select('repair','retrain');result(10,False);assert page.locator('.index-formula').inner_text()!=old
    for q,pos in [(65,10),(130,12),(0,0)]:query(q);result(pos)
    page.go_back();expect(page.locator('#index-query')).to_have_value('130');result(12);page.reload();result(12)
    datasets={}
    for value in page.locator('#index-dataset option').evaluate_all('nodes=>nodes.map(n=>n.value)'):
        select('dataset',value);datasets[value]=tuple(result());expect(page.locator('#index-mutation')).to_have_value('base')
    assert len(datasets)==len(set(datasets.values()))==3
    select('dataset','uniform');select('mutation','insert');query(70);result(10,True)
    page.get_by_role('button',name='＋ 留在案头',exact=True).click();page.get_by_role('link',name='打开案头 →').click()
    expect(page.locator('.desk-items')).to_contain_text('索引也能学习')
    page.get_by_label('这一刻，想弄明白什么？').fill('SYNTHETIC_INDEX_PRIVATE')
    page.get_by_label('旁注',exact=True).fill('<script>window.INDEX_PRIVATE_BAD=true</script>')
    saved=download(page,lambda:page.get_by_role('button',name='下载私人案头',exact=True).click());value=json.loads(saved)
    session=next(r for r in value['records'] if r['kind']=='session');item=session['payload']['items'][0]
    assert item['exercise']=={'dataset':'uniform','mutation':'insert','repair':'stale','query':70},item
    page.reload();import_file(page,saved);page.locator('.desk-items h3 a').click();result(10,True)
    for key,value in item['exercise'].items():assert parse_qs(urlparse(page.url).query).get(key)==[str(value)]
    assert 'PRIVATE' not in page.url and page.evaluate('window.INDEX_PRIVATE_BAD') is None
    page.locator('.index-audit summary').click();expect(page.locator('.index-audit tbody tr')).to_have_count(12);fits(page)
    record('independent lower_bound, fallback/recalibration/refit, boundaries, 3 datasets, focus/history, persisted exercise and inert private text')
