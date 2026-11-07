const test = require('node:test');
const assert = require('node:assert/strict');
const study = require('../assets/index-study.js');
const lowerBound = (keys,q) => {const index=keys.findIndex(key=>key>=q); return index<0?keys.length:index;};

test('all teaching states and integer queries agree with an independent linear oracle',()=>{
  for(const dataset of study.DATASETS) for(const mutation of ['base','insert']) for(const repair of ['stale','rebound','retrain']) for(let query=0;query<=130;query++) {
    const x=study.evaluate({dataset:dataset.id,mutation,repair,query});
    const expected=lowerBound(x.keys,query), message=JSON.stringify(x.state);
    assert.equal(x.result.position,expected,message);
    assert.equal(x.result.found,x.keys[expected]===query,message);
    assert.equal(x.baseline.position,expected,message);
    if(mutation==='base'||repair!=='stale') {
      assert.equal(x.local.certified,true,message);
      assert.equal(x.audit.covered,x.keys.length,message);
    }
    assert.ok(x.model.a>0,message);
    assert.ok(x.window.lo<=x.window.hi,message);
    assert.ok(x.result.comparisons>=x.local.trace.length+x.result.guardComparisons,message);
  }
});
test('inserting keys exposes the actual wrong local result before recovery',()=>{
  const x=study.evaluate({mutation:'insert',query:70});
  assert.deepEqual(x.baseKeys,[10,20,30,40,50,60,70,80]);
  assert.equal(x.window.prediction,6);assert.deepEqual(x.window,{prediction:6,lo:6,hi:7});
  assert.equal(x.local.position,7);assert.equal(x.local.certified,false);
  assert.equal(x.local.found,false);assert.equal(x.result.position,10);assert.equal(x.result.fallback,true);
  assert.deepEqual(x.local.trace,[{lo:6,hi:7,mid:6,key:40,relation:'<'}]);
  assert.deepEqual(x.result.trace.map(step=>step.mid),[6,9,11,10]);
  assert.equal(x.result.comparisons,8); // 1 local + 2 guard + 4 fallback + 1 equality.
  assert.equal(x.model.calibrationValid,false);assert.ok(x.audit.missedKeys.includes(70));
});
test('recalibration restores coverage without changing parameters; refitting is distinct',()=>{
  const old=study.evaluate({mutation:'insert'}), bound=study.evaluate({mutation:'insert',repair:'rebound'}), fit=study.evaluate({mutation:'insert',repair:'retrain'});
  assert.equal(bound.model.a,old.model.a);assert.equal(bound.model.b,old.model.b);
  assert.deepEqual([bound.model.minError,bound.model.maxError],[0,4]);
  assert.equal(bound.model.trainedCount,8);assert.equal(bound.model.calibratedCount,12);
  assert.equal(bound.result.fallback,false);assert.equal(bound.result.position,10);
  assert.notEqual(fit.model.a,old.model.a);assert.equal(fit.model.trainedCount,12);
});
test('missing keys, endpoints and equality have explicit lower-bound semantics and counts',()=>{
  const exact=study.evaluate({query:70});assert.equal(exact.result.comparisons,3); // one binary + two guard comparisons.
  const gap=study.evaluate({query:65});assert.equal(gap.result.position,6);assert.equal(gap.result.found,false);assert.equal(gap.result.fallback,false);
  assert.equal(study.evaluate({query:0}).result.position,0);
  const end=study.evaluate({query:130});assert.equal(end.result.position,8);assert.equal(end.result.found,false);
  assert.equal(end.local.trace.length,0);assert.equal(end.result.comparisons,1);
  assert.equal(study.evaluate({mutation:'insert',query:10}).local.certified,true,'a stale index can still certify one query');
  assert.equal(study.evaluate({mutation:'insert',query:10}).model.calibrationValid,false,'one success does not validate old calibration');
});
test('normalization admits only finite supported public state without mutating inputs',()=>{
  for(const query of [NaN,Infinity,-1,131,1.1,'',' ','1e2','0x10',{},[],null]) assert.equal(study.normalize({query}).query,70);
  assert.equal(study.normalize({query:'0'}).query,0);assert.equal(study.normalize({query:'130'}).query,130);
  assert.deepEqual(study.normalize(null),{dataset:'uniform',mutation:'base',repair:'stale',query:70});
  const input=Object.freeze({dataset:'curved',query:75,mutation:'insert',repair:'retrain',private:'do not copy'});
  const a=study.evaluate(input),b=study.evaluate(input);assert.deepEqual(a,b);assert.equal(a.state.private,undefined);
  a.keys[0]=999;assert.notEqual(study.evaluate(input).keys[0],999);
  assert.deepEqual(study.normalize({dataset:'__proto__',mutation:'x',repair:'x'}),study.normalize());
});
test('traces are actual binary decisions and the certificate uses adjacent keys only',()=>{
  for(const dataset of study.DATASETS) for(const repair of ['stale','rebound','retrain']) {
    const x=study.evaluate({dataset:dataset.id,mutation:'insert',repair,query:dataset.query});
    for(const trace of [x.local.trace,x.result.trace,x.baseline.trace]) for(const step of trace) {
      assert.equal(step.mid,Math.floor((step.lo+step.hi)/2));assert.equal(step.key,x.keys[step.mid]);
      assert.equal(step.relation,step.key<x.state.query?'<':'>=');
    }
    const i=x.local.position;
    assert.equal(x.local.certified,(i===0||x.keys[i-1]<x.state.query)&&(i===x.keys.length||x.keys[i]>=x.state.query));
    assert.equal(x.result.guardComparisons,Number(i>0)+Number(i<x.keys.length));
  }
});
