'use strict';
/* Behaviour tests for the shared practice query/brief and the CLI.
 *
 * Synthetic controls check candidate identity and scope; canonical queries
 * check the public examples against the real content.
 */
const {test} = require('node:test');
const assert = require('node:assert/strict');
const {execFileSync} = require('node:child_process');
const {mkdtempSync, readFileSync, writeFileSync} = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const Practice = require('../assets/practice.js');

const CLI = path.join(__dirname, 'export_practice.cjs');
const CANONICAL = path.join(__dirname, '..', 'data', 'materials.json');

function evidence(label, url) {
  return {label, url, observation: `Observation for ${label}.`, limit: `Limit for ${label}.`};
}

function application(title, url) {
  return {
    title, status: 'adopted', date: '2026-09-21', url,
    decision: `Decision for ${title}.`, observation: `Observation for ${title}.`, limit: `Limit for ${title}.`,
  };
}

const FINDINGS = [
  {
    id: 'retrieval-candidate-competition',
    title: 'Retrieval candidate competition',
    byline: 'Editorial desk',
    updated: '2026-09-21',
    status: 'proposed-transfer',
    questionIds: ['experience-to-capability'],
    materialIds: ['continual-learning-experience-reuse'],
    triggers: ['重复', '候选', '占满', 'duplicate', 'retrieval'],
    claim: 'Deduplicate shared evidence rows before ranking.',
    when: 'When several memory items share one evidence row.',
    action: 'Collapse duplicate evidence rows before ranking.',
    avoid: 'Do not let duplicate rows inflate one candidate.',
    validation: 'Compare candidate counts before and after dedup.',
    limit: 'Lexical and deterministic only.',
    evidence: [evidence('Retrieval competition study', 'research/experience-reuse-retrieval-study/README.md')],
    applications: [application('Local trial', 'research/experience-reuse-retrieval-study/README.md#result')],
  },
  {
    id: 'revision-needs-scope',
    title: 'Revision needs scope',
    byline: 'Editorial desk',
    updated: '2026-09-21',
    status: 'proposed-transfer',
    questionIds: ['experience-to-capability'],
    materialIds: ['truth-maintenance-system'],
    triggers: ['新版', '旧版', '版本', '覆盖', 'revision', 'scope'],
    claim: 'Recompute every dependent claim after a retraction.',
    when: 'After a correction changes a stored fact.',
    action: 'Walk dependents and recompute each one.',
    avoid: 'Never keep a dependent that lost its support.',
    validation: 'Compare dependent sets before and after.',
    limit: 'Scope depends on the recorded dependency graph.',
    evidence: [evidence('Correction scope study', 'research/correction-scope-study/README.md')],
    applications: [],
  },
  {
    id: 'retraction-needs-recomputation',
    title: 'Retraction needs recomputation',
    byline: 'Editorial desk',
    updated: '2026-09-21',
    status: 'proposed-transfer',
    questionIds: [],
    materialIds: ['useful-memories-become-faulty'],
    triggers: ['来源', '删除', '缓存', 'retraction', 'recompute'],
    claim: 'A retraction invalidates derived conclusions.',
    when: 'When a memory item is retracted.',
    action: 'Recompute conclusions that depended on it.',
    avoid: 'Do not present stale conclusions as current.',
    validation: 'List conclusions that changed.',
    limit: 'Requires an explicit dependency record.',
    evidence: [evidence('Faulty memory study', 'research/faulty-memory-release-boundary-audit/README.md')],
    applications: [application('Rejected trial', 'https://example.org/rejected')],
  },
];

function data(findings = FINDINGS) {
  return {materials: [], studies: [], questions: [], findings};
}

test('a natural sentence ranks the intended finding first', () => {
  const hits = Practice.query(data(), '候选增加之后，结果被重复条目占满');
  assert.equal(hits[0].finding.id, 'retrieval-candidate-competition');
  assert.ok(hits[0].score > 0);
  assert.ok(hits[0].matches.includes('重复'));
  assert.ok(hits[0].matches.includes('候选'));
});

test('matches are short strings, not objects', () => {
  const hits = Practice.query(data(), '结果被重复条目占满');
  assert.equal(hits[0].finding.id, 'retrieval-candidate-competition');
  for (const match of hits[0].matches) assert.equal(typeof match, 'string');
});

