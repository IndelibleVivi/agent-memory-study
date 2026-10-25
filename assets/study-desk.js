/* Local, explicit continuation/workspace files and the original retrieval-set exercise. */
(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.StudyDesk = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";
  const schema = "ams-continuation/1";
  const workspaceSchema = "ams-workspace/2";
  const workspaceLimit = 24;
  const workspaceBytes = 2 * 1024 * 1024;
  const excerptLimit = 12;
  const excerptRoles = {context: "背景", support: "支持这一理解", contrast: "形成对照", question: "留下疑问"};
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
    if (!value || typeof value !== "object" || Array.isArray(value) || ![workspaceSchema, "ams-workspace/1"].includes(value.schema)) throw new Error("这不是支持的 AMS 案头文件。");
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
        basis: textField(ref.basis, "公开内容快照", 200000), excerpts: []};
      if (!/^(?:#[a-zA-Z0-9_-]{1,120})?$/.test(entry.anchor)) throw new Error("接续位置格式无效。");
      const excerpts = ref.excerpts === undefined && value.schema === "ams-workspace/1" ? [] : ref.excerpts;
      if (!Array.isArray(excerpts) || excerpts.length > excerptLimit) throw new Error(`每个对象最多保留 ${excerptLimit} 条摘录。`);
      const identities = new Set();
      for (const part of excerpts) {
        if (!part || typeof part !== "object" || Array.isArray(part) || typeof part.id !== "string" || !/^excerpt-[1-9][0-9]{0,8}$/.test(part.id)) throw new Error("摘录身份无效。");
        if (identities.has(part.id)) throw new Error("摘录包含重复身份。");
        identities.add(part.id);
        if (!Object.hasOwn(excerptRoles, part.role)) throw new Error("摘录用途无效。");
        const excerpt = {id: part.id, quote: textField(part.quote, "摘录", 8000), comment: textField(part.comment, "摘录批注", 8000), role: part.role,
          anchor: textField(part.anchor, "摘录位置", 121), contentVersion: textField(part.contentVersion, "摘录内容日期", 160), basis: textField(part.basis, "摘录来源快照", 200000)};
        if (!excerpt.quote.trim() || !/^(?:#[a-zA-Z0-9_-]{1,120})?$/.test(excerpt.anchor)) throw new Error("摘录须有文字及有效位置。");
        entry.excerpts.push(excerpt);
      }
      if (ref.exercise && item.exercise === "retrieval-sets") {
        const ex = exercise(ref.exercise); entry.exercise = {k: ex.k, need: ex.need, ranking: ex.ranking};
      }
      result.items.push(entry);
    }
    if (!Array.isArray(value.compare) || value.compare.length > 2 || value.compare.some(id => typeof id !== "string" || !seen.has(id)) || new Set(value.compare).size !== value.compare.length) throw new Error("对读须选取案头内的一至两个不同对象，也可以留空。");
    result.compare = [...value.compare];
    // Every accepted in-memory state must also fit the actual download format.
    if (new TextEncoder().encode(JSON.stringify(result, null, 2)).length > workspaceBytes) throw new Error("案头超过 2 MiB；请先保存当前案头，再分开整理。");
    return result;
  }
  function serializeWorkspace(work, data) { return JSON.stringify(workspace(work, data), null, 2); }
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
      contentVersion: item.date || item.updated || data.room?.edition || "", basis: basis(ref, data), excerpts: []});
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
  function changed(ref, data) { return revision(ref, data).status === "changed"; }
  function addExcerpt(work, id, input, data) {
    const result = workspace(work, data), ref = result.items.find(ref => key(ref) === id);
    if (!ref) throw new Error("先把对象加入案头再摘录。");
    if (ref.excerpts.length >= excerptLimit) throw new Error(`每个对象最多保留 ${excerptLimit} 条摘录。`);
    const nextId = Math.max(0, ...ref.excerpts.map(part => Number(part.id.slice(8)))) + 1;
    const item = resolve(ref, data);
    ref.excerpts.push({id: `excerpt-${nextId}`, quote: input.quote, comment: input.comment ?? "", role: input.role ?? "context", anchor: input.anchor ?? "",
      contentVersion: item.date || item.updated || data.room?.edition || "", basis: basis(ref, data)});
    return workspace(result, data);
  }
  function rebase(work, id, data) {
    const result = workspace(work, data), ref = result.items.find(ref => key(ref) === id);
    if (!ref) throw new Error("案头没有这个对象。");
    const item = resolve(ref, data);
    ref.basis = basis(ref, data); ref.contentVersion = item.date || item.updated || data.room?.edition || "";
    return workspace(result, data);
  }
  function revision(ref, data) {
    const current = JSON.parse(basis(ref, data));
    if (!ref.basis) return {status: "unknown", fields: [], before: "", after: ""};
    let saved;
    try {saved = JSON.parse(ref.basis);} catch {return {status: "invalid", fields: [], before: ref.basis, after: ""};}
    if (!saved || Array.isArray(saved) || saved.id !== ref.id) return {status: "invalid", fields: [], before: ref.basis, after: ""};
    try {
      const fields = [...new Set([...Object.keys(saved), ...Object.keys(current)])].filter(field => JSON.stringify(saved[field]) !== JSON.stringify(current[field])).sort();
      // Inert pretty-printed text, including HTML source. Never return a renderable
      // imported fragment. Object order is irrelevant to the field comparison.
      return {status: fields.length ? "changed" : "current", fields,
        before: JSON.stringify(saved, null, 2), after: JSON.stringify(current, null, 2)};
    } catch {return {status: "invalid", fields: [], before: ref.basis, after: ""};}
  }
  function history(initial, data) {
    let states = [serializeWorkspace(initial, data)], position = 0, group = null, saved = states[0];
    function value() { return JSON.parse(states[position]); }
    function commit(next, editingGroup = null) {
      const text = serializeWorkspace(next, data);
      if (text === states[position]) return value();
      states = states.slice(0, position + 1);
      if (editingGroup && editingGroup === group && position > 0) states[position] = text;
      else {states.push(text); position++;}
      group = editingGroup;
      // Snapshots are private page memory. Keep the most recent 20 transitions,
      // and cap their serialized UTF-8 size at 8 MiB for large reading sessions.
      let bytes = states.reduce((sum, state) => sum + new TextEncoder().encode(state).length, 0);
      while (states.length > 21 || (bytes > 8 * 1024 * 1024 && states.length > 1)) {
        bytes -= new TextEncoder().encode(states.shift()).length; position--;
      }
      return value();
    }
    return {value, commit, canUndo: () => position > 0, canRedo: () => position < states.length - 1,
      undo() {if (position > 0) position--; group = null; return value();},
      redo() {if (position < states.length - 1) position++; group = null; return value();},
      markSaved() {saved = states[position]; group = null;}, dirty: () => states[position] !== saved};
  }
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
      else if (revision(ref, data).status === "invalid") lines.push("来源快照不可比较；不能据此确认旧笔记与当前正文的关系。", "");
      else if (!ref.basis) lines.push("没有来源快照；内容日期不能确认正文身份。", "");
      if (ref.note) lines.push("### 我的笔记", "", ref.note, "");
      if (ref.excerpts.length) lines.push("### 摘录与批注", "", "用途是持有人的阅读判断，不代表来源认可、引用核实或已确认结论。", "");
      for (const part of ref.excerpts) {
        lines.push(`#### ${part.id} · ${excerptRoles[part.role]}`, "", part.quote.split("\n").map(line => `> ${line}`).join("\n"), "",
          `- 来源：${packets.publicUrl(ref.kind, ref.id)}${part.anchor}`, `- 摘录内容日期：${part.contentVersion || "未标日期"}`, `- 来源版本：${{current: "与当前内容相同", changed: "公开内容已变化", unknown: "无快照", invalid: "快照不可比较"}[revision({...ref, basis: part.basis}, data).status]}`, "");
        if (part.comment) lines.push(part.comment, "");
      }
      lines.push("<details>", "<summary>当前公开研究包</summary>", "", packets.markdown(packets.packet(data, ref.kind, ref.id)), "</details>", "");
    });
    return lines.join("\n") + "\n";
  }
  return {schema, documents, exercise, validate, parse, workspaceSchema, workspaceLimit, workspaceBytes, excerptLimit, excerptRoles,
    key, resolve, basis, emptyWorkspace, workspace, serializeWorkspace, parseWorkspace, add, remove, move, changed, addExcerpt, rebase, revision, history, workspaceMarkdown};
});
