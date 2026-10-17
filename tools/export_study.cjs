#!/usr/bin/env node
/* Export one public source, entry, inquiry, or transfer as a portable packet. */
"use strict";

const fs = require("node:fs");
const path = require("node:path");
const StudyPackets = require(path.join(__dirname, "..", "assets", "study-packets.js"));

const DEFAULT_DATA = path.join(__dirname, "..", "data", "materials.json");
const USAGE = `Usage:
  node tools/export_study.cjs --kind source|entry|inquiry|transfer --id ID --format markdown|json [--out PATH]

The public route aliases material, study, question, and finding are accepted too.
Packets include current public content and a bounded manifest, not linked full texts.`;

function parseArgs(argv) {
  const args = {kind: null, id: null, format: null, out: null, data: DEFAULT_DATA, help: false};
  for (let index = 0; index < argv.length; index += 1) {
    const flag = argv[index];
    if (flag === "--help" || flag === "-h") { args.help = true; continue; }
    if (!["--kind", "--id", "--format", "--out", "--data"].includes(flag)) throw new Error(`Unknown argument: ${flag}`);
    const value = argv[index + 1];
    if (value === undefined || value.startsWith("--")) throw new Error(`Missing value for ${flag}`);
    args[flag.slice(2)] = value;
    index += 1;
  }
  return args;
}

function main(argv) {
  let args;
  try { args = parseArgs(argv); }
  catch (error) { process.stderr.write(`${error.message}\n\n${USAGE}\n`); return 2; }
  if (args.help) { process.stdout.write(`${USAGE}\n`); return 0; }
  if (!args.kind || !args.id || !args.format) {
    process.stderr.write(`--kind, --id, and --format are required.\n\n${USAGE}\n`);
    return 2;
  }
  if (!["markdown", "json"].includes(args.format)) {
    process.stderr.write(`--format must be markdown or json.\n`);
    return 2;
  }
  let data;
  try { data = JSON.parse(fs.readFileSync(path.resolve(args.data), "utf8")); }
  catch (error) { process.stderr.write(`Cannot read public data: ${error.message}\n`); return 1; }
  let output;
  try {
    const bundle = StudyPackets.packet(data, args.kind, args.id);
    output = args.format === "json" ? `${JSON.stringify(bundle, null, 2)}\n` : StudyPackets.markdown(bundle);
  } catch (error) { process.stderr.write(`${error.message}\n`); return 1; }
  if (args.out) {
    const target = path.resolve(args.out);
    if (fs.existsSync(target)) { process.stderr.write(`Refusing to overwrite ${target}\n`); return 1; }
    fs.writeFileSync(target, output, "utf8");
  } else process.stdout.write(output);
  return 0;
}

if (require.main === module) process.exitCode = main(process.argv.slice(2));
module.exports = {main, parseArgs};
