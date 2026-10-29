#!/usr/bin/env node
// Node prerender and browser hydration share the same React tree. No browser
// process, local database, account, or network request is part of this build.
import "./compile-contracts.mjs";
import {build} from "esbuild";
import {readFile,writeFile,mkdir,copyFile,access} from "node:fs/promises";
import path from "node:path";
import {fileURLToPath,pathToFileURL} from "node:url";
import {execFileSync} from "node:child_process";
import {createRequire} from "node:module";

const here=path.dirname(fileURLToPath(import.meta.url)),root=path.resolve(here,"../.."),require=createRequire(import.meta.url);
const seo=require(path.join(root,"assets/seo.js")),search=require(path.join(root,"assets/reading-search.js")),researchMap=require(path.join(root,"assets/research-map.js"));
const studyPackets=require(path.join(root,"assets/study-packets.js"));
const siteConfig=JSON.parse(await readFile(path.join(here,"site-config.json"),"utf8"));
const args=process.argv.slice(2),arg=(name,defaultValue)=>{const i=args.indexOf(name);return i<0?defaultValue:args[i+1];};
const output=path.resolve(root,arg("--output","dist/site")),base=arg("--base","/");
if(!base.startsWith("/")||!base.endsWith("/")||base.includes(".."))throw new Error("--base must be an absolute path ending in /");
try{await access(output);throw new Error("Output already exists; select a fresh directory to preserve artifacts.");}catch(error){if(error.code!=="ENOENT")throw error;}
const script=await readFile(path.join(root,"assets/materials-data.js"),"utf8");
if(!script.startsWith("window.READING_ROOM = ")||!script.trimEnd().endsWith(";"))throw new Error("Unknown generated reader projection");
const data=JSON.parse(script.slice("window.READING_ROOM = ".length).trimEnd().slice(0,-1));
let manifest=null;try{manifest=JSON.parse(await readFile(path.join(root,"data/public-corpus.manifest.json"),"utf8"));}catch(error){if(error.code!=="ENOENT")throw error;}
const collections={material:"materials",study:"studies",question:"questions",finding:"findings"};
const all=Object.entries(collections).flatMap(([kind,field])=>data[field].map(item=>({kind,item})));
const catalogue=all.map(({kind,item})=>({kind,id:item.id,title:item.title,intro:item.intro||item.question||item.claim||"",byline:item.byline||item.shortAuthor||"",date:item.date||item.updated||String(item.year||""),
  categories:item.categories||[],failureSurfaces:item.failureSurfaces||[],domains:data.room.domains.filter(d=>(d[kind+"Ids"]||[]).includes(item.id)||(item.domains||[]).includes(d.id)).map(d=>d.id),
  directions:data.room.directions.filter(d=>(d[kind+"Ids"]||[]).includes(item.id)||(item.directionIds||[]).includes(d.id)).map(d=>d.id),
  noteDepth:item.noteDepth,materialIds:kind==="material"?[item.id]:item.materialIds||item.readings?.map(r=>r.materialId)||[],shard:`reader-data/${kind}/${item.id}.json`,packet:`${kind}/${item.id}/index.json`,
  ref:(()=>{const obj=manifest?.objects.find(r=>r.public_kind===kind&&(r.public_id===item.id||r.id===item.id));return obj?{kind:obj.kind,id:obj.id,revision:obj.revision}:undefined;})(),exercise:item.exercise}));
