"""Original structured development families; no private material or language inference."""
import hashlib
import json

FAMILIES=('fact-replacement','scope-narrowing','exception-expiry','commitment-revocation',
          'premise-correction','authority-conflict','unauthorized-message','other-project','stable')


def canonical(x): return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'))

def identity(x): return hashlib.sha256(canonical(x).encode()).hexdigest()


def fixtures():
    result=[]
    for family in FAMILIES:
        def event(eid, **kw):
            e=dict(id=eid,project='P',scopes=['alpha','beta'],key='mode',kind='assert',value='blue',
                   valid_from=0,valid_to=None,observed_time=0,authority='owner',supersedes=[],
                   source='original-synthetic:'+family+':'+eid)
            e.update(kw); return e
        initial=[event('base'),event('archive',key='archive',value='keep'),event('q-base',project='Q',value='blue')]
        update=[]
        common=dict(valid_from=2,observed_time=2,scopes=['alpha'])
        if family=='fact-replacement': update=[event('revision',value='red',supersedes=['base'],**dict(common,valid_from=0))]
        elif family=='scope-narrowing': update=[event('restriction',kind='scope-update',value='blue',allowed_scopes=['beta'],supersedes=['base'],**dict(common,scopes=['alpha','beta']))]
        elif family=='exception-expiry':
            initial.append(event('temporary',value='red',valid_from=1,valid_to=4,observed_time=1,scopes=['alpha'],supersedes=['base']))
            update=[event('expiry-notice',kind='notice',value=None,valid_from=4,observed_time=2)]
        elif family=='commitment-revocation':
            initial[0]['kind']='commitment'
            update=[event('withdrawal',kind='revoke',value=None,supersedes=['base'],**dict(common,valid_from=3))]
        elif family=='premise-correction':
            initial[0].update(kind='rule',value='ship',dependency='ready',mapping={'yes':'ship','no':'hold'})
            initial.append(event('premise',key='ready',value='yes'))
            update=[event('premise-revision',key='ready',value='no',supersedes=['premise'],**common)]
        elif family=='authority-conflict': update=[event('rival',value='red',**common)]
        elif family=='unauthorized-message': update=[event('visitor',value='red',authority='visitor',supersedes=['base'],**common)]
        elif family=='other-project': update=[event('q-revision',value='red',project='Q',supersedes=['q-base'],**common)]
        result.append(dict(id=family,group=family,initial=initial,revision=update))
    return dict(schema='ams-revision-fixtures/1',status='public-development-diagnostic-not-blinded',families=result)


def query(key='mode',scope='alpha',valid_time=2,observed_time=2):
    return dict(project='P',key=key,scope=scope,valid_time=valid_time,observed_time=observed_time)


def probes(step):
    t=step+1
    return dict(main=query(valid_time=t,observed_time=t),preserved=query('archive',valid_time=t,observed_time=t),
                boundary=query(scope='beta',valid_time=t,observed_time=t),
                historical_old=query(valid_time=0,observed_time=0),
                historical_before_observed=query(valid_time=2,observed_time=1),
                historical_after_observed=query(valid_time=2,observed_time=2),
                historical_revised_valid=query(valid_time=0,observed_time=2))


def gold(events,q,visiting=()):
    """Independent bitemporal latent-state interpreter; never passed to rule answerer."""
    relevant=[e for e in events if e['project']==q['project'] and e['key']==q['key']
              and q['scope'] in e['scopes'] and e['authority']=='owner'
              and e['observed_time']<=q['observed_time'] and e['valid_from']<=q['valid_time']
              and (e['valid_to'] is None or q['valid_time']<e['valid_to']) and e['kind']!='notice']
    removed={old for e in relevant for old in e['supersedes']}
    active=[e for e in relevant if e['id'] not in removed and e['kind']!='revoke'
            and (e['kind']!='scope-update' or q['scope'] in e['allowed_scopes'])]
    if not active: return dict(accepted=['abstain:unknown'],support=[])
    values=set(); support=[]
    for e in active:
        support.append(e['id'])
        if e['kind']=='rule':
            if q['key'] in visiting: raise ValueError('cyclic fixture dependency')
            dep=gold(events,dict(q,key=e['dependency']),visiting+(q['key'],))
            support.extend(dep['support'])
            label=dep['accepted'][0]
            if not label.startswith('answer:'): return dict(accepted=['clarify:conflict'],support=sorted(set(support)))
            values.add(e['mapping'][label.split(':',1)[1]])
        else: values.add(e['value'])
    if len(values)>1: return dict(accepted=['clarify:conflict','abstain:conflict'],support=sorted(set(support)))
    return dict(accepted=['answer:'+next(iter(values))],support=sorted(set(support)))
