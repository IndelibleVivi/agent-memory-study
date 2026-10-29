#!/usr/bin/env node
/* Export one public source, entry, inquiry, or transfer as a portable packet. */
"use strict";

const fs = require("node:fs");
const path = require("node:path");
const StudyPackets = require(path.join(__dirname, "..", "assets", "study-packets.js"));
const StudyDesk = require(path.join(__dirname, "..", "assets", "study-desk.js"));

const DEFAULT_DATA = path.join(__dirname, "..", "data", "materials.json");
const USAGE = `Usage:
  node tools/export_study.cjs --kind source|entry|inquiry|transfer --id ID --format markdown|json [--out PATH] [--version 1|2]
  node tools/export_study.cjs --select study:ID --select material:ID --format markdown|json [--out PATH] [--version 1|2]
  node tools/export_study.cjs --workspace PATH --format markdown|json [--out PATH] [--version 1|2]

The public route aliases material, study, question, and finding are accepted too.
Packets include current public content and a bounded manifest, not linked full texts.
--workspace exports only the current public selections, never private workspace text.`;

function parseArgs(argv) {
  const args = {kind: null, id: null, select: [], workspace: null, format: null, out: null, data: DEFAULT_DATA, help: false, version: "1"};
  for (let index = 0; index < argv.length; index += 1) {
    const flag = argv[index];
    if (flag === "--help" || flag === "-h") { args.help = true; continue; }
    if (!["--kind", "--id", "--select", "--workspace", "--format", "--out", "--data", "--version"].includes(flag)) throw new Error(`Unknown argument: ${flag}`);
    const value = argv[index + 1];
    if (value === undefined || value.startsWith("--")) throw new Error(`Missing value for ${flag}`);
    if (flag === "--select") args.select.push(value);
    else args[flag.slice(2)] = value;
    index += 1;
  }
  return args;
}

function main(argv) {
  let args;
  try { args = parseArgs(argv); }
  catch (error) { process.stderr.write(`${error.message}\n\n${USAGE}\n`); return 2; }
  if (args.help) { process.stdout.write(`${USAGE}\n`); return 0; }
  const single = Boolean(args.kind || args.id), modeCount = Number(single) + Number(args.select.length > 0) + Number(Boolean(args.workspace));
  if (modeCount !== 1 || (single && (!args.kind || !args.id)) || !args.format) {
    process.stderr.write(`Choose one input: --kind and --id, repeated --select, or --workspace; --format is required.\n\n${USAGE}\n`);
    return 2;
  }
  if (!["markdown", "json"].includes(args.format)) {
    process.stderr.write(`--format must be markdown or json.\n`);
    return 2;
  }
  if (!["1", "2"].includes(args.version)) {process.stderr.write("--version must be 1 or 2.\n");return 2;}
  let data;
  try { data = JSON.parse(fs.readFileSync(path.resolve(args.data), "utf8")); }
  catch (error) { process.stderr.write(`Cannot read public data: ${error.message}\n`); return 1; }
  let output;
  try {
    let bundle;
    if (single) bundle = StudyPackets.packet(data, args.kind, args.id);
    else {
      let refs;
      if (args.workspace) {
        const input = path.resolve(args.workspace);
        if (fs.statSync(input).size > 32*1024*1024) throw new Error("Workspace file exceeds 32 MiB.");
        const text=fs.readFileSync(input,"utf8"), workspace=JSON.parse(text);
        if(workspace.schema==="ams-workspace/3") {
          if(!Array.isArray(workspace.records))throw new Error("Workspace records are missing.");
          refs=workspace.records.filter(r=>r.kind==="session"&&workspace.roots?.some(ref=>ref.kind===r.kind&&ref.id===r.id&&ref.revision===r.revision)).flatMap(r=>r.payload?.items||[]).flatMap(item=>item.public_kind?[{kind:item.public_kind,id:item.public_id}]:item.legacy&&["material","study","question","finding"].includes(item.legacy.kind)?[{kind:item.legacy.kind,id:item.legacy.id}]:[]);
        } else refs=StudyDesk.parseWorkspace(text,data).items;
      } else refs = args.select.map(value => {
        const match = /^([a-z]+):([a-z0-9]+(?:-[a-z0-9]+)*)$/.exec(value);
        if (!match) throw new Error(`Use --select KIND:ID, got: ${value}`);
        return {kind: match[1], id: match[2]};
      });
      bundle = StudyPackets.collection(data, refs);
    }
    if(args.version==="2") {
      if(path.resolve(args.data)!==DEFAULT_DATA)throw new Error("Packet v2 uses the current compiler manifest; custom --data is a v1 compatibility option.");
      const root=path.join(__dirname,".."),manifest=JSON.parse(fs.readFileSync(path.join(root,"data/public-corpus.manifest.json"),"utf8"));
      const upgrade=packet=>{const entry=manifest.objects.find(row=>row.public_kind===packet.kind&&row.public_id===packet.id);if(!entry)throw new Error("Missing compiler packet for "+packet.kind+"/"+packet.id);return JSON.parse(fs.readFileSync(path.join(root,entry.packet_v2),"utf8"));};
      bundle=single?upgrade(bundle):{schema:"ams-study-collection/2",title:"AMS 公开选材包",objects:bundle.objects.map(upgrade),policy:"Selected current public objects only; no private workspace fields or prior snapshots."};
    }
    output = args.format === "json" ? `${JSON.stringify(bundle, null, 2)}\n`
      : single ? StudyPackets.markdown(bundle) : StudyPackets.collectionMarkdown(bundle);
  } catch (error) { process.stderr.write(`${error.message}\n`); return 1; }
  if (args.out) {
    const target = path.resolve(args.out);
    try {fs.writeFileSync(target, output, {encoding: "utf8", flag: "wx"});}
    catch (error) {process.stderr.write(error.code === "EEXIST" ? `Refusing to overwrite ${target}\n` : `${error.message}\n`); return 1;}
  } else process.stdout.write(output);
  return 0;
}

if (require.main === module) process.exitCode = main(process.argv.slice(2));
module.exports = {main, parseArgs};
