"""Executable injected-transport boundary; no built-in HTTP or credential lookup.

A real provider-specific wire mapper must be selected, documented and authorized
separately. Mock tests exercise this normalized contract only.
"""
import hashlib
import json


def identity(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()


class ProviderFailure(Exception):
    def __init__(self, code, submission='not-submitted'):
        super().__init__(code)
        if code not in {'rate_limit','context_overflow','refusal','timeout','transport_error'}:
            raise ValueError('unknown provider failure')
        if submission not in {'not-submitted','unknown','confirmed'}: raise ValueError('invalid submission state')
        self.code,self.submission=code,submission


def validate_binding(binding):
    required={'provider','model_revision','tokenizer','input_token_count','fee_cap','authorized'}
    if set(binding)!=required or binding['authorized'] is not True:
        raise ValueError('exact authorized provider binding required')
    if any(not isinstance(binding[k],str) or not binding[k].strip() for k in ('provider','model_revision','tokenizer','fee_cap')):
        raise ValueError('provider/model/tokenizer/fee cap must be bound')
    if type(binding['input_token_count']) is not int or binding['input_token_count']<0:
        raise ValueError('actual tokenizer input count required')


def execute_cell(cell,binding,transport,prior=None,resolution=None):
    """No automatic retry. Explicit invocation is a new attempt; unknown blocks it."""
    validate_binding(binding)
    if prior and prior['status']=='indeterminate' and resolution!='operator-authorized-retry-after-reconciliation':
        raise ValueError('unknown submission requires external reconciliation before retry')
    request={'model_revision':binding['model_revision'],'messages':cell['messages'],
             'max_output_tokens':cell['max_output_tokens'],'tokenizer':binding['tokenizer']}
    receipt={'schema':'ams-conditional-provider-attempt/1','cell_id':cell['job']['id'],
             'request':request,'request_digest':identity(request),'binding_digest':identity(binding),
             'retry_of':identity(prior) if prior else None,'resolution':resolution,
             'raw_response':None,'status':None,'error':None,'used':'unknown'}
    try:
        raw=transport(request)
        receipt['raw_response']=raw
        if not isinstance(raw,dict) or raw.get('status') not in ('ok','refusal'):
            receipt['status']='parse_failure'
        elif raw['status']=='refusal':receipt['status']='refusal'
        elif not isinstance(raw.get('output_text'),str):receipt['status']='parse_failure'
        else:
            try:
                r=json.loads(raw['output_text'])
                if set(r)!={'action','value','citations'} or r['action'] not in ('answer','abstain') or not isinstance(r['value'],str) or not isinstance(r['citations'],list) or any(not isinstance(i,str) for i in r['citations']):
                    raise ValueError('response schema')
                receipt['status']='successful'
            except (ValueError,TypeError):receipt['status']='parse_failure'
    except ProviderFailure as exc:
        receipt['status']='indeterminate' if exc.submission=='unknown' else 'failed'
        receipt['error']={'code':exc.code,'submission':exc.submission}
    receipt['response_digest']=identity(receipt['raw_response'])
    return receipt


def review_binding(content,rubric):
    return {'content_digest':identity(content),'rubric_digest':identity(rubric)}


def review_matches(review,content,rubric):
    return review==review_binding(content,rubric)
