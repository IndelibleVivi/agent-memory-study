#!/usr/bin/env python3
"""Fit and compare specific memory-selection implementations on public fixtures."""
import argparse
import copy
import json
import math
from pathlib import Path
import platform
import random
import time
from fixture_build import LABELS, label, in_scope

ROOT = Path(__file__).resolve().parent
FEATURES = ('family_match', 'goal_match', 'param_match', 'prereq_met', 'tool_ok',
            'already_known', 'expired', 'side_effect', 'verified', 'sensitive')
METHODS = ('no-experience', 'episodic', 'rules', 'scorer')
STEPS, RATE, L2, UPDATE_STEPS = 400, 0.5, 0.01, 40


def rows_for(fixture, split, version=1):
    return [{'id': f"{e['id']}--{i}", 'event': e['id'], 'group': e['group'],
             'index': i, 'context': e['context'], 'candidate': c, 'expected': e[f'labels_v{version}'][i]}
            for e in fixture['splits'][split] for i, c in enumerate(e['candidates'])]


def vector(row):
    c, m = row['context'], row['candidate']
    return [int(m['family'] == c['family']), int(m['goal'] == c['goal']),
            int(m['param'] == c['param']), int(all(x in c['known'] for x in m['requires'])),
            int(m['tool'] in c['tools']), int(m['fact'] in c['known']),
            int(m['expired']), int(m['side_effect']), int(m['verified']), int(c['sensitive'])]


def fit(rows, initial=None, steps=STEPS, active=None):
    """Deterministic OVR logistic gradient descent, including a real warm start."""
    active = list(range(len(FEATURES))) if active is None else active
    start = copy.deepcopy(initial) if initial is not None else [[0.0]*11 for _ in LABELS]
    weights = copy.deepcopy(start)
    xs = [[v if i in active else 0 for i, v in enumerate(vector(r))]+[1] for r in rows]
    for _ in range(steps):
        for k, target in enumerate(LABELS):
            grad = [0.0]*11
            for r, x in zip(rows, xs):
                z = sum(w*v for w, v in zip(weights[k], x))
                error = 1/(1+math.exp(-z)) - int(r['expected'] == target)
                for j, v in enumerate(x): grad[j] += error*v
            for j in range(11):
                weights[k][j] -= RATE*(grad[j]/len(rows) + (L2*weights[k][j] if j < 10 else 0))
    return {'initial': start, 'weights': weights, 'steps': steps, 'active': active}


def scorer(model, rows):
    def predict(r):
        x = [v if i in model['active'] else 0 for i, v in enumerate(vector(r))]+[1]
        scores = [sum(w*v for w, v in zip(ws, x)) for ws in model['weights']]
        return LABELS[max(range(4), key=lambda k: scores[k])]
    return [predict(r) for r in rows]


def induce(rows, depth=0):
    """Readable greedy binary decision tree, depth<=4, induced only from feedback."""
    counts = [sum(r['expected'] == lab for r in rows) for lab in LABELS]
    majority = LABELS[max(range(4), key=lambda k: counts[k])]
    if depth == 4 or max(counts) == len(rows): return {'label': majority, 'support': len(rows)}
    def impurity(rs):
        return len(rs)*(1-sum((sum(r['expected']==lab for r in rs)/len(rs))**2 for lab in LABELS)) if rs else 0
    choices=[]
    for f in range(10):
        parts = [[r for r in rows if vector(r)[f] == value] for value in (0,1)]
        if all(parts): choices.append((sum(impurity(p) for p in parts), f, parts))
    if not choices: return {'label': majority, 'support': len(rows)}
    _, f, parts=min(choices,key=lambda x:(x[0],x[1]))
    return {'feature': FEATURES[f], 'zero': induce(parts[0],depth+1), 'one': induce(parts[1],depth+1)}


def rule_predict(tree, rows):
    def predict(r):
        node=tree; x=vector(r)
        while 'feature' in node: node=node['one' if x[FEATURES.index(node['feature'])] else 'zero']
        return node['label']
    return [predict(r) for r in rows]


def episodic(train, test):
    xs=[vector(r) for r in train]
    return [train[min(range(len(train)),key=lambda i:sum(a!=b for a,b in zip(xs[i],vector(r))))]['expected'] for r in test]


def metrics(rows, pred):
    n=len(rows)
    if not n: return {'n': 0, 'correct': 0, 'accuracy': None}
    units={}
    for r,p in zip(rows,pred): units.setdefault(r['event'],[]).append((r,p))
    empty=[v for v in units.values() if not any(r['expected']=='useful' for r,p in v)]
    return {'n': n, 'correct': sum(r['expected']==p for r,p in zip(rows,pred)),
            'accuracy': sum(r['expected']==p for r,p in zip(rows,pred))/n,
            'useful_missed': sum(r['expected']=='useful' and p!='useful' for r,p in zip(rows,pred)),
            'harmful_selected': sum(r['expected']=='harmful' and p=='useful' for r,p in zip(rows,pred)),
            'unnecessary_selected': sum(r['expected'] in ('redundant','irrelevant') and p=='useful' for r,p in zip(rows,pred)),
            'events': len(units), 'exact_selection': sum(all((r['expected']=='useful')==(p=='useful') for r,p in v) for v in units.values()),
            'empty_events': len(empty), 'correct_empty': sum(not any(p=='useful' for r,p in v) for v in empty),
            'per_group': {g: {'n':sum(r['group']==g for r in rows), 'correct':sum(r['group']==g and r['expected']==p for r,p in zip(rows,pred))} for g in sorted({r['group'] for r in rows})}}


