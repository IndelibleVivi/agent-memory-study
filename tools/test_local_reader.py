#!/usr/bin/env python3
"""Finite full-App local acceptance with original synthetic material, no providers.

Starts the real CLI subprocess, keeps the runtime outside the source checkout,
and retains a machine-readable receipt and screenshots under --output-dir.
"""
from __future__ import annotations
import argparse
import base64
import json
import os
from pathlib import Path
import queue
import re
import signal
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright, expect
from reader_browser_support import ROOT, ready, fits, download, import_file, observe
sys.path.insert(0,str(ROOT))
from services.local.records import record,command,ref,revise

CANARY='AMS_PRIVATE_SYNTHETIC_CANARY_7f2d'
QUESTION='陌生问题：future questions、multilingual 与 representation，保留相同观察后还能回答 XOR 吗？'
QUOTE='A partial reading is not a complete observation of every future question.'

class LocalProcess:
    def __init__(self,site,data,output):self.site,self.data,self.output=site,data,output;self.process=None;self.starts=0
    def start(self):
        self.starts+=1;self.log=(self.output/f'service-{self.starts}.log').open('w')
        self.process=subprocess.Popen([sys.executable,'-B','-m','services.local','--project',str(ROOT),'--data-root',str(self.data),'serve','--port','0','--site-root',str(self.site)],cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,bufsize=1)
        lines=queue.Queue()
        def read():
            for line in self.process.stdout:self.log.write(line);self.log.flush();lines.put(line)
        self.reader=threading.Thread(target=read,daemon=True);self.reader.start();end=time.monotonic()+30
        while time.monotonic()<end:
            try:line=lines.get(timeout=.2)
            except queue.Empty:
                if self.process.poll() is not None:raise AssertionError('local CLI startup failed; see service log')
                continue
            if line.startswith('AMS local: '):self.url=line.split('AMS local: ',1)[1].strip();return self.url
        raise AssertionError('local CLI did not print its startup address')
    def stop(self,abrupt=False):
        if self.process and self.process.poll() is None:
            self.process.kill() if abrupt else self.process.send_signal(signal.SIGINT)
            self.process.wait(timeout=20)
        if hasattr(self,'reader'):self.reader.join(timeout=3)
        if hasattr(self,'log'):self.log.close()


