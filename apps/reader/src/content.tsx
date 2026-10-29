import React from "react";
import type {Content, PublicKind, CatalogueItem} from "./types";

export const labels: Record<PublicKind,string> = {material:"来源札记",study:"研究文章",question:"开放问题",finding:"实践判断"};
export function Section({id,title,children}:{id:string;title:string;children:React.ReactNode}) {
  return <section id={id} className="reader-section"><h2>{title}</h2>{children}</section>;
}
const Paragraphs = ({items}:{items?:string[]}) => <>{items?.map((text,i)=><p key={i}>{text}</p>)}</>;
function Notes({items}:{items:any[]}) {
  return <>{items.map((item,i)=><section className="reader-note" key={i}>
    {item.type&&<small>{item.type}</small>}
    {(item.title||item.label||item.step)&&<h3>{item.title||item.label||item.step}</h3>}
    {Object.entries(item).filter(([key])=>!["title","label","step","url","links","id","type"].includes(key)).map(([key,value])=>
      typeof value==="string"?<p key={key} className={["limit","boundary","locator","basis"].includes(key)?"margin-note":undefined}>{value}</p>:
      Array.isArray(value)&&value.every(v=>typeof v==="string")?<Paragraphs key={key} items={value}/>:null)}
    {item.url&&<a href={item.url}>查看依据 ↗</a>}
    {item.links?.map((link:any)=><a key={link.url} href={link.url}>{link.label} ↗</a>)}
  </section>)}</>;
}
export function MaterialBody({item,link}:{item:Content;link:any}) {
  const sections:[string,string,any,string][] = [
    ["paper-reading","为什么读它",item.whyRead,"text"], ["paper-grips","关键抓手",item.keyPoints,"paragraphs"],
    ["paper-argument","论证怎样展开",item.argumentMap,"notes"], ["paper-method","方法与测量",item.methodNotes,"notes"],
    ["paper-findings","论文报告了什么",item.reportedFindings,"paragraphs"], ["paper-limits","证据到哪里为止",item.evidenceLimits,"paragraphs"],
    ["paper-tensions","原文内部的张力",item.sourceTensions,"notes"], ["paper-inferences","编者判断",item.editorialInferences,"notes"],
    ["paper-protocols","可继续检验的方案 · 未执行",item.openProtocols,"notes"], ["paper-contributions","署名观点与已记录的测试",item.contributions,"notes"]
  ];
  return <>
    <aside className="source-scope"><p><strong>实际阅读范围 · {item.noteDepth}</strong></p><p>{item.readingScope}</p>
      <p className="source-actions"><a href={item.pdf?.url}>阅读 PDF ↗</a><a href={item.sourceUrl}>官方来源 ↗</a></p>
      <small>{item.pdf?.delivery==="bundled"?`随站分发 · ${item.pdf.license}`:`官方链接 · ${item.pdf?.accessNote||""}`}</small>
      {item.pdf?.licenseUrl&&<a href={item.pdf.licenseUrl}>文件授权 ↗</a>}<p className="margin-note">{item.sourceNote}</p></aside>
    {sections.filter(([, ,value])=>value&&(typeof value==="string"||value.length)).map(([id,title,value,type])=><Section key={id} id={id} title={title}>
      {type==="text"?<p>{value}</p>:type==="notes"?<Notes items={value}/>:<Paragraphs items={value}/>}</Section>)}
    {item.amsEvidence&&<Section id="paper-ams-evidence" title="本站的已执行观察"><p className="byline">{item.amsEvidence.byline}</p>
      <Paragraphs items={item.amsEvidence.observations}/><Paragraphs items={item.amsEvidence.findings}/>
      <details><summary>复核方法与推论</summary><Notes items={item.amsEvidence.methods||[]}/><Notes items={item.amsEvidence.reasoning||[]}/></details>
      <a href={item.amsEvidence.artifactUrl}>方法、记录与复跑入口 ↗</a></Section>}
    {item.designTransfer&&<Section id="paper-transfer" title="这一步，可以怎样借用？"><p className="margin-note">编者建议 · proposed-not-run · {item.designTransfer.byline} · {item.designTransfer.date}</p>
      {["abstract","skim"].includes(item.noteDepth)&&<p>初读线索，仍待全文与实现核验。</p>}
      <dl>{[["when","什么时候"],["move","可以借哪一步"],["check","先做什么对照"],["boundary","边界"],["basis","依据"]].map(([key,label])=><React.Fragment key={key}><dt>{label}</dt><dd>{item.designTransfer[key]}</dd></React.Fragment>)}</dl></Section>}
    {!!item.studyConnections?.length&&<Section id="paper-studies" title="在研究中怎样读到它">{item.studyConnections.map((connection:any)=><section key={connection.id} className="reader-note"><h3>{link("study",connection.id,connection.title)}</h3><p>{connection.takeaway}</p><p className="margin-note">{connection.locator}</p><p>{connection.limit}</p></section>)}</Section>}
    <Section id="paper-question" title="继续追问"><p>{item.editorialQuestion}</p></Section>
  </>;
}

