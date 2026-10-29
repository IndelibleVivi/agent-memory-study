import React,{useEffect,useMemo,useRef,useState} from "react";
import {useHref} from "react-router";
import Constellation from "../../../assets/constellation.js";
import Sculpture from "../../../assets/continuity-sculpture.js";
import type {Bootstrap} from "./types";
import "./maps.css";

// This is a bounded display of the compiler's graph, never a new relationship
// extractor. Large catalogues keep the full index and display a selected ego graph.
export function ResearchView({bootstrap,sculpture=false}:{bootstrap:Bootstrap;sculpture?:boolean}) {
  const root=useRef<HTMLDivElement>(null),base=useHref("/"),[focus,setFocus]=useState("study/ams-thesis");
  const [localOnly,setLocalOnly]=useState(()=>typeof window!=="undefined"&&matchMedia("(max-width:760px)").matches);
  const [filters,setFilters]=useState(false);
  const large=bootstrap.graph.nodes.length>160;
  const model=useMemo(()=>{
    const original=bootstrap.graph,chosen=original.nodes.findIndex((n:any)=>n.key===focus);
    const indices=new Set<number>((large||localOnly)&&!sculpture?[Math.max(0,chosen)]:original.nodes.map((_:any,i:number)=>i));
    if((large||localOnly)&&!sculpture)for(const [a,b] of original.edges)if(a===chosen||b===chosen){indices.add(a);indices.add(b);}
    const selected=[...indices].slice(0,160),lookup=new Map(selected.map((v,i)=>[v,i]));
    return {nodes:selected.map(i=>({...original.nodes[i],item:{shortTitle:original.nodes[i].title}})),
      edges:original.edges.filter(([a,b]:number[])=>lookup.has(a)&&lookup.has(b)).map(([a,b]:number[])=>[lookup.get(a),lookup.get(b)])};
  },[bootstrap.graph,focus,large,localOnly,sculpture]);
  useEffect(()=>{
    if(!root.current||!model.nodes.length)return;
    const data={room:bootstrap.room},routeHref=(kind:string,id:string)=>bootstrap.portable?`#/?${kind}=${encodeURIComponent(id)}`:`${base}${kind}/${encodeURIComponent(id)}/`;
    const mounted=sculpture?Sculpture.mount(data,{root:root.current as any,model,routeHref}):Constellation.mount({root:root.current,data,model,routeHref,selectedKey:focus,layoutDomains:localOnly?[]:undefined,hideGroups:localOnly,onSelect:localOnly?setFocus:undefined});
    return()=>mounted?.destroy();
  },[model,sculpture,bootstrap.room,base,localOnly]);
  return <div className="research-view" ref={root}>
    {large&&<label className="ego-selector">选择局部引用范围<select value={focus} onChange={e=>setFocus(e.target.value)}>{bootstrap.catalogue.map(n=><option key={n.kind+"/"+n.id} value={n.kind+"/"+n.id}>{n.title}</option>)}</select><small>显示所选对象与直接引用近邻，最多 160 个；完整资料目录仍可搜索。</small></label>}
    {sculpture&&<p className="margin-note">每道环带是一份研究。随引用展开，回到具体的文字。</p>}
    {sculpture?<div className="room-hero">
      <div id="continuity-sculpture" className="sculpture-stage" tabIndex={0} role="group" aria-label="三维研究体：拖动旋转，点击选择；方向键旋转，Enter选择下一份">
        <svg className="sculpture-fallback" viewBox="0 0 1000 500" aria-hidden="true"/><canvas aria-hidden="true"/>
      </div>
      <div className="sculpture-toolbar"><div>{[["field","环带"],["spread","展阅"],["links","引用"]].map(([v,t])=><button key={v} data-sculpture-view={v}>{t}</button>)}</div><div><button className="sculpture-toggle">静止 Ⅱ</button><button id="sculpture-reset">复位</button></div></div>
      <div className="sculpture-inspector"><p className="row-meta"><span id="sculpture-kind"/><span id="sculpture-ordinal"/></p><h2 id="sculpture-title"/><p id="sculpture-summary"/><div><button data-sculpture-step="-1" aria-label="上一份研究">←</button><button data-sculpture-step="1" aria-label="下一份研究">→</button><a id="sculpture-open">阅读全文 ↗</a></div><details className="sculpture-source"><summary>公开对象</summary><select id="sculpture-record" aria-label="选择公开对象"/><pre id="sculpture-code"/></details></div>
    </div>:<section id="constellation" className="constellation" aria-label="研究星图" data-local={localOnly}>
      <header className="map-heading"><div><p className="eyebrow">THE RESEARCH CONSTELLATION</p><h2>沿着引用，继续读。</h2></div><p>一份研究，如何走向另一份。<br/>选一个星点，打开它的来处与下一问。</p></header>
      <div className="map-workspace"><div className="map-observatory">
        <div className="map-topline"><div className="map-scope"><button aria-pressed={localOnly} onClick={()=>setLocalOnly(true)}>当前引用</button><button aria-pressed={!localOnly} onClick={()=>setLocalOnly(false)}>完整星图</button></div><button className="map-filter-toggle" onClick={()=>setFilters(!filters)} aria-expanded={filters} aria-controls="map-filter-panel"><svg viewBox="0 0 24 24" width="17" height="17" aria-hidden="true"><path d="M4 7h16M4 17h16M9 4v6M16 14v6" fill="none" stroke="currentColor" strokeWidth="1.3"/></svg>筛选</button></div>
        <div className="map-filters" id="map-filter-panel" hidden={!filters}><div className="map-kind-options">{[["","全部"],["study","札记"],["material","来源"],["question","问题"],["finding","判断"]].map(([v,t])=><button key={v} data-map-kind={v} aria-pressed={!v}>{t}</button>)}</div><label>领域<select id="map-domain"><option value="">全部领域</option></select></label><label>查找<input id="map-query" type="search" placeholder="标题或关键词"/></label></div>
        <div className="map-drawing-caption"><p id="constellation-stats"/><div><button data-map-view="map" aria-pressed="true">图</button><span>/</span><button data-map-view="list" aria-pressed="false">列表</button></div></div>
        <div className="constellation-canvas"><div id="constellation-plot"/><div id="constellation-list" hidden/><p id="map-empty" hidden>这个范围内没有匹配对象。</p></div>
        <div className="map-controls" id="map-camera-controls"><div className="map-zoom"><button id="map-zoom-out" aria-label="缩小星图">−</button><span id="map-zoom-value">100%</span><button id="map-zoom-in" aria-label="放大星图">＋</button></div><div><button id="map-focus" hidden aria-pressed="false">只看相关</button><button id="map-motion" aria-pressed="false">暂停</button><button id="map-reset">复位</button><button id="map-fullscreen" hidden>全屏</button></div></div>
      </div><aside id="constellation-reading" className="constellation-reading"/></div>
      <p className="map-footnote"><span aria-hidden="true">↳</span> 连线只记录显式引用；空间位置不代表相似度。</p><p id="map-announcement" className="visually-hidden" role="status"/>
    </section>}

  </div>;
}
