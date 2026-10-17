/* A closed, half-twisted ribbon. Decorative geometry, not a research diagram. */
(() => {
  "use strict";
  const stage = document.querySelector("#continuity-sculpture");
  if (!stage) return;
  const canvas = stage.querySelector("canvas");
  const button = document.querySelector(".sculpture-toggle");
  const motion = matchMedia("(prefers-reduced-motion: reduce)");
  const gl = canvas.getContext("webgl", {alpha:true, antialias:true, powerPreference:"low-power", premultipliedAlpha:false});
  if (!gl) { stage.dataset.renderer = "fallback"; return; }
  const vertex = `
    attribute vec3 position; attribute vec3 normal;
    uniform float turn; uniform float aspect;
    varying vec3 world; varying vec3 surface;
    mat3 rx(float a){float c=cos(a),s=sin(a);return mat3(1.,0.,0.,0.,c,s,0.,-s,c);}
    mat3 ry(float a){float c=cos(a),s=sin(a);return mat3(c,0.,-s,0.,1.,0.,s,0.,c);}
    mat3 rz(float a){float c=cos(a),s=sin(a);return mat3(c,s,0.,-s,c,0.,0.,0.,1.);}
    void main(){
      mat3 pose=rz(-.42)*rx(.80+.09*sin(turn*.7))*ry(turn);
      world=pose*position; surface=pose*normal;
      float z=5.4-world.z; float f=3.2;
      gl_Position=vec4(world.x*f/aspect,world.y*f, .9*z-.2,z);
    }`;
  const fragment = `
    precision mediump float;
    varying vec3 world; varying vec3 surface;
    void main(){
      vec3 n=normalize(surface), view=normalize(vec3(0.,0.,5.4)-world);
      if(dot(n,view)<0.) n=-n;
      vec3 r=reflect(-view,n);
      // Broad studio reflections give the ribbon its brushed silver surface.
      float sky=smoothstep(-.5,.8,r.y);
      vec3 metal=mix(vec3(.16,.23,.20),vec3(.81,.84,.77),sky);
      float strip=exp(-pow((r.y-.31)/.12,2.));
      float dark=exp(-pow((r.x+.25)/.17,2.))*.34;
      metal += vec3(.34,.35,.28)*strip;
      metal *= 1.-dark;
      float soft=max(dot(n,normalize(vec3(-3.,5.,5.))),0.);
      metal *= .56+.44*soft;
      float edge=pow(1.-max(dot(n,view),0.),3.);
      metal=mix(metal,vec3(.94,.95,.89),edge*.62);
      float grain=sin(world.y*180.+world.x*12.)*.002;
      metal+=grain;
      gl_FragColor=vec4(pow(max(metal,vec3(0.)),vec3(.87)),1.);
    }`;
  function shader(type, source) {
    const item=gl.createShader(type); gl.shaderSource(item,source); gl.compileShader(item);
    if (!gl.getShaderParameter(item,gl.COMPILE_STATUS)) { gl.deleteShader(item); return null; }
    return item;
  }
  const vs=shader(gl.VERTEX_SHADER,vertex), fs=shader(gl.FRAGMENT_SHADER,fragment);
  if (!vs || !fs) { stage.dataset.renderer="fallback"; return; }
  const program=gl.createProgram();gl.attachShader(program,vs);gl.attachShader(program,fs);gl.linkProgram(program);
  gl.deleteShader(vs);gl.deleteShader(fs);
  if(!gl.getProgramParameter(program,gl.LINK_STATUS)){stage.dataset.renderer="fallback";return;}
  gl.useProgram(program);
  const position=(u,v)=>{
    const a=.43*Math.cos(v),b=.055*Math.sin(v),c=Math.cos(u/2),s=Math.sin(u/2);
    const radial=a*c-b*s,vertical=a*s+b*c;
    return [(1.05+radial)*Math.cos(u),vertical,(1.05+radial)*Math.sin(u)];
  };
  const vertices=[],normals=[],indices=[],U=220,V=36;
  for(let i=0;i<=U;i++) for(let j=0;j<=V;j++){
    const u=i/U*Math.PI*2,v=j/V*Math.PI*2,p=position(u,v),a=position(u+.001,v),b=position(u,v+.001);
    const du=a.map((n,k)=>n-p[k]),dv=b.map((n,k)=>n-p[k]);
    const n=[du[1]*dv[2]-du[2]*dv[1],du[2]*dv[0]-du[0]*dv[2],du[0]*dv[1]-du[1]*dv[0]];
    const len=Math.hypot(...n);vertices.push(...p);normals.push(...n.map(x=>x/len));
    if(i<U&&j<V){const k=i*(V+1)+j;indices.push(k,k+V+1,k+1,k+1,k+V+1,k+V+2);}
  }
  for(const [name,values] of [["position",vertices],["normal",normals]]){
    const buffer=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,buffer);gl.bufferData(gl.ARRAY_BUFFER,new Float32Array(values),gl.STATIC_DRAW);
    const loc=gl.getAttribLocation(program,name);gl.enableVertexAttribArray(loc);gl.vertexAttribPointer(loc,3,gl.FLOAT,false,0,0);
  }
  const buffer=gl.createBuffer();gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER,buffer);gl.bufferData(gl.ELEMENT_ARRAY_BUFFER,new Uint16Array(indices),gl.STATIC_DRAW);
  const turnUniform=gl.getUniformLocation(program,"turn"),aspectUniform=gl.getUniformLocation(program,"aspect");
  gl.enable(gl.DEPTH_TEST);gl.clearColor(0,0,0,0);
  let angle=.42,previous=0,frame=0,visible=false,paused=motion.matches,lost=false;
  function paint(){
    if(lost)return;
    const rect=stage.getBoundingClientRect();if(!rect.width||!rect.height)return;
    const ratio=Math.min(devicePixelRatio||1,1.5,800/rect.width);
    const width=Math.round(rect.width*ratio),height=Math.round(rect.height*ratio);
    if(canvas.width!==width||canvas.height!==height){canvas.width=width;canvas.height=height;gl.viewport(0,0,width,height);}
    gl.uniform1f(turnUniform,angle);gl.uniform1f(aspectUniform,width/height);
    gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT);gl.drawElements(gl.TRIANGLES,indices.length,gl.UNSIGNED_SHORT,0);
  }
  function tick(now){
    frame=0;if(previous)angle+=Math.min(now-previous,60)*.00012;previous=now;paint();
    if(!paused&&visible&&!document.hidden&&!lost)frame=requestAnimationFrame(tick);
  }
  function sync(){
    if(frame)cancelAnimationFrame(frame);frame=0;previous=0;
    const running=!paused&&visible&&!document.hidden&&!lost;
    stage.dataset.motion=running?"running":"still";
    button.setAttribute("aria-pressed",String(paused));
    button.replaceChildren(document.createTextNode(paused?"播放动态 ▷":"暂停动态 Ⅱ"));
    if(running)frame=requestAnimationFrame(tick);else paint();
  }
  button.hidden=false;button.addEventListener("click",()=>{paused=!paused;sync();});
  motion.addEventListener("change",()=>{paused=motion.matches;sync();});
  document.addEventListener("visibilitychange",sync);
  new IntersectionObserver(entries=>{visible=entries[0].isIntersecting;sync();},{threshold:.05}).observe(stage);
  new ResizeObserver(()=>paint()).observe(stage);
  canvas.addEventListener("webglcontextlost",event=>{
    event.preventDefault();lost=true;stage.dataset.renderer="fallback";button.hidden=true;sync();
  });
  // A restored context needs its resources rebuilt; the static artwork remains usable.
  stage.dataset.renderer="webgl";sync();
})();