def original_pdf():
    # A real two-page PDF with xref and selectable original text, no dependency
    # on installed generators or external papers.
    pages=[QUOTE,'Page two: fixed scope. This original acceptance fixture is not a published paper.']
    objects=[b'<< /Type /Catalog /Pages 2 0 R >>',b'<< /Type /Pages /Kids [3 0 R 5 0 R] /Count 2 >>']
    for index,text in enumerate(pages):
        stream=('BT /F1 11 Tf 42 720 Td ('+text+') Tj ET').encode()
        objects.extend([f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 7 0 R >> >> /Contents {4+2*index} 0 R >>'.encode(),b'<< /Length '+str(len(stream)).encode()+b' >>\nstream\n'+stream+b'\nendstream'])
    objects.append(b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>');raw=b'%PDF-1.4\n';offsets=[0]
    for n,obj in enumerate(objects,1):offsets.append(len(raw));raw+=f'{n} 0 obj\n'.encode()+obj+b'\nendobj\n'
    xref=len(raw);raw+=f'xref\n0 {len(objects)+1}\n0000000000 65535 f \n'.encode()+b''.join(f'{x:010} 00000 n \n'.encode() for x in offsets[1:]);return raw+f'trailer\n<< /Size {len(objects)+1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n'.encode()


def api(page,path,body=None,expected=200):
    response=page.evaluate('''async([path,body])=>{const config=JSON.parse(document.getElementById('ams-local-bootstrap').textContent);const r=await fetch('/api'+path,{method:body===null?'GET':'POST',headers:{Authorization:'Bearer '+config.token,'Content-Type':'application/json'},...(body===null?{}:{body:JSON.stringify(body)})});return {status:r.status,data:await r.json()};}''',[path,body])
    assert response['status']==expected,(path,response)
    return response['data']


def rows(page,kind):return api(page,'/entities?kind='+kind)['records']
def save_records(page,*values):api(page,'/units',{'commands':[command(value) for value in values]});return values

def navigate(page,url,suffix='?space=continue'):
    page.goto(url+suffix);ready(page);expect(page.locator('.ams-app')).to_have_attribute('data-mode','local')

def saved(page):expect(page.locator('[data-save-state]')).to_have_attribute('data-save-state','committed',timeout=15000)
def fixed_key(pointer):return '/'.join(pointer[k] for k in ('kind','id','revision'))

def select_review(page,pointer):page.get_by_label('本次复核对象',exact=True).select_option(fixed_key(pointer))
def propose_apply(page,reason,body=None):
    page.get_by_label('这一次决定',exact=True).select_option('rewrite' if body else 'maintain')
    if body:page.get_by_label('拟改正文',exact=True).fill(body)
    page.get_by_label('修订依据与理由',exact=True).fill(reason);page.get_by_role('button',name='保存修订提议',exact=True).click();page.get_by_role('button',name='接受此项',exact=True).click();page.get_by_role('button',name='原子应用已接受项',exact=True).click()
    expect(page.locator('.review-changeset')).to_contain_text(re.compile('检查后保持不变|已应用'))


def lab_registry_checks(page,url,report):
    pending=[]
    def hold_registry(route):pending.append(route)
    page.route('**/api/studies',hold_registry)
    navigate(page,url,'?space=lab')
    choice=page.get_by_label('选择一项研究',exact=True)
    choice.select_option('c2c-cache-retraction-study')
    choice.select_option('observation-contract-study')
    expect(page.locator('.lab-plan')).to_contain_text('Registry 尚未连接')
    assert len(pending)==1
    pending[0].fulfill(response=pending[0].fetch())
    page.unroute('**/api/studies',hold_registry)
    operation=page.get_by_label('操作',exact=True)
    expect(operation).to_have_value('run')
    expect(page.get_by_label('声明模型',exact=True)).to_be_visible()
    operation.select_option('prepare')
    expect(operation).to_have_value('prepare')
    choice.select_option('c2c-cache-retraction-study')
    expect(operation).to_have_value('inspect')
    expect(operation.locator('option[value="run"]')).to_have_count(0)
    expect(page.get_by_label('声明模型',exact=True)).to_have_count(0)
    assert api(page,'/jobs')['jobs']==[]
    report['checks'].append('Study selection before delayed registry resolves to an advertised operation; explicit prepare works, history-only study stays inspect, and selection never submits a job')


def story_one(page,url,output,report):
    navigate(page,url);page.get_by_role('button',name='＋ 带进来',exact=True).click();dialog=page.locator('.capture-dialog')
    dialog.get_by_label('遇见了什么？',exact=True).fill(QUESTION);dialog.get_by_label('为什么现在留它？',exact=True).fill(CANARY+' 原创合成来件，不是注册论文。')
    raw=original_pdf();(output/'original-two-page.pdf').write_bytes(raw);dialog.get_by_role('button',name='留在案头 →',exact=True).click();expect(dialog).to_have_count(0)
    card=page.locator('.capture-card').filter(has_text=QUESTION);card.get_by_role('button',name='继续认清 ↗',exact=True).click();card.locator('summary').filter(has_text='辨认作品与版本').click();card.get_by_role('button',name='查明确的标识与候选',exact=True).click();card.get_by_label('这份作品叫什么？',exact=True).fill('Original finite-observation acceptance fixture');card.get_by_label('身份处理').select_option('new');card.get_by_role('button',name='确认这次身份判断',exact=True).click();expect(card).to_contain_text('已明确绑定')
    card.locator('summary').filter(has_text='原件与实际阅读').click();card.get_by_label('为这次遇见选择本机原件',exact=True).set_input_files({'name':'original-two-page.pdf','mimeType':'application/pdf','buffer':raw});card.get_by_role('button',name='确认取得这个选定文件',exact=True).click();material=card.locator('.acquired-material');expect(material).to_contain_text('原件已保存');material.get_by_label('文字提取').select_option('pdf-pypdf');material.get_by_label('取得范围').select_option('partial');material.get_by_role('button',name='提取文字并检查',exact=True).click();expect(material.locator('.acquired-text')).to_contain_text(QUOTE);expect(material.locator('.acquired-text')).to_contain_text('Page two')
    material.get_by_label('明确读到的片段',exact=True).fill(QUOTE);material.get_by_role('button',name='记录这次阅读范围',exact=True).click();expect(material.get_by_label('明确读到的片段',exact=True)).to_have_value('');material.get_by_role('button',name='留到案头，继续对读',exact=True).click();saved(page)
    card.locator('summary').filter(has_text='这次遇见，可能连向哪里').click();card.get_by_role('button',name='找公开材料中的线索',exact=True).click();expect(card).to_contain_text('不代表支持')
    for article in ('future-questions-and-memory','experience-becomes-policy','representation-and-use'):
        navigate(page,url,'study/'+article+'/');expect(page.locator('#study-title')).to_be_visible();page.get_by_role('button',name='＋ 留在案头',exact=True).click();expect(page.locator('.notice')).to_contain_text('已加入当前案头')
    paragraph=page.locator('.study-essay p').first;quote=paragraph.inner_text();paragraph.evaluate("node=>{const range=document.createRange();range.selectNodeContents(node);const s=getSelection();s.removeAllRanges();s.addRange(range);node.dispatchEvent(new KeyboardEvent('keyup',{bubbles:true,key:'Shift'}));}")
    page.get_by_role('button',name='摘到案头',exact=True).click();page.get_by_role('link',name='打开案头 →',exact=True).click();expect(page.locator('.excerpt-card')).to_contain_text(quote);page.get_by_label('这段摘录的批注',exact=True).fill(CANARY+' 公开片段的私人批注');page.get_by_label('旁注',exact=True).first.fill('只记录实际部分阅读，候选相似不构成支持。')
    page.get_by_label('这一刻，想弄明白什么？',exact=True).fill(QUESTION);page.get_by_label('两处之间，我看见了什么？',exact=True).fill('PR7讨论未来问题契约，多语言/表征对读不自动推出相同机制。')
    compare=page.locator('.comparison-selectors select');compare.nth(0).select_option('study:future-questions-and-memory');compare.nth(1).select_option('study:representation-and-use');expect(page.locator('.compare-pane')).to_have_count(2)
    page.get_by_label('下次从哪里继续',exact=True).fill('在声明有限模型内检查 XOR 观察碰撞，勿推广为模型收益。');page.get_by_label('下次从哪里继续',exact=True).blur();saved(page)
    pack=json.loads(download(page,lambda:page.get_by_role('button',name='下载私人案头',exact=True).click()));(output/'story-one-private.json').write_text(json.dumps(pack,ensure_ascii=False,indent=2));assert CANARY in json.dumps(pack,ensure_ascii=False)
    session=next(r for r in rows(page,'session') if r['payload'].get('question')==QUESTION);reads=rows(page,'read_activity');assert len(reads)==1 and reads[0]['extent']==[QUOTE];extraction=rows(page,'extraction')[0];assert extraction['coverage']=='partial'
    story={'session_ref':ref(session),'read_ref':ref(reads[0]),'extraction_ref':ref(extraction),'excerpt_refs':[ref(r) for r in rows(page,'excerpt')],'quote':quote,'item_refs':[r['target_ref'] for r in session['payload']['items']]};report['stories']['capture_to_reading']=story
    navigate(page,url,'?space=lab');page.get_by_label('选择一项研究',exact=True).select_option('observation-contract-study');page.get_by_label('声明模型',exact=True).select_option('future-access');page.get_by_label('状态 A',exact=True).select_option('w00');page.get_by_label('状态 B',exact=True).select_option('w01');page.get_by_role('button',name='开始本地计算',exact=True).click();expect(page.locator('.lab-job')).to_contain_text('本次操作完成',timeout=20000);expect(page.locator('.lab-signature')).to_contain_text('找到区分序列');job=api(page,'/job?id='+api(page,'/jobs')['jobs'][0]['id']);story['native_job_id']=job['id'];story['native_evidence']=api(page,'/job/evidence?id='+job['id'])
    navigate(page,url);saved(page);page.screenshot(path=str(output/'story-one.png'),full_page=True)
    report['checks'].append('Story 1: original real PDF, partial read vs acquired bytes, public PR7/multilingual/representation comparison, fixed quote/note, real finite P8 native job')


def scope_fixtures(page):
    old=record('claim_revision',{'title':'Original finite source scope','byline':'AMS synthetic','claim':'Only the original fixed task is covered.','scope':'fixed-task','scope_binding':'fixed-task','payload':{}})
    new=revise(old,claim='A new target task has different supervision.',scope='new-task',scope_binding='new-task')
    a,b,c=[record('claim_revision',{'title':name,'byline':'AMS synthetic','claim':text,'scope':'fixed-task','scope_binding':'fixed-task','payload':{}}) for name,text in [('Second premise','A distinct premise, independence unassessed.'),('Conclusion','A finite conditional conclusion.'),('Alternative premise','A separate complete warrant.')]]
    save_records(page,old,a,b,c);api(page,'/commands',command(new,previous=old))
    raw=b'Original source quote stays on fixed-task.';blob=api(page,'/blobs',{'base64':base64.b64encode(raw).decode()});art=record('artifact',{'media_type':'text/plain','byte_length':len(raw),'artifact_digest':blob['digest'],'storage':{'kind':'blob','locator':blob['digest']},'role':'authored','visibility':'private','obtained_at':'2026-10-30T00:00:00Z','representation_of':ref(old)})
    excerpt=record('excerpt',{'target_ref':ref(old),'representation_ref':ref(art),'selector':'Original source quote','comment':'Exact old-scope acceptance fixture.'});save_records(page,art,excerpt)
    return {'old':old,'new':new,'premise':a,'conclusion':b,'alternative':c,'artifact':art,'excerpt':excerpt}


def story_two(page,url,output,report):
    fixtures=scope_fixtures(page);navigate(page,url,'?space=continue&tool=review');select_review(page,ref(fixtures['excerpt']));expect(page.locator('.review-reading-text').first).to_contain_text('Original source quote');page.get_by_label('比较依据',exact=True).select_option(fixed_key(ref(fixtures['new'])));expect(page.locator('.review-reading-text').nth(1)).to_contain_text('different supervision')
    public=next(r['ref'] for r in api(page,'/authoring/catalogue')['records'] if r['ref']['id']=='entry:representation-and-use');select_review(page,public);propose_apply(page,'Current public P0 distinguishes executed scripted/oracle and unexecuted provider scope.');expect(page.locator('.review-changeset')).to_contain_text('检查后保持不变');assert api(page,'/entity?kind=entry&id='+public['id']+'&revision='+public['revision'])['revision']==public['revision']
    select_review(page,ref(fixtures['conclusion']));page.get_by_role('button',name='论证关系',exact=True).click()
    def relation(source,reason):
        page.get_by_label('关系来源依据',exact=True).select_option(fixed_key(ref(source)));page.get_by_label('关系适用范围',exact=True).fill('fixed-task');page.get_by_label('关系范围绑定',exact=True).fill('fixed-task');page.get_by_label('关系证据位置',exact=True).fill('Original synthetic statement, exact fixed revision');page.get_by_label('候选关系理由',exact=True).fill(reason);page.get_by_role('button',name='保存候选关系',exact=True).click();expect(page.get_by_role('button',name='保存候选关系',exact=True)).to_be_enabled();page.get_by_label('正式关系审阅理由',exact=True).fill('Explicit fixed-task review, no automatic semantic support.');page.locator('.review-relations article').filter(has_text=reason).get_by_role('button',name='接受为正式关系',exact=True).click();expect(page.get_by_role('button',name='保存候选关系',exact=True)).to_be_enabled()
    for source,reason in [(fixtures['old'],'Old fixed premise'),(fixtures['premise'],'Joint second premise'),(fixtures['alternative'],'Alternative complete warrant')]:relation(source,reason)
    relations=api(page,'/authoring/open',{'target_ref':ref(fixtures['conclusion'])})['relations']
    for r in [r for r in relations if r['from_ref'] in (ref(fixtures['old']),ref(fixtures['premise']))]:page.get_by_label('选择理由 '+r['id'],exact=True).check()
    page.get_by_label('支持组合理由',exact=True).fill('Joint fixed premises');page.get_by_role('button',name='保存支持组合',exact=True).click();expect(page.get_by_role('button',name='保存支持组合',exact=True)).to_be_enabled()
    for r in relations:
        if r['from_ref']==ref(fixtures['alternative']):page.get_by_label('选择理由 '+r['id'],exact=True).check()
    page.get_by_label('支持组合理由',exact=True).fill('Complete alternative warrant');page.get_by_role('button',name='保存支持组合',exact=True).click();expect(page.get_by_role('button',name='保存支持组合',exact=True)).to_be_enabled();page.get_by_label('支持组合方式',exact=True).select_option('alternative-warrants')
    warrants=api(page,'/authoring/open',{'target_ref':ref(fixtures['conclusion'])})['bundles']
    for w in warrants:page.get_by_label('选择理由 '+w['id'],exact=True).check()
    page.get_by_label('支持组合理由',exact=True).fill('Alternative reasons, independence not inferred');page.get_by_role('button',name='保存支持组合',exact=True).click();expect(page.get_by_role('button',name='保存支持组合',exact=True)).to_be_enabled();assert api(page,'/entity?kind=excerpt&id='+fixtures['excerpt']['id'])==fixtures['excerpt']
    # An ordinary authored manuscript remains independent of graph completeness.
    page.get_by_role('button',name='＋ 写一份新的私人文稿',exact=True).click()
    for label,value in [('新文稿题名','Original scope review manuscript'),('新文稿署名','AMS synthetic'),('新文稿一句简介','Original bounded acceptance text'),('新文稿正文','The old source remains valid for its original task. New scope requires explicit review.')]:page.get_by_label(label,exact=True).fill(value)
    page.get_by_role('button',name='保存私人文稿',exact=True).click();page.get_by_role('button',name='比较与修改',exact=True).click();propose_apply(page,'Preserve the scope boundary and unresolved independence.','A reviewed bounded statement; no scientific benefit or new model execution is inferred.');expect(page.locator('.review-reading-text').first).to_contain_text('reviewed bounded statement')
    page.get_by_role('button',name='选择发表',exact=True).click();page.get_by_label('公开文章ID',exact=True).fill('original-scope-acceptance')
    for label,value in [('许可依据','Original synthetic acceptance bytes'),('许可条款或具体授权','Explicit permission for this local test only'),('公开署名 / attribution','AMS synthetic')]:page.get_by_label(label,exact=True).fill(value)
    page.locator('.review-publication form').first.get_by_role('checkbox').last.check();page.get_by_role('button',name='生成私人发表选择与预览',exact=True).click();expect(page.get_by_role('heading',name='这些文件会进入选择',exact=True)).to_be_visible();patch=download(page,lambda:page.get_by_role('button',name='下载有base的可应用patch',exact=True).click());assert b'diff --git ' in patch and b'study/entries/original-scope-acceptance' in patch;assert CANARY.encode() not in patch;(output/'reviewed-selection.patch').write_bytes(patch)
    manifest=rows(page,'publication_manifest')[-1];report['stories']['scope_to_publication']={'old_ref':ref(fixtures['old']),'new_ref':ref(fixtures['new']),'excerpt_ref':ref(fixtures['excerpt']),'manifest_ref':ref(manifest),'bundle_refs':[ref(r) for r in rows(page,'support_bundle')],'no_git_execution':True};page.screenshot(path=str(output/'story-two.png'),full_page=True);report['checks'].append('Story 2: old quote/new scope, exact public checked-unchanged, explicit formal AND/OR, real base-bound manuscript apply + reviewed publication preview/patch')


def story_three(page,url,output,report):
    before_runs=rows(page,'run');navigate(page,url,'?space=lab');page.get_by_label('选择一项研究',exact=True).select_option('c2c-cache-retraction-study');page.get_by_label('操作',exact=True).select_option('inspect');page.get_by_role('button',name='查看已保存结果',exact=True).click();expect(page.locator('.lab-job')).to_contain_text('本次操作完成',timeout=20000)
    inspect_job=api(page,'/job?id='+api(page,'/jobs')['jobs'][0]['id']);assert inspect_job['plan']['operation']=='inspect';assert not inspect_job['result']['result']['execution_history']['reviewed_float32']['summary']['causal_query_controls_pass'];page.get_by_role('button',name='固定历史检查依据（不创建Run）',exact=True).click();expect(page.get_by_role('button',name='历史依据已固定',exact=True)).to_be_disabled();page.get_by_role('button',name='留下 Observation',exact=True).click()
    values={'实际观察':'Retained float32 causal-query controls failed at the original 1e-4 threshold; the history also records precision and same-shape diagnostics.','适用范围 / case / metric':'Saved single-model historical numerical control; early full tensors unavailable.','原先预期':'Partition changes alone should preserve the control at the retained threshold.','实际看见':'Float32 failure is retained, later precision amendment is separate; no new inference.','设计题名':'Original three-explanation C2C diagnostic design','竞争解释 A':'Numerical precision and different kernel/reduction paths explain the difference.','竞争解释 B':'Position/scope or shortened query changes the compared computation.','竞争解释 C':'A semantic cache mechanism contributes; historical differences alone do not identify it.','能区分两者的诊断对照':'Preserve dtype, shape, prefix and fixed seeds; compare same-shape permutation separately from shortened query and precision. This is a proposed contrast only.','仍未解决 / 下次从哪里继续':'Early full tensors are missing; what new independently authorized evidence would discriminate these explanations?'}
    for label,value in values.items():page.get_by_label(label,exact=True).fill(value)
    page.get_by_role('button',name='保存并连回当前案头',exact=True).click();expect(page.locator('.lab-notice')).to_contain_text('Observation');observations=rows(page,'observation');observation=observations[-1];assert 'run_ref' not in observation and observation['basis_refs'];design=rows(page,'design')[-1];assert '竞争解释 C' in design['body'] and design['status']=='proposed-not-run'
    page.get_by_label('操作',exact=True).select_option('check-saved-results');page.get_by_role('button',name='核查公开保存结果',exact=True).click();expect(page.locator('.lab-job')).to_contain_text('本次操作完成',timeout=20000);checked=api(page,'/job?id='+api(page,'/jobs')['jobs'][0]['id']);assert checked['plan']['operation']=='check-saved-results'
    page.locator('.lab-jobs li').filter(has_text=inspect_job['id'][:8]).get_by_role('button').click();page.get_by_role('button',name='固定历史检查依据（不创建Run）',exact=True).click();saved_observation=page.locator('.lab-saved-observations>details').first;saved_observation.locator('summary').first.click();expect(page.get_by_label('分析方法',exact=True)).to_be_visible();page.get_by_label('分析方法',exact=True).fill('Inspect retained history and run the native saved-receipt verification; no new model execution.');page.get_by_label('分析范围',exact=True).fill('Historical retained single-model control only.');page.get_by_label('分析判断与限制',exact=True).fill('The float32 failure remains. Missing early tensors prevent retrospective reconstruction; no semantic effectiveness claim follows.');page.get_by_role('button',name='保存独立 Analysis',exact=True).click();expect(page.locator('.lab-authored-analysis [role=status]')).to_contain_text('Analysis已保存');first=rows(page,'analysis')[-1]
    page.get_by_label('分析判断与限制',exact=True).fill('Revised analysis: precision amendment does not erase the original 1e-4 failure. Same-shape numerical dependence is distinct from semantic recovery. Early full tensors remain unavailable.');page.get_by_role('button',name='保存分析新版本',exact=True).click();expect(page.locator('.lab-authored-analysis [role=status]')).not_to_contain_text(first['revision']);analysis=rows(page,'analysis')[-1];assert analysis['id']==first['id'] and analysis['revision']!=first['revision'];assert analysis['run_refs']==[];assert api(page,'/entity?kind=analysis&id='+first['id']+'&revision='+first['revision'])['result']==first['result']
    navigate(page,url,'?space=continue&tool=review');select_review(page,ref(analysis));expect(page.locator('.review-reading-text').first).to_contain_text('Early full tensors remain unavailable');page.get_by_role('button',name='＋ 写一份新的私人文稿',exact=True).click()
    for label,value in [('新文稿题名','Original bounded C2C interpretation'),('新文稿署名','AMS synthetic'),('新文稿一句简介','Authored interpretation of retained public controls, not new inference.'),('新文稿正文','Synthetic provisional explanation to be bounded by actual historical evidence.')]:page.get_by_label(label,exact=True).fill(value)
    page.get_by_role('button',name='保存私人文稿',exact=True).click();body='The retained C2C float32 control failed at its original threshold. Precision amendments and same-shape diagnostics remain distinct. Cache distribution dependence does not establish factual recovery. Early full tensors were not saved; no new model run is reported.';propose_apply(page,'Bound the authored interpretation to actual saved controls and explicit missing early raw.',body);expect(page.locator('.review-reading-text').first).to_contain_text('Early full tensors were not saved');page.get_by_label('修订开放问题',exact=True).fill('Which separately authorized new contrast could distinguish the three explanations?');page.get_by_role('button',name='保留编辑停点',exact=True).click();expect(page.locator('.review-notice')).to_contain_text('编辑停点已留')
    entry=next(r for r in rows(page,'entry') if r['title']=='Original bounded C2C interpretation');assert entry['payload']['source_basis_ref']==ref(analysis);assert rows(page,'run')==before_runs
    report['stories']['historical_c2c']={'inspection_job':inspect_job['id'],'check_job':checked['id'],'observation_ref':ref(observation),'design_ref':ref(design),'analysis_old_ref':ref(first),'analysis_ref':ref(analysis),'entry_ref':ref(entry),'no_new_run':True};page.screenshot(path=str(output/'story-three.png'),full_page=True);report['checks'].append('Story 3: real historical failure -> no-Run Observation -> three alternatives/proposed Design -> native saved-receipt check -> independent Analysis revision -> exact-basis bounded manuscript -> unresolved stop')


def recovery_checks(page,context,url,output,report):
    navigate(page,url);before=page.get_by_label('这一刻，想弄明白什么？',exact=True).input_value();held=[]
    def hold_creation(route):
        body=route.request.post_data_json
        if any(c.get('record',{}).get('kind')=='thread' for c in body.get('commands',[])):held.append(route)
        else:route.continue_()
    page.route('**/api/units',hold_creation);page.get_by_role('button',name='＋ 新案头',exact=True).click();expect(page.locator('.desk-layout')).to_have_attribute('inert','');assert not page.get_by_label('这一刻，想弄明白什么？',exact=True).evaluate('node=>{node.focus();return document.activeElement===node}');page.keyboard.insert_text('MUST_NOT_ENTER_OLD_DESK');expect(page.get_by_label('这一刻，想弄明白什么？',exact=True)).to_have_value(before);assert held;held[0].fulfill(response=held[0].fetch());page.unroute('**/api/units',hold_creation);expect(page.get_by_label('这一刻，想弄明白什么？',exact=True)).to_be_editable();expect(page.get_by_label('这一刻，想弄明白什么？',exact=True)).to_have_value('');page.get_by_label('这一刻，想弄明白什么？',exact=True).fill('CAS original synthetic base');page.get_by_label('这一刻，想弄明白什么？',exact=True).blur();saved(page)
    other=context.new_page();observe(other,url,report);navigate(other,url);other.locator('.thread-list button').filter(has_text='CAS original synthetic base').click();expect(other.get_by_label('这一刻，想弄明白什么？',exact=True)).to_have_value('CAS original synthetic base')
    page.get_by_label('这一刻，想弄明白什么？',exact=True).fill('CAS first tab committed input');page.get_by_label('这一刻，想弄明白什么？',exact=True).blur();saved(page)
    other.get_by_label('这一刻，想弄明白什么？',exact=True).fill('CAS second tab retained input');other.get_by_label('这一刻，想弄明白什么？',exact=True).blur();expect(other.locator('.conflict-panel')).to_be_visible();other.locator('.conflict-panel summary').click();expect(other.locator('.conflict-panel')).to_contain_text('CAS first tab committed input');expect(other.get_by_label('这一刻，想弄明白什么？',exact=True)).to_have_value('CAS second tab retained input')
    conflict=json.loads(download(other,lambda:other.get_by_role('button',name='下载私人案头',exact=True).click()));assert conflict['schema']=='ams-uncommitted-input/1' and conflict['record']['payload']['question']=='CAS second tab retained input';(output/'cas-uncommitted.json').write_text(json.dumps(conflict,ensure_ascii=False,indent=2));other.get_by_role('button',name='以当前输入更新新版本',exact=True).click();saved(other)
    # Chromium's real Input domain emits composition updates/commit, rather than
    # replacing DOM values behind React. This is not an OS-specific IME claim.
    box=other.get_by_label('这一刻，想弄明白什么？',exact=True);box.fill('');box.focus();cdp=context.new_cdp_session(other);cdp.send('Input.imeSetComposition',{'text':'记忆连续性','selectionStart':5,'selectionEnd':5});cdp.send('Input.insertText',{'text':'记忆连续性'});expect(box).to_have_value('记忆连续性');box.blur();saved(other);other.reload();ready(other);expect(other.get_by_label('这一刻，想弄明白什么？',exact=True)).to_have_value('记忆连续性')
    session=next(r for r in rows(other,'session') if r['payload']['question']=='记忆连续性');history=api(other,'/history?kind=session&id='+session['id'])['records'];assert any(r['payload']['question']=='CAS first tab committed input' for r in history) and any(r['payload']['question']=='CAS second tab retained input' for r in history)
    seen=[]
    def lose_ack(route):
        request=route.request.post_data_json
        if request.get('record',{}).get('kind')=='session':
            seen.append(request);response=route.fetch();assert response.status==200;route.abort('failed')
        else:route.continue_()
    other.route('**/api/commands',lose_ack);unack='断线前未确认的中文输入 '+CANARY;box=other.get_by_label('这一刻，想弄明白什么？',exact=True);box.fill(unack);box.blur();expect(other.locator('[data-save-state]')).to_have_attribute('data-save-state','disconnected');recovery=download(other,lambda:other.get_by_role('button',name='下载私人案头',exact=True).click());value=json.loads(recovery);assert value['schema']=='ams-uncommitted-input/1' and value['record']['payload']['question']==unack;assert len({c['idempotency_key'] for c in seen})==1;(output/'lost-ack-recovery.json').write_bytes(recovery)
    other.unroute('**/api/commands',lose_ack);import_file(other,recovery);expect(other.get_by_label('这一刻，想弄明白什么？',exact=True)).to_have_value(unack);saved(other);other.close()
    report['checks'].append('New-desk pending locks old input until actual ack; real two-tab CAS preserves both inputs/history; Chromium IME composition commits Chinese without loss; actual committed/lost HTTP ack exports unknown-input file and explicit import recovers it')


def restart_assertions(browser,service,page,output,report):
    old_token=page.evaluate("JSON.parse(document.getElementById('ams-local-bootstrap').textContent).token");service.stop(abrupt=True);url=service.start();page=browser.new_page(viewport={'width':1440,'height':1000},reduced_motion='reduce');observe(page,url,report);navigate(page,url)
    new_token=page.evaluate("JSON.parse(document.getElementById('ams-local-bootstrap').textContent).token");assert old_token!=new_token
    status=page.evaluate("async token=>(await fetch('/api/doctor',{headers:{Authorization:'Bearer '+token}})).status",old_token);assert status==401
    original=report['stories']['capture_to_reading'];session=api(page,'/entity?kind=session&id='+original['session_ref']['id']);assert session['payload']['question']==QUESTION
    for old in original['excerpt_refs']:
        current=api(page,'/entity?kind=excerpt&id='+old['id']+'&revision='+old['revision']);assert ref(current)==old
    page.locator('.thread-list button').filter(has_text=QUESTION).click();expect(page.locator('.desk-items .excerpt-card').first).to_contain_text(original['quote']);expect(page.get_by_label('这段摘录的批注',exact=True)).to_have_value(CANARY+' 公开片段的私人批注');expect(page.get_by_label('旁注',exact=True).first).to_have_value('只记录实际部分阅读，候选相似不构成支持。')
    scope=report['stories']['scope_to_publication'];manifest=api(page,'/entity?kind=publication_manifest&id='+scope['manifest_ref']['id']+'&revision='+scope['manifest_ref']['revision']);preview=api(page,'/publication/preview',{'manifest_ref':ref(manifest)});assert preview['files'];assert all(api(page,'/entity?kind=support_bundle&id='+b['id']+'&revision='+b['revision'])['rationale'] for b in scope['bundle_refs']);assert api(page,'/entity?kind=excerpt&id='+scope['excerpt_ref']['id'])['target_ref']==scope['old_ref']
    history=report['stories']['historical_c2c'];analysis=api(page,'/entity?kind=analysis&id='+history['analysis_ref']['id']+'&revision='+history['analysis_ref']['revision']);assert 'Early full tensors' in analysis['result'];assert analysis['run_refs']==[];assert api(page,'/doctor')['ok']
    page.locator('.public-selection summary').click();public=download(page,lambda:page.get_by_role('button',name='公开选材 JSON ↓').click());assert CANARY.encode() not in public
    for width in (1440,1024,768,390,320):
        page.set_viewport_size({'width':width,'height':1000});fits(page);page.get_by_label('这一刻，想弄明白什么？',exact=True).scroll_into_view_if_needed();page.screenshot(path=str(output/f'local-recovered-{width}.png'))
    page.evaluate('document.documentElement.style.fontSize="200%"');fits(page);page.screenshot(path=str(output/'local-recovered-320-font200.png'));page.evaluate('document.documentElement.style.fontSize=""')
    report['checks'].append('Five local multi-desk viewports 1440/1024/768/390/320 and 320px at 200% font fit without page overflow')
    report['checks'].append('Actual SIGKILL/restart same data root rotates token and rejects old token; exact quotes/annotations/notes, formal reasons, private publication selection and historical Analysis survive; public selection excludes private canary')
    return page,url


def cli_backup_restore(browser,service,page,output,runtime,report):
    service.stop();plan=output/'native-cli-plan.json';plan.write_text(json.dumps({'plan':{'study':'observation-contract-study','operation':'run','parameters':{'operation':'search-pair','model':'equivalent-control','left':'a','right':'b'}},'idempotency_key':'original-cli-native'}))
    def cli(data,*args):
        result=subprocess.run([sys.executable,'-B','-m','services.local','--project',str(ROOT),'--data-root',str(data),*map(str,args)],cwd=ROOT,check=True,text=True,capture_output=True,timeout=60);return json.loads(result.stdout)
    job=cli(service.data,'request','/jobs','--json',plan);assert job['state']=='succeeded' and job['attempts'][-1]['state']=='succeeded';(output/'cli-native-job.json').write_text(json.dumps(job,ensure_ascii=False,indent=2))
    backup=runtime/'backup';restored=runtime/'restored';receipt=cli(service.data,'backup',backup);restoration=cli(service.data,'restore',backup,restored);doctor=cli(restored,'doctor');assert doctor['ok'];service.data=restored;url=service.start();page=browser.new_page(viewport={'width':1440,'height':1000});observe(page,url,report);navigate(page,url);original=report['stories']['capture_to_reading'];page.locator('.thread-list button').filter(has_text=QUESTION).click();expect(page.locator('.desk-items .excerpt-card').first).to_contain_text(original['quote']);assert api(page,'/entity?kind=session&id='+original['session_ref']['id'])['payload']['question']==QUESTION;native=api(page,'/job/evidence?id='+job['id']);assert native
    report['backup']={'receipt':receipt,'restoration':restoration,'doctor':doctor,'cli_job_id':job['id'],'restored_native_evidence_available':True};report['checks'].append('Actual CLI request waits native finite job to succeeded before owner close; complete backup/restore into a new root passes doctor and retains exact quote plus native evidence')
    return page,url


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--site-root',type=Path,default=ROOT/'dist/site');parser.add_argument('--output-dir',type=Path,default=ROOT/'dist/local-acceptance');parser.add_argument('--browser-executable');args=parser.parse_args();output=args.output_dir.resolve();output.mkdir(parents=True,exist_ok=True);site=args.site_root.resolve()
    if not (site/'index.html').is_file():raise SystemExit('Build an actual reader artifact first (--site-root).')
    runtime=Path(tempfile.mkdtemp(prefix='runtime-',dir=output if not output.is_relative_to(ROOT) else None));data=runtime/'data';service=LocalProcess(site,data,output);report={'checks':[],'stories':{},'errors':[],'external':[],'runtime':str(runtime),'site':str(site),'status':'failed'}
    try:
        url=service.start()
        with sync_playwright() as p:
            browser=p.chromium.launch(executable_path=args.browser_executable);context=browser.new_context(viewport={'width':1440,'height':1000},reduced_motion='reduce');page=context.new_page();observe(page,url,report)
            try:
                lab_registry_checks(page,url,report);story_one(page,url,output,report);story_two(page,url,output,report);story_three(page,url,output,report);recovery_checks(page,context,url,output,report);page,url=restart_assertions(browser,service,page,output,report);page,url=cli_backup_restore(browser,service,page,output,runtime,report)
            except Exception:
                report['status']='failed'
                page.screenshot(path=str(output/'failure.png'),full_page=True);(output/'failure-text.txt').write_text(page.locator('body').inner_text());raise
            assert not report['errors'] and not report['external'],report
            for path in site.rglob('*'):
                if path.is_file():assert CANARY.encode() not in path.read_bytes(),path
            report['checks'].append('All supplied public artifact bytes scanned for the injected private synthetic canary; no external requests or page errors')
            report['status']='passed';browser.close()
    finally:
        service.stop();(output/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    assert report['status']=='passed','Remaining acceptance steps not implemented'
    print('PASS: full local App three stories, real CLI native job, exact-reference restart, CAS, IME, lost ack recovery, backup/restore and public canary')

if __name__=='__main__':main()