test('an English problem sentence ranks the intended finding first', () => {
  const hits = Practice.query(data(), 'duplicate candidates crowd out useful retrieval results');
  assert.equal(hits[0].finding.id, 'retrieval-candidate-competition');
});

test('ranking differs by actual relevance instead of a flat score', () => {
  const hits = Practice.query(data(), '重复 候选');
  // Distinct matching units must produce different scores per finding.
  const scores = new Set(hits.map(hit => hit.score));
  assert.ok(hits.length >= 1);
  assert.ok(hits[0].score > 0);
  if (hits.length > 1) assert.ok(scores.size > 1, 'scores should not be identical');
});

test('same-topic different-scope findings stay independent', () => {
  const hits = Practice.query(data(), 'retraction');
  const ids = hits.map(hit => hit.finding.id);
  assert.ok(ids.includes('retraction-needs-recomputation'));
  assert.ok(ids.includes('revision-needs-scope'));
  // The scope-specific query still prefers the scope finding.
  assert.equal(Practice.query(data(), 'revision scope')[0].finding.id, 'revision-needs-scope');
});

test('unrelated and punctuation-only queries return an empty result', () => {
  assert.deepEqual(Practice.query(data(), '量子色动力学完全无关的查询'), []);
  assert.deepEqual(Practice.query(data(), 'zzzzz-qqq'), []);
  // A non-empty query with no lexical units must not dump the whole inventory.
  assert.deepEqual(Practice.query(data(), '...!!!'), []);
  assert.deepEqual(Practice.query(data(), '、、、'), []);
});

test('empty and whitespace queries browse the first findings with score 0', () => {
  for (const q of ['', '   ', '\t\n']) {
    const hits = Practice.query(data(), q);
    assert.equal(hits.length, 3);
    assert.deepEqual(hits.map(hit => hit.finding.id),
      ['retrieval-candidate-competition', 'revision-needs-scope', 'retraction-needs-recomputation']);
    for (const hit of hits) {
      assert.equal(hit.score, 0);
      assert.deepEqual(hit.matches, []);
    }
  }
});

test('duplicate evidence rows do not multiply candidates or inflate rank', () => {
  const base = Practice.query(data(), 'retraction');
  const doubled = FINDINGS.map(finding => ({
    ...finding,
    evidence: [...finding.evidence, ...finding.evidence],
  }));
  const withDoubles = Practice.query(data(doubled), 'retraction');
  assert.deepEqual(withDoubles.map(hit => hit.finding.id), base.map(hit => hit.finding.id));
  assert.deepEqual(withDoubles.map(hit => hit.score), base.map(hit => hit.score));
  // Duplicated prose fields do not add rank either.
  const repeatedProse = FINDINGS.map(finding => ({...finding, claim: `${finding.claim} ${finding.claim}`}));
  const withRepeatedProse = Practice.query(data(repeatedProse), 'retraction');
  assert.deepEqual(withRepeatedProse.map(hit => hit.score), base.map(hit => hit.score));
  // Repeating a query token is also deduplicated.
  const repeated = Practice.query(data(), 'retraction retraction');
  assert.deepEqual(repeated.map(hit => hit.finding.id), base.map(hit => hit.finding.id));
  assert.deepEqual(repeated.map(hit => hit.score), base.map(hit => hit.score));
});

test('limit is deterministic, capped at 3 and zero stays empty', () => {
  const many = Practice.query(data(), 'retraction 重复 版本', 10);
  assert.ok(many.length <= 3);
  assert.deepEqual(many.map(hit => hit.finding.id), Practice.query(data(), 'retraction 重复 版本', 10).map(hit => hit.finding.id));
  assert.equal(Practice.query(data(), 'retraction 重复 版本', 1).length, 1);
  assert.equal(Practice.query(data(), 'retraction 重复 版本', 2).length, 2);
  assert.equal(Practice.query(data(), 'result sets many', 10).length <= 3, true);
  assert.equal(Practice.query(data(), '重复', 0).length, 0);
  assert.equal(Practice.query(data(), '   ', 0).length, 0);
});

test('query does not mutate canonical data', () => {
  const canonical = data();
  const before = JSON.stringify(canonical);
  Practice.query(canonical, 'retraction');
  Practice.brief(canonical, 'retraction');
  assert.equal(JSON.stringify(canonical), before);
});

