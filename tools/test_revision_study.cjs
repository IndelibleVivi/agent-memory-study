const {test} = require('node:test');
const assert = require('node:assert/strict');
const {select, run} = require('../assets/revision-study.js');
const study = require('../data/materials.json').studies[0];
const scenario = id => study.scenarios.find(item => item.id === id);

test('correction changes advice without giving the policy its environment answer', () => {
  const s = scenario('corrected');
  assert.equal(run(s, 'scoped', 'before').verdict, 'mismatch');
  assert.equal(run(s, 'scoped', 'after').verdict, 'accepted');
  const altered = structuredClone(s);
  altered.environment.after = '--format';
  assert.equal(run(altered, 'scoped', 'after').flag, '--output');
  assert.equal(run(altered, 'scoped', 'after').verdict, 'mismatch');
});
test('new version must not overwrite a still-valid old task', () => {
  assert.equal(run(scenario('legacy'), 'latest', 'after').verdict, 'mismatch');
  assert.equal(run(scenario('legacy'), 'scoped', 'after').verdict, 'accepted');
});
test('withdrawing one support preserves another; history remains inspectable', () => {
  const result = run(scenario('alternative-support'), 'scoped', 'after');
  assert.deepEqual(result.supports, ['example-v1']);
  assert.equal(result.verdict, 'accepted');
  assert.equal(result.evidence.length, 2);
  assert.equal(result.evidence[0].active, false);
});
test('no support and conflict are distinct abstentions, neither completes the task', () => {
  assert.equal(run(scenario('withdrawn'), 'scoped', 'after').reason, 'no-support');
  const conflict = run(scenario('conflict'), 'scoped', 'after');
  assert.equal(conflict.reason, 'conflict');
  assert.equal(conflict.verdict, 'abstained');
  assert.equal(run(scenario('conflict'), 'frozen', 'after').verdict, 'accepted');
});
test('wrong scope metadata defeats scoped reconstruction', () => {
  assert.equal(run(scenario('mislabelled-scope'), 'scoped', 'after').verdict, 'mismatch');
});
test('selection uses supplied evidence; frozen ignores withdrawals, none gives no advice', () => {
  const s = scenario('withdrawn');
  assert.deepEqual(run(s, 'frozen', 'after').supports, ['draft-v2']);
  assert.equal(run(s, 'none', 'after').reason, 'no-memory');
  assert.equal(select('scoped', 'v9', [{id:'a',scope:'v8',flag:'--format',active:true}], []).reason, 'no-support');
});
test('all declared cases and policies execute deterministically without mutating fixtures', () => {
  const before = JSON.stringify(study);
  for (const s of study.scenarios) for (const p of study.policies) for (const phase of ['before','after']) {
    assert.deepEqual(run(s,p.id,phase),run(s,p.id,phase));
  }
  assert.equal(JSON.stringify(study),before);
});
