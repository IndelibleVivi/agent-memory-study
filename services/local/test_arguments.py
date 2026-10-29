from pathlib import Path
import tempfile
import os
import unittest
from schemas.validate import validate_command
from services.local.repository import Repository
from services.local.records import record,command,ref,ACTOR
from services.local.arguments import ArgumentService

PROJECT=Path(__file__).resolve().parents[2]
class P6Base(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=os.environ.get("AMS_P6_TEST_ROOT"));self.addCleanup(self.temp.cleanup)
        self.repo=Repository(Path(self.temp.name)/'data',PROJECT,validate_command);self.addCleanup(self.repo.close)
        self.args=ArgumentService(self.repo)
    def save(self,value):self.repo.apply(command(value));return value
    def claim(self,text='限定判断',scope='finite'):
        return self.save(record('claim_revision',{'title':text,'byline':'AMS synthetic tests','claim':text,'scope':scope,'scope_binding':scope,'payload':{}}))
    def proposal(self,p,c,scope='finite'):
        return self.args.propose({'from_ref':ref(p),'to_ref':ref(c),'relation':'supports','scope':scope,'scope_binding':scope,'locator':'synthetic:paragraph-1','rationale':'明确有限范围','generated_by':{'kind':'agent','id':'actor:test-agent'},'method_version':'test/1'})
    def relation(self,p,c):return self.args.accept(ref(self.proposal(p,c)),'已检查片段与量词')
    def bundle(self,conclusion,premises,relations):
        return self.args.bundle({'conclusion_ref':ref(conclusion),'scope':'finite','scope_binding':'finite','rationale':'共同理由','combination':'all-premises','premise_refs':[ref(p) for p in premises],'relation_refs':[ref(r) for r in relations],'independence':{'status':'not-assessed'}})

class ArgumentTests(P6Base):
    def test_proposal_not_formal_and_reject_preserves(self):
        p,c=self.claim('前提'),self.claim();proposal=self.proposal(p,c)
        self.assertEqual(self.args.impact(ref(p))['review_paths'],[])
        self.args.reject(ref(proposal),'范围不充分')
        with self.assertRaises(ValueError):self.args.accept(ref(proposal),'改为接受')
        self.assertEqual(self.repo.load('relation_proposal',proposal['id'])['status'],'proposal')
    def test_accept_idempotent_human_and_scope(self):
        p,c=self.claim('前提'),self.claim();proposal=self.proposal(p,c)
        with self.assertRaises(ValueError):self.args.accept(ref(proposal),'自动接受',{'kind':'agent','id':'actor:a'})
        a=self.args.accept(ref(proposal),'确认');self.assertEqual(a,self.args.accept(ref(proposal),'确认'))
        other=self.proposal(p,c,'different-task-and-time')
        with self.assertRaisesRegex(ValueError,'scope'):self.args.accept(ref(other),'文案相反不代表同一任务')
    def test_and_loss_does_not_assign_false(self):
        p,q,c=self.claim('p'),self.claim('q'),self.claim('c');r1,r2=self.relation(p,c),self.relation(q,c)
        b=self.bundle(c,[p,q],[r1,r2]);self.args.withdraw(ref(r1),'撤回此项依据')
        status=self.args.support_status(ref(b));self.assertEqual(status['basis_state'],'needs-review');self.assertEqual(status['claim_truth'],'not-assigned')
        self.assertEqual(self.repo.load('evidence_relation',r1['id'])['status'],'accepted')
    def test_or_alternative_remains_and_shared_upstream_visible(self):
        p,q,c=self.claim('p'),self.claim('q'),self.claim('c');r1,r2=self.relation(p,c),self.relation(q,c)
        b1,b2=self.bundle(c,[p],[r1]),self.bundle(c,[q],[r2])
        fields={'conclusion_ref':ref(c),'scope':'finite','scope_binding':'finite','rationale':'替代理由','combination':'alternative-warrants','warrant_refs':[ref(b1),ref(b2)],'independence':{'status':'not-assessed'}}
        either=self.args.bundle(fields);self.args.withdraw(ref(r1),'撤回p')
        self.assertEqual(self.args.support_status(ref(either))['basis_state'],'recorded-alternative-remains')
        b3=self.bundle(c,[q],[r2]);same=self.args.bundle({**fields,'warrant_refs':[ref(b2),ref(b3)]})
        status=self.args.support_status(ref(same));self.assertEqual(status['shared_recorded_upstream'],[ref(q)]);self.assertEqual(status['independence']['status'],'not-assessed')
    def test_independence_argument_required(self):
        c=self.claim();
        with self.assertRaises(ValueError):self.args.bundle({'conclusion_ref':ref(c),'scope':'finite','scope_binding':'finite','rationale':'理由','combination':'alternative-warrants','warrant_refs':[],'independence':{'status':'argued-independent'}})
    def test_navigation_and_render_change_do_not_create_impact(self):
        p,c=self.claim('p'),self.claim('c');unrelated=self.claim('same-domain')
        self.relation(p,c);impact=self.args.impact(ref(p))
        self.assertEqual([r['to_ref'] for r in impact['review_paths']],[ref(c)])
        self.assertNotIn(ref(unrelated),[r['to_ref'] for r in impact['review_paths']])
        self.assertEqual(self.args.impact(ref(unrelated))['review_paths'],[])

