const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const researchMap = require('../assets/research-map.js');
const data = require('../data/materials.json');

function edgeKeys(model) {
  return model.edges.map(edge => edge.map(index => model.nodes[index].key).sort().join(' | ')).sort();
}

function hasEdge(model, first, second) {
  return edgeKeys(model).includes([first, second].sort().join(' | '));
}

function minimumDistance(positions) {
  let minimum = Infinity;
  for (let i = 0; i < positions.length; i++) {
    for (let j = 0; j < i; j++) {
      minimum = Math.min(minimum, Math.hypot(positions[i].x - positions[j].x, positions[i].y - positions[j].y));
    }
  }
  return minimum;
}

function checkGeometry(layout, count, separation = 26) {
  assert.equal(layout.positions.length, count);
  const margin = Math.min(44, layout.width * .08, layout.height * .08);
  for (const point of [...layout.positions, ...layout.groups]) {
    assert.ok(Number.isFinite(point.x) && Number.isFinite(point.y), 'coordinates must be finite');
    assert.ok(point.x >= margin && point.x <= layout.width - margin, 'x must stay inside the useful margin');
    assert.ok(point.y >= margin && point.y <= layout.height - margin, 'y must stay inside the useful margin');
  }
  assert.ok(minimumDistance(layout.positions) >= separation,
    `node centers must remain clickable: minimum ${minimumDistance(layout.positions)}`);
}

function freeze(value) {
  if (value && typeof value === 'object') {
    Object.values(value).forEach(freeze);
    Object.freeze(value);
  }
  return value;
}

test('graph follows typed references and compiler anchors, with no dangling, self, duplicate, or inferred edges', () => {
  const input = {
    studies: [
      {
        id: 'one', title: 'Shared subject', studyIds: ['one'], materialIds: ['source', 'missing'],
        questionIds: ['question'], findingIds: ['finding'],
        continuation: {studyIds: ['two'], materialIds: ['continued-source']},
        readings: [{materialId: 'source'}, {materialId: 'missing'}],
        bodyHtml: '<a href="?study=body%2Dlinked&amp;phase=after#section">Internal</a>' +
          '<a href="?study=one">Self</a><a href="?study=missing">Dangling</a>' +
          '<a href="https://example.org/?study=external">External</a>' +
          '<a href="//example.org/?study=external">External</a>' +
          '<a href="/study/external/">A non-compiler route</a>' +
          '<span data-href="?study=external">Not an anchor</span>' +
          '<a data-href="?study=external" href="https://example.org/">Not href</a>'
      },
      {id: 'two', title: 'Two', continuation: {studyIds: ['one']}},
      {id: 'body-linked', title: 'Body linked'},
      {id: 'external', title: 'Shared subject'}
    ],
    materials: [{id: 'source', studyIds: ['one']}, {id: 'continued-source'}],
    questions: [{id: 'question', findingIds: ['finding']}],
    findings: [{id: 'finding', questionIds: ['question']}]
  };
  const model = researchMap.graph(input);
  const expected = [
    ['study/one', 'material/source'], ['study/one', 'material/continued-source'],
    ['study/one', 'study/two'], ['study/one', 'study/body-linked'],
    ['study/one', 'question/question'], ['study/one', 'finding/finding'],
    ['question/question', 'finding/finding']
  ].map(edge => edge.sort().join(' | ')).sort();
  assert.deepEqual(edgeKeys(model), expected);
  assert.deepEqual([...researchMap.neighbors(model, 0)].sort((a, b) => a - b), [1, 2, 4, 5, 6, 7]);
  assert.equal(researchMap.neighbors(model, 3).size, 0, 'matching titles and external links create no relationship');
  assert.equal(researchMap.neighbors(model, -1).size, 0);
});

