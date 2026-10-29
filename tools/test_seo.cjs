const {test} = require('node:test');
const assert = require('node:assert/strict');
const seo = require('../assets/seo.js');
const data = require('../data/materials.json');
const base = new URL('https://preview.example/agent-memory-study/');

test('physical paths resolve on a Pages subpath and index.html aliases', () => {
  assert.deepEqual(seo.pathRoute(new URL('material/pm-bench/',base),base), {material:'pm-bench'});
  assert.deepEqual(seo.pathRoute(new URL('finding/revision-needs-scope/index.html',base),base), {finding:'revision-needs-scope'});
  assert.equal(seo.pathRoute(new URL('https://preview.example/other/material/pm-bench/'),base),null);
});

test('navigation retains practice, filters, scenario and fragment, and removes old detail identity', () => {
  const current = new URL('material/pm-bench/?material=pm-bench&utm_source=reference',base);
  const route = {study:'after-a-correction',scenario:'legacy',phase:'after',practice:'重复候选',q:'memory',topic:'可靠性',depth:'read'};
  const output = new URL(seo.routeUrl(route,current,base,true,'#study-lab'),base);
  assert.equal(output.pathname,'/agent-memory-study/study/after-a-correction/');
  for (const key of ['scenario','phase','practice','q','topic','depth']) assert.equal(output.searchParams.get(key),route[key]);
  assert.equal(output.searchParams.get('material'),null);
  assert.equal(output.searchParams.get('study'),null);
  assert.equal(output.hash,'#study-lab');
  assert.equal(output.searchParams.get('utm_source'),'reference');
  assert.equal(new URL(seo.routeUrl({},output,base,true),base).pathname,base.pathname);
});

test('source HTTP and file URLs retain query route compatibility', () => {
  for (const current of ['http://127.0.0.1:8080/index.html','file:///public/reading-room/index.html']) {
    const original = new URL(current);
    const result = new URL(seo.routeUrl({material:'pm-bench'},original,new URL('./',original),false),original);
    assert.equal(result.pathname,original.pathname);
    assert.equal(result.searchParams.get('material'),'pm-bench');
  }
});

test('all published pages have unique metadata, with state excluded and paper authors not attributed as note authors', () => {
  const routes = [{}];
  for (const [kind,key] of Object.entries({material:'materials',study:'studies',question:'questions',finding:'findings'})) {
    data[key].forEach(item=>routes.push({[kind]:item.id}));
  }
  const urls = new Set(), titles = new Set();
  for (const route of routes) {
    const meta = seo.metadata(data,{...route,practice:'PRIVATE_QUERY_SENTINEL',q:'PRIVATE_QUERY_SENTINEL'});
    assert.ok(meta.description.length > 20);
    assert.ok(!JSON.stringify(meta).includes('PRIVATE_QUERY_SENTINEL'));
    assert.ok(!meta.canonical.includes('?'));
    assert.equal(meta.structured.author,undefined);
    urls.add(meta.canonical); titles.add(meta.title);
  }
  assert.equal(urls.size,routes.length); assert.equal(titles.size,routes.length);
});

test('research groups and the original exercise preserve state without entering metadata', () => {
  const state={study:'retrieval-and-relevance',k:5,ranking:'contrast',need:'implement',domain:'retrieval',direction:'relevance'};
  const url=new URL(seo.routeUrl(state,base,base,true,'#study-lab'),base);
  for(const [key,value] of Object.entries(state)) if(key!=='study') assert.equal(url.searchParams.get(key),String(value));
  const meta=seo.metadata(data,state);
  assert.equal(meta.canonical,seo.site+'study/retrieval-and-relevance/');
  const other=new URL(seo.routeUrl({...state,study:'ams-thesis'},url,base,true),base);
  assert.equal(other.searchParams.get('k'),null);
});

test('ordered index routes retain zero and isolate exercise state from other articles and metadata', () => {
  const state = {study:'what-an-index-learns',dataset:'clustered',mutation:'insert',repair:'rebound',query:0,k:8,ranking:'contrast'};
  for (const physical of [false,true]) {
    const url = new URL(seo.routeUrl(state,base,base,physical,'#study-lab'),base);
    for (const key of ['dataset','mutation','repair','query']) assert.equal(url.searchParams.get(key),String(state[key]));
    assert.equal(url.searchParams.get('k'),null);
    const other = new URL(seo.routeUrl({...state,study:'retrieval-and-relevance'},url,base,physical),base);
    for (const key of ['dataset','mutation','repair','query']) assert.equal(other.searchParams.get(key),null);
    assert.equal(other.searchParams.get('k'),'8');
  }
  assert.equal(seo.metadata(data,state).canonical,seo.site+'study/what-an-index-learns/');
});
