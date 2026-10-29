import StudyDesk from "../../../assets/study-desk.js";
import {validateEntity} from "../.build/contracts.js";
import {contentDigest,canonicalObjectBytes} from "../../../packages/research-core/canonical.js";
import {digest,unbase64,makeRecord,makeCommand,pointer,utf8} from "./adapters";
import type {WorkspaceAdapter,Entity,EntityRef} from "./types";

export function strictJSON(bytes:Uint8Array) {
  if(bytes.length>32*1024*1024)throw new Error("私人研究文件限 32 MiB。");
  const text=new TextDecoder("utf-8",{fatal:true}).decode(bytes),value=JSON.parse(text);
  const stack:{object:boolean;key:boolean;seen:Set<string>}[]=[];
  // JSON.parse owns syntax. This pass rejects the duplicate keys it otherwise
  // silently replaces, including escaped spellings of the same property.
  for(const token of text.match(/"(?:\\.|[^"\\])*"|[{}\[\]:,]|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?|true|false|null/g)||[]) {
    const current=stack.at(-1);
    if(token==="{"||token==="["){stack.push({object:token==="{",key:token==="{",seen:new Set()});if(stack.length>100)throw new Error("文件嵌套过深。");}
    else if(token==="}"||token==="]")stack.pop();
    else if(token===","&&current)current.key=current.object;
    else if(token===":"&&current)current.key=false;
    else if(token.startsWith('"')&&current?.object&&current.key){const key=JSON.parse(token);if(current.seen.has(key))throw new Error("JSON 含重复字段；未导入。");current.seen.add(key);current.key=false;}
    else if(!token.startsWith('"')&&/^[\d-]/.test(token)&&!Number.isFinite(Number(token)))throw new Error("文件含非有限数值。");
  }
  return value;
}
export async function validateRecord(record:Entity) {
  if(!record.id||!validateEntity(record))throw new Error("对象不符合当前 AMS schema。");
  if(record.revision!==record.state_revision)throw new Error("对象的当前版本指针不一致。");
  if(JSON.stringify(await contentDigest(record))!==JSON.stringify(record.content_digest)) {
    const expected=await contentDigest(record),observed=record.content_digest as any;
    if(expected.value!==observed?.value||expected.canonicalization!==observed?.canonicalization||expected.algorithm!==observed?.algorithm||JSON.stringify(expected.fields)!==JSON.stringify(observed?.fields))throw new Error("对象内容与固定身份不一致。");
  }
}
export function exactRefs(value:any,into:EntityRef[]=[]):EntityRef[] {
  if(value&&typeof value==="object") {
    if(!Array.isArray(value)&&Object.keys(value).sort().join(",")==="id,kind,revision")into.push(value);
    else Object.values(value).forEach(part=>exactRefs(part,into));
  }
  return into;
}
export function validateClosure(records:Entity[],publicRecords:Entity[]=[]) {
  const index=new Map<string,Entity>(),same=(a:EntityRef,b:EntityRef)=>a.kind===b.kind&&a.id===b.id&&a.revision===b.revision;
  const equal=(a:any,b:any)=>new TextDecoder().decode(canonicalObjectBytes({value:a}))===new TextDecoder().decode(canonicalObjectBytes({value:b}));
  for(const record of [...records,...publicRecords]){const old=index.get(record.revision);if(old&&!equal(old,record))throw new Error("同一版本身份出现不同内容。");index.set(record.revision,record);}
  const resolve=(ref:EntityRef)=>{const found=index.get(ref.revision);if(!found||!same(found,ref))throw new Error("案头引用不完整。");return found;};
  const scope=(a:Entity,b:Entity)=>equal(a.scope,b.scope)&&equal(a.scope_binding,b.scope_binding);
  const review=(record:Entity)=>{if(record.review.actor.kind!=="human"&&!record.review.delegation_ref)throw new Error("正式决定缺少审阅或委托依据。");};
  for(const record of index.values()) {
    for(const ref of exactRefs(record)){const found=index.get(ref.revision);if(!found||!same(found,ref))throw new Error("案头引用不完整。");}
    if(record.kind==="source_revision") {
      const work=resolve(record.work_ref);
      if(work.kind!=="source_work"||work.id!==record.id)throw new Error("来源版本不属于此作品。");
      if(record.identity.mode==="observed-snapshot"&&record.identity.snapshot_captured){const artifact=resolve(record.identity.artifact_ref);if(!artifact.source_revision_ref||!same(artifact.source_revision_ref,record))throw new Error("快照字节绑定了别的版本。");}
    } else if(record.kind==="source_note") {
      const work=resolve(record.work_ref),revision=resolve(record.source_revision_ref);
      if(work.kind!=="source_work"||revision.kind!=="source_revision"||!same(revision.work_ref,record.work_ref)||!work.aliases.includes(record.alias))throw new Error("札记与作品／版本身份不一致。");
    } else if(record.kind==="excerpt"||record.kind==="read_activity") {
      const representation=index.get(record.representation_ref.revision)!,allowed=[representation.source_revision_ref,representation.representation_of,record.representation_ref,
        ...[...index.values()].filter(r=>r.kind==="extraction"&&same(r.output_artifact_ref,record.representation_ref)).map(r=>r.source_revision_ref)].filter(Boolean);
      if(!allowed.some(ref=>same(ref,record.target_ref)))throw new Error("摘录或阅读记录的表示没有绑定其目标版本。");
      if(record.kind==="read_activity"&&record.method==="agent-delivered"&&resolve(record.receipt_ref).role!=="receipt")throw new Error("Agent 送达需要真实 receipt artifact。");
    } else if(record.kind==="evidence_relation") {
      const proposal=resolve(record.proposal_ref);
      if(["from_ref","to_ref","relation","scope","scope_binding","locator"].some(field=>!equal(record[field],proposal[field])))throw new Error("正式关系与被审阅建议不一致。");
      review(record);
    } else if(record.kind==="support_bundle") {
      const conclusion=resolve(record.conclusion_ref);
      if(conclusion.kind!=="claim_revision"||!scope(record,conclusion))throw new Error("支持组合与结论范围不一致。");
      if(record.combination==="all-premises"){
        const premises=new Set(record.premise_refs.map((r:EntityRef)=>r.revision)),covered=new Set<string>();
        for(const ref of record.relation_refs){const relation=resolve(ref);if(relation.kind!=="evidence_relation"||!["supports","derives"].includes(relation.relation)||!same(relation.to_ref,record.conclusion_ref)||!scope(relation,record))throw new Error("AND 前提缺少同范围正式支持。");covered.add(relation.from_ref.revision);}
        if(!premises.size||premises.size!==covered.size||[...premises].some(v=>!covered.has(v as string)))throw new Error("AND 的每个前提都需要正式关系。");
      }else{
        if(record.warrant_refs.length<2)throw new Error("OR 至少需要两条 warrant。");
        for(const ref of record.warrant_refs){const warrant=resolve(ref);if(warrant.kind!=="support_bundle"||warrant.combination!=="all-premises"||!same(warrant.conclusion_ref,record.conclusion_ref)||!scope(warrant,record))throw new Error("替代 warrant 的结论或范围不同。");}
      }
      review(record);
    } else if(record.kind==="changeset") {
      for(const item of record.items){
        if(item.application_state==="applied"&&(item.review_state!=="accepted"||!item.result_ref||item.result_ref.kind!==item.base_ref.kind||item.result_ref.id!==item.base_ref.id||item.result_ref.revision===item.base_ref.revision))throw new Error("应用结果需要已接受决定及同对象的新版本。");
        if(item.application_state==="checked-unchanged"&&(item.review_state!=="accepted"||item.result_ref||item.change?.mode!=="no-change"))throw new Error("维持原状需要明确的 no-change 决定。");
      }
    }
  }
}
export async function previewPortable(bytes:Uint8Array,publicData:any) {
  const value=strictJSON(bytes),identity="sha256:"+await digest(bytes);
  if(value.schema==="ams-workspace/3") {
    if(!Array.isArray(value.records)||value.records.length>512||!value.blobs||typeof value.blobs!=="object"||Array.isArray(value.blobs)||!Array.isArray(value.roots)||!value.roots.length)throw new Error("案头记录或文件清单不完整。");
    const seen=new Map<string,Entity>();
    for(const record of value.records){await validateRecord(record);if(seen.has(record.revision))throw new Error("重复版本身份。");seen.set(record.revision,record);}
    for(const [key,encoded] of Object.entries(value.blobs)){if(typeof encoded!=="string"||"sha256:"+await digest(unbase64(encoded))!==key)throw new Error("依据文件损坏。");}
    for(const record of value.records)if(record.kind==="artifact"&&record.storage.kind==="blob") {
      const encoded=value.blobs[record.artifact_digest];
      if(!encoded||unbase64(encoded).length!==record.byte_length)throw new Error("缺少完整依据文件。");
    }
    for(const ref of value.roots){const found=seen.get(ref.revision);if(!found||found.id!==ref.id||found.kind!==ref.kind)throw new Error("案头入口没有对应版本。");}
    if(!Array.isArray(value.public_records||[])||(value.public_records||[]).length>512)throw new Error("引用快照清单无效。");
    for(const record of value.public_records||[])await validateRecord(record);
    validateClosure(value.records,value.public_records||[]);
    return {digest:identity,source_format:value.schema,records:value.records.length,unresolved:[],message:"确认后恢复固定版本与私人文字；不执行文件中的 HTML 或链接。",value};
  }
  let workspace;
  if(value.schema==="ams-continuation/1") {
    const old=StudyDesk.parse(new TextDecoder().decode(bytes),publicData);
    workspace={title:"",question:"",synthesis:"",next:"",compare:[],items:[{...old,excerpts:[]}]};
  } else if(["ams-workspace/1","ams-workspace/2"].includes(value.schema))workspace=StudyDesk.parseWorkspace(new TextDecoder().decode(bytes),publicData);
  else if(value.schema==="ams-uncommitted-input/1") {
    if(!value.record||value.record.kind!=="session"||!value.record.payload)throw new Error("没有可恢复的输入。");
    workspace={title:"恢复的未确认输入",...value.record.payload};
    if(!Array.isArray(workspace.items)||workspace.items.length>24||workspace.items.some((item:any)=>!item||typeof item!=="object"||Array.isArray(item))||utf8(workspace).length>2*1024*1024)throw new Error("恢复案头超过容量或对象无效。");
    for(const field of ["question","synthesis","next","return_when"])if(workspace[field]!==undefined&&typeof workspace[field]!=="string")throw new Error("恢复的文字字段无效。");
    return {digest:identity,source_format:value.schema,items:workspace.items.length,unresolved:workspace.items.map((item:any)=>item.target_ref).filter(Boolean),message:"恢复文字和原始输入为独立案头；离线文件未包含的依据字节仍须从原环境恢复。",value,workspace};
  } else throw new Error("不是支持的 AMS 文件。");
  return {digest:identity,source_format:value.schema,items:workspace.items.length,unresolved:[],message:"旧依据保持原样。公开页面仅恢复已知对象；失踪对象可在本地模式保留。",value,workspace};
}
export async function importPortable(adapter:WorkspaceAdapter,preview:any,raw:Uint8Array) {
  const value=preview.value;
  if(value.schema==="ams-workspace/3") {
    await adapter.request("/public/cache",{records:value.public_records||[]});
    for(const encoded of Object.values(value.blobs))await adapter.upload(unbase64(encoded as string));
    const commands=[],latest=new Map<string,Entity>();
    for(const record of value.records) {
      let prior;
      try{prior=await adapter.load(record.kind,record.id,record.revision);}catch{}
      if(prior){if(JSON.stringify(prior)!==JSON.stringify(record))throw new Error("版本身份冲突。");continue;}
      const key=record.kind+"/"+record.id;
      if(!latest.has(key)){let existing;try{existing=await adapter.load(record.kind,record.id);}catch{}if(existing)throw new Error("这个对象已在页面中继续；先下载当前案头，再打开独立页面比较。");}
      commands.push(makeCommand(record,latest.get(key)));latest.set(key,record);
    }
    if(commands.length)await adapter.applyUnit(commands);
    return {mapping:{roots:value.roots,format:value.schema}};
  }
  const commands:any[]=[],workspace=preview.workspace;
  const artifact=async(bytes:Uint8Array)=>{const blob=await adapter.upload(bytes),item=await makeRecord("artifact",{media_type:"application/json",byte_length:blob.byte_length,artifact_digest:blob.digest,storage:{kind:"blob",locator:blob.digest},role:"other",visibility:"private",obtained_at:new Date().toISOString()});commands.push(makeCommand(item));return item;};
  const original=await artifact(raw),thread=await makeRecord("thread",{title:workspace.title||"",byline:"Local researcher",status:"open",payload:{original_import_ref:pointer(original),attention:"resting"}});commands.push(makeCommand(thread));
  const items=[];
  for(const old of workspace.items){const saved=await artifact(utf8(old));items.push({key:(old.kind||old.public_kind||"recovered")+":"+(old.id||old.public_id||old.key),legacy:{kind:old.kind||old.public_kind||"recovered",id:old.id||old.public_id||old.key},title:old.title||old.id||old.public_id||old.key||"恢复的材料",target_ref:pointer(saved),representation_ref:pointer(saved),binding:"review-required",anchor:old.anchor||"",note:old.note||"",legacy_excerpts:old.excerpts||old.legacy_excerpts||[],excerpt_refs:[]});}
  const session=await makeRecord("session",{thread_ref:pointer(thread),visibility:"private",started_at:new Date().toISOString(),payload:{items,question:workspace.question||"",synthesis:workspace.synthesis||"",next:workspace.next||"",attention:"resting",return_when:workspace.return_when||"",compare:workspace.compare||[],original_import_ref:pointer(original)}});commands.push(makeCommand(session));await adapter.applyUnit(commands);
  return {mapping:{roots:[pointer(thread),pointer(session)],format:value.schema}};
}
