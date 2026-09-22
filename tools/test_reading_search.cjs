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
  const total = data.materials.length + data.studies.length
    + (data.questions || []).length + (data.findings || []).length;
  assert.equal(search.search(index,'').length, total);
  const h=search.search(index,'428')[0];
  assert.equal(h.item.id,'statefuse-conflict-preserving-memory');
  assert.ok(h.matchLabels.some(l=>l.includes('AMS') || l.includes('测试')));
});

test('questions and findings are indexed by human prose, facets by materialIds', () => {
  const fake={materials:[
    {id:'m1',title:'Material one',authors:[],categories:['x'],failureSurfaces:[],noteDepth:'read'},
  ],studies:[],questions:[{
    id:'q1',title:'Question title',question:'问题正文关键词',intro:'',judgment:'',byline:'Desk',
    updated:'2026-09-21',status:'open',
    explanations:[{title:'解释标题',text:'解释正文关键词'}],
    evidence:[{label:'证据标签词',url:'https://example.org/e',observation:'观察正文关键词',limit:'边界正文关键词'}],
    materialIds:['m1'],studyIds:[],findingIds:['f1'],
    nextTest:{question:'下一个测试关键词',comparison:'c',success:'s',reviseWhen:'r',boundary:'b'},
  }],findings:[{
    id:'f1',title:'Finding title',byline:'Desk',updated:'2026-09-21',status:'proposed-transfer',
    questionIds:['q1'],materialIds:['m1'],triggers:['触发词'],
    claim:'主张关键词',when:'w',action:'a',avoid:'av',validation:'v',limit:'l',
    evidence:[{label:'证据标签',url:'https://example.org/e',observation:'观察',limit:'边界'}],
    applications:[{title:'应用标题词',status:'cited',date:'2026-09-21',url:'https://example.org/a',
      decision:'决定关键词',observation:'o',limit:'边界'}],
  }]};
  const i=search.buildIndex(fake);
  assert.equal(search.search(i,'问题正文关键词')[0].kind,'question');
  assert.equal(search.search(i,'解释正文关键词')[0].kind,'question');
  assert.equal(search.search(i,'下一个测试关键词')[0].kind,'question');
  assert.equal(search.search(i,'主张关键词')[0].kind,'finding');
  assert.equal(search.search(i,'触发词')[0].kind,'finding');
  assert.equal(search.search(i,'决定关键词')[0].kind,'finding');
  // same-material facet filtering uses materialIds
  assert.equal(search.search(i,'问题正文关键词',{topic:'x'}).length,1);
  assert.equal(search.search(i,'主张关键词',{depth:'read'}).length,1);
  assert.equal(search.search(i,'主张关键词',{depth:'worked'}).length,0);
  // statuses, ids and URLs stay out of the index
  for (const q of ['proposed-transfer','q1','f1','open','example.org','https']) {
    assert.equal(search.search(i,q).length,0,q);
  }
});

test('question and finding hits keep deterministic order and bounded snippets', () => {
  const fake={materials:[{id:'m1',title:'M',authors:[],categories:[],failureSurfaces:[],noteDepth:'read'}],
    studies:[],questions:[{id:'q1',title:'Shared keyword',question:'x',intro:'body keyword here',
      judgment:'',byline:'',updated:'2026-09-21',status:'open',explanations:[],evidence:[],materialIds:['m1'],studyIds:[],findingIds:[],
      nextTest:{question:'',comparison:'',success:'',reviseWhen:'',boundary:''}}],findings:[]};
  const i=search.buildIndex(fake);
  assert.deepEqual(search.search(i,'Shared keyword'), search.search(i,'Shared keyword'));
  const hit=search.search(i,'keyword')[0];
  assert.ok(hit.snippet.text.length<=147);
});

test('unknown filters and absent studies fail closed without changing the data', () => {
  const before=JSON.stringify(data);
  assert.equal(search.search(index,'',{depth:'made-up'}).length,0);
  search.search(index,'mEmOrY',{surface:'retrieval-active-context'});
  assert.equal(JSON.stringify(data),before);
  assert.equal(search.buildIndex({materials:[]}).length,0);
});


test('cross-source readings are searchable without treating source URLs as prose', () => {
  const hits = search.search(index, 'jevlike');
  assert.ok(hits.some(hit => hit.kind === 'study' && hit.item.id === 'experience-becomes-policy'));
  const fake = {materials:[], studies:[{id:'cross-source',title:'A study',readings:[],
    externalReadings:[{label:'Implementation entry',kind:'Source code',locator:'README only',
      takeaway:'Option attention',limit:'Not reproduced',url:'https://example.org/secret-source-path'}]}]};
  const idx = search.buildIndex(fake);
  assert.equal(search.search(idx, 'attention README').length, 1);
  assert.equal(search.search(idx, 'secret-source-path').length, 0);
});

test('Jev reading and source study can be found through their memory boundary', () => {
  const hits = search.search(index, 'Jev obsolete');
  assert.ok(hits.some(hit => hit.kind === 'material' && hit.item.id === 'jev-mem-system-one-control'));
  assert.ok(hits.some(hit => hit.kind === 'study' && hit.item.id === 'who-controls-memory'));
});
