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
 for(const mode of ['field','spread','links']){
  const layout=sculpture.layout(model,mode,selected);
  assert.equal(layout.length,model.nodes.length);
  assert.ok(layout.every(pose=>pose.length===7&&pose.every(Number.isFinite)));
 }
 assert.notDeepEqual(sculpture.layout(model,'field',selected),sculpture.layout(model,'spread',selected));
});

test('pointer picking and keyboard rotation share the rendering projection',()=>{
 assert.deepEqual(sculpture.project([0,0,0],0,0,800,500),[400,250,0]);
 const a=sculpture.project([1,0,0],0,0,800,500),b=sculpture.project([1,0,0],Math.PI/2,0,800,500);
 assert.ok(a[0]>400);assert.ok(Math.abs(b[0]-400)<1e-8);
});

test('crossed ribbons select the visible surface using local perspective depth',()=>{
 const back={i:0,p:[5,5,3],curve:[[0,5,0],[10,5,0]],quads:[[[0,4,0],[10,4,0],[0,6,0],[10,6,0]]]};
 const front={i:1,p:[5,5,-3],curve:[[5,0,2],[5,10,2]],quads:[[[4,0,2],[6,0,2],[4,10,2],[6,10,2]]]};
 assert.equal(sculpture.pickObject([back,front],5,5).i,1,'local surface depth must win over the ring centre depth');
 assert.equal(sculpture.pickObject([front,back],2,5).i,0,'the front ring must not steal a nearby uncovered surface');
 assert.equal(sculpture.pickObject([back],10.5,5).i,0,'thin rings retain a nearby hit target');
});

test('the complete current geometry stays inside the stage at allowed viewing angles',()=>{
 const model=sculpture.graph(data),selected=model.nodes.findIndex(x=>x.id==='ams-thesis');
 for(const [width,height] of [[1440,420],[390,250],[320,250]]){
  for(const mode of ['field','spread','links']){
   for(const yaw of [0,.8,1.6,2.4,3.2,4,4.8,5.6])for(const pitch of [-1.2,-.8,-Math.PI/6,-.4,0,.4,Math.PI/6,.8,1.2]){
    for(const pose of sculpture.layout(model,mode,selected))for(let angle=0;angle<Math.PI*2;angle+=.3){
     const [x,y]=sculpture.project(sculpture.ribbonPoint(pose,angle,1),yaw,pitch,width,height);
     assert.ok(x>=0&&x<=width&&y>=0&&y<=height,`${mode} clipped at ${width}×${height}, ${yaw}/${pitch}`);
    }
   }
  }
 }
});

test('spread geometry stays visible across corpus growth and transitions to other views',()=>{
 for(const count of [1,51,128,257]){
  const model=sculpture.graph({studies:Array.from({length:count},(_,i)=>({id:`growth-${i}`}))});
  const spread=sculpture.layout(model,'spread',0);
  const poses=[...spread];
  for(const mode of ['field','links']){
   const other=sculpture.layout(model,mode,0);
   poses.push(...other);
   for(const t of [.25,.5,.75])poses.push(...spread.map((pose,i)=>pose.map((v,j)=>v+(other[i][j]-v)*t)));
  }
  for(const [width,height] of [[1440,420],[390,250],[320,250]]){
   for(const yaw of [0,Math.PI/2,Math.PI,Math.PI*1.5])for(const pitch of [-1.2,-Math.PI/6,0,Math.PI/6,1.2]){
    for(const pose of poses)for(const side of [-1,1])for(let angle=0;angle<Math.PI*2;angle+=.3){
     const [x,y]=sculpture.project(sculpture.ribbonPoint(pose,angle,side),yaw,pitch,width,height);
     assert.ok(x>=0&&x<=width&&y>=0&&y<=height,`growth ${count} clipped at ${width}×${height}, ${yaw}/${pitch}`);
    }
   }
  }
 }
});
