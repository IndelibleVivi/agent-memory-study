import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {resolve} from "node:path";
import {EphemeralAdapter,makeRecord,makeCommand,pointer} from "../src/adapters";
import {buildPlan,DEFAULT_INPUT,LabClient,nativeValue,P8_MODELS,prepareObservation,stageValues} from "../src/lab-model";
const p8={id:"observation-contract-study",operations:["inspect","prepare","run"],evidence_kind:"finite-exact",provider:false,network:false};
test("P8 selectors match actual declared model IDs and state handles",()=>{
 const fixture=JSON.parse(readFileSync(resolve("../../research/observation-contract-study/fixtures.json"),"utf8"));
 assert.deepEqual(P8_MODELS.map(m=>m.id).sort(),fixture.models.map((m:any)=>m.id).sort());
 for(const model of P8_MODELS)assert.deepEqual(model.states,Object.keys(fixture.models.find((m:any)=>m.id===model.id).plant.states));
});
test("bounded plans distinguish zero from exhaustive and reject invalid/cross-owner actions",()=>{
 assert.deepEqual(buildPlan(p8,"run",{...DEFAULT_INPUT,steps:"0",cost:"1/2"}).parameters,{operation:"search-pair",model:"score-weighted",left:"revision",right:"scope",max_steps:0,max_cost:"1/2"});
 assert.ok(!("max_steps" in buildPlan(p8,"run",DEFAULT_INPUT).parameters!));
 for(const changes of [{steps:"101"},{steps:"-1"},{cost:"1/0"},{model:"private-path"},{left:"gold"},{left:"scope"}])assert.throws(()=>buildPlan(p8,"run",{...DEFAULT_INPUT,...changes}));
 assert.throws(()=>buildPlan({...p8,operations:["inspect"]},"run",DEFAULT_INPUT));
 assert.throws(()=>buildPlan(p8,"replay",DEFAULT_INPUT));
 const plan=buildPlan({...p8,id:"conditional-contribution-study"},"prepare",DEFAULT_INPUT);assert.deepEqual(plan.parameters,{});
});
test("lost submit ack reuses key; changing unknown submission is refused",async()=>{
 const calls:any[]=[];let first=true;
 const client=new LabClient({request:async(_path:string,body:any)=>{calls.push(body);if(first){first=false;throw new Error("ack lost");}return {id:"owned",state:"queued"};}} as any);
 const plan=buildPlan(p8,"run",DEFAULT_INPUT);await assert.rejects(client.submit(plan));
 await assert.rejects(client.submit({...plan,operation:"inspect"}),/上一提交/);
 assert.equal((await client.submit(plan)).id,"owned");assert.equal(calls[0].idempotency_key,calls[1].idempotency_key);
});
test("native evidence keeps empty delivered memory and absent raw distinct",()=>{
 const stage=stageValues({request:{messages:[{role:"user",content:JSON.stringify({memory:""})}]},delivered:{used:"unknown"},response:'{"action":"abstain"}',score:{citations_valid:true}});
 assert.equal(stage.delivered,"");assert.equal(stage.audit.used,"unknown");assert.equal(stage.response.action,"abstain");
 assert.equal(stageValues({delivered:{selected_ids:["a"]}}).delivered,null);
 assert.deepEqual(nativeValue({result:{result:{trace:[],status:"indistinguishable"}}}),{trace:[],status:"indistinguishable"});
});
test("Observation and proposed Design preserve exact Run basis, no automatic interpretation",async()=>{
 const adapter=new EphemeralAdapter(),bytes=new TextEncoder().encode("synthetic test protocol/code/result"),blob=await adapter.upload(bytes);
 const artifact=await makeRecord("artifact",{media_type:"text/plain",byte_length:blob.byte_length,artifact_digest:blob.digest,storage:{kind:"blob",locator:blob.digest},role:"code",visibility:"private",obtained_at:"2026-10-29T00:00:00Z"});await adapter.apply(makeCommand(artifact));
 const r=pointer(artifact),run=await makeRecord("run",{protocol_ref:r,code_ref:r,config_ref:r,dataset_refs:[],rubric_ref:r,executor:"synthetic test",started_at:"2026-10-29T00:00:00Z",status:"complete",result_artifact_refs:[r]});await adapter.apply(makeCommand(run));
 const draft={statement:"观察仍相同",scope:"fixed pair / bounded 1 step",expected:"可分",observed:"bound exhausted",title:"增加界限作诊断",explanationA:"真正等价",explanationB:"允许序列更长",control:"同 pair 扩大步界，其他条件固定",question:"超过界限后会怎样？",withDesign:true};
 const plan=await prepareObservation(run,draft,"finite trace/0");await adapter.applyUnit(plan.commands);await adapter.applyUnit(plan.commands);
 assert.equal((await adapter.list("observation")).length,1);assert.deepEqual(plan.observation.run_ref,pointer(run));assert.deepEqual(plan.observation.basis_refs,[r]);assert.equal(plan.design!.status,"proposed-not-run");assert.match(plan.design!.body,/竞争解释 B/);assert.match(plan.design!.body,/未执行/);
 await assert.rejects(prepareObservation(run,{...draft,control:""},"trace"));assert.equal((await adapter.list("design")).length,1);
});
test("historical receipt Observation and three-explanation Design do not create a Run",async()=>{
 const adapter=new EphemeralAdapter(),blob=await adapter.upload(new TextEncoder().encode('original synthetic historical receipt'));
 const artifact=await makeRecord('artifact',{media_type:'application/json',byte_length:blob.byte_length,artifact_digest:blob.digest,storage:{kind:'blob',locator:blob.digest},role:'receipt',visibility:'private',obtained_at:'2026-10-30T00:00:00Z'});await adapter.apply(makeCommand(artifact));
 const draft={statement:'retained failure',scope:'saved numerical control only',expected:'invariance',observed:'failure',title:'Three explanations remain open',explanationA:'precision',explanationB:'shape/scope',explanationC:'semantic mechanism',control:'fixed precision/shape separate contrast; proposed only',question:'missing early tensors',withDesign:true};
 await assert.rejects(prepareObservation(artifact,{...draft,explanationC:''},'historical receipt'),/历史控制需三项/);
 const plan=await prepareObservation(artifact,draft,'historical receipt');await adapter.applyUnit(plan.commands);assert.ok(!('run_ref' in plan.observation));assert.deepEqual(plan.observation.basis_refs,[pointer(artifact)]);assert.equal((await adapter.list('run')).length,0);assert.match(plan.design!.body,/竞争解释 C/);assert.match(plan.design!.body,/非新Run/);
 const analysis=await makeRecord('analysis',{run_refs:[],method:'explicit author inspection',scope:'historical only',result:'failure retained; no raw reconstruction',observation_refs:[pointer(plan.observation)]});await adapter.apply(makeCommand(analysis));assert.equal((await adapter.list('analysis')).length,1);assert.equal((await adapter.list('run')).length,0);
});
