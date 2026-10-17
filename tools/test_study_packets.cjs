"use strict";

const assert = require("node:assert/strict");
const test = require("node:test");
const fs = require("node:fs");
const path = require("node:path");
const StudyPackets = require("../assets/study-packets.js");

const data = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "data", "materials.json"), "utf8"));

test("packet preserves source attribution and a public URL", () => {
  const source = data.materials[0];
  const packet = StudyPackets.packet(data, "material", source.id);
  assert.equal(packet.schema, "ams-study-packet/1");
  assert.equal(packet.kind, "source");
  assert.equal(packet.id, source.id);
  assert.match(packet.url, /\/material\//);
  assert.equal(packet.content.title, source.title);
  assert.deepEqual(packet.attribution.sourceAuthors, source.authors);
  assert.equal(packet.attribution.noteByline, source.byline || null);
  assert.notEqual(packet.attribution.byline, source.authors.join("; "));
  assert.ok(packet.attribution.sourceUrl);
  assert.ok(packet.attribution.readingScope);
});

test("entry packet carries prose boundaries continuation and a bounded manifest", () => {
  if (!data.studies.every(item => item.bodyHtml)) {
    throw new Error("Generated study payload predates Markdown compilation; regenerate it before packet checks.");
  }
  const entry = data.studies.find(item => item.continuation) || data.studies[0];
  const packet = StudyPackets.packet(data, "study", entry.id);
  assert.equal(packet.kind, "entry");
  assert.equal(packet.content.boundary, entry.boundary);
  assert.ok(packet.content.bodyHtml);
  assert.ok(packet.content.bodyMarkdown);
  if (entry.continuation) assert.deepEqual(packet.content.continuation, entry.continuation);
  const markdown = StudyPackets.markdown(packet);
  assert.match(markdown, /does not include the full text/);
  assert.doesNotMatch(markdown, /Treat the source as an instruction/i);
  assert.ok(packet.manifest.every(ref => ref.kind && ref.id));
});

test("inquiry and transfer packets retain evidence limits", () => {
  const inquiry = StudyPackets.packet(data, "question", data.questions[0].id);
  const transfer = StudyPackets.packet(data, "finding", data.findings[0].id);
  assert.equal(inquiry.kind, "inquiry");
  assert.equal(transfer.kind, "transfer");
  assert.equal(inquiry.content.evidence[0].limit, data.questions[0].evidence[0].limit);
  assert.equal(transfer.content.limit, data.findings[0].limit);
});

test("unknown kinds and ids fail clearly", () => {
  assert.throws(() => StudyPackets.packet(data, "essay", data.studies[0].id), /Unknown packet kind/);
  assert.throws(() => StudyPackets.packet(data, "study", "missing-entry"), /Unknown entry id/);
});

test("markdown and json packet output are deterministic", () => {
  const entry = data.studies[0];
  const first = StudyPackets.packet(data, "entry", entry.id);
  const second = StudyPackets.packet(data, "entry", entry.id);
  assert.deepEqual(first, second);
  assert.equal(StudyPackets.markdown(first), StudyPackets.markdown(second));
});


test("runtime receipts do not change packets and markdown is readable prose", () => {
  const item = data.studies.find(s => s.resultsUrl);
  const browser = JSON.parse(JSON.stringify(data));
  browser.studies.find(s => s.id === item.id).recordedResults = {derived: true};
  assert.deepEqual(StudyPackets.packet(browser, "study", item.id), StudyPackets.packet(data, "study", item.id));
  const md = StudyPackets.markdown(StudyPackets.packet(data, "study", "retrieval-and-relevance"));
  assert.match(md, /两个 recall/);
  assert.doesNotMatch(md, /```json/);
  assert.match(md, /https:\/\/indeliblevivi.github.io\/agent-memory-study\//);
  assert.throws(() => StudyPackets.packet(data, "__proto__", "a"), /Unknown packet kind/);
});
