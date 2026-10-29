import test from "node:test";
import assert from "node:assert/strict";
import {EphemeralAdapter,makeRecord,makeCommand,revise,pointer,base64,utf8} from "../src/adapters";
import {DeskStore,privateWorkspaceMarkdown} from "../src/desk-store";
import {strictJSON,validateClosure} from "../src/portable";

test("creating a desk locks its target and retries a lost acknowledgement once",async()=>{
  const adapter=new EphemeralAdapter(),desk=new DeskStore(adapter);await desk.create("original");desk.edit({question:"原案头的问题"});await desk.flush();
  const old=desk.state.active!,apply=adapter.applyUnit.bind(adapter);
  let release!:()=>void,submitted!:()=>void;
  const gate=new Promise<void>(resolve=>release=resolve),ready=new Promise<void>(resolve=>submitted=resolve);
  adapter.applyUnit=async commands=>{submitted();await gate;await apply(commands);throw new Error("ack lost");};
  const first=desk.create("next");assert.equal(desk.create("next"),first);await ready;
  assert.equal(desk.state.creating,true);assert.equal(desk.edit({question:"不能误写旧案头"}),false);
  assert.equal(desk.active()!.record.payload.question,"原案头的问题");
  release();await assert.rejects(first,/ack lost/);
  assert.equal(desk.state.active,old);assert.equal(desk.state.creating,false);
  adapter.applyUnit=apply;await desk.create("next");
  assert.notEqual(desk.state.active,old);assert.equal(desk.active()!.record.payload.question,"");
  assert.equal((await adapter.list("session")).length,2);
  assert.equal((await adapter.load("session",old)).payload.question,"原案头的问题");
});