test('brief exposes boundary, method and portable absolute URLs', () => {
  const briefing = Practice.brief(data(), '候选增加之后，结果被重复条目占满');
  assert.equal(briefing.method, 'local-lexical-query');
  assert.equal(briefing.browse, false);
  assert.equal(briefing.boundary.inference, 'none');
  assert.equal(briefing.boundary.network, 'none');
  const finding = briefing.findings[0];
  assert.ok(finding.evidence[0].url.startsWith('https://indeliblevivi.github.io/agent-memory-study/'));
  assert.ok(finding.applications[0].url.includes('#result'));
  assert.ok(finding.readerUrl.includes('finding=retrieval-candidate-competition'));
});

test('brief preserves provenance via linked material and question ids', () => {
  const briefing = Practice.brief(data(), '候选增加之后，结果被重复条目占满');
  assert.deepEqual(briefing.findings[0].materialIds, ['continual-learning-experience-reuse']);
  assert.deepEqual(briefing.findings[0].questionIds, ['experience-to-capability']);
  assert.deepEqual(briefing.findings[0].materialLinks, [
    {id: 'continual-learning-experience-reuse',
      url: 'https://indeliblevivi.github.io/agent-memory-study/?material=continual-learning-experience-reuse'},
  ]);
  assert.deepEqual(briefing.findings[0].questionLinks, [
    {id: 'experience-to-capability',
      url: 'https://indeliblevivi.github.io/agent-memory-study/?question=experience-to-capability'},
  ]);
});

test('empty-query brief marks browse mode and labels it in markdown', () => {
  const briefing = Practice.brief(data(), '');
  assert.equal(briefing.browse, true);
  assert.equal(briefing.findings.length, 3);
  const md = Practice.markdown(briefing);
  assert.ok(md.includes('empty query'));
});

test('unknown finding id fails clearly and exact export does not rank', () => {
  assert.throws(() => Practice.brief(data(), '', {findingId: 'nope'}), /Unknown finding id: nope/);
  const exact = Practice.brief(data(), '', {findingId: 'retraction-needs-recomputation'});
  assert.equal(exact.findings.length, 1);
  assert.equal(exact.boundary.ranking, 'none (exact canonical id)');
});

test('markdown retains status, limits, all evidence and application results', () => {
  const briefing = Practice.brief(data(), '', {findingId: 'retrieval-candidate-competition'});
  const md = Practice.markdown(briefing);
  for (const token of ['proposed-transfer', 'Editorial desk', '2026-09-21', 'Claim', 'When', 'Action',
    'Avoid', 'Validation', 'Limit', 'Evidence', 'Applications', 'adopted', 'Reader']) {
    assert.ok(md.includes(token), `markdown missing ${token}`);
  }
  assert.ok(md.includes('Limit for Retrieval competition study'));
  assert.ok(md.includes('Decision for Local trial'));
  // Provenance is linked, not printed as opaque ids.
  assert.ok(md.includes('[continual-learning-experience-reuse](https://indeliblevivi.github.io/agent-memory-study/?material=continual-learning-experience-reuse)'));
  assert.ok(md.includes('[experience-to-capability](https://indeliblevivi.github.io/agent-memory-study/?question=experience-to-capability)'));
  // Evidence and application labels are Markdown links usable outside the checkout.
  assert.ok(md.includes('[Retrieval competition study](https://indeliblevivi.github.io/agent-memory-study/research/experience-reuse-retrieval-study/README.md)'));
  assert.ok(md.includes('[Local trial](https://indeliblevivi.github.io/agent-memory-study/research/experience-reuse-retrieval-study/README.md#result)'));
  const rejected = Practice.markdown(
    Practice.brief(data(), '', {findingId: 'retraction-needs-recomputation'}),
  );
  assert.ok(rejected.includes('rejected'));
});

test('markdown handles an empty result without inventing findings', () => {
  const md = Practice.markdown(Practice.brief(data(), 'zzzzz-nope'));
  assert.ok(md.includes('No finding matched'));
  assert.ok(!md.includes('## '));
});

function runCli(args, options = {}) {
  return execFileSync(process.execPath, [CLI, ...args], {encoding: 'utf8', ...options});
}

