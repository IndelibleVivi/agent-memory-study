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
