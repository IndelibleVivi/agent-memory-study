import copy
import json
import unittest

import natural as n
import natural_facts as f
from test_natural import data, receipt


class FactualPipelineTests(unittest.TestCase):
    def test_only_memory_differs_across_arms_and_gold_is_absent(self):
        q={'questions':[{'id':'c:f1','case':'c','kind':'scope','text':'现在走哪个通道？',
           'answer_schema':{'type':['string','null'],'enum':['前台','柜机',None]},
           'gold':'SECRET-GOLD','support':['secret-source'],'rationale':'secret-reason'}]}
        mm={'c--'+a:{'status':'valid','memory':a} for a in ('prose','ledger')}
        jobs=f.jobs(data(),mm,q)
        self.assertEqual(len(jobs),8)
        stripped=[]
        for j in jobs:
            p=copy.deepcopy(j['payload'])
            self.assertNotIn('SECRET',n.canonical(p));self.assertNotIn('secret-',n.canonical(p))
            u=json.loads(p['input'][1]['content'])
            if j['arm']=='none':self.assertEqual(u['memory'],'')
            u['memory']='';p['input'][1]['content']=n.canonical(u);p['model']='same'
            stripped.append(p)
        self.assertTrue(all(p==stripped[0] for p in stripped))

    def test_null_does_not_become_a_guess(self):
        schema={'type':['integer','null']}
        for answer in (None,11):
            self.assertEqual(f.parse(receipt({'answer':answer,'sources':[],'basis':''}),schema),
                             {'status':'valid','answer':answer})
        for answer in ('11',True,{'answer':11}):
            self.assertEqual(f.parse(receipt({'answer':answer,'sources':[],'basis':''}),schema)['status'],'parse-error')

    def test_set_order_is_irrelevant_but_duplicates_are_invalid(self):
        schema={'type':['array','null'],'items':{'type':'string','enum':['路线','访谈','插画']}}
        a=f.parse(receipt({'answer':['路线','插画'],'sources':[],'basis':''}),schema)
        b=f.parse(receipt({'answer':['插画','路线'],'sources':[],'basis':''}),schema)
        self.assertEqual(a,b)
        for answer in (['路线','路线'],['虚构未知章节']):
            self.assertEqual(f.parse(receipt({'answer':answer,'sources':[],'basis':''}),schema)['status'],'parse-error')

    def test_malformed_or_incomplete_response_is_not_a_semantic_null(self):
        schema={'type':['string','null']}
        for body in ('[]','null','{}'):
            p=f.parse({'http_status':200,'raw_body':body},schema)
            self.assertNotEqual(p['status'],'valid')
        self.assertEqual(f.parse(receipt({'answer':'前台','sources':[],'basis':''},'incomplete'),schema)['status'],'incomplete')


if __name__=='__main__':unittest.main()
