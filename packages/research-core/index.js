/* Pure contracts for source identity, navigation, directed references, and packets.
 * The compiler owns Markdown; this module never parses HTML to infer references.
 */
export const CONTRACT_VERSION = "ams-core/2";
export const COMPILER_VERSION = "ams-content-compiler/2";
export const PACKET_VERSION = "ams-study-packet/2";
export const COLLECTION_VERSION = "ams-study-collection/2";
export const PUBLIC_MANIFEST_VERSION = "ams-public-corpus-manifest/1";

const families = {
  source_note: { publicKind: "material", field: "materials" },
  entry: { publicKind: "study", field: "studies" },
  thread: { publicKind: "question", field: "questions" },
  claim_revision: { publicKind: "finding", field: "findings" },
};

export const PUBLIC_KINDS = Object.fromEntries(
  Object.entries(families).map(([kind, value]) => [value.publicKind, kind]),
);

export function entityRef(record) {
  if (!record || typeof record !== "object" || typeof record.kind !== "string" ||
      typeof record.id !== "string" || typeof record.revision !== "string") {
    throw new Error("entityRef: record requires kind, id and revision");
  }
  return { kind: record.kind, id: record.id, revision: record.revision };
}

export function refKey(ref) {
  if (!ref || typeof ref !== "object") throw new Error("refKey: expected a reference");
  return `${ref.kind}:${ref.id}@${ref.revision}`;
}

export function publicRef(publicKind, id, revision = null) {
  const kind = PUBLIC_KINDS[publicKind];
  if (!kind || typeof id !== "string" || !id) throw new Error(`unknown public kind: ${publicKind}`);
  return revision ? { kind, id, revision } : { kind, id };
}

export function referenceGraph(manifest) {
  if (!manifest || manifest.schema !== PUBLIC_MANIFEST_VERSION) {
    throw new Error(`referenceGraph: expected ${PUBLIC_MANIFEST_VERSION}`);
  }
  const references = Array.isArray(manifest.graphs?.references) ? manifest.graphs.references : [];
  const nodes = manifest.objects.map(item => ({
    key: `${item.public_kind}/${item.public_id}`,
    kind: item.public_kind,
    id: item.public_id,
    revision: item.revision,
    route: item.route,
  }));
  const known = new Set(nodes.map(node => node.key));
  for (const ref of references) {
    if (!known.has(ref.from) || !known.has(ref.to)) {
      throw new Error(`referenceGraph: dangling reference ${ref.from} -> ${ref.to}`);
    }
  }
  return { nodes, references: references.map(ref => ({ ...ref })) };
}

export function navigationOf(manifest) {
  if (!manifest || manifest.schema !== PUBLIC_MANIFEST_VERSION) {
    throw new Error(`navigationOf: expected ${PUBLIC_MANIFEST_VERSION}`);
  }
  return (manifest.graphs.navigation_memberships || []).map(item => ({ ...item }));
}

export function argumentOf(manifest) {
  if (!manifest || manifest.schema !== PUBLIC_MANIFEST_VERSION) {
    throw new Error(`argumentOf: expected ${PUBLIC_MANIFEST_VERSION}`);
  }
  return (manifest.graphs.arguments || []).map(item => ({ ...item }));
}

export function impact(manifest, publicKind, id) {
  if (!Object.hasOwn(PUBLIC_KINDS, publicKind) || typeof id !== "string" || !id) {
    throw new Error("impact: expected a known public kind and id");
  }
  const graph = referenceGraph(manifest);
  const target = `${publicKind}/${id}`;
  if (!graph.nodes.some(node => node.key === target)) throw new Error(`impact: unknown ${target}`);
  const incoming = new Map();
  for (const reference of graph.references) {
    if (reference.relation === "navigation") continue;
    const rows = incoming.get(reference.to) || [];
    rows.push(reference);
    incoming.set(reference.to, rows);
  }
  const best = new Map([[target, { distance: 0, path: [] }]]);
  let frontier = [target];
  while (frontier.length) {
    const next = new Map();
    for (const key of frontier.sort()) {
      const found = best.get(key);
      for (const reference of (incoming.get(key) || []).slice().sort((a, b) =>
        a.from.localeCompare(b.from) || a.locator.localeCompare(b.locator))) {
        if (reference.from === target || best.has(reference.from)) continue;
        const candidate = { distance: found.distance + 1, path: [reference, ...found.path] };
        const previous = next.get(reference.from);
        if (!previous || JSON.stringify(candidate.path) < JSON.stringify(previous.path)) {
          next.set(reference.from, candidate);
        }
      }
    }
    frontier = [...next.keys()].sort();
    for (const key of frontier) best.set(key, next.get(key));
  }
  const byKey = new Map(graph.nodes.map(node => [node.key, node]));
  return {
    target,
    affected: [...best.entries()].filter(([key]) => key !== target).map(([key, result]) => ({
      ...byKey.get(key), ...result,
    })).sort((left, right) => left.distance - right.distance || left.key.localeCompare(right.key)),
  };
}

function routeFor(kind, id) {
  return `https://indeliblevivi.github.io/agent-memory-study/${kind}/${encodeURIComponent(id)}/`;
}

export function packet(manifest, publicKind, id, loaded = null) {
  if (loaded) return packetFromShards(manifest, publicKind, id, loaded);
  throw new Error("packet: load packetShardPath(manifest, kind, id) first");
}

export function objectFor(manifest, publicKind, id) {
  const object = manifest?.objects?.find(item =>
    item.public_kind === publicKind && (item.public_id === id || item.id === id));
  if (!object) throw new Error(`objectFor: unknown ${publicKind}:${id}`);
  return { ...object };
}

export function objectShardPath(manifest, publicKind, id) {
  return objectFor(manifest, publicKind, id).shard;
}

export function packetShardPath(manifest, publicKind, id) {
  return objectFor(manifest, publicKind, id).packet_v2;
}

export function revisionShardPath(manifest, publicKind, id) {
  return objectFor(manifest, publicKind, id).revision_shard;
}

export function packetFromShards(manifest, publicKind, id, loaded = {}) {
  const object = objectFor(manifest, publicKind, id);
  const value = loaded[object.packet_v2] || loaded[id] ||
    (loaded.schema === PACKET_VERSION ? loaded : null);
  if (!value) throw new Error(`packetFromShards: load ${object.packet_v2} first`);
  if (value.schema !== PACKET_VERSION) throw new Error(`packetFromShards: expected ${PACKET_VERSION}`);
  if (value.id !== object.public_id || value.kind !== object.public_kind) {
    throw new Error("packetFromShards: packet identity differs from manifest");
  }
  return JSON.parse(JSON.stringify(value));
}

export function collection(manifest, refs, loaded = {}) {
  if (!Array.isArray(refs) || refs.length > 24) throw new Error("collection: select at most 24 objects");
  const seen = new Set();
  const objects = [];
  for (const ref of refs) {
    const value = packetFromShards(manifest, ref.kind, ref.id, loaded);
    const key = `${value.kind}:${value.id}`;
    if (!seen.has(key)) { seen.add(key); objects.push(value); }
  }
  return {
    schema: COLLECTION_VERSION,
    title: "AMS 公开选材包",
    objects,
    policy: "Only selected current public objects; no private workspace text, recursive full text, or inferred relationships.",
  };
}

export function packetPublicRoute(kind, id) {
  if (!Object.hasOwn(PUBLIC_KINDS, kind)) throw new Error(`unknown public kind: ${kind}`);
  return routeFor(kind, id);
}
