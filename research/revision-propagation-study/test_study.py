import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import fixtures as data
import study


class RevisionTests(unittest.TestCase):
    def family(self,name='fact-replacement'):
        return next(f for f in data.fixtures()['families'] if f['id']==name)

    def job(self,**kw):
        j=dict(id='test',family='fact-replacement',policy='versions',delay=1,retention='tombstone',branch='natural')
        j.update(kw); return j

    def small(self):
        return dict(delays=[1],retentions=['tombstone'],policies=['versions'],branches=['natural'],tasks=10)

    def test_families_gold_bitemporal_and_boundaries(self):
        self.assertEqual(len(data.fixtures()['families']),9)
        expected={'fact-replacement':'answer:red','scope-narrowing':'abstain:unknown',
            'exception-expiry':'answer:red','commitment-revocation':'answer:blue',
            'premise-correction':'answer:hold','authority-conflict':'clarify:conflict',
            'unauthorized-message':'answer:blue','other-project':'answer:blue','stable':'answer:blue'}
        for name,label in expected.items():
            f=self.family(name); events=f['initial']+f['revision']
            self.assertIn(label,data.gold(events,data.query())['accepted'])
            self.assertEqual(data.gold(events,data.query(scope='beta'))['accepted'],data.gold(f['initial'],data.query(scope='beta'))['accepted'])
            self.assertEqual(data.gold(events,data.query(observed_time=1))['accepted'],data.gold(f['initial'],data.query(observed_time=1))['accepted'])
            if name!='fact-replacement':
                self.assertEqual(data.gold(events,data.query(valid_time=0))['accepted'],data.gold(f['initial'],data.query(valid_time=0))['accepted'])
        f=self.family('exception-expiry')
        self.assertEqual(data.gold(f['initial']+f['revision'],data.query(valid_time=4))['accepted'],['answer:blue'])

    def test_retrospective_vs_as_known_and_future_activation(self):
        f=self.family(); events=f['initial']+f['revision']
        self.assertEqual(data.gold(events,data.query(valid_time=0,observed_time=0))['accepted'],['answer:blue'])
        self.assertEqual(data.gold(events,data.query(valid_time=0,observed_time=2))['accepted'],['answer:red'])
        f=self.family('commitment-revocation'); events=f['initial']+f['revision']
        self.assertEqual(data.gold(events,data.query(valid_time=2))['accepted'],['answer:blue'])
        self.assertEqual(data.gold(events,data.query(valid_time=3,observed_time=3))['accepted'],['abstain:unknown'])
        ep=study.episode(f,self.job(family=f['id'],policy='dependencies',delay=0))
        self.assertEqual(ep['snapshots'][1]['probes']['main']['action']['label'],'abstain:unknown')

    def test_independent_answerer_cannot_receive_gold(self):
        delivery=dict(records=[dict(label='answer:deliberate-wrong',support=['x'])])
        self.assertEqual(study.answerer(delivery)['label'],'answer:deliberate-wrong')
        with self.assertRaises(TypeError): study.answerer(delivery,{'accepted':['answer:red']})
        changed=copy.deepcopy(delivery); changed['oracle_extra_information']=dict(label='answer:red',support=['extra'])
        self.assertEqual(study.answerer(changed)['label'],'answer:red')

    def test_shared_checkpoint_and_sibling_isolation(self):
        f=self.family(); before=copy.deepcopy(f); checkpoints=[]
        for p in study.POLICIES:
            ep=study.episode(f,self.job(policy=p)); checkpoints.append(ep['checkpoint_identity'])
        self.assertEqual(len(set(checkpoints)),1)
        a=study.episode(f,self.job()); b=study.episode(f,self.job())
        a['snapshots'][0]['after']['store']['events'][0]['value']='mutated'
        self.assertNotEqual(a,b); self.assertEqual(f,before)

    def test_scheduler_delays_are_task_counts(self):
        for delay in (0,1,3):
            ep=study.episode(self.family(),self.job(delay=delay))
            self.assertEqual(ep['first_refresh_task'],delay+1)
            self.assertEqual(ep['snapshots'][delay]['probes']['main']['action']['label'],'answer:red')
            self.assertTrue(all(s['probes']['main']['action']['label']=='answer:blue' for s in ep['snapshots'][:delay]))

    def test_stale_delivery_and_single_layer_repair_evidence(self):
        for layer in study.LAYERS:
            stale=study.episode(self.family(),self.job(branch='stale-'+layer))
            repair=study.episode(self.family(),self.job(branch='repair-'+layer))
            self.assertEqual(stale['snapshots'][0],repair['snapshots'][0])
            self.assertTrue(stale['snapshots'][0]['probes']['main']['score']['version_stale_delivered'])
            self.assertFalse(stale['snapshots'][0]['probes']['main']['score']['correct'])
            intervention=repair['snapshots'][1]['intervention']
            self.assertEqual(intervention['layer'],layer)
            changed=[k for k in intervention['before'] if intervention['before'][k]!=intervention['after'][k]]
            self.assertEqual(changed,[layer])
            self.assertEqual(len(repair['snapshots'][1]['probes']),7)
            injected=stale['snapshots'][0]['fault_injection']
            self.assertTrue(all(injected['before'][k]==injected['after'][k] for k in injected['before'] if k!=layer))

    def test_dependency_recompute_and_expiry(self):
        f=self.family('premise-correction')
        version=study.episode(f,self.job(family=f['id'],policy='versions',delay=0))
        dep=study.episode(f,self.job(family=f['id'],policy='dependencies',delay=0))
        self.assertEqual(version['snapshots'][0]['probes']['main']['action']['label'],'answer:ship')
        self.assertEqual(dep['snapshots'][0]['probes']['main']['action']['label'],'answer:hold')
        f=self.family('exception-expiry')
        dep=study.episode(f,self.job(family=f['id'],policy='dependencies',delay=0))
        self.assertEqual(dep['snapshots'][2]['probes']['main']['action']['label'],'answer:blue')
        self.assertGreaterEqual(dep['recomputations'],2)

    def test_history_retention_and_deletion_not_privacy_claim(self):
        a=study.episode(self.family(),self.job(delay=0))
        b=study.episode(self.family(),self.job(delay=0,retention='delete'))
        self.assertTrue(a['snapshots'][0]['probes']['historical_old']['score']['correct'])
        self.assertFalse(b['snapshots'][0]['probes']['historical_old']['score']['correct'])
        self.assertTrue(a['snapshots'][0]['after']['store']['tombstones'])
        self.assertNotIn('base',[e['id'] for e in b['snapshots'][0]['after']['store']['events']])

    def test_writes_are_main_only_and_probe_readonly(self):
        ep=study.episode(self.family(),self.job())
        self.assertEqual(len(ep['snapshots'][-1]['after']['writes']),10)
        for s in ep['snapshots']:
            self.assertEqual(s['write']['action_identity'],data.identity(s['probes']['main']['action']))
        focused=study.focused_contrast(); yes=focused['with_writeback']; no=focused['without_writeback']
        self.assertTrue(yes['snapshots'][1]['probes']['main']['score']['correct'])
        self.assertFalse(yes['snapshots'][4]['probes']['main']['score']['correct'])
        self.assertTrue(no['snapshots'][4]['probes']['main']['score']['correct'])
        self.assertEqual(no['snapshots'][-1]['after']['writes'],[])

    def test_reappearance_requires_old_binding_and_same_expected_phase(self):
        f=self.family(); yes=study.focused_contrast()['with_writeback']
        self.assertTrue(study.recurrence_metrics(yes,f)['old_influence_reappearance'])
        other=copy.deepcopy(yes)
        for s in other['snapshots'][2:]:
            p=s['probes']['main']
            if not p['score']['correct']:
                p['action']['label']='answer:new-unrelated-error'
                p['delivery']['records'][-1]['support']=['unrelated-new-source']
                p['delivery']['records'][-1]['source_identity']='new-source-version'
        metrics=study.recurrence_metrics(other,f)
        self.assertTrue(metrics['any_error_after_repair'])
        self.assertFalse(metrics['old_influence_reappearance'])
        f=self.family('exception-expiry'); ep=study.episode(f,self.job(family=f['id'],delay=0))
        # Wrong, then repaired in the red phase; later red is stale only after expiry.
        ep['snapshots'][0]['probes']['main']['action']['label']='answer:unrelated'
        self.assertFalse(study.recurrence_metrics(ep,f)['old_influence_reappearance'])

    def test_oracle_boundaries_and_negative_control(self):
        for b in ('oracle-retrieval','oracle-context'):
            ep=study.episode(self.family(),self.job(branch=b,delay=3))
            self.assertTrue(all(s['probes']['main']['score']['correct'] for s in ep['snapshots']))
            if b=='oracle-context': self.assertIn('oracle_extra_information',ep['snapshots'][0]['probes']['main']['delivery'])
        f=self.family('stable')
        for p in study.POLICIES:
            ep=study.episode(f,self.job(family=f['id'],policy=p))
            self.assertTrue(all(s['probes']['main']['score']['correct'] for s in ep['snapshots']))

    def test_complete_roundtrip_corruption_and_foreign_config(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)/'run'; first=study.execute(root,self.small())
            self.assertEqual(first,study.verify(root))
            study.freeze(root/'report.json',first)
            self.assertEqual(study.load(root/'report.json'),study.verify(root))
            with self.assertRaisesRegex(ValueError,'empty/new'): study.execute(root,self.small())
            m=study.load(root/'manifest.json'); m['scorer']='wrong'; (root/'manifest.json').write_text(data.canonical(m))
            with self.assertRaisesRegex(ValueError,'identity'): study.verify(root)
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)/'run'; study.execute(root,self.small())
            p=next(root.glob('episodes/*/episode.json')); p.write_text('corrupt')
            with self.assertRaisesRegex(ValueError,'corrupt'): study.verify(root)

    def test_saved_summary_rejects_missing_bucket_and_illegal_score(self):
        saved=study.load(study.ROOT/'results.json')
        for mutation in ('missing-bucket','illegal-correct'):
            changed=copy.deepcopy(saved)
            key=next(iter(changed['results']))
            if mutation=='missing-bucket': del changed['results'][key]
            else: changed['results'][key]['checkpoints']['1']['correct']=999999
            with self.subTest(mutation=mutation),patch.object(study,'load',return_value=changed):
                with self.assertRaises(ValueError): study.check_saved()
        self.assertEqual(study.check_saved()['families'],9)

    def test_rejects_unsupported_configuration(self):
        c=self.small(); c['tasks']=9
        with self.assertRaises(ValueError): study.jobs(c)
        c=self.small(); c['delays']=[2]
        with self.assertRaises(ValueError): study.jobs(c)

    def test_partial_interrupted_episode_preserved(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)/'run'; original=study.freeze
            def interrupt(path,value):
                if path.name=='receipt.json': raise KeyboardInterrupt()
                original(path,value)
            with patch.object(study,'freeze',side_effect=interrupt):
                with self.assertRaises(KeyboardInterrupt): study.execute(root,self.small())
            episode=next(root.glob('episodes/*/episode.json')); raw=episode.read_bytes()
            with self.assertRaisesRegex(ValueError,'partial'): study.verify(root)
            with self.assertRaisesRegex(ValueError,'empty/new'): study.execute(root,self.small())
            self.assertEqual(episode.read_bytes(),raw)


if __name__=='__main__': unittest.main()
