"""Original diagnostic events. Writers receive events only, never questions/gold."""
import copy
import hashlib
import json

VERSION = 'ams-representation-fixture/1'
FAMILIES = ('scope', 'authority', 'time', 'agreement', 'provenance', 'relations', 'conflict', 'unknown')


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def events_for(family, updated, wording):
    def event(i, **kw):
        return dict(id=f'{family}:e{i}', time=i, kind='decision', scope='current', actor='owner',
                    authority=True, accepted=True, value='blue', wording=f'采用蓝色方案。{wording}', **kw)
    # Each family has a real distinguishing intervention, not renamed duplicate rows.
    base = event(1)
    events = [base]
    if family == 'scope':
        other = event(2); other.update(scope='expanded', value='green', wording='扩展任务采用绿色。'); events.append(other)
    elif family == 'authority':
        other = event(2); other.update(actor='visitor', authority=False, value='red', wording='访客要求红色。'); events.append(other)
    elif family == 'time':
        other = event(2); other.update(time=9, value='red', wording='第九日才启用红色。'); events.append(other)
    elif family == 'agreement':
        other = event(2); other.update(accepted=False, value='red', wording='有人提过红色，还没有同意。'); events.append(other)
    elif family == 'provenance':
        other = event(2); other.update(kind='observation', actor='scribe', value='red', wording='书记员转述红色建议，并非本人决定。'); events.append(other)
    elif family == 'relations':
        for i, pair in ((2, ['A', 'B']), (3, ['B', 'C'])):
            other = event(i); other.update(kind='relation', pair=pair, wording='与'.join(pair)+'直接交谈。'); events.append(other)
    elif family == 'conflict':
        other = event(2); other.update(time=1, value='red', wording='同一时刻也批准红色，未指定优先级。'); events.append(other)
    elif family == 'unknown':
        events[0].update(scope='unrelated', wording='无关任务采用蓝色。')
    if updated:
        other = event(4); other.update(time=4, value='amber', wording='仅当前任务从第四日起改为琥珀色；扩展任务不变。'); events.append(other)
    return events


def questions(task):
    common = [
        dict(id='current', kind='decision', scope='current', at=5, task_role='common', text='第五日当前任务应采用什么？'),
        dict(id='boundary', kind='decision', scope='expanded', at=5, task_role='common', text='第五日相邻范围 expanded 的任务应采用什么？'),
    ]
    added = [
        dict(id='historical', kind='decision', scope='current', at=1, text='第一日当前任务批准了什么？'),
        dict(id='agreement', kind='agreement', text='红色是否获得有权限者正式接受（截至第五日）？'),
        dict(id='provenance', kind='provenance', event=1, text='原始第一条事件由谁、在何时记录？'),
        dict(id='wording', kind='wording', event=1, text='原始第一条事件的逐字原话是什么？'),
        dict(id='direct', kind='direct', text='A 与 C 是否有直接交谈的记录？'),
        dict(id='indirect', kind='indirect', text='是否存在 A—B—C 的间接关系链？'),
    ]
    for q in added: q['task_role']='added'
    return common if task=='current' else common+added


def truth(events, question):
    """Latent event-state interpreter. No backend, representation or score access."""
    q = question
    if q['kind'] == 'decision':
        valid = [e for e in events if e['kind']=='decision' and e['accepted'] and e['authority']
                 and e['scope']==q['scope'] and e['time']<=q['at']]
        if not valid:
            return {'accepted': ['abstain:unknown', 'clarify:scope'], 'conflicting': False}
        latest = max(e['time'] for e in valid)
        values = sorted({e['value'] for e in valid if e['time']==latest})
        if len(values)>1:
            return {'accepted': ['clarify:conflict', 'abstain:conflict'], 'conflicting': True}
        answer = values[0]
    elif q['kind'] == 'agreement':
        answer = 'yes' if any(e['kind']=='decision' and e['time']<=5 and e['value']=='red'
                             and e['authority'] and e['accepted'] for e in events) else 'no'
    elif q['kind'] in ('wording', 'provenance'):
        e=events[q['event']-1]
        answer = e['wording'] if q['kind']=='wording' else f"{e['actor']}@{e['time']}"
    else:
        edges={tuple(sorted(e['pair'])) for e in events if e['kind']=='relation'}
        answer = 'yes' if ((('A','C') in edges) if q['kind']=='direct' else
                          ({('A','B'),('B','C')} <= edges)) else 'no'
    return {'accepted': ['answer:'+answer], 'conflicting': False}


def writer(events, representation):
    """Fixed summary keeps decision qualifications; deletes provenance, wording and old history."""
    if representation == 'raw':
        return [dict(id='raw:'+e['id'], record=dict(e, representation='raw'), covers=[e['id']]) for e in events]
    if representation == 'summary':
        keep=[]
        for e in events:
            if e['kind']=='decision' and any(x['kind']=='decision' and x['scope']==e['scope']
                    and x['authority'] and x['accepted'] and x['time']>e['time'] and x['time']<=5 for x in events):
                continue
            r={k:v for k,v in e.items() if k not in ('actor','wording')}
            r['representation']='summary'
            keep.append(dict(id='summary:'+e['id'], record=r, covers=[e['id']]))
        return keep
    return writer(events,'raw')+writer(events,'summary')


def corpus():
    cases=[]
    # Split allocation is fixed at FAMILY level, before history/task/wording variants.
    for index,family in enumerate(FAMILIES):
        for updated in (False,True):
            for task in ('current','expanded'):
                for wording in ('原话甲','原话乙'):
                    events=events_for(family,updated,wording)
                    cases.append(dict(id=f'{family}-{int(updated)}-{task}-{wording}', group=family,
                        split='development' if index<4 else 'diagnostic', history='updated' if updated else 'fixed',
                        task=task, variant=wording, events=events, questions=questions(task)))
    return dict(schema=VERSION, status='public-development-diagnostic-not-blinded', families=list(FAMILIES), cases=cases)


def evidence(case, question, delivered):
    """Conservative closed-world obligations; only complete delivered records count.

    Missing history/provenance is representation loss, never filled from latent state.
    Negative claims require the whole event set, not absence in a truncated prefix.
    """
    records=[x['record'] for x in delivered]
    q=question; events=case['events']
    if q['kind'] in ('provenance','wording'):
        needed=events[q['event']-1]['id']
        sufficient=any(r['id']==needed and r['representation']=='raw' for r in records)
    else:
        available={r['id'] for r in records}
        if q['kind']=='decision':
            valid=[e for e in events if e['kind']=='decision' and e['scope']==q['scope'] and e['time']<=q['at'] and e['authority'] and e['accepted']]
            latest=max((e['time'] for e in valid), default=None)
            needed={e['id'] for e in valid if e['time']==latest}
            sufficient=(needed <= available) and bool(records)
            if not needed: sufficient={e['id'] for e in events} <= available
        else:
            sufficient={e['id'] for e in events} <= available
    return ('conflicting' if truth(events,q)['conflicting'] else 'sufficient') if sufficient else 'insufficient'
