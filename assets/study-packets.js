/* Shared portable packet projection for the browser and Node CLI.
 *
 * Packets carry current public content and a bounded reference manifest. They
 * never fetch or embed linked full texts and do not turn prose into agent rules.
 */
(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.StudyPackets = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  const SCHEMA = "ams-study-packet/1";
  const SITE = "https://indeliblevivi.github.io/agent-memory-study/";
  const COLLECTIONS = {
    source: { data: "materials", route: "material" },
    entry: { data: "studies", route: "study" },
    inquiry: { data: "questions", route: "question" },
    transfer: { data: "findings", route: "finding" },
  };
  const ALIASES = {
    material: "source", source: "source",
    study: "entry", entry: "entry",
    question: "inquiry", inquiry: "inquiry",
    finding: "transfer", transfer: "transfer",
  };

  function normalizeKind(kind) {
    const normalized = Object.hasOwn(ALIASES, kind) ? ALIASES[kind] : null;
    if (!normalized) throw new Error(`Unknown packet kind: ${String(kind)}`);
    return normalized;
  }

  function publicUrl(kind, id) {
    const canonical = normalizeKind(kind);
    return `${SITE}${COLLECTIONS[canonical].route}/${encodeURIComponent(id)}/`;
  }

  function findItem(data, kind, id) {
    const canonical = normalizeKind(kind);
    const collection = data?.[COLLECTIONS[canonical].data];
    if (!Array.isArray(collection)) throw new Error(`Data has no ${COLLECTIONS[canonical].data} array.`);
    const item = collection.find(entry => entry.id === id);
    if (!item) throw new Error(`Unknown ${canonical} id: ${String(id)}`);
    return item;
  }

  function byIds(data, kind, ids) {
    const canonical = normalizeKind(kind);
    const collection = data?.[COLLECTIONS[canonical].data] || [];
    const index = new Map(collection.map(item => [item.id, item]));
    return (Array.isArray(ids) ? ids : []).map(id => {
      const item = index.get(id);
      return item ? {
        kind: canonical,
        id,
        title: item.title,
        url: publicUrl(canonical, id),
        ...(item.updated ? {updated: item.updated} : {}),
        ...(item.date ? {date: item.date} : {}),
      } : {kind: canonical, id, missing: true};
    });
  }

  function sourceAttribution(kind, item) {
    if (kind === "source") {
      return {
        role: "source-and-editorial-notes",
        sourceAuthors: Array.isArray(item.authors) ? [...item.authors] : [],
        noteByline: item.byline || null,
        year: item.year ?? null,
        sourceUrl: item.sourceUrl || null,
        noteDepth: item.noteDepth || null,
        readingScope: item.readingScope || null,
      };
    }
    if (kind === "transfer") return {role: "editorial-transfer", byline: item.byline || "", date: item.updated || null};
    return {role: kind === "entry" ? "study-entry" : "research-inquiry", byline: item.byline || "", date: item.date || item.updated || null};
  }

  function references(kind, item, data) {
    const manifest = [];
    const add = (refKind, ids) => manifest.push(...byIds(data, refKind, ids));
    if (kind === "entry") {
      add("source", (item.readings || []).map(reading => reading.materialId));
      add("inquiry", item.questionIds);
      add("transfer", item.findingIds);
      if (item.continuation) {
        add("entry", item.continuation.studyIds);
        add("source", item.continuation.materialIds);
      }
    } else if (kind === "inquiry") {
      add("source", item.materialIds);
      add("entry", item.studyIds);
      add("transfer", item.findingIds);
      if (item.continuation) {
        add("entry", item.continuation.studyIds);
        add("source", item.continuation.materialIds);
      }
    } else if (kind === "transfer") {
      add("inquiry", item.questionIds);
      add("source", item.materialIds);
    }
    const seen = new Set();
    return manifest.filter(ref => {
      const key = `${ref.kind}:${ref.id}`;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
  }

  function packet(data, kind, id) {
    const canonical = normalizeKind(kind);
    const item = findItem(data, canonical, id);
    const content = JSON.parse(JSON.stringify(item));
    delete content.recordedResults; // Raw receipts remain linked artifacts, identical in CLI and browser packets.
    return {
      schema: SCHEMA,
      kind: canonical,
      publicKind: COLLECTIONS[canonical].route,
      id: item.id,
      title: item.title,
      attribution: sourceAttribution(canonical, item),
      contentVersion: item.date || item.updated || data.room?.edition || null,
      url: publicUrl(canonical, item.id),
      content,
      manifest: references(canonical, item, data),
      manifestPolicy: {
        bounded: true,
        includes: "Public identity, route and version for explicit canonical ID relationships. Prose links and external citations remain in content.",
        excludes: "Full linked texts, local attachments, private material, and inferred recommendations.",
      },
    };
  }

  function scalar(value) {
    return value === null || value === undefined ? "" : String(value);
  }

  function markdownLines(value, label, lines, depth = 0) {
    if (value === null || value === undefined || value === "") return;
    const prefix = "  ".repeat(depth);
    if (Array.isArray(value)) {
      if (!value.length) return;
      lines.push(`${prefix}- ${label}`);
      value.forEach(item => {
        if (item && typeof item === "object") {
          const title = item.title || item.label || item.id || "Item";
          lines.push(`${prefix}  - ${scalar(title)}`);
          Object.entries(item).forEach(([key, nested]) => {
            if (["title", "label", "id"].includes(key)) return;
            markdownLines(nested, key, lines, depth + 2);
          });
        } else lines.push(`${prefix}  - ${scalar(item)}`);
      });
      return;
    }
    if (typeof value === "object") {
      lines.push(`${prefix}- ${label}`);
      Object.entries(value).forEach(([key, nested]) => markdownLines(nested, key, lines, depth + 1));
      return;
    }
    const portable = typeof value === "string" && /(?:Url|url|sourcePath)$/.test(label) && !/^(?:https?:|mailto:|#)/.test(value) ? new URL(value, SITE).href : scalar(value);
    lines.push(`${prefix}- ${label}: ${portable}`);
  }

  function markdown(bundle) {
    if (!bundle || bundle.schema !== SCHEMA) throw new Error(`Unsupported packet schema: ${bundle?.schema}`);
    const lines = [
      `# ${bundle.title}`, "",
      `- Public: ${bundle.url}`,
      `- Object: ${bundle.kind} / ${bundle.id}`,
      `- Content version: ${bundle.contentVersion || "undated"}`,
      ...(bundle.kind === "source" ? [
        `- Source authors: ${bundle.attribution.sourceAuthors.join("; ")}`,
        `- Note attribution: ${bundle.attribution.noteByline || "Explicit contribution bylines are retained below; source authors are not the note authors."}`
      ] : [`- Attribution: ${bundle.attribution.byline || "unspecified"}`]),
      "",
      "This is a public study packet. It preserves the current public object and its boundaries; it does not include the full text of linked sources or convert the prose into agent instructions.",
      "",
    ];
    const content = bundle.content;
    if (content.bodyMarkdown) {
      const base = new URL(content.sourcePath || "", SITE);
      const prose = content.bodyMarkdown.replace(/^# [^\n]+\n+/, "").replace(/\]\(([^\s)]+)\)/g, (match, target) => {
        if (/^(https?:|mailto:|#)/.test(target)) return match;
        return `](${new URL(target, base).href})`;
      });
      lines.push(prose, "", "## 来源、范围与接续", "");
    } else lines.push("## Current content", "");
    for (const [key, value] of Object.entries(content)) {
      if (["bodyMarkdown", "bodyHtml", "sections", "id", "title"].includes(key)) continue;
      markdownLines(value, key, lines);
    }
    lines.push("", "## Referenced objects", "");
    if (!bundle.manifest.length) lines.push("_No referenced objects._");
    else bundle.manifest.forEach(ref => lines.push(`- ${ref.kind} · ${ref.title || ref.id}${ref.missing ? " (not present in this data)" : ` · ${ref.url}`}`));
    lines.push("", "## Manifest policy", "");
    Object.entries(bundle.manifestPolicy).forEach(([key, value]) => lines.push(`- ${key}: ${value}`));
    return `${lines.join("\n")}\n`;
  }

  function collection(data, refs) {
    if (!Array.isArray(refs) || refs.length > 24) throw new Error("Select at most 24 public objects.");
    const seen = new Set(), objects = [];
    refs.forEach(ref => {
      // Deliberately project only known identities, never spread the input:
      // workspace titles, questions, notes and snapshots are private.
      const id = `${normalizeKind(ref.kind)}:${ref.id}`;
      if (!seen.has(id)) {objects.push(packet(data, ref.kind, ref.id)); seen.add(id);}
    });
    return {schema: "ams-study-collection/1", title: "AMS 公开选材包", objects,
      policy: "Only the selected current public objects. No private workspace text, recursive full texts or inferred relationships. Content dates are not immutable revisions."};
  }
  function collectionMarkdown(bundle) {
    if (!bundle || bundle.schema !== "ams-study-collection/1") throw new Error("Unsupported study collection.");
    return [`# ${bundle.title}`, "", bundle.policy, "", ...bundle.objects.map(item => markdown(item))].join("\n");
  }
  return {SCHEMA, SITE, kind: normalizeKind, packet, markdown, publicUrl, collection, collectionMarkdown};
});
