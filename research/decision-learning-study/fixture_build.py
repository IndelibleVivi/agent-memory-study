#!/usr/bin/env python3
"""Original public structured fixtures; label policy is explicit, not real utility."""
import json
from pathlib import Path

LABELS = ('useful', 'redundant', 'irrelevant', 'harmful')
GROUPS = {'train': ('archive', 'import', 'cleanup', 'backup'),
          'validation': ('catalogue', 'package'),
          'test': ('export', 'migrate', 'index', 'restore')}


def in_scope(context, candidate):
    return context['sensitive'] and not candidate['verified']


def label(context, candidate, version=1):
    if candidate['family'] != context['family'] or candidate['goal'] != context['goal']:
        return 'irrelevant'
    if candidate['param'] != context['param']:
        return 'irrelevant'
    if (candidate['expired'] or candidate['side_effect']
            or any(x not in context['known'] for x in candidate['requires'])
            or candidate['tool'] not in context['tools']):
        return 'harmful'
    if candidate['fact'] in context['known']:
        return 'redundant'
    if version == 2 and in_scope(context, candidate):
        return 'harmful'
    return 'useful'


def generate():
    result = {'schema': 'ams-decision-fixtures/2', 'splits': {},
              'correction': {'version': 2, 'rule': 'Previously useful, unverified candidates in sensitive contexts become harmful.'}}
    for split, groups in GROUPS.items():
        events = []
        for family in groups:
            context = {'family': family, 'goal': 'prepare', 'param': 'current',
                       'tools': ['reader'], 'known': ['ready', 'already-known'], 'sensitive': False}
            base = {'family': family, 'goal': 'prepare', 'param': 'current',
                    'tool': 'reader', 'requires': ['ready'], 'fact': 'new-fact',
                    'expired': False, 'side_effect': False, 'verified': False}
            changes = [({}, '符合条件，来源未核验'),
                       ({'verified': True}, '符合条件，来源已核验'),
                       ({'fact': 'already-known'}, '已经知道的内容'),
                       ({'family': 'other-domain'}, '来自其他任务范围'),
                       ({'goal': 'publish'}, '目标不匹配'),
                       ({'param': 'legacy'}, '参数范围不匹配'),
                       ({'requires': ['missing']}, '前置条件尚不满足'),
                       ({'tool': 'unavailable'}, '所需工具不可用'),
                       ({'expired': True}, '记录已经过期'),
                       ({'side_effect': True}, '附带不允许的副作用'),
                       ({'fact': 'alternative', 'requires': [], 'verified': True}, '无需前置条件的已核验候选'),
                       ({'fact': 'alternative', 'requires': []}, '无需前置条件的未核验候选')]
            candidates = [dict(base, **change, description=description) for change, description in changes]
            for sensitive in (False, True):
                for mode in ('base', 'known-more', 'all-known'):
                    ctx = dict(context, sensitive=sensitive, known=list(context['known']))
                    if mode in ('known-more', 'all-known'): ctx['known'].append('new-fact')
                    if mode == 'all-known': ctx['known'].append('alternative')
                    unit = f'{family}-{"sensitive" if sensitive else "ordinary"}-{mode}'
                    cs = [dict(c, requires=list(c['requires'])) for c in candidates]
                    events.append({'id': unit, 'group': family, 'title': f'{family} · {"敏感" if sensitive else "普通"}任务 · {mode}',
                                   'context': ctx, 'candidates': cs,
                                   'labels_v1': [label(ctx, c) for c in cs],
                                   'labels_v2': [label(ctx, c, 2) for c in cs]})
        result['splits'][split] = events
    return result


if __name__ == '__main__':
    (Path(__file__).parent / 'fixtures.json').write_text(json.dumps(generate(), ensure_ascii=False, indent=2)+'\n')
