/* Original ordered-index teaching model. No external model, storage or benchmark. */
(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.IndexStudy = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";
  const DATASETS = Object.freeze([
    {id: "uniform", label: "等距 · 八个键", keys: [10,20,30,40,50,60,70,80], insertions: [15,25,35,45], query:70},
    {id: "clustered", label: "聚簇 · 两段密集", keys: [10,11,12,13,70,71,72,73], insertions: [14,15,16,17], query:71},
    {id: "curved", label: "间距渐增 · 弯曲分布", keys: [2,4,8,16,32,50,75,110], insertions: [3,6,12,24], query:75},
  ].map(value => Object.freeze({...value, keys:Object.freeze(value.keys), insertions:Object.freeze(value.insertions)})));
  function normalize(input = {}) {
    if (!input || typeof input !== "object" || Array.isArray(input)) input = {};
    const dataset = DATASETS.find(value => value.id === input.dataset) || DATASETS[0];
    const query = (typeof input.query === "number" || typeof input.query === "string" && /^\d{1,3}$/.test(input.query))
      && Number.isInteger(Number(input.query)) && Number(input.query) >= 0 && Number(input.query) <= 130 ? Number(input.query) : dataset.query;
    return {dataset:dataset.id, mutation:input.mutation === "insert" ? "insert" : "base",
      repair:["stale","rebound","retrain"].includes(input.repair) ? input.repair : "stale", query};
  }
  function fit(keys) {
    const mean = keys.reduce((a,b)=>a+b,0) / keys.length, meanRank = (keys.length - 1) / 2;
    let numerator = 0, denominator = 0;
    keys.forEach((key,rank)=>{numerator += (key-mean)*(rank-meanRank); denominator += (key-mean)**2;});
    const a = numerator / denominator;
    return {a, b:meanRank-a*mean};
  }
  // Deliberately use the actual floating-point fit and floor throughout; no
  // epsilon/rounding hides a boundary. Calibration includes its integer error.
  function predict(model,key) { return Math.floor(model.a*key+model.b); }
  function calibrate(model,keys) {
    const errors = keys.map((key,rank)=>rank-predict(model,key));
    return {...model,minError:Math.min(...errors),maxError:Math.max(...errors)};
  }
  function windowFor(model,query,n) {
    const prediction = predict(model,query), clamp = value=>Math.max(0,Math.min(n,value));
    return {prediction,lo:clamp(prediction+model.minError),hi:clamp(prediction+model.maxError+1)};
  }
  function search(keys,query,lo,hi) {
    const trace=[];
    while(lo<hi) {
      const mid=Math.floor((lo+hi)/2), key=keys[mid], relation=key<query?"<":">=";
      trace.push({lo,hi,mid,key,relation});
      if(relation === "<") lo=mid+1; else hi=mid;
    }
    return {position:lo,trace};
  }
  function checkedSearch(keys,query,window) {
    const candidate=search(keys,query,window.lo,window.hi), i=candidate.position;
    let guardComparisons=0, left=true, right=true, rightRelation=null;
    if(i>0) { guardComparisons++; left=keys[i-1]<query; }
    if(i<keys.length) {
      // One three-way key comparison serves both >= and exact membership.
      guardComparisons++; rightRelation=Math.sign(keys[i]-query); right=rightRelation>=0;
    }
    const certified=left&&right;
    const local={...candidate,found:rightRelation===0,certified};
    let position=i, trace=candidate.trace, found=local.found, fallbackComparisons=0;
    if(!certified) {
      const fallback=search(keys,query,0,keys.length);
      position=fallback.position; trace=fallback.trace; found=false;
      fallbackComparisons=trace.length;
      if(position<keys.length) {fallbackComparisons++;found=keys[position]===query;}
    }
    return {local,result:{position,found,trace,fallback:!certified,guardComparisons,
      comparisons:candidate.trace.length+guardComparisons+fallbackComparisons}};
  }
  function evaluate(input={}) {
    const state=normalize(input), dataset=DATASETS.find(value=>value.id===state.dataset);
    const baseKeys=[...dataset.keys], insertions=state.mutation==="insert"?[...dataset.insertions]:[];
    const keys=[...baseKeys,...insertions].sort((a,b)=>a-b);
    const retrain=state.mutation==="insert"&&state.repair==="retrain";
    const recalibrate=state.mutation==="insert"&&state.repair!=="stale";
    const model={...calibrate(fit(retrain?keys:baseKeys),recalibrate?keys:baseKeys),
      trainedCount:retrain?keys.length:baseKeys.length,calibratedCount:recalibrate?keys.length:baseKeys.length,
      calibrationValid:state.mutation==="base"||recalibrate,mode:state.mutation==="base"?"base":state.repair};
    const window=windowFor(model,state.query,keys.length);
    // The answer path finishes before either independent teaching diagnostic.
    const {local,result}=checkedSearch(keys,state.query,window);
    const baseline=search(keys,state.query,0,keys.length);
    baseline.found=baseline.position<keys.length&&keys[baseline.position]===state.query;
    const rows=keys.map((key,rank)=>({key,rank,prediction:predict(model,key),error:rank-predict(model,key),
      inserted:insertions.includes(key),inWindow:rank>=window.lo&&rank<window.hi}));
    const missedKeys=keys.filter((key,rank)=>{const w=windowFor(model,key,keys.length);return rank<w.lo||rank>w.hi;});
    return {state,baseKeys,keys,insertions,model,window,local,baseline,result,rows,
      audit:{covered:keys.length-missedKeys.length,total:keys.length,missedKeys}};
  }
  return {DATASETS,normalize,evaluate};
});
