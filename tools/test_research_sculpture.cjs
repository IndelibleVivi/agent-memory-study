const test=require('node:test');
const assert=require('node:assert/strict');
const sculpture=require('../assets/continuity-sculpture.js');
const data=require('../data/materials.json');

test('the sculpture uses real public identities and only explicit known links',()=>{
 const model=sculpture.graph({studies:[{id:'one',title:'One',readings:[{materialId:'source'}],bodyHtml:'<a href="?study=two">Two</a><a href="https://example.org/?study=alien">External</a>'},{id:'two',title:'Two',continuation:{studyIds:['one'],materialIds:['missing']}}],materials:[{id:'source',title:'Source'}]});
 assert.deepEqual(model.nodes.map(x=>x.key),['study/one','study/two','material/source']);
 assert.deepEqual([...sculpture.neighbors(model,0)].sort(),[1,2]);
 assert.equal(model.edges.length,2,'reciprocal references must not duplicate a connection');
});

test('all public object families participate; selections preserve their route identity',()=>{
 const model=sculpture.graph(data);
 assert.equal(model.nodes.length,data.materials.length+data.studies.length+data.questions.length+data.findings.length);
 assert.equal(new Set(model.nodes.map(x=>x.key)).size,model.nodes.length);
 const thesis=model.nodes.findIndex(x=>x.id==='ams-thesis');
 assert.ok([...sculpture.neighbors(model,thesis)].some(i=>model.nodes[i].id==='how-we-study'));
 assert.ok(model.nodes.some(x=>x.kind==='finding'));
});

test('the relation view exposes only the selection and its explicit neighbors',()=>{
 const model=sculpture.graph(data),selected=model.nodes.findIndex(x=>x.id==='ams-thesis');
 const nearby=sculpture.neighbors(model,selected),poses=sculpture.layout(model,'links',selected);
 poses.forEach((pose,i)=>assert.equal(pose[6]===1,i===selected||nearby.has(i)));
 for(const mode of ['stack','spread','links']){
  const layout=sculpture.layout(model,mode,selected);
  assert.equal(layout.length,model.nodes.length);
  assert.ok(layout.every(pose=>pose.length===7&&pose.every(Number.isFinite)));
 }
 assert.notDeepEqual(sculpture.layout(model,'stack',selected),sculpture.layout(model,'spread',selected));
});

test('pointer picking and keyboard rotation share the rendering projection',()=>{
 assert.deepEqual(sculpture.project([0,0,0],0,0,800,500),[400,250,0]);
 const a=sculpture.project([1,0,0],0,0,800,500),b=sculpture.project([1,0,0],Math.PI/2,0,800,500);
 assert.ok(a[0]>400);assert.ok(Math.abs(b[0]-400)<1e-8);
});