test('all current public objects retain their identity and representative explicit connections', () => {
  const model = researchMap.graph(data);
  assert.equal(model.nodes.length, 47);
  assert.deepEqual(Object.fromEntries(['study', 'material', 'question', 'finding'].map(kind =>
    [kind, model.nodes.filter(node => node.kind === kind).length])), {study: 13, material: 27, question: 2, finding: 5});
  assert.equal(new Set(model.nodes.map(node => node.key)).size, model.nodes.length);
  assert.equal(new Set(edgeKeys(model)).size, model.edges.length);
  model.edges.forEach(([from, to]) => {
    assert.ok(Number.isInteger(from) && from >= 0 && from < model.nodes.length);
    assert.ok(Number.isInteger(to) && to >= 0 && to < model.nodes.length);
    assert.notEqual(from, to);
  });
  for (const [first, second] of [
    ['study/ams-thesis', 'study/how-we-study'],
    ['study/after-a-correction', 'material/truth-maintenance-system'],
    ['study/retrieval-and-relevance', 'study/what-an-index-learns'],
    ['study/future-questions-and-memory', 'study/forms-of-experience'],
    ['study/future-questions-and-memory', 'material/fluctlightdb-observation-binding'],
    ['question/experience-becomes-policy', 'study/experience-becomes-policy'],
    ['question/experience-to-capability', 'finding/revision-needs-scope'],
    ['finding/output-guard-is-not-unlearning', 'material/cache-to-cache']
  ]) assert.ok(hasEdge(model, first, second), `missing public relationship: ${first} / ${second}`);
  assert.equal(hasEdge(model, 'question/experience-becomes-policy', 'question/experience-to-capability'), false,
    'a general evidence URL does not become a compiler or typed-ID reference');
  const families = {study: 'studies', material: 'materials', question: 'questions', finding: 'findings'};
  for (const node of model.nodes) {
    assert.equal(node.item, data[families[node.kind]].find(item => item.id === node.id));
    assert.equal(node.title, node.item.title);
    assert.equal(node.summary, node.kind === 'finding' ? node.item.claim : node.item.intro);
  }
});

test('domain membership is the ordered union of explicit metadata and typed map membership', () => {
  const input = freeze({
    room: {domains: [
      {id: 'beta', title: 'Beta', materialIds: ['same'], findingIds: ['finding']},
      {id: 'alpha', title: 'Alpha', studyIds: ['same', 'second']}
    ]},
    studies: [
      {id: 'same', title: 'A study', domains: ['alpha', 'beta', 'alpha', 'unknown'], intro: 'Original intro'},
      {id: 'second', title: 'Second', materialIds: ['same']}
    ],
    materials: [{id: 'same', title: 'A material'}],
    questions: [{id: 'question', title: 'Alpha and Beta', materialIds: ['same']}],
    findings: [{id: 'finding', title: 'Finding', claim: 'Original claim'}]
  });
  const model = researchMap.graph(input);
  assert.deepEqual(model.nodes.map(node => [node.key, node.domainIds, node.primaryDomain]), [
    ['study/same', ['beta', 'alpha'], 'beta'], ['study/second', ['alpha'], 'alpha'],
    ['material/same', ['beta'], 'beta'], ['question/question', [], null],
    ['finding/finding', ['beta'], 'beta']
  ]);
  assert.equal(model.nodes[0].item, input.studies[0], 'retain the original item without adding fields');
  assert.equal(model.nodes[0].summary, 'Original intro');
  assert.equal(model.nodes[4].summary, 'Original claim');
  assert.equal(model.nodes[1].summary, '');
  assert.deepEqual(model, researchMap.graph(input));
  assert.equal(hasEdge(model, 'study/second', 'study/same'), false, 'shared domain membership is not a citation');
});

test('current multiple memberships and unclassified objects remain explicit', () => {
  const model = researchMap.graph(data);
  const node = key => model.nodes.find(item => item.key === key);
  assert.deepEqual(node('study/records-representations-systems').domainIds, ['data', 'representation', 'indexing', 'memory']);
  assert.deepEqual(node('study/relevance-in-context').domainIds, ['indexing', 'retrieval', 'control', 'evaluation']);
  assert.deepEqual(node('material/insightemb-action-intent-retrieval').domainIds, ['representation', 'retrieval']);
  assert.deepEqual(node('study/ams-thesis').domainIds, []);
  assert.equal(node('study/ams-thesis').primaryDomain, null);
  assert.ok(model.nodes.filter(item => item.kind === 'finding').every(item => item.primaryDomain === null));
});

test('current layout is bounded, well separated, deterministic, and independent of graph edges', () => {
  const model = researchMap.graph(data);
  const before = JSON.stringify(model);
  const layout = researchMap.clusterLayout(model, data.room.domains);
  assert.equal(layout.width, 1200);
  assert.equal(layout.height, 720);
  assert.deepEqual(layout.groups.map(group => group.id), [...data.room.domains.map(domain => domain.id), 'unclassified']);
  data.room.domains.forEach((domain, index) => {
    assert.equal(layout.groups[index].title, domain.title);
    assert.equal(layout.groups[index].english, domain.english);
  });
  checkGeometry(layout, model.nodes.length);
  assert.deepEqual(layout, researchMap.clusterLayout(model, data.room.domains));
  assert.deepEqual(layout, researchMap.clusterLayout({...model, edges: []}, data.room.domains),
    'connections must not be treated as similarity forces');
  assert.equal(JSON.stringify(model), before, 'layout must not mutate the graph or its original items');
  checkGeometry(researchMap.clusterLayout(model, data.room.domains, 800, 480), model.nodes.length);
});

