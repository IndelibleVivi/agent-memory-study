import React,{useEffect,useMemo,useRef,useState,useSyncExternalStore} from "react";
import {Link,useLocation,useNavigate} from "react-router";
import type {Bootstrap,CatalogueItem,Content,PublicKind,Space} from "./types";
import {base64,download,EphemeralAdapter,LocalAdapter} from "./adapters";
import {DeskStore,privateWorkspaceMarkdown,type DeskState} from "./desk-store";
import {ContentBody,contents,labels} from "./content";
import {Exercise} from "./exercises";
import {Compare,ExcerptCard,LabContinuation,BasisComparison} from "./desk-evidence";
import {CaptureCard,IntakeShelf} from "./intake";
import {LabView} from "./lab";
import {ReviewView} from "./review";
import {ResearchView} from "./maps";
import ReadingSearch from "../../../assets/reading-search.js";
import SEO from "../../../assets/seo.js";
import StudyDesk from "../../../assets/study-desk.js";
import {PacketActions,PublicSelection,PracticeView} from "./public-tools";

const spaces:{id:Space;zh:string;en:string}[]=[{id:"continue",zh:"继续",en:"Continue"},{id:"explore",zh:"探索",en:"Explore"},{id:"library",zh:"资料",en:"Library"},{id:"lab",zh:"实验",en:"Lab"}];
const kinds:PublicKind[]=["material","study","question","finding"];
const key=(kind:PublicKind,id:string)=>kind+"/"+id;

