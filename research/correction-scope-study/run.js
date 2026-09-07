'use strict';
const {run} = require('../../assets/revision-study.js');
const study = require('../../data/materials.json').studies.find(item => item.id === 'after-a-correction');
const results = [];
for (const scenario of study.scenarios) {
  for (const phase of ['before', 'after']) {
    for (const policy of study.policies) {
      const result = run(scenario, policy.id, phase);
      results.push({scenario: scenario.id, phase, policy: policy.id, ...result});
    }
  }
}
process.stdout.write(JSON.stringify({study: study.id, boundary: study.boundary, results}, null, 2) + '\n');