test("schema and identity validation precede an atomic unit",async()=>{
  const adapter=new EphemeralAdapter(),valid=await makeRecord("thread",{title:"",byline:"Test",status:"open",payload:{}}),bad=structuredClone(valid);
  bad.title="changed without new digest";
  await assert.rejects(adapter.applyUnit([makeCommand(valid),makeCommand(bad)]));
  assert.equal((await adapter.list()).length,0);
  const cmd=makeCommand(valid);await adapter.apply(cmd);await adapter.apply(cmd);assert.equal((await adapter.list()).length,1);
  const collision={...makeCommand(await makeRecord("thread",{title:"x",byline:"Test",status:"open",payload:{}})),idempotency_key:cmd.idempotency_key};
  await assert.rejects(adapter.apply(collision),/idempotency-conflict/);
});
test("simultaneous updates from one base cannot silently overwrite",async()=>{
  const adapter=new EphemeralAdapter(),base=await makeRecord("thread",{title:"base",byline:"Test",status:"open",payload:{}});await adapter.apply(makeCommand(base));
  const left=await revise(base,{title:"left"}),right=await revise(base,{title:"right"});
  const results=await Promise.allSettled([adapter.apply(makeCommand(left,base)),adapter.apply(makeCommand(right,base))]);
  assert.equal(results.filter(r=>r.status==="fulfilled").length,1);
  assert.equal((await adapter.load("thread",base.id)).title,"left");
});
test("selected export restores all bytes and no unrelated private thread",async()=>{
  const source=new EphemeralAdapter(),desk=new DeskStore(source);await desk.create("selected");desk.edit({question:"第一处问题"});await desk.flush();
  await desk.capture("<img src=x onerror=alert(1)>","只保留纯文本");const first=desk.state.active!;
  await desk.create("DO_NOT_EXPORT_CANARY");desk.select(first);
  const pack=await desk.exportActive();assert.ok(!JSON.stringify(pack).includes("DO_NOT_EXPORT_CANARY"));
  const target=new EphemeralAdapter(),raw=utf8(pack),preview=await target.request("/import/preview",{base64:base64(raw)});
  assert.equal((await target.list()).length,0);await target.request("/import/confirm",{digest:preview.digest});await target.request("/import/confirm",{digest:preview.digest});
  assert.equal((await target.list("session"))[0].payload.question,"第一处问题");assert.equal((await target.list("capture"))[0].input,"<img src=x onerror=alert(1)>");
});
test("duplicate escaped JSON keys and damaged attachments are rejected",async()=>{
  assert.throws(()=>strictJSON(new TextEncoder().encode('{"x":1,"\\u0078":2}')),/重复/);
  const adapter=new EphemeralAdapter();await assert.rejects(adapter.request("/import/preview",{base64:base64(utf8({schema:"ams-workspace/3",records:[],roots:[],blobs:{}}))}));
});
test("saving one desk does not clear another desk's changes",async()=>{
  const desk=new DeskStore(new EphemeralAdapter());await desk.create("first");desk.edit({question:"unsaved first"});await desk.flush();const first=desk.state.active!;
  await desk.create("second");desk.edit({question:"saved second"});await desk.flush();await desk.exportActive();assert.equal(desk.hasUnsaved(),true);
  desk.select(first);await desk.exportActive();assert.equal(desk.hasUnsaved(),false);
});
test("a pinned public basis survives an offline export and new-page import",async()=>{
  const original=await makeRecord("entry",{title:"Original",byline:"Test",entry_type:"learning-note",date:"2026-10-29",intro:"basis",body_file:"study/entries/original.md",payload:{bodyMarkdown:"original words"}});
  const source=new EphemeralAdapter(undefined,async()=>original),desk=new DeskStore(source);
  await desk.add({kind:"study",id:"original",title:"Original",intro:"",byline:"Test",date:"2026-10-29",categories:[],failureSurfaces:[],domains:[],directions:[],materialIds:[],shard:"original.json",ref:pointer(original)},{id:"original",title:"Original",bodyHtml:"<p>original words</p>"});
  await desk.excerpt("study:original","original words","#section-1");
  const pack=await desk.exportActive();assert.deepEqual(pack.public_records,[original]);
  const target=new EphemeralAdapter(),preview=await target.request("/import/preview",{base64:base64(utf8(pack))});
  await target.request("/import/confirm",{digest:preview.digest});
  assert.deepEqual(await target.load(original.kind,original.id,original.revision),original);
  assert.equal((await target.list("excerpt"))[0].target_ref.revision,original.revision);
  const corrupt=structuredClone(pack);corrupt.public_records=[];
  await assert.rejects(new EphemeralAdapter().request("/import/preview",{base64:base64(utf8(corrupt))}),/引用不完整/);
});
test("unacknowledged input opens separately without evaluating old refs",async()=>{
  const adapter=new EphemeralAdapter();
  const value={schema:"ams-uncommitted-input/1",record:{kind:"session",payload:{question:"没有 ack 的原话",items:[{key:"lost",note:"原旁注",target_ref:{kind:"entry",id:"lost",revision:"rev:lost"}}]}}};
  const preview=await adapter.request("/import/preview",{base64:base64(utf8(value))});
  await adapter.request("/import/confirm",{digest:preview.digest});
  assert.equal((await adapter.list("session"))[0].payload.question,"没有 ack 的原话");
  assert.equal((await adapter.list("session"))[0].payload.items[0].note,"原旁注");
  assert.equal((await adapter.list("session"))[0].payload.items[0].target_ref.kind,"artifact");
});
test("portable formal arguments cannot bypass scope and unchanged-result rules",async()=>{
  const claim=await makeRecord("claim_revision",{title:"claim",byline:"Test",claim:"fixed",scope:"task-A",scope_binding:"task-A",payload:{}});
  const changeset=await makeRecord("changeset",{review_state:"accepted",application_state:"checked-unchanged",publication_refs:[],items:[{id:"one",target:"private-thread",base_ref:pointer(claim),change:{mode:"replace-fields",fields:{claim:"different"}},review_state:"accepted",application_state:"checked-unchanged"}]});
  assert.throws(()=>validateClosure([claim,changeset]),/no-change/);
  const proposal=await makeRecord("relation_proposal",{from_ref:pointer(claim),to_ref:pointer(claim),relation:"supports",scope:"task-A",scope_binding:"task-A",locator:"p1",rationale:"test",generated_by:{kind:"agent",id:"actor:test"},method_version:"test/1",status:"proposal"});
  const relation=await makeRecord("evidence_relation",{from_ref:pointer(claim),to_ref:pointer(claim),relation:"supports",scope:"task-B",scope_binding:"task-B",locator:"p1",rationale:"test",proposal_ref:pointer(proposal),review:{actor:{kind:"human",id:"actor:test"},at:new Date().toISOString(),rationale:"reviewed"},status:"accepted"});
  assert.throws(()=>validateClosure([claim,proposal,relation]),/建议不一致/);
});
test("double import confirmation creates one recovery desk",async()=>{
  const adapter=new EphemeralAdapter(),value={schema:"ams-uncommitted-input/1",record:{kind:"session",payload:{question:"recover once",items:[]}}};
  const preview=await adapter.request("/import/preview",{base64:base64(utf8(value))});
  const [a,b]=await Promise.all([adapter.request("/import/confirm",{digest:preview.digest}),adapter.request("/import/confirm",{digest:preview.digest})]);
  assert.deepEqual(a,b);assert.equal((await adapter.list("session")).length,1);
});
test("history budget is shared across desks and undo/redo remains meaningful",async()=>{
  const desk=new DeskStore(new EphemeralAdapter());await desk.create("first");
  for(let i=0;i<15;i++){desk.edit({question:"first "+i});desk.endGroup();}await desk.flush();
  await desk.create("second");for(let i=0;i<15;i++){desk.edit({question:"second "+i});desk.endGroup();}await desk.flush();
  assert.equal(Object.values(desk.state.edits).reduce((n,e)=>n+e.past.length+e.future.length,0),20);
  desk.undo();assert.equal(desk.active()!.record.payload.question,"second 13");desk.undo(true);assert.equal(desk.active()!.record.payload.question,"second 14");await desk.flush();
});
test("oversized complete download is refused before replacing a desk or its history",async()=>{
  const adapter=new EphemeralAdapter(),desk=new DeskStore(adapter);await desk.create();
  const item=async(size:number)=>{const blob=await adapter.upload(new Uint8Array(size));const record=await makeRecord("artifact",{media_type:"application/octet-stream",byte_length:size,artifact_digest:blob.digest,storage:{kind:"blob",locator:blob.digest},role:"other",visibility:"private",obtained_at:new Date().toISOString()});await adapter.apply(makeCommand(record));return {key:record.id,target_ref:pointer(record),representation_ref:pointer(record)};};
  desk.edit({items:[await item(18*1024*1024)]});await desk.flush();desk.endGroup();
  const before=JSON.stringify(desk.active());const second=await item(7*1024*1024);
  assert.equal(desk.edit({items:[...desk.active()!.record.payload.items,second]}),false);
  assert.equal(JSON.stringify(desk.active()),before);assert.match(desk.state.error!,/32 MiB/);
  await assert.rejects(desk.captureFile(new File([new Uint8Array(7*1024*1024)],"synthetic-large.bin")),/32 MiB/);
  assert.equal(JSON.stringify(desk.active()),before);
  const saved=await desk.exportActive();assert.ok(new TextEncoder().encode(JSON.stringify(saved,null,2)).length<32*1024*1024);
});