export function InquiryBody({item,kind,link}:{item:Content;kind:"question"|"finding";link:(kind:PublicKind,id:string,text?:string)=>React.ReactNode}) {
  return <>
    {kind==="question"?<Section id="inquiry-judgment" title="目前的认识"><p>{item.judgment}</p><p>{item.intro}</p><Notes items={item.explanations||[]}/></Section>:
      <Section id="inquiry-use" title="怎样借用"><dl>{[["when","什么时候想起它"],["action","它改变哪个选择"],["avoid","不要这样使用"],["validation","在目标侧怎样检查"]].map(([key,label])=><React.Fragment key={key}><dt>{label}</dt><dd>{item[key]}</dd></React.Fragment>)}</dl><p className="margin-note">{item.limit}</p></Section>}
    <Section id="inquiry-evidence" title="这件事，是怎么知道的？"><Notes items={item.evidence||[]}/><div className="reference-list">{item.materialIds?.map((id:string)=><React.Fragment key={id}>{link("material",id)}</React.Fragment>)}</div></Section>
    {kind==="question"?<><Section id="inquiry-next" title="下一次，怎样让认识改变？">{item.nextTest&&<Notes items={[item.nextTest]}/>}</Section>
      <Section id="inquiry-practice" title="带回实践"><div className="reference-list">{item.findingIds?.map((id:string)=><React.Fragment key={id}>{link("finding",id)}</React.Fragment>)}{item.studyIds?.map((id:string)=><React.Fragment key={id}>{link("study",id)}</React.Fragment>)}</div></Section></>:
      <Section id="inquiry-applications" title="取用之后，发生了什么？"><Notes items={item.applications||[]}/>{!item.applications?.length&&<p>尚无公开的目标侧取用记录。</p>}<p className="margin-note">引用过、采用过、有帮助是不同结论。</p></Section>}
  </>;
}

export function StudyBody({item,link}:{item:Content;link:(kind:PublicKind,id:string,text?:string)=>React.ReactNode}) {
  return <>
    <div className="study-essay" dangerouslySetInnerHTML={{__html:item.bodyHtml||""}}/>
    {!!(item.readings?.length||item.externalReadings?.length)&&<details id="study-sources" className="reader-section"><summary>来源与实际阅读范围</summary>
      {item.readings?.map((reading:any)=><section key={reading.materialId} className="reader-note"><h3>{link("material",reading.materialId,reading.label)}</h3><p>{reading.takeaway}</p><p className="margin-note">{reading.locator}</p><p>{reading.limit}</p></section>)}
      {item.externalReadings?.map((reading:any)=><section key={reading.url} className="reader-note"><small>{reading.kind}</small><h3><a href={reading.url}>{reading.label} ↗</a></h3><p>{reading.takeaway}</p><p className="margin-note">{reading.locator}</p><p>{reading.limit}</p></section>)}
    </details>}
    {!!(item.takeaways?.length||item.closing)&&<Section id="study-takeaways" title="留下的理解"><Notes items={item.takeaways||[]}/><p>{item.closing}</p></Section>}
    {!!item.changes?.length&&<Section id="study-changes" title="理解怎样变化"><Notes items={item.changes}/></Section>}
    {item.boundary&&<p className="research-boundary">{item.boundary}</p>}
    {item.continuation&&<Section id="study-continuation" title="下次，从这里继续"><h3>{item.continuation.question}</h3><p>{item.continuation.why}</p>
      <div className="reference-list">{item.continuation.studyIds?.map((id:string)=><React.Fragment key={id}>{link("study",id)}</React.Fragment>)}{item.continuation.materialIds?.map((id:string)=><React.Fragment key={id}>{link("material",id)}</React.Fragment>)}</div></Section>}
  </>;
}

export function ContentBody({kind,item,link}:{kind:PublicKind;item:Content;link:(kind:PublicKind,id:string,text?:string)=>React.ReactNode}) {
  return kind==="material"?<MaterialBody item={item} link={link}/>:kind==="study"?<StudyBody item={item} link={link}/>:<InquiryBody kind={kind} item={item} link={link}/>;
}

export function contents(item:Content,kind:PublicKind) {
  if (kind==="study") return [...(item.bodyHtml||"").matchAll(/<h2(?: id="([^"]+)")?[^>]*>(.*?)<\/h2>/gs)].map((match:any,i:number)=>({id:match[1]||`section-${i+1}`,text:match[2].replace(/<[^>]+>/g,"")}));
  if (kind==="material") return [["paper-reading","为什么读它"],["paper-grips","关键抓手"],["paper-argument","论证怎样展开"],["paper-method","方法与测量"],["paper-findings","论文报告"],["paper-limits","证据边界"],["paper-question","继续追问"]].map(([id,text])=>({id,text}));
  return [{id:"inquiry-evidence",text:"依据与边界"},{id:kind==="question"?"inquiry-next":"inquiry-applications",text:kind==="question"?"下一问":"取用记录"}];
}