export function App({bootstrap,documentOnly=false}:{bootstrap:Bootstrap;documentOnly?:boolean}) {
  const actualLocation=useLocation(),navigate=useNavigate(),[hydrated,setHydrated]=useState(false);
  // A static home document cannot know a visitor's query. Hydrate its exact
  // route first, then apply private/local and legacy query navigation.
  const initialURL=new URL(bootstrap.location,"https://ams.invalid");
  const location=hydrated?actualLocation:{...actualLocation,pathname:initialURL.pathname,search:initialURL.search,hash:initialURL.hash};
  const query=new URLSearchParams(location.search);
  const [desk,setDesk]=useState(()=>new DeskStore(new EphemeralAdapter(Object.fromEntries(Object.entries({material:"materials",study:"studies",question:"questions",finding:"findings"}).map(([kind,field])=>[field,bootstrap.catalogue.filter(row=>row.kind===kind)])),async(ref)=>{
    if(bootstrap.portableRecords?.[ref.revision])return bootstrap.portableRecords[ref.revision];
    const shard=bootstrap.recordIndex[ref.revision];if(!shard)throw new Error("缺少这个公开版本；请从保存的研究文件恢复。");
    const response=await fetch(bootstrap.base+shard);if(!response.ok)throw new Error("公开依据暂时无法取得。");return response.json();
  })));
  const state=useSyncExternalStore(desk.subscribe,desk.snapshot,desk.snapshot);
  const [capture,setCapture]=useState(false),[notification,notify]=useState("");
  const [cache,setCache]=useState<Record<string,Content>>(()=>({...bootstrap.portableContent,...(bootstrap.initial?{[key(bootstrap.initial.kind,bootstrap.initial.item.id)]:bootstrap.initial.item}:{})}));
  const [loadError,setLoadError]=useState(""),[retry,setRetry]=useState(0);
  const path=location.pathname.split("/").filter(Boolean),kind=kinds.find(kind=>query.has(kind))||(kinds.includes(path[0] as PublicKind)?path[0] as PublicKind:null);
  const id=kind?(query.get(kind)||decodeURIComponent(path[1]||"")):"";
  const selected=kind?bootstrap.catalogue.find(row=>row.kind===kind&&row.id===id):null;
  const current=selected?cache[key(selected.kind,selected.id)]:null;
  const space=(spaces.some(s=>s.id===query.get("space"))?query.get("space"):location.hash==="#workbench"?"continue":"explore") as Space;
  const href=(kind:PublicKind,id:string)=>bootstrap.portable?`?${kind}=${encodeURIComponent(id)}`:`/${kind}/${encodeURIComponent(id)}/`;
  const link=(kind:PublicKind,id:string,text?:string,anchor="",exercise:Record<string,string|number>={})=><Link to={href(kind,id)+(Object.keys(exercise).length?(bootstrap.portable?"&":"?")+new URLSearchParams(Object.entries(exercise).map(([k,v])=>[k,String(v)])).toString():"")+anchor}>{text||bootstrap.catalogue.find(row=>row.kind===kind&&row.id===id)?.title||id}</Link>;
  const action=async(work:()=>Promise<unknown>,success?:string)=>{try{await work();if(success)notify(success);}catch(error){notify(String(error));}};
  useEffect(()=>{
    setHydrated(true);
    const element=document.getElementById("ams-local-bootstrap");
    if(element){const config=JSON.parse(element.textContent||"{}");const store=new DeskStore(new LocalAdapter(config.token));setDesk(store);void store.refresh();
      if(actualLocation.pathname==="/"&&!actualLocation.search)navigate("/?space=continue",{replace:true});}
  },[]);
  useEffect(()=>{
    if(!selected||current)return;
    let active=true;setLoadError("");
    fetch(bootstrap.base+selected.shard).then(response=>{if(!response.ok)throw new Error("正文暂时无法取得；请重试。");return response.json();}).then(item=>{if(active)setCache(old=>({...old,[key(selected.kind,selected.id)]:item}));}).catch(error=>{if(active)setLoadError(String(error));});
    return()=>{active=false;};
  },[selected?.id,selected?.kind,current,retry]);
  useEffect(()=>{
    if(!hydrated)return;
    const metadata=SEO.metadata({room:bootstrap.room,...Object.fromEntries(Object.entries({material:"materials",study:"studies",question:"questions",finding:"findings"}).map(([k,field])=>[field,k===kind&&current?[current]:[]]))},kind?{[kind]:id}:{});
    document.title=metadata.title;
    document.querySelector('meta[name="description"]')?.setAttribute("content",metadata.description);
    document.querySelector('link[rel="canonical"]')?.setAttribute("href",metadata.canonical);
    document.querySelector('meta[property="og:title"]')?.setAttribute("content",metadata.title);
    document.querySelector('meta[property="og:description"]')?.setAttribute("content",metadata.description);
    const structured=document.querySelector('script[type="application/ld+json"]');if(structured)structured.textContent=JSON.stringify(metadata.structured);
    if(location.hash){requestAnimationFrame(()=>document.getElementById(decodeURIComponent(location.hash.slice(1)))?.scrollIntoView());}
    else window.scrollTo({top:0,behavior:"instant"});
  },[location.pathname,location.hash,kind,id,current,hydrated]);
  useEffect(()=>{
    const warn=(event:BeforeUnloadEvent)=>{const unsaved=desk.hasUnsaved();if(unsaved){event.preventDefault();event.returnValue="";}};
    window.addEventListener("beforeunload",warn);return()=>window.removeEventListener("beforeunload",warn);
  },[desk]);
  if(documentOnly&&selected&&current)return <Reader item={current} meta={selected} link={link} bootstrap={bootstrap} desk={desk} query={query} change={()=>{}} notify={()=>{}}/>;
  return <div className="ams-app" data-mode={desk.adapter.capabilities.mode} data-ready={hydrated}>
    <a href="#main" className="skip-link">跳到正文</a>
    <header className="app-header"><Link to="/" className="brand"><span className="brand-mark" aria-hidden="true">a<span>m</span>s</span><span>Agent Memory<br/>Study</span></Link>
      <nav aria-label="四个研究空间">{spaces.map(item=><Link key={item.id} to={`/?space=${item.id}`} aria-current={!kind&&space===item.id?"page":undefined}><span>{item.zh}</span><small>{item.en}</small></Link>)}</nav>
      <button className="capture-button" onClick={()=>setCapture(true)} data-interactive="">＋ 带进来</button></header>
    <div className="mode-line"><span>{desk.adapter.capabilities.durable?"本地研究环境":"公开书房"}</span><span>{desk.adapter.capabilities.durable?"案头保存于本机":"私人接续留在页面；刷新前请下载"}</span></div>
    <main id="main" tabIndex={-1}>
      {kind ? selected?(current?<Reader item={current} meta={selected} link={link} bootstrap={bootstrap} desk={desk} query={query} change={(fields:Record<string,string|number>)=>{const params=new URLSearchParams(location.search);Object.entries(fields).forEach(([name,value])=>params.set(name,String(value)));navigate({pathname:location.pathname,search:params.toString(),hash:"#study-lab"},{preventScrollReset:true});}} notify={notify}/>:<div className="loading-state" role="status">{loadError||"正在打开正文…"}{loadError&&<button onClick={()=>setRetry(n=>n+1)}>重试</button>}</div>):<div className="empty-state"><h1>没有找到这篇内容</h1><p>旧入口可能已更名。资料目录保留可辨认的公开身份。</p><Link to="/?space=library">回到资料 →</Link></div>:
        space==="continue"&&query.get("tool")==="review"?<ReviewView desk={desk} catalogue={bootstrap.catalogue} link={link}/>:space==="continue"?<DeskView desk={desk} catalogue={bootstrap.catalogue} bootstrap={bootstrap} link={link} action={action}/>:
        space==="lab"?<LabView catalogue={bootstrap.catalogue} link={link} desk={desk}/>:
        <><IntakeShelf desk={desk} catalogue={bootstrap.catalogue} visible={space==="library"}/><Discovery bootstrap={bootstrap} library={space==="library"} query={query} link={link} navigate={navigate}/></>}
    </main>
    <footer><span>Agent Memory Study</span><p>保存、理解、使用，以及再次改变。</p><Link to={href("study","ams-thesis")}>研究从哪里开始 ↗</Link><a href={bootstrap.base+"docs/authoring.md"}>作者路径 ↗</a></footer>
    <div role="status" aria-live="polite" className={notification?"notice":"notice is-empty"}>{notification}{notification&&<button onClick={()=>notify("")} aria-label="关闭提示">×</button>}</div>
    {capture&&<CaptureDialog desk={desk} close={()=>setCapture(false)} notify={notify}/>}
  </div>;
}

