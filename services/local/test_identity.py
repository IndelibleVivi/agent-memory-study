import unittest
from services.local.test_intake import P4Base
from services.local.identity import parse_identifier
from services.local.records import ref,command,revise

class IdentityTests(P4Base):
    def test_strict_namespace_and_query_preservation(self):
        doi=parse_identifier('https://DOI.org/10.1234/ABC?mode=raw&version=2#section')
        self.assertIn({'namespace':'doi','value':'10.1234/abc'},doi['identifiers']);self.assertIn('?mode=raw&version=2#section',doi['locator'])
        arxiv=parse_identifier('https://arxiv.org/pdf/2607.12345v3.pdf?download=1')
        self.assertEqual(arxiv['publisher_version'],'2607.12345v3');self.assertEqual(arxiv['identifiers'][-1]['value'],'2607.12345')
        sha='a'*40;git=parse_identifier('https://github.com/org/repo/commit/'+sha+'?diff=split')
        self.assertEqual(git['publisher_version'],sha);self.assertEqual(parse_identifier('https://github.com/org/repo/tree/main')['publisher_version'],None)
        self.assertFalse(parse_identifier('not a DOI 10.12/foo')['identifiers'])
        with self.assertRaises(ValueError):parse_identifier('https://user:secret@example.org/')
    def test_doi_ambiguity_merge_and_split_preserve_history(self):
        c,a=self.confirmed('10.1234/example','a');other=self.saved('10.1234/example','b');b=self.identity.confirm(other['id'],title='Distinct synthetic work explicitly retained',expected_revision=other['revision'],new_work=True,idempotency_key='b:confirm')
        resolution=self.identity.resolve(c['id']);self.assertEqual(resolution['state'],'conflicted');self.assertEqual(len(resolution['candidates']),2)
        old=self.repo.load('source_work',a['work_ref']['id'],a['work_ref']['revision'])
        self.identity.merge([a['work_ref'],b['work_ref']],a['work_ref'],reason='explicit same work decision',idempotency_key='merge')
        self.assertEqual(len(self.identity.resolve(c['id'])['candidates']),1)
        self.identity.split([a['work_ref'],b['work_ref']],reason='new evidence distinguishes them',idempotency_key='split')
        self.assertEqual(self.identity.resolve(c['id'])['state'],'conflicted')
        self.assertEqual(self.repo.load('source_work',a['work_ref']['id'],a['work_ref']['revision']),old)
    def test_v2_v3_old_version_and_metadata_only(self):
        c,a=self.confirmed();c3=self.saved('arxiv:2607.12345v3','v3')
        b=self.identity.confirm(c3['id'],title='new metadata',work_ref=a['work_ref'],expected_revision=c3['revision'],idempotency_key='confirm-v3')
        self.assertNotEqual(a['source_revision_ref'],b['source_revision_ref'])
        self.assertEqual(self.repo.load('source_revision',a['work_ref']['id'],a['source_revision_ref']['revision'])['identity']['value'],'2607.12345v2')
        c2=self.saved('arxiv:2607.12345v2','v2again')
        again=self.identity.confirm(c2['id'],title='metadata update only',work_ref=a['work_ref'],expected_revision=c2['revision'],idempotency_key='v2again-confirm')
        self.assertEqual(again['source_revision_ref'],a['source_revision_ref'])
    def test_git_requires_repository_identity_and_fixed_commit(self):
        c=self.saved('https://github.com/org/repo/commit/'+'a'*40)
        with self.assertRaises(ValueError):self.identity.confirm(c['id'],title='repo',expected_revision=c['revision'],idempotency_key='without-id')
        d=self.identity.confirm(c['id'],title='repo',identifiers=[{'namespace':'github-repository','value':'12345'}],expected_revision=c['revision'],idempotency_key='with-id')
        self.assertEqual(self.repo.load('source_revision',d['work_ref']['id'])['identity']['namespace'],'git')
    def test_confirm_retry_no_new_work_and_unversioned_metadata(self):
        c,a=self.confirmed('https://example.org/paper?v=1')
        same=self.identity.confirm(c['id'],title='Original synthetic metadata',expected_revision=c['revision'],idempotency_key='capture:confirm');self.assertEqual(a,same)
        c2=self.saved('https://example.org/paper?v=1','again')
        b=self.identity.confirm(c2['id'],title='metadata-only',work_ref=a['work_ref'],expected_revision=c2['revision'],idempotency_key='metadata')
        self.assertEqual(a['source_revision_ref'],b['source_revision_ref'])
    def test_repeated_encounter_reuses_exact_work_without_losing_capture(self):
        first,a=self.confirmed('10.1234/same','first');second,b=self.confirmed('10.1234/same','second')
        self.assertNotEqual(first['id'],second['id']);self.assertEqual(a['work_ref'],b['work_ref']);self.assertEqual(a['source_revision_ref'],b['source_revision_ref'])
        self.assertEqual(len(self.repo.list('source_work')),1)

    def test_title_similarity_never_merges(self):
        c=self.saved('An uncertain conceptual title');self.assertEqual(self.identity.resolve(c['id'])['candidates'],[])
        with self.assertRaises(ValueError):self.identity.confirm(c['id'],title='title',publisher_version='main',expected_revision=c['revision'],idempotency_key='bad-version')
    def test_explicit_identifiers_and_editions_cannot_bypass_allowlist(self):
        c=self.saved('arxiv:2607.12345v2')
        for n,kwargs in enumerate(({'identifiers':[{'namespace':'doi','value':'not-a-doi'}]}, {'identifiers':[{'namespace':'semantic-title','value':'similar'}]}, {'publisher_version':'2607.99999v2'}, {'publisher_version':'2607.12345v0'}, {'publisher_version':{'mode':'publisher-version','namespace':'git','value':'main','source_locator':'selected','identity_basis':'manual'}}, {'publisher_version':{'mode':'observed-snapshot','snapshot_captured':True}})):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError):self.identity.confirm(c['id'],title='synthetic',expected_revision=c['revision'],idempotency_key=f'bad:{n}',**kwargs)
        self.assertEqual(self.repo.list('source_work'),[])

if __name__=='__main__':unittest.main()
