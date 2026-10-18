/* Public object relationships and editorial domain layout. Neither connections
   nor coordinates imply similarity, ranking, or evidence beyond explicit links. */
(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.ResearchMap = api;
})(typeof globalThis === "object" ? globalThis : this, function () {
  "use strict";

  const families = {study: "studies", material: "materials", question: "questions", finding: "findings"};
  const references = [["materialIds", "material"], ["studyIds", "study"], ["questionIds", "question"], ["findingIds", "finding"]];
  const list = value => Array.isArray(value) ? value : [];

  function domainList(domains) {
    const seen = new Set();
    return list(domains).filter(domain => {
      if (!domain || typeof domain.id !== "string" || !domain.id || seen.has(domain.id)) return false;
      seen.add(domain.id);
      return true;
    });
  }

  function graph(data = {}) {
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
    const byKey = new Map(nodes.map((node, index) => [node.key, index]));
    const edges = [], seen = new Set();
    function connect(from, kind, id) {
      if (typeof id !== "string") return;
      const to = byKey.get(`${kind}/${id}`);
      if (to === undefined || from === to) return;
      const key = `${Math.min(from, to)}:${Math.max(from, to)}`;
      if (!seen.has(key)) { seen.add(key); edges.push([from, to]); }
    }
    nodes.forEach((node, index) => {
      const item = node.item;
      for (const [field, kind] of references) {
        list(item[field]).forEach(id => connect(index, kind, id));
        list(item.continuation?.[field]).forEach(id => connect(index, kind, id));
      }
      list(item.readings).forEach(reading => connect(index, "material", reading.materialId));
      // The compiler emits double-quoted, query-relative anchors for known routes.
      // Do not scan prose, external URLs, tags, or shared domain membership for edges.
      const html = typeof item.bodyHtml === "string" ? item.bodyHtml : "";
      for (const match of html.matchAll(/<a\b[^>]*?\shref="(\?[^\"]*)"[^>]*>/g)) {
        const query = new URLSearchParams(match[1].slice(1).split("#", 1)[0].replaceAll("&amp;", "&"));
        for (const kind of Object.keys(families)) {
          if (query.has(kind)) connect(index, kind, query.get(kind));
        }
      }
    });
    return {nodes, edges};
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

  return {graph, neighbors, clusterLayout};
});
