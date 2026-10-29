/* Public object relationships and editorial domain layout. Neither connections
   nor coordinates imply similarity, ranking, or evidence beyond explicit links. */
(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.ResearchMap = api;
})(typeof globalThis === "object" ? globalThis : this, function () {
  "use strict";

  const families = {study: "studies", material: "materials", question: "questions", finding: "findings"};
  const referenceFields = [["materialIds", "material"], ["studyIds", "study"], ["questionIds", "question"], ["findingIds", "finding"]];
  const list = value => Array.isArray(value) ? value : [];

  function domainList(domains) {
    const seen = new Set();
    return list(domains).filter(domain => {
      if (!domain || typeof domain.id !== "string" || !domain.id || seen.has(domain.id)) return false;
      seen.add(domain.id);
      return true;
    });
  }

  function sourceData(data = {}) {
    if (data?.schema === "ams-public-corpus-manifest/1") {
      const manifestFamilies = {
        material: "materials", study: "studies",
        question: "questions", finding: "findings",
      };
      const rows = Object.fromEntries(
        Object.values(manifestFamilies).map(name => [name, []]),
      );
      for (const object of list(data.objects)) {
        rows[manifestFamilies[object.public_kind]].push({
          id: object.public_id, title: object.public_id, intro: "",
          domains: [], _manifestObject: object,
        });
      }
      return {
        ...rows, room: data.room || {domains: []},
        references: data.graphs?.references || [],
        navigation: data.graphs?.navigation_memberships || [],
      };
    }
    return data;
  }

  function referenceGraph(rawData = {}) {
    const data = sourceData(rawData);
    if (data.references) {
      const nodes = Object.entries(families).flatMap(([kind, family]) =>
        list(data[family]).map(item => ({
          key: `${kind}/${item.id}`, kind, id: item.id, title: item.title,
          item, domainIds: [], primaryDomain: null, summary: item.intro || "",
        })));
      return {nodes, references: data.references.map(reference => ({...reference}))};
    }
    const domains = domainList(data?.room?.domains);
    const nodes = Object.entries(families).flatMap(([kind, family]) =>
      list(data?.[family]).map(item => {
        const explicit = new Set(list(item.domains));
        const domainIds = domains.filter(domain => explicit.has(domain.id) ||
          list(domain[`${kind}Ids`]).includes(item.id)).map(domain => domain.id);
        return {
          key: `${kind}/${item.id}`, kind, id: item.id, title: item.title, item,
          domainIds, primaryDomain: domainIds[0] || null,
          summary: typeof item.intro === "string" ? item.intro : typeof item.claim === "string" ? item.claim : ""
        };
      }));
    const byKey = new Map(nodes.map(node => [node.key, node]));
    const references = [], seen = new Set();
    function connect(node, kind, id, relation, locator) {
      if (typeof id !== "string") return;
      const to = `${kind}/${id}`;
      if (!byKey.has(to) || node.key === to) return;
      const key = `${node.key}\0${to}\0${relation}\0${locator}`;
      if (!seen.has(key)) {
        seen.add(key);
        references.push({from: node.key, to, relation, locator});
      }
    }
    nodes.forEach(node => {
      const item = node.item;
      for (const [field, kind] of referenceFields) {
        list(item[field]).forEach((id, position) =>
          connect(node, kind, id, "related", `${field}[${position}]`));
        list(item.continuation?.[field]).forEach((id, position) =>
          connect(node, kind, id, "continuation", `continuation.${field}[${position}]`));
      }
      list(item.readings).forEach((reading, position) =>
        connect(node, "material", reading?.materialId, "reading", `readings[${position}].materialId`));
      // The compiler emits direct Markdown references beside rendered HTML.
      // Never mine HTML here: presentation and relation extraction stay separate.
      list(item.ast?.references).forEach((reference, position) => {
        const targetKind = reference?.kind === "entry" ? "study"
          : reference?.kind === "source_note" ? "material"
          : reference?.kind === "thread" ? "question"
          : reference?.kind === "claim_revision" ? "finding" : reference?.kind;
        connect(node, targetKind, reference?.id, "body-link",
          `ast.references[${position}]`);
      });
    });
    return {nodes, references};
  }

  function graph(data = {}) {
    const model = referenceGraph(data);
    const byKey = new Map(model.nodes.map((node, index) => [node.key, index]));
    const edges = [], seen = new Set();
    for (const reference of model.references) {
      const from = byKey.get(reference.from), to = byKey.get(reference.to);
      if (from === undefined || to === undefined || from === to) continue;
      const key = `${Math.min(from, to)}:${Math.max(from, to)}`;
      if (!seen.has(key)) {seen.add(key); edges.push([from, to]);}
    }
    return {nodes: model.nodes, edges};
  }

  function impact(data, kind, id) {
    if (!Object.hasOwn(families, kind) || typeof id !== "string" || !id) {
      throw new Error("impact requires a known kind and a non-empty id");
    }
    const model = referenceGraph(data);
    const target = `${kind}/${id}`;
    const targetNode = model.nodes.find(node => node.key === target);
    if (!targetNode) throw new Error(`Unknown public object: ${target}`);
    const incoming = new Map();
    for (const reference of model.references) {
      const rows = incoming.get(reference.to) || [];
      rows.push(reference);
      incoming.set(reference.to, rows);
    }
    const nodes = new Map(model.nodes.map(node => [node.key, node]));
    const best = new Map([[target, {distance: 0, path: []}]]);
    let frontier = [target];
    while (frontier.length) {
      const candidates = new Map();
      for (const key of frontier) {
        const found = best.get(key);
        const rows = (incoming.get(key) || []).slice().sort((left, right) =>
          left.from.localeCompare(right.from) || left.relation.localeCompare(right.relation) ||
          left.locator.localeCompare(right.locator) || left.to.localeCompare(right.to));
        for (const reference of rows) {
          if (reference.from === target || best.has(reference.from)) continue;
          const candidate = {distance: found.distance + 1, path: [reference, ...found.path]};
          const previous = candidates.get(reference.from);
          if (!previous || JSON.stringify(candidate.path) < JSON.stringify(previous.path)) {
            candidates.set(reference.from, candidate);
          }
        }
      }
      frontier = [...candidates.keys()].sort();
      for (const key of frontier) best.set(key, candidates.get(key));
    }
    const affected = [...best.entries()].filter(([key]) => key !== target).map(([key, found]) => {
      const node = nodes.get(key);
      return {
        key, kind: node.kind, id: node.id, title: node.title,
        distance: found.distance, path: found.path
      };
    }).sort((left, right) =>
      left.distance - right.distance || left.key.localeCompare(right.key));
    return {target, affected};
  }

  function neighbors(model, index) {
    const result = new Set();
    for (const [from, to] of list(model?.edges)) {
      if (from === index) result.add(to);
      else if (to === index) result.add(from);
    }
    return result;
  }

  // Contiguous weighted partitions retain map order while giving crowded groups
  // more room. A small reserve keeps sparse/empty domain labels from collapsing.
  function partition(groups, box, cells) {
    if (groups.length === 1) { cells.set(groups[0].id, box); return; }
    const total = groups.reduce((sum, group) => sum + group.weight, 0);
    let sum = 0, split = 1, best = Infinity, portion = 0;
    for (let index = 1; index < groups.length; index++) {
      sum += groups[index - 1].weight;
      const difference = Math.abs(total / 2 - sum);
      if (difference < best) { best = difference; split = index; portion = sum / total; }
    }
    const across = box.width >= box.height;
    const first = {...box}, second = {...box};
    if (across) {
      first.width = box.width * portion;
      second.x += first.width; second.width -= first.width;
    } else {
      first.height = box.height * portion;
      second.y += first.height; second.height -= first.height;
    }
    partition(groups.slice(0, split), first, cells);
    partition(groups.slice(split), second, cells);
  }

  function clusterLayout(model, domains, width = 1200, height = 720) {
    width = Number.isFinite(width) && width > 0 ? width : 1200;
    height = Number.isFinite(height) && height > 0 ? height : 720;
    const nodes = list(model?.nodes);
    const groups = domainList(domains).map(domain => ({
      id: domain.id, title: domain.title || domain.id, english: domain.english || "", indices: []
    }));
    const byId = new Map(groups.map(group => [group.id, group]));
    const unclassified = {id: "unclassified", title: "未分类", english: "Unclassified", indices: []};
    nodes.forEach((node, index) => {
      (byId.get(node.primaryDomain) || unclassified).indices.push(index);
    });
    if (unclassified.indices.length) groups.push(unclassified);
    if (!groups.length) return {width, height, groups: [], positions: []};

    const margin = Math.min(44, width * .08, height * .08);
    const cells = new Map();
    partition(groups.map(group => ({id: group.id, weight: group.indices.length + 8})), {
      x: margin, y: margin, width: width - margin * 2, height: height - margin * 2
    }, cells);
    const positions = new Array(nodes.length);
    const anchors = groups.map(group => {
      const box = cells.get(group.id);
      const inset = Math.min(20, box.width * .12, box.height * .12);
      const heading = Math.min(44, box.height * .25);
      const left = box.x + inset, top = box.y + inset + heading;
      const right = box.x + box.width - inset, bottom = box.y + box.height - inset;
      const count = group.indices.length;
      const centerX = (left + right) / 2, centerY = (top + bottom) / 2;
      const radiusX = (right - left) / 2, radiusY = (bottom - top) / 2;
      // The golden-angle disk spreads points without mutable/random state; it
      // remains local to this group's allotted rectangle even for skewed data.
      group.indices.forEach((index, ordinal) => {
        const angle = ordinal * Math.PI * (3 - Math.sqrt(5)) - Math.PI / 2;
        const radius = count === 1 ? 0 : Math.sqrt((ordinal + .5) / count);
        positions[index] = {
          x: centerX + Math.cos(angle) * radiusX * radius,
          y: centerY + Math.sin(angle) * radiusY * radius
        };
      });
      return {id: group.id, title: group.title, english: group.english, x: left, y: box.y + inset};
    });
    return {width, height, groups: anchors, positions};
  }

  return {referenceGraph, graph, impact, neighbors, clusterLayout};
});
