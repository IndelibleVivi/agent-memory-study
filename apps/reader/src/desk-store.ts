import {actor,base64,identity,makeCommand,makeRecord,pointer,revise,RequestError,utf8} from "./adapters";
import type {CatalogueItem,Command,Content,Entity,SaveStatus,WorkspaceAdapter} from "./types";

type Editing = {record:Entity; status:SaveStatus; pending?:Command; error?:any; past:any[];future:any[];group:boolean; checkpoint?:string};
export type DeskState = {threads:Entity[];sessions:Entity[];active:string|null;edits:Record<string,Editing>;loading:boolean;creating:boolean;error:string|null;serial:number};
export class DeskStore {
  private listeners=new Set<()=>void>();
  private timers=new Map<string,ReturnType<typeof setTimeout>>();
  private inFlight=new Set<string>();
  private tick=0;
  private trimHistory(edits:Record<string,Editing>) {
    const frames=()=>Object.values(edits).flatMap(edit=>[...edit.past,...edit.future]);
    while(frames().length>20||utf8(frames()).length>8*1024*1024){
      const oldest=Math.min(...frames().map(frame=>frame.tick));
      for(const edit of Object.values(edits)){edit.past=edit.past.filter(frame=>frame.tick!==oldest);edit.future=edit.future.filter(frame=>frame.tick!==oldest);}
    }
    return edits;
  }
  private captureAttempt:{payload:string;key:string}|null=null;
  private createAttempt:{title:string;thread:Entity;session:Entity;commands:Command[]}|null=null;
  private creatingTask:Promise<Entity>|null=null;
  state:DeskState={threads:[],sessions:[],active:null,edits:{},loading:false,creating:false,error:null,serial:0};
  constructor(public adapter:WorkspaceAdapter) {}
  subscribe=(listener:()=>void)=>{this.listeners.add(listener);return()=>{this.listeners.delete(listener);};};
  snapshot=()=>this.state;
  private emit(patch:Partial<DeskState>={}) {this.state={...this.state,...patch,serial:this.state.serial+1};this.listeners.forEach(listener=>listener());}
  async refresh() {
    this.emit({loading:true,error:null});
    try {
      const [threads,sessions]=await Promise.all([this.adapter.list("thread"),this.adapter.list("session")]);
      this.emit({threads,sessions,loading:false});
      if(!this.state.active&&sessions.length)this.select(sessions[0].id);
    } catch(error) {this.emit({loading:false,error:String(error)});}
  }
  select(id:string) {
    if(this.state.creating)return;
    const record=this.state.sessions.find(item=>item.id===id);
    if(!record)return;
    const edits={...this.state.edits};
    if(!edits[id])edits[id]={record:structuredClone(record),status:this.adapter.capabilities.durable?"committed":"ephemeral",past:[],future:[],group:false};
    this.emit({active:id,edits});
  }
  hasUnsaved() {return this.state.creating||!!this.createAttempt||Object.values(this.state.edits).some(edit=>this.adapter.capabilities.durable?["pending","conflict","disconnected"].includes(edit.status):edit.checkpoint!==JSON.stringify(edit.record.payload));}
  active() {return this.state.active?this.state.edits[this.state.active]:undefined;}
  create(title="") {
    if(this.creatingTask)return this.creatingTask;
    this.emit({creating:true,error:null});
    this.creatingTask=(async()=>{
      try{
        if(!this.createAttempt){
          const thread=await makeRecord("thread",{title,byline:"Local researcher",status:"open",payload:{attention:"active",created_at:new Date().toISOString()}});
          const session=await makeRecord("session",{thread_ref:pointer(thread),visibility:"private",started_at:new Date().toISOString(),payload:{items:[],question:"",synthesis:"",next:"",attention:"active",return_when:"",compare:[],capture_refs:[]}});
          this.createAttempt={title,thread,session,commands:[makeCommand(thread),makeCommand(session)]};
        }
        const {thread,session,commands}=this.createAttempt;
        await this.adapter.applyUnit(commands);
        this.createAttempt=null;
        this.emit({threads:[thread,...this.state.threads.filter(r=>r.id!==thread.id)],sessions:[session,...this.state.sessions.filter(r=>r.id!==session.id)],creating:false});this.select(session.id);
        return session;
      }catch(error){this.emit({error:"新案头尚未确认创建；可重试同一笔请求。 "+String(error)});throw error;}
      finally{this.creatingTask=null;this.emit({creating:false});}
    })();
    return this.creatingTask;
  }
  edit(patch:Record<string,unknown>,id=this.state.active) {
    if(this.state.creating)return false;
    if(!id)return;
    const old=this.state.edits[id];if(!old)return;
    const payload={...old.record.payload,...patch};
    if(JSON.stringify(payload)===JSON.stringify(old.record.payload))return;
    try{this.adapter.checkCapacity?.({...old.record,payload});}catch(error){this.emit({error:String(error)});return false;}
    const past=old.group?old.past:[...old.past,{tick:++this.tick,payload:structuredClone(old.record.payload)}];
    if(utf8(payload).length>2*1024*1024){this.emit({error:"案头文字与状态超过 2 MiB；已有内容保留，请另开案头。"});return false;}
    const next={...old,record:{...old.record,payload},past,future:[],group:true,status:"pending" as const};
    this.emit({edits:this.trimHistory({...this.state.edits,[id]:next}),error:null});
    if(this.timers.has(id))clearTimeout(this.timers.get(id));
    this.timers.set(id,setTimeout(()=>void this.flush(id),600));
    return true;
  }
  endGroup(id=this.state.active) {if(id&&this.state.edits[id])this.emit({edits:{...this.state.edits,[id]:{...this.state.edits[id],group:false}}});}
  async flush(id=this.state.active) {
    if(!id||this.inFlight.has(id))return;
    const edit=this.state.edits[id];if(!edit||["committed","ephemeral","conflict"].includes(edit.status))return;
    this.inFlight.add(id);
    let pending=edit.pending;
    try {
      const base=this.state.sessions.find(item=>item.id===id)!;
      if(!pending){const next=await revise(base,{payload:edit.record.payload});pending=makeCommand(next,base);}
      this.emit({edits:{...this.state.edits,[id]:{...this.state.edits[id],pending,status:"pending",error:undefined}}});
      await this.adapter.apply(pending);
      const newest=this.state.edits[id], unchanged=JSON.stringify(newest.record.payload)===JSON.stringify(pending.record.payload);
      this.emit({sessions:this.state.sessions.map(item=>item.id===id?pending!.record:item),edits:{...this.state.edits,[id]:{...newest,record:unchanged?pending.record:newest.record,pending:undefined,status:unchanged?(this.adapter.capabilities.durable?"committed":"ephemeral"):"pending",error:undefined}}});
    } catch(error) {
      const conflict=error instanceof RequestError&&error.status===409;
      this.emit({edits:{...this.state.edits,[id]:{...this.state.edits[id],pending,status:conflict?"conflict":"disconnected",error:error instanceof RequestError?error.detail:{message:String(error)}}}});
    } finally {
      this.inFlight.delete(id);
      if(this.state.edits[id].status==="pending")void this.flush(id);
    }
  }
  async resolveConflict(choice:"current"|"mine") {
    const id=this.state.active, edit=this.active();if(!id||!edit)return;
    const current=await this.adapter.load("session",id);
    const record=choice==="current"?current:{...current,payload:edit.record.payload};
    this.emit({sessions:this.state.sessions.map(item=>item.id===id?current:item),edits:{...this.state.edits,[id]:{...edit,record,pending:undefined,error:undefined,status:choice==="current"?"committed":"pending",group:false}}});
    if(choice==="mine")await this.flush(id);
  }
  undo(redo=false) {
    const id=this.state.active, edit=this.active();if(!id||!edit)return;
    const source=redo?edit.future:edit.past;if(!source.length)return;
    const frame=source[source.length-1],payload=frame.payload, current={tick:frame.tick,payload:edit.record.payload};
    this.emit({edits:{...this.state.edits,[id]:{...edit,record:{...edit.record,payload},past:redo?[...edit.past,current]:edit.past.slice(0,-1),future:redo?edit.future.slice(0,-1):[...edit.future,current],group:false,status:"pending"}}});
    void this.flush(id);
  }
  async add(meta:CatalogueItem,content:Content,anchor="") {
    if(!this.active())await this.create();
    const edit=this.active()!, key=meta.kind+":"+meta.id;
    if(edit.record.payload.items.some((item:any)=>item.key===key))return;
    if(edit.record.payload.items.length>=24)throw new Error("一个案头最多留 24 个对象；可以再开一个案头继续。");
    if(meta.ref)await this.adapter.load(meta.ref.kind,meta.ref.id,meta.ref.revision);
    const bytes=utf8(content), blob=await this.adapter.upload(bytes);
    const artifact=await makeRecord("artifact",{media_type:"application/json",byte_length:blob.byte_length,artifact_digest:blob.digest,storage:{kind:"blob",locator:blob.digest},role:"authored",visibility:"private",...(meta.ref?{representation_of:meta.ref}:{}),obtained_at:new Date().toISOString()});
    await this.adapter.apply(makeCommand(artifact));
    const entry={key,public_kind:meta.kind,public_id:meta.id,title:meta.title,target_ref:meta.ref||pointer(artifact),representation_ref:pointer(artifact),binding:meta.ref?"pinned":"observed",anchor,note:"",excerpt_refs:[]};
    if(this.edit({items:[...this.active()!.record.payload.items,entry]})===false)throw new Error(this.state.error||"案头容量不足。");await this.flush();
  }
  async replaceBasis(key:string,meta:CatalogueItem,content:Content) {
    const payload=this.active()?.record.payload,item=payload?.items.find((r:any)=>r.key===key);if(!item||!meta.ref)return;
    await this.adapter.load(meta.ref.kind,meta.ref.id,meta.ref.revision);
    const bytes=utf8(content),blob=await this.adapter.upload(bytes),artifact=await makeRecord("artifact",{media_type:"application/json",byte_length:blob.byte_length,artifact_digest:blob.digest,storage:{kind:"blob",locator:blob.digest},role:"authored",visibility:"private",representation_of:meta.ref,obtained_at:new Date().toISOString()});
    await this.adapter.apply(makeCommand(artifact));
    const replacement={...item,public_kind:meta.kind,public_id:meta.id,title:meta.title,target_ref:meta.ref,representation_ref:pointer(artifact),binding:"pinned",previous_basis:[...(item.previous_basis||[]),{target_ref:item.target_ref,representation_ref:item.representation_ref}]};
    if(this.edit({items:payload.items.map((r:any)=>r.key===key?replacement:r)})===false)throw new Error(this.state.error||"案头容量不足。");
    this.endGroup();await this.flush();
  }
  async attachCapture(value:Entity) {
    if(!this.active())await this.create();
    const refs=this.active()!.record.payload.capture_refs||[];
    if(!refs.some((r:any)=>r.id===value.id)&&this.edit({capture_refs:[...refs,pointer(value)]})===false)throw new Error(this.state.error||"案头容量不足。");
    await this.flush();return value;
  }
  async capture(input:string,why_now:string) {
    if(!input.trim())throw new Error("先留下一句话或一个链接。");
    let value:Entity;
    if(this.adapter.capabilities.durable){
      const payload=JSON.stringify({input,why_now});
      if(this.captureAttempt?.payload!==payload)this.captureAttempt={payload,key:identity("capture-command")};
      value=(await this.adapter.request("/capture",{text:input,why_now,channel:"web",idempotency_key:this.captureAttempt.key})).capture;
    }else{value=await makeRecord("capture",{captured_at:new Date().toISOString(),actor,channel:"web",input,why_now,attention:"resting",visibility:"private"});await this.adapter.apply(makeCommand(value));}
    await this.attachCapture(value);this.captureAttempt=null;return value;
  }
  async captureFile(file:File,input="",why="") {
    if(file.size>23*1024*1024)throw new Error("浏览器单次文件限 23 MiB；较大原件请用本地 CLI 的 file plan。");
    if(!this.adapter.capabilities.durable&&(this.active()?.record.payload.items.length||0)>=24)throw new Error("当前案头已满，请另开研究线；文件尚未捕获。");
    const bytes=new Uint8Array(await file.arrayBuffer());
    if(this.adapter.capabilities.durable){const result=await this.adapter.request("/capture/file",{text:input||file.name,why_now:why,base64:base64(bytes),media_type:file.type||"application/octet-stream",channel:"web",idempotency_key:identity("capture-file")});return this.attachCapture(result.capture);}
    if(!this.active())await this.create();
    const capture=await makeRecord("capture",{captured_at:new Date().toISOString(),actor,channel:"web",input:input||file.name,why_now:why||"主动选定文件",attention:"resting",visibility:"private"}),blob=await this.adapter.upload(bytes);
    await this.adapter.apply(makeCommand(capture));
    const artifact=await makeRecord("artifact",{media_type:file.type||"application/octet-stream",byte_length:blob.byte_length,artifact_digest:blob.digest,storage:{kind:"blob",locator:blob.digest},role:"source-manifestation",visibility:"private",representation_of:pointer(capture),obtained_at:new Date().toISOString()});await this.adapter.apply(makeCommand(artifact));
    const payload=this.active()!.record.payload;if(this.edit({capture_refs:[...(payload.capture_refs||[]),pointer(capture)],items:[...payload.items,{key:artifact.id,title:file.name,target_ref:pointer(capture),representation_ref:pointer(artifact),binding:"observed",anchor:"",note:"",excerpt_refs:[]}]})===false)throw new Error(this.state.error||"案头容量不足。");await this.flush();return capture;
  }
  async excerpt(key:string,quote:string,anchor:string) {
    const edit=this.active();if(!edit)return;
    const item=edit.record.payload.items.find((row:any)=>row.key===key);if(!item)return;
    if((item.excerpt_refs||[]).length>=12)throw new Error("一个对象最多保留 12 条摘录；已有内容不变。");
    const value=await makeRecord("excerpt",{target_ref:item.target_ref,representation_ref:item.representation_ref,selector:JSON.stringify({quote,anchor}),comment:""});
    await this.adapter.apply(makeCommand(value));
    if(this.edit({items:edit.record.payload.items.map((row:any)=>row.key===key?{...row,excerpt_refs:[...(row.excerpt_refs||[]),pointer(value)]}:row)})===false)throw new Error(this.state.error||"案头容量不足。");await this.flush();
  }
  async exportActive(checkpoint=true) {
    const activeId=this.state.active;
    if(activeId)while(this.inFlight.has(activeId))await new Promise(resolve=>setTimeout(resolve,10));
    await this.flush();
    const edit=this.active();if(!edit)throw new Error("先打开一个案头。");
    if(["disconnected","conflict","pending"].includes(edit.status))
      return {schema:"ams-uncommitted-input/1",message:"这些输入尚未收到保存回执。先保存此文件，恢复连接后再比较。",record:edit.record,pending:edit.pending||null};
    const thread=this.state.threads.find(item=>item.id===edit.record.thread_ref.id)!;
    const result=await this.adapter.export([pointer(thread),pointer(edit.record)]);
    if(checkpoint)this.emit({edits:{...this.state.edits,[edit.record.id]:{...edit,checkpoint:JSON.stringify(edit.record.payload)}}});
    return result;
  }
}

