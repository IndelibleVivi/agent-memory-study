import "./compile-contracts.mjs";
import {build} from "esbuild";
import {execFileSync} from "node:child_process";
await build({entryPoints:["test/desk.test.ts","test/lab.test.ts","test/review.test.ts"],outdir:".build/tests",outExtension:{".js":".cjs"},bundle:true,platform:"node",format:"cjs",logLevel:"warning"});
execFileSync(process.execPath,["--test",".build/tests/desk.test.cjs",".build/tests/lab.test.cjs",".build/tests/review.test.cjs"],{stdio:"inherit"});
