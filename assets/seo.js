/* Shared by the interactive reader and its build-time browser renderer. */
(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.AMS_SEO = api;
})(typeof window === "undefined" ? globalThis : window, function () {
  "use strict";
  const site = "https://indeliblevivi.github.io/agent-memory-study/";
  const kinds = ["material", "study", "question", "finding"];
  const collections = { material: "materials", study: "studies", question: "questions", finding: "findings" };
  const routeKeys = [...kinds, "practice", "scenario", "phase", "thread", "path", "q", "topic", "surface", "depth"];

  function pathFor(route) {
    const kind = kinds.find(key => route[key]);
    return kind ? `${kind}/${encodeURIComponent(route[kind])}/` : "";
  }

  function pathRoute(url, base) {
    if (!url.pathname.startsWith(base.pathname)) return null;
    const parts = url.pathname.slice(base.pathname.length).replace(/index\.html$/, "").split("/").filter(Boolean);
    return parts.length === 2 && kinds.includes(parts[0]) ? { [parts[0]]: decodeURIComponent(parts[1]) } : null;
  }

  function routeUrl(route, current, base, physical, hash = "") {
    const url = new URL(current);
    routeKeys.forEach(key => url.searchParams.delete(key));
    if (physical) url.pathname = new URL(pathFor(route), base).pathname;
    for (const kind of kinds) if (!physical && route[kind]) url.searchParams.set(kind, route[kind]);
    for (const key of ["practice", "thread", "path", "q", "topic", "depth"]) {
      if (route[key]) url.searchParams.set(key, route[key]);
    }
    if (route.surface && route.surface !== route.thread) url.searchParams.set("surface", route.surface);
    if (route.study && route.scenario) url.searchParams.set("scenario", route.scenario);
    if (route.study && route.phase === "after") url.searchParams.set("phase", "after");
    url.hash = hash;
    return `${url.pathname}${url.search}${url.hash}`;
  }

  function metadata(data, route) {
    const kind = kinds.find(key => route[key]);
    const item = kind && data[collections[kind]].find(entry => entry.id === route[kind]);
    const name = "Agent Memory Study";
    const title = item ? `${item.title} · ${kind === "material" ? "阅读笔记 · " : ""}${name}` : `${name} · Agent memory 阅读与研究`;
    const text = item
      ? (kind === "material" ? `阅读范围：${item.noteDepth}。${item.intro}` : item.question || item.claim || item.intro)
      : "关于 agent memory、learning 与 cognitive architecture 的公开研究空间：原文与实现、可复跑实验、问题专题和有范围的实践判断。";
    const normalized = text.replace(/\s+/g, " ").trim();
    const description = normalized.length > 200 ? normalized.slice(0, 197) + "…" : normalized;
    const canonical = new URL(item ? pathFor(route) : "", site).href;
    const structured = {
      "@context": "https://schema.org", "@type": item ? "WebPage" : "WebSite",
      name: title, url: canonical, description, inLanguage: "zh-CN",
    };
    if (item) structured.isPartOf = { "@type": "WebSite", name, url: site };
    // Paper authors wrote the cited source, not this site's editorial reading note.
    if (kind === "material") structured.about = { "@type": "CreativeWork", name: item.title, url: item.sourceUrl };
    return { title, description, canonical, structured, image: new URL("assets/icons/ams-icon-512.png", site).href };
  }
  return { site, kinds, routeKeys, pathFor, pathRoute, routeUrl, metadata };
});