def all_predictions(train,test,model,tree):
    return {'no-experience':['irrelevant']*len(test), 'episodic':episodic(train,test),
            'rules':rule_predict(tree,test), 'scorer':scorer(model,test)}


def subset_metrics(rows,pred,indices):
    return metrics([rows[i] for i in indices],[pred[i] for i in indices])


def report(fixture):
    train,validation,test=[rows_for(fixture,s) for s in ('train','validation','test')]
    model=fit(train);tree=induce(train)
    before=all_predictions(train,test,model,tree)
    new_train=rows_for(fixture,'train',2);new_test=rows_for(fixture,'test',2)
    changed=[i for i,(a,b) in enumerate(zip(test,new_test)) if a['expected']!=b['expected']]
    preserved=[i for i in range(len(test)) if i not in changed]
    boundary=[i for i,r in enumerate(test) if r['expected']=='useful' and i not in changed]
    correction=[b for a,b in zip(train,new_train) if a['expected']!=b['expected']]
    refit=fit(new_train);update=fit(correction,initial=model['weights'],steps=UPDATE_STEPS)
    frozen=scorer(model,new_test)
    guarded=[('harmful' if p=='useful' and in_scope(r['context'],r['candidate']) else p) for r,p in zip(new_test,frozen)]
    after={'frozen':frozen,'refit':scorer(refit,new_test),'incremental':scorer(update,new_test),'guard':guarded}
    groups={'changed':changed,'preserved':preserved,'boundary':boundary}
    phase_metrics={name:{scope:subset_metrics(new_test,pred,idx) for scope,idx in groups.items()} for name,pred in after.items()}
    transitions={name:{scope:{f'{a}→{b}':sum(frozen[i]==a and pred[i]==b for i in idx) for a in LABELS for b in LABELS} for scope,idx in groups.items()} for name,pred in after.items()}
    shuffled=copy.deepcopy(train);labs=[r['expected'] for r in shuffled];random.Random(17).shuffle(labs)
    for r,lab in zip(shuffled,labs):r['expected']=lab
    shuffled_preds=all_predictions(shuffled,test,fit(shuffled),induce(shuffled))
    renamed=[copy.deepcopy(r) for r in test]
    for r in renamed:
        r['context']['family']='renamed-'+r['context']['family'];r['candidate']['family']='renamed-'+r['candidate']['family']
    ablations={name:metrics(test,scorer(fit(train,active=indices),test)) for name,indices in
               {'candidate-only':[6,7,8], 'context-only':[9], 'relations-only':[0,1,2,3,4,5]}.items()}
    train_x={tuple(vector(r)) for r in train}
    leaf_count=lambda t: 1 if 'label' in t else leaf_count(t['zero'])+leaf_count(t['one'])
    return {'schema':'ams-decision-results/2','study':'decision-learning-study',
            'config':{'features':list(FEATURES),'labels':list(LABELS),'optimiser':'full-batch OVR logistic gradient descent',
                      'steps':STEPS,'rate':RATE,'l2':L2,'update_steps':UPDATE_STEPS,'initialisation':'zero, deterministic; one fit, no seed replicates','tree_max_depth':4},
            'splits':{s:{'groups':len({e['group'] for e in es}),'events':len(es),'rows':sum(len(e['candidates']) for e in es)} for s,es in fixture['splits'].items()},
            'support':{'test_rows_with_seen_vector':sum(tuple(vector(r)) in train_x for r in test),'test_rows':len(test),'unique_train_vectors':len(train_x)},
            'cost':{'scorer_parameters':44,'saved_cases':len(train),'rule_leaves':leaf_count(tree),'fit_steps':STEPS,'incremental_rows':len(correction)},
            'before':{'metrics':{k:metrics(test,v) for k,v in before.items()},'predictions':before},
            'validation':metrics(validation,scorer(model,validation)),
            'after':{'metrics':phase_metrics,'predictions':after,'transitions':transitions,'correction_row_ids':[r['id'] for r in correction]},
            'controls':{'shuffled-label':{k:metrics(test,v) for k,v in shuffled_preds.items()},
                        'identity-invariance':all_predictions(train,renamed,model,tree)==before,
                        'input-ablations':ablations},
            'models':{'original':model,'refit':refit,'incremental':update,'rules':tree},
            'cases':[{**{k:r[k] for k in ('id','event','group','index','context','candidate')},'expected_v1':r['expected'],'expected_v2':new_test[i]['expected'],
                      'scope':'changed' if i in changed else ('boundary' if i in boundary else 'preserved')} for i,r in enumerate(test)]}


def rounded(value):
    if isinstance(value,float):return round(value,10)
    if isinstance(value,list):return [rounded(x) for x in value]
    if isinstance(value,dict):return {k:rounded(v) for k,v in value.items()}
    return value


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--check',action='store_true')
    parser.add_argument('--output',type=Path,default=ROOT/'results.json');args=parser.parse_args()
    started=time.perf_counter();result=rounded(report(json.loads((ROOT/'fixtures.json').read_text())))
    if args.check:
        checked=json.loads(args.output.read_text());checked.pop('execution',None)
        if result!=checked:raise SystemExit('FAIL: recomputed deterministic result differs')
        print('PASS: parameters, predictions, scope metrics and controls recomputed')
    else:
        result['execution']={'python':platform.python_version(),'elapsed_seconds':round(time.perf_counter()-started,4),
                             'note':'One local total runtime, not a method speed comparison. Excluded from deterministic --check.'}
        args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps({'before':{k:v['accuracy'] for k,v in result['before']['metrics'].items()},
                          'after':{k:{g:m['accuracy'] for g,m in v.items()} for k,v in result['after']['metrics'].items()}},indent=2))


if __name__=='__main__':main()
