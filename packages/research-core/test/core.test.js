import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import {CONTENT_FIELDS,contentFieldsFor} from "../canonical.js";
import {collection,objectFor,packet,packetFromShards,packetShardPath,referenceGraph} from "../index.js";

const ROOT = path.resolve(import.meta.dirname, "../../..");
const manifest = JSON.parse(fs.readFileSync(path.join(ROOT, "data/public-corpus.manifest.json"), "utf8"));
const compatibility = JSON.parse(fs.readFileSync(path.join(ROOT, "data/materials.json"), "utf8"));
const expectedCount = ["studies","materials","questions","findings"].reduce((total,field)=>total+compatibility[field].length,0);

test("manifest remains metadata-only and packet paths are explicit", () => {
  assert.equal(manifest.schema, "ams-public-corpus-manifest/1");
  assert.equal(manifest.objects.length, expectedCount);
  assert.ok(manifest.objects.every(item => !Object.hasOwn(item, "packet")));
  for (const item of manifest.objects) {
    assert.ok(fs.statSync(path.join(ROOT, item.packet_v2)).isFile());
    assert.ok(fs.statSync(path.join(ROOT, item.shard)).isFile());
    assert.ok(fs.statSync(path.join(ROOT, item.revision_shard)).isFile());
  }
});

test("reader resolves alias to packet without guessing id prefixes", () => {
  const object = objectFor(manifest, "material", "a-tma-state-aware-memory");
  assert.equal(object.public_id, "a-tma-state-aware-memory");
  assert.equal(object.kind, "source_note");
  assert.equal(packetShardPath(manifest, "material", "a-tma-state-aware-memory"), object.packet_v2);
  const loaded = JSON.parse(fs.readFileSync(path.join(ROOT, object.packet_v2), "utf8"));
  assert.equal(packet(manifest, "material", "a-tma-state-aware-memory", loaded).schema, "ams-study-packet/2");
  assert.equal(packetFromShards(manifest, "material", "a-tma-state-aware-memory", {[object.packet_v2]: loaded}).id, object.public_id);
  assert.throws(() => packet(manifest, "material", "a-tma-state-aware-memory"), /load packetShardPath/);
});

test("graph follows references and not navigation membership", () => {
  const graph = referenceGraph(manifest);
  assert.equal(graph.nodes.length, expectedCount);
  assert.ok(graph.references.length > 0);
  assert.ok(manifest.graphs.navigation_memberships.length > 0);
  assert.ok(graph.references.every(ref => ref.relation !== "navigation"));
});

test("collection consumes only explicitly loaded public packets", () => {
  const refs = [{kind:"material",id:"a-tma-state-aware-memory"},{kind:"study",id:"retrieval-and-relevance"}];
  const loaded = Object.fromEntries(refs.map(ref => {
    const item = objectFor(manifest, ref.kind, ref.id);
    return [item.packet_v2, JSON.parse(fs.readFileSync(path.join(ROOT, item.packet_v2), "utf8"))];
  }));
  const result = collection(manifest, refs, loaded);
  assert.equal(result.schema, "ams-study-collection/2");
  assert.deepEqual(result.objects.map(item => item.id), refs.map(ref => ref.id));
});

test("unknown records cannot infer canonical digest fields", () => {
  assert.throws(() => contentFieldsFor({kind:"unknown",title:"x"}), /unsupported kind/);
  const fields = contentFieldsFor({kind:"thread",title:"",byline:"x",status:"open",payload:{}});
  assert.deepEqual(fields, ["byline","payload","status","title"]);
  assert.deepEqual(fields, CONTENT_FIELDS.thread);
});
