import copy
import unittest
from services.local.test_intake import P4Base
from services.local.connectors import ZoteroConnector,GitHubConnector,record_observation

class ConnectorTests(P4Base):
    def zotero(self):return {'headers':{'Last-Modified-Version':'41'},'data':[{'key':'TEST0001','version':9,'data':{'itemType':'journalArticle','title':'Synthetic record','DOI':'10.1234/example','url':'https://example.org/paper','tags':[{'tag':'do not spread'}],'note':'private fixture note','path':'local synthetic path'}}]}
    def test_zotero_metadata_versions_and_no_private_fields(self):
        result=ZoteroConnector().decode(self.zotero(),['TEST0001']);self.assertEqual(result['library_record_version'],41);self.assertEqual(result['records'][0]['record_version'],9)
        self.assertEqual(result['records'][0]['content_revision'],'not-inferred-from-Zotero-version');self.assertNotIn('path',result['records'][0]);self.assertNotIn('note',result['records'][0]);self.assertFalse(result['writeback']);self.assertFalse(result['live_verified'])
    def test_zotero_selected_only_key_and_permission(self):
        z=self.zotero()
        with self.assertRaises(ValueError):ZoteroConnector().decode(z,['bibtexCitation2026'])
        z['data'][0]['data']['itemType']='attachment'
        with self.assertRaises(ValueError):ZoteroConnector().decode(z,['TEST0001'])
        self.assertEqual(ZoteroConnector().decode(z,['TEST0001'],attachments=True)['records'][0]['item_type'],'attachment')
        z['data'][0]['version']='not-actual-integer'
        with self.assertRaises(ValueError):ZoteroConnector().decode(z,['TEST0001'],attachments=True)
    def test_github_fixed_identity_commit_and_blob_range(self):
        repository={'id':12345,'full_name':'synthetic/repo'};commit={'sha':'a'*40,'files':[{'sha':'b'*40,'filename':'src/file.py','status':'modified','patch':'@@ selected excerpt'}]}
        r=GitHubConnector().decode(repository,commit,requested_ref='main',observed_at='2026-10-29T00:00:00Z')
        self.assertEqual(r['repository_identity'],'12345');self.assertEqual(r['requested_ref'],'main');self.assertEqual(r['files'][0]['blob_sha'],'b'*40)
        renamed=GitHubConnector().decode({**repository,'full_name':'renamed/repo'},commit,requested_ref='release',observed_at='2026-10-29T01:00:00Z');self.assertEqual(renamed['repository_identity'],r['repository_identity'])
        with self.assertRaises(ValueError):GitHubConnector().decode(repository,{'sha':'main'},requested_ref='main',observed_at='now')
    def test_selected_connector_capture_then_explicit_confirm(self):
        receipt=GitHubConnector().decode({'id':12345,'full_name':'synthetic/repo'},{'sha':'a'*40,'files':[]},requested_ref='main',observed_at='2026-10-29T00:00:00Z')
        saved=self.capture.capture_connector(receipt,idempotency_key='connector-capture')
        c=self.repo.load('capture',saved[0]['capture_ref']['id'])
        self.assertFalse(saved[0]['identity_accepted']);self.assertEqual(self.repo.list('source_work'),[])
        confirmed=self.identity.confirm(c['id'],title='Selected recorded repository',expected_revision=c['revision'],idempotency_key='explicit-confirm')
        work=self.repo.load('source_work',confirmed['work_ref']['id']);self.assertIn('12345',[i['value'] for i in work['identifiers']])
        self.assertEqual(self.capture.get(c['id'])['details']['connector_metadata']['requested_ref'],'main')

    def test_observation_cursor_receipt_is_durable_idempotent(self):
        r=ZoteroConnector().decode(self.zotero(),['TEST0001'])
        self.assertEqual(record_observation(self.repo,'zotero',['TEST0001'],r,idempotency_key='obs'),r)
        self.assertEqual(record_observation(self.repo,'zotero',['TEST0001'],r,idempotency_key='obs'),r)
        with self.assertRaises(ValueError):record_observation(self.repo,'zotero',['OTHER001'],r,idempotency_key='obs')

if __name__=='__main__':unittest.main()
