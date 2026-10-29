import React,{useEffect,useRef,useState} from "react";
import {Link} from "react-router";
import type {Bootstrap,Entity,EntityRef,WorkspaceAdapter} from "./types";
import type {DeskStore} from "./desk-store";

function useRecord(adapter:WorkspaceAdapter,pointer:EntityRef) {
  const [record,setRecord]=useState<Entity|null>(null),[error,setError]=useState("");
  useEffect(()=>{let active=true;setRecord(null);setError("");adapter.load(pointer.kind,pointer.id,pointer.revision).then(value=>{if(active)setRecord(value);}).catch(error=>{if(active)setError(String(error));});return()=>{active=false;};},[adapter,pointer.kind,pointer.id,pointer.revision]);
  return {record,error};
}
export function ExcerptCard({adapter,pointer,annotation,onAnnotation}:{adapter:WorkspaceAdapter;pointer:EntityRef;annotation?:any;onAnnotation?:(patch:any)=>void}) {
  const {record,error}=useRecord(adapter,pointer);
  let selected:{quote?:string;anchor?:string}={};
  if(record){try{selected=JSON.parse(record.selector);}catch{selected={quote:record.selector};}}
  return <blockquote className="excerpt-card">{error?<p role="alert">{error}</p>:<><p>{selected.quote||"正在取回摘录…"}</p>{record?.comment&&<p className="margin-note">{record.comment}</p>}<small>摘录自固定依据 · {selected.anchor}</small>{onAnnotation&&<><label>这段摘录的批注<textarea aria-label="这段摘录的批注" value={annotation?.comment||""} onChange={e=>onAnnotation({comment:e.target.value})}/></label><label>这段摘录的用途<select value={annotation?.role||"open"} onChange={e=>onAnnotation({role:e.target.value})}>{[["open","尚未决定"],["question","疑问"],["support","私人支持线索"],["contrast","对照"],["counterexample","反例线索"],["method","方法"]].map(([v,t])=><option key={v} value={v}>{t}</option>)}</select></label><p className="margin-note">私人用途不改变公开的支持关系。</p></>}</>}</blockquote>;
}

export function LabContinuation({desk,links}:{desk:DeskStore;links:any[]}) {
  return <section className="lab-continuation"><h2>上次实验，留下了什么？</h2>{links.map((item:any)=><LabNote key={item.observation_ref.revision} adapter={desk.adapter} item={item}/>)}<Link to="/?space=lab">回到实验与原始依据 →</Link></section>;
}
function LabNote({adapter,item}:{adapter:WorkspaceAdapter;item:any}) {
  const {record,error}=useRecord(adapter,item.observation_ref),[design,setDesign]=useState<Entity|null>(null),[designError,setDesignError]=useState("");
  useEffect(()=>{let active=true;if(item.design_ref)void adapter.load(item.design_ref.kind,item.design_ref.id,item.design_ref.revision).then(v=>{if(active)setDesign(v);}).catch(error=>{if(active)setDesignError(String(error));});return()=>{active=false;};},[item.design_ref?.revision]);
  return <section className="excerpt-card">{error?<p role="alert">{error}</p>:<><h3>{record?.statement||"取回观察…"}</h3><p className="margin-note">范围：{record?.scope}</p>{designError&&<p role="alert">{designError}</p>}{design&&<><h4>{design.title}</h4><p>{design.question}</p><details><summary>竞争解释与诊断计划 · 尚未执行</summary><pre>{JSON.stringify(design,null,2)}</pre></details></>}{item.analysis_ref&&<AnalysisNote adapter={adapter} pointer={item.analysis_ref}/>}<details><summary>{item.basis_ref?"固定历史依据 · 没有新 Run":"当时的固定依据"}</summary><pre>{JSON.stringify({basis:item.basis_ref,run:item.run_ref,observation:item.observation_ref,design:item.design_ref,analysis:item.analysis_ref},null,2)}</pre></details></>}</section>;
}

function AnalysisNote({adapter,pointer}:{adapter:WorkspaceAdapter;pointer:EntityRef}) {
  const {record,error}=useRecord(adapter,pointer);
  return <section className="analysis-continuation"><h4>这次分析</h4>{error?<p role="alert">{error}</p>:record?<><p>{record.result}</p><p className="margin-note">方法：{record.method} · 范围：{record.scope}</p></>:<p>取回固定分析…</p>}</section>;
}