function Discovery({bootstrap,library,query,link,navigate}:{bootstrap:Bootstrap;library:boolean;query:URLSearchParams;link:any;navigate:any}) {
  const [input,setInput]=useState(query.get("q")||""),[searchIndex,setSearchIndex]=useState<any[]|null>(bootstrap.searchIndex||null),[searchError,setSearchError]=useState("");
  const discoveryLocation=useLocation();
  const [view,setView]=useState(query.has("path")||query.has("thread")?"atlas":"articles");
  useEffect(()=>{if(query.has("path")||query.has("thread"))setView("atlas");else if(discoveryLocation.hash==="#constellation")setView("map");},[query.get("path"),query.get("thread"),discoveryLocation.hash]);
  const q=query.get("q")||"", domain=query.get("domain")||"",direction=query.get("direction")||"",type=query.get("type")||"";
  const update=(fields:Record<string,string>)=>{const params=new URLSearchParams(query);Object.entries(fields).forEach(([name,value])=>value?params.set(name,value):params.delete(name));navigate("/?"+params.toString());};
  useEffect(()=>{setInput(q);if((!q&&!query.get("topic")&&!query.get("surface")&&!query.get("thread")&&!query.get("depth"))||searchIndex)return;let active=true;fetch(bootstrap.base+"reader-data/search.json").then(r=>r.json()).then(v=>{if(active)setSearchIndex(v);}).catch(error=>setSearchError(String(error)));return()=>{active=false;};},[q,query.toString()]);
  let rows=bootstrap.catalogue.filter(row=>(!library||row.kind==="material"||type)&&(!type||row.kind===type)&&(!domain||row.domains.includes(domain))&&(!direction||row.directions.includes(direction)));
  const savedPath=bootstrap.atlas.readingPaths?.find((path:any)=>path.id===query.get("path"));if(savedPath)rows=rows.filter(row=>row.kind==="material"&&savedPath.materialIds.includes(row.id));
  const hits=searchIndex?ReadingSearch.search(searchIndex,q,{topic:query.get("topic")||"",surface:query.get("surface")||query.get("thread")||"",depth:query.get("depth")||""}):null;
  if(hits){const rank=new Map(hits.map((hit:any,i:number)=>[key(hit.kind,hit.item.id),i]));rows=rows.filter(row=>rank.has(key(row.kind,row.id))).sort((a,b)=>Number(rank.get(key(a.kind,a.id)))-Number(rank.get(key(b.kind,b.id))));}
  const [count,setCount]=useState(30);
  const heading=library?"把材料，放回它的来处。":"信息留下之后，\n理解怎样继续？";
  return <div className="discovery"><section className={library?"space-heading":"explore-heading"}><div><p className="eyebrow">{library?"LIBRARY / 资料":"A LIVING RESEARCH PROGRAMME"}</p><h1>{heading}</h1><p className="space-intro">{library?"作品、版本、文件与实际读到的部分，各有自己的位置。":"从 agent memory 出发，沿着信息、经验与智能之间的关系读、比较、推导，再让新的依据改变认识。"}</p></div>
      {!library&&<aside className="programme-note"><span>从一个尚未明白的地方开始</span><p>{bootstrap.room.invitation||bootstrap.room.intro}</p>{link("study","ams-thesis","走进研究 →")}</aside>}</section>
    {!library&&<nav className="domain-strip" aria-label="研究领域"><button aria-pressed={!domain} onClick={()=>update({domain:""})}>全部</button>{bootstrap.room.domains?.map((d:any)=><button key={d.id} aria-pressed={domain===d.id} onClick={()=>update({domain:d.id})}>{d.title||d.label}</button>)}</nav>}
    {!library&&<><nav className="view-lenses" aria-label="探索方式" data-interactive="">{[["articles","文章"],["domains","领域与方向"],["map","星图"],["programme","研究体"],["atlas","问题路径"]].map(([v,t])=><button key={v} aria-pressed={view===v} onClick={()=>setView(v)}>{t}</button>)}</nav>
      {view==="map"||view==="programme"?<ResearchView bootstrap={bootstrap} sculpture={view==="programme"}/>:view==="domains"?<div className="programme-paths">{bootstrap.room.directions?.map((d:any)=><section key={d.id}><p className="eyebrow">{d.english}</p><h2><button onClick={()=>update({direction:d.id})}>{d.title}</button></h2><p>{d.intro}</p><p>{d.question}</p></section>)}</div>:view==="atlas"?<div className="programme-paths">{bootstrap.atlas.readingPaths?.map((d:any)=><section key={d.id}><p className="eyebrow">保存的阅读路径</p><h2>{d.title}</h2><p>{d.description}</p><button onClick={()=>update({path:d.id,surface:"",thread:""})}>沿这条路径读 →</button></section>)}{bootstrap.atlas.failureSurfaces?.map((d:any)=><section key={d.id}><h2>{d.title||d.label}</h2><p>{d.question||d.intro||d.description}</p><button onClick={()=>update({surface:d.id})}>沿这个问题读 →</button></section>)}</div>:!q&&!domain&&!direction&&<div className="programme-paths">{bootstrap.room.starts?.map((start:any)=><section key={start.studyId}><p className="eyebrow">{start.kicker}</p><h2>{link("study",start.studyId,start.prompt)}</h2><pre>{start.notation}</pre></section>)}</div>}</>}
    {(library||query.has("practice"))&&<PracticeView bootstrap={bootstrap} query={query.get("practice")||""} link={link} update={value=>update({practice:value,space:"library"})}/>}
    {savedPath&&<p className="margin-note">当前保存路径：{savedPath.title} · {savedPath.description}</p>}
    <section className="catalogue"><div className="catalogue-tools"><div><p className="eyebrow">{q?"搜索结果":"沿这些线索继续"}</p><h2>{domain?(bootstrap.room.domains?.find((d:any)=>d.id===domain)?.title||domain):library?"来源与札记":"正在生长的研究"}</h2></div>
      <form role="search" onSubmit={event=>{event.preventDefault();setCount(30);update({q:input});}}><label className="visually-hidden" htmlFor="research-search">搜索正文、作者与问题</label><input id="research-search" value={input} onChange={event=>setInput(event.target.value)} placeholder="搜索正文、作者与问题"/><button>查找</button></form></div>
      <div className="filter-row"><label>内容<select value={type} onChange={event=>update({type:event.target.value})}><option value="">{library?"来源材料":"全部内容"}</option>{kinds.map(kind=><option key={kind} value={kind}>{labels[kind]}</option>)}</select></label><span role="status">{q&&!searchIndex?(searchError||"正在读取公开搜索索引…"):`${rows.length} 个公开对象`}</span></div>
      <ol className="catalogue-rows">{rows.slice(0,count).map((row,index)=><li key={key(row.kind,row.id)}><span className="row-number">{String(index+1).padStart(2,"0")}</span><div><div className="row-meta"><span>{labels[row.kind]}</span><span>{row.date}</span></div><h3>{link(row.kind,row.id)}</h3><p>{row.intro}</p><small>{row.byline}</small></div><span className="row-arrow" aria-hidden="true">↗</span></li>)}</ol>
      {rows.length>count&&<><button onClick={()=>setCount(count+30)}>再展开 30 项</button><noscript><ol className="catalogue-rows" start={count+1}>{rows.slice(count).map(row=><li key={key(row.kind,row.id)}><div><h3>{link(row.kind,row.id)}</h3><p>{row.intro}</p></div></li>)}</ol></noscript></>}{!rows.length&&<p className="empty-state">这里还没有匹配的公开对象。可以把这个问题先带进案头。</p>}
    </section>
    {!library&&<section className="recent-changes"><h2>最近的改变</h2>{bootstrap.room.changes?.slice(0,4).map((change:any)=><section key={change.date+change.studyId}><p className="eyebrow">{change.date}</p><h3>{link("study",change.studyId,change.title)}</h3><p>{change.text}</p></section>)}</section>}
  </div>;
}

