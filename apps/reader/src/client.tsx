import React from "react";
import {hydrateRoot,createRoot} from "react-dom/client";
import {BrowserRouter,HashRouter} from "react-router";
import {App} from "./App";
import "./style.css";
import siteConfig from "../site-config.json";

const data=window.__AMS_BOOTSTRAP__;
if(data.portable){
  if(!location.hash&&location.search)location.hash="/"+location.search;
  createRoot(document.getElementById("root")!).render(<HashRouter><App bootstrap={data}/></HashRouter>);
}else hydrateRoot(document.getElementById("root")!,<BrowserRouter basename={data.base}><App bootstrap={data}/></BrowserRouter>);
document.documentElement.classList.add("interactive");
// Retain only the already-approved public aggregate beacon. Local/file previews
// never load it; there are no custom events or private data in this request.
if(!data.portable&&!document.getElementById("ams-local-bootstrap")&&location.hostname===siteConfig.analytics.host){const script=document.createElement("script");script.src=siteConfig.analytics.source;script.defer=true;script.dataset.cfBeacon=JSON.stringify({token:siteConfig.analytics.token});document.head.append(script);}
