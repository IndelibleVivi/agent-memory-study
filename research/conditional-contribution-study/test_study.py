"""Finite retrieval/consumer contracts and immutable raw recovery checks."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parent
EVIDENCE=Path(os.environ.get('AMS_P9_TEST_ROOT',tempfile.gettempdir()))
def module(name):
    spec=importlib.util.spec_from_file_location('conditional_'+name,ROOT/(name+'.py'))
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
s=module('study');p=module('provider');a=module('adapter')
CASES={c['id']:c for c in s.corpus()['cases']}
def setting():
    c=s.config();c.update(representations=['compact'],modes=['full'],policies=['top-k'],backends=['scripted']);return c

def cell(case='xor-01',arm='BS',rep='raw',mode='full',policy='top-k',backend='scripted'):
    j={'case':case,'family':CASES[case]['family'],'split':CASES[case]['split'],'arm':arm,'representation':rep,'mode':mode,'policy':policy,'backend':backend}
    j={'id':s.digest(j)[:24],**j};r,au=s.prepare(CASES[case],j);raw=s.consume(r)
    return j,r,au,s.parse(raw),s.score(CASES[case],au,raw)


class StudyTests(unittest.TestCase):
    def test_fixed_plan_families_and_conditions(self):
        self.assertEqual(len(s.jobs()),864)
        self.assertEqual(len({j['family'] for j in s.jobs()}),4)
        self.assertEqual({j['arm'] for j in s.jobs()},set(s.ARMS))
        self.assertTrue(all(j['split']==s.corpus()['family_splits'][j['family']] for j in s.jobs()))

    def test_complement_and_duplicate(self):
        for arm in ['empty','B','S','duplicate','sham']:
            self.assertEqual(cell(arm=arm)[3]['action'],'abstain')
        self.assertEqual(cell()[3]['value'],'1')

    def test_redundancy_no_positive_increment(self):
        for arm in ['B','S','BS','duplicate','sham']:
            self.assertTrue(cell('redundant',arm)[4]['task_correct'])

    def test_four_xor_worlds(self):
        for x in (0,1):
            for y in (0,1):self.assertEqual(cell(f'xor-{x}{y}')[3]['value'],str(x^y))

    def test_native_ranking_and_selection(self):
        j,req,au,_,_=cell()
        pool=s.materials(CASES[j['case']],j['arm'],j['representation'])
        ranks=s.retriever.rank(pool,'signal')
        self.assertEqual(au['selected_ids'],s.retriever.select(ranks,3,'top-k'))
        self.assertEqual([r['id'] for r in au['ranking']],[r['id'] for r in ranks])
        self.assertEqual([r['rank'] for r in au['ranking']],[1,2])

    def test_gold_isolation_and_writer_identity(self):
        j,r,au,_,_=cell();c=copy.deepcopy(CASES[j['case']]);c['world']={'x':9,'y':8}
        changed_r,changed_au=s.prepare(c,j)
        self.assertEqual(r,changed_r);self.assertEqual(au,changed_au)
        altered=copy.deepcopy(c['B']);altered[0]['value']['prose']='Different prose'
        self.assertNotEqual(s.digest(s.writer(altered,'raw')),s.digest(s.writer(c['B'],'raw')))
        self.assertEqual(s.writer(altered,'compact'),s.writer(c['B'],'compact'))

    def test_same_key_policy_loses_distinct_method(self):
        self.assertEqual(cell('same-key-methods')[3]['value'],'unlock')
        result=cell('same-key-methods',policy='unique-key')
        self.assertEqual(result[2]['selected_ids'],['b']);self.assertEqual(result[3]['action'],'abstain')
        self.assertEqual(len(result[2]['ranking']),2)

    def test_actual_budget_loss_and_compact_control(self):
        raw=cell(mode='equal');compact=cell(rep='compact',mode='equal')
        self.assertTrue(raw[2]['truncated']);self.assertEqual(raw[3]['action'],'abstain')
        self.assertEqual(compact[3]['value'],'1');self.assertFalse(compact[2]['truncated'])
        data=json.loads(raw[1]['messages'][1]['content'])
        self.assertLessEqual(len(data['memory'].encode()),200)
        self.assertEqual(raw[2]['delivery_digest'],s.digest(data['memory']))

    def test_exact_sham_bytes_each_writer(self):
        for c in CASES.values():
            for rep in ['raw','compact']:
                real=s.materials(c,'S',rep);sham=s.materials(c,'sham',rep)[len(c['B']):]
                self.assertEqual([len(s.line(r).encode()) for r in real],[len(s.line(r).encode()) for r in sham])
                self.assertTrue(all(r['value']['kind']=='noise' for r in sham))

    def test_world_change_vs_channel_corruption(self):
        base=cell('revision-baseline');changed=cell('revision-world-change');corrupt=cell('revision-evidence-corruption')
        self.assertEqual(base[3]['value'],'Friday')
        self.assertEqual(changed[3]['value'],corrupt[3]['value'])
        self.assertTrue(changed[4]['task_correct']);self.assertFalse(corrupt[4]['task_correct'])
        self.assertTrue(corrupt[4]['unsupported_answer'])
        self.assertEqual(s.gold(CASES['revision-baseline']),s.gold(CASES['revision-evidence-corruption']))

    def test_oracle_extra_information_separate(self):
        x=cell(arm='empty');o=cell(arm='empty',backend='oracle')
        self.assertNotIn('oracle_extra_information',x[1]);self.assertIn('oracle_extra_information',o[1])
        self.assertEqual(x[3]['action'],'abstain');self.assertTrue(o[4]['task_correct'])
        self.assertEqual(x[4]['used'],'unknown')

    def test_parser_and_citation_membership(self):
        with self.assertRaises(ValueError):s.parse('{bad')
        _,_,au,_,_=cell()
        score=s.score(CASES['xor-01'],au,s.response('answer','1',['invented']))
        self.assertTrue(score['task_correct']);self.assertFalse(score['citations_valid'])

    def temp(self):return tempfile.TemporaryDirectory(prefix='p9-test-',dir=EVIDENCE)

    def test_run_replay_and_completed_resume(self):
        with self.temp() as td:
            root=Path(td)/'run';r=s.run(root,setting());self.assertEqual(r,s.replay(root))
            self.assertEqual(r['attempt_count'],54)
            self.assertEqual(r,s.run(root,setting(),resume=True))
            with self.assertRaises(ValueError):s.run(root,setting())

    def test_failed_then_retry_preserves_receipt(self):
        with self.temp() as td:
            root=Path(td)/'run'
            def fail(req):raise RuntimeError('intentional local failure')
            s.run(root,setting(),limit=1,backend=fail)
            first=next((root/'attempts').glob('*/*/receipt.json'));old=first.read_bytes()
            r=s.run(root,setting(),resume=True)
            self.assertEqual(r['attempt_count'],55);self.assertEqual(first.read_bytes(),old)
            _,rr,_=s.check_raw(root);self.assertEqual(sum(x['status']=='failed' for x in rr),1)
            self.assertTrue(any(x['start']['retry_of'] for x in rr))

    def test_interrupted_local_attempt_indeterminate_then_new(self):
        with self.temp() as td:
            root=Path(td)/'run'
            def interrupt(req):raise KeyboardInterrupt()
            with self.assertRaises(KeyboardInterrupt):s.run(root,setting(),limit=1,backend=interrupt)
            self.assertEqual(len(s.check_raw(root)[2]),1)
            s.run(root,setting(),resume=True,limit=1)
            _,rr,pending=s.check_raw(root)
            self.assertFalse(pending);self.assertEqual([x['status'] for x in rr],['indeterminate','successful'])

    def test_parse_failure_retained(self):
        with self.temp() as td:
            root=Path(td)/'run';s.run(root,setting(),limit=1,backend=lambda _: 'bad-json')
            _,r,_=s.check_raw(root);self.assertEqual(r[0]['status'],'parse_failure');self.assertIsNone(r[0]['score'])

    def test_corruption_and_rubric_drift_rejected(self):
        with self.temp() as td:
            root=Path(td)/'run';s.run(root,setting(),limit=1)
            rp=next((root/'attempts').glob('*/*/receipt.json'));r=s.load(rp);r['raw_response']='tampered';rp.write_text(s.canonical(r))
            with self.assertRaisesRegex(ValueError,'binding drift'):s.replay(root)
        with self.temp() as td:
            root=Path(td)/'run';s.run(root,setting(),limit=1)
            with patch.object(s,'sources',return_value={'different':'revision'}):
                with self.assertRaisesRegex(ValueError,'drift'):s.replay(root)

    def test_atomic_publication_and_nonempty_manifest_rejection(self):
        with self.temp() as td:
            path=Path(td)/'artifact.json';s.freeze(path,{'accepted':True})
            with self.assertRaises(FileExistsError):s.freeze(path,{'accepted':False})
            self.assertEqual(s.load(path),{'accepted':True})
            new=Path(td)/'other.json'
            with patch.object(s.os,'link',side_effect=RuntimeError('interrupt')):
                with self.assertRaises(RuntimeError):s.freeze(new,{'x':'完整'})
            self.assertFalse(new.exists());self.assertTrue(list(Path(td).glob('.*.pending')))
            with self.assertRaisesRegex(ValueError,'nonempty'):s.run(Path(td),setting())

    def test_single_writer_and_repo_boundary(self):
        with self.temp() as td:
            root=Path(td)/'run'
            with s.single_writer(root):
                with self.assertRaisesRegex(ValueError,'writer'):s.run(root,setting())
        with self.assertRaisesRegex(ValueError,'outside repository'):s.run(ROOT/'not-a-run',setting())

    def test_adapter_capabilities_match_dispatch(self):
        self.assertEqual(set(a.describe_capabilities()['operations']),set(a.OPERATIONS))
        self.assertEqual(a.execute({'operation':'provider-plan'})['result']['cell_count'],432)
        with self.assertRaises(ValueError):a.validate_plan({'operation':'provider-plan','gold':'secret'})
        with self.assertRaises(ValueError):a.validate_plan({'operation':'run-live'})


class ProviderTests(unittest.TestCase):
    def binding(self):return {'provider':'mock-only','model_revision':'mock-v1','tokenizer':'mock-count/1','input_token_count':100,'fee_cap':'mock zero','authorized':True}
    def cell(self):return {'job':{'id':'test'},'messages':[{'role':'user','content':'original synthetic only'}],'max_output_tokens':96}
    def test_no_call_without_binding(self):
        calls=[]
        with self.assertRaises(ValueError):p.execute_cell(self.cell(),{},lambda r:calls.append(r))
        self.assertEqual(calls,[])

    def test_success_refusal_parse_and_tokenizer_binding(self):
        bind=self.binding();c=self.cell()
        good=p.execute_cell(c,bind,lambda r:{'status':'ok','output_text':s.response('answer','1')})
        self.assertEqual(good['status'],'successful');self.assertEqual(good['used'],'unknown')
        for raw,status in [({'status':'refusal'},'refusal'),({'status':'ok','output_text':'no json'},'parse_failure')]:
            self.assertEqual(p.execute_cell(c,bind,lambda _,v=raw:v)['status'],status)
        new={**bind,'tokenizer':'changed'}
        self.assertNotEqual(p.execute_cell(c,new,lambda r:{'status':'refusal'})['binding_digest'],good['binding_digest'])

    def test_rate_limit_context_and_unknown_no_automatic_retry(self):
        for code in ['rate_limit','context_overflow']:
            def fail(_):raise p.ProviderFailure(code)
            r=p.execute_cell(self.cell(),self.binding(),fail);self.assertEqual(r['status'],'failed');self.assertEqual(r['error']['code'],code)
        calls=[]
        def unknown(r):calls.append(r);raise p.ProviderFailure('timeout','unknown')
        r=p.execute_cell(self.cell(),self.binding(),unknown);self.assertEqual(r['status'],'indeterminate')
        with self.assertRaises(ValueError):p.execute_cell(self.cell(),self.binding(),unknown,prior=r)
        self.assertEqual(len(calls),1)
        retry=p.execute_cell(self.cell(),self.binding(),lambda _:{'status':'refusal'},prior=r,resolution='operator-authorized-retry-after-reconciliation')
        self.assertEqual(retry['retry_of'],p.identity(r))

    def test_review_invalidates_content_or_rubric(self):
        review=p.review_binding('response',{'version':1})
        self.assertTrue(p.review_matches(review,'response',{'version':1}))
        self.assertFalse(p.review_matches(review,'new-response',{'version':1}))
        self.assertFalse(p.review_matches(review,'response',{'version':2}))


if __name__=='__main__':unittest.main()