function Reader({item,meta,link,bootstrap,desk,query,change,notify}:any) {
  const readerLocation=useLocation();
  const article=useRef<HTMLElement>(null),[selection,setSelection]=useState("");
  const [reference,setReference]=useState<{meta:CatalogueItem;trigger:HTMLElement}|null>(null);
  const state=useSyncExternalStore(desk.subscribe,desk.snapshot,desk.snapshot),active=desk.active();
  const exerciseState=()=>item.exercise?StudyDesk.exerciseState(item.exercise,Object.fromEntries(query)):Object.fromEntries(["scenario","phase"].filter(k=>query.has(k)).map(k=>[k,query.get(k)]));
  const rememberExercise=(fields:any=exerciseState())=>{const payload=desk.active()?.record.payload;if(payload?.items.some((r:any)=>r.key===meta.kind+":"+meta.id))desk.edit({items:payload.items.map((r:any)=>r.key===meta.kind+":"+meta.id?{...r,exercise:fields}:r)});};
  const changeExercise=(fields:any)=>{const next={...Object.fromEntries(query),...fields};rememberExercise(item.exercise?StudyDesk.exerciseState(item.exercise,next):Object.fromEntries(["scenario","phase"].filter(k=>next[k]).map(k=>[k,next[k]])));change(fields);};
  const add=async()=>{try{await desk.add(meta,item,readerLocation.hash);rememberExercise();notify("已加入当前案头。");}catch(error){notify(String(error));}};
  useEffect(()=>{
    const capture=()=>{if(!article.current)return;const entry=desk.active(),payload=entry?.record.payload;if(!payload)return;const saved=payload.items.find((row:any)=>row.key===meta.kind+":"+meta.id);if(!saved)return;
      const headings=[...(article.current?.querySelectorAll<HTMLElement>("h2[id]")||[])],heading=headings.filter(node=>node.getBoundingClientRect().top<180).at(-1),anchor=heading?"#"+heading.id:"";
      if(saved.anchor!==anchor)desk.edit({items:payload.items.map((row:any)=>row.key===saved.key?{...row,anchor}:row)});
    };
    let timer:ReturnType<typeof setTimeout>|undefined;
    const scroll=()=>{if(timer)clearTimeout(timer);timer=setTimeout(capture,300);};
    window.addEventListener("scroll",scroll,{passive:true});return()=>{if(timer)clearTimeout(timer);capture();window.removeEventListener("scroll",scroll);};
  },[desk,meta.kind,meta.id]);
  return <div className="reader-layout"><aside className="reader-toc"><Link to="/?space=explore">← 回到探索</Link><p className="eyebrow">在这篇里</p><nav aria-label="本文目录">{contents(item,meta.kind).map((entry:any)=><Link key={entry.id} to={{pathname:readerLocation.pathname,search:readerLocation.search,hash:"#"+entry.id}}>{entry.text}</Link>)}</nav><div className="reader-actions"><button data-interactive="" onClick={add}>＋ 留在案头</button><PacketActions bootstrap={bootstrap} meta={meta}/><Link data-interactive="" to="/?space=continue">打开案头 →</Link></div></aside>
    <article ref={article} onClick={event=>{
      const target=(event.target as HTMLElement).closest<HTMLAnchorElement>("a");if(!target||event.metaKey||event.ctrlKey||event.shiftKey||event.altKey)return;
      const url=new URL(target.href),base=new URL(bootstrap.base,window.location.href);if(url.origin!==base.origin)return;
      const path=url.pathname.slice(base.pathname.length).split("/").filter(Boolean),params=url.searchParams;
      const found=bootstrap.catalogue.find((row:CatalogueItem)=>params.get(row.kind)===row.id||(path[0]===row.kind&&path[1]===row.id));
      if(found){event.preventDefault();setReference({meta:found,trigger:target});}
    }} onPointerUp={()=>{const picked=window.getSelection();setSelection(picked&&article.current?.contains(picked.anchorNode)?picked.toString().trim():"");}} onKeyUp={()=>{const picked=window.getSelection();setSelection(picked&&article.current?.contains(picked.anchorNode)?picked.toString().trim():"");}}>
      <header className="reader-heading"><p className="eyebrow">{labels[meta.kind as PublicKind]}</p><h1 id={meta.kind==="material"?"material-title":meta.kind==="study"?"study-title":"inquiry-title"} tabIndex={-1}>{item.title}</h1><p className="reader-dek">{item.question||item.claim||item.intro}</p><p className="byline">{meta.kind==="material"?`${item.authors?.join(", ")} · ${item.year} · 来源作者`:item.byline+" · "+(item.date||item.updated)}</p></header>
      <ContentBody kind={meta.kind} item={item} link={link}/><Exercise item={item} state={Object.fromEntries(query)} change={changeExercise}/>
    </article>
    {selection&&<div className="selection-action" data-interactive=""><span>已选 {selection.length} 字</span><button onClick={async()=>{try{await desk.add(meta,item);await desk.excerpt(meta.kind+":"+meta.id,selection,readerLocation.hash);setSelection("");notify("摘录与当时的来源版本已一起留下。");}catch(error){notify(String(error));}}}>摘到案头</button><button onClick={()=>setSelection("")} aria-label="关闭摘录">×</button></div>}
    {reference&&<ReferencePreview value={reference} link={link} bootstrap={bootstrap} close={()=>{reference.trigger.focus();setReference(null);}}/>}
  </div>;
}

