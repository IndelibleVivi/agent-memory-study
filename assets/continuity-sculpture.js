/* Public research objects, rendered as an interactive ring. Spatial layouts are
   editorial arrangements; connections are explicit links, never inferred similarity. */
(function (root, factory) {
  const api = factory(typeof module === "object" && module.exports ? require("./research-map.js") : root.ResearchMap);
  if (typeof module === "object" && module.exports) module.exports = api;
  else { root.ResearchSculpture = api; api.mount(root.READING_ROOM); }
})(typeof globalThis === "object" ? globalThis : this, function (map) {
  "use strict";
  const labels = {study:"STUDY", material:"SOURCE", question:"QUESTION", finding:"FINDING"};
  const {graph, neighbors} = map;
  function layout(model,mode,selected) {
    const count=model.nodes.length, linked=neighbors(model,selected), related=[...linked];
    const cols=Math.ceil(Math.sqrt(count)*1.35), rows=Math.ceil(count/cols);
    const domains=[...new Set(model.nodes.map(n=>n.primaryDomain))];
    const members=domains.map(d=>model.nodes.map((n,i)=>n.primaryDomain===d?i:-1).filter(i=>i>=0));
    return model.nodes.map((node,i)=>{
      if(mode==="spread") return [(i%cols-(cols-1)/2)*.39, ((rows-1)/2-Math.floor(i/cols))*.34, 0, .13, 0, 0, 1];
      if(mode==="links") {
        if(i===selected)return [0,0,.65,.43,0,0,1];
        const k=related.indexOf(i), angle=(k<0?i/count:k/Math.max(1,related.length))*Math.PI*2;
        const radius=k<0?2.0:1.35;
        return [Math.cos(angle)*radius,Math.sin(angle)*radius*.69,k<0?-.6:0,k<0?.07:.18,0,0,k<0?.1:1];
      }
      const sector=domains.indexOf(node.primaryDomain), group=members[sector];
      const angle=-Math.PI/2+(sector+.08+.84*(group.indexOf(i)+.5)/group.length)*Math.PI*2/domains.length;
      return [Math.cos(angle)*1.65,0,Math.sin(angle)*1.65,.57,0,-angle,1];
    });
  }
  // Each loop is one object; the cross-section angle groups its primary domain.
  function ribbonPoint(pose,angle,side=0) {
    const local=rotate([Math.cos(angle)*pose[3],Math.sin(angle)*pose[3],side*pose[3]*.037],pose[5],pose[4]);
    return [pose[0]+local[0],pose[1]+local[1],pose[2]+local[2]];
  }
  function rotate(p,yaw,pitch) {
    const c=Math.cos(yaw),s=Math.sin(yaw),x=p[0]*c+p[2]*s,z=-p[0]*s+p[2]*c;
    return [x,p[1]*Math.cos(pitch)-z*Math.sin(pitch),p[1]*Math.sin(pitch)+z*Math.cos(pitch)];
  }
  const focalLength=pitch=>3.8/(1+.85*Math.max(0,Math.abs(Math.sin(pitch))-.5));
  function project(p,yaw,pitch,width,height) {
    const [x,y,z]=rotate(p,yaw,pitch), scale=focalLength(pitch)/(7-z), size=Math.min(height,width*.55);
    return [width/2+x*scale*size*.64,height/2-y*scale*size/2,z];
  }
  function triangleDepth(points,x,y) {
    const [a,b,c]=points;
    const divisor=(b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1]);
    if(Math.abs(divisor)<1e-8)return null;
    const u=((b[1]-c[1])*(x-c[0])+(c[0]-b[0])*(y-c[1]))/divisor;
    const v=((c[1]-a[1])*(x-c[0])+(a[0]-c[0])*(y-c[1]))/divisor,w=1-u-v;
    if(Math.min(u,v,w)<-1e-6)return null;
    return 7-1/(u/(7-a[2])+v/(7-b[2])+w/(7-c[2]));
  }
  function pickObject(projected,x,y) {
    let surface=null,nearest=null;
    for(const node of projected){
      for(const quad of node.quads){
        if(x<Math.min(...quad.map(p=>p[0]))||x>Math.max(...quad.map(p=>p[0]))||y<Math.min(...quad.map(p=>p[1]))||y>Math.max(...quad.map(p=>p[1])))continue;
        for(const triangle of [[quad[0],quad[1],quad[2]],[quad[2],quad[1],quad[3]]]){
          const z=triangleDepth(triangle,x,y);
          if(z!==null&&(!surface||z>surface.z))surface={i:node.i,d:0,z};
        }
      }
      // Generous hit area around thin rings; use the actual local segment, not
      // the loop's average depth. Empty loop centres remain selectable as well.
      let best={i:node.i,d:Math.hypot(node.p[0]-x,node.p[1]-y),z:node.p[2]};
      for(let j=0;j<node.curve.length;j++){
        const a=node.curve[j],b=node.curve[(j+1)%node.curve.length],dx=b[0]-a[0],dy=b[1]-a[1];
        const t=Math.max(0,Math.min(1,((x-a[0])*dx+(y-a[1])*dy)/(dx*dx+dy*dy||1)));
        const d=Math.hypot(x-a[0]-t*dx,y-a[1]-t*dy),z=7-1/((1-t)/(7-a[2])+t/(7-b[2]));
        if(d<best.d)best={i:node.i,d,z};
      }
      if(!nearest||best.d<nearest.d-1e-5||(Math.abs(best.d-nearest.d)<1e-5&&best.z>nearest.z))nearest=best;
    }
    return surface||nearest;
  }
  function mount(data) {
    const stage=document.querySelector("#continuity-sculpture");
    if(!stage || !data)return;
    const sculpture=stage.closest(".room-hero");
    const model=graph(data); if(!model.nodes.length)return;
    const canvas=stage.querySelector("canvas"), motion=matchMedia("(prefers-reduced-motion: reduce)");
    const labelLayer=document.createElement("div");labelLayer.className="sculpture-labels";stage.append(labelLayer);
    const controls=[...document.querySelectorAll("[data-sculpture-view]")];
    const toggle=document.querySelector(".sculpture-toggle"), selector=document.querySelector("#sculpture-record");
    let selected=Math.max(0,model.nodes.findIndex(x=>x.id==="ams-thesis")), mode="field";
    let current=layout(model,mode,selected), target=current.map(x=>x.slice());
    let yaw=-.35,pitch=.52,frame=0,previous=0,visible=false,paused=motion.matches,lost=false,drag=null;
    let projected=[], gl=null, paint=()=>{}, active=false, hover=-1, labelSignature="", labelNodes=[];
    selector.replaceChildren(...model.nodes.map((node,i)=>{
      const option=document.createElement("option");option.value=i;option.textContent=`${labels[node.kind]} / ${node.title}`;return option;
    }));
    document.querySelectorAll("[data-research-count]").forEach(el=>el.textContent=String(model.nodes.length).padStart(2,"0"));
    function describe() {
      const node=model.nodes[selected], links=neighbors(model,selected);
      selector.value=selected;
      document.querySelector("#sculpture-ordinal").textContent=`${String(selected+1).padStart(2,"0")} / ${String(model.nodes.length).padStart(2,"0")}`;
      document.querySelector("#sculpture-kind").textContent=labels[node.kind];
      document.querySelector("#sculpture-title").textContent=node.title;
      document.querySelector("#sculpture-summary").textContent=node.summary;
      document.querySelector(".sculpture-source summary").textContent=`{ ${node.key} }`;
      document.querySelector("#sculpture-code").textContent=`{\n  type: "${node.kind}",\n  id: "${node.id}",\n  links: ${links.size},\n  view: "${mode}"\n}`;
      const link=document.querySelector("#sculpture-open");
      link.href=`?${node.kind}=${encodeURIComponent(node.id)}`;link.dataset.route=node.kind;link.dataset.routeId=node.id;
      link.setAttribute("aria-label",`阅读：${node.title}`);
      stage.dataset.view=mode;stage.closest(".room-hero").dataset.view=mode;stage.dataset.selection=node.key;
      controls.forEach(button=>button.setAttribute("aria-pressed",String(button.dataset.sculptureView===mode)));
    }
    function labelsAtPositions() {
      if(!active||lost)return;
      const related=[...neighbors(model,selected)];
      const ids=[...new Set([...(mode==="links"&&related.length<=8?related:[]),...(hover>=0?[hover]:[])])];
      const signature=ids.join(":");
      if(signature!==labelSignature){
        labelSignature=signature;
        labelNodes=ids.map(i=>{
          const button=document.createElement("button");button.type="button";button.dataset.node=String(i);
          button.textContent=model.nodes[i].title;button.setAttribute("aria-label",`选取：${model.nodes[i].title}`);
          button.addEventListener("pointerdown",event=>event.stopPropagation());
          button.addEventListener("click",()=>{choose(i);stage.focus({preventScroll:true});});return button;
        });
        labelLayer.replaceChildren(...labelNodes);
      }
      for(const button of labelNodes){
        const node=projected[Number(button.dataset.node)];if(!node)continue;
        button.style.left=`${node.p[0]}px`;button.style.top=`${node.p[1]+25}px`;
      }
    }
    function moving() { return current.some((p,i)=>p.some((x,j)=>Math.abs(x-target[i][j])>.001)); }
    function animate(now) {
      frame=0;const delta=previous?Math.min(now-previous,40):16;previous=now;
      if(!paused&&!drag)yaw+=delta*.000075;
      const step=motion.matches?1:1-Math.exp(-delta/115);
      current=current.map((p,i)=>p.map((x,j)=>x+(target[i][j]-x)*step));paint();
      if(active&&visible&&!document.hidden&&(!paused||moving()))frame=requestAnimationFrame(animate);
      else previous=0;
    }
    function refresh() {
      if(frame)cancelAnimationFrame(frame);frame=0;previous=0;
      const running=active&&visible&&!document.hidden&&!paused&&!lost;
      stage.dataset.motion=running?"running":"still";
      toggle.setAttribute("aria-pressed",String(paused));toggle.textContent=paused?"旋转 ↻":"静止 Ⅱ";
      if(motion.matches)current=target.map(x=>x.slice());
      paint();
      if(active&&visible&&!document.hidden&&(running||moving()))frame=requestAnimationFrame(animate);
    }
    function choose(index) { selected=(index+model.nodes.length)%model.nodes.length;target=layout(model,mode,selected);describe();refresh(); }
    selector.addEventListener("change",()=>choose(Number(selector.value)));
    document.querySelectorAll("[data-sculpture-step]").forEach(button=>button.addEventListener("click",()=>choose(selected+Number(button.dataset.sculptureStep))));
    controls.forEach(button=>button.addEventListener("click",()=>{mode=button.dataset.sculptureView;target=layout(model,mode,selected);describe();refresh();}));
    document.querySelector("#sculpture-reset").addEventListener("click",()=>{yaw=-.35;pitch=.52;refresh();});
    toggle.addEventListener("click",()=>{paused=!paused;refresh();});
    motion.addEventListener("change",()=>{paused=motion.matches;refresh();});
    document.addEventListener("visibilitychange",refresh);
    describe();
    // The typographic reveals carry no hidden-only information; touch and keyboard expose the same copy.
    if("IntersectionObserver" in window) {
      const reveal=new IntersectionObserver(entries=>entries.forEach(entry=>entry.target.classList.toggle("is-in-view",entry.isIntersecting)),{threshold:.12});
      document.querySelectorAll(".section-heading,.room-changes,.about").forEach(node=>reveal.observe(node));
    }
    sculpture.querySelectorAll("[data-sculpture-control]").forEach(node=>node.hidden=false);
    gl=canvas.getContext("webgl",{alpha:true,antialias:true,powerPreference:"low-power",premultipliedAlpha:false});
    function drawFallback() {
      const svg=stage.querySelector('.sculpture-fallback'),NS='http://www.w3.org/2000/svg';
      svg.replaceChildren();svg.setAttribute('viewBox','0 0 1000 500');
      const poses=layout(model,mode,selected);
      poses.map((pose,i)=>({pose,i,z:rotate(pose,yaw,pitch)[2]})).sort((a,b)=>a.z-b.z).forEach(({pose,i})=>{
        const path=document.createElementNS(NS,'path');
        path.setAttribute('d',Array.from({length:65},(_,j)=>{const p=project(ribbonPoint(pose,j/64*Math.PI*2),yaw,pitch,1000,500);return `${j?'L':'M'}${p[0].toFixed(2)},${p[1].toFixed(2)}`;}).join(' ')+'Z');
        path.setAttribute('fill','none');path.setAttribute('stroke',i===selected?'#a9550f':'#718a91');path.setAttribute('stroke-width',i===selected?'3':'1');path.setAttribute('opacity',String(pose[6]));svg.append(path);
      });
    }
    function fallback() {active=false;lost=true;drag=null;stage.classList.remove("is-dragging");labelLayer.replaceChildren();stage.dataset.renderer="fallback";stage.removeAttribute("tabindex");stage.setAttribute("role","img");stage.setAttribute("aria-label","公开研究的环形视图");controls.forEach(button=>button.disabled=true);toggle.hidden=true;document.querySelector("#sculpture-reset").hidden=true;paint=drawFallback;refresh();}
    drawFallback();
    if(!gl){fallback();return;}
    const vertex=`attribute vec3 position;attribute vec3 normal;attribute vec4 color;
      uniform float yaw;uniform float pitch;uniform float aspect;uniform float fit;uniform float focal;varying vec3 n;varying vec3 p;varying vec4 c;
      mat3 ry(float a){float c=cos(a),s=sin(a);return mat3(c,0.,-s,0.,1.,0.,s,0.,c);}
      mat3 rx(float a){float c=cos(a),s=sin(a);return mat3(1.,0.,0.,0.,c,s,0.,-s,c);}
      void main(){mat3 r=rx(pitch)*ry(yaw);p=r*position;n=r*normal;c=color;float z=7.-p.z;gl_Position=vec4(p.x*1.28*focal*fit/aspect,p.y*focal*fit,.9*z-.2,z);}`;
    const fragment=`precision mediump float;varying vec3 n;varying vec3 p;varying vec4 c;uniform float wire;
      void main(){vec3 nn=normalize(n);if(!gl_FrontFacing)nn=-nn;float light=.55+.45*abs(dot(nn,normalize(vec3(-2.,5.,4.))));
      float rim=pow(1.-abs(dot(nn,normalize(vec3(0.,0.,7.)-p))),3.);vec3 base=c.rgb*light+rim*.18;
      gl_FragColor=vec4(mix(base,c.rgb,wire),c.a);}`;
    function shader(type,source){const s=gl.createShader(type);gl.shaderSource(s,source);gl.compileShader(s);return gl.getShaderParameter(s,gl.COMPILE_STATUS)?s:null;}
    const vs=shader(gl.VERTEX_SHADER,vertex),fs=shader(gl.FRAGMENT_SHADER,fragment);if(!vs||!fs){fallback();return;}
    const program=gl.createProgram();gl.attachShader(program,vs);gl.attachShader(program,fs);gl.linkProgram(program);gl.deleteShader(vs);gl.deleteShader(fs);
    if(!gl.getProgramParameter(program,gl.LINK_STATUS)){fallback();return;}gl.useProgram(program);
    const buffer=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,buffer);
    for(const [name,size,offset] of [["position",3,0],["normal",3,12],["color",4,24]]){const loc=gl.getAttribLocation(program,name);gl.enableVertexAttribArray(loc);gl.vertexAttribPointer(loc,size,gl.FLOAT,false,40,offset);}
    const uniforms=Object.fromEntries(["yaw","pitch","aspect","fit","focal","wire"].map(name=>[name,gl.getUniformLocation(program,name)]));
    gl.enable(gl.BLEND);gl.blendFunc(gl.SRC_ALPHA,gl.ONE_MINUS_SRC_ALPHA);gl.enable(gl.DEPTH_TEST);gl.clearColor(0,0,0,0);
    paint=()=>{
      if(!active||lost)return;
      const box=stage.getBoundingClientRect();if(!box.width||!box.height)return;
      const ratio=Math.min(devicePixelRatio||1,1.6,1400/box.width),width=Math.round(box.width*ratio),height=Math.round(box.height*ratio);
      if(canvas.width!==width||canvas.height!==height){canvas.width=width;canvas.height=height;gl.viewport(0,0,width,height);}
      const faces=[],lines=[]; projected=[];
      function vertexAt(pose,angle,side){
        return [ribbonPoint(pose,angle,side),rotate([Math.cos(angle),Math.sin(angle),0],pose[5],pose[4])];
      }
      function push(dest,point,color){dest.push(...point[0],...point[1],...color);}
      current.forEach((pose,i)=>{
        const selectedNow=i===selected, alpha=pose[6], shade=.47+(i%4)*.035;
        const color=selectedNow?[.73,.37,.09,1]:[shade,shade+.12,shade+.16,alpha*.88];
        const line=selectedNow?[.65,.30,.045,1]:[.38,.49,.53,alpha*.55];
        const curve=[],quads=[];
        for(let segment=0;segment<64;segment++){
          const a=segment/64*Math.PI*2,b=(segment+1)/64*Math.PI*2;
          const p0=vertexAt(pose,a,-1),p1=vertexAt(pose,b,-1),p2=vertexAt(pose,a,1),p3=vertexAt(pose,b,1);
          [p0,p1,p2,p2,p1,p3].forEach(p=>push(faces,p,color));
          [p0,p1,p2,p3].forEach(p=>push(lines,p,line));
          curve.push(project(ribbonPoint(pose,a),yaw,pitch,box.width,box.height));
          quads.push([p0,p1,p2,p3].map(p=>project(p[0],yaw,pitch,box.width,box.height)));
        }
        projected.push({i,p:project(pose,yaw,pitch,box.width,box.height),curve,quads});
      });
      if(mode==="links")for(const edge of model.edges.filter(edge=>edge.includes(selected))){
        edge.forEach(i=>push(lines,[[current[i][0],current[i][1],current[i][2]],[0,1,0]],[.78,.65,.43,.70]));
      }
      gl.uniform1f(uniforms.yaw,yaw);gl.uniform1f(uniforms.pitch,pitch);gl.uniform1f(uniforms.aspect,width/height);
      gl.uniform1f(uniforms.fit,Math.min(1,width*.55/height));
      gl.uniform1f(uniforms.focal,focalLength(pitch));
      gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT);gl.uniform1f(uniforms.wire,0);
      gl.bufferData(gl.ARRAY_BUFFER,new Float32Array(faces),gl.DYNAMIC_DRAW);gl.drawArrays(gl.TRIANGLES,0,faces.length/10);
      gl.uniform1f(uniforms.wire,1);gl.depthMask(false);
      gl.bufferData(gl.ARRAY_BUFFER,new Float32Array(lines),gl.DYNAMIC_DRAW);gl.drawArrays(gl.LINES,0,lines.length/10);gl.depthMask(true);
      stage.dataset.pose=`${yaw.toFixed(3)},${pitch.toFixed(3)}`;
      labelsAtPositions();
    };
    stage.addEventListener("pointerdown",event=>{
      if(event.button!==0||!active||drag)return;drag={id:event.pointerId,x:event.clientX,y:event.clientY,yaw,pitch,distance:0};stage.setPointerCapture(event.pointerId);stage.classList.add("is-dragging");
    });
    stage.addEventListener("pointermove",event=>{
      if(!active)return;
      if(!drag){
        const rect=stage.getBoundingClientRect(),x=event.clientX-rect.left,y=event.clientY-rect.top;
        const closest=pickObject(projected,x,y);
        const next=closest?.d<12?closest.i:-1;if(next!==hover){hover=next;labelsAtPositions();}return;
      }
      if(event.pointerId!==drag.id)return;
      const dx=event.clientX-drag.x,dy=event.clientY-drag.y;drag.distance=Math.max(drag.distance,Math.hypot(dx,dy));
      yaw=drag.yaw+dx*.007;pitch=Math.max(-1.2,Math.min(1.2,drag.pitch+dy*.005));paint();
    });
    function release(event){
      if(!drag||event.pointerId!==drag.id)return;
      if(drag.distance<6&&event.type==="pointerup"){
        const rect=stage.getBoundingClientRect(),x=event.clientX-rect.left,y=event.clientY-rect.top;
        const closest=pickObject(projected,x,y);
        if(closest?.d<22)choose(closest.i);
      }
      if(stage.hasPointerCapture(event.pointerId))stage.releasePointerCapture(event.pointerId);
      drag=null;stage.classList.remove("is-dragging");refresh();
    }
    stage.addEventListener("pointerup",release);stage.addEventListener("pointercancel",release);
    stage.addEventListener("pointerleave",()=>{hover=-1;labelsAtPositions();});
    stage.addEventListener("keydown",event=>{
      if(event.target!==stage||!active)return;
      const keys={ArrowLeft:[-.14,0],ArrowRight:[.14,0],ArrowUp:[0,-.12],ArrowDown:[0,.12]};
      if(keys[event.key]){event.preventDefault();yaw+=keys[event.key][0];pitch=Math.max(-1.2,Math.min(1.2,pitch+keys[event.key][1]));paint();}
      if(event.key==="Enter"){event.preventDefault();choose(selected+1);}
    });
    canvas.addEventListener("webglcontextlost",event=>{event.preventDefault();fallback();});
    new ResizeObserver(()=>paint()).observe(stage);
    new IntersectionObserver(entries=>{visible=entries[0].isIntersecting;refresh();},{threshold:.05}).observe(stage);
    active=true;stage.dataset.renderer="webgl";refresh();
  }
  return {graph,neighbors,layout,ribbonPoint,rotate,project,pickObject,mount};
});