function runCliFail(args) {
  try {
    execFileSync(process.execPath, [CLI, ...args], {encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe']});
  } catch (error) {
    return {status: error.status, stderr: String(error.stderr)};
  }
  throw new Error(`expected CLI to fail: ${args.join(' ')}`);
}

test('CLI exports JSON and markdown from another working directory', () => {
  const temp = mkdtempSync(path.join(os.tmpdir(), 'practice-cli-'));
  const fixture = path.join(temp, 'data.json');
  writeFileSync(fixture, JSON.stringify(data()));
  const json = execFileSync(process.execPath,
    [CLI, '--query', '候选增加之后，结果被重复条目占满', '--format', 'json', '--data', fixture],
    {encoding: 'utf8', cwd: os.tmpdir()});
  const parsed = JSON.parse(json);
  assert.equal(parsed.findings[0].id, 'retrieval-candidate-competition');
  const md = execFileSync(process.execPath,
    [CLI, '--finding', 'revision-needs-scope', '--format', 'markdown', '--data', fixture],
    {encoding: 'utf8', cwd: os.tmpdir()});
  assert.ok(md.includes('Revision needs scope'));
});

test('CLI writes to --out when provided', () => {
  const temp = mkdtempSync(path.join(os.tmpdir(), 'practice-cli-'));
  const fixture = path.join(temp, 'data.json');
  writeFileSync(fixture, JSON.stringify(data()));
  const out = path.join(temp, 'brief.md');
  runCli(['--query', 'retraction', '--format', 'markdown', '--out', out, '--data', fixture]);
  assert.ok(readFileSync(out, 'utf8').includes('Retraction'));
});

test('CLI treats an explicit empty query as browse, not an error', () => {
  const temp = mkdtempSync(path.join(os.tmpdir(), 'practice-cli-'));
  const fixture = path.join(temp, 'data.json');
  writeFileSync(fixture, JSON.stringify(data()));
  const briefing = JSON.parse(runCli(['--query', '', '--format', 'json', '--data', fixture]));
  assert.equal(briefing.browse, true);
  assert.equal(briefing.findings.length, 3);
  // A punctuation-only query stays empty rather than browsing.
  const punct = JSON.parse(runCli(['--query', '...!!!', '--format', 'json', '--data', fixture]));
  assert.equal(punct.findings.length, 0);
  assert.equal(punct.browse, false);
});

test('CLI fails helpfully on bad arguments and missing ids', () => {
  const temp = mkdtempSync(path.join(os.tmpdir(), 'practice-cli-'));
  const fixture = path.join(temp, 'data.json');
  writeFileSync(fixture, JSON.stringify(data()));
  const scenarios = [
    ['--query', 'x', '--format', 'yaml', '--data', fixture],
    ['--format', 'json', '--data', fixture],
    ['--query', 'x', '--format', 'json', '--limit', '0', '--data', fixture],
    ['--query', 'x', '--format', 'json', '--bogus', '1', '--data', fixture],
    ['--finding', 'does-not-exist', '--format', 'json', '--data', fixture],
    ['--query', 'x', '--finding', 'y', '--format', 'json', '--data', fixture],
    ['--query', 'x', '--format', 'json', '--data', path.join(temp, 'missing.json')],
  ];
  for (const args of scenarios) {
    const result = runCliFail(args);
    assert.notEqual(result.status, 0, args.join(' '));
    assert.ok(result.stderr.length > 0, args.join(' '));
  }
  const missingId = runCliFail(['--finding', 'does-not-exist', '--format', 'json', '--data', fixture]);
  assert.match(missingId.stderr, /Unknown finding id/);
});

test('CLI reads canonical data fresh each invocation', () => {
  const temp = mkdtempSync(path.join(os.tmpdir(), 'practice-cli-'));
  const fixture = path.join(temp, 'data.json');
  writeFileSync(fixture, JSON.stringify(data([FINDINGS[0]])));
  const first = JSON.parse(runCli(['--query', '重复 候选', '--format', 'json', '--data', fixture]));
  assert.equal(first.findings.length, 1);
  writeFileSync(fixture, JSON.stringify(data([FINDINGS[1], FINDINGS[2]])));
  const second = JSON.parse(runCli(['--query', 'retraction', '--format', 'json', '--data', fixture]));
  assert.deepEqual(
    second.findings.map(f => f.id).sort(),
    ['retraction-needs-recomputation', 'revision-needs-scope'],
  );
});

test('canonical data satisfies the practice contract when arrays are present', () => {
  const canonical = JSON.parse(readFileSync(CANONICAL, 'utf8'));
  assert.ok(Array.isArray(canonical.findings) && canonical.findings.length);
  for (const id of ['retrieval-candidate-competition', 'revision-needs-scope',
    'retraction-needs-recomputation']) {
    assert.ok(canonical.findings.some(finding => finding.id === id), `missing ${id}`);
  }
  // A Chinese problem query built from the canonical triggers must hit only its finding.
  const hits = Practice.query(canonical, '候选 重复 占满');
  assert.equal(hits[0].finding.id, 'retrieval-candidate-competition');
  // An English trigger word resolves the finding too.
  const english = Practice.query(canonical, 'retraction recompute');
  assert.deepEqual(english.map(hit => hit.finding.id), ['retraction-needs-recomputation']);
  // The accepted natural-language problem queries must rank their finding first
  // without adding those full sentences to canonical content.
  const natural = [
    ['候选增加之后，结果被重复条目占满', 'retrieval-candidate-competition'],
    ['结果被重复条目占满', 'retrieval-candidate-competition'],
    ['新版说明覆盖了旧版经验', 'revision-needs-scope'],
    ['来源删除后，缓存还有影响吗', 'retraction-needs-recomputation'],
    ['duplicate candidates crowd out useful retrieval results', 'retrieval-candidate-competition'],
  ];
  for (const [query, id] of natural) {
    assert.equal(Practice.query(canonical, query)[0]?.finding.id, id, `${query} should hit ${id}`);
  }
  assert.deepEqual(Practice.query(canonical, '火星天气 superconductivity'), []);
  const briefing = Practice.brief(canonical, '', {findingId: 'retrieval-candidate-competition'});
  assert.equal(briefing.findings[0].id, 'retrieval-candidate-competition');
  assert.ok(Practice.markdown(briefing).length > 0);
  const exported = JSON.parse(runCli(['--finding', 'retrieval-candidate-competition', '--format', 'json']));
  assert.equal(exported.findings[0].id, 'retrieval-candidate-competition');
});


test('ordinary unrelated English questions do not match fragments or function words', () => {
  const canonical = JSON.parse(readFileSync(CANONICAL, 'utf8'));
  for (const q of ['What is the weather today?', 'How do I plan a trip to Paris?',
    'What should I do for dinner?', 'is', 'to', 'the', 'revis', 'cachet']) {
    assert.deepEqual(Practice.query(canonical, q), [], q);
  }
  assert.equal(Practice.query(canonical, 'How do I avoid duplicate retrieval results?')[0].finding.id,
    'retrieval-candidate-competition');
});


test('identical titles with different conditions keep separate candidate slots', () => {
  const older = {...FINDINGS[0], id:'old-scope', when:'Only for version one'};
  const newer = {...FINDINGS[0], id:'new-scope', when:'Only for version two'};
  const hits = Practice.query(data([older, newer]), 'duplicate retrieval');
  assert.deepEqual(hits.map(hit => hit.finding.id), ['old-scope', 'new-scope']);
  assert.notEqual(hits[0].finding.when, hits[1].finding.when);
});

test('practice examples and bilingual learning queries discover their intended findings', () => {
  const canonical = JSON.parse(readFileSync(CANONICAL, 'utf8'));
  // The practice desk shows these exact chips as the example queries. This
  // checks the current five still resolve, not a per-finding maintenance rule.
  const samples = [
    ['结果被重复条目占满', 'retrieval-candidate-competition'],
    ['新版说明覆盖了旧版经验', 'revision-needs-scope'],
    ['来源删除后，缓存还有影响吗', 'retraction-needs-recomputation'],
    ['改对更正项却损伤保留范围', 'correction-needs-retention-checks'],
    ['输出被挡住，参数算纠正了吗', 'output-guard-is-not-unlearning'],
  ];
  for (const [query, id] of samples) {
    assert.ok(canonical.findings.some(finding => finding.id === id), `sample targets unknown finding ${id}`);
    assert.equal(Practice.query(canonical, query)[0]?.finding.id, id, `${query} should discover ${id}`);
  }
  // The two new topics must be discoverable independently in both languages
  // and must not collapse into the neighbouring retraction/recomputation one.
  for (const query of ['纠正 增量 保留范围', 'replay retention']) {
    assert.equal(Practice.query(canonical, query)[0]?.finding.id, 'correction-needs-retention-checks', query);
  }
  for (const query of ['输出约束 参数 遗忘', 'guard unlearning 来源遗忘']) {
    assert.equal(Practice.query(canonical, query)[0]?.finding.id, 'output-guard-is-not-unlearning', query);
  }
});