export function privateWorkspaceMarkdown(pack:any) {
  const records=pack.records||[pack.record].filter(Boolean),sessions=records.filter((r:any)=>r.kind==="session");
  const lines=["# AMS 私人研究案头", "", "私人文字与固定依据；请自行保管。此 Markdown 供阅读，恢复完整状态请使用同时下载的 JSON。", ""];
  for(const session of sessions){const p=session.payload;lines.push("## 当前停点",p.question||"", "", "### 形成的理解",p.synthesis||"","", "### 下次继续",p.next||"","", "### 回来条件",p.return_when||"", "");
    for(const item of p.items||[]){lines.push("## "+(item.title||item.key),"",item.note||"","", "固定版本："+item.target_ref?.revision, "位置："+(item.anchor||""),"");
      for(const ref of item.excerpt_refs||[]){const excerpt=records.find((r:any)=>r.revision===ref.revision);if(excerpt){let quote=excerpt.selector;try{quote=JSON.parse(quote).quote||quote;}catch{}const annotation=item.excerpt_annotations?.[ref.id]||{};lines.push("### 摘录",quote,"",annotation.comment||excerpt.comment||"",annotation.role?"用途："+annotation.role:"","");}}
      for(const excerpt of item.legacy_excerpts||[])lines.push("### 旧摘录",excerpt.quote||excerpt.text||"",excerpt.note||"","");
    }
    if(p.comparison_note)lines.push("## 对读之间",p.comparison_note,"");
  }
  for(const capture of records.filter((r:any)=>r.kind==="capture"))lines.push("## 遇见",capture.input,"",capture.why_now||"","");
  return lines.join("\n");
}
