import {actor,pointer,RequestError} from "./adapters";
import type {Entity,EntityRef,WorkspaceAdapter} from "./types";
import type {DeskStore} from "./desk-store";
export type ReviewRow={ref:EntityRef;title:string;scope:string;public:boolean;editable:boolean};
export type ReviewDraft={decision:string;body:string;scope:string;title:string;intro:string;byline:string;explanation:string;open_question:string;explanationA:string;explanationB:string;control:string};
export const DECISIONS:Record<string,string>={maintain:"维持 · 检查后不修改",narrow:"缩小适用范围",rewrite:"改写解释", "needs-experiment":"需要新的诊断实验",defer:"暂不确定 · 先保留"};
export const RELATIONS:Record<string,string>={background:"背景",analogy:"类比",supports:"支持",limits:"限定",challenges:"挑战",derives:"推导"};
export const refKey=(ref:EntityRef)=>[ref.kind,ref.id,ref.revision].join("/");
export const sameRef=(a?:EntityRef,b?:EntityRef)=>!!a&&!!b&&refKey(a)===refKey(b);
export class ReviewClient {
 private pending=new Map<string,{payload:string;key:string;body:any}>();
 constructor(private adapter:WorkspaceAdapter){}
 async write(path:string,body:any,keyed=true){const payload=JSON.stringify(body),prior=this.pending.get(path);if(prior&&prior.payload!==payload)throw new Error("上一操作回执尚未确认，请返回原输入重试或下载原命令；不会替换其依据。");const item=prior||{payload,key:"review:"+crypto.randomUUID(),body};this.pending.set(path,item);try{const result=await this.adapter.request(path,{...body,...(keyed?{idempotency_key:item.key}:{})});this.pending.delete(path);return result;}catch(error){if(error instanceof RequestError&&error.status>=400&&error.status<500&&![408,429].includes(error.status))this.pending.delete(path);throw error;}}
 outstanding(){return [...this.pending].map(([path,value])=>({path,body:value.body,idempotency_key:value.key}));}
}
export async function awaitDeskSave(desk:DeskStore,id:string,timeoutMs=10000){
 await desk.flush(id);
 return new Promise<void>((resolve,reject)=>{let unsubscribe=()=>{};const finish=(error?:Error)=>{clearTimeout(timer);unsubscribe();error?reject(error):resolve();};const check=()=>{const edit=desk.state.edits[id];if(!edit)return finish(new Error("案头已切换；原草稿仍保留。"));if(["committed","ephemeral"].includes(edit.status))finish();else if(["conflict","disconnected"].includes(edit.status))finish(new Error("案头保存尚未确认；请处理连接或版本冲突，草稿保留。"));};const timer=setTimeout(()=>finish(new Error("等待案头回执超时；不会把未确认输入标作已保存。")),timeoutMs);unsubscribe=desk.subscribe(check);check();});
}
export function draftFrom(opened:any):ReviewDraft {const r=opened.record;return {decision:"maintain",body:opened.body||"",scope:opened.scope||"",title:r.title||"",intro:r.intro||"",byline:r.byline||"",explanation:"",open_question:opened.open_question||"",explanationA:"",explanationB:"",control:""};}
export function proposalRequest(base:Entity,draft:ReviewDraft){
 if(!DECISIONS[draft.decision]||!draft.explanation.trim())throw new Error("请明确这次决定与依据。");
 let explanation=draft.explanation;
 if(draft.decision==="needs-experiment"){
  if([draft.explanationA,draft.explanationB,draft.control,draft.open_question].some(v=>!v.trim()))throw new Error("实验设计需要两个竞争解释、诊断对照和未解决的问题。");
  explanation+=`\n\n竞争解释 A：${draft.explanationA}\n竞争解释 B：${draft.explanationB}\n诊断对照：${draft.control}`;
 }
 const metadata=base.kind==="entry"?{title:draft.title,intro:draft.intro,byline:draft.byline}:base.kind==="claim_revision"?{title:draft.title,byline:draft.byline}:undefined;
 return {base_ref:pointer(base),decision:draft.decision,body:draft.body,scope:draft.scope,explanation,open_question:draft.open_question,...(metadata?{metadata}:{})};
}
export function relationFields(from:EntityRef,to:Entity,relation:string,scope:string,binding:string,locator:string,rationale:string){
 if(!RELATIONS[relation]||![scope,binding,locator,rationale].every(s=>s.trim()))throw new Error("关系需要范围、绑定、具体位置和理由。");
 return {from_ref:from,to_ref:pointer(to),relation,scope,scope_binding:binding,locator,rationale,generated_by:actor,method_version:"review-ui/1"};
}
export function bundleFields(conclusion:Entity,mode:string,selected:Entity[],rationale:string,independence:string,argument:string){
 if(conclusion.kind!=="claim_revision"||!selected.length||!rationale.trim())throw new Error("先选固定判断、已接受理由与组合说明。");
 if(independence==="argued-independent"&&!argument.trim())throw new Error("来源数量不证明独立；请给出独立性论证。");
 const common={conclusion_ref:pointer(conclusion),scope:conclusion.scope,scope_binding:conclusion.scope_binding,rationale,combination:mode,independence:{status:independence,...(argument.trim()?{argument}: {})}};
 if(mode==="all-premises"){
  if(selected.some(r=>r.kind!=="evidence_relation"||r.status!=="accepted"||!sameRef(r.to_ref,pointer(conclusion))))throw new Error("AND只能选择该固定结论的正式关系。");
  const unique=new Map(selected.map(r=>[refKey(r.from_ref),r.from_ref]));return {...common,premise_refs:[...unique.values()],relation_refs:selected.map(pointer)};
 }
 if(mode!=="alternative-warrants"||selected.some(r=>r.kind!=="support_bundle"||r.combination!=="all-premises"||!sameRef(r.conclusion_ref,pointer(conclusion))))throw new Error("OR只能选择同一固定结论的完整AND warrant。");
 return {...common,warrant_refs:selected.map(pointer)};
}
export function itemText(item:any,baseBody:string){return item.change?.mode==="replace-fields"?item.change.fields?.payload?.bodyMarkdown??item.change.fields?.claim??baseBody:baseBody;}
export function deliveryRequest(manifest_ref:EntityRef,values:{repository:string;build:string;site:string;commit:string;repo_url:string;digest:string;site_url:string;deployment:string;observed_at:string;confirmed:boolean}){
 if(!values.confirmed)throw new Error("请先明确确认你已核对这些交付观察。");
 const delivery:any={repository:{state:values.repository},build:{state:values.build},site:{state:values.site}};
 if(values.repository==="visible"){if(!/^[a-f0-9]{40}$/.test(values.commit)||!/^https?:\/\//.test(values.repo_url))throw new Error("可见仓库需要确切commit与观察URL。");Object.assign(delivery.repository,{commit:values.commit,url:values.repo_url,observed_at:values.observed_at});}
 if(values.build!=="not-built"){if(!/^[a-f0-9]{40}$/.test(values.commit))throw new Error("build需要确切source commit。");Object.assign(delivery.build,{source_commit:values.commit,...(values.digest?{artifact_digest:values.digest}:{})});}
 if(values.site==="active")Object.assign(delivery.site,{source_commit:values.commit,artifact_digest:values.digest,deployment_id:values.deployment,url:values.site_url,verified_at:values.observed_at});
 return {manifest_ref,delivery};
}
