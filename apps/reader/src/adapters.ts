import type {Command, Entity, EntityRef, WorkspaceAdapter} from "./types";
import {validateCommand} from "../.build/contracts.js";
import {contentDigest,canonicalObjectBytes} from "../../../packages/research-core/canonical.js";

export const actor = {kind: "human" as const, id: "actor:local-researcher"};
export const pointer = (item: Entity): EntityRef => ({kind: item.kind, id: item.id, revision: item.revision});
export const identity = (kind: string) => `${kind}:${crypto.randomUUID().replaceAll("-", "")}`;
export const utf8 = (value: unknown) => new TextEncoder().encode(JSON.stringify(value));
export function base64(bytes: Uint8Array): string {
  let value = "";
  for (let i=0; i<bytes.length; i+=8192) value += String.fromCharCode(...bytes.subarray(i, i+8192));
  return btoa(value);
}
export const unbase64 = (value: string) => Uint8Array.from(atob(value), character => character.charCodeAt(0));
export async function digest(bytes: Uint8Array) {
  return [...new Uint8Array(await crypto.subtle.digest("SHA-256", bytes as BufferSource))].map(n=>n.toString(16).padStart(2,"0")).join("");
}
export async function makeRecord(kind: string, fields: Record<string, unknown>, previous?: Entity): Promise<Entity> {
  const revision = identity("rev");
  const item: any = {schema:"ams-core/2", kind, id:previous?.id || identity(kind), ...fields, revision, state_revision:revision};
  item.content_digest = await contentDigest(item);
  return item;
}
export async function revise(item: Entity, changes: Record<string, unknown>) {
  const {schema,kind,id,revision,state_revision,content_digest,...fields} = item;
  return makeRecord(kind,{...fields,...changes},item);
}
export function makeCommand(item: Entity, previous?: Entity): Command {
  const command_id = identity("command");
  return {schema:"ams-command/1",kind:"command",command_id,idempotency_key:command_id,
    operation:previous?"update":"create",target:{kind:item.kind,id:item.id},actor,record:item,
    ...(previous ? {expected_revision:previous.state_revision} : {})};
}
export class RequestError extends Error {
  constructor(public detail: any, public status: number) {super(detail.message || detail.code || "操作未完成");}
}
export class LocalAdapter implements WorkspaceAdapter {
  capabilities = {mode:"local" as const,durable:true,jobs:true};
  constructor(private token: string) {}
  async request(path: string, body?: unknown) {
    const response = await fetch("/api"+path, {method:body===undefined?"GET":"POST",headers:{Authorization:"Bearer "+this.token,...(body===undefined?{}:{"Content-Type":"application/json"})},...(body===undefined?{}:{body:JSON.stringify(body)})});
    const value = await response.json();
    if (!response.ok) throw new RequestError(value,response.status);
    return value;
  }
  async list(kind?: string) {return (await this.request("/entities"+(kind?"?kind="+encodeURIComponent(kind):""))).records;}
  load(kind: string,id: string,revision?: string) {return this.request("/entity?"+new URLSearchParams({kind,id,...(revision?{revision}:{})}));}
  apply(command: Command) {return this.request("/commands",command);}
  applyUnit(commands: Command[]) {return this.request("/units",{commands});}
  upload(bytes: Uint8Array) {return this.request("/blobs",{base64:base64(bytes)});}
  async blob(digest: string) {return unbase64((await this.request("/blob?"+new URLSearchParams({digest}))).base64);}
  export(roots: EntityRef[]) {return this.request("/export",{roots});}
}
export class EphemeralAdapter implements WorkspaceAdapter {
  private queue:Promise<any>=Promise.resolve();
  private preview:any=null;
  private imported=new Map<string,any>();
  private importing=new Map<string,Promise<any>>();
  private publicSnapshots=new Map<string,Entity>();
  constructor(private publicData:any={materials:[],studies:[],questions:[],findings:[]},private publicLoader?:(ref:EntityRef)=>Promise<Entity>) {}
  async cachePublic(records:Entity[]) {
    const {validateRecord}=await import("./portable"),candidate=new Map(this.publicSnapshots);
    for(const value of records){await validateRecord(value);const prior=candidate.get(value.revision);if(prior&&new TextDecoder().decode(canonicalObjectBytes(prior))!==new TextDecoder().decode(canonicalObjectBytes(value)))throw new Error("公开引用快照身份冲突。");candidate.set(value.revision,structuredClone(value));}
    this.publicSnapshots=candidate;
  }
  capabilities = {mode:"public" as const,durable:false,jobs:false};
  private snapshots = new Map<string,Entity>();
  private current = new Map<string,string>();
  private receipts = new Map<string,{command: string;receipt:any}>();
  private blobs = new Map<string,Uint8Array>();
  async list(kind?: string) {return [...this.current.values()].map(key=>structuredClone(this.snapshots.get(key)!)).filter(item=>!kind||item.kind===kind);}
  async load(kind: string,id: string,revision?: string) {
    const key = revision || this.current.get(kind+"/"+id);
    let item = key && (this.snapshots.get(key)||this.publicSnapshots.get(key));
    if(!item&&revision&&this.publicLoader){const value=await this.publicLoader({kind,id,revision});if(value.kind!==kind||value.id!==id||value.revision!==revision)throw new Error("公开 shard 与引用身份不一致。");await this.cachePublic([value]);item=value;}
    if (!item || item.kind!==kind || item.id!==id) throw new RequestError({code:"not-found",message:"当前页面没有这个对象。"},404);
    return structuredClone(item);
  }
  async apply(command: Command) {
    return (await this.applyUnit([command])).receipts[0];
  }
  async applyUnit(commands: Command[]) {
    const work=this.queue.catch(()=>{}).then(()=>this.commitUnit(commands));this.queue=work;return work;
  }
  private async commitUnit(commands:Command[]) {
    if(!Array.isArray(commands)||!commands.length||commands.length>512)throw new Error("一次操作应含 1–512 个命令。");
    const {validateRecord}=await import("./portable");
    for(const command of commands){
      if(!validateCommand(command)||command.record.kind!==command.target.kind||command.record.id!==command.target.id)throw new Error("命令不符合 AMS schema 或目标身份不一致。");
      await validateRecord(command.record);
      const value=command.record;if(value.kind==="artifact"&&value.storage.kind==="blob"){const bytes=this.blobs.get(value.artifact_digest);if(!bytes||bytes.length!==value.byte_length)throw new Error("缺少完整依据文件。");}
    }
    const receipts = new Map(this.receipts), current = new Map(this.current), snapshots = new Map(this.snapshots);
    const results = commands.map(command=>{
      const key = command.target.kind+"/"+command.target.id, encoded = new TextDecoder().decode(canonicalObjectBytes(command));
      const existing = receipts.get(command.command_id)||receipts.get(command.idempotency_key);
      if (existing) {
        if (existing.command!==encoded) throw new RequestError({code:"idempotency-conflict"},409);
        return existing.receipt;
      }
      const base = current.get(key);
      if (command.operation==="create" ? !!base || command.expected_revision!==undefined : base!==command.expected_revision || !base)
        throw new RequestError({code:"revision-conflict",message:"页面中的对象已变化；你的输入仍在。",current:base&&snapshots.get(base),rejected_command:command},409);
      if (snapshots.has(command.record.revision)) throw new RequestError({code:"revision-reuse"},409);
      const receipt = {schema:"ams-command-receipt/1",command_id:command.command_id,target:command.target,state_revision:command.record.revision,ephemeral:true};
      snapshots.set(command.record.revision,structuredClone(command.record));current.set(key,command.record.revision);receipts.set(command.command_id,{command:encoded,receipt});receipts.set(command.idempotency_key,{command:encoded,receipt});
      return receipt;
    });
    const {exactRefs,validateClosure}=await import("./portable");
    const visited=new Set<string>();
    const resolve=async(value:Entity)=>{if(visited.has(value.revision))return;visited.add(value.revision);for(const ref of exactRefs(value)){const record=snapshots.get(ref.revision)||await this.load(ref.kind,ref.id,ref.revision);await resolve(record);}};
    for(const c of commands)await resolve(c.record);
    validateClosure([...snapshots.values()],[...this.publicSnapshots.values()]);
    for(const command of commands)if(command.record.kind==="session")this.checkCapacity(command.record,snapshots);
    this.receipts=receipts;this.current=current;this.snapshots=snapshots;
    return {receipts:results};
  }
  async upload(bytes: Uint8Array) {const value="sha256:"+await digest(bytes);this.blobs.set(value,bytes.slice());return {digest:value,byte_length:bytes.length};}
  async blob(digest: string) {const bytes=this.blobs.get(digest);if(!bytes)throw new Error("页面内依据已不可用。");return bytes.slice();}
  private exportSnapshot(roots:EntityRef[],snapshots=this.snapshots) {
    const selected = new Set<string>(),public_refs:EntityRef[]=[],public_records:Entity[]=[];
    const walk=(value:any)=>{
      if (!value||typeof value!=="object") return;
      if (Object.keys(value).sort().join(",")==="id,kind,revision" && snapshots.has(value.revision) && !selected.has(value.revision)) {selected.add(value.revision);walk(snapshots.get(value.revision));}
      if(Object.keys(value).sort().join(",")==="id,kind,revision"&&!snapshots.has(value.revision)&&!public_refs.some(r=>r.kind===value.kind&&r.id===value.id&&r.revision===value.revision)){const record=this.publicSnapshots.get(value.revision);if(!record)throw new Error("缺少固定依据；先恢复引用快照。");public_refs.push(value);public_records.push(record);walk(record);}
      Object.values(value).forEach(item=>walk(item));
    };
    roots.forEach(walk);
    const records=[...snapshots.values()].filter(item=>selected.has(item.revision));
    const blobs=Object.fromEntries(records.filter(item=>item.kind==="artifact"&&item.storage.kind==="blob").map(item=>{const bytes=this.blobs.get(item.artifact_digest);if(!bytes)throw new Error("缺少完整依据文件。");return [item.artifact_digest,base64(bytes)];}));
    return {schema:"ams-workspace/3",exported_at:new Date().toISOString(),roots,records,blobs,public_refs,public_records};
  }
  checkCapacity(record:Entity,snapshots=this.snapshots) {
    if(record.kind!=="session")return;
    const candidate=new Map(snapshots);candidate.set(record.revision,record);
    const pack=this.exportSnapshot([pointer(record)],candidate);
    if(pack.records.length>512||new TextEncoder().encode(JSON.stringify(pack,null,2)).length>32*1024*1024)throw new RequestError({code:"capacity",message:"这个案头的完整保存文件将超过 32 MiB 或 512 个版本；已有内容保留，请另开案头。"},413);
  }
  async export(roots:EntityRef[]) {const result=this.exportSnapshot(roots);if(new TextEncoder().encode(JSON.stringify(result,null,2)).length>32*1024*1024)throw new Error("完整保存文件超过 32 MiB。");return result;}
  async request(path:string,body?:any): Promise<any> {
    const {previewPortable,importPortable}=await import("./portable");
    if(path==="/public/cache"){await this.cachePublic(body.records);return {};}
    if(path==="/import/preview") {const raw=unbase64(body.base64),preview=await previewPortable(raw,this.publicData);this.preview={...preview,raw};const {value,workspace,...report}=preview;return report;}
    if(path==="/import/confirm") {if(this.imported.has(body.digest))return this.imported.get(body.digest);if(this.importing.has(body.digest))return this.importing.get(body.digest);if(this.preview?.digest!==body.digest)throw new Error("预览已变化，请重新选择文件。");const work=importPortable(this,this.preview,this.preview.raw).then(result=>{this.imported.set(body.digest,result);return result;}).finally(()=>this.importing.delete(body.digest));this.importing.set(body.digest,work);return work;}
    throw new Error("此操作需要明确启动本地研究环境。当前文字仍可下载带走。");
  }
}

export function download(name:string,value:unknown,type="application/json") {
  const blob = new Blob([typeof value==="string"?value:JSON.stringify(value,null,2)],{type:type+";charset=utf-8"});
  const url=URL.createObjectURL(blob), link=document.createElement("a");link.href=url;link.download=name;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