function ReferencePreview({value,link,close,bootstrap}:any) {
  const [body,setBody]=useState<Content|null>(null),[error,setError]=useState("");
  useEffect(()=>{let active=true;const cached=bootstrap.portableContent?.[value.meta.kind+"/"+value.meta.id];if(cached)setBody(cached);else fetch(bootstrap.base+value.meta.shard).then(r=>{if(!r.ok)throw new Error("引用正文暂不可用。");return r.json();}).then(v=>{if(active)setBody(v);}).catch(e=>{if(active)setError(String(e));});return()=>{active=false;};},[value.meta.id]);
  const dialog=useRef<HTMLDialogElement>(null);useEffect(()=>{dialog.current?.showModal();},[]);
  return <dialog className="reference-preview" ref={dialog} onCancel={close}><div className="dialog-heading"><p className="eyebrow">引用，就在这里</p><button onClick={close} aria-label="关闭引用预览">×</button></div><h2>{value.meta.title}</h2><p>{value.meta.intro}</p><p className="margin-note">{value.meta.byline} · {value.meta.date}</p>{value.meta.ref&&<details><summary>本次公开版本</summary><code>{value.meta.ref.revision}</code></details>}{error&&<p role="alert">{error}</p>}{body&&<div className="reference-body"><ContentBody kind={value.meta.kind} item={body} link={link}/></div>}<p onClick={close}>{link(value.meta.kind,value.meta.id,"打开全文 →")}</p></dialog>;
}