test("changing current basis preserves old excerpts and Markdown is not a recovery checkpoint",async()=>{
  const old=await makeRecord("entry",{title:"Basis",byline:"Test",entry_type:"learning-note",date:"2026-10-29",intro:"original",body_file:"study/entries/basis.md",payload:{bodyMarkdown:"old words"}});
  const next=await revise(old,{intro:"changed",payload:{bodyMarkdown:"new words"}}),records=[old,next];
  const adapter=new EphemeralAdapter(undefined,async ref=>records.find(r=>r.revision===ref.revision)!),desk=new DeskStore(adapter);
  const meta:any={kind:"study",id:"basis",title:"Basis",intro:"",byline:"Test",date:"2026-10-29",categories:[],failureSurfaces:[],domains:[],directions:[],materialIds:[],shard:"basis.json",ref:pointer(old)};
  await desk.add(meta,{id:"basis",title:"Basis",bodyHtml:"<p>old words</p>"});await desk.excerpt("study:basis","old words","#section-1");desk.endGroup();
  const excerpt=(await adapter.list("excerpt"))[0],before=structuredClone(excerpt);
  await desk.replaceBasis("study:basis",{...meta,ref:pointer(next)},{id:"basis",title:"Basis",bodyHtml:"<p>new words</p>"});
  assert.equal(desk.active()!.record.payload.items[0].target_ref.revision,next.revision);
  assert.equal(desk.active()!.record.payload.items[0].previous_basis[0].target_ref.revision,old.revision);
  assert.deepEqual(await adapter.load("excerpt",excerpt.id),before);
  desk.edit({question:"私人停点"});await desk.flush();
  assert.match(privateWorkspaceMarkdown(await desk.exportActive(false)),/私人停点/);assert.equal(desk.hasUnsaved(),true);
  await desk.exportActive();assert.equal(desk.hasUnsaved(),false);
});
