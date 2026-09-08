#!/usr/bin/env python3
"""Finite BM25 retrieval witnesses inspired by Hu et al.; no agent simulation."""
import argparse
from contextlib import closing
import json
from pathlib import Path
import sqlite3


ROOT = Path(__file__).resolve().parent
POLICIES = ('top-k', 'unique-key', 'unique-key-value')


def rank(items, query):
    """Index keys only; FTS5 whitespace terms are ANDed; stable insertion ties.

    Fixtures provide simple FTS5 queries. Values and relevance labels do not
    affect retrieval. SQLite's BM25 score is lower for a better match.
    """
    with closing(sqlite3.connect(':memory:')) as db:
        db.execute('CREATE VIRTUAL TABLE memories USING fts5(key)')
        db.executemany('INSERT INTO memories(key) VALUES (?)',
                       [(item['key'],) for item in items])
        matches = db.execute(
            'SELECT rowid, bm25(memories) AS score FROM memories '
            'WHERE memories MATCH ? ORDER BY score, rowid', (query,)
        ).fetchall()
    return [dict(items[rowid - 1], score=round(score, 12)) for rowid, score in matches]


def select(ranked, budget, policy):
    """Select from one shared full ranking; exact-string dedup before the cap.

    The two dedup policies scan past duplicates to fill the entry budget.
    No dedup edits the store, changes scores, or receives relevance labels.
    """
    selected, seen = [], set()
    for item in ranked:
        if policy == 'top-k':
            identity = item['id']
        elif policy == 'unique-key':
            identity = item['key']
        elif policy == 'unique-key-value':
            identity = (item['key'], item['value'])
        else:
            raise ValueError(policy)
        if identity in seen:
            continue
        seen.add(identity)
        selected.append(item['id'])
        if len(selected) == budget:
            break
    return selected


def load_fixtures():
    return json.loads((ROOT / 'fixtures.json').read_text(encoding='utf-8'))


def report(fixture=None):
    fixture = load_fixtures() if fixture is None else fixture
    cases = []
    for case in fixture['cases']:
        old_ids = [item['id'] for item in case['base']]
        base_ranked = rank(case['base'], case['query'])
        old_ranking = [item['id'] for item in base_ranked]
        stages = []
        for growth in fixture['growth']:
            pool = case['base'] + case['additions'][:growth]
            ranked = rank(pool, case['query']) if growth else base_ranked
            ranked_ids = [item['id'] for item in ranked]
            observations = []
            for budget in fixture['budgets']:
                for policy in POLICIES:
                    chosen = select(ranked, budget, policy)
                    selected = [item for item in ranked if item['id'] in chosen]
                    observations.append({
                        'budget_entries': budget, 'policy': policy,
                        'selected_ids': chosen,
                        'hit': bool(set(chosen) & set(case['relevant_ids'])),
                        'distinct_keys': len({item['key'] for item in selected}),
                        'distinct_key_values': len({(item['key'], item['value']) for item in selected}),
                    })
            stages.append({
                'added': growth, 'pool_size': len(pool),
                'old_items_retained': sum(item['id'] in old_ids for item in pool),
                'old_item_count': len(old_ids),
                'old_matching_order_preserved': [i for i in ranked_ids if i in old_ids] == old_ranking,
                'ranking': [{'id': item['id'], 'score': item['score']} for item in ranked],
                'relevant_ranks': {i: ranked_ids.index(i) + 1 if i in ranked_ids else None
                                   for i in case['relevant_ids']},
                'observations': observations,
            })
        cases.append({'id': case['id'], 'query': case['query'], 'stages': stages})
    return {
        'study': 'experience-reuse-retrieval-study',
        'boundary': 'AMS synthetic key-only SQLite FTS5 BM25 retrieval; no ReMe implementation, LLM, environment success, or paper reproduction.',
        'sqlite_version': sqlite3.sqlite_version,
        'budgets_are': 'maximum returned entries, not equal tokens or equal retrieval work',
        'cases': cases,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='rerun and compare public results, excluding runtime version')
    args = parser.parse_args()
    result = report()
    if args.check:
        checked = json.loads((ROOT / 'results.json').read_text(encoding='utf-8'))
        comparable = lambda data: {k: v for k, v in data.items() if k != 'sqlite_version'}
        if comparable(checked) != comparable(result):
            raise SystemExit('FAIL: fresh rankings or selections differ from checked results')
        count = sum(len(stage['observations']) for case in result['cases'] for stage in case['stages'])
        print(f'PASS: {len(result["cases"])} scenarios, {count} selections match; SQLite {sqlite3.sqlite_version}')
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
