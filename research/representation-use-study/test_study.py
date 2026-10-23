import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import corpus
import study


class RepresentationTests(unittest.TestCase):

    def config(self, **kw):
        c=study.settings(modes=('full',),orders=('forward',),backends=('scripted','latest','abstain','oracle'))
        c.update(kw)
        return c

    def first(self, **kw):
        c=self.config(**kw); j=study.plan(c)[0]; case=study.index()[j['case']]; q=case['questions'][0]
        return c,j,case,q

    def interrupt_write(self,target):
        """Write a real prefix then interrupt, for official or staged artifact names."""
        original=Path.open; triggered=[]
        class PrefixWriter:
            def __init__(self,stream): self.stream=stream
            def __enter__(self): self.stream.__enter__(); return self
            def __exit__(self,*args): return self.stream.__exit__(*args)
            def __getattr__(self,name): return getattr(self.stream,name)
            def write(self,value):
                self.stream.write(value[:max(1,len(value)//2)])
                self.stream.flush(); triggered.append(True)
                raise KeyboardInterrupt('synthetic interruption after actual prefix write')
        def opening(path,*args,**kwargs):
            stream=original(path,*args,**kwargs)
            mode=args[0] if args else kwargs.get('mode','r')
            if not triggered and 'x' in mode and (path.name==target or path.name.startswith('.'+target+'.')):
                return PrefixWriter(stream)
            return stream
        return patch.object(Path,'open',opening)

    def test_receipt_mid_write_is_not_published_and_can_resume(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); config=self.config()
            with self.interrupt_write('receipt.json'):
                with self.assertRaises(KeyboardInterrupt): study.run(root,config,limit=1)
            self.assertFalse(list(root.glob('attempts/*/*/receipt.json')))
            partials=list(root.glob('attempts/*/*/.receipt.json.*.pending'))
            self.assertEqual(len(partials),1)
            before=partials[0].read_bytes()
            result=study.run(root,config,resume=True,limit=1)
            self.assertEqual(result['states'],{'interrupted':1,'successful':1})
            self.assertEqual(partials[0].read_bytes(),before)

    def test_attempt_artifact_interruptions_during_write_and_publication(self):
        config=self.config(); one=study.plan(config)[:1]; link=study.os.link
        for artifact in ('request.json','started.json','response.txt','receipt.json'):
            for moment in ('mid-write','before-publish','after-publish'):
                with self.subTest(artifact=artifact,moment=moment),tempfile.TemporaryDirectory() as td:
                    root=Path(td); hit=[]
                    def publication(src,dst):
                        if Path(dst).name==artifact and not hit:
                            hit.append(True)
                            if moment=='after-publish': link(src,dst)
                            raise KeyboardInterrupt('synthetic '+moment)
                        return link(src,dst)
                    interrupt=self.interrupt_write(artifact) if moment=='mid-write' else patch.object(study.os,'link',publication)
                    with patch.object(study,'plan',return_value=one),patch.object(study,'backend',wraps=study.backend) as b:
                        with interrupt:
                            with self.assertRaises(KeyboardInterrupt): study.run(root,config,limit=1)
                        before={p:p.read_bytes() for p in root.rglob('*') if p.is_file()}
                        official=list(root.glob('attempts/*/*/'+artifact))
                        self.assertEqual(bool(official),moment=='after-publish')
                        if official:
                            if artifact.endswith('.json'): study.load(official[0])
                            else: study.parse(official[0].read_text())
                        initial_calls=b.call_count
                        result=study.run(root,config,resume=True,limit=1)
                        done=artifact=='receipt.json' and moment=='after-publish'
                        self.assertEqual(b.call_count-initial_calls,0 if done else 1)
                        self.assertEqual(result['states'],{'successful':1} if done else {'interrupted':1,'successful':1})
                        self.assertTrue(all(p.exists() and p.read_bytes()==value for p,value in before.items()))
                        if not done:
                            receipts=study.check_run(root)[1]
                            old=next(r for r in receipts if r['status']=='interrupted')
                            self.assertTrue(old['incomplete_artifacts'])
                            self.assertEqual(old['request'] is None,artifact=='request.json' and moment!='after-publish')

    def test_manifest_and_report_atomic_publication_no_overwrite(self):
        for artifact in ('manifest.json','report.json'):
            for moment in ('mid-write','before-publish','after-publish'):
                with self.subTest(artifact=artifact,moment=moment),tempfile.TemporaryDirectory() as td:
                    root=Path(td); path=root/artifact; value={'complete':'中文'*40}; hit=[]; link=study.os.link
                    def publication(src,dst):
                        if Path(dst).name==artifact and not hit:
                            hit.append(True)
                            if moment=='after-publish': link(src,dst)
                            raise KeyboardInterrupt('synthetic '+moment)
                        return link(src,dst)
                    interrupt=self.interrupt_write(artifact) if moment=='mid-write' else patch.object(study.os,'link',publication)
                    with interrupt:
                        with self.assertRaises(KeyboardInterrupt): study.freeze(path,value)
                    self.assertEqual(path.exists(),moment=='after-publish')
                    staged=list(root.glob('.'+artifact+'.*.pending')); self.assertEqual(len(staged),1)
                    before=staged[0].read_bytes()
                    if path.exists():
                        self.assertEqual(study.load(path),value)
                        with self.assertRaises(FileExistsError): study.freeze(path,{'replace':'forbidden'})
                        self.assertEqual(study.load(path),value)
                    else:
                        study.freeze(path,value); self.assertEqual(study.load(path),value)
                    self.assertEqual(staged[0].read_bytes(),before)

    def test_no_published_manifest_requires_new_output_and_no_backend(self):
        for moment in ('mid-write','before-publish','after-publish'):
            with self.subTest(moment=moment),tempfile.TemporaryDirectory() as td:
                root=Path(td); config=self.config(); hit=[]; link=study.os.link
                def publication(src,dst):
                    if Path(dst).name=='manifest.json' and not hit:
                        hit.append(True)
                        if moment=='after-publish': link(src,dst)
                        raise KeyboardInterrupt('synthetic '+moment)
                    return link(src,dst)
                interrupt=self.interrupt_write('manifest.json') if moment=='mid-write' else patch.object(study.os,'link',publication)
                with interrupt:
                    with self.assertRaises(KeyboardInterrupt): study.run(root,config,limit=1)
                before={p:p.read_bytes() for p in root.iterdir() if p.is_file()}
                if moment=='after-publish':
                    self.assertEqual(study.run(root,config,resume=True,limit=1)['states'],{'successful':1})
                else:
                    with patch.object(study,'backend',side_effect=AssertionError('untrusted startup executed')):
                        with self.assertRaisesRegex(ValueError,'without complete published manifest'):
                            study.run(root,config,resume=True,limit=1)
                self.assertTrue(all(p.read_bytes()==value for p,value in before.items()))

    def test_published_corruption_is_not_recovered_as_interruption(self):
        for artifact in ('manifest.json','request.json','started.json','receipt.json'):
            with self.subTest(artifact=artifact),tempfile.TemporaryDirectory() as td:
                root=Path(td); config=self.config(); study.run(root,config,limit=1)
                path=root/'manifest.json' if artifact=='manifest.json' else next(root.glob('attempts/*/*/'+artifact))
                path.write_text('{"truncated":')
                with patch.object(study,'backend',side_effect=AssertionError('corruption executed')):
                    with self.assertRaises(json.JSONDecodeError): study.run(root,config,resume=True,limit=1)
                self.assertEqual(path.read_text(),'{"truncated":')

    def test_family_split_before_variants_and_matrix(self):
        data=corpus.corpus(); self.assertEqual(len(data['cases']),64)
        groups={}
        for c in data['cases']: groups.setdefault(c['group'],set()).add(c['split'])
        self.assertEqual(len(groups),8); self.assertTrue(all(len(s)==1 for s in groups.values()))
        for group in groups:
            cs=[c for c in data['cases'] if c['group']==group]
            self.assertEqual(len(cs),8)
            self.assertEqual({(c['history'],c['task']) for c in cs},
                             {(h,t) for h in ('fixed','updated') for t in ('current','expanded')})

    def test_task_expansion_adds_uses_without_changing_common_questions(self):
        self.assertEqual(sum(len(c['questions']) for c in corpus.corpus()['cases']),320)
        current=corpus.questions('current'); expanded=corpus.questions('expanded')
        self.assertEqual(len(current),2); self.assertEqual(len(expanded),8)
        self.assertEqual(current,expanded[:2])
        self.assertTrue(all(q['task_role']=='added' for q in expanded[2:]))
        self.assertEqual({q['kind'] for q in expanded[2:]},
                         {'decision','agreement','provenance','wording','direct','indirect'})
        for case in corpus.corpus()['cases']:
            match=next(c for c in corpus.corpus()['cases'] if c['group']==case['group'] and
                       c['history']==case['history'] and c['variant']==case['variant'] and c['task']!=case['task'])
            self.assertEqual(case['events'],match['events'])
            self.assertEqual(case['questions'][:2],match['questions'][:2])

    def test_gold_scope_authority_time_acceptance_history(self):
        q={'kind':'decision','scope':'current','at':5}
        for f in ('scope','authority','time','agreement','provenance'):
            e=corpus.events_for(f,False,'x')
            self.assertEqual(corpus.truth(e,q)['accepted'],['answer:blue'])
            updated=corpus.events_for(f,True,'x')
            self.assertEqual(corpus.truth(updated,q)['accepted'],['answer:amber'])
            self.assertEqual(corpus.truth(updated,dict(q,at=1))['accepted'],['answer:blue'])
        conflict=corpus.truth(corpus.events_for('conflict',False,'x'),q)
        self.assertEqual(set(conflict['accepted']),{'clarify:conflict','abstain:conflict'})
        self.assertTrue(conflict['conflicting'])
        self.assertIn('clarify:scope',corpus.truth(corpus.events_for('unknown',False,'x'),q)['accepted'])

    def test_indirect_is_not_direct_and_positive_direct_control(self):
        events=corpus.events_for('relations',False,'x')
        self.assertEqual(corpus.truth(events,{'kind':'direct'})['accepted'],['answer:no'])
        self.assertEqual(corpus.truth(events,{'kind':'indirect'})['accepted'],['answer:yes'])
        changed=copy.deepcopy(events); changed[-1]['pair']=['A','C']
        self.assertEqual(corpus.truth(changed,{'kind':'direct'})['accepted'],['answer:yes'])
        self.assertEqual(corpus.truth(changed,{'kind':'indirect'})['accepted'],['answer:no'])

    def test_writer_cannot_receive_questions_and_drops_detail(self):
        events=corpus.events_for('scope',True,'x'); before=copy.deepcopy(events)
        summary=corpus.writer(events,'summary')
        self.assertEqual(before,events)
        self.assertFalse(any('wording' in m['record'] or 'actor' in m['record'] for m in summary))
        self.assertFalse(any(m['record']['id']=='scope:e1' for m in summary))
        with self.assertRaises(TypeError): corpus.writer(events,'summary',{'gold':'secret'})

    def test_complete_json_without_terminal_newline_first_and_later_record(self):
        case=next(c for c in corpus.corpus()['cases'] if c['group']=='scope' and c['history']=='fixed' and c['task']=='current')
        materials=corpus.writer(case['events'],'raw'); preceding=b''
        for index,m in enumerate(materials):
            record=corpus.canonical(m['record']).encode('utf-8')
            budget=len(preceding)+len(record)
            with self.subTest(record=index,budget=budget):
                config=self.config(memory_budget=budget)
                job=dict(arm='raw',order='forward',mode='equal',backend='scripted')
                q=case['questions'][index]
                request,audit=study.prepare(case,q,job,config)
                self.assertEqual(request['memory'].encode('utf-8'),preceding+record)
                self.assertFalse(request['memory'].endswith('\n'))
                self.assertEqual(audit['memory_bytes'],budget)
                self.assertEqual(audit['delivered'][-1]['delivered_bytes'],len(record))
                self.assertEqual(audit['delivered'][-1]['full_bytes'],len(record)+1)
                self.assertTrue(all(c['complete'] for c in audit['delivered']))
                self.assertEqual(json.loads(request['memory'].splitlines()[-1]),m['record'])
                self.assertEqual(audit['availability'],'sufficient')
                result=study.score(case,q,audit,study.backend(request))
                self.assertTrue(result['task_correct'])
                self.assertTrue(result['citations_valid'])
                self.assertFalse(result['unsupported_answer'])
            preceding+=record+b'\n'

    def test_missing_closing_brace_and_split_chinese_bytes_stay_incomplete(self):
        case=next(c for c in corpus.corpus()['cases'] if c['group']=='scope' and c['history']=='fixed' and c['task']=='current')
        preceding=b''; job=dict(arm='raw',order='forward',mode='equal',backend='scripted')
        for index,m in enumerate(corpus.writer(case['events'],'raw')):
            record=corpus.canonical(m['record']).encode('utf-8'); chinese=next(i for i,b in enumerate(record) if b>=128)
            for endpoint in (len(record)-1,chinese+1,chinese+2):
                with self.subTest(record=index,endpoint=endpoint):
                    budget=len(preceding)+endpoint
                    request,audit=study.prepare(case,case['questions'][index],job,self.config(memory_budget=budget))
                    self.assertEqual(request['memory'],(preceding+record[:endpoint]).decode('utf-8',errors='ignore'))
                    self.assertLessEqual(audit['memory_bytes'],budget)
                    self.assertFalse(audit['delivered'][-1]['complete'])
                    self.assertTrue(all(c['complete'] for c in audit['delivered'][:-1]))
                    self.assertEqual(audit['availability'],'insufficient')
                    with self.assertRaises(json.JSONDecodeError): json.loads(request['memory'].splitlines()[-1])
                    self.assertNotEqual(study.parse(study.backend(request))['action'],'answer')
            preceding+=record+b'\n'

    def test_actual_budget_count_partial_unicode_order_and_sufficiency(self):
        config,j,c,q=self.first(memory_budget=43)
        j.update(mode='equal'); request,audit=study.prepare(c,q,j,config)
        self.assertLessEqual(audit['memory_bytes'],43)
        self.assertEqual(audit['memory_bytes'],len(request['memory'].encode()))
        self.assertEqual(audit['request_bytes'],len(corpus.canonical(request).encode()))
        self.assertEqual(audit['availability'],'insufficient')
        self.assertFalse(audit['delivered'][0]['complete'])
        self.assertEqual(audit['used'],'unknown')
        config['memory_budget']=0
        self.assertEqual(study.prepare(c,q,j,config)[1]['delivered'],[])
        j.update(mode='full'); r0,a0=study.prepare(c,q,j,config)
        j['order']='reverse'; r1,a1=study.prepare(c,q,j,config)
        self.assertEqual(a1['selected_ids'],list(reversed(a0['selected_ids'])))
        self.assertNotEqual(r0['memory'],r1['memory'])

    def test_summary_loss_and_conflict_are_not_untruncated_labels(self):
        config,j,c,q=self.first(); j['arm']='summary'
        word=next(q for q in corpus.questions('expanded') if q['kind']=='wording')
        self.assertEqual(study.prepare(c,word,j,config)[1]['availability'],'insufficient')
        c=next(c for c in corpus.corpus()['cases'] if c['group']=='conflict' and c['history']=='fixed' and c['task']=='current')
        q=c['questions'][0]; j['arm']='raw'
        self.assertEqual(study.prepare(c,q,j,config)[1]['availability'],'conflicting')
        j['mode']='equal'; config['memory_budget']=1
        self.assertEqual(study.prepare(c,q,j,config)[1]['availability'],'insufficient')
        # Updated summaries support current action while losing the old historical value.
        c=next(c for c in corpus.corpus()['cases'] if c['group']=='scope' and c['history']=='updated' and c['task']=='current')
        j.update(arm='summary',mode='full')
        self.assertEqual(study.prepare(c,c['questions'][0],j,config)[1]['availability'],'sufficient')
        self.assertEqual(study.prepare(c,next(q for q in corpus.questions('expanded') if q['id']=='historical'),j,config)[1]['availability'],'insufficient')

    def test_backend_has_no_gold_and_controls_have_counterexamples(self):
        config,j,c,q=self.first(); request,audit=study.prepare(c,q,j,config)
        self.assertNotIn('oracle_extra_information',request)
        self.assertEqual(study.parse(study.backend(request))['value'],'blue')
        request['backend']='latest'
        self.assertEqual(study.parse(study.backend(request))['value'],'green')
        request['backend']='abstain'
        self.assertTrue(study.score(c,q,audit,study.backend(request))['over_abstain'])
        request['backend']='oracle'; request['oracle_extra_information']=corpus.truth(c['events'],q)
        self.assertTrue(study.score(c,q,audit,study.backend(request))['task_correct'])
        bad=study.response('answer:blue',['absent:e999'])
        self.assertFalse(study.score(c,q,audit,bad)['citations_valid'])

    def test_failure_resume_replay_without_backend_invocation(self):
        with tempfile.TemporaryDirectory(prefix='ams-representation-') as td:
            root=Path(td); config=self.config(fail_once=True)
            first=study.run(root,config,limit=2)
            self.assertEqual(first['states'],{'failed':1,'successful':1})
            with patch.object(study,'backend',wraps=study.backend) as b:
                second=study.run(root,config,resume=True,limit=1)
                self.assertEqual(b.call_count,1)
            self.assertEqual(second['states'],{'failed':1,'successful':2})
            with patch.object(study,'backend',side_effect=AssertionError('replay called backend')):
                self.assertEqual(study.report(root),second)
            _,receipts,pending=study.check_run(root)
            retry=next(r for r in receipts if r['attempt']==2)
            self.assertEqual(retry['retry_of'],retry['job']['id']+'/0001')
            self.assertEqual(len(pending),0)
            self.assertEqual(len(list(root.glob('attempts/*/*/response.txt'))),2)

    def test_interrupted_attempt_retained_and_retried(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); config,j,c,q=self.first()
            with patch.object(study,'backend',side_effect=KeyboardInterrupt):
                with self.assertRaises(KeyboardInterrupt): study.run(root,config,limit=1)
            self.assertEqual(len(study.check_run(root)[2]),1)
            r=study.run(root,config,resume=True,limit=1)
            self.assertEqual(r['states'],{'interrupted':1,'successful':1})
            self.assertIn('may have executed',next(r for r in study.check_run(root)[1] if r['status']=='interrupted')['error'])

    def test_request_only_interruption_recovers(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); config=self.config()
            original=study.freeze
            def interrupt(path,value,raw=False):
                if path.name=='started.json': raise KeyboardInterrupt()
                original(path,value,raw)
            with patch.object(study,'freeze',side_effect=interrupt):
                with self.assertRaises(KeyboardInterrupt): study.run(root,config,limit=1)
            r=study.run(root,config,resume=True,limit=1)
            self.assertEqual(r['states'],{'interrupted':1,'successful':1})

    def test_corrupt_response_foreign_receipt_settings_and_source_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); config=self.config(); study.run(root,config,limit=1)
            with self.assertRaisesRegex(ValueError,'manifest'): study.run(root,self.config(memory_budget=1),resume=True)
            with patch.object(study,'SCORER','changed'):
                with self.assertRaisesRegex(ValueError,'manifest'): study.report(root)
            with patch.object(study,'source_identity',return_value={'changed':'identity'}):
                with self.assertRaisesRegex(ValueError,'manifest'): study.report(root)
            path=next(root.glob('attempts/*/*/receipt.json')); value=study.load(path)
            value['run_id']='foreign'; path.write_text(corpus.canonical(value))
            with self.assertRaisesRegex(ValueError,'binding'): study.report(root)
            value['run_id']=study.load(root/'manifest.json')['run_id']; path.write_text(corpus.canonical(value))
            raw=next(root.glob('attempts/*/*/response.txt')); raw.write_text('corrupt')
            with self.assertRaisesRegex(ValueError,'corrupt artifact'): study.report(root)

    def test_completed_work_is_never_invoked_again(self):
        config=self.config(); jobs=study.plan(config)[:2]
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            with patch.object(study,'plan',return_value=jobs):
                result=study.run(root,config)
                self.assertEqual(result['successful_jobs'],2)
                with patch.object(study,'backend',side_effect=AssertionError('duplicate invocation')):
                    self.assertEqual(study.run(root,config,resume=True),result)
        with self.assertRaises(ValueError): study.settings(orders=('forward','forward'))

    def test_failed_then_interrupted_retry_counts_unique_jobs(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); config=self.config(fail_once=True)
            study.run(root,config,limit=1)
            with patch.object(study,'backend',side_effect=KeyboardInterrupt):
                with self.assertRaises(KeyboardInterrupt): study.run(root,config,resume=True,limit=1)
            result=study.report(root)
            self.assertEqual(result['unexecuted'],len(study.plan(config))-1)
            bucket=result['results']['full_task_set']['full/forward/raw/scripted']
            self.assertEqual(bucket['executed_jobs'],1)
            self.assertEqual(bucket['scored_responses'],0)
            self.assertEqual(bucket['metrics']['task_correct'],0)
            self.assertEqual(bucket['outcome_statuses']['pending_interrupted'],1)
            self.assertGreater(result['results']['all_arms_sufficient']['full/forward/raw/scripted']['planned_jobs'],0)
            self.assertEqual(result['results']['all_arms_sufficient']['full/forward/raw/scripted']['scored_responses'],0)

    def test_response_written_before_receipt_is_retained(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); config=self.config(); original=study.freeze
            def interrupt(path,value,raw=False):
                if path.name=='receipt.json': raise KeyboardInterrupt()
                original(path,value,raw)
            with patch.object(study,'freeze',side_effect=interrupt):
                with self.assertRaises(KeyboardInterrupt): study.run(root,config,limit=1)
            raw=next(root.glob('attempts/*/*/response.txt')).read_bytes()
            result=study.run(root,config,resume=True,limit=1)
            receipts=study.check_run(root)[1]
            interrupted=next(r for r in receipts if r['status']=='interrupted')
            self.assertEqual(study.read_bound(root,interrupted['response']).encode(),raw)
            self.assertEqual(result['states'],{'interrupted':1,'successful':1})

    def test_runtime_is_recorded_but_portable_replay_is_not_patch_bound(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); config=self.config(); before=study.run(root,config,limit=1)
            m=study.load(root/'manifest.json'); m['python']='different-runtime'
            (root/'manifest.json').write_text(corpus.canonical(m))
            self.assertEqual(study.report(root),before)
            with self.assertRaisesRegex(ValueError,'manifest'): study.run(root,config,resume=True,limit=1)

    def test_full_raw_and_coexistence_reader_across_positions(self):
        config=self.config()
        for case in corpus.corpus()['cases']:
            for q in case['questions']:
                for order in study.ORDERS:
                    for arm in ('raw','coexistence'):
                        job=dict(arm=arm,order=order,mode='full',backend='scripted')
                        request,audit=study.prepare(case,q,job,config)
                        self.assertTrue(study.score(case,q,audit,study.backend(request))['task_correct'])

    def test_fail_once_does_not_fail_each_new_resumed_job(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); config=self.config(fail_once=True)
            study.run(root,config,limit=1)
            study.run(root,config,resume=True,limit=1)
            result=study.run(root,config,resume=True,limit=1)
            self.assertEqual(result['states'],{'failed':1,'successful':2})

    def test_over_abstain_requires_sufficient_answerable_evidence(self):
        config,job,answerable,q=self.first()
        for action in ('abstain:insufficient','clarify:scope'):
            with self.subTest(case='answerable',action=action):
                _,audit=study.prepare(answerable,q,job,config)
                result=study.score(answerable,q,audit,study.response(action))
                self.assertEqual(audit['availability'],'sufficient')
                self.assertTrue(result['over_abstain'])
                self.assertFalse(result['task_correct'])
                self.assertFalse(result['acceptable'])
        for family,availability in (('conflict','conflicting'),('unknown','sufficient')):
            with self.subTest(case=family):
                case=next(c for c in corpus.corpus()['cases'] if c['group']==family and c['history']=='fixed')
                q=case['questions'][0]; _,audit=study.prepare(case,q,job,config)
                result=study.score(case,q,audit,study.response('abstain:insufficient'))
                self.assertEqual(audit['availability'],availability)
                self.assertFalse(result['over_abstain'])
                # Deferral is required, but wrong reason is still a label/rubric failure.
                self.assertFalse(result['task_correct'])
                self.assertFalse(result['acceptable'])
                proper=corpus.truth(case['events'],q)['accepted'][0]
                self.assertTrue(study.score(case,q,audit,study.response(proper))['acceptable'])
        config['memory_budget']=1; job['mode']='equal'; q=answerable['questions'][0]
        _,audit=study.prepare(answerable,q,job,config)
        result=study.score(answerable,q,audit,study.response('abstain:insufficient'))
        self.assertEqual(audit['availability'],'insufficient')
        self.assertFalse(result['over_abstain'])
        self.assertFalse(result['task_correct'])
        self.assertTrue(result['acceptable'])

    def test_saved_control_summary_identity_and_accounting(self):
        result=study.check_saved_sample()
        self.assertEqual(result['families'],8)
        self.assertEqual(result['planned_requests'],7680)

    def test_safe_references_and_parse_refusal_timeout_states(self):
        with tempfile.TemporaryDirectory() as td:
            for ref in ('../escape','/absolute'):
                with self.assertRaises(ValueError): study.safe_ref(Path(td),ref)
        for raw,status in [('not-json','parse_failure'),('{"action":"refusal"}','refusal')]:
            with tempfile.TemporaryDirectory() as td:
                with patch.object(study,'backend',return_value=raw): result=study.run(Path(td),self.config(),limit=1)
                self.assertEqual(result['states'],{status:1})
        with tempfile.TemporaryDirectory() as td:
            with patch.object(study,'backend',side_effect=TimeoutError('synthetic timeout')):
                result=study.run(Path(td),self.config(),limit=1)
            self.assertEqual(result['states'],{'timeout':1})


if __name__=='__main__':
    unittest.main()