class DelegatedArgumentTests(P6Base):
    def test_host_bound_delegation_is_real_review_not_imported_authority(self):
        p,c=self.claim('premise'),self.claim('conclusion');proposal=self.proposal(p,c)
        grant=self.save(record('thread',{'title':'Explicit synthetic delegation','byline':'AMS tests','status':'open','payload':{'actor':'actor:review-agent','operation':'argument.accept','target_ref':ref(proposal)}}))
        agent={'kind':'agent','id':'actor:review-agent'}
        with self.assertRaises(ValueError):self.args.accept(ref(proposal),'self-issued grant',agent,delegation_ref=ref(grant))
        def authorize(actor,operation,target,requested):
            if actor!=agent or operation!='argument.accept' or target!=ref(proposal) or requested!=ref(grant):raise ValueError('outside trusted bounded delegation')
            return ref(grant)
        delegated=ArgumentService(self.repo,review_authorizer=authorize)
        accepted=delegated.accept(ref(proposal),'bounded delegated review',agent,delegation_ref=ref(grant))
        self.assertEqual(accepted['review']['delegation_ref'],ref(grant));self.assertEqual(accepted,delegated.accept(ref(proposal),'bounded delegated review',agent,delegation_ref=ref(grant)))
        with self.assertRaises(ValueError):delegated.withdraw(ref(accepted),'not delegated',agent,delegation_ref=ref(grant))
    def test_transitive_shared_upstream_and_withdrawal_are_not_independence(self):
        source,p,q,c=self.claim('source'),self.claim('p'),self.claim('q'),self.claim('c')
        upstream=self.relation(source,p);self.relation(source,q)
        b1=self.bundle(c,[p],[self.relation(p,c)]);b2=self.bundle(c,[q],[self.relation(q,c)])
        either=self.args.bundle({'conclusion_ref':ref(c),'scope':'finite','scope_binding':'finite','rationale':'alternative explicitly recorded warrants','combination':'alternative-warrants','warrant_refs':[ref(b1),ref(b2)],'independence':{'status':'not-assessed'}})
        self.assertEqual(self.args.support_status(ref(either))['shared_recorded_upstream'],[ref(source)])
        self.args.withdraw(ref(upstream),'one upstream basis withdrawn')
        self.assertEqual(self.args.support_status(ref(b1))['basis_state'],'needs-review');self.assertEqual(self.args.support_status(ref(either))['basis_state'],'recorded-alternative-remains')

if __name__ == "__main__":
    unittest.main()
