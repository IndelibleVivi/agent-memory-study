/* Interactive projection of ResearchMap. Only explicit references create edges. */
(() => {
  'use strict';
  const NS='http://www.w3.org/2000/svg';
  const kinds={study:'研究札记',material:'来源材料',question:'开放问题',finding:'实践判断'};
  const make=(tag,cls,text)=>{const el=document.createElement(tag);if(cls)el.className=cls;if(text)el.textContent=text;return el;};
  const svgEl=(tag,attrs={},text)=>{const el=document.createElementNS(NS,tag);for(const [key,value] of Object.entries(attrs))el.setAttribute(key,value);if(text)el.textContent=text;return el;};
  function mount({root,data,routeHref}) {
    const model=ResearchMap.graph(data), narrow=matchMedia('(max-width: 760px)');
    let width=narrow.matches?720:1200, height=narrow.matches?900:560;
    let layout=ResearchMap.clusterLayout(model,data.room.domains,width,height);
    const $=id=>root.querySelector(id), plot=$('#constellation-plot'), panel=$('#constellation-reading');
    const motion=matchMedia('(prefers-reduced-motion: reduce)');
    let hovered=-1;
    let selected=Math.max(0,model.nodes.findIndex(n=>n.id==='ams-thesis')), focus=false, kind='', domain='', query='', view='map';
    let camera={x:0,y:0,w:width,h:height}, target={...camera}, frame=0, previous=0, visible=false, paused=motion.matches, drag=null;
    let flowPhase=0;
    let matching=new Set(model.nodes.map((_,i)=>i));
    const svg=svgEl('svg',{viewBox:`0 0 ${width} ${height}`,role:'group','aria-label':'研究星图，可拖动平移；选择节点查看详情。缩放与复位按钮位于图下。',tabindex:'0'});
    const backdrop=svgEl('g',{'aria-hidden':'true',class:'map-coordinate'});
    const groupLayer=svgEl('g',{'aria-hidden':'true',class:'map-domains'});
    function drawGroups(){groupLayer.replaceChildren();backdrop.replaceChildren();layout.groups.forEach((group,i)=>{
      const points=model.nodes.map((n,j)=>({n,p:layout.positions[j]})).filter(({n})=>(n.primaryDomain||'unclassified')===group.id).map(({p})=>p);
      if(points.length){
        const xs=points.map(p=>p.x),ys=points.map(p=>p.y),cx=(Math.min(...xs)+Math.max(...xs))/2,cy=(Math.min(...ys)+Math.max(...ys))/2;
        backdrop.append(svgEl('ellipse',{cx,cy,rx:Math.max(75,(Math.max(...xs)-Math.min(...xs))/2+38),ry:Math.max(55,(Math.max(...ys)-Math.min(...ys))/2+35),transform:`rotate(${i%2?-12:12} ${cx} ${cy})`}));
      }
      const g=svgEl('g',{transform:`translate(${group.x} ${group.y})`,'data-domain':group.id});
      g.append(svgEl('text',{class:'map-domain-number',y:4},String(i+1).padStart(2,'0')),
        svgEl('text',{x:narrow.matches?40:30,y:0},group.title),svgEl('text',{x:30,y:16,class:'map-domain-english'},group.english));groupLayer.append(g);
    });}
    drawGroups();
    const edgeLayer=svgEl('g',{'aria-hidden':'true',class:'map-edges'});
    const edges=model.edges.map(([a,b])=>{
      const p=layout.positions[a],q=layout.positions[b];
      const path=svgEl('path',{d:`M${p.x},${p.y} Q${(p.x+q.x)/2+ (q.y-p.y)*.10},${(p.y+q.y)/2-(q.x-p.x)*.10} ${q.x},${q.y}`});edgeLayer.append(path);return path;
    });
    const nodeLayer=svgEl('g',{class:'map-nodes'});
    const nodes=model.nodes.map((node,i)=>{
      const p=layout.positions[i],g=svgEl('a',{href:routeHref(node.kind,node.id),class:`map-node map-${node.kind}`,transform:`translate(${p.x} ${p.y})`,'data-map-node':i,'aria-label':`${kinds[node.kind]}：${node.title}`,tabindex:'0'});
      g.append(svgEl('title',{},`${node.title} · ${kinds[node.kind]}`),svgEl('circle',{r:narrow.matches?32:22,class:'map-hit'}),svgEl('circle',{r:13,class:'map-halo'}));
      g.append(node.kind==='question'?svgEl('path',{d:'M0 -6 6 0 0 6 -6 0Z',class:'map-star'}):node.kind==='finding'?svgEl('rect',{x:-4,y:-4,width:8,height:8,class:'map-star'}):svgEl('circle',{r:node.kind==='study'?5:3.4,class:'map-star'}));
      const short=node.kind==='material'?(node.item.shortTitle||node.title.split(/[：:—]/)[0]):node.title;
      const label=short.length>19?short.slice(0,18)+'…':short;
      g.append(svgEl('text',{x:p.x>width*.68?-18:18,y:4,'text-anchor':p.x>width*.68?'end':'start',class:'map-node-label'},label));
      g.append(svgEl('text',{x:-5,y:-19,class:'map-node-number'},String(i+1).padStart(2,'0')));
      g.addEventListener('click',event=>{if(event.metaKey||event.ctrlKey||event.shiftKey||event.altKey)return;event.preventDefault();event.stopPropagation();if(!drag?.moved)choose(i);});
      g.addEventListener('keydown',event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();event.stopPropagation();choose(i);}});
      g.addEventListener('pointerenter',()=>{hovered=i;placeLabels();});g.addEventListener('pointerleave',()=>{hovered=-1;placeLabels();});
      g.addEventListener('focus',()=>{hovered=i;placeLabels();});g.addEventListener('blur',()=>{hovered=-1;placeLabels();});
      nodeLayer.append(g);return g;
    });
    svg.append(backdrop,edgeLayer,groupLayer,nodeLayer);plot.replaceChildren(svg);
    const list=$('#constellation-list');
    const listRows=model.nodes.map((node,i)=>{
      const row=make('div','map-list-row'), button=make('button','',node.title), link=make('a','','阅读 ↗');
      button.type='button';button.addEventListener('click',()=>choose(i));link.href=routeHref(node.kind,node.id);link.dataset.route=node.kind;link.dataset.routeId=node.id;
      row.append(make('span','map-list-kind',kinds[node.kind]),button,link);list.append(row);return row;
    });
    const domainSelect=$('#map-domain');
    layout.groups.forEach(group=>{const option=make('option','',group.title);option.value=group.id;domainSelect.append(option);});
    const nodeLink=(node,label)=>{const a=make('a','',label);a.href=routeHref(node.kind,node.id);a.dataset.route=node.kind;a.dataset.routeId=node.id;return a;};
    function describe() {
      const node=model.nodes[selected],related=[...ResearchMap.neighbors(model,selected)];
      const meta=make('div','map-reading-meta');meta.append(make('span','',kinds[node.kind]),make('span','',String(selected+1).padStart(2,'0')+' / '+model.nodes.length));
      const title=make('h3','',node.title);title.id='map-reading-title';
      const copy=make('p','map-reading-copy',node.summary||node.item.whyRead||'从原始材料与公开札记继续阅读。');
      const taxonomy=node.domainIds.map(id=>data.room.domains.find(d=>d.id===id)?.title).join(' · ')||'尚未归类';
      const open=nodeLink(node,'打开这份研究 ↗');open.className='map-read-link';open.id='map-open';
      const relatedHeading=make('p','map-related-heading',`EXPLICIT LINKS / ${related.length} 条引用关系`);
      const relatedList=make('div','map-related');
      related.forEach(i=>{const link=nodeLink(model.nodes[i],model.nodes[i].title);link.addEventListener('click',event=>{if(event.metaKey||event.ctrlKey||event.shiftKey||event.altKey)return;event.preventDefault();event.stopPropagation();choose(i);});relatedList.append(link);});
      if(!related.length)relatedList.append(make('p','','当前没有显式引用关系。'));
      const reading=make('div','map-reading-main'),relations=make('div','map-reading-relations');
      reading.append(title,make('p','map-taxonomy',taxonomy),copy,open);relations.append(relatedHeading,relatedList);
      panel.replaceChildren(meta,reading,relations);
      panel.dataset.selection=node.key;
      $('#map-announcement').textContent=`已选择${node.title}，${related.length}条显式引用。`;
    }
    function placeLabels() {
      if(!svg.isConnected||!svg.getClientRects().length)return;
      const overlaps=(a,b)=>a.x<b.x+b.w+4&&a.x+a.w+4>b.x&&a.y<b.y+b.h+3&&a.y+a.h+3>b.y;
      const obstacles=layout.groups.map((group,i)=>{const b=groupLayer.children[i].getBBox();return {x:group.x+b.x,y:group.y+b.y,w:b.width,h:b.height};});
      const points=layout.positions.map(p=>({x:p.x-11,y:p.y-11,w:22,h:22}));
      const priority=[...new Set([selected,hovered,...model.nodes.map((node,i)=>node.kind==='study'?i:-1),...model.nodes.map((_,i)=>!narrow.matches?i:-1)])].filter(i=>i>=0);
      nodes.forEach(node=>node.querySelector('.map-node-label').style.opacity='0');
      for(const i of priority){
        if(nodes[i].classList.contains('is-dimmed'))continue;
        const label=nodes[i].querySelector('.map-node-label'),p=layout.positions[i];
        const w=label.getComputedTextLength(),h=Math.max(12,label.getBBox().height);
        const choices=[[18,4,'start'],[-18,4,'end'],[0,-22,'middle'],[0,30,'middle'],[18,-18,'start'],[-18,28,'end']].map(([x,y,anchor])=>{
          const rect={x:p.x+x-(anchor==='end'?w:anchor==='middle'?w/2:0),y:p.y+y-h*.82,w,h};
          const score=obstacles.filter(o=>overlaps(rect,o)).length*4+points.filter(o=>overlaps(rect,o)).length;
          return {x,y,anchor,rect,score};
        }).filter(c=>c.rect.x>=8&&c.rect.x+c.rect.w<=width-8&&c.rect.y>=4&&c.rect.y+c.rect.h<=height-4).sort((a,b)=>a.score-b.score);
        const best=choices[0];
        if(!best||(best.score>0&&i!==selected&&i!==hovered))continue;
        label.setAttribute('x',best.x);label.setAttribute('y',best.y);label.setAttribute('text-anchor',best.anchor);label.style.opacity='1';obstacles.push(best.rect);
      }
    }
    function updateAppearance() {
      const related=ResearchMap.neighbors(model,selected);related.add(selected);
      nodes.forEach((node,i)=>{
        const shown=matching.has(i)&&(!focus||related.has(i));
        node.classList.toggle('is-dimmed',!shown);node.classList.toggle('is-selected',i===selected);
        node.classList.toggle('is-related',i!==selected&&related.has(i));
        node.setAttribute('tabindex',shown?'0':'-1');node.setAttribute('aria-current',i===selected?'true':'false');
        node.setAttribute('aria-hidden',String(!shown));
        listRows[i].hidden=!shown;listRows[i].classList.toggle('is-selected',i===selected);
      });
      edges.forEach((edge,i)=>{const [a,b]=model.edges[i],active=(a===selected||b===selected)&&matching.has(a)&&matching.has(b);edge.classList.toggle('is-active',active);edge.classList.toggle('is-dimmed',(!matching.has(a)||!matching.has(b))||(focus&&!active));});
      const count=[...matching].filter(i=>!focus||related.has(i)).length;
      $('#constellation-stats').textContent=`${String(count).padStart(2,'0')} / ${model.nodes.length} OBJECTS · ${model.edges.length} LINKS`;
      $('#map-empty').hidden=count>0;
      $('#map-focus').setAttribute('aria-pressed',String(focus));placeLabels();
    }
    function bounds(indices) {
      if(!indices.length)return {x:0,y:0,w:width,h:height};
      const points=indices.map(i=>layout.positions[i]),xs=points.map(p=>p.x),ys=points.map(p=>p.y);
      let w=Math.max(360,Math.max(...xs)-Math.min(...xs)+190),h=Math.max(240,Math.max(...ys)-Math.min(...ys)+160);
      w=Math.max(w,h*width/height);h=w*height/width;
      return {x:(Math.min(...xs)+Math.max(...xs)-w)/2,y:(Math.min(...ys)+Math.max(...ys)-h)/2,w,h};
    }
    function fit() {target=bounds(focus?[selected,...ResearchMap.neighbors(model,selected)].filter(i=>matching.has(i)):[...matching]);refresh();}
    function choose(index) {selected=index;describe();updateAppearance();if(focus)fit();else refresh();}
    function filter() {
      const terms=query.toLocaleLowerCase().trim().split(/\s+/).filter(Boolean);
      matching=new Set(model.nodes.map((n,i)=>({n,i})).filter(({n})=>(!kind||n.kind===kind)&&(!domain||(domain==='unclassified'?!n.primaryDomain:n.domainIds.includes(domain)))&&terms.every(t=>`${n.title} ${n.summary} ${n.id}`.toLocaleLowerCase().includes(t))).map(({i})=>i));
      if(!matching.has(selected)&&matching.size){selected=[...matching][0];describe();}
      updateAppearance();fit();
    }
    function paint() {svg.setAttribute('viewBox',`${camera.x} ${camera.y} ${camera.w} ${camera.h}`);edgeLayer.style.setProperty('--map-flow',String(flowPhase));$('#map-zoom-value').textContent=Math.round(width/camera.w*100)+'%';}
    function animate(now) {
      frame=0;const dt=previous?Math.min(40,now-previous):16;previous=now;
      const step=motion.matches?1:1-Math.exp(-dt/100);
      for(const k of ['x','y','w','h'])camera[k]+=(target[k]-camera[k])*step;
      if(!paused)flowPhase-=dt*.012;
      paint();
      const moving=Object.keys(camera).some(k=>Math.abs(camera[k]-target[k])>.05);
      if(visible&&!document.hidden&&view==='map'&&(!paused||moving))frame=requestAnimationFrame(animate);else previous=0;
    }
    function refresh() {
      if(frame)cancelAnimationFrame(frame);frame=0;previous=0;
      const running=visible&&!document.hidden&&view==='map';root.dataset.motion=running&&!paused?'running':'still';
      $('#map-motion').setAttribute('aria-pressed',String(paused));$('#map-motion').textContent=paused?'动态 ○':'静止 Ⅱ';
      if(motion.matches)camera={...target};
      placeLabels();paint();
      if(running)frame=requestAnimationFrame(animate);
    }
    function zoom(factor) {const w=Math.max(240,Math.min(width*1.6,target.w*factor)),h=w*height/width;target={x:target.x+(target.w-w)/2,y:target.y+(target.h-h)/2,w,h};refresh();}
    $('#map-zoom-in').addEventListener('click',()=>zoom(.78));$('#map-zoom-out').addEventListener('click',()=>zoom(1/.78));
    $('#map-reset').addEventListener('click',()=>{focus=false;kind='';domain='';query='';$('#map-query').value='';domainSelect.value='';root.querySelectorAll('[data-map-kind]').forEach(b=>b.setAttribute('aria-pressed',String(!b.dataset.mapKind)));filter();target={x:0,y:0,w:width,h:height};refresh();});
    $('#map-focus').addEventListener('click',()=>{focus=!focus;updateAppearance();fit();});
    $('#map-motion').addEventListener('click',()=>{paused=!paused;refresh();});
    $('#map-query').addEventListener('input',event=>{query=event.target.value;filter();});domainSelect.addEventListener('change',()=>{domain=domainSelect.value;filter();});
    root.querySelectorAll('[data-map-kind]').forEach(button=>button.addEventListener('click',()=>{kind=button.dataset.mapKind;root.querySelectorAll('[data-map-kind]').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));filter();}));
    root.querySelectorAll('[data-map-view]').forEach(button=>button.addEventListener('click',()=>{view=button.dataset.mapView;root.querySelectorAll('[data-map-view]').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));plot.hidden=view!=='map';list.hidden=view!=='list';$('#map-camera-controls').hidden=view!=='map';refresh();}));
    const fullscreen=$('#map-fullscreen');
    if(root.requestFullscreen && document.fullscreenEnabled){
      fullscreen.hidden=false;
      fullscreen.addEventListener('click',async()=>{
        try{if(document.fullscreenElement===root)await document.exitFullscreen();else await root.requestFullscreen();}
        catch{ $('#map-announcement').textContent='当前浏览器未能进入全屏，星图仍可在页面内使用。'; }
      });
      document.addEventListener('fullscreenchange',()=>{
        fullscreen.textContent=document.fullscreenElement===root?'退出全屏 ×':'展开星图 ⤢';
        fullscreen.setAttribute('aria-pressed',String(document.fullscreenElement===root));refresh();
      });
      root.addEventListener('click',event=>{
        if(!event.defaultPrevented&&event.target.closest('a[data-route]')&&document.fullscreenElement===root)document.exitFullscreen().catch(()=>{});
      });
    }
    const pointer=event=>{const p=new DOMPoint(event.clientX,event.clientY);return p.matrixTransform(svg.getScreenCTM().inverse());};
    svg.addEventListener('pointerdown',event=>{if(drag||event.button!==0||event.metaKey||event.ctrlKey||event.shiftKey||event.altKey)return;const p=pointer(event);drag={id:event.pointerId,start:p,node:event.target.closest('[data-map-node]')?.dataset.mapNode,moved:false};svg.setPointerCapture(event.pointerId);});
    svg.addEventListener('pointermove',event=>{if(!drag||event.pointerId!==drag.id)return;const p=pointer(event),dx=p.x-drag.start.x,dy=p.y-drag.start.y;if(Math.hypot(dx,dy)>5)drag.moved=true;if(drag.moved){target={...camera,x:camera.x-dx,y:camera.y-dy};target.x=Math.max(-target.w*.85,Math.min(width-target.w*.15,target.x));target.y=Math.max(-target.h*.85,Math.min(height-target.h*.15,target.y));camera={...target};paint();svg.classList.add('is-dragging');}});
    const release=event=>{if(!drag||event.pointerId!==drag.id)return;if(!drag.moved&&drag.node!==undefined)choose(Number(drag.node));if(svg.hasPointerCapture(event.pointerId))svg.releasePointerCapture(event.pointerId);svg.classList.remove('is-dragging');setTimeout(()=>{drag=null;},0);};
    svg.addEventListener('pointerup',release);svg.addEventListener('pointercancel',release);
    // The canvas has explicit buttons; wheel scrolling remains ordinary page scrolling.
    svg.addEventListener('keydown',event=>{if(event.target!==svg)return;const step=camera.w*.08;if(event.key==='+'||event.key==='='){zoom(.78);}else if(event.key==='-'){zoom(1/.78);}else if(event.key==='Home'){target={x:0,y:0,w:width,h:height};refresh();}else if(['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(event.key)){target={...target,x:target.x+({'ArrowLeft':-step,'ArrowRight':step}[event.key]||0),y:target.y+({'ArrowUp':-step,'ArrowDown':step}[event.key]||0)};refresh();}else return;event.preventDefault();});
    narrow.addEventListener('change',()=>{
      width=narrow.matches?720:1200;height=narrow.matches?900:560;
      layout=ResearchMap.clusterLayout(model,data.room.domains,width,height);drawGroups();
      nodes.forEach((node,i)=>{const p=layout.positions[i];node.setAttribute('transform',`translate(${p.x} ${p.y})`);node.querySelector('.map-hit').setAttribute('r',narrow.matches?32:22);const label=node.querySelector('.map-node-label');label.setAttribute('x',p.x>width*.68?-18:18);label.setAttribute('text-anchor',p.x>width*.68?'end':'start');});
      edges.forEach((edge,i)=>{const [a,b]=model.edges[i],p=layout.positions[a],q=layout.positions[b];edge.setAttribute('d',`M${p.x},${p.y} Q${(p.x+q.x)/2+(q.y-p.y)*.10},${(p.y+q.y)/2-(q.x-p.x)*.10} ${q.x},${q.y}`);});
      camera={x:0,y:0,w:width,h:height};target={...camera};placeLabels();if(focus||query||domain||kind)fit();refresh();
    });
    new IntersectionObserver(entries=>{visible=entries[0].isIntersecting;refresh();},{threshold:.02}).observe(plot);
    document.addEventListener('visibilitychange',refresh);motion.addEventListener('change',()=>{paused=motion.matches;refresh();});
    root.querySelectorAll('[data-js-control]').forEach(el=>el.hidden=false);
    describe();updateAppearance();paint();
    document.fonts.ready.then(placeLabels);
    return {refresh};
  }
  window.AMSConstellation={mount};
})();
