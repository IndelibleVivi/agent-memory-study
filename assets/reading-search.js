/* Human-readable fields only. One index for browser and model-free tests. */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.ReadingSearch = factory();
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";
  const normalize = value => String(value ?? "").normalize("NFKC").toLocaleLowerCase("zh-CN").replace(/\s+/gu, " ").trim();

  function fieldsFor(item, kind, materials) {
    const fields = [];
    const add = (label, text, weight = 1) => {
      if (typeof text === "string" && text.trim()) fields.push({label, text, normalized: normalize(text), weight});
    };
    const strings = (label, values) => (values || []).forEach(text => add(label, text));
    const objects = (label, values, keys) => (values || []).forEach(value => keys.forEach(key => add(label, value[key])));
    add("标题", item.title, 30);
    if (kind === "material") {
      add("作者", (item.authors || []).join(" "), 12);
      add("年份", String(item.year));
      add("导读", item.whyRead, 5); add("摘要", item.intro, 4);
      strings("关键抓手", item.keyPoints);
      strings("论文报告", item.reportedFindings); strings("证据边界", item.evidenceLimits);
      objects("论证", item.argumentMap, ["step", "claim"]);
      objects("方法", item.methodNotes, ["label", "text"]);
      objects("原文内部张力", item.sourceTensions, ["label", "observation", "implication"]);
      objects("编者判断", item.editorialInferences, ["label", "text", "boundary"]);
      add("继续追问", item.editorialQuestion);
      if (item.designTransfer) ["when", "move", "check", "boundary", "basis"].forEach(k => add("怎样借用", item.designTransfer[k]));
      objects("未执行方案", item.openProtocols, ["title", "question", "method", "fixtures", "controls", "measures", "limitations"]);
      objects("署名观点与测试", item.contributions, ["title", "byline", "text", "basis", "method", "controls", "rawResult", "derivedResult", "limitations", "boundary"]);
      const audit = item.amsEvidence;
      if (audit) {
        strings("AMS 复核", audit.observations); strings("AMS 结果", audit.findings);
        objects("AMS 方法", audit.methods, ["label", "text"]);
        objects("AMS 推论", audit.reasoning, ["step", "claim"]);
      }
    } else {
      add("副标题", item.subtitle, 15); add("导读", item.intro, 5); add("署名", item.byline, 3);
      objects("共读正文", item.sections, ["title", "text"]);
      objects("带走判断", item.takeaways, ["title", "text"]);
      objects("串读", item.readings, ["label", "takeaway", "limit"]);
      objects("场景", item.scenarios, ["title", "description", "lesson"]);
      ["labTitle", "labIntro", "boundary", "closing"].forEach(k => add("共读实验", item[k]));
      for (const reading of item.readings || []) {
        const material = materials.get(reading.materialId);
        if (material) add("串读材料", `${material.title} ${(material.authors || []).join(" ")}`);
      }
    }
    return fields;
  }

  function buildIndex(data) {
    const materials = new Map(data.materials.map(item => [item.id, item]));
    return [
      ...data.materials.map(item => ({kind: "material", item, facets: [item]})),
      ...(data.studies || []).map(item => ({kind: "study", item, facets: (item.readings || []).map(r => materials.get(r.materialId)).filter(Boolean)})),
    ].map((entry, order) => ({...entry, order, fields: fieldsFor(entry.item, entry.kind, materials)}));
  }

  function excerpt(field, terms) {
    if (!field) return null;
    const positions = terms.map(t => field.normalized.indexOf(t)).filter(p => p >= 0);
    // Normalization may change offsets; use the original text for display, never HTML.
    const at = positions.length ? Math.min(...positions) : 0;
    const start = Math.max(0, at - 32);
    const text = field.text.slice(start, start + 145);
    return {label: field.label, text: `${start ? "…" : ""}${text}${start + 145 < field.text.length ? "…" : ""}`};
  }

  function search(index, query = "", filters = {}) {
    const q = normalize(query);
    const terms = [...new Set(q.split(" ").filter(Boolean))];
    const filtered = index.filter(entry => {
      if (!filters.topic && !filters.surface && !filters.depth) return true;
      // All selected facets must belong to one referenced material, not separate members.
      return entry.facets.some(m => (!filters.topic || (m.categories || []).includes(filters.topic))
        && (!filters.surface || (m.failureSurfaces || []).includes(filters.surface))
        && (!filters.depth || m.noteDepth === filters.depth));
    });
    const hits = [];
    for (const entry of filtered) {
      if (!terms.every(term => entry.fields.some(f => f.normalized.includes(term)))) continue;
      const matched = entry.fields.filter(f => terms.some(t => f.normalized.includes(t)));
      const score = terms.length ? (normalize(entry.item.title) === q ? 10000 : 0)
        + terms.reduce((sum, term) => sum + Math.max(0, ...entry.fields.filter(f => f.normalized.includes(term)).map(f => f.weight)), 0) : 0;
      // Prefer a useful body snippet over repeating a matching title; name the hit locations.
      const body = matched.find(f => !["标题", "作者", "年份"].includes(f.label));
      hits.push({kind: entry.kind, item: entry.item, score, order: entry.order,
        matchLabels: [...new Set(matched.map(f => f.label))].slice(0, 4),
        snippet: terms.length ? excerpt(body || matched[0], terms) : null});
    }
    return hits.sort((a, b) => b.score - a.score || a.order - b.order);
  }
  return {buildIndex, search, normalize};
});
