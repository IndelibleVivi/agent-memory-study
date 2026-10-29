import test from "node:test";
import assert from "node:assert/strict";
import {ReviewClient,bundleFields,deliveryRequest,draftFrom,proposalRequest,refKey,relationFields,sameRef} from "../src/review-model";
import type {Entity} from "../src/types";
const ref={kind:"claim_revision",id:"claim:fixture",revision:"rev:fixture"};
const conclusion={...ref,schema:"ams-core/2",state_revision:ref.revision,content_digest:{},title:"bounded",byline:"AMS tests",claim:"limited claim",scope:"finite",scope_binding:"finite",payload:{}} as Entity;
test("fixed references compare complete identity and tolerate object key ordering",()=>{
 assert.equal(refKey(ref),refKey({revision:ref.revision,id:ref.id,kind:ref.kind}));assert.ok(sameRef(ref,{...ref}));assert.ok(!sameRef(ref,{...ref,revision:"rev:new"}));
});
test("lost authoring ack reuses exact operation key and refuses substituted draft",async()=>{
 const calls:any[]=[];let first=true;const client=new ReviewClient({request:async(path:string,body:any)=>{calls.push({path,body});if(first){first=false;throw new Error("ack lost after commit");}return {saved:true};}} as any);
 await assert.rejects(client.write("/authoring/propose",{base_ref:ref,body:"A"}));await assert.rejects(client.write("/authoring/propose",{base_ref:ref,body:"B"}),/上一操作/);assert.equal(client.outstanding().length,1);await client.write("/authoring/propose",{base_ref:ref,body:"A"});assert.equal(calls[0].body.idempotency_key,calls[1].body.idempotency_key);assert.equal(client.outstanding().length,0);
});
test("ordinary manuscript review does not require claim; diagnostic design needs competing explanations",()=>{
 const entry={...conclusion,kind:"entry",id:"entry:fixture",intro:"intro",payload:{}} as Entity;const draft=draftFrom({record:entry,body:"authored body",scope:""});draft.explanation="checked wording and actual scope";assert.equal(proposalRequest(entry,draft).base_ref.kind,"entry");assert.equal(proposalRequest(entry,draft).decision,"maintain");
 draft.decision="needs-experiment";assert.throws(()=>proposalRequest(entry,draft));Object.assign(draft,{explanationA:"A",explanationB:"B",control:"fixed contrast",open_question:"unresolved"});assert.match(proposalRequest(entry,draft).explanation,/竞争解释 B/);
});
test("relations remain proposals; AND and OR use actual accepted typed inputs",()=>{
 const from={kind:"source_revision",id:"work:fixture",revision:"rev:source"};const fields=relationFields(from,conclusion,"supports","finite","finite","paragraph 2","bounded source reading");assert.equal(fields.method_version,"review-ui/1");assert.ok(!("review" in fields));
 const relation={kind:"evidence_relation",id:"relation:fixture",revision:"rev:relation",status:"accepted",to_ref:ref,from_ref:from} as Entity;
 const and=bundleFields(conclusion,"all-premises",[relation],"joint warrant","not-assessed","");assert.deepEqual(and.premise_refs,[from]);assert.deepEqual(and.relation_refs,[{kind:relation.kind,id:relation.id,revision:relation.revision}]);
 assert.throws(()=>bundleFields(conclusion,"all-premises",[{...relation,status:"proposal"}],"reason","not-assessed",""));assert.throws(()=>bundleFields(conclusion,"alternative-warrants",[relation],"reason","not-assessed",""));assert.throws(()=>bundleFields(conclusion,"all-premises",[relation],"reason","argued-independent",""));
});
test("delivery observation is explicitly confirmed and keeps repository/build/site separate",()=>{
 const values={repository:"visible",build:"failed",site:"failed",commit:"a".repeat(40),repo_url:"https://example.invalid/repo",digest:"",site_url:"",deployment:"",observed_at:"2026-10-29T00:00:00Z",confirmed:false};assert.throws(()=>deliveryRequest(ref,values));const r=deliveryRequest(ref,{...values,confirmed:true});assert.equal(r.delivery.repository.state,"visible");assert.equal(r.delivery.build.state,"failed");assert.equal(r.delivery.site.state,"failed");assert.ok(!("artifact_digest" in r.delivery.build));
});
test("explicit validation rejection clears uncertain-send slot while network/5xx remains pending",async()=>{
 const {RequestError}=await import('../src/adapters');let first=true;const client=new ReviewClient({request:async()=>{if(first){first=false;throw new RequestError({message:'scope mismatch'},400);}return {accepted:true};}} as any);
 await assert.rejects(client.write('/argument/accept',{proposal_ref:ref,rationale:'wrong scope'},false));assert.equal(client.outstanding().length,0);assert.deepEqual(await client.write('/argument/accept',{proposal_ref:{...ref,revision:'rev:new'},rationale:'bounded scope'},false),{accepted:true});
});
