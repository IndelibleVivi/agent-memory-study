import json
from pathlib import Path
import subprocess
import unittest
from services.local.test_arguments import P6Base
from services.local.records import record,command,ref,revise
from services.local.revisions import RevisionService

class RevisionTests(P6Base):
    def setUp(self):super().setUp();self.service=RevisionService(self.repo,Path(self.temp.name)/'public')
    def thread(self):return self.save(record('thread',{'title':'研究','byline':'AMS tests','status':'open','payload':{'note':'旧理解'}}))
    def accepted(self,items):
        c=self.service.create(items)
        for i in items:c=self.service.review(c['id'],i['id'],'accepted','已审查依据与范围',expected_revision=c['revision'])
        return c
    def test_batch_review_not_accept_all_and_pause_preserves(self):
        t=self.thread();c=self.service.create([{'id':'a','target':'private-thread','base_ref':ref(t),'change':'改写'},{'id':'b','target':'private-thread','base_ref':ref(t),'change':'另一项'}])
        c=self.service.review(c['id'],'a','accepted','只接受a',expected_revision=c['revision'])
        self.assertEqual(c['review_state'],'reviewing');self.assertEqual(c['items'][1]['review_state'],'proposed')
        paused=self.service.pause(c['id'],expected_revision=c['revision']);self.assertEqual(paused['items'][0]['review_state'],'accepted')
    def test_git_unit_real_bytes_receipt_and_conflict_preserve(self):
        from services.local.revisions import git
        project=self.service.project;project.mkdir();(project/'study/entries').mkdir(parents=True)
        path=project/'study/entries/test.md';path.write_text('old\n')
        git(project,'init','-b','main');git(project,'config','user.name','AMS Synthetic');git(project,'config','user.email','test@example.invalid');git(project,'add','.');git(project,'commit','-m','synthetic base')
        base=git(project,'rev-parse','HEAD')
        e=self.save(record('entry',{'entry_type':'research-essay','title':'bounded','byline':'AMS tests','date':'2026-10-29','intro':'synthetic','body_file':'entries/test.md','payload':{'body':'old'}}))
        c=self.accepted([{'id':'public','target':'public-corpus','base_ref':ref(e),'change':'New bounded wording'}])
        unit=self.service.prepare_git(c['id'],['public'],{'study/entries/test.md':'new\n'},base_commit=base,expected_revision=c['revision'],idempotency_key='git-unit')
        self.assertEqual(path.read_text(),'old\n')
        path.write_text('new\n');git(project,'add','study/entries/test.md');git(project,'commit','-m','synthetic reviewed patch');commit=git(project,'rev-parse','HEAD')
        updated=revise(e,payload={'body':'new'});self.repo.apply(command(updated,previous=e))
        result=self.service.record_git_unit(unit['id'],{'state':'applied','base_commit':base,'commit':commit,'result_refs':{'public':ref(updated)}})
        self.assertEqual(result['state'],'applied');self.assertEqual(self.repo.load('changeset',c['id'])['items'][0]['result_ref'],ref(updated))
        with self.assertRaises(ValueError):self.service.record_git_unit(unit['id'],{'state':'conflict','base_commit':base})

    def test_atomic_database_apply_retry_and_excerpt_preservation(self):
        t=self.thread();other=self.thread()
        c=self.accepted([{'id':'a','target':'private-thread','base_ref':ref(t),'change':{'mode':'replace-fields','fields':{'payload':{'note':'新解释'}}}},{'id':'b','target':'private-thread','base_ref':ref(other),'change':{'mode':'replace-fields','fields':{'payload':{'note':'第二项'}}}}])
        result=self.service.apply_db(c['id'],['a','b'],expected_revision=c['revision'],idempotency_key='unit')
        self.assertEqual(result,self.service.apply_db(c['id'],['a','b'],expected_revision=c['revision'],idempotency_key='unit'))
        self.assertEqual(self.repo.load('thread',t['id'])['payload']['note'],'新解释')
        self.assertEqual(self.repo.load('thread',t['id'],t['revision'])['payload']['note'],'旧理解')
    def test_stale_base_does_not_partially_apply(self):
        t,o=self.thread(),self.thread()
        c=self.accepted([{'id':i,'target':'private-thread','base_ref':ref(v),'change':{'mode':'replace-fields','fields':{'title':'changed'}}} for i,v in [('a',t),('b',o)]])
        moved=revise(o,title='concurrent');self.repo.apply(command(moved,previous=o))
        r=self.service.apply_db(c['id'],['a','b'],expected_revision=c['revision'],idempotency_key='conflict')
        self.assertEqual(r['state'],'conflict');self.assertEqual(self.repo.load('thread',t['id'])['revision'],t['revision']);self.assertEqual(self.repo.load('thread',o['id'])['title'],'concurrent')
    def test_p0_already_corrected_checked_unchanged_no_new_target(self):
        root=Path(__file__).resolve().parents[2];current=(root/'research/representation-use-study/README.md').read_text()
        self.assertIn('离线控制已实现',current);self.assertIn('自然语言比较',current)
        t=self.save(record('thread',{'title':'P0 scope already reconciled','byline':'AMS tests','status':'open','payload':{'note':'scripted/oracle已执行；自然语言provider尚未执行'}}))
        c=self.accepted([{'id':'p0','target':'private-thread','base_ref':ref(t),'change':{'mode':'no-change','reason':'scripted/oracle已执行，provider未执行，当前措辞已准确'}}])
        r=self.service.apply_db(c['id'],['p0'],expected_revision=c['revision'],idempotency_key='no-change')
        self.assertEqual(r['state'],'checked-unchanged');self.assertEqual(self.repo.load('thread',t['id'])['revision'],t['revision']);self.assertFalse(r['applied_refs'])
    def test_old_excerpt_basis_cannot_be_rebound(self):
        t=self.thread();o=self.thread();raw=b'original excerpt bytes';self.repo.put_blob(raw)
        import hashlib
        digest='sha256:'+hashlib.sha256(raw).hexdigest()
        from services.local.repository import now
        a=self.save(record('artifact',{'media_type':'text/plain','byte_length':len(raw),'artifact_digest':digest,'storage':{'kind':'blob','locator':digest},'role':'authored','visibility':'private','obtained_at':now(),'representation_of':ref(t)}))
        excerpt=self.save(record('excerpt',{'target_ref':ref(t),'representation_ref':ref(a),'selector':'original excerpt','comment':'private'}))
        c=self.accepted([{'id':'excerpt','target':'private-thread','base_ref':ref(excerpt),'change':{'mode':'replace-fields','fields':{'target_ref':ref(o)}}}])
        with self.assertRaisesRegex(ValueError,'basis'):self.service.apply_db(c['id'],['excerpt'],expected_revision=c['revision'],idempotency_key='forbid-rebind')
        self.assertEqual(self.repo.load('excerpt',excerpt['id'])['target_ref'],ref(t))

    def test_c2c_readonly_analysis_scoped_private_revision(self):
        root=Path(__file__).resolve().parents[2]
        source=root/'research/c2c-cache-retraction-study/execution-history.json';original=source.read_bytes();history=json.loads(original)
        self.assertFalse(history['reviewed_float32']['summary']['causal_query_controls_pass'])
        note='保存C2C分布依赖不等于事实恢复；原float32控制失败仍保留，未重新推理'
        t=self.thread();c=self.accepted([{'id':'c2c','target':'private-thread','base_ref':ref(t),'change':{'mode':'replace-fields','fields':{'payload':{'note':note,'basis':'research/c2c-cache-retraction-study/execution-history.json'}}}}])
        self.service.apply_db(c['id'],['c2c'],expected_revision=c['revision'],idempotency_key='c2c')
        self.assertIn('不等于',self.repo.load('thread',t['id'])['payload']['note']);self.assertEqual(source.read_bytes(),original)

    def test_delegated_review_apply_and_typed_saved_receipt(self):
        t=self.thread();c=self.service.create([{'id':'d','target':'private-thread','base_ref':ref(t),'change':{'mode':'replace-fields','fields':{'title':'delegated bounded revision'}}}])
        grant=self.save(record('thread',{'title':'Host-authorized bounded delegation','byline':'AMS tests','status':'open','payload':{'changeset_id':c['id'],'operations':['revision.review','revision.apply']}}));agent={'kind':'agent','id':'actor:bounded-review'}
        def trusted(actor,operation,target,requested):
            if actor!=agent or operation not in ('revision.review','revision.apply') or target['id']!=c['id'] or requested!=ref(grant):raise ValueError('outside scoped grant')
            return ref(grant)
        service=RevisionService(self.repo,self.service.project,review_authorizer=trusted)
        reviewed=service.review(c['id'],'d','accepted','delegated review',expected_revision=c['revision'],actor=agent,delegation_ref=ref(grant),idempotency_key='delegated-review')
        self.assertEqual(reviewed,service.review(c['id'],'d','accepted','delegated review',expected_revision=c['revision'],actor=agent,delegation_ref=ref(grant),idempotency_key='delegated-review'))
        result=service.apply_db(c['id'],['d'],expected_revision=reviewed['revision'],idempotency_key='delegated-apply',actor=agent,delegation_ref=ref(grant))
        self.assertEqual(result['authorization']['delegation_ref'],ref(grant));self.assertEqual(self.repo.load('thread',t['id'])['title'],'delegated bounded revision')
        with self.repo.transaction():self.repo.db.execute('UPDATE revision_units SET receipt=? WHERE id=?',(json.dumps({**result,'unknown_field':True}),result['id']))
        with self.assertRaises(ValueError):service.units(c['id'])
    def test_equal_replace_fields_is_checked_unchanged_without_target_revision(self):
        t=self.thread();c=self.accepted([{'id':'equal','target':'private-thread','base_ref':ref(t),'change':{'mode':'replace-fields','fields':{'title':t['title']}}}])
        r=self.service.apply_db(c['id'],['equal'],expected_revision=c['revision'],idempotency_key='equal-fields')
        self.assertEqual(r['state'],'checked-unchanged');self.assertEqual(self.repo.load('thread',t['id'])['revision'],t['revision'])

    def test_git_plan_ack_recovery_after_nochange_owner_result(self):
        from services.local.revisions import git
        project=self.service.project;project.mkdir();git(project,'init','-b','main');git(project,'config','user.name','AMS test');git(project,'config','user.email','synthetic@example.invalid');(project/'seed').write_text('original');git(project,'add','seed');git(project,'commit','-m','synthetic baseline');base=git(project,'rev-parse','HEAD')
        t=self.thread();c=self.accepted([{'id':'unchanged','target':'public-corpus','base_ref':ref(t),'change':{'mode':'no-change','reason':'exact selected scope already correct'}}])
        arguments=dict(base_commit=base,expected_revision=c['revision'],idempotency_key='same-plan')
        unit=self.service.prepare_git(c['id'],['unchanged'],{},**arguments)
        recorded=self.service.record_git_unit(unit['id'],{'base_commit':base,'state':'checked-unchanged'})
        again=self.service.prepare_git(c['id'],['unchanged'],{},**arguments)
        self.assertEqual(again['id'],unit['id']);self.assertEqual(again['receipt'],recorded['receipt']);self.assertEqual(git(project,'rev-parse','HEAD'),base)

if __name__=='__main__':unittest.main()
