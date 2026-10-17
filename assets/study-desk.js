/* Local, explicit continuation files and the original retrieval-set exercise. */
(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.StudyDesk = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";
  const schema = "ams-continuation/1";
  const documents = ["a", "b", "c", "d", "e", "f", "g", "h"];
  const rankings = {reference: documents, contrast: ["a", "d", "e", "f", "b", "c", "g", "h"]};
  const needs = {understand: ["a", "d", "e", "f"], implement: ["b", "c", "g"]};
  function exercise(input = {}) {
    const k = Math.max(1, Math.min(8, Number.isInteger(Number(input.k)) ? Number(input.k) : 3));
    const ranking = Object.hasOwn(rankings, input.ranking) ? input.ranking : "reference";
    const need = Object.hasOwn(needs, input.need) ? input.need : "understand";
    const selected = rankings[ranking].slice(0, k);
    const reference = documents.slice(0, k);
    const relevant = needs[need];
    const hits = selected.filter(id => relevant.includes(id));
    const overlap = selected.filter(id => reference.includes(id));
    return {k, ranking, need, selected, reference, relevant, hits, overlap,
      neighborRecall: overlap.length / k, precision: hits.length / k, recall: hits.length / relevant.length};
  }
  const families = {material: "materials", study: "studies", question: "questions", finding: "findings"};
  function validate(value, data) {
    if (!value || typeof value !== "object" || Array.isArray(value) || value.schema !== schema) throw new Error("这不是支持的 AMS 接续文件。");
    if (!Object.hasOwn(families, value.kind) || typeof value.id !== "string") throw new Error("接续文件缺少有效对象。");
    const item = data[families[value.kind]]?.find(item => item.id === value.id);
    if (!item) throw new Error("当前书房没有文件所指的研究对象。");
    if (typeof value.note !== "string" || value.note.length > 20000) throw new Error("笔记须为不超过 20,000 字符的文字。");
    if (typeof value.anchor !== "string" || !/^(?:#[a-zA-Z0-9_-]{1,120})?$/.test(value.anchor)) throw new Error("接续位置格式无效。");
    const state = {schema, kind: value.kind, id: value.id, note: value.note, anchor: value.anchor,
      contentVersion: typeof value.contentVersion === "string" ? value.contentVersion.slice(0, 160) : ""};
    if (value.exercise && item.exercise === "retrieval-sets") {
      const ex = exercise(value.exercise); state.exercise = {k: ex.k, need: ex.need, ranking: ex.ranking};
    }
    return state;
  }
  function parse(text, data) {
    if (typeof text !== "string" || text.length > 128000) throw new Error("接续文件过大，限 128 KB。");
    let value;
    try { value = JSON.parse(text); } catch { throw new Error("接续文件不是有效 JSON。"); }
    return validate(value, data);
  }
  return {schema, documents, exercise, validate, parse};
});