test('primary domain places a node in its own cluster without losing secondary membership', () => {
  const domains = [{id: 'first', title: 'First'}, {id: 'second', title: 'Second'}];
  const model = researchMap.graph({room: {domains}, studies: [
    {id: 'a', domains: ['second', 'first']}, {id: 'b', domains: ['first']},
    {id: 'c', domains: ['second']}, {id: 'd', domains: ['second']}
  ]});
  const layout = researchMap.clusterLayout(model, domains);
  assert.deepEqual(model.nodes[0].domainIds, ['first', 'second']);
  assert.ok(layout.positions.slice(0, 2).every(point => point.x < layout.width / 2));
  assert.ok(layout.positions.slice(2).every(point => point.x > layout.width / 2));
  assert.ok(layout.groups[0].x < layout.width / 2 && layout.groups[1].x > layout.width / 2);
  checkGeometry(layout, 4);
});

test('skewed groups, empty domains, unclassified nodes, and modest growth keep usable geometry', () => {
  for (const sizes of [[1, 1, 1, 1, 1, 1, 1, 120], [15, 15, 15, 15, 15, 15, 15, 15], [0, 0, 0, 120, 0, 0, 0, 0]]) {
    const domains = sizes.map((size, index) => ({id: `domain-${index}`, title: `Domain ${index}`}));
    const input = {room: {domains}, studies: sizes.flatMap((size, group) =>
      Array.from({length: size}, (_, index) => ({id: `${group}-${index}`, domains: [`domain-${group}`]}))),
    findings: Array.from({length: 6}, (_, index) => ({id: `unclassified-${index}`}))};
    const model = researchMap.graph(input);
    const layout = researchMap.clusterLayout(model, domains);
    assert.equal(layout.groups.length, 9);
    checkGeometry(layout, model.nodes.length);
    assert.deepEqual(layout, researchMap.clusterLayout(model, domains));
  }
});

test('empty and entirely unclassified inputs work without inventing a subject', () => {
  assert.deepEqual(researchMap.graph(), {nodes: [], edges: []});
  assert.deepEqual(researchMap.clusterLayout(researchMap.graph(), []), {width: 1200, height: 720, groups: [], positions: []});
  const emptyDomains = researchMap.clusterLayout({nodes: [], edges: []}, [{id: 'empty', title: 'Empty'}]);
  assert.equal(emptyDomains.groups.length, 1);
  checkGeometry(emptyDomains, 0);
  for (const count of [1, 2, 20, 100]) {
    const model = researchMap.graph({studies: Array.from({length: count}, (_, index) => ({id: `s-${index}`}))});
    const layout = researchMap.clusterLayout(model, []);
    assert.equal(layout.groups.length, 1);
    assert.equal(layout.groups[0].id, 'unclassified');
    assert.ok(model.nodes.every(node => node.primaryDomain === null && node.domainIds.length === 0));
    checkGeometry(layout, count);
  }
});

test('invalid dimensions fall back and tiny view boxes still produce finite contained points', () => {
  const model = researchMap.graph({studies: [{id: 'a'}, {id: 'b'}]});
  assert.deepEqual(researchMap.clusterLayout(model, [], Infinity, -10), researchMap.clusterLayout(model, []));
  const tiny = researchMap.clusterLayout(model, [], 10, 8);
  assert.equal(tiny.width, 10);
  assert.equal(tiny.height, 8);
  checkGeometry(tiny, 2, 0);
});

test('the same pure API loads in a browser global without DOM, network, or storage', () => {
  const context = vm.createContext({URLSearchParams});
  const source = fs.readFileSync(path.join(__dirname, '../assets/research-map.js'), 'utf8');
  vm.runInContext(source, context);
  assert.deepEqual(Object.keys(context.ResearchMap).sort(), ['clusterLayout', 'graph', 'neighbors']);
  const model = context.ResearchMap.graph({studies: [{id: 'one', bodyHtml: '<a href="?material=source">Source</a>'}], materials: [{id: 'source'}]});
  assert.equal(model.nodes.length, 2);
  assert.equal(model.edges.length, 1);
  checkGeometry(context.ResearchMap.clusterLayout(model, []), 2);
});
