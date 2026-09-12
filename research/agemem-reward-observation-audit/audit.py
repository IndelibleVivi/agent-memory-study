"""Run pinned AgeMem reward functions on public synthetic messages, without models."""

import argparse
import copy
import importlib.util
import json
import math
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
UPSTREAM = 'https://github.com/y1y5/AgeMem'
COMMIT = '98f563f907d67b2f2436e3ae7b7ceff32e482814'
MODULE = 'trinity/common/workflows/memory_reward/my_reward.py'
INSPECTED = [MODULE, 'trinity/common/workflows/memory_context/train_hotpotQA.py',
             'trinity/algorithm/advantage_fn/multi_step_grpo_advantage.py']
WEIGHTS = dict(task_completion_weight=0.5, tool_efficiency_weight=0.2,
               context_management_weight=0.15, memory_management_weight=0.15)
CONSTANTS = dict(task_score=0.5, finished_at_round=4, max_rounds=10,
                 found_answer=True, max_tokens=8192,
                 supporting_facts=['The amber train uses platform four.'])


def require(condition, message):
    if not condition:
        raise ValueError(message)


def load_source(checkout):
    head = subprocess.check_output(['git', '-C', str(checkout), 'rev-parse', 'HEAD'],
                                   text=True).strip()
    require(head == COMMIT, f'Expected {COMMIT}, got {head}')
    subprocess.run(['git', '-C', str(checkout), 'diff', '--exit-code', 'HEAD', '--',
                    *INSPECTED], check=True, capture_output=True)
    spec = importlib.util.spec_from_file_location('ams_agemem_reward', checkout / MODULE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FixedJudge:
    """Deliberate test double: record public requests and return a fixed string."""

    def __init__(self, reply):
        self.reply = reply
        self.calls = []

    def chat(self, **kwargs):
        self.calls.append(copy.deepcopy(kwargs))
        return self.reply


def fixtures():
    return json.loads((HERE / 'fixtures.json').read_text())['cases']


def summarize(rows):
    by_id = {row['id']: row for row in rows}
    return {
        'cases': len(rows),
        'judge_stub_cases': sum(row['input']['judge_reply'] is not None for row in rows),
        'failed_operation_messages_with_maintenance_one': [
            name for name in ('updated-false', 'deleted-false')
            if by_id[name]['breakdown']['memory_r_maintenance'] == 1.0],
        'stage1_add_count_retained_vs_reset': [
            by_id[name]['memory_stats']['added_count']
            for name in ('history-retained', 'history-reset')],
        'ignored_retrieval_marked_used': by_id['retrieval-ignored']['memory_stats']['used_retrieved_memory'],
        'unrelated_query_marked_preserved': by_id['unrelated-query']['context_stats']['preserved_user_query'],
        'maintenance_with_zero_vs_one_stub_judge': [
            by_id[name]['breakdown']['memory_r_maintenance'] for name in ('judge-0.0', 'judge-1.0')],
        'maintenance_weighted_contribution_when_one': WEIGHTS['memory_management_weight'] / 3,
        'all_inputs_unchanged': all(row['input_unchanged'] for row in rows),
    }


def verify(result):
    require(result['upstream'] == UPSTREAM and result['commit'] == COMMIT, 'Source identity drift')
    require(result['executed_module'] == MODULE and result['inspected_sources'] == INSPECTED,
            'Source scope drift')
    require(result['weights'] == WEIGHTS and result['constants'] == CONSTANTS, 'Run settings drift')
    rows = result['results']
    expected = fixtures()
    require(len(rows) == len(expected) == 16, 'Missing or extra cases')
    for row, case in zip(rows, expected):
        require(row['id'] == case['id'] and row['group'] == case['group'], 'Case order drift')
        require(row['input'] == case['input'] and row['input_unchanged'], 'Input binding drift')
        for path, value in case['expected'].items():
            actual = row
            for part in path.split('.'):
                actual = actual[part]
            require(actual == value, f'{case["id"]}: {path}: {actual!r} != {value!r}')
        calls = row['judge_calls']
        require(len(calls) == (1 if case['input']['judge_reply'] is not None else 0), 'Judge path drift')
        if calls:
            require(calls[0]['model_name'] == 'qwen-max', 'Unexpected upstream model argument')
            require(case['input']['question'] in calls[0]['messages'][0]['content'], 'Question binding drift')
        b = row['breakdown']
        require(math.isclose(b['memory_management'], 0.15 * sum(
            b[k] for k in ('memory_r_storage', 'memory_r_maintenance', 'memory_r_relevance')) / 3),
            f'{case["id"]}: memory weighting mismatch')
        require(b['task_completion'] == 0.25, 'Task weight mismatch')
        # Fixtures never reach round/token limits: no penalty or clipping conceals the sum.
        total = sum(b[k] for k in ('task_completion', 'tool_efficiency',
                                    'context_management', 'memory_management'))
        require(-1 < total < 1 and math.isclose(total, b['total']), 'Total arithmetic mismatch')
        require(row['returned_total'] == b['total'], 'Return/breakdown mismatch')
    by_id = {row['id']: row for row in rows}
    for event in ('updated', 'deleted'):
        require(by_id[event + '-true']['breakdown']['memory_management'] ==
                by_id[event + '-false']['breakdown']['memory_management'], 'Maintenance pair differs')
    mention = by_id['summary-name-only']
    context = mention['context_stats']
    # Independently isolate Eq. (20)'s implemented presence signal from other terms.
    preventive = mention['breakdown']['context_management'] / 0.15 * 3 - (
        1 - context['token_usage_ratio']) - 1
    require(math.isclose(preventive, 1), 'Mention-only preventive signal drift')
    require(result['summary'] == summarize(rows), 'Summary differs from raw results')


def run(checkout):
    module = load_source(checkout)
    rows = []
    for case in fixtures():
        inputs = copy.deepcopy(case['input'])
        messages = inputs['messages']
        judge = FixedJudge(inputs['judge_reply']) if inputs['judge_reply'] is not None else None
        calculator = module.ThreeStageRewardCalculator(**WEIGHTS, chat_client=judge)
        tool_stats = module.extract_tool_usage_stats(messages)
        context_stats = module.extract_context_stats(messages, CONSTANTS['max_tokens'])
        memory_stats = module.extract_memory_stats(messages, None)
        total, breakdown = calculator.calculate_total_reward(
            task_score=CONSTANTS['task_score'], tool_usage_stats=tool_stats,
            context_stats=context_stats, memory_stats=memory_stats,
            finished_at_round=CONSTANTS['finished_at_round'], max_rounds=CONSTANTS['max_rounds'],
            found_answer=CONSTANTS['found_answer'], question=inputs['question'],
            supporting_facts=CONSTANTS['supporting_facts'], context_messages=messages)
        rows.append(dict(id=case['id'], group=case['group'], input=case['input'],
                         input_unchanged=inputs == case['input'], tool_stats=tool_stats,
                         context_stats=context_stats, memory_stats=memory_stats,
                         returned_total=total, breakdown=breakdown,
                         judge_calls=judge.calls if judge else []))
    result = dict(schema='ams.agemem-reward-observation.v1', upstream=UPSTREAM, commit=COMMIT,
                  executed_module=MODULE, inspected_sources=INSPECTED,
                  weights=WEIGHTS, constants=CONSTANTS, results=rows, summary=summarize(rows))
    verify(result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--source-repo', type=Path, help='External checkout pinned to the recorded commit')
    mode.add_argument('--verify-checked', action='store_true', help='Check saved receipt only; no upstream run')
    parser.add_argument('--check', action='store_true', help='Fresh source execution must equal saved receipt')
    args = parser.parse_args()
    if args.verify_checked:
        require(not args.check, '--check requires --source-repo')
        verify(json.loads((HERE / 'results.json').read_text()))
        print('PASS: 16 checked AgeMem receipts bind to fixtures; arithmetic verified; upstream not rerun')
    else:
        result = run(args.source_repo.resolve())
        if args.check:
            require(result == json.loads((HERE / 'results.json').read_text()), 'Fresh upstream output differs')
            print('PASS: 16 fresh upstream AgeMem reward cases match saved results; 2 use a fixed judge stub')
        else:
            print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