await mkdir(path.join(output,"assets"),{recursive:true});await mkdir(path.join(here,".build"),{recursive:true});
await build({entryPoints:[path.join(here,"src/server.tsx")],outfile:path.join(here,".build/server.mjs"),bundle:true,platform:"node",format:"esm",packages:"external",banner:{js:'import {createRequire as _createRequire} from "node:module"; const require=_createRequire(import.meta.url);'},logLevel:"warning"});
const browserBuild=await build({entryPoints:[path.join(here,"src/client.tsx")],outdir:path.join(output,"assets"),entryNames:"reader-[hash]",metafile:true,bundle:true,platform:"browser",format:"iife",target:["es2022"],minify:true,loader:{".woff2":"file"},assetNames:"fonts/[name]-[hash]",define:{"process.env.NODE_ENV":'"production"'},logLevel:"warning"});
const browserJS=path.basename(Object.keys(browserBuild.metafile.outputs).find(file=>file.endsWith(".js"))),browserCSS=path.basename(Object.keys(browserBuild.metafile.outputs).find(file=>file.endsWith(".css")));
const {render}=await import(pathToFileURL(path.join(here,".build/server.mjs")).href+"?v="+Date.now());
const safeJSON=value=>JSON.stringify(value).replaceAll("<","\\u003c").replaceAll("\u2028","\\u2028").replaceAll("\u2029","\\u2029");
const escape=value=>String(value).replaceAll("&","&amp;").replaceAll('"',"&quot;").replaceAll("<","&lt;").replaceAll(">","&gt;");
function content(item,contentBase=base){
  const out=structuredClone(item);
  if(data.materials.some(m=>m.id===item.id))out.studyConnections=data.studies.flatMap(study=>(study.readings||[]).filter(reading=>reading.materialId===item.id).map(reading=>({id:study.id,title:study.title,takeaway:reading.takeaway,limit:reading.limit,locator:reading.locator})));
  const normalizeLinks=value=>{if(!value||typeof value!=="object")return;for(const [key,part] of Object.entries(value)){if(typeof part==="string"&&/(?:^url$|Url$)/.test(key)&&part&&!/^(?:[a-z]+:|#|\/)/i.test(part))value[key]=contentBase+part;else if(typeof part==="object")normalizeLinks(part);}};
  normalizeLinks(out);
  if(out.bodyHtml){let i=0;out.bodyHtml=out.bodyHtml.replace(/^<h1\b[^>]*>[\s\S]*?<\/h1>\s*/,"").replace(/<h2(?:\s[^>]*)?>/g,()=>`<h2 id="section-${++i}">`).replace(/<table>/g,'<div class="table-scroll" tabindex="0" role="region" aria-label="内容对照表，可横向滚动"><table>').replace(/<\/table>/g,"</table></div>");
    out.bodyHtml=out.bodyHtml.replace(/href="(?![a-z]+:|#|\/)([^"]*)"/gi,(_,href)=>`href="${escape(contentBase+href)}"`);}
  return out;
}
function html(boot,route,offlineBody=""){const metadata=seo.metadata(data,route);return `<!doctype html>\n<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="google-site-verification" content="${escape(siteConfig.verification)}"><title>${escape(metadata.title)}</title><meta name="description" content="${escape(metadata.description)}"><link rel="canonical" href="${escape(metadata.canonical)}"><meta property="og:title" content="${escape(metadata.title)}"><meta property="og:description" content="${escape(metadata.description)}"><meta property="og:image" content="${escape(metadata.image)}"><link rel="manifest" href="${boot.base}site.webmanifest">${siteConfig.icons.map(file=>`<link rel="${file.includes("apple-touch")?"apple-touch-icon":"icon"}" href="${boot.base+file}">`).join("")}<link rel="stylesheet" href="${boot.base}assets/${browserCSS}"><script type="application/ld+json">${safeJSON(metadata.structured)}</script></head><body><noscript><style>button,input,select,textarea,[data-interactive]{display:none!important}.offline-book .reader-toc{display:none}.offline-book .reader-layout{display:block}.offline-book article{max-width:800px;margin:4rem auto;padding:1rem}</style><p class="margin-note">正文、引用与研究包无需 JavaScript；案头、搜索与演算交互需要启用 JavaScript。</p></noscript><div id="root">${render(boot)}</div>${offlineBody}<script>window.__AMS_BOOTSTRAP__=${safeJSON(boot)};</script><script defer src="${boot.base}assets/${browserJS}"></script></body></html>`;}
const graph=researchMap.referenceGraph(data);
const graphIndex={nodes:graph.nodes.map(({item,...node})=>node),references:graph.references,edges:researchMap.graph(data).edges};
const recordIndex={},portableRecords={};
for(const relative of manifest.record_shards){const value=JSON.parse(await readFile(path.join(root,relative),"utf8"));recordIndex[value.revision]=relative;portableRecords[value.revision]=value;const destination=path.join(output,relative);await mkdir(path.dirname(destination),{recursive:true});await copyFile(path.join(root,relative),destination);}
const common={recordIndex,schema:"ams-reader/1",base,portable:false,catalogue,room:data.room,atlas:data.atlas,graph:graphIndex};
await mkdir(path.join(output,"reader-data"),{recursive:true});
const searchIndex=search.buildIndex(data).map(({item,facets,...entry})=>({...entry,item:{id:item.id,title:item.title},facets:facets.map(({categories,failureSurfaces,noteDepth})=>({categories,failureSurfaces,noteDepth}))}));
await writeFile(path.join(output,"reader-data/search.json"),JSON.stringify(searchIndex));
const packets={};
const routes=[{route:{},directory:"",initial:null},...all.map(({kind,item})=>({route:{[kind]:item.id},directory:seo.pathFor({[kind]:item.id}),initial:{kind,item:content(item)}}))];
for(const {route,directory,initial} of routes){
  const destination=path.join(output,directory,"index.html");await mkdir(path.dirname(destination),{recursive:true});
  const boot={...common,initial,location:"/"+directory};
  await writeFile(destination,html(boot,route));
  if(initial){const shard=path.join(output,`reader-data/${initial.kind}/${initial.item.id}.json`);await mkdir(path.dirname(shard),{recursive:true});await writeFile(shard,JSON.stringify(initial.item));
    const entry=manifest.objects.find(o=>o.public_kind===initial.kind&&o.public_id===initial.item.id),packet=JSON.parse(await readFile(path.join(root,entry.packet_v2),"utf8"));packets[initial.kind+"/"+initial.item.id]=packet;
    await writeFile(path.join(output,directory,"index.json"),JSON.stringify(packet));await writeFile(path.join(output,directory,"index.md"),studyPackets.markdown(packet));}
}
// Public file allowlist. Runtime data roots and the checkout as a whole are
// never inputs. Tracked source/evidence remains downloadable as before.
const tracked=execFileSync("git",["ls-files","-z","assets/fonts","assets/icons","research","docs"],{cwd:root,encoding:"utf8"}).split("\0").filter(Boolean);
const files=new Set([...tracked,"agent-memory-study.rdf","NOTICE.md","THIRD_PARTY_NOTICES.md","site.webmanifest","publications/agent-memory-study-project-introduction.zh-CN.pdf",...data.materials.filter(m=>m.pdf.delivery==="bundled").map(m=>m.pdf.url),...data.studies.map(s=>s.sourcePath)]);
// Explicit additions under development are public source, not arbitrary
// untracked files. Once committed these simply coincide with the tracked set.
for(const [directory,names] of Object.entries({
  "research/observation-contract-study":["README.md","adapter.py","fixtures.json","protocol.md","results.json","study.py","test_study.py"],
  "research/conditional-contribution-study":["README.md","adapter.py","corpus.json","observation-chain.json","protocol.md","provider-plan.json","provider.py","sample-results.json","study.py","test_study.py"]
})){for(const name of names)files.add(directory+"/"+name);}
files.add("assets/fonts/notosanssc-OFL.txt");
for(const file of ["docs/intake.md","docs/execution.md","docs/revision-publication.md","docs/local-workspace.md","docs/current-state.md","docs/acceptance.md"])files.add(file);
for(const relative of files){const source=path.resolve(root,relative);if(!source.startsWith(root+path.sep))throw new Error("Public asset escaped source root");const destination=path.join(output,relative);await mkdir(path.dirname(destination),{recursive:true});await copyFile(source,destination);}
await writeFile(path.join(output,".nojekyll"),"");
await mkdir(path.join(output,"portable"),{recursive:true});
const portableContent=Object.fromEntries(all.map(({kind,item})=>[kind+"/"+item.id,content(item,"../")]));
const portableBoot={...common,base:"../",portable:true,location:"/",initial:null,portableContent,portableRecords,portablePackets:packets,searchIndex};
// The file reader mounts a HashRouter; it does not hydrate a different URL
// representation. With JS disabled the same React body tree supplies all texts.
const offlineLinks=(html,kind,id)=>html.replace(/id="([^"]+)"/g,(_,anchor)=>`id="offline-${kind}-${id}-${anchor}"`).replace(/href="([^"]+)"/g,(_,href)=>{if(href.startsWith("#"))return `href="#offline-${kind}-${id}-${href.slice(1)}"`;const url=new URL(href.replaceAll("&amp;","&"),"https://ams.invalid/portable/index.html"),found=catalogue.find(row=>url.searchParams.get(row.kind)===row.id||url.pathname.endsWith(`/${row.kind}/${row.id}/`));return `href="${found?"#offline-"+found.kind+"-"+found.id+(url.hash?"-"+url.hash.slice(1):""):href}"`;});
const offlineBody='<noscript><div class="offline-book">'+all.map(({kind,item})=>`<section id="offline-${kind}-${item.id}">${offlineLinks(render({...portableBoot,location:`/?${kind}=${item.id}`,initial:{kind,item:portableContent[kind+"/"+item.id]}},true),kind,item.id)}</section>`).join("")+'</div></noscript>';
await writeFile(path.join(output,"portable/index.html"),html(portableBoot,{},offlineBody).replace(/<div id="root">([\s\S]*?)<\/div><noscript><div class="offline-book">/,(_,home)=>`<div id="root">${offlineLinks(home,"home","index")}</div><noscript><div class="offline-book">`));
await writeFile(path.join(output,"sitemap.xml"),'<?xml version="1.0" encoding="utf-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'+routes.map(({route})=>`<url><loc>${escape(seo.metadata(data,route).canonical)}</loc></url>`).join("")+"</urlset>");
await writeFile(path.join(output,"404.html"),`<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>页面不存在 · Agent Memory Study</title><meta name="robots" content="noindex"><link rel="stylesheet" href="${base}assets/${browserCSS}"><main class="empty-state"><h1>这里没有这篇内容。</h1><p><a href="${base}">回到探索 →</a></p></main></html>`);
await writeFile(path.join(output,"build-receipt.json"),JSON.stringify({schema:"ams-reader-build/1",renderer:"React shared server/client tree",routes:routes.map(r=>"/"+r.directory),objects:all.length,base,portable:"portable/index.html",materials:data.materials.length,bundled:data.materials.filter(m=>m.pdf.delivery==="bundled").length,official:data.materials.filter(m=>m.pdf.delivery==="official").length},null,2));
console.log(`Built ${routes.length} shared-tree reading pages + 404; ${all.length} on-demand bodies. ${output}`);
