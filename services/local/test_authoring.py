import base64
import json
from pathlib import Path
import subprocess
import unittest
from services.local.test_arguments import P6Base
from services.local.authoring import ReviewAuthoringService
from services.local.records import record,command,ref,revise
from services.local.revisions import git
from schemas.validate import check_structure

class AuthoringTests(P6Base):
    def setUp(self):
        super().setUp();self.project=Path(self.temp.name)/'synthetic';self.project.mkdir()
        git(self.project,'init','-b','main');git(self.project,'config','user.name','AMS synthetic');git(self.project,'config','user.email','test@example.invalid')
        (self.project/'seed.txt').write_text('synthetic baseline');git(self.project,'add','seed.txt');git(self.project,'commit','-m','synthetic baseline')
        self.base=git(self.project,'rev-parse','HEAD');self.service=ReviewAuthoringService(self.repo,self.project)
    def manuscript(self):return self.service.create(title='Bounded original note',body='Original public-safe authored text.',byline='AMS synthetic',intro='Limited synthetic statement.',idempotency_key='create')['record']
    def accept_apply(self,proposed):
        c=proposed['changeset'];c=self.service.revisions.review(c['id'],'review','accepted','Explicit bounded review',expected_revision=c['revision'],idempotency_key='accept')
        r=self.service.revisions.apply_db(c['id'],['review'],expected_revision=c['revision'],idempotency_key='apply');return c,r
    def test_lightweight_manuscript_create_edit_reopen_and_ack_reuse(self):
        entry=self.manuscript();self.assertEqual(self.repo.list('claim_revision'),[])
        draft=self.service.propose(base_ref=ref(entry),decision='rewrite',body='Revised scope, no model inference.',explanation='Narrow to actually observed controls.',open_question='What would a new contrast distinguish?',idempotency_key='proposal')
        self.assertEqual(draft,self.service.propose(base_ref=ref(entry),decision='rewrite',body='Revised scope, no model inference.',explanation='Narrow to actually observed controls.',open_question='What would a new contrast distinguish?',idempotency_key='proposal'))
        c,r=self.accept_apply(draft);self.assertEqual(self.service.open(r['applied_refs'][0])['body'],'Revised scope, no model inference.')
        check_structure(r,'OperationalApplyReceipt')
        row=self.repo.db.execute('SELECT payload FROM revision_units WHERE id=?',(r['id'],)).fetchone();check_structure(json.loads(row[0]),'OperationalApplyUnit')
        self.assertEqual(self.service.open(ref(entry))['body'],'Original public-safe authored text.')
    def test_catalogue_retains_explicit_old_basis_and_new_manuscript_lineage(self):
        entry=self.manuscript();moved=revise(entry,payload={**entry['payload'],'bodyMarkdown':'New current scope'});self.repo.apply(command(moved,previous=entry))
        source=self.service.create(title='Based on old exact wording',body='Bounded private interpretation',byline='AMS tests',intro='Original synthetic text',basis_ref=ref(entry),idempotency_key='old-basis')['record']
        options=[r['ref'] for r in self.service.catalogue()['records']]
        self.assertIn(ref(entry),options);self.assertIn(ref(moved),options);self.assertEqual(source['payload']['source_basis_ref'],ref(entry));self.assertEqual(self.service.open(ref(entry))['body'],'Original public-safe authored text.')
    def test_analysis_basis_displays_actual_result_without_inventing_run(self):
        raw=b'original synthetic saved receipt';digest=self.repo.put_blob(raw)
        artifact=self.save(record('artifact',{'media_type':'text/plain','byte_length':len(raw),'artifact_digest':digest,'storage':{'kind':'blob','locator':digest},'role':'receipt','visibility':'private','obtained_at':'2026-10-30T00:00:00Z'}))
        observation=self.save(record('observation',{'scope':'historical control only','statement':'retained failure','basis_refs':[ref(artifact)]}))
        analysis=self.save(record('analysis',{'run_refs':[],'observation_refs':[ref(observation)],'method':'Explicit authored inspection','scope':'historical only','result':'Failure retained; missing raw is not reconstructed.'}))
        opened=self.service.open(ref(analysis));self.assertEqual(opened['body'],analysis['result']);self.assertEqual(opened['scope'],analysis['scope']);self.assertEqual(self.repo.list('run'),[])
    def test_public_fixed_ref_order_and_checked_unchanged_no_rewrite(self):
        entry=record('entry',{'entry_type':'research-essay','title':'Current P0 scope','byline':'AMS tests','date':'2026-10-29','intro':'scope already corrected','body_file':'study/entries/p0.md','payload':{'bodyMarkdown':'Scripted/oracle controls executed; provider natural-language comparison not executed.'},'references':[]})
        service=ReviewAuthoringService(self.repo,self.project,[entry]);pointer={'revision':entry['revision'],'id':entry['id'],'kind':'entry'}
        self.assertTrue(service.open(pointer)['public']);proposal=service.propose(base_ref=pointer,decision='maintain',explanation='Current public wording already matches the actual scope.',idempotency_key='maintain')
        c=service.revisions.review(proposal['changeset']['id'],'review','accepted','checked current explicit scope',expected_revision=proposal['changeset']['revision']);result=service.revisions.apply_db(c['id'],['review'],expected_revision=c['revision'],idempotency_key='unchanged')
        self.assertEqual(result['state'],'checked-unchanged');self.assertEqual(result['applied_refs'],[]);self.assertEqual(self.repo.list('entry'),[])
    def test_public_rewrite_is_private_copy_and_conflict_preserves_two_texts(self):
        entry=self.manuscript();draft=self.service.propose(base_ref=ref(entry),decision='rewrite',body='Proposed interpretation A',explanation='fixed interpretation review',idempotency_key='propose')
        moved=revise(entry,payload={**entry['payload'],'bodyMarkdown':'Concurrent interpretation B'});self.repo.apply(command(moved,previous=entry))
        c,r=self.accept_apply(draft);self.assertEqual(r['state'],'conflict');self.assertEqual(self.service.open(ref(moved))['body'],'Concurrent interpretation B')
        self.assertEqual(self.repo.load('changeset',c['id'])['items'][0]['change']['fields']['payload']['bodyMarkdown'],'Proposed interpretation A')
    def test_publication_selection_atomic_ack_recovery_portable_paths_and_real_patch(self):
        entry=self.manuscript();rights={'basis':'own original synthetic work','license_or_permission':'explicit test permission','attribution':'AMS synthetic'}
        updated=revise(entry,payload={**entry['payload'],'public_metadata':{'boundary':'bounded original work','private_note':'never export this private field'}});self.repo.apply(command(updated,previous=entry));entry=updated
        result=self.service.publication_plan(entry_ref=ref(entry),public_id='bounded-note',base_commit=self.base,rights=rights,idempotency_key='publication')
        same=self.service.publication_plan(entry_ref=ref(entry),public_id='bounded-note',base_commit=self.base,rights=rights,idempotency_key='publication');self.assertEqual(result,same);self.assertEqual(len(self.repo.list('publication_manifest')),1)
        preview=result['preview'];self.assertEqual({f['path'] for f in preview['files']},{'study/entries/bounded-note.md','study/entries/bounded-note.json'})
        metadata=json.loads(base64.b64decode(next(f for f in preview['files'] if f['path'].endswith('.json'))['content_base64']));self.assertNotIn('private_note',metadata);self.assertEqual(metadata['boundary'],'bounded original work')
        patch=self.service.patch(ref(result['manifest']));p=self.project/'review.patch';p.write_text(patch['patch'])
        subprocess.run(['git','apply','--check',str(p)],cwd=self.project,check=True,capture_output=True)
        self.assertFalse((self.project/'study/entries/bounded-note.md').exists());self.assertNotIn(result['manifest']['id'],json.dumps(self.service.publication.public_projection(ref(result['manifest']))))
    def test_bad_rights_rolls_back_all_release_records(self):
        entry=self.manuscript();count=len(self.repo.list())
        with self.assertRaises(ValueError):self.service.publication_plan(entry_ref=ref(entry),public_id='bounded-note',base_commit=self.base,rights={},idempotency_key='bad')
        self.assertEqual(len(self.repo.list()),count);self.assertEqual(self.repo.list('publication_manifest'),[])
    def test_publication_links_exact_applied_changeset_without_rewriting_unit_history(self):
        entry=self.manuscript();draft=self.service.propose(base_ref=ref(entry),decision='rewrite',body='Selected bounded revision.',explanation='Explicit reviewed update.',idempotency_key='linked-proposal')
        accepted,receipt=self.accept_apply(draft);applied=self.repo.load('changeset',accepted['id']);units=self.service.revisions.units(applied['id'])
        rights={'basis':'original synthetic work','license_or_permission':'explicit test permission','attribution':'AMS tests'}
        result=self.service.publication_plan(entry_ref=receipt['applied_refs'][0],public_id='linked-note',base_commit=self.base,rights=rights,idempotency_key='linked-publication')
        current=self.repo.load('changeset',applied['id']);self.assertEqual(current['publication_refs'],[ref(result['manifest'])]);self.assertNotEqual(current['revision'],applied['revision'])
        self.assertEqual(self.repo.load('changeset',applied['id'],applied['revision'])['publication_refs'],[])
        self.assertEqual(self.service.revisions.units(applied['id']),units)
        release_ref=result['manifest']['selected_refs'][0];release=self.repo.load('entry',release_ref['id'],release_ref['revision'])
        self.assertEqual(release['payload']['release_of'],receipt['applied_refs'][0])
    def test_c2c_interpretation_revision_preserves_historical_raw_boundary(self):
        history=json.loads((Path(__file__).resolve().parents[2]/'research/c2c-cache-retraction-study/execution-history.json').read_text());self.assertFalse(history['reviewed_float32']['summary']['causal_query_controls_pass'])
        entry=self.manuscript();p=self.service.propose(base_ref=ref(entry),decision='rewrite',body='The float32 control failed at the retained threshold. Missing early tensors remain unavailable. Distribution dependence does not establish factual recovery.',scope='saved single-model numerical control only; no new inference',explanation='Keep failed controls and precision amendment separate.',open_question='Would a new independently authorized run change the bounded inference?',idempotency_key='c2c')
        _,r=self.accept_apply(p);self.assertIn('Missing early tensors',self.service.open(r['applied_refs'][0])['body']);self.assertEqual(self.repo.list('run'),[])

    def test_binary_attachment_patch_is_applyable_without_private_paths(self):
        from services.local.repository import now
        entry=self.manuscript();raw=b'\x00\xffOriginal binary fixture\x00';digest=self.repo.put_blob(raw)
        a=self.save(record('artifact',{'media_type':'application/octet-stream','byte_length':len(raw),'artifact_digest':digest,'storage':{'kind':'blob','locator':digest},'role':'other','visibility':'public-candidate','obtained_at':now()}))
        rights={'basis':'original synthetic bytes','license_or_permission':'explicit test permission','attribution':'AMS tests'}
        result=self.service.publication_plan(entry_ref=ref(entry),public_id='binary-note',base_commit=self.base,rights=rights,attachments=[{'artifact_ref':ref(a),'public_path':'research/selected/binary.bin','rights':rights}],idempotency_key='binary')
        patch=self.service.patch(ref(result['manifest']))['patch'];self.assertIn('GIT binary patch',patch);self.assertNotIn(str(self.temp.name),patch)
        file=self.project/'selected.patch';file.write_text(patch);subprocess.run(['git','apply',str(file)],cwd=self.project,check=True,capture_output=True)
        self.assertEqual((self.project/'research/selected/binary.bin').read_bytes(),raw)
    def test_public_copy_and_paused_text_remain_separate_from_published_snapshot(self):
        entry=record('entry',{'entry_type':'learning-note','title':'Public fixed snapshot','byline':'AMS tests','date':'2026-10-29','intro':'bounded','body_file':'study/entries/public.md','payload':{'bodyMarkdown':'Original fixed public wording','id':'public'},'references':[]})
        service=ReviewAuthoringService(self.repo,self.project,[entry]);p=service.propose(base_ref=ref(entry),decision='defer',body='Private unfinished alternative',explanation='No decision yet',open_question='Need another contrast',idempotency_key='defer')
        self.assertNotEqual(p['working_ref']['id'],entry['id']);self.assertEqual(p['changeset']['items'][0]['change']['fields']['payload']['bodyMarkdown'],'Private unfinished alternative')
        paused=service.revisions.review(p['changeset']['id'],'review','paused','Preserve unresolved text',expected_revision=p['changeset']['revision'])
        self.assertEqual(paused['items'][0]['review_state'],'paused');self.assertEqual(service.open(ref(entry))['body'],'Original fixed public wording')

if __name__=='__main__':unittest.main()
