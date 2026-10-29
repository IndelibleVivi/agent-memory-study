"""Reviewed ArgumentGraph over canonical immutable records; never a truth engine."""
from __future__ import annotations
import json
from schemas.validate import exact_ref, validate_entity, validate_graph, walk_exact_refs, check_structure
from .records import ACTOR, command, record, ref
from .repository import now, encoded

ARGUMENTS_MIGRATION_SQL=(
 'CREATE TABLE argument_decisions (proposal_revision TEXT PRIMARY KEY, decision TEXT NOT NULL, actor TEXT NOT NULL, rationale TEXT NOT NULL, decided_at TEXT NOT NULL, result_ref TEXT)',
 'CREATE TABLE argument_withdrawals (relation_revision TEXT PRIMARY KEY, actor TEXT NOT NULL, rationale TEXT NOT NULL, withdrawn_at TEXT NOT NULL)',
)

def human(actor):
    if not isinstance(actor,dict) or actor.get('kind')!='human':raise ValueError('explicit human review required by this acceptance profile')
    return actor

def authorization_identity(value):
    # Old private decision rows contained Actor only; new ones retain real Review.
    return {'actor':value.get('actor',value),'delegation_ref':value.get('delegation_ref')}

class ArgumentService:
    def __init__(self,repo,public_records=(),*,review_authorizer=None):
        self.repo=repo;self.public={exact_ref(ref(v)):v for v in public_records}
        self.review_authorizer=review_authorizer
        if self.public: repo.cache_public_records(list(self.public.values()))
    def authorize(self,actor,operation,target_ref,rationale,delegation_ref=None):
        if not isinstance(rationale,str) or not rationale.strip():raise ValueError('explicit review rationale required')
        check_structure(actor,'Actor');self.resolve(target_ref)
        review={'actor':actor,'at':now(),'rationale':rationale}
        if actor['kind']!='human' or delegation_ref is not None:
            if self.review_authorizer is None:raise ValueError('trusted host delegation required for this review actor')
            grant=self.review_authorizer(actor,operation,target_ref,delegation_ref)
            exact_ref(grant);self.resolve(grant)
            if delegation_ref is not None and grant!=delegation_ref:raise ValueError('host authorization returned a different delegation')
            review['delegation_ref']=grant
        check_structure(review,'Review');return review
    def resolve(self,r):
        key=exact_ref(r)
        try:return self.repo.load(*key[:2],revision=key[2])
        except ValueError:
            if key in self.public:return self.public[key]
            raise ValueError('unresolved exact reference') from None
    def _validate(self,value):
        validate_entity(value);available={exact_ref(ref(value)):value};queue=list(walk_exact_refs(value))
        while queue:
            r=queue.pop();key=exact_ref(r)
            if key in available:continue
            found=self.resolve(r);available[key]=found;queue.extend(walk_exact_refs(found))
        validate_graph([value],list(available.values()))
    def propose(self,fields,*,idempotency_key=None):
        def apply():
            proposal=record('relation_proposal',{**fields,'status':'proposal'})
            self._validate(proposal);self.repo._apply(command(proposal));return proposal
        if idempotency_key:
            from .intake import remember
            return remember(self.repo,idempotency_key,{'operation':'argument.propose','fields':fields},apply)
        with self.repo.transaction():return apply()
    def accept(self,proposal_ref,rationale,actor=ACTOR,*,delegation_ref=None):
        review=self.authorize(actor,'argument.accept',proposal_ref,rationale,delegation_ref)
        if not rationale.strip():raise ValueError('review rationale required')
        proposal=self.resolve(proposal_ref)
        if proposal['kind']!='relation_proposal':raise ValueError('expected proposal')
        conclusion=self.resolve(proposal['to_ref'])
        if proposal['relation'] in ('supports','derives') and conclusion['kind']=='claim_revision':
            if any(proposal[k]!=conclusion[k] for k in ('scope','scope_binding')):raise ValueError('support scope differs from fixed claim')
        with self.repo.transaction():
            old=self.repo.db.execute('SELECT * FROM argument_decisions WHERE proposal_revision=?',(proposal['revision'],)).fetchone()
            if old:
                if old['decision']!='accepted' or old['rationale']!=rationale or authorization_identity(json.loads(old['actor']))!=authorization_identity(review):raise ValueError('proposal already decided differently; create new proposal revision')
                return self.resolve(json.loads(old['result_ref']))
            fields={k:proposal[k] for k in ('from_ref','to_ref','relation','scope','scope_binding','locator','rationale')}
            accepted=record('evidence_relation',{**fields,'proposal_ref':ref(proposal),'review':review,'status':'accepted'})
            self._validate(accepted);self.repo._apply(command(accepted,actor=actor))
            self.repo.db.execute('INSERT INTO argument_decisions VALUES (?,?,?,?,?,?)',(proposal['revision'],'accepted',encoded(review),rationale,now(),encoded(ref(accepted))))
        return accepted
    def reject(self,proposal_ref,rationale,actor=ACTOR,*,delegation_ref=None):
        review=self.authorize(actor,'argument.reject',proposal_ref,rationale,delegation_ref);proposal=self.resolve(proposal_ref)
        if proposal['kind']!='relation_proposal' or not rationale.strip():raise ValueError('proposal and rejection rationale required')
        with self.repo.transaction():
            old=self.repo.db.execute('SELECT decision,rationale,actor FROM argument_decisions WHERE proposal_revision=?',(proposal['revision'],)).fetchone()
            if old:
                if old['decision']!='rejected' or old['rationale']!=rationale or authorization_identity(json.loads(old['actor']))!=authorization_identity(review):raise ValueError('proposal already decided differently')
            else:self.repo.db.execute('INSERT INTO argument_decisions VALUES (?,?,?,?,?,NULL)',(proposal['revision'],'rejected',encoded(review),rationale,now()))
        return {'proposal_ref':ref(proposal),'decision':'rejected','rationale':rationale,'authorization':review}
    def bundle(self,fields,actor=ACTOR,*,delegation_ref=None,idempotency_key=None):
        if idempotency_key:
            from .intake import remember
            return remember(self.repo,idempotency_key,{'operation':'argument.bundle','fields':fields,'actor':actor,**({'delegation_ref':delegation_ref} if delegation_ref else {})},lambda:self._bundle(fields,actor,delegation_ref=delegation_ref))
        with self.repo.transaction():return self._bundle(fields,actor,delegation_ref=delegation_ref)
    def _bundle(self,fields,actor=ACTOR,*,delegation_ref=None):
        review=self.authorize(actor,'argument.bundle',fields['conclusion_ref'],fields['rationale'],delegation_ref)
        fields={**fields,'review':review}
        conclusion=self.resolve(fields['conclusion_ref'])
        if conclusion['kind']!='claim_revision':raise ValueError('bundle conclusion must be fixed claim')
        if any(fields[k]!=conclusion[k] for k in ('scope','scope_binding')):raise ValueError('bundle scope differs from fixed claim')
        mode=fields['combination']
        if fields['independence']['status']=='argued-independent' and not fields['independence'].get('argument','').strip():raise ValueError('independence requires explicit argument')
        refs=fields.get('relation_refs',[]) if mode=='all-premises' else fields.get('warrant_refs',[])
        for r in refs:
            item=self.resolve(r)
            if any(item[k]!=fields[k] for k in ('scope','scope_binding')):raise ValueError('warrant/relation scope mismatch')
        value=record('support_bundle',fields);self._validate(value);self.repo._apply(command(value,actor=actor));return value
    def withdraw(self,relation_ref,rationale,actor=ACTOR,*,delegation_ref=None):
        review=self.authorize(actor,'argument.withdraw',relation_ref,rationale,delegation_ref);relation=self.resolve(relation_ref)
        if relation['kind']!='evidence_relation' or not rationale.strip():raise ValueError('fixed relation and reason required')
        with self.repo.transaction():
            old=self.repo.db.execute('SELECT actor,rationale FROM argument_withdrawals WHERE relation_revision=?',(relation['revision'],)).fetchone()
            if old and (authorization_identity(json.loads(old['actor']))!=authorization_identity(review) or old['rationale']!=rationale):raise ValueError('withdrawal already recorded differently')
            if not old:self.repo.db.execute('INSERT INTO argument_withdrawals VALUES (?,?,?,?)',(relation['revision'],encoded(review),rationale,now()))
        return {'relation_ref':relation_ref,'basis_state':'withdrawn','claim_truth':'not-assigned','authorization':review}
    def support_status(self,bundle_ref):
        b=self.resolve(bundle_ref)
        if b['kind']!='support_bundle':raise ValueError('expected support bundle')
        if b['combination']=='all-premises':
            with self.repo.lock:withdrawn={r[0] for r in self.repo.db.execute('SELECT relation_revision FROM argument_withdrawals')}
            relations=[r for r in self.repo.list('evidence_relation') if r['relation'] in ('supports','derives')]
            leaves={};upstream={};cycle=False
            def visit(pointer,path):
                nonlocal cycle
                key=exact_ref(pointer)
                if key in path:cycle=True;return
                incoming=[r for r in relations if r['to_ref']==pointer]
                if not incoming:leaves[key]=pointer
                for edge in incoming:
                    upstream[edge['revision']]=ref(edge);visit(edge['from_ref'],path|{key})
            for pointer in b['premise_refs']:visit(pointer,set())
            considered={r['revision']:r for r in [*b['relation_refs'],*upstream.values()]}
            affected=[r for revision,r in considered.items() if revision in withdrawn]
            return {'bundle_ref':bundle_ref,'basis_state':'needs-review' if affected or cycle else 'recorded-support','affected':affected,'claim_truth':'not-assigned','leaf_refs':list(leaves.values()),'recorded_upstream_cycle':cycle}
        alternatives=[self.support_status(r) for r in b['warrant_refs']]
        leaves=[{exact_ref(r) for r in a['leaf_refs']} for a in alternatives]
        shared=set.intersection(*leaves) if leaves else set()
        return {'bundle_ref':bundle_ref,'basis_state':'recorded-alternative-remains' if any(a['basis_state']=='recorded-support' for a in alternatives) else 'recorded-basis-needs-review',
                'alternatives':alternatives,'shared_recorded_upstream':[{'kind':k,'id':i,'revision':v} for k,i,v in sorted(shared)],'independence':b['independence'],'claim_truth':'not-assigned',
                'leaf_refs':[{'kind':k,'id':i,'revision':v} for k,i,v in sorted(set.union(*leaves))]}
    def impact(self,changed_ref):
        exact_ref(changed_ref);relations=self.repo.list('evidence_relation');seen={exact_ref(changed_ref)};paths=[]
        while True:
            new=[]
            for edge in relations:
                if exact_ref(edge['from_ref']) in seen and exact_ref(edge['to_ref']) not in seen:
                    seen.add(exact_ref(edge['to_ref']));new.append(edge['to_ref']);paths.append({'relation_ref':ref(edge),'from_ref':edge['from_ref'],'to_ref':edge['to_ref'],'scope':edge['scope'],'scope_binding':edge['scope_binding'],'rationale':edge['rationale']})
            if not new:break
        return {'changed_ref':changed_ref,'review_paths':paths,'scope':'recorded accepted relations only; not exhaustive semantic dependency','truth_assignments':[]}
