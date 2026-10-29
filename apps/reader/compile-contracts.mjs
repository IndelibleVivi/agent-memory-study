// Compile the canonical schema once at build time. Imported files cannot supply
// schemas, executable validators, URLs or alternate definitions.
import Ajv2020 from "ajv/dist/2020.js";
import addFormats from "ajv-formats";
import standalone from "ajv/dist/standalone/index.js";
import {readFile,mkdir,writeFile} from "node:fs/promises";
import {fileURLToPath} from "node:url";
const schema=JSON.parse(await readFile(new URL("../../schemas/core.schema.json",import.meta.url),"utf8"));
const ajv=new Ajv2020({strict:false,allErrors:false,code:{source:true,esm:true},validateFormats:true});
addFormats(ajv);ajv.addSchema(schema);
ajv.addSchema({$id:"urn:ams:reader-entity",$ref:schema.$id+"#/$defs/EntityRecord"});
ajv.addSchema({$id:"urn:ams:reader-command",$ref:schema.$id+"#/$defs/Command"});
await mkdir(new URL(".build/",import.meta.url),{recursive:true});
await writeFile(new URL(".build/contracts.js",import.meta.url),standalone(ajv,{validateEntity:"urn:ams:reader-entity",validateCommand:"urn:ams:reader-command"}));
