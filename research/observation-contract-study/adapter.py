"""Small public instrument boundary. No platform registry or subprocess lifecycle."""
from __future__ import annotations
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location('ams_observation_native', ROOT / 'study.py')
_native = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_native)


def describe_capabilities():
    return {'id': 'observation-contract-study', 'version': '1',
            'schema': _native.SCHEMA, 'evidence_type': 'finite-exact',
            'empirical_sample_count': 0, 'network': False, 'provider': False,
            'operations': ['analyze-model', 'search-pair'],
            'native_inputs': 'fixtures.json:models',
            'limits': 'Finite deterministic declared models; pairwise open-loop actions only.'}


def validate_plan(plan):
    if not isinstance(plan, dict) or plan.get('operation') not in {'analyze-model', 'search-pair'}:
        raise ValueError('unknown operation')
    permitted = {'operation', 'model'} if plan['operation'] == 'analyze-model' else {
        'operation', 'model', 'left', 'right', 'max_steps', 'max_cost'}
    if set(plan) - permitted or not {'operation', 'model'} <= set(plan):
        raise ValueError('invalid plan fields')
    models = json.loads((ROOT / 'fixtures.json').read_text())['models']
    model = next((m for m in models if m['id'] == plan['model']), None)
    if model is None:
        raise ValueError('unknown model')
    _native.validate_model(model)
    if plan['operation'] == 'search-pair':
        if not {'left', 'right'} <= set(plan):
            raise ValueError('pair states required')
        if any(plan[k] not in model['plant']['states'] for k in ('left', 'right')):
            raise ValueError('unknown state')
        n = plan.get('max_steps')
        if n is not None and (type(n) is not int or n < 0):
            raise ValueError('invalid max_steps')
        if plan.get('max_cost') is not None:
            _native.cost(plan['max_cost'])
    return model


def execute(plan):
    model = validate_plan(plan)
    if plan['operation'] == 'analyze-model':
        result = _native.analyze(model)
    else:
        result = _native.search_pair(model['plant'], plan['left'], plan['right'],
                                    plan.get('max_steps'), plan.get('max_cost'))
    return {'schema': 'ams-observation-contract-instrument/1',
            'study_id': 'observation-contract-study', 'plan': dict(plan),
            'empirical_sample_count': 0, 'bindings': _native.source_bindings(), 'result': result}
