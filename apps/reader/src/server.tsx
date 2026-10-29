import React from "react";
import {renderToString} from "react-dom/server";
import {StaticRouter} from "react-router";
import {App} from "./App";
import type {Bootstrap} from "./types";
export function render(bootstrap:Bootstrap,documentOnly=false) {return renderToString(<StaticRouter basename={bootstrap.portable?undefined:bootstrap.base} location={bootstrap.portable?bootstrap.location:bootstrap.base.replace(/\/$/,"")+bootstrap.location}><App bootstrap={bootstrap} documentOnly={documentOnly}/></StaticRouter>);}
