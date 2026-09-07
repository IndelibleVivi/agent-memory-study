/* One deterministic engine shared by the reading room and the local runner. */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.RevisionStudy = factory();
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  // Selection receives no environment answer. Order is the fixture's declared receipt order.
  function select(policy, target, evidence, initial) {
    let candidates;
    if (policy === 'none') return {flag: null, supports: [], reason: 'no-memory'};
    if (policy === 'frozen') candidates = initial.slice(0, 1);
    else if (policy === 'latest') candidates = evidence.filter(item => item.active).slice(-1);
    else if (policy === 'scoped') candidates = evidence.filter(item => item.active && item.scope === target);
    else throw new Error(`Unknown policy: ${policy}`);
    const supports = candidates.map(item => item.id);
    if (!candidates.length) return {flag: null, supports, reason: 'no-support'};
    const flags = new Set(candidates.map(item => item.flag));
    if (flags.size > 1) return {flag: null, supports, reason: 'conflict'};
    return {flag: candidates[0].flag, supports, reason: 'supported'};
  }

  function run(scenario, policy, phase) {
    if (!['before', 'after'].includes(phase)) throw new Error(`Unknown phase: ${phase}`);
    const changed = phase === 'after';
    const withdrawn = new Set(changed ? scenario.change.retracts : []);
    const evidence = [...scenario.initial, ...(changed ? scenario.change.adds : [])]
      .map(item => ({...item, active: !withdrawn.has(item.id)}));
    const advice = select(policy, scenario.target, evidence, scenario.initial);
    // The synthetic tool checks a proposed command only after selection has finished.
    const expected = scenario.environment[phase];
    const verdict = advice.flag === null ? 'abstained' : advice.flag === expected ? 'accepted' : 'mismatch';
    return {...advice, verdict, expected, evidence};
  }
  return {select, run};
});