export function Compare({desk,items}:{desk:DeskStore;items:any[]}) {
  const [tab,setTab]=useState("A");
  const payload=desk.active()!.record.payload, compare=payload.compare||[];
  const selected=compare.map((key:string)=>items.find(item=>item.key===key)).filter(Boolean).slice(0,2);
  const choose=(index:number,key:string)=>{const next=[...compare];next[index]=key;desk.edit({compare:next.filter(Boolean)});desk.endGroup();};
  return <section className="comparison" aria-label="并排对读"><div className="comparison-heading"><h2>把两处放在一起读</h2><p className="margin-note">各自的位置和这次比较的想法，随案头保留。</p></div>
    <div className="comparison-selectors">{["A","B"].map((name,i)=><label key={name}>{name}<select value={compare[i]||""} onChange={event=>choose(i,event.target.value)}><option value="">选一份材料</option>{items.map(item=><option key={item.key} value={item.key} disabled={compare[1-i]===item.key}>{item.title||item.public_id||item.legacy?.id||item.key}</option>)}</select></label>)}</div>
    <div className="compare-tabs" role="tablist" aria-label="手机对读">{["A","B"].map(name=><button key={name} role="tab" aria-selected={tab===name} onClick={()=>setTab(name)}>{name} · {selected[name==="A"?0:1]?.title||"未选择"}</button>)}</div>
    <div className="compare-panes">{selected.map((item:any,index:number)=><ComparePane key={item.key} desk={desk} item={item} name={index===0?"A":"B"} active={tab===(index===0?"A":"B")}/>)}</div>
    <label className="compare-note">两处之间，我看见了什么？<textarea aria-label="两处之间，我看见了什么？" value={payload.comparison_note||""} onChange={event=>desk.edit({comparison_note:event.target.value})} onBlur={()=>desk.endGroup()}/></label>
  </section>;
}
function ComparePane({desk,item,name,active}:{desk:DeskStore;item:any;name:string;active:boolean}) {
  const adapter=desk.adapter, {record,error}=useRecord(adapter,item.representation_ref),[text,setText]=useState(""),[failure,setFailure]=useState("");
  const pane=useRef<HTMLDivElement>(null), restoring=useRef(true),sessionId=desk.state.active;
  useEffect(()=>{if(!record)return;let active=true;adapter.blob(record.artifact_digest).then(bytes=>{
    let value=new TextDecoder().decode(bytes);try{const old=JSON.parse(value);value=old.bodyMarkdown||old.text||old.basis||JSON.stringify(old,null,2);}catch{}
    if(active)setText(value);
  }).catch(error=>{if(active)setFailure(String(error));});return()=>{active=false;};},[record?.revision]);
  useEffect(()=>{if(!text||!pane.current)return;pane.current.scrollTop=item.compare_scroll||0;restoring.current=false;},[text]);
  return <section className={`compare-pane ${active?"is-active":""}`} aria-label={`${name} 对读正文`}><h3>{name} · {item.title||item.legacy?.id}</h3><p className="margin-note">保存时的依据 · 原文文字视图</p>
    <div className="pinned-text" ref={pane} tabIndex={0} onScroll={()=>{
      if(restoring.current||!pane.current)return;
      const position=Math.round(pane.current.scrollTop),payload=sessionId?desk.state.edits[sessionId]?.record.payload:null;
      if(payload)desk.edit({items:payload.items.map((row:any)=>row.key===item.key?{...row,compare_scroll:position}:row)},sessionId);
    }}>{error||failure?<p role="alert">{error||failure}</p>:<pre>{text||"正在取回保存时的内容…"}</pre>}</div></section>;
}

export function BasisComparison({desk,item,bootstrap}:{desk:DeskStore;item:any;bootstrap:Bootstrap}) {
  const meta=bootstrap.catalogue.find(r=>r.kind===(item.public_kind||item.legacy?.kind)&&r.id===(item.public_id||item.legacy?.id));
  const [preview,setPreview]=useState<any>(null),[saved,setSaved]=useState(""),[error,setError]=useState("");
  const current=meta?.ref?.revision===item.target_ref.revision;
  const inspect=async()=>{try{
    const artifact=await desk.adapter.load(item.representation_ref.kind,item.representation_ref.id,item.representation_ref.revision);
    const raw=new TextDecoder().decode(await desk.adapter.blob(artifact.artifact_digest));let text=raw;try{const value=JSON.parse(raw);text=value.bodyMarkdown||value.basis||JSON.stringify(value,null,2);}catch{}setSaved(text);
    if(meta){const content=bootstrap.portableContent?.[meta.kind+"/"+meta.id]||await fetch(bootstrap.base+meta.shard).then(r=>{if(!r.ok)throw new Error("当前公开正文暂不可用。");return r.json();});setPreview(content);}else setPreview({unresolved:true});
  }catch(e){setError(String(e));}};
  return <details className="basis-comparison"><summary>{current?"当前公开依据已固定":meta?"比较旧依据与当前公开版本":"查看保存的原始依据"}</summary><p className="margin-note">当前案头继续使用保存时的版本。摘录另有独立依据，更新这里不会改写旧摘录。</p><button onClick={()=>void inspect()}>打开依据对照</button>{error&&<p role="alert">{error}</p>}{preview&&<><div className="basis-columns"><section><h4>案头当时的依据</h4><pre>{saved}</pre></section>{!preview.unresolved&&<section><h4>当前公开版本</h4><pre>{preview.bodyMarkdown||JSON.stringify(preview,null,2)}</pre></section>}</div>{!current&&meta&&<button onClick={async()=>{try{await desk.replaceBasis(item.key,meta,preview);setPreview(null);}catch(e){setError(String(e));}}}>以当前公开版本继续，保留旧摘录</button>}<button onClick={()=>setPreview(null)}>继续使用案头原版本</button></>}{!!item.previous_basis?.length&&<p className="margin-note">保留 {item.previous_basis.length} 次之前的依据。</p>}</details>;
}
