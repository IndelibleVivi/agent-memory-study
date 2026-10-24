const test = require("node:test");
const assert = require("node:assert/strict");
const desk = require("../assets/study-desk.js");
test("reference overlap and task relevance use different sets", () => {
  const a = desk.exercise({k: 3});
  assert.equal(a.neighborRecall, 1); assert.equal(a.precision, 1 / 3); assert.equal(a.recall, 1 / 4);
  const b = desk.exercise({k: 3, ranking: "contrast"});
  assert.equal(b.neighborRecall, 1 / 3); assert.equal(b.precision, 1); assert.equal(b.recall, 3 / 4);
  const c = desk.exercise({k: 8}); assert.equal(c.recall, 1); assert.equal(c.precision, 1 / 2);
  assert.notEqual(desk.exercise({need: "implement"}).recall, a.recall);
});
const data = {studies: [{id: "a", exercise: "retrieval-sets"}]};
const state = {schema: desk.schema, kind: "study", id: "a", note: "下次算 k=5。<script>literal</script>", anchor: "#study-lab", exercise: {k: 5, ranking: "contrast"}};
test("continuation preserves literal private text and only accepted fields", () => {
  const parsed = desk.parse(JSON.stringify({...state, externalUrl: "https://example.org"}), data);
  assert.equal(parsed.note, state.note); assert.equal(parsed.exercise.k, 5);
  assert.equal(parsed.externalUrl, undefined);
});
test("unknown, oversized and malformed continuations fail without navigation", () => {
  for (const value of [{...state, id: "missing"}, {...state, kind: "__proto__"}, {...state, note: "a".repeat(20001)}, {...state, anchor: "#<img>"}])
    assert.throws(() => desk.validate(value, data));
  assert.throws(() => desk.parse("[", data)); assert.throws(() => desk.parse("x".repeat(128001), data));
});

const room = {
  room: {edition: "2026-10-25"},
  materials: [
    {id: "source-a", title: "Source A", date: "2026-10-20", authors: ["A"], intro: "Public source A."},
    {id: "source-b", title: "Source B", updated: "2026-10-21", authors: ["B"], intro: "Public source B."},
  ],
  studies: [
    {id: "entry-a", title: "Entry A", date: "2026-10-22", bodyMarkdown: "# Entry A\n\nLiteral **public** prose.",
     readings: [{materialId: "source-a"}], labTitle: "Open question"},
  ],
  questions: [
    {id: "question-a", title: "Question A", updated: "2026-10-23", question: "What remains?"},
  ],
  findings: [
    {id: "transfer-a", title: "Transfer A", updated: "2026-10-24", claim: "A bounded claim."},
  ],
};

function added(refs, work = desk.emptyWorkspace(), target = room) {
  return refs.reduce((current, ref) => desk.add(current, ref, target), work);
}

test("workspace preserves mixed-kind order, zero notes and at most two comparisons", () => {
  const work = added([
    {kind: "material", id: "source-b"},
    {kind: "study", id: "entry-a"},
    {kind: "question", id: "question-a"},
    {kind: "finding", id: "transfer-a"},
  ]);
  assert.deepEqual(work.items.map(ref => desk.key(ref)), [
    "material:source-b", "study:entry-a", "question:question-a", "finding:transfer-a",
  ]);
  assert.deepEqual(work.compare, ["material:source-b", "study:entry-a"]);
  assert.ok(work.items.every(ref => ref.note === "" && ref.anchor === ""));
  assert.equal(work.items[0].contentVersion, "2026-10-21");
  assert.match(work.items[0].basis, /Public source B/);

  const moved = desk.move(work, "finding:transfer-a", -1, room);
  assert.deepEqual(moved.items.map(ref => desk.key(ref)), [
    "material:source-b", "study:entry-a", "finding:transfer-a", "question:question-a",
  ]);
  assert.deepEqual(desk.move(moved, "material:source-b", -1, room).items.map(desk.key),
    moved.items.map(desk.key), "moving the first item up is a no-op");
  assert.deepEqual(desk.move(moved, "question-a", 1, room).items.map(desk.key),
    moved.items.map(desk.key), "an unknown id is a no-op rather than mutating a neighbour");

  const removed = desk.remove(moved, "material:source-b", room);
  assert.deepEqual(removed.items.map(desk.key), [
    "study:entry-a", "finding:transfer-a", "question:question-a",
  ]);
  assert.deepEqual(removed.compare, ["study:entry-a"], "removing a compared object releases its slot");
});

test("workspace accepts exactly 24 distinct objects and refuses the 25th without mutation", () => {
  const target = {
    room: {edition: "edition-one"},
    materials: Array.from({length: 25}, (_, i) => ({id: `source-${i}`, title: `Source ${i}`, intro: `Body ${i}`})),
    studies: [], questions: [], findings: [],
  };
  const full = added(Array.from({length: 24}, (_, i) => ({kind: "material", id: `source-${i}`})), undefined, target);
  assert.equal(full.items.length, desk.workspaceLimit);
  assert.equal(desk.workspaceLimit, 24);
  const before = JSON.stringify(full);
  assert.throws(() => desk.add(full, {kind: "material", id: "source-24"}, target), /已满/);
  assert.equal(JSON.stringify(full), before, "a rejected addition leaves the caller's workspace unchanged");
});

