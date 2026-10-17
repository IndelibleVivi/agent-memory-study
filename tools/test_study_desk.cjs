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
