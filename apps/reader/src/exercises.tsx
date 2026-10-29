import React, {useEffect,useState} from "react";
import IndexStudy from "../../../assets/index-study.js";
import StudyDesk from "../../../assets/study-desk.js";
import RevisionStudy from "../../../assets/revision-study.js";
import {download} from "./adapters";
import type {Content} from "./types";

type Props = {item:Content;state:Record<string,string>;change:(fields:Record<string,string|number>)=>void};
export function Exercise({item,state,change}:Props) {
  if (item.exercise==="ordered-index") return <IndexExercise state={state} change={change}/>;
  if (item.exercise==="retrieval-sets") return <RetrievalExercise state={state} change={change}/>;
  if (item.kind==="editorial-synthesis-with-deterministic-demo") return <RevisionExercise item={item} state={state} change={change}/>;
  if (item.kind==="editorial-synthesis-with-proposed-experiment") return <section className="study-lab" id="study-lab"><p className="eyebrow">研究方案 · 尚未执行</p><h2>{item.labTitle}</h2><p>{item.labIntro}</p><p>{item.boundary}</p><a href={item.artifactUrl}>阅读方案与执行边界 →</a></section>;
  if (item.recordedResults) return <RecordedStudy item={item} state={state} change={change}/>;
  return null;
}
function Selector({id,label,value,options,onChange,disabled=false}:{id:string;label:string;value:string;options:string[][];onChange:(value:string)=>void;disabled?:boolean}) {
  return <label>{label}<select id={id} value={value} onChange={event=>onChange(event.target.value)} disabled={disabled}>{options.map(([value,text])=><option key={value} value={value}>{text}</option>)}</select></label>;
}
function RetrievalExercise({state,change}:Omit<Props,"item">) {
  const x=StudyDesk.exercise(state);
  return <section id="study-lab" className="study-lab"><p className="eyebrow">原创集合演算</p><h2>换一个集合，看看比例怎样变化。</h2><p>a–h、顺序与相关集合均为设定；这里没有执行 embedding、ANN 或模型检索。</p>
    <div className="study-controls" data-interactive=""><Selector id="retrieval-ranking" label="返回的排序" value={x.ranking} options={[["reference","A · 与参考近邻相同"],["contrast","B · 手工对照"]]} onChange={ranking=>change({ranking})}/>
      <Selector id="retrieval-need" label="当前相关集合" value={x.need} options={[["understand","R₁ = {a, d, e, f}"],["implement","R₂ = {b, c, g}"]]} onChange={need=>change({need})}/>
      <label>取前 k 项：{x.k}<input id="retrieval-k" type="range" min="1" max="8" value={x.k} onChange={event=>change({k:event.target.value})}/></label></div>
    <div className="retrieval-documents">{StudyDesk.documents.map((id:string)=><span key={id} className={`retrieval-doc ${x.selected.includes(id)?"is-selected":""} ${x.relevant.includes(id)?"is-relevant":""}`}>{id}</span>)}</div>
    <p className="margin-note">深色底 = 已返回 · 下划线 = 需求相关</p>
    <div className="retrieval-metrics" aria-live="polite">{[["近邻集合召回",x.neighborRecall,`${x.overlap.length} / ${x.k}`],[`Precision@${x.k}`,x.precision,`${x.hits.length} / ${x.k}`],[`Recall@${x.k}`,x.recall,`${x.hits.length} / ${x.relevant.length}`]].map(([label,value,formula])=><div key={label as string}><span>{label}</span><strong>{(Number(value)*100).toFixed(1)}%</strong><span>{formula}</span></div>)}</div>
    <p>返回 {'{'+x.selected.join(", ")+'}'} · 参考近邻 {'{'+x.reference.join(", ")+'}'} · 相关 {'{'+x.relevant.join(", ")+'}'}</p>
  </section>;
}
function IndexExercise({state,change}:Omit<Props,"item">) {
  const x=IndexStudy.evaluate(state), px=(key:number)=>40+key/130*520,py=(rank:number)=>220-rank/(x.keys.length+1)*190;
  const [query,setQuery]=useState(String(x.state.query));
  useEffect(()=>setQuery(String(x.state.query)),[x.state.query]);
  const traces=(title:string,trace:any[])=> <section><h3>{title}</h3>{trace.length?<ol>{trace.map((step,i)=><li key={i}>[{step.lo}, {step.hi}) → #{step.mid} 的键 {step.key} {step.relation} {x.state.query}</li>)}</ol>:<p>区间为空；直接检查边界位置。</p>}</section>;
  return <section id="study-lab" className="study-lab index-exercise"><p className="eyebrow">A POSITION IS A PREDICTION / 原创索引演算</p><h2>预测可以出错。查找怎样保持正确？</h2>
    <p>这里实际计算线性回归与二分查找，没有运行论文模型或 DSI。先查找 70，再插入四个键，观察位置、模型与误差界怎样改变。</p>
    <div className="study-controls" data-interactive=""><Selector id="index-dataset" label="键的分布" value={x.state.dataset} options={IndexStudy.DATASETS.map((d:any)=>[d.id,d.label])} onChange={dataset=>change({dataset,mutation:"base",repair:"stale",query:IndexStudy.DATASETS.find((d:any)=>d.id===dataset)!.query})}/>
      <Selector id="index-mutation" label="记录状态" value={x.state.mutation} options={[["base","原始记录"],["insert","插入一组新键"]]} onChange={mutation=>change({mutation})}/>
      <Selector id="index-repair" label="索引怎样跟上" value={x.state.repair} disabled={x.state.mutation==="base"} options={[["stale","沿用旧模型与旧界"],["rebound","保留模型，重测误差界"],["retrain","重新拟合与校准"]]} onChange={repair=>change({repair})}/>
      <form onSubmit={event=>{event.preventDefault();change({query:Number(query)});}}><label>查找键 · 0–130<input id="index-query" type="number" min="0" max="130" step="1" required value={query} onChange={event=>setQuery(event.target.value)}/></label><button>查找 →</button></form></div>
    <div className="index-board"><figure className="index-figure"><svg viewBox="0 0 600 260" role="img" aria-label="真实键的位置与当前线性预测；具体数值见逐键误差表">
      <defs><clipPath id="index-plot-clip"><rect x="40" y="10" width="520" height="224"/></clipPath></defs>
      {Array.from({length:Math.floor(x.keys.length/2)+1},(_,i)=><line key={i} x1="40" x2="560" y1={py(i*2)} y2={py(i*2)} className="index-gridline"/>)}
      <rect x="40" y={py(x.window.hi)} width="520" height={Math.max(2,py(x.window.lo)-py(x.window.hi))} className="index-band"/>
      <path d={Array.from({length:131},(_,key)=>`${key?"L":"M"}${px(key)},${py(x.model.a*key+x.model.b)}`).join(" ")} className="index-prediction" clipPath="url(#index-plot-clip)"/>
      <line x1={px(x.state.query)} x2={px(x.state.query)} y1="14" y2="244" className="index-query-line"/>
      {x.rows.map((row:any)=>row.inserted?<path key={row.key} d={`M${px(row.key)},${py(row.rank)-7} l7,7 -7,7 -7,-7 Z`} className="index-point is-inserted"><title>{`键 ${row.key} · 位置 ${row.rank} · 新插入`}</title></path>:<circle key={row.key} cx={px(row.key)} cy={py(row.rank)} r={row.key===x.state.query?7:5.5} className="index-point"><title>{`键 ${row.key} · 位置 ${row.rank}`}</title></circle>)}
      {[0,65,130].map(key=><text key={key} x={px(key)} y="250" textAnchor="middle">{key}</text>)}</svg>
      <figcaption>圆点：原有记录　铜色菱形：新增记录　斜线：f(k)　色带：当前搜索窗口</figcaption></figure>
      <div id="index-summary" aria-live="polite" data-fallback={String(x.result.fallback)}><p>{x.result.fallback?"旧窗口未通过检查 → 全区间回退":"相邻键检查通过 → 接受局部结果"}</p>
        <h3>{x.result.found?`找到 ${x.state.query}`:x.result.position===x.keys.length?"没有相等键 · 位于末尾":`没有相等键 · 后继 ${x.keys[x.result.position]}`}</h3>
        <dl className="index-metrics">{[["预测位置 p(q)",x.window.prediction],["局部候选位置",x.local.position],["最终 lower_bound",x.result.position]].map(([key,value])=><React.Fragment key={key}><dt>{key}</dt><dd>{value}</dd></React.Fragment>)}</dl>
        <p>窗口 [{x.window.lo}, {x.window.hi})；返回位置允许等于右端 {x.window.hi}。</p><p className="index-formula">f(k) = {x.model.a.toFixed(5)}k {x.model.b<0?"−":"+"} {Math.abs(x.model.b).toFixed(5)}</p>
        <p>误差界 [{x.model.minError}, {x.model.maxError}] · 拟合 {x.model.trainedCount} 条 · 校准 {x.model.calibratedCount} 条。</p><p className="index-calibration">{x.model.calibrationValid?"误差界已在当前记录上校准。":"记录已经变化，旧校准不再保证当前全部记录。"}</p></div></div>
    <ol className="index-records" aria-label="当前有序记录及从零开始的位置">{x.rows.map((row:any)=><li key={row.key} className={`${row.inserted?"is-inserted":""} ${row.inWindow?"in-window":""}`}><span>#{row.rank}</span><strong>{row.key}</strong><small>{row.inserted?"新增":"原有"}</small></li>)}</ol>
    <p className="index-guard">位置 i={x.local.position}：左侧须不存在或小于 {x.state.query}，右侧须不存在或大于等于 {x.state.query}。{x.local.certified?"两个条件成立。":"条件不成立，保留失败路径并回退。"}</p>
    <div className="index-traces">{traces("① 窗口内实际查找",x.local.trace)}{traces(x.result.fallback?"② 全区间回退":"对照 · 从全区间直接二分",x.result.fallback?x.result.trace:x.baseline.trace)}</div>
    <p className="margin-note">安全路径共 {x.result.comparisons} 次键比较，其中相邻检查 {x.result.guardComparisons} 次。对照不提供答案；比较次数不等于时间性能。</p>
    <details className="index-audit"><summary>逐键检查预测与误差</summary><p>旁路检查：{x.audit.covered} / {x.audit.total} 个存储键的位置落在候选范围内。</p><div className="table-scroll" tabIndex={0} role="region" aria-label="逐键误差表，可横向滚动"><table><thead><tr>{["键","真实位置","预测位置","位置 − 预测","记录"].map(value=><th key={value}>{value}</th>)}</tr></thead><tbody>{x.rows.map((row:any)=><tr key={row.key}>{[row.key,row.rank,row.prediction,row.error,row.inserted?"新增":"原有"].map((value,i)=><td key={i}>{value}</td>)}</tr>)}</tbody></table></div></details>
  </section>;
}
function RevisionExercise({item,state,change}:Props) {
  const scenario=item.scenarios.find((s:any)=>s.id===state.scenario)||item.scenarios.find((s:any)=>s.id==="corrected")||item.scenarios[0];
  const phase=state.phase==="after"?"after":"before", evidence=RevisionStudy.run(scenario,"scoped",phase);
  const verdicts:Record<string,string>={accepted:"工具接受",mismatch:"工具拒绝 · 参数不符",abstained:"未执行 · 任务未完成"};
  return <section id="study-lab" className="study-lab"><p className="eyebrow">原创规则演示</p><h2>{item.labTitle}</h2><p>{item.labIntro}</p><p className="research-boundary">{item.boundary}</p>
    <div className="study-controls" data-interactive=""><Selector id="study-scenario" label="选择一个场景" value={scenario.id} options={item.scenarios.map((s:any)=>[s.id,s.title])} onChange={scenario=>change({scenario})}/>
      <div role="group" aria-label="事件阶段">{[["before","事件前"],["after","应用事件后"]].map(([value,label])=><button key={value} id={"study-phase-"+value} aria-pressed={phase===value} onClick={()=>change({phase:value,scenario:scenario.id})}>{label}</button>)}</div></div>
    <p>{scenario.description}</p><p>{phase==="after"?"已应用":"尚未应用"}：{scenario.change.label}</p><div className="study-experiment"><section><h3>当前任务 / export-json {scenario.target}</h3><ul>{evidence.evidence.map((r:any)=><li key={r.id}><span>{r.active?"有效":"已撤回"}</span> <code>{r.id}</code><p>{r.scope} → {r.flag} json</p></li>)}</ul></section>
      <div>{item.policies.map((policy:any)=>{const r=RevisionStudy.run(scenario,policy.id,phase);return <section key={policy.id} className="study-output"><h3>{policy.label}</h3><strong>{verdicts[r.verdict]}</strong><p>{policy.description}</p><code>{r.flag?`export-json ${r.flag} json`:"暂不建议执行"}</code><p>依据：{r.supports.join("、")||"无"}</p></section>;})}</div></div>
    <p>独立工具 contract：{scenario.target} 接受 {evidence.expected} json；仅用于执行后的检查。</p><p>{scenario.lesson}</p><a href={item.artifactUrl}>方法、源码与逐场景结果 ↗</a></section>;
}
function ReceiptTable({id,caption,headings,rows}:{id:string;caption:string;headings:string[];rows:any[][]}) {
  return <div className="table-scroll" tabIndex={0} role="region" aria-label={caption+"；可横向滚动"}><table id={id}><caption>{caption}</caption><thead><tr>{headings.map(h=><th key={h} scope="col">{h}</th>)}</tr></thead><tbody>{rows.map((row,i)=><tr key={i}>{row.map((value,j)=>j?<td key={j}>{value}</td>:<th scope="row" key={j}>{value}</th>)}</tr>)}</tbody></table></div>;
}
function RecordedStudy({item,state,change}:Props) {
  const saved=item.recordedResults, cases=saved.cases||[],phase=state.phase==="after"?"after":"before",jev=saved.schema==="ams-jev-contract-results/1";
  const ids=[...new Set(cases.map((row:any)=>jev?row.id:row.event))] as string[];
  const selected=ids.includes(state.scenario)?state.scenario:jev?ids[0]:(cases.find((r:any)=>r.scope==="changed")?.event||ids[0]);
  const rows=cases.map((row:any,index:number)=>({...row,indexInReceipt:index})).filter((row:any)=>(jev?row.id:row.event)===selected),one=rows[0];
  const methods:Record<string,string>=phase==="after"?{frozen:"仅改记录 · 参数不动",refit:"完整重训",incremental:"仅纠正样本 · 继续训练",guard:"运行时约束"}:{"no-experience":"不使用新增经验",episodic:"案例近邻",rules:"归纳规则",scorer:"小型分类器"};
  const fraction=(m:any)=>`${m.correct}/${m.n}`,labels:Record<string,string>={useful:"有用",redundant:"已知 / 无增量",irrelevant:"不相关",harmful:"有害"};
  return <section id="study-lab" className="study-lab"><p className="eyebrow">保存的运行证据 · 已执行{jev?"源码对照":"结构化标签实验"}</p><h2>{item.labTitle}</h2><p>{item.labIntro}</p><p className="research-boundary">{item.boundary}</p>
    <div className="study-controls" data-interactive=""><Selector id="study-scenario" label="事件 / case" value={selected} options={ids.map(id=>[id,jev?cases.find((r:any)=>r.id===id).title:id])} onChange={scenario=>change({scenario})}/><div role="group" aria-label="查看保存的前后状态">{[["before",jev?"调用前":"初次学习"],["after",jev?"调用后":"纠正反馈后"]].map(([id,label])=><button key={id} id={"study-phase-"+id} aria-pressed={phase===id} onClick={()=>change({phase:id,scenario:selected})}>{label}</button>)}</div></div>
    {jev?<><p>{one.intervention}</p><p id="contract-comparison">存储节点 {one.before.stored_ids.length} → {one.after.stored_ids.length}；向量成员 {one.before.vector_ids.length} → {one.after.vector_ids.length}；派生摘要 {one.before.summary_ids.length} → {one.after.summary_ids.length}；关系 {one.before.links.length} → {one.after.links.length}。</p><section id="contract-state"><h3>{phase==="after"?"调用后的快照":"调用前的快照"}</h3><dl>{[["stored_ids","存储节点"],["vector_ids","向量成员"],["summary_ids","派生摘要"]].map(([field,label])=><React.Fragment key={field}><dt>{label}</dt><dd>{one[phase][field].join(" · ")||"无"}</dd></React.Fragment>)}</dl></section><p className="margin-note">统一显示标签对应运行 UUID。内存后端的成员变化不证明真实持久化或语义检索命中。</p><p>本例执行断言 {Object.values(one.checks).filter(Boolean).length}/{Object.keys(one.checks).length} 符合预期；这不是模型判断正确率。</p><details id="contract-observations"><summary>给定判断、实际返回与逐项断言</summary><pre>{JSON.stringify(cases.find((r:any)=>r.id===selected),null,2)}</pre></details><details><summary>原函数、替身与限制</summary><pre>{JSON.stringify({source:saved.source,method:saved.method,boundary:saved.boundary},null,2)}</pre></details></>:
    <><p>{saved.splits.train.groups} 个训练组 / {saved.splits.test.groups} 个测试组；测试 {saved.splits.test.events} 个事件、{saved.splits.test.rows} 条候选。{saved.support.test_rows_with_seen_vector}/{saved.support.test_rows} 条测试观测向量曾在训练中出现；这是支持内标签预测，不是新语义泛化。</p><p>{phase==="after"?"新标签只改变敏感任务中原本有用但来源未核验的候选。有效边界属于保留范围，两列不能相加。":"四种具体实现接受同一观测；三种学习器使用同一训练反馈。标签一致不代表真实任务完成率。"}</p>
    <ReceiptTable id="decision-summary" caption={phase==="after"?"纠正后的范围检查 · 正确数 / 总数":"初次学习 · 测试集实际预测"} headings={phase==="after"?["处理","应改变范围","应保留范围","其中：有效边界"]:["方法","标签正确","选择集合完全正确","有用候选遗漏","有害候选误选","全不选正确"]} rows={Object.entries(methods).map(([id,name])=>{const m=saved[phase].metrics[id];return phase==="after"?[name,fraction(m.changed),fraction(m.preserved),fraction(m.boundary)]:[name,fraction(m),`${m.exact_selection}/${m.events}`,m.useful_missed,m.harmful_selected,`${m.correct_empty}/${m.empty_events}`];})}/>
    <p>当前任务：{one.context.family} / {one.context.goal}；{one.context.sensitive?"敏感":"普通"}范围。已知：{one.context.known.join("、")}；可用工具：{one.context.tools.join("、")}。</p>
    <ReceiptTable id="decision-cases" caption="完整候选 · 标签一致与不一致" headings={["候选经验","生成规则标签",...Object.values(methods)]} rows={rows.map((r:any)=>{const expected=r[phase==="after"?"expected_v2":"expected_v1"];return [r.candidate.description,labels[expected],...Object.keys(methods).map(id=>{const p=saved[phase].predictions[id][r.indexInReceipt];return `${p===expected?"✓":"✕"} ${labels[p]}`;})];})}/>
    <details><summary>此事件的原始观测与两个版本标签</summary><pre>{JSON.stringify(rows.map(({indexInReceipt,...row}:any)=>row),null,2)}</pre></details><details><summary>负控制、信息删减与拟合规模</summary><p>分类器 {saved.cost.scorer_parameters} 个参数，{saved.cost.fit_steps} 步拟合；案例 {saved.cost.saved_cases} 条；规则 {saved.cost.rule_leaves} 个叶节点；增量更新 {saved.cost.incremental_rows} 条纠正样本。</p><ReceiptTable id="decision-control" caption="置换训练标签，保持测试标签" headings={["方法","标签正确"]} rows={Object.entries(saved.controls["shuffled-label"]).map(([id,m])=>[id,fraction(m)])}/><ReceiptTable id="decision-ablation" caption="输入删减 · 独立重新拟合" headings={["可见输入","标签正确"]} rows={Object.entries(saved.controls["input-ablations"]).map(([id,m])=>[id,fraction(m)])}/><p>名称一致重命名：{saved.controls["identity-invariance"]?"输出不变":"输出发生变化"}。名称原本不进入特征；这里只检查实现的标识依赖。</p></details></>}
    <p><a href={item.resultsUrl}>完整保存结果 ↗</a> · <a href={item.artifactUrl}>方法与复跑入口 ↗</a></p><button data-interactive="" onClick={()=>download(item.id+"-results.json",saved)}>下载实验结果 JSON</button><p className="margin-note">这里只读取保存的 receipt，没有重新运行上游源码或模型。</p></section>;
}
