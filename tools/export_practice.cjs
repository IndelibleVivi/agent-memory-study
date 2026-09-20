#!/usr/bin/env node
/* Machine-readable practice brief exporter.
 *
 * Reads canonical data fresh on each invocation, runs the shared local lexical
 * implementation in assets/practice.js, and prints Markdown or JSON. This is a
 * thin CLI: argument parsing only, no extra framework.
 */
'use strict';

const fs = require('node:fs');
const path = require('node:path');
const Practice = require(path.join(__dirname, '..', 'assets', 'practice.js'));

const DEFAULT_DATA = path.join(__dirname, '..', 'data', 'materials.json');

const USAGE = `Usage:
  node tools/export_practice.cjs --query <text> --format markdown|json [--limit N] [--out PATH]
  node tools/export_practice.cjs --finding <id> --format markdown|json [--out PATH]

Options:
  --query <text>    Natural-language problem query (Chinese or English).
  --finding <id>    Export one finding by canonical id (no ranking).
  --format <fmt>    Required. "markdown" or "json".
  --limit <n>       Max findings for a query brief (default 3).
  --out <path>      Write to a file instead of stdout.
  --data <path>     Override the canonical data file (default data/materials.json).
  --help            Show this help.`;

function parseArgs(argv) {
  const args = {query: null, queryGiven: false, finding: null, format: null, limit: 3,
    out: null, data: DEFAULT_DATA, help: false};
  for (let i = 0; i < argv.length; i += 1) {
    const flag = argv[i];
    const value = argv[i + 1];
    switch (flag) {
      case '--help':
      case '-h':
        args.help = true;
        break;
      case '--finding':
      case '--format':
      case '--limit':
      case '--out':
      case '--data':
        if (value === undefined || value.startsWith('--')) {
          throw new Error(`Missing value for ${flag}.\n\n${USAGE}`);
        }
        args[flag.slice(2)] = value;
        i += 1;
        break;
      case '--query':
        if (value === undefined || value.startsWith('--')) {
          throw new Error(`Missing value for ${flag}.\n\n${USAGE}`);
        }
        args.query = value;
        args.queryGiven = true;
        i += 1;
        break;
      default:
        throw new Error(`Unknown argument: ${flag}\n\n${USAGE}`);
    }
  }
  return args;
}

function readData(dataPath) {
  const resolved = path.resolve(dataPath);
  if (!fs.existsSync(resolved)) {
    throw new Error(`Canonical data not found: ${resolved}`);
  }
  let data;
  try {
    data = JSON.parse(fs.readFileSync(resolved, 'utf8'));
  } catch (error) {
    throw new Error(`Canonical data is not valid JSON (${resolved}): ${error.message}`);
  }
  if (!Array.isArray(data.findings) || !data.findings.length) {
    throw new Error(
      `Canonical data has no findings array; a practice brief needs at least one finding (${resolved}).`
    );
  }
  return data;
}

function main(argv) {
  let args;
  try {
    args = parseArgs(argv);
  } catch (error) {
    process.stderr.write(`${error.message}\n`);
    return 2;
  }
  if (args.help) {
    process.stdout.write(`${USAGE}\n`);
    return 0;
  }
  if (args.finding && args.queryGiven) {
    process.stderr.write(`Choose either --query or --finding, not both.\n\n${USAGE}\n`);
    return 2;
  }
  if (!args.finding && !args.queryGiven) {
    process.stderr.write(`Provide --query or --finding.\n\n${USAGE}\n`);
    return 2;
  }
  if (args.format !== 'markdown' && args.format !== 'json') {
    process.stderr.write(`--format must be "markdown" or "json".\n\n${USAGE}\n`);
    return 2;
  }
  const limit = Number(args.limit);
  if (!Number.isInteger(limit) || limit < 1) {
    process.stderr.write(`--limit must be a positive integer.\n\n${USAGE}\n`);
    return 2;
  }

  let data;
  try {
    data = readData(args.data);
  } catch (error) {
    process.stderr.write(`${error.message}\n`);
    return 1;
  }

  let briefing;
  try {
    briefing = args.finding
      ? Practice.brief(data, '', {findingId: args.finding})
      : Practice.brief(data, args.query, {limit});
  } catch (error) {
    process.stderr.write(`${error.message}\n`);
    return 1;
  }

  const output = args.format === 'json'
    ? JSON.stringify(briefing, null, 2) + '\n'
    : Practice.markdown(briefing);

  if (args.out) {
    fs.writeFileSync(path.resolve(args.out), output, 'utf8');
  } else {
    process.stdout.write(output);
  }
  return 0;
}

if (require.main === module) {
  process.exitCode = main(process.argv.slice(2));
}

module.exports = {main, parseArgs};
