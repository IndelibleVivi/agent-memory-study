#!/usr/bin/env node
/* Local stdio bridge for author.py. Input is synthetic or explicit private JSON;
   results only go back to the caller and are never written by this process. */
"use strict";

const fs = require("node:fs");
const researchMap = require("../assets/research-map.js");
const studyPackets = require("../assets/study-packets.js");
const studyDesk = require("../assets/study-desk.js");

const MAX_INPUT = 2 * 1024 * 1024;
const MAX_DATA = 16 * 1024 * 1024;

function fail(message) {
  process.stdout.write(JSON.stringify({error: message}) + "\n");
  process.exitCode = 1;
}

function parseText(text, limit, name) {
  if (Buffer.byteLength(text, "utf8") > limit) throw new Error(`${name} exceeds ${limit} bytes`);
  try {
    return JSON.parse(text);
  } catch {
    throw new Error(`${name} is not valid JSON`);
  }
}

function pathIsAbsolute(value) {
  return value.startsWith("/") && !value.includes("\0");
}
function revisionStatus(ref, data) {
  const {status, fields} = studyDesk.revision(ref, data);
  return {status, fields};
}

let text = "";
process.stdin.setEncoding("utf8");
process.stdin.on("data", chunk => {
  text += chunk;
  if (Buffer.byteLength(text, "utf8") > MAX_INPUT + 1024) {
    fail(`bridge input exceeds ${MAX_INPUT} bytes`);
    process.stdin.destroy();
  }
});
process.stdin.on("end", () => {
  if (process.exitCode) return;
  try {
    const input = parseText(text, MAX_INPUT, "bridge input");
    if (!input || typeof input !== "object" || Array.isArray(input)) {
      throw new Error("bridge input must be an object");
    }
    let result;
    if (input.command === "impact") {
      if (typeof input.dataFile !== "string" || !pathIsAbsolute(input.dataFile)) {
        throw new Error("impact requires an absolute dataFile prepared by the author CLI");
      }
      const data = parseText(fs.readFileSync(input.dataFile, "utf8"), MAX_DATA, "compiled data");
      const referenceGraph = researchMap.referenceGraph(data);
      result = {...researchMap.impact(data, input.kind, input.id),
        references: referenceGraph.references, nodes: referenceGraph.nodes.map(({key, kind, id, title}) => ({key, kind, id, title}))};
    } else if (input.command === "workspace") {
      if (typeof input.workspaceFile !== "string" || typeof input.dataFile !== "string" ||
          !pathIsAbsolute(input.dataFile)) {
        throw new Error("workspace requires a workspaceFile and an absolute dataFile");
      }
      if (!pathIsAbsolute(input.workspaceFile)) {
        throw new Error("workspace requires an absolute workspaceFile");
      }
      if (fs.statSync(input.workspaceFile).size > MAX_INPUT) throw new Error("案头文件过大，限 2 MiB。");
      const workspaceText = fs.readFileSync(input.workspaceFile, "utf8");
      const data = parseText(fs.readFileSync(input.dataFile, "utf8"), MAX_DATA, "compiled data");
      const workspace = studyDesk.parseWorkspace(workspaceText, data);
      const urls = {}, revisions = {};
      for (const ref of workspace.items) {
        const key = studyDesk.key(ref);
        urls[key] = studyPackets.publicUrl(ref.kind, ref.id);
        revisions[key] = {
          object: revisionStatus(ref, data),
          excerpts: Object.fromEntries(ref.excerpts.map(part =>
            [part.id, revisionStatus({...ref, basis: part.basis}, data)])),
        };
      }
      result = {workspace, urls, revisions};
    } else {
      throw new Error(`unsupported bridge command: ${String(input.command)}`);
    }
    process.stdout.write(JSON.stringify({result}) + "\n");
  } catch (error) {
    fail(error instanceof Error ? error.message : String(error));
  }
});