function DeskView({desk,catalogue,bootstrap,link,action}:any) {
  const state=useSyncExternalStore<DeskState>(desk.subscribe,desk.snapshot,desk.snapshot),edit=desk.active(),session=edit?.record;
  const [preview,setPreview]=useState<any>(null);
  const status:Record<string,string>={ephemeral:"留在当前页面 · 下载后可带走",pending:"正在保存…",committed:"已保存到本机",conflict:"发现另一份改动 · 当前输入已保留",disconnected:"连接中断 · 当前输入尚未确认保存"};
  return <div className="continue-space"><div className="space-heading"><div><p className="eyebrow">CONTINUE / 继续</p><h1>从停下的地方，接着想。</h1><p className="space-intro">一条线索可以暂时没有名字。留下当下的问题，下次就有地方回来。</p></div><button disabled={state.creating} onClick={()=>action(()=>desk.create())}>{state.creating?"正在创建…":"＋ 新案头"}</button></div>
    {state.creating&&<p role="status">正在打开新案头，收到保存回执后就可以开始写。</p>}
    <div className="desk-layout" inert={state.creating} aria-busy={state.creating}><aside className="thread-list"><h2>研究线</h2>{state.threads.map((thread:any)=>{const sessions=state.sessions.filter((s:any)=>s.thread_ref.id===thread.id);return <section key={thread.id}><h3>{thread.title||"未命名的研究线"}</h3>{sessions.map((s:any)=><button key={s.id} aria-pressed={state.active===s.id} onClick={()=>desk.select(s.id)}>{s.payload.question||s.payload.next||"从这里开始"}<small>{s.payload.attention||"active"}</small></button>)}</section>;})}
      <label className="file-button">导入接续文件<input type="file" accept="application/json,.json" onChange={event=>{const file=event.target.files?.[0];if(file)void action(async()=>{const bytes=new Uint8Array(await file.arrayBuffer());setPreview(await desk.adapter.request("/import/preview",{base64:base64(bytes)}));});event.target.value="";}}/></label>
      {preview&&<div className="import-preview"><h3>导入预览</h3><p>{preview.message}</p><p>{preview.items??preview.records} 个对象；{preview.unresolved.length} 个待辨认。</p><button onClick={()=>action(async()=>{const result=await desk.adapter.request("/import/confirm",{digest:preview.digest});await desk.refresh();const root=result.mapping.roots.find((r:any)=>r.kind==="session");if(root)desk.select(root.id);setPreview(null);})}>确认导入</button><button onClick={()=>setPreview(null)}>取消</button></div>}
    </aside><section className="desk-main" aria-label="当前案头" onBlur={()=>desk.endGroup()}>
      {state.error&&<p role="alert">{state.error}</p>}
      {!session?<div className="empty-state"><span className="empty-orbit" aria-hidden="true">↝</span><h2>留一个可以回来的地方。</h2><p>带进一句话，或者在阅读时把一篇文章留在案头。</p><button onClick={()=>action(()=>desk.create())}>开始一条研究线</button></div>:<>
        <p className="desk-review-entry"><Link to="/?space=continue&tool=review">整理成文、比较依据与修订 →</Link></p><div className="save-bar"><span role="status" data-save-state={edit!.status}>{status[edit!.status]}</span><div><button disabled={!edit!.past.length} onClick={()=>desk.undo()}>撤销</button><button disabled={!edit!.future.length} onClick={()=>desk.undo(true)}>重做</button><button onClick={()=>action(async()=>download("ams-private-workspace.json",await desk.exportActive()))}>下载私人案头</button><button onClick={()=>action(async()=>download("ams-private-workspace.md",privateWorkspaceMarkdown(await desk.exportActive(false)),"text/markdown"))}>私人 Markdown ↓</button></div></div>
        {edit!.status==="disconnected"&&<button onClick={()=>action(()=>desk.flush())}>重试同一笔保存</button>}
        {edit!.status==="conflict"&&<div className="conflict-panel" role="alert"><h3>两份改动都值得先看一眼</h3><details><summary>当前已保存版本</summary><pre>{JSON.stringify(edit!.error?.current?.payload,null,2)}</pre></details><button onClick={()=>action(()=>desk.resolveConflict("current"))}>使用已保存版本</button><button onClick={()=>action(()=>desk.resolveConflict("mine"))}>以当前输入更新新版本</button></div>}
        <label className="desk-question">这一刻，想弄明白什么？<textarea aria-label="这一刻，想弄明白什么？" value={session.payload.question} placeholder="可以先是一句没想清楚的话。" onChange={event=>desk.edit({question:event.target.value})} onBlur={()=>desk.endGroup()}/></label>
        {!!session.payload.capture_refs?.length&&<div className="capture-shelf">{session.payload.capture_refs.map((pointer:any)=><CaptureCard key={pointer.id} desk={desk} pointer={pointer} catalogue={catalogue}/>)}</div>}
        {!!session.payload.lab_links?.length&&<LabContinuation desk={desk} links={session.payload.lab_links}/>}
        <div className="desk-items">{session.payload.items.map((item:any)=><section key={item.key}><div className="row-meta"><span>{item.binding==="unresolved"?"待辨认的旧对象":"留在案头"}</span><button aria-label="移出当前案头" onClick={()=>desk.edit({items:session.payload.items.filter((r:any)=>r.key!==item.key),compare:session.payload.compare.filter((key:string)=>key!==item.key)})}>移出</button></div><h3>{item.public_kind?link(item.public_kind,item.public_id,item.title,item.anchor||"",item.exercise||{}):item.title||item.legacy?.id||item.key}</h3>
          <label>旁注<textarea aria-label="旁注" value={item.note} onChange={event=>desk.edit({items:session.payload.items.map((r:any)=>r.key===item.key?{...r,note:event.target.value}:r)})} onBlur={()=>desk.endGroup()}/></label>
          <p className="margin-note">{item.excerpt_refs?.length||item.legacy_excerpts?.length||0} 条摘录 · 依据版本保留</p>
          {item.excerpt_refs?.map((pointer:any)=><ExcerptCard key={pointer.id} adapter={desk.adapter} pointer={pointer} annotation={item.excerpt_annotations?.[pointer.id]} onAnnotation={(patch:any)=>desk.edit({items:session.payload.items.map((r:any)=>r.key===item.key?{...r,excerpt_annotations:{...r.excerpt_annotations,[pointer.id]:{...r.excerpt_annotations?.[pointer.id],...patch}}}:r)})}/>)}
          {item.legacy_excerpts?.map((part:any)=><blockquote className="excerpt-card" key={part.id}><p>{part.quote||part.text}</p><p>{part.note||part.comment}</p><details><summary>旧摘录依据 · 纯文本</summary><pre>{part.basis}</pre></details></blockquote>)}
          <p><Link to="/?space=continue&tool=review" onClick={()=>{desk.edit({review_target_ref:item.target_ref});desk.endGroup();}}>带着这份依据继续写 →</Link></p><BasisComparison desk={desk} item={item} bootstrap={bootstrap}/></section>)}</div>
        <PublicSelection bootstrap={bootstrap} items={session.payload.items}/>
        {session.payload.items.length>1&&<Compare desk={desk} items={session.payload.items}/>}
        {[["synthesis","现在形成的理解"],["next","下次从哪里继续"],["return_when","什么时候再回来"]].map(([field,label])=><label className="desk-field" key={field}>{label}<textarea aria-label={label} value={session.payload[field]||""} onChange={event=>desk.edit({[field]:event.target.value})} onBlur={()=>desk.endGroup()}/></label>)}
        <label>这条线索现在<select value={session.payload.attention} onChange={event=>desk.edit({attention:event.target.value})}>{[["active","正在想"],["resting","先放在这里"],["waiting","等一个条件"],["closed","暂时告一段落"]].map(([v,t])=><option key={v} value={v}>{t}</option>)}</select></label>
      </>}
    </section></div></div>;
}

