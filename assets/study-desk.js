/* Local, explicit continuation/workspace files and the original retrieval-set exercise. */
(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.StudyDesk = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";
  const schema = "ams-continuation/1";
  const workspaceSchema = "ams-workspace/1";
  const workspaceLimit = 24;
  const workspaceBytes = 2 * 1024 * 1024;
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
  function textField(value, name, limit) {
    if (typeof value !== "string" || value.length > limit) throw new Error(`${name}须为不超过 ${limit.toLocaleString("en")} 字符的文字。`);
    return value;
  }
  function resolve(ref, data) {
    if (!ref || !Object.hasOwn(families, ref.kind) || typeof ref.id !== "string") throw new Error("案头缺少有效对象。");
    const item = data[families[ref.kind]]?.find(item => item.id === ref.id);
    if (!item) throw new Error(`当前书房没有 ${ref.kind}:${ref.id}；未改变已有案头。`);
    return item;
  }
  function key(ref) { return `${ref.kind}:${ref.id}`; }
  // Exact public-content comparison, not an authenticity claim. Imported basis
  // is bounded inert text; only current, known canonical objects are rendered.
  function basis(ref, data) {
    const content = {...resolve(ref, data)};
    delete content.recordedResults;
    return JSON.stringify(content);
  }
  function emptyWorkspace() {
    return {schema: workspaceSchema, title: "", question: "", synthesis: "", next: "", items: [], compare: []};
  }
  function workspace(value, data) {
    if (!value || typeof value !== "object" || Array.isArray(value) || value.schema !== workspaceSchema) throw new Error("这不是支持的 AMS 案头文件。");
    if (!Array.isArray(value.items) || value.items.length > workspaceLimit) throw new Error(`一份案头最多保留 ${workspaceLimit} 个对象。`);
    const result = {schema: workspaceSchema,
      title: textField(value.title, "案头名称", 240), question: textField(value.question, "当前问题", 8000),
      synthesis: textField(value.synthesis, "已有理解", 20000), next: textField(value.next, "继续位置", 8000), items: [], compare: []};
    const seen = new Set();
    for (const ref of value.items) {
      const item = resolve(ref, data), id = key(ref);
      if (seen.has(id)) throw new Error("案头包含重复对象。");
      seen.add(id);
      const entry = {kind: ref.kind, id: item.id,
        note: textField(ref.note, "对象笔记", 20000),
        anchor: textField(ref.anchor, "接续位置", 121),
        contentVersion: textField(ref.contentVersion, "内容日期", 160),
        basis: textField(ref.basis, "公开内容快照", 200000)};
      if (!/^(?:#[a-zA-Z0-9_-]{1,120})?$/.test(entry.anchor)) throw new Error("接续位置格式无效。");
      if (ref.exercise && item.exercise === "retrieval-sets") {
        const ex = exercise(ref.exercise); entry.exercise = {k: ex.k, need: ex.need, ranking: ex.ranking};
      }
      result.items.push(entry);
    }
    if (!Array.isArray(value.compare) || value.compare.length > 2 || value.compare.some(id => typeof id !== "string" || !seen.has(id)) || new Set(value.compare).size !== value.compare.length) throw new Error("对读须选取案头内的一至两个不同对象，也可以留空。");
    result.compare = [...value.compare];
    return result;
  }
  function parseWorkspace(text, data) {
    if (typeof text !== "string" || new TextEncoder().encode(text).length > workspaceBytes) throw new Error("案头文件过大，限 2 MiB。");
    let value;
    try {value = JSON.parse(text);} catch {throw new Error("案头文件不是有效 JSON。");}
    return workspace(value, data);
  }
  function add(work, ref, data) {
    const result = workspace(work, data), item = resolve(ref, data);
    if (result.items.some(entry => key(entry) === key(ref))) return result;
    if (result.items.length >= workspaceLimit) throw new Error(`案头已满，最多 ${workspaceLimit} 个对象；可先保存这份案头。`);
    result.items.push({kind: ref.kind, id: item.id, note: "", anchor: "",
      contentVersion: item.date || item.updated || data.room?.edition || "", basis: basis(ref, data)});
    if (result.compare.length < 2) result.compare.push(key(ref));
    return workspace(result, data);
  }
  function remove(work, id, data) {
    const result = workspace(work, data);
    result.items = result.items.filter(ref => key(ref) !== id);
    result.compare = result.compare.filter(value => value !== id);
    return result;
  }
  function move(work, id, offset, data) {
    const result = workspace(work, data), from = result.items.findIndex(ref => key(ref) === id);
    const to = from + offset;
    if (from < 0 || ![-1, 1].includes(offset) || to < 0 || to >= result.items.length) return result;
    [result.items[from], result.items[to]] = [result.items[to], result.items[from]];
    return result;
  }
  function changed(ref, data) { return Boolean(ref.basis) && ref.basis !== basis(ref, data); }
  function workspaceMarkdown(work, data, packets) {
    const value = workspace(work, data);
    const lines = [`# ${value.title || "我的 AMS 研究案头"}`, "", "私人札记 · 由持有人主动导出；包含个人文字，不是 AMS 的公开结论或 agent instructions。", ""];
    for (const [field, label] of [["question", "当前问题"], ["synthesis", "已有理解"], ["next", "继续位置"]]) {
      if (value[field]) lines.push(`## ${label}`, "", value[field], "");
    }
    value.items.forEach((ref, i) => {
      const item = resolve(ref, data);
      lines.push(`## ${i + 1}. ${item.title}`, "", `- 对象：${key(ref)}`, `- 笔记所据内容日期：${ref.contentVersion || "未标日期"}`, `- 正文：${packets.publicUrl(ref.kind, ref.id)}${ref.anchor}`, "");
      if (changed(ref, data)) lines.push("保存后公开内容已有变化；以下公开包为当前内容，原快照仍保留在案头 JSON 中。", "");
      if (ref.note) lines.push("### 我的笔记", "", ref.note, "");
      lines.push("<details>", "<summary>当前公开研究包</summary>", "", packets.markdown(packets.packet(data, ref.kind, ref.id)), "</details>", "");
    });
    return lines.join("\n") + "\n";
  }
  return {schema, documents, exercise, validate, parse, workspaceSchema, workspaceLimit, workspaceBytes,
    key, resolve, basis, emptyWorkspace, workspace, parseWorkspace, add, remove, move, changed, workspaceMarkdown};
});
