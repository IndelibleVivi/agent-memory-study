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
    ["anchor", "basis", "contentVersion", "excerpts", "id", "kind", "note"]);
});

test("workspace/1 migrates once; workspace/2 excerpts retain their original basis through rebase", () => {
  const ref = {kind: "study", id: "entry-a"};
  const legacy = added([ref]); legacy.schema = "ams-workspace/1";
  delete legacy.items[0].excerpts;
  const migrated = desk.parseWorkspace(JSON.stringify(legacy), room);
  assert.equal(migrated.schema, "ams-workspace/2");
  assert.deepEqual(migrated.items[0].excerpts, []);
  const captured = desk.addExcerpt(migrated, desk.key(ref), {
    quote: "Literal **public** prose.", anchor: "#section-1", role: "contrast", comment: "My uncertainty",
  }, room);
  const original = structuredClone(captured.items[0].excerpts[0]);
  assert.equal(original.id, "excerpt-1");
  assert.equal(original.basis, captured.items[0].basis);
  assert.equal(migrated.items[0].excerpts.length, 0, "capture is atomic and does not mutate its input");
  const revised = structuredClone(room); revised.studies[0].bodyMarkdown += "\nNew claim";
  const rebased = desk.rebase(captured, desk.key(ref), revised);
  assert.equal(desk.changed(rebased.items[0], revised), false);
  assert.deepEqual(rebased.items[0].excerpts[0], original, "reviewing the object cannot rewrite a quotation's origin");
  assert.equal(desk.revision({...ref, basis: original.basis}, revised).status, "changed");
  const roundTrip = desk.parseWorkspace(desk.serializeWorkspace(rebased, revised), revised);
  assert.deepEqual(roundTrip, rebased);
  assert.match(desk.workspaceMarkdown(rebased, revised, require("../assets/study-packets.js")), /My uncertainty/);
});

test("excerpt imports rebuild fields and reject invalid or excessive input atomically", () => {
  const work = added([{kind: "material", id: "source-a"}]);
  const first = desk.addExcerpt(work, "material:source-a", {quote: "<script>literal</script>", comment: "c", role: "question", anchor: ""}, room);
  const snapshot = JSON.stringify(first);
  for (const part of [{role: "proven"}, {quote: ""}, {quote: "a".repeat(8001)}, {anchor: "#<bad>"}]) {
    assert.throws(() => desk.addExcerpt(first, "material:source-a", {quote: "q", role: "context", anchor: "", comment: "", ...part}, room));
  }
  assert.equal(JSON.stringify(first), snapshot);
  const hostile = structuredClone(first); hostile.items[0].excerpts[0].url = "https://example.invalid/private";
  const parsed = desk.workspace(hostile, room);
  assert.equal(parsed.items[0].excerpts[0].url, undefined);
  hostile.items[0].excerpts.push({...hostile.items[0].excerpts[0]});
  assert.throws(() => desk.workspace(hostile, room), /重复/);
  let full = work;
  for (let i = 0; i < desk.excerptLimit; i++) full = desk.addExcerpt(full, "material:source-a", {quote: "q", role: "context", comment: "", anchor: ""}, room);
  assert.throws(() => desk.addExcerpt(full, "material:source-a", {quote: "q"}, room), /摘录/);
});

test("revision inspection is literal, distinguishes unknown from mismatched snapshots, and handles same-day changes", () => {
  const ref = added([{kind: "study", id: "entry-a"}]).items[0];
  assert.equal(desk.revision(ref, room).status, "current");
  assert.equal(desk.changed({...ref, basis: JSON.stringify(JSON.parse(ref.basis), null, 2)}, room), false,
    "JSON envelope whitespace alone does not create a contradictory changed flag");
  assert.equal(desk.revision({...ref, basis: ""}, room).status, "unknown");
  assert.equal(desk.revision({...ref, basis: '{"id":"other","bodyHtml":"<img onerror=bad()>"}'}, room).status, "invalid");
  const modified = structuredClone(room); modified.studies[0].bodyMarkdown += "\nChanged on the same day";
  const result = desk.revision(ref, modified);
  assert.equal(result.status, "changed");
  assert.match(result.before, /Literal/); assert.match(result.after, /Changed on the same day/);
  assert.deepEqual(result.fields, ["bodyMarkdown"]);
});

test("history coalesces one editing session, restores several operations, branches, and compares exact save checkpoints", () => {
  const history = desk.history(desk.emptyWorkspace(), room);
  const a = added([{kind: "material", id: "source-a"}]); history.commit(a);
  history.commit({...a, question: "first"}, "question-focus-1");
  history.commit({...a, question: "second"}, "question-focus-1");
  history.markSaved(); assert.equal(history.dirty(), false);
  history.commit({...history.value(), next: "later"}, "next-focus-2");
  assert.equal(history.dirty(), true);
  assert.equal(history.undo().question, "second"); assert.equal(history.dirty(), false);
  assert.equal(history.undo().question, "");
  assert.equal(history.redo().question, "second");
  history.commit({...history.value(), synthesis: "new branch"});
  assert.equal(history.canRedo(), false);
  history.undo(); history.undo(); history.undo();
  assert.equal(history.value().items.length, 0);
  assert.equal(history.canUndo(), false);
  for (let i = 0; i < 30; i++) history.commit({...history.value(), title: String(i)});
  let steps = 0; while (history.canUndo()) {history.undo(); steps++;}
  assert.equal(steps, 20, "bounded history retains the latest twenty transitions");
});

test("large work remains saveable; size rejection keeps the last accepted state and history stays bounded", () => {
  const target = {room: room.room, materials: [], questions: [], findings: [],
    studies: Array.from({length: 9}, (_, i) => ({id: `large-${i}`, title: `Large ${i}`, bodyMarkdown: "课".repeat(60000)}))};
  let work = desk.emptyWorkspace();
  for (let i = 0; i < 9; i++) work = desk.add(work, {kind: "study", id: `large-${i}`}, target);
  const history = desk.history(work, target);
  const before = desk.serializeWorkspace(history.value(), target);
  const oversized = desk.workspace(work, target);
  for (const ref of oversized.items) ref.note = "课".repeat(20000);
  assert.throws(() => history.commit(oversized), /2 MiB/);
  assert.equal(desk.serializeWorkspace(history.value(), target), before);
  for (let i = 0; i < 12; i++) history.commit({...work, title: String(i)});
  let steps = 0; while (history.canUndo()) {history.undo(); steps++;}
  assert.ok(steps > 0 && steps < 20, "the byte bound reduces retained steps for large work");
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