function CaptureDialog({desk,close,notify}:any) {
  const [file,setFile]=useState<File|null>(null);
  const ref=useRef<HTMLDialogElement>(null),[input,setInput]=useState(""),[why,setWhy]=useState(""),[saving,setSaving]=useState(false),[error,setError]=useState("");
  useEffect(()=>{ref.current?.showModal();const previous=document.activeElement;return()=>{if(previous instanceof HTMLElement)previous.focus();};},[]);
  return <dialog ref={ref} className="capture-dialog" onCancel={close}><form onSubmit={async event=>{event.preventDefault();setSaving(true);try{if(file)await desk.captureFile(file,input,why);else await desk.capture(input,why);notify(desk.adapter.capabilities.durable?"这次遇见，已经留在本机。":"这次遇见留在当前页面；离开前可下载案头。");close();}catch(error){setError(String(error));}finally{setSaving(false);}}}>
    <div className="dialog-heading"><p className="eyebrow">CAPTURE / 带进来</p><button type="button" onClick={close} aria-label="关闭">×</button></div><h2>先留下，慢慢认清。</h2><label>遇见了什么？<textarea aria-label="遇见了什么？" autoFocus required={!file} value={input} onChange={event=>setInput(event.target.value)} placeholder="一句话、一个链接，或者尚未明白的概念。"/></label><label>为什么现在留它？<textarea aria-label="为什么现在留它？" value={why} onChange={event=>setWhy(event.target.value)} placeholder="可以暂时空着。"/></label><label className="file-button">或选一个本机文件<input type="file" onChange={event=>setFile(event.target.files?.[0]||null)}/></label>{file&&<p>{file.name} · {Math.round(file.size/1024)} KiB <button type="button" onClick={()=>setFile(null)}>移除选择</button></p>}<p className="margin-note">不必先命名、分类，或替它安排用途。文件原件只留在本机或当前页面。</p>{error&&<p role="alert">{error}</p>}<button className="primary-action" disabled={saving}>{saving?"正在留下…":"留在案头 →"}</button></form></dialog>;
}
