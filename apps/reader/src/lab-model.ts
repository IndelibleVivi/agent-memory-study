import {makeCommand,makeRecord,pointer} from "./adapters";
import type {Command,Entity,WorkspaceAdapter} from "./types";

export type StudyCapability={id:string;operations:string[];evidence_kind:string;provider:boolean;network:boolean};
export type Plan={study:string;operation:string;parameters?:Record<string,unknown>;source_job?:string};
export type Job={id:string;state:string;created_at:string;updated_at:string;plan?:Plan;attempts?:any[];result?:any};
export const TERMINAL=new Set(["succeeded","failed","cancelled","interrupted","indeterminate","blocked"]);
export const STATES:Record<string,string>={queued:"等待执行",preparing:"准备中",running:"正在执行","cancel-requested":"正在确认取消",succeeded:"本次操作完成",failed:"执行失败",cancelled:"已取消",interrupted:"执行中断",indeterminate:"提交结果未知",blocked:"条件未满足"};
export const OPERATIONS:Record<string,string>={inspect:"查看已保存结果",prepare:"检查执行计划",run:"开始本地计算",replay:"核验本次 raw", "check-saved-results":"核查公开保存结果",packet:"整理复现包"};
export const STUDIES:Record<string,{title:string;question:string;boundary:string;saved:string;article?:string;command:string}>={
 "observation-contract-study":{title:"可区分性与观察契约",question:"相同观察能否容纳不同答案？允许的行动能把它们分开吗？",boundary:"有限确定性构造；经验样本 0。碰撞 witness 与可执行区分序列分开。",saved:"results.json",article:"distinguishability-and-observation",command:"python3 research/observation-contract-study/study.py --check"},
 "conditional-contribution-study":{title:"信息的条件贡献",question:"S 已送达之后，在 B 已有时还增加了什么？",boundary:"真实 SQLite FTS5；scripted 与携带 gold 的 oracle 分列。4 个原创 family；used unknown。",saved:"sample-results.json",article:"conditional-information-and-use",command:"python3 research/conditional-contribution-study/study.py --check"},
 "representation-use-study":{title:"从表征到使用",question:"材料被选中、送达、引用与实际有用，是同一回事吗？",boundary:"Scripted/oracle 控制；selected 是原生全部材料，没有独立 retriever；used unknown。",saved:"sample-results.json",command:"python3 research/representation-use-study/study.py check-sample"},
 "revision-propagation-study":{title:"修订如何传播",question:"旧写回会在修正后再次出现吗？",boundary:"纵向 typed synthetic controls；干预前 checkpoint 匹配，后续中介不重新匹配。",saved:"results.json",command:"python3 research/revision-propagation-study/study.py check-sample"},
 "task-relative-sufficiency":{title:"任务相关的充分性",question:"对当前任务足够的记忆，换一个问题后还够吗？",boundary:"独立有限枚举；数学构造不等于模型表现。",saved:"results.json",command:"python3 research/task-relative-sufficiency/study.py --check"},
 "c2c-cache-retraction-study":{title:"C2C 历史数值控制",question:"撤回缓存后，原来的数值差异还在吗？",boundary:"只读历史 receipt；float32 阈值失败与 precision amendment 保留。早期完整 tensors 未发布。",saved:"results.json",command:"见 research/c2c-cache-retraction-study/protocol.md 的历史复验边界"},
 "decision-learning-study":{title:"结构化决策学习",question:"限定标签上的纠正表现，能说明什么？",boundary:"只读已保存分类器结果，不运行新训练；不推出自然语言或 agent 收益。",saved:"results.json",command:"python3 research/decision-learning-study/study.py --check"}
};
const futureStates=["w00","w01","w10","w11"];
export const P8_MODELS=[
 {id:"future-access",states:futureStates,label:"未来问题 · 获准重访"},
 ...["permitted","available","correct_revision","target_bound","adequate_coverage"].map(gate=>({id:"future-denied-"+gate,states:futureStates,label:"重访门槛关闭 · "+gate})),
 {id:"future-side-information",states:futureStates,label:"已有侧信息"},
 {id:"writeback-active",states:["live","cached","withdrawn-live","withdrawn-cached"],label:"写回 · 可撤回"},
 {id:"writeback-forbidden",states:["live","cached","withdrawn-live","withdrawn-cached"],label:"写回 · 禁止撤回"},
 {id:"equivalent-control",states:["a","b"],label:"真正不可区分控制"},
 {id:"score-weighted",states:["revision","revision-ready","scope","scope-ready"],label:"相同总分 · 非均匀成本"},
 {id:"score-unit-cost",states:["revision","revision-ready","scope","scope-ready"],label:"相同总分 · 单位成本"},
 {id:"nonpairwise-control",states:["a","b","c"],label:"两两相容 / 全类不相容"}
];
export type PlanInput={model:string;instrument:string;left:string;right:string;steps:string;cost:string;limit:string};
export const DEFAULT_INPUT:PlanInput={model:"score-weighted",instrument:"search-pair",left:"revision",right:"scope",steps:"",cost:"",limit:"24"};
export function buildPlan(capability:StudyCapability,operation:string,input:PlanInput):Plan {
 if(!capability.operations.includes(operation)||operation==="replay")throw new Error("请选择此研究实际支持的操作。");
 const parameters:Record<string,unknown>={};
 if(operation==="run"&&capability.id==="observation-contract-study"){
  const model=P8_MODELS.find(m=>m.id===input.model);if(!model)throw new Error("请选择声明模型。");
  parameters.operation=input.instrument;parameters.model=model.id;
  if(!["search-pair","analyze-model"].includes(input.instrument))throw new Error("未知 instrument 操作。");
  if(input.instrument==="search-pair"){
   if(!model.states.includes(input.left)||!model.states.includes(input.right)||input.left===input.right)throw new Error("请选择模型内两个不同状态。");
   Object.assign(parameters,{left:input.left,right:input.right});
   if(input.steps!==""){if(!/^\d+$/.test(input.steps)||Number(input.steps)>100)throw new Error("步数界限须为 0–100 的整数；留空为无界。");parameters.max_steps=Number(input.steps);}
   if(input.cost!==""){if(!/^(?:\d+(?:\.\d+)?|\d+\/[1-9]\d*)$/.test(input.cost))throw new Error("成本须为非负数或分数，例如 1/2；留空为无界。");parameters.max_cost=input.cost;}
  }
 }else if(operation==="run"&&["conditional-contribution-study","representation-use-study","revision-propagation-study"].includes(capability.id)&&input.limit!==""){
  if(!/^\d+$/.test(input.limit)||Number(input.limit)<1||Number(input.limit)>100)throw new Error("本地上限须为 1–100；留空按原生完整/默认计划执行。");parameters.limit=Number(input.limit);
 }
 return {study:capability.id,operation,parameters};
}
// A lost HTTP acknowledgement reuses the same key; it never creates an automatic retry attempt.
export class LabClient {
 private pending:{payload:string;key:string}|null=null;
 constructor(private adapter:WorkspaceAdapter){}
 async submit(plan:Plan){const payload=JSON.stringify(plan);if(this.pending&&this.pending.payload!==payload)throw new Error("上一提交尚未收到回执；先重试原提交或在运行列表确认后再更改计划。");this.pending??={payload,key:"lab:"+crypto.randomUUID()};const result=await this.adapter.request("/jobs",{plan,idempotency_key:this.pending.key});this.pending=null;return result as Job;}
 retry(id:string,key:string){return this.adapter.request("/job/retry",{id,idempotency_key:key});}
}
export function nativeValue(value:any):any {
 let current=value;for(let i=0;i<4&&current?.result&&typeof current.result==="object"&&!current.rows&&!current.models&&!current.trace&&!current.pairs&&!current.provider_plan;i++)current=current.result;return current;
}
export function parseValue(value:any):any {if(typeof value!=="string")return value;try{return JSON.parse(value);}catch{return value;}}
export function stageValues(stage:any){
 const request=parseValue(stage.request),audit=stage.delivered??stage.audit,response=parseValue(stage.response);
 let delivered:any=null;
 if(typeof request?.memory==="string")delivered=request.memory;
 if(request?.messages){const user=request.messages.filter((m:any)=>m.role==="user").map((m:any)=>m.content).join("\n");const parsed=parseValue(user);delivered=typeof parsed==="object"?(parsed.memory??user):user;}
 return {request,audit,response,score:stage.score,delivered};
}
export type ObservationDraft={statement:string;scope:string;expected:string;observed:string;title:string;explanationA:string;explanationB:string;explanationC?:string;control:string;question:string;withDesign:boolean};
export async function prepareObservation(run:Entity,draft:ObservationDraft,locator:string){
 if(!(run.kind==="run"&&run.status==="complete")&&!(run.kind==="artifact"&&run.role==="receipt"))throw new Error("先固定一次成功 Run 或历史检查的准确依据。");
 if(!draft.statement.trim()||!draft.scope.trim())throw new Error("请写下实际观察与适用范围。");
 const observation=await makeRecord("observation",{...(run.kind==="run"?{run_ref:pointer(run)}:{}),scope:draft.scope.trim(),statement:[draft.statement.trim(),`证据位置：${locator}`,draft.expected&&`预期：${draft.expected}`,draft.observed&&`观察：${draft.observed}`].filter(Boolean).join("\n"),basis_refs:run.kind==="run"?run.result_artifact_refs||[]:[pointer(run)]});
 let design:Entity|null=null;
 if(draft.withDesign){if([draft.title,draft.explanationA,draft.explanationB,draft.control,draft.question,...(run.kind==="artifact"?[draft.explanationC||""]:[])].some(s=>!s.trim()))throw new Error("下一设计需要题名、竞争解释（历史控制需三项）、诊断对照和仍未解决的问题。");design=await makeRecord("design",{title:draft.title.trim(),status:"proposed-not-run",body:`依据 Observation：${observation.id} @ ${observation.revision}\n${run.kind==="run"?"Run":"历史 receipt（非新Run）"}：${run.id} @ ${run.revision}\n\n竞争解释 A：${draft.explanationA}\n竞争解释 B：${draft.explanationB}${draft.explanationC?`\n竞争解释 C：${draft.explanationC}`:""}\n\n诊断对照：${draft.control}\n\n未解决的问题：${draft.question}\n\n本设计未执行；不把任一解释自动当作结论。`});}
 return {observation,design,commands:[makeCommand(observation),...(design?[makeCommand(design)]:[])] as Command[]};
}
