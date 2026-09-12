const {test} = require('node:test');
const assert = require('node:assert/strict');
const search = require('../assets/reading-search.js');
const data = require('../data/materials.json');
const index = search.buildIndex(data);

test('a shared reading can be found by its exact title', () => {
  const hits = search.search(index, '一条更正之后');
  assert.equal(hits[0].kind, 'study');
  assert.equal(hits[0].item.id, 'after-a-correction');
});

test('AND tokens can match title and author; NFKC and whitespace normalize', () => {
  for (const q of ['TRUSTMEM Yang', '  ｔｒｕｓｔｍｅｍ\tＹＡＮＧ  ']) {
    const hits = search.search(index, q);
    assert.equal(hits[0].item.id, 'trustmem-consolidation');
    assert.ok(hits[0].matchLabels.includes('标题'));
    assert.ok(hits[0].matchLabels.includes('作者'));
  }
  assert.equal(search.search(index, 'TRUSTMEM NONEXISTENTTERM123').length, 0);
});

test('metadata and URLs are not ordinary search content', () => {
  const fake = {materials: [{id:'secret-id', title:'Readable title', authors:['Ada'],
    noteDepth:'worked', sourceUrl:'https://example.test/hidden-url',
    categories:[], failureSurfaces:[], designTransfer:{status:'proposed-not-run'}}], studies:[]};
  const i = search.buildIndex(fake);
  for (const q of ['secret-id', 'hidden-url', 'proposed-not-run', 'noteDepth']) assert.equal(search.search(i,q).length,0);
  assert.equal(search.search(i,'Ada').length,1);
});

test('an exact title outranks a body mention and ordering is deterministic', () => {
  const fake = {materials: [
    {id:'body',title:'Another',authors:[],intro:'Target exact'},
    {id:'title',title:'Target exact',authors:[]},
  ],studies:[]};
  const i = search.buildIndex(fake);
  assert.deepEqual(search.search(i,'Target exact').map(r=>r.item.id), ['title','body']);
  assert.deepEqual(search.search(i,'Target exact'), search.search(i,'Target exact'));
});

test('study facets must be satisfied by the same referenced material', () => {
  const fake = {materials:[
    {id:'a',title:'A',authors:[],categories:['x'],failureSurfaces:['s'],noteDepth:'read'},
    {id:'b',title:'B',authors:[],categories:['y'],failureSurfaces:['s'],noteDepth:'worked'},
  ],studies:[{id:'study',title:'Shared',readings:[{materialId:'a'},{materialId:'b'}]}]};
  const i=search.buildIndex(fake);
  assert.equal(search.search(i,'Shared',{topic:'x',depth:'worked'}).length,0);
  assert.equal(search.search(i,'Shared',{topic:'x',depth:'read'}).length,1);
  assert.equal(search.search(i,'Shared',{surface:'s'}).length,1);
});

test('plain snippets are bounded and do not manufacture highlights or HTML', () => {
  const fake={materials:[{id:'x',title:'x',authors:[],intro:'<img src=x onerror=alert(1)> '+ 'long '.repeat(150) + 'needle'}],studies:[]};
  const i=search.buildIndex(fake);
  const h=search.search(i,'needle')[0];
  assert.ok(h.snippet.text.includes('needle')); assert.ok(h.snippet.text.length<=147);
  assert.ok(search.search(i,'onerror')[0].snippet.text.includes('<img'));
});

test('empty query preserves inventory and audit prose stays discoverable', () => {
  assert.equal(search.search(index,'').length, data.materials.length+data.studies.length);
  const h=search.search(index,'428')[0];
  assert.equal(h.item.id,'statefuse-conflict-preserving-memory');
  assert.ok(h.matchLabels.some(l=>l.includes('AMS') || l.includes('测试')));
});

test('unknown filters and absent studies fail closed without changing the data', () => {
  const before=JSON.stringify(data);
  assert.equal(search.search(index,'',{depth:'made-up'}).length,0);
  search.search(index,'mEmOrY',{surface:'retrieval-active-context'});
  assert.equal(JSON.stringify(data),before);
  assert.equal(search.buildIndex({materials:[]}).length,0);
});
