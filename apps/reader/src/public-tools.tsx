import React,{useEffect,useState} from "react";
import {download} from "./adapters";
import type {Bootstrap,CatalogueItem,PublicKind} from "./types";
import StudyPackets from "../../../assets/study-packets.js";
import Practice from "../../../assets/practice.js";

export async function loadPacket(bootstrap:Bootstrap,meta:CatalogueItem){
  const saved=bootstrap.portablePackets?.[meta.kind+"/"+meta.id];
  const packet=saved||await fetch(bootstrap.base+meta.packet).then(r=>{if(!r.ok)throw new Error("公开研究包暂时无法取得。");return r.json();});
  if(packet.schema!=="ams-study-packet/2"||packet.kind!==meta.kind||packet.id!==meta.id)throw new Error("研究包身份不符。");
  return packet;
}
export function PacketActions({bootstrap,meta}:{bootstrap:Bootstrap;meta:CatalogueItem}){
  const [error,setError]=useState("");
  const save=async(format:string)=>{try{const packet=await loadPacket(bootstrap,meta);download(meta.id+(format==="json"?".json":".md"),format==="json"?packet:StudyPackets.markdown(packet),format==="json"?"application/json":"text/markdown");}catch(e){setError(String(e));}};
  if(!bootstrap.portable)return <><a href={bootstrap.base+meta.packet} download>研究包 JSON ↓</a><a href={bootstrap.base+meta.packet?.replace(/\.json$/,".md")} download>研究包 Markdown ↓</a></>;
  return <><button onClick={()=>void save("json")}>研究包 JSON ↓</button><button onClick={()=>void save("markdown")}>研究包 Markdown ↓</button>{error&&<p role="alert">{error}</p>}</>;
}
export function PublicSelection({bootstrap,items}:{bootstrap:Bootstrap;items:any[]}){
  const [error,setError]=useState("");
  const save=async(format:string)=>{try{
    const selected:CatalogueItem[]=[];
    for(const item of items){const kind=item.public_kind||item.legacy?.kind,id=item.public_id||item.legacy?.id;const meta=bootstrap.catalogue.find(r=>r.kind===kind&&r.id===id);if(meta&&!selected.some(r=>r.kind===meta.kind&&r.id===meta.id))selected.push(meta);}
    const objects=await Promise.all(selected.map(meta=>loadPacket(bootstrap,meta)));
    const bundle={schema:"ams-study-collection/2",title:"AMS 公开选材包",objects,policy:"Only selected current public objects. No private notes, excerpts, titles, prior snapshots or inferred support."};
    download("ams-public-selection."+(format==="json"?"json":"md"),format==="json"?bundle:StudyPackets.collectionMarkdown(bundle),format==="json"?"application/json":"text/markdown");
  }catch(e){setError(String(e));}};
  return <details className="public-selection" data-interactive=""><summary>只带走当前公开选材</summary><p className="margin-note">按已知公开身份重建今天的研究包；私人问题、摘录、旁注和旧快照留在案头。</p><button onClick={()=>void save("json")}>公开选材 JSON ↓</button><button onClick={()=>void save("markdown")}>公开选材 Markdown ↓</button>{error&&<p role="alert">{error}</p>}</details>;
}
export function PracticeView({bootstrap,query,link,update}:{bootstrap:Bootstrap;query:string;link:(kind:PublicKind,id:string,text?:string)=>React.ReactNode;update:(value:string)=>void}){
  const [value,setValue]=useState(query),[data,setData]=useState<any>(null),[error,setError]=useState("");
  useEffect(()=>{let active=true;Promise.all(bootstrap.catalogue.filter(r=>r.kind==="finding").map(async meta=>bootstrap.portableContent?.[meta.kind+"/"+meta.id]||await fetch(bootstrap.base+meta.shard).then(r=>{if(!r.ok)throw new Error("实践条目暂不可用。");return r.json();}))).then(findings=>{if(active)setData({findings});}).catch(e=>{if(active)setError(String(e));});return()=>{active=false;};},[bootstrap]);
  useEffect(()=>setValue(query),[query]);
  const hits=data?Practice.query(data,query):[];
  return <section className="practice-view"><p className="eyebrow">PRACTICE / 带回设计</p><h2>眼前的选择，可以向哪些经验借一步？</h2><p className="margin-note">公开词项匹配，最多三条独立判断。查询进入公开 URL 与浏览器历史；私人项目内容请留在案头。</p><form onSubmit={e=>{e.preventDefault();update(value);}}><label>公开的问题或机制<input value={value} onChange={e=>setValue(e.target.value)} placeholder="例如：scope、检索预算、纠错"/></label><button>找一个切口</button></form>{error&&<p role="alert">{error}</p>}{hits.map((hit:any)=><section key={hit.finding.id}><h3>{link("finding",hit.finding.id,hit.finding.title)}</h3><p>{hit.finding.when}</p><p>{hit.finding.action}</p><p className="margin-note">{hit.finding.avoid} {hit.finding.limit}</p><small>匹配：{hit.matches.join("、")||"按目录浏览"}</small></section>)}{data&&!hits.length&&<p>没有符合这些词项的判断；没有自动生成建议。</p>}{data&&<div data-interactive=""><button onClick={()=>download("ams-practice-brief.json",Practice.brief(data,query))}>Brief JSON ↓</button><button onClick={()=>download("ams-practice-brief.md",Practice.markdown(Practice.brief(data,query)),"text/markdown")}>Brief Markdown ↓</button></div>}</section>;
}
