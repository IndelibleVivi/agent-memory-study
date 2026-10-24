const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {spawnSync} = require('node:child_process');
const desk = require('../assets/study-desk.js');
const packets = require('../assets/study-packets.js');
const data = require('../data/materials.json');
const cli = path.join(__dirname, 'export_study.cjs');
function run(...args) { return spawnSync(process.execPath, [cli, ...args], {encoding:'utf8'}); }

test('ordered multi-object CLI matches the shared public projection', () => {
  const refs = [{kind:'study',id:'retrieval-and-relevance'}, {kind:'material',id:'agm-theory-change'}];
  const result = run('--select','study:retrieval-and-relevance','--select','material:agm-theory-change','--format','json');
  assert.equal(result.status,0,result.stderr);
  assert.deepEqual(JSON.parse(result.stdout),packets.collection(data,refs));
  const md = run('--select','study:retrieval-and-relevance','--select','material:agm-theory-change','--format','markdown');
  assert.equal(md.status,0,md.stderr); assert.equal(md.stdout,packets.collectionMarkdown(packets.collection(data,refs)));
});
test('workspace CLI reads identities without publishing any private content or old snapshots', () => {
  const dir=fs.mkdtempSync(path.join(os.tmpdir(),'ams-export-'));
  try {
    const work=desk.add(desk.emptyWorkspace(),{kind:'study',id:'retrieval-and-relevance'},data);
    for(const key of ['title','question','synthesis','next'])work[key]='PRIVATE-SENTINEL';
    work.items[0].note='PRIVATE-SENTINEL'; work.items[0].basis='OLD-SNAPSHOT-SENTINEL';
    const input=path.join(dir,'work.json');fs.writeFileSync(input,JSON.stringify(work));
    for(const format of ['json','markdown']) {
      const result=run('--workspace',input,'--format',format);
      assert.equal(result.status,0,result.stderr);
      assert.ok(!result.stdout.includes('PRIVATE-SENTINEL'));
      assert.ok(!result.stdout.includes('OLD-SNAPSHOT-SENTINEL'));
      assert.ok(result.stdout.includes('retrieval-and-relevance'));
    }
  } finally { fs.rmSync(dir,{recursive:true,force:true}); }
});
test('ambiguous modes, malformed selectors and unknown objects fail without stdout', () => {
  for(const args of [
    ['--kind','study','--id','retrieval-and-relevance','--select','study:ams-thesis'],
    ['--select','study:../private'],['--select','__proto__:ams-thesis'],['--select','study:absent']
  ]) { const r=run(...args,'--format','json'); assert.notEqual(r.status,0);assert.equal(r.stdout,''); }
});
test('an existing output survives export unchanged', () => {
  const dir=fs.mkdtempSync(path.join(os.tmpdir(),'ams-export-'));
  try {
    const output=path.join(dir,'packet.md');fs.writeFileSync(output,'KEEP');
    const result=run('--select','study:ams-thesis','--format','markdown','--out',output);
    assert.notEqual(result.status,0);assert.equal(fs.readFileSync(output,'utf8'),'KEEP');
  } finally { fs.rmSync(dir,{recursive:true,force:true}); }
});