test("workspace rejects unknown and prototype-shaped identities while rebuilding fields", () => {
  const valid = added([{kind: "material", id: "source-a"}]);
  assert.throws(() => desk.add(desk.emptyWorkspace(), {kind: "material", id: "missing"}, room), /当前书房没有/);
  for (const kind of ["__proto__", "constructor", "toString"]) {
    assert.throws(() => desk.workspace({
      ...desk.emptyWorkspace(), items: [{...valid.items[0], kind}],
    }, room), /有效对象/);
  }
  assert.throws(() => desk.workspace({...valid, items: [{...valid.items[0], id: "__proto__"}]}, room),
    /当前书房没有/);

  const hostile = {
    ...valid,
    title: "Private title",
    question: "<img src=x onerror=alert(1)>",
    synthesis: "Private synthesis",
    next: "Private next",
    extra: "not copied",
    items: [{
      ...valid.items[0],
      note: "<script>window.BAD=true</script>",
      basis: "opaque imported text only",
      externalUrl: "https://example.invalid/private",
      html: "<b>must not survive</b>",
      nested: {private: true},
    }],
  };
  const rebuilt = desk.workspace(hostile, room);
  assert.deepEqual(Object.keys(rebuilt).sort(), ["compare", "items", "next", "question", "schema", "synthesis", "title"]);
  assert.equal(rebuilt.title, "Private title");
  assert.equal(rebuilt.items[0].note, hostile.items[0].note);
  assert.equal(rebuilt.items[0].basis, "opaque imported text only");
  assert.equal(rebuilt.extra, undefined);
  for (const key of ["externalUrl", "html", "nested"]) assert.equal(rebuilt.items[0][key], undefined);
  assert.deepEqual(Object.keys(rebuilt.items[0]).sort(),
    ["anchor", "basis", "contentVersion", "id", "kind", "note"]);
});

test("workspace file limit counts UTF-8 bytes at the 2 MiB boundary", () => {
  const valid = added([{kind: "material", id: "source-a"}]);
  const base = JSON.stringify(valid);
  const before = JSON.parse(base);
  assert.ok(new TextEncoder().encode(base).length < desk.workspaceBytes);
  assert.equal(desk.parseWorkspace(base, room).items[0].id, "source-a");
  const padded = JSON.stringify({...before, unknownPadding: "x".repeat(desk.workspaceBytes + 1)});
  assert.ok(new TextEncoder().encode(padded).length > desk.workspaceBytes);
  assert.throws(() => desk.parseWorkspace(padded, room), /2 MiB/);
  const emptyPadding = JSON.stringify({...before, unknownPadding: ""});
  const remaining = desk.workspaceBytes - new TextEncoder().encode(emptyPadding).length;
  const exact = JSON.stringify({...before, unknownPadding: "课".repeat(Math.floor(remaining / 3)) + "x".repeat(remaining % 3)});
  assert.equal(new TextEncoder().encode(exact).length, desk.workspaceBytes);
  assert.deepEqual(desk.parseWorkspace(exact, room), valid);
  assert.throws(() => desk.parseWorkspace(exact + " ", room), /2 MiB/);

  const unicode = JSON.stringify({...before, synthesis: "课".repeat(20000)});
  assert.ok(new TextEncoder().encode(unicode).length < 200000);
  assert.equal(desk.parseWorkspace(unicode, room).synthesis[0], "课");
  assert.throws(() => desk.parseWorkspace(JSON.stringify({...before, synthesis: "课".repeat(20001)}), room),
    /20,000/);
});

test("workspace detects same-day public changes by current content, not only dates", () => {
  const work = added([{kind: "study", id: "entry-a"}]);
  assert.equal(desk.changed(work.items[0], room), false);
  const sameDay = structuredClone(room);
  sameDay.studies[0].bodyMarkdown += "\n\nA later sentence on the same date.";
  sameDay.studies[0].date = room.studies[0].date;
  assert.equal(sameDay.studies[0].date, work.items[0].contentVersion);
  assert.equal(desk.changed(work.items[0], sameDay), true);
  const confirmed = {...work.items[0], basis: desk.basis(work.items[0], sameDay)};
  assert.equal(desk.changed(confirmed, sameDay), false);

  const imported = {...work.items[0], basis: ""};
  assert.equal(desk.changed(imported, sameDay), false,
    "a legacy/private import without a public basis makes no stale claim");
});

test("workspace Markdown keeps private fields and anchors while projecting current public packets", () => {
  const source = {...added([{kind: "material", id: "source-a"}]).items[0],
    note: "A private note", anchor: "#source-anchor"};
  source.basis = JSON.stringify({...room.materials[0], intro: "An older public version."});
  const entry = added([{kind: "study", id: "entry-a"}]).items[0];
  const work = desk.workspace({
    ...added([]),
    title: "My private desk",
    question: "A private question",
    synthesis: "A private synthesis",
    next: "A private next step",
    items: [source, entry],
  }, room);
  const markdown = desk.workspaceMarkdown(work, room, require("../assets/study-packets.js"));
  assert.match(markdown, /# My private desk/);
  assert.match(markdown, /A private question/);
  assert.match(markdown, /A private synthesis/);
  assert.match(markdown, /A private next step/);
  assert.match(markdown, /A private note/);
  assert.match(markdown, /#source-anchor/);
  assert.match(markdown, /保存后公开内容已有变化/);
  assert.match(markdown, /Source A/);
  assert.match(markdown, /Entry A/);
});
