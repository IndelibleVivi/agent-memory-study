(() => {
  "use strict";

  const data = window.READING_ROOM;
  if (
    !data
    || !Array.isArray(data.materials)
    || data.materials.length === 0
    || !data.atlas
    || !Array.isArray(data.atlas.failureSurfaces)
    || !Array.isArray(data.atlas.readingPaths)
  ) {
    document.body.textContent = "阅读室的 public data 缺失或不完整。";
    return;
  }

  const materialsById = new Map(data.materials.map((material) => [material.id, material]));
  const surfacesById = new Map(data.atlas.failureSurfaces.map((surface) => [surface.id, surface]));
  const pathsById = new Map(data.atlas.readingPaths.map((path) => [path.id, path]));
  const routeKeys = ["material", "thread", "path", "q", "topic", "surface", "depth"];
  const depthOrder = ["abstract", "skim", "read", "worked"];
  const svgNamespace = "http://www.w3.org/2000/svg";
  const constellationViewBox = { width: 1200, height: 680 };
  const constellationAnchorOverrides = new Map([
    ["state-representation", { x: 165, y: 190, labelX: 116, labelY: 133, textAnchor: "start" }],
    ["write-consolidation", { x: 430, y: 350, labelX: 380, labelY: 418, textAnchor: "middle" }],
    ["retrieval-active-context", { x: 650, y: 170, labelX: 650, labelY: 104, textAnchor: "middle" }],
    ["wake-prospective-action", { x: 1015, y: 255, labelX: 1080, labelY: 205, textAnchor: "end" }],
    ["abstraction-experience", { x: 720, y: 530, labelX: 720, labelY: 610, textAnchor: "middle" }],
    ["metacognitive-control", { x: 915, y: 78, labelX: 965, labelY: 42, textAnchor: "middle" }],
    ["justification-revision", { x: 180, y: 540, labelX: 116, labelY: 611, textAnchor: "start" }],
  ]);
  const constellationAnchors = new Map(data.atlas.failureSurfaces.map((surface, index, surfaces) => {
    const fixed = constellationAnchorOverrides.get(surface.id);
    if (fixed) return [surface.id, fixed];
    const angle = -Math.PI / 2 + (index * Math.PI * 2) / surfaces.length;
    const x = constellationViewBox.width / 2 + Math.cos(angle) * 450;
    const y = constellationViewBox.height / 2 + Math.sin(angle) * 250;
    return [surface.id, {
      x,
      y,
      labelX: x + Math.cos(angle) * 58,
      labelY: y + Math.sin(angle) * 58,
      textAnchor: Math.cos(angle) < -0.2 ? "end" : Math.cos(angle) > 0.2 ? "start" : "middle",
    }];
  }));
  let route = readRoute();
  let articleObserver = null;

  const refs = {
    atlasView: document.querySelector("#atlas-view"),
    materialView: document.querySelector("#material-view"),
    atlasTitle: document.querySelector("#atlas-title"),
    atlasDek: document.querySelector("#atlas-dek"),
    atlasLabel: document.querySelector("#atlas-label"),
    surfaceList: document.querySelector("#surface-list"),
    surfaceFocus: document.querySelector("#surface-focus"),
    surfaceFocusIndex: document.querySelector("#surface-focus-index"),
    surfaceFocusTitle: document.querySelector("#surface-focus-title"),
    surfaceFocusQuestion: document.querySelector("#surface-focus-question"),
    surfaceFocusTension: document.querySelector("#surface-focus-tension"),
    surfaceMaterials: document.querySelector("#surface-materials"),
    constellationStats: document.querySelector("#constellation-stats"),
    constellationPlot: document.querySelector("#constellation-plot"),
    constellationMatrix: document.querySelector("#constellation-matrix"),
    constellationReadingIndex: document.querySelector("#constellation-reading-index"),
    constellationReadingTitle: document.querySelector("#constellation-reading-title"),
    constellationReadingMeta: document.querySelector("#constellation-reading-meta"),
    constellationReadingCopy: document.querySelector("#constellation-reading-copy"),
    constellationReadingLinks: document.querySelector("#constellation-reading-links"),
    pathGrid: document.querySelector("#path-grid"),
    pathFocus: document.querySelector("#path-focus"),
    libraryControls: document.querySelector("#library-controls"),
    search: document.querySelector("#search"),
    topicFilter: document.querySelector("#topic-filter"),
    surfaceFilter: document.querySelector("#surface-filter"),
    depthFilter: document.querySelector("#depth-filter"),
    clearFilters: document.querySelector("#clear-filters"),
    materialIndex: document.querySelector("#material-index"),
    resultCount: document.querySelector("#result-count"),
    librarySummary: document.querySelector("#library-summary"),
    emptyState: document.querySelector("#empty-state"),
    editorialNote: document.querySelector("#editorial-note"),
    architectureNote: document.querySelector("#architecture-note"),
    architectureLine: document.querySelector("#architecture-line"),
    architectureReveal: document.querySelector("#architecture-reveal"),
    materialNumber: document.querySelector("#material-number"),
    materialTitle: document.querySelector("#material-title"),
    materialMeta: document.querySelector("#material-meta"),
    materialSurfaceLinks: document.querySelector("#material-surface-links"),
    materialIntro: document.querySelector("#material-intro"),
    materialPoints: document.querySelector("#material-points"),
    argumentSection: document.querySelector("#paper-argument"),
    materialArgumentMap: document.querySelector("#material-argument-map"),
    methodSection: document.querySelector("#paper-method"),
    materialMethodNotes: document.querySelector("#material-method-notes"),
    findingsSection: document.querySelector("#paper-findings"),
    materialFindings: document.querySelector("#material-findings"),
    materialLimits: document.querySelector("#material-limits"),
    limitsFallback: document.querySelector("#limits-fallback"),
    tensionsSection: document.querySelector("#paper-tensions"),
    materialTensions: document.querySelector("#material-tensions"),
    whyReadBlock: document.querySelector("#why-read-block"),
    materialWhyRead: document.querySelector("#material-why-read"),
    materialInferences: document.querySelector("#material-inferences"),
    materialQuestion: document.querySelector("#material-question"),
    protocolsSection: document.querySelector("#paper-protocols"),
    materialProtocols: document.querySelector("#material-protocols"),
    contributionsSection: document.querySelector("#paper-contributions"),
    materialContributions: document.querySelector("#material-contributions"),
    articleToc: document.querySelector("#article-toc"),
    sourceRail: document.querySelector("#source-rail"),
    sourceMobile: document.querySelector("#paper-source-mobile"),
    routeStatus: document.querySelector("#route-status"),
    menuButton: document.querySelector("#menu-button"),
    siteNav: document.querySelector("#site-nav"),
  };

  function readRoute() {
    const params = new URLSearchParams(window.location.search);
    const material = materialsById.has(params.get("material")) ? params.get("material") : null;
    const thread = surfacesById.has(params.get("thread")) ? params.get("thread") : null;
    const path = pathsById.has(params.get("path")) ? params.get("path") : null;
    const topic = data.filters.includes(params.get("topic")) ? params.get("topic") : "";
    const explicitSurface = surfacesById.has(params.get("surface")) ? params.get("surface") : "";
    const depth = depthOrder.includes(params.get("depth")) ? params.get("depth") : "";
    return {
      material,
      thread,
      path,
      q: params.get("q") || "",
      topic,
      surface: explicitSurface || thread || "",
      depth,
    };
  }

  function routeUrl(nextRoute, hash = "") {
    const url = new URL(window.location.href);
    routeKeys.forEach((key) => url.searchParams.delete(key));
    if (nextRoute.material) url.searchParams.set("material", nextRoute.material);
    if (nextRoute.thread) url.searchParams.set("thread", nextRoute.thread);
    if (nextRoute.path) url.searchParams.set("path", nextRoute.path);
    if (nextRoute.q) url.searchParams.set("q", nextRoute.q);
    if (nextRoute.topic) url.searchParams.set("topic", nextRoute.topic);
    if (nextRoute.surface && nextRoute.surface !== nextRoute.thread) {
      url.searchParams.set("surface", nextRoute.surface);
    }
    if (nextRoute.depth) url.searchParams.set("depth", nextRoute.depth);
    url.hash = hash;
    return `${url.pathname}${url.search}${url.hash}`;
  }

  function navigate(nextRoute, options = {}) {
    const { replace = false, hash = "", focus = true } = options;
    route = {
      ...route,
      ...nextRoute,
    };
    const method = replace ? "replaceState" : "pushState";
    window.history[method]({}, "", routeUrl(route, hash));
    render({ focus, hash });
  }

  function normalize(value) {
    return String(value || "").toLocaleLowerCase("zh-CN").normalize("NFKC");
  }

  function routeHref(type, id) {
    const next = { ...route, material: null, thread: null, path: null };
    if (type === "material") next.material = id;
    if (type === "thread") {
      next.thread = id;
      next.surface = id;
    }
    if (type === "path") next.path = id;
    return routeUrl(next);
  }

  function createRouteLink(type, id, text, className = "") {
    const link = document.createElement("a");
    link.href = routeHref(type, id);
    link.dataset.route = type;
    link.dataset.routeId = id;
    link.className = className;
    link.textContent = text;
    return link;
  }

  function createExternalLink(href, text, className = "") {
    const link = document.createElement("a");
    link.href = href;
    link.textContent = text;
    link.className = className;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    return link;
  }

  function createTextElement(tag, text, className = "") {
    const node = document.createElement(tag);
    node.textContent = text;
    node.className = className;
    return node;
  }

  function renderEasterEggs() {
    const easterEgg = data.atlas.easterEgg;
    const [before, after] = data.atlas.thesis.split(easterEgg.heroWord);
    const word = document.createElement("button");
    word.type = "button";
    word.className = "easter-word";
    word.dataset.easter = "hero";
    word.dataset.original = easterEgg.heroWord;
    word.dataset.reveal = easterEgg.heroReveal;
    word.setAttribute("aria-pressed", "false");
    word.setAttribute(
      "aria-label",
      `${easterEgg.heroWord}. Activate to reveal ${easterEgg.heroReveal}.`,
    );
    const original = createTextElement("span", easterEgg.heroWord, "easter-word-original");
    const reveal = createTextElement("span", easterEgg.heroReveal, "easter-word-reveal");
    original.setAttribute("aria-hidden", "true");
    reveal.setAttribute("aria-hidden", "true");
    word.append(original, reveal);
    refs.atlasTitle.replaceChildren(document.createTextNode(before), word, document.createTextNode(after));

    refs.architectureLine.textContent = easterEgg.aboutLine;
    refs.architectureReveal.textContent = easterEgg.aboutReveal;
    refs.architectureNote.dataset.original = easterEgg.aboutLine;
    refs.architectureNote.dataset.reveal = easterEgg.aboutReveal;
    refs.architectureNote.setAttribute("aria-pressed", "false");
    refs.architectureNote.setAttribute(
      "aria-label",
      `${easterEgg.aboutLine} Activate to reveal a second line.`,
    );
  }

  function renderAtlasFrame() {
    renderEasterEggs();
    refs.atlasDek.textContent = data.atlas.dek;
    refs.atlasLabel.textContent = data.atlas.editorialLabel;
    refs.editorialNote.textContent = data.editorialNote;
    renderSurfaces();
    renderConstellation();
    renderPaths();
    syncControls();
    renderLibrary();
  }

  function selectedSurface() {
    return surfacesById.get(route.thread || route.surface) || null;
  }

  function renderSurfaces() {
    const selected = selectedSurface();
    const rows = data.atlas.failureSurfaces.map((surface) => {
      const item = document.createElement("li");
      const link = createRouteLink("thread", surface.id, "", "surface-link");
      if (surface.id === selected?.id) link.setAttribute("aria-current", "true");
      link.append(
        createTextElement("span", surface.number, "surface-number"),
        createTextElement("span", surface.label, "surface-label"),
        createTextElement("span", surface.question, "surface-summary"),
        createTextElement("span", "→", "surface-arrow"),
      );
      item.append(link);
      return item;
    });
    refs.surfaceList.replaceChildren(...rows);

    refs.surfaceFocus.hidden = !selected;
    if (!selected) {
      refs.surfaceFocusIndex.textContent = "";
      refs.surfaceFocusTitle.textContent = "";
      refs.surfaceFocusQuestion.textContent = "";
      refs.surfaceFocusTension.textContent = "";
      refs.surfaceMaterials.replaceChildren();
      return;
    }

    refs.surfaceFocusIndex.textContent = selected.number;
    refs.surfaceFocusTitle.textContent = selected.label;
    refs.surfaceFocusQuestion.textContent = selected.question;
    refs.surfaceFocusTension.textContent = selected.tension;
    refs.surfaceMaterials.replaceChildren(...selected.materialIds.map((materialId) => {
      const material = materialsById.get(materialId);
      const item = document.createElement("li");
      item.append(createRouteLink("material", material.id, material.title));
      return item;
    }));
  }

  function createSvgElement(tag, attributes = {}, text = "") {
    const node = document.createElementNS(svgNamespace, tag);
    Object.entries(attributes).forEach(([name, value]) => node.setAttribute(name, String(value)));
    if (text) node.textContent = text;
    return node;
  }

  function stableHash(value) {
    let hash = 2166136261;
    for (const character of value) {
      hash ^= character.codePointAt(0);
      hash = Math.imul(hash, 16777619);
    }
    return hash >>> 0;
  }

  function constellationPositions() {
    const positions = new Map();
    const placed = [];
    [...data.materials]
      .sort((left, right) => left.number - right.number)
      .forEach((material) => {
        const anchors = material.failureSurfaces.map((surfaceId) => constellationAnchors.get(surfaceId));
        const base = anchors.reduce(
          (point, anchor) => ({ x: point.x + anchor.x / anchors.length, y: point.y + anchor.y / anchors.length }),
          { x: 0, y: 0 },
        );
        const hash = stableHash(material.id);
        let angle = ((hash % 360) * Math.PI) / 180;
        let radius = anchors.length === 1 ? 72 + ((hash >>> 9) % 3) * 22 : 22 + ((hash >>> 11) % 3) * 13;
        let point = null;

        for (let attempt = 0; attempt < 14; attempt += 1) {
          point = {
            x: Math.max(54, Math.min(constellationViewBox.width - 54, base.x + Math.cos(angle) * radius)),
            y: Math.max(48, Math.min(constellationViewBox.height - 48, base.y + Math.sin(angle) * radius)),
          };
          const collides = placed.some((other) => Math.hypot(point.x - other.x, point.y - other.y) < 44);
          if (!collides) break;
          angle += 2.399963;
          radius += attempt % 2 === 0 ? 10 : 2;
        }

        point.angle = angle;
        positions.set(material.id, point);
        placed.push(point);
      });
    return positions;
  }

  function constellationContext() {
    const matches = matchingMaterials();
    const activePath = pathsById.get(route.path);
    const explicitSurfaceId = route.thread || route.surface;
    const hasFilter = Boolean(route.q || route.topic || route.surface || route.depth);
    return {
      matches,
      matchingIds: new Set(matches.map((material) => material.id)),
      activePath,
      pathIds: new Set(activePath ? activePath.materialIds : []),
      explicitSurfaceId,
      hasFilter,
      hasEmphasis: hasFilter || Boolean(activePath) || Boolean(explicitSurfaceId),
    };
  }

  function materialIsEmphasized(material, context) {
    if (context.activePath && !context.pathIds.has(material.id)) return false;
    if (context.explicitSurfaceId && !material.failureSurfaces.includes(context.explicitSurfaceId)) return false;
    if (context.hasFilter && !context.matchingIds.has(material.id)) return false;
    return true;
  }

  function setConstellationReading(kind = "default", item = null) {
    refs.constellationReadingLinks.replaceChildren();

    if (kind === "material" && item) {
      refs.constellationReadingIndex.textContent = String(item.number).padStart(2, "0");
      refs.constellationReadingTitle.textContent = item.title;
      refs.constellationReadingMeta.textContent = `${item.authors.join(", ")} · ${item.year} · ${item.noteDepth}`;
      refs.constellationReadingCopy.textContent = item.whyRead || item.intro;
      refs.constellationReadingLinks.append(createRouteLink("material", item.id, "打开这份材料 →"));
      return;
    }

    if (kind === "surface" && item) {
      refs.constellationReadingIndex.textContent = item.number;
      refs.constellationReadingTitle.textContent = item.label;
      refs.constellationReadingMeta.textContent = `${item.materialIds.length} 条材料进入这个 failure surface`;
      refs.constellationReadingCopy.textContent = `${item.question} ${item.tension}`;
      refs.constellationReadingLinks.append(createRouteLink("thread", item.id, "打开这个 failure surface →"));
      return;
    }

    if (kind === "path" && item) {
      refs.constellationReadingIndex.textContent = item.number;
      refs.constellationReadingTitle.textContent = item.title;
      refs.constellationReadingMeta.textContent = `${item.materialIds.length} 站 · 编者建议顺序`;
      refs.constellationReadingCopy.textContent = item.description;
      refs.constellationReadingLinks.append(createRouteLink("path", item.id, "查看路径顺序 →"));
      return;
    }

    const context = constellationContext();
    if (context.activePath) {
      setConstellationReading("path", context.activePath);
      return;
    }
    if (context.explicitSurfaceId) {
      setConstellationReading("surface", surfacesById.get(context.explicitSurfaceId));
      return;
    }
    if (context.hasFilter) {
      refs.constellationReadingIndex.textContent = String(context.matches.length).padStart(2, "0");
      refs.constellationReadingTitle.textContent = "当前筛选穿过的星域";
      refs.constellationReadingMeta.textContent = `${context.matches.length} / ${data.materials.length} 条材料保持清晰`;
      refs.constellationReadingCopy.textContent = "未匹配的星仍留在背景，方便看见筛选结果位于整张研究地图的哪里。清空筛选即可恢复全图。";
      return;
    }

    const bridges = data.materials.filter((material) => material.failureSurfaces.length > 1).length;
    refs.constellationReadingIndex.textContent = "∞";
    refs.constellationReadingTitle.textContent = "A field that grows with the reading";
    refs.constellationReadingMeta.textContent = `${data.materials.length} materials · ${bridges} cross-surface bridges`;
    refs.constellationReadingCopy.textContent = "固定的是 failure-surface 语义，不是星星数量。新增 public material 会从 canonical membership 自动进入这片星域；空白、孤立与密集都只描述当前 corpus。";
  }

  function setConstellationHover(kind, id, active) {
    const svg = refs.constellationPlot.querySelector("svg");
    if (!svg) return;
    svg.classList.toggle("has-hover", active);
    if (!active) {
      svg.querySelectorAll(".is-hover-match").forEach((node) => node.classList.remove("is-hover-match"));
      setConstellationReading();
      return;
    }

    const materialIds = kind === "material"
      ? new Set([id])
      : new Set(surfacesById.get(id).materialIds);
    const surfaceIds = kind === "surface"
      ? new Set([id])
      : new Set(materialsById.get(id).failureSurfaces);

    svg.querySelectorAll("[data-material-id]").forEach((node) => {
      node.classList.toggle("is-hover-match", materialIds.has(node.dataset.materialId));
    });
    svg.querySelectorAll("[data-surface-id]").forEach((node) => {
      node.classList.toggle("is-hover-match", surfaceIds.has(node.dataset.surfaceId));
    });
    svg.querySelectorAll(".constellation-edge").forEach((node) => {
      node.classList.toggle(
        "is-hover-match",
        materialIds.has(node.dataset.materialId) && surfaceIds.has(node.dataset.surfaceId),
      );
    });
    setConstellationReading(kind, kind === "material" ? materialsById.get(id) : surfacesById.get(id));
  }

  function renderConstellationPlot(positions, context) {
    const svg = createSvgElement("svg", {
      viewBox: `0 0 ${constellationViewBox.width} ${constellationViewBox.height}`,
      role: "img",
      "aria-labelledby": "constellation-svg-title constellation-svg-description",
      preserveAspectRatio: "xMidYMid meet",
    });
    svg.append(
      createSvgElement("title", { id: "constellation-svg-title" }, "Agent Memory Study research constellation"),
      createSvgElement(
        "desc",
        { id: "constellation-svg-description" },
        "Materials are connected to the failure surfaces used by the public atlas. Links open stable material and surface routes.",
      ),
    );

    const edges = createSvgElement("g", { class: "constellation-edges", "aria-hidden": "true" });
    data.materials.forEach((material) => {
      const point = positions.get(material.id);
      material.failureSurfaces.forEach((surfaceId) => {
        const anchor = constellationAnchors.get(surfaceId);
        const edge = createSvgElement("line", {
          x1: point.x,
          y1: point.y,
          x2: anchor.x,
          y2: anchor.y,
          class: "constellation-edge",
          "data-material-id": material.id,
          "data-surface-id": surfaceId,
        });
        if (context.hasEmphasis && !materialIsEmphasized(material, context)) edge.classList.add("is-dimmed");
        if (context.hasEmphasis && materialIsEmphasized(material, context)) edge.classList.add("is-emphasized");
        edges.append(edge);
      });
    });
    svg.append(edges);

    if (context.activePath) {
      const overlay = createSvgElement("g", { class: "constellation-path-overlay", "aria-hidden": "true" });
      context.activePath.materialIds.forEach((materialId, index, materialIds) => {
        const point = positions.get(materialId);
        if (index < materialIds.length - 1) {
          const next = positions.get(materialIds[index + 1]);
          overlay.append(createSvgElement("line", {
            x1: point.x,
            y1: point.y,
            x2: next.x,
            y2: next.y,
            class: "constellation-path-line",
          }));
        }
        overlay.append(createSvgElement("text", {
          x: point.x + 12,
          y: point.y - 12,
          class: "constellation-path-step",
        }, String(index + 1).padStart(2, "0")));
      });
      svg.append(overlay);
    }

    const materialNodes = createSvgElement("g", { class: "constellation-materials" });
    data.materials.forEach((material) => {
      const point = positions.get(material.id);
      const link = createSvgElement("a", {
        href: routeHref("material", material.id),
        class: "constellation-material-link",
        tabindex: "0",
        role: "link",
        "aria-label": `${String(material.number).padStart(2, "0")} ${material.title}. ${material.authors.join(", ")}, ${material.year}. Reading depth ${material.noteDepth}.`,
        "data-route": "material",
        "data-route-id": material.id,
        "data-material-id": material.id,
      });
      if (context.hasEmphasis && !materialIsEmphasized(material, context)) link.classList.add("is-dimmed");
      if (context.hasEmphasis && materialIsEmphasized(material, context)) link.classList.add("is-emphasized");

      const pointsRight = Math.cos(point.angle) >= 0;
      const label = `${String(material.number).padStart(2, "0")} ${material.shortAuthor || material.authors[0]}`;
      link.append(
        createSvgElement("circle", { cx: point.x, cy: point.y, r: 22, class: "constellation-hit" }),
        createSvgElement("circle", { cx: point.x, cy: point.y, r: 4.7, class: "constellation-star" }),
      );
      if (["read", "worked"].includes(material.noteDepth)) {
        link.append(createSvgElement("circle", { cx: point.x, cy: point.y, r: 10.5, class: "constellation-depth-ring" }));
      }
      link.append(createSvgElement("text", {
        x: point.x + (pointsRight ? 13 : -13),
        y: point.y + 4,
        "text-anchor": pointsRight ? "start" : "end",
        class: "constellation-material-label",
      }, label));
      link.addEventListener("mouseenter", () => setConstellationHover("material", material.id, true));
      link.addEventListener("focus", () => setConstellationHover("material", material.id, true));
      link.addEventListener("mouseleave", () => setConstellationHover("material", material.id, false));
      link.addEventListener("blur", () => setConstellationHover("material", material.id, false));
      materialNodes.append(link);
    });
    svg.append(materialNodes);

    const surfaceNodes = createSvgElement("g", { class: "constellation-surfaces" });
    data.atlas.failureSurfaces.forEach((surface) => {
      const anchor = constellationAnchors.get(surface.id);
      const link = createSvgElement("a", {
        href: routeHref("thread", surface.id),
        class: "constellation-surface-link",
        tabindex: "0",
        role: "link",
        "aria-label": `${surface.number} ${surface.label}. ${surface.question}`,
        "data-route": "thread",
        "data-route-id": surface.id,
        "data-surface-id": surface.id,
      });
      if (context.explicitSurfaceId === surface.id) link.classList.add("is-emphasized");
      link.append(
        createSvgElement("circle", { cx: anchor.x, cy: anchor.y, r: 15, class: "constellation-surface-ring" }),
        createSvgElement("circle", { cx: anchor.x, cy: anchor.y, r: 2.5, class: "constellation-surface-core" }),
      );
      const label = createSvgElement("text", {
        x: anchor.labelX,
        y: anchor.labelY,
        "text-anchor": anchor.textAnchor,
        class: "constellation-surface-label",
      });
      const [primary, secondary] = surface.label.split(" / ");
      label.append(
        createSvgElement("tspan", { x: anchor.labelX, dy: "0" }, `${surface.number} ${primary}`),
        createSvgElement("tspan", { x: anchor.labelX, dy: "18" }, secondary || ""),
      );
      link.append(label);
      link.addEventListener("mouseenter", () => setConstellationHover("surface", surface.id, true));
      link.addEventListener("focus", () => setConstellationHover("surface", surface.id, true));
      link.addEventListener("mouseleave", () => setConstellationHover("surface", surface.id, false));
      link.addEventListener("blur", () => setConstellationHover("surface", surface.id, false));
      surfaceNodes.append(link);
    });
    svg.append(surfaceNodes);

    refs.constellationPlot.replaceChildren(svg);
  }

  function renderConstellationMatrix(context) {
    const table = document.createElement("table");
    const caption = createTextElement("caption", "Materials by failure surface. Filled dots mark membership.", "sr-only");
    const head = document.createElement("thead");
    const headRow = document.createElement("tr");
    const materialHeader = createTextElement("th", "Material");
    materialHeader.scope = "col";
    headRow.append(materialHeader);
    data.atlas.failureSurfaces.forEach((surface) => {
      const cell = document.createElement("th");
      cell.scope = "col";
      const link = createRouteLink("thread", surface.id, surface.number);
      link.title = surface.label;
      link.setAttribute("aria-label", `${surface.number} ${surface.label}`);
      cell.append(link);
      headRow.append(cell);
    });
    head.append(headRow);

    const body = document.createElement("tbody");
    data.materials.forEach((material) => {
      const row = document.createElement("tr");
      if (context.hasEmphasis && !materialIsEmphasized(material, context)) row.classList.add("is-dimmed");
      if (context.hasEmphasis && materialIsEmphasized(material, context)) row.classList.add("is-emphasized");
      const labelCell = document.createElement("th");
      labelCell.scope = "row";
      labelCell.append(createRouteLink(
        "material",
        material.id,
        `${String(material.number).padStart(2, "0")} ${material.title}`,
      ));
      row.append(labelCell);
      data.atlas.failureSurfaces.forEach((surface) => {
        const cell = document.createElement("td");
        const included = material.failureSurfaces.includes(surface.id);
        const mark = createTextElement("span", included ? "●" : "·", included ? "matrix-star" : "matrix-empty");
        mark.setAttribute("aria-hidden", "true");
        cell.append(mark, createTextElement("span", included ? `属于 ${surface.label}` : `不属于 ${surface.label}`, "sr-only"));
        row.append(cell);
      });
      body.append(row);
    });
    table.append(caption, head, body);
    refs.constellationMatrix.replaceChildren(table);
  }

  function renderConstellation() {
    const bridgeCount = data.materials.filter((material) => material.failureSurfaces.length > 1).length;
    refs.constellationStats.textContent = `${data.materials.length} materials · ${data.atlas.failureSurfaces.length} surfaces · ${bridgeCount} bridges`;
    const positions = constellationPositions();
    const context = constellationContext();
    renderConstellationPlot(positions, context);
    renderConstellationMatrix(context);
    setConstellationReading();
  }

  function renderPaths() {
    refs.pathGrid.replaceChildren(...data.atlas.readingPaths.map((path) => {
      const article = document.createElement("article");
      article.className = "path-item";
      if (route.path === path.id) article.classList.add("is-selected");
      const title = document.createElement("h3");
      title.append(
        createTextElement("span", path.number, "path-number"),
        createRouteLink("path", path.id, path.title),
      );
      article.append(
        title,
        createTextElement("p", path.description),
        createRouteLink("path", path.id, "查看路径 →", "path-link"),
      );
      return article;
    }));

    const activePath = pathsById.get(route.path);
    refs.pathFocus.hidden = !activePath;
    if (!activePath) {
      refs.pathFocus.replaceChildren();
      return;
    }
    const heading = createTextElement("h3", `${activePath.number} / ${activePath.title}`);
    const disclosure = createTextElement("p", "编者建议顺序 · 可以从任意一篇离开", "content-kind editorial-kind");
    const list = document.createElement("ol");
    list.className = "path-materials";
    activePath.materialIds.forEach((materialId) => {
      const material = materialsById.get(materialId);
      const item = document.createElement("li");
      item.append(
        createTextElement("span", String(material.number).padStart(2, "0"), "path-step"),
        createRouteLink("material", material.id, material.title),
        createTextElement("span", material.noteDepth, `depth-word depth-${material.noteDepth}`),
      );
      list.append(item);
    });
    refs.pathFocus.replaceChildren(disclosure, heading, list);
  }

  function fillSelect(select, label, values, selectedValue) {
    const options = [new Option(label, "")];
    values.forEach(({ value, text }) => options.push(new Option(text, value)));
    select.replaceChildren(...options);
    select.value = selectedValue;
  }

  function syncControls() {
    refs.search.value = route.q;
    fillSelect(
      refs.topicFilter,
      "全部主题",
      data.filters.map((topic) => ({ value: topic, text: topic })),
      route.topic,
    );
    fillSelect(
      refs.surfaceFilter,
      "全部 failure surfaces",
      data.atlas.failureSurfaces.map((surface) => ({ value: surface.id, text: `${surface.number} ${surface.label}` })),
      route.surface,
    );
    fillSelect(
      refs.depthFilter,
      "全部 depth",
      depthOrder.map((depth) => ({ value: depth, text: depth })),
      route.depth,
    );
  }

  function matchingMaterials() {
    const query = normalize(route.q).trim();
    return data.materials.filter((material) => {
      if (route.topic && !material.categories.includes(route.topic)) return false;
      if (route.surface && !material.failureSurfaces.includes(route.surface)) return false;
      if (route.depth && material.noteDepth !== route.depth) return false;
      if (!query) return true;
      const haystack = normalize([
        material.title,
        material.authors.join(" "),
        material.shortAuthor,
        material.year,
        JSON.stringify(material),
      ].join(" "));
      return haystack.includes(query);
    });
  }

  function renderLibrary() {
    const materials = matchingMaterials();
    refs.librarySummary.textContent = `${data.materials.length} 条 public allowlisted records；按阅读范围理解，不按“完成度”排名。`;
    refs.resultCount.textContent = `${materials.length} / ${data.materials.length} 条材料`;
    refs.emptyState.hidden = materials.length !== 0;
    refs.materialIndex.replaceChildren(...materials.map(createMaterialRow));
  }

  function createMaterialRow(material) {
    const row = document.createElement("article");
    row.className = "material-row";
    row.setAttribute("role", "listitem");

    const number = createTextElement("span", String(material.number).padStart(2, "0"), "material-row-number");
    const copy = document.createElement("div");
    copy.className = "material-row-copy";
    const title = createRouteLink("material", material.id, material.title, "material-row-title");
    const meta = createTextElement("p", `${material.authors.join(", ")} · ${material.year}`);
    copy.append(title, meta);

    const topics = createTextElement("p", material.categories.join(" · "), "material-row-topics");
    const depth = createTextElement("span", material.noteDepth, `depth-word depth-${material.noteDepth}`);
    const surfaces = document.createElement("div");
    surfaces.className = "material-row-surfaces";
    material.failureSurfaces.forEach((surfaceId) => {
      const surface = surfacesById.get(surfaceId);
      const link = createRouteLink("thread", surface.id, surface.number);
      link.title = surface.label;
      link.setAttribute("aria-label", `${surface.number} ${surface.label}`);
      surfaces.append(link);
    });
    row.append(number, copy, topics, depth, surfaces);
    return row;
  }

  function renderMaterial(material) {
    refs.materialNumber.textContent = String(material.number).padStart(2, "0");
    refs.materialTitle.textContent = material.title;
    refs.materialMeta.textContent = `${material.authors.join(", ")} · ${material.year}`;
    refs.materialSurfaceLinks.replaceChildren(...material.failureSurfaces.map((surfaceId) => {
      const surface = surfacesById.get(surfaceId);
      return createRouteLink("thread", surface.id, `${surface.number} ${surface.label}`);
    }));
    refs.materialIntro.textContent = material.intro;
    refs.materialPoints.replaceChildren(...material.keyPoints.map((point) => createTextElement("li", point)));

    const argumentMap = material.argumentMap || [];
    refs.argumentSection.hidden = argumentMap.length === 0;
    refs.materialArgumentMap.replaceChildren(...argumentMap.map((item) => {
      const block = document.createElement("section");
      block.className = "research-note argument-step";
      block.append(
        createTextElement("p", item.step, "research-note-label"),
        createTextElement("p", item.claim, "research-note-text"),
        createTextElement("p", item.locator, "research-note-locator"),
      );
      return block;
    }));

    const methodNotes = material.methodNotes || [];
    refs.methodSection.hidden = methodNotes.length === 0;
    refs.materialMethodNotes.replaceChildren(...methodNotes.map((item) => {
      const block = document.createElement("section");
      block.className = "research-note method-note";
      block.append(
        createTextElement("h3", item.label),
        createTextElement("p", item.text, "research-note-text"),
        createTextElement("p", item.locator, "research-note-locator"),
      );
      return block;
    }));

    const findings = material.reportedFindings || [];
    refs.findingsSection.hidden = findings.length === 0;
    refs.materialFindings.replaceChildren(...findings.map((finding) => createTextElement("li", finding)));

    const limits = material.evidenceLimits || [];
    refs.materialLimits.replaceChildren(...limits.map((limit) => createTextElement("li", limit)));
    refs.materialLimits.hidden = limits.length === 0;
    refs.limitsFallback.hidden = limits.length !== 0;

    const tensions = material.sourceTensions || [];
    refs.tensionsSection.hidden = tensions.length === 0;
    refs.materialTensions.replaceChildren(...tensions.map((tension) => {
      const block = document.createElement("section");
      block.className = "tension-block";
      block.append(
        createTextElement("h3", tension.label),
        createTextElement("p", tension.observation, "tension-observation"),
        createTextElement("p", `定位：${tension.locators.join(" · ")}`, "research-note-locator"),
        createTextElement("p", `编者 consequence：${tension.implication}`, "tension-implication"),
      );
      return block;
    }));

    const inferences = material.editorialInferences || [];
    refs.whyReadBlock.hidden = !material.whyRead;
    refs.materialWhyRead.textContent = material.whyRead || "";
    refs.materialInferences.replaceChildren(...inferences.map((inference) => {
      const block = document.createElement("section");
      block.className = "inference-block";
      block.append(
        createTextElement("p", `${inference.label} · Editorial inference — not tested by the paper`, "inference-label"),
        createTextElement("p", inference.text, "inference-text"),
        createTextElement("p", inference.boundary, "inference-boundary"),
      );
      return block;
    }));
    refs.materialQuestion.textContent = material.editorialQuestion;

    const protocols = material.openProtocols || [];
    refs.protocolsSection.hidden = protocols.length === 0;
    refs.materialProtocols.replaceChildren(...protocols.map((protocol) => {
      const block = document.createElement("section");
      block.className = "protocol-block";
      block.append(
        createTextElement("p", "Proposed · not run", "protocol-status"),
        createTextElement("h3", protocol.title),
        createTextElement("p", protocol.question, "protocol-question"),
      );
      const details = document.createElement("dl");
      [
        ["Method", protocol.method],
        ["Public / synthetic fixtures", protocol.fixtures],
        ["Controls", protocol.controls],
        ["Measures", protocol.measures],
        ["Limitations", protocol.limitations],
      ].forEach(([label, value]) => {
        details.append(createTextElement("dt", label), createTextElement("dd", value));
      });
      block.append(details);
      return block;
    }));

    const contributions = material.contributions || [];
    refs.contributionsSection.hidden = contributions.length === 0;
    refs.materialContributions.replaceChildren(...contributions.map((contribution) => {
      const block = document.createElement("section");
      block.className = "contribution-block";
      block.append(
        createTextElement(
          "p",
          `${contribution.type === "public-test" ? "Public test" : "Editorial perspective"} · ${contribution.byline} · ${contribution.date}`,
          "contribution-meta",
        ),
        createTextElement("h3", contribution.title),
      );
      if (contribution.type === "perspective") {
        block.append(createTextElement("p", contribution.text, "contribution-text"));
      } else {
        const details = document.createElement("dl");
        [
          ["Method", contribution.method],
          ["Environment", contribution.environment],
          ["Fixture", contribution.fixture],
          ["Controls", contribution.controls],
          ["Raw result", contribution.rawResult],
          ["Derived result", contribution.derivedResult],
          ["Limitations", contribution.limitations],
        ].forEach(([label, value]) => {
          details.append(createTextElement("dt", label), createTextElement("dd", value));
        });
        block.append(details);
      }
      block.append(
        createTextElement("p", `Evidence basis：${contribution.basis}`, "contribution-basis"),
        createTextElement("p", `Boundary：${contribution.boundary}`, "contribution-boundary"),
      );
      if (contribution.links.length) {
        const links = document.createElement("p");
        links.className = "contribution-links";
        contribution.links.forEach((link, index) => {
          if (index) links.append(document.createTextNode(" · "));
          links.append(createExternalLink(link.url, `${link.label} ↗`));
        });
        block.append(links);
      }
      return block;
    }));

    const sourceContent = buildSourceContent(material);
    const mobileSourceContent = sourceContent.cloneNode(true);
    refs.sourceRail.replaceChildren(sourceContent);
    refs.sourceMobile.replaceChildren(mobileSourceContent);
    renderArticleToc();
    observeArticleSections();
    document.title = `${material.title} · Agent Memory Study`;
  }

  function buildSourceContent(material) {
    const fragment = document.createDocumentFragment();
    const depthSection = document.createElement("section");
    depthSection.append(
      createTextElement("p", "Reading depth", "rail-label"),
      createTextElement("p", material.noteDepth, `rail-depth depth-${material.noteDepth}`),
      createTextElement("p", material.readingScope, "rail-copy"),
    );

    const actionSection = document.createElement("section");
    actionSection.append(createTextElement("p", "Read the source", "rail-label"));
    const actions = document.createElement("div");
    actions.className = "rail-actions";
    actions.append(
      createExternalLink(material.pdf.url, "阅读 PDF ↗", "primary-action"),
      createExternalLink(material.sourceUrl, "官方来源 ↗", "secondary-action"),
    );
    actionSection.append(actions);

    const deliverySection = document.createElement("section");
    deliverySection.append(createTextElement("p", "Source / PDF delivery / license", "rail-label"));
    const delivery = material.pdf.delivery === "bundled"
      ? `Bundled copy · ${material.pdf.license}`
      : `Official link${material.pdf.accessNote ? ` · ${material.pdf.accessNote}` : ""}`;
    deliverySection.append(createTextElement("p", delivery, "rail-copy"));
    if (material.pdf.delivery === "bundled") {
      deliverySection.append(createExternalLink(material.pdf.licenseUrl, "查看 file-level license ↗", "rail-link"));
    }
    if (material.sourceNote) deliverySection.append(createTextElement("p", material.sourceNote, "rail-note"));

    const identitySection = document.createElement("section");
    identitySection.append(createTextElement("p", "Citation identity", "rail-label"));
    identitySection.append(createExternalLink(material.sourceUrl, material.sourceUrl, "rail-link break-link"));
    if (material.doi) identitySection.append(createTextElement("p", `DOI ${material.doi}`, "rail-copy"));

    fragment.append(depthSection, actionSection, deliverySection, identitySection);
    return fragment;
  }

  function renderArticleToc() {
    const sections = [...document.querySelectorAll(".article-main > .article-section:not([hidden])")]
      .filter((section) => section.offsetParent !== null);
    refs.articleToc.replaceChildren(...sections.map((section, index) => {
      const link = document.createElement("a");
      link.href = `#${section.id}`;
      link.textContent = `${index + 1}  ${section.dataset.tocLabel}`;
      return link;
    }));
  }

  function observeArticleSections() {
    if (articleObserver) articleObserver.disconnect();
    const links = [...refs.articleToc.querySelectorAll("a")];
    if (!("IntersectionObserver" in window)) return;
    articleObserver = new IntersectionObserver((entries) => {
      const visible = entries
        .filter((entry) => entry.isIntersecting)
        .sort((left, right) => left.boundingClientRect.top - right.boundingClientRect.top)[0];
      if (!visible) return;
      links.forEach((link) => {
        const active = link.getAttribute("href") === `#${visible.target.id}`;
        link.setAttribute("aria-current", String(active));
      });
    }, { rootMargin: "-18% 0px -66% 0px", threshold: 0 });
    [...document.querySelectorAll(".article-main > .article-section:not([hidden])")]
      .filter((section) => section.offsetParent !== null)
      .forEach((section) => {
        articleObserver.observe(section);
      });
  }

  function render(options = {}) {
    const { focus = false, hash = window.location.hash } = options;
    const material = materialsById.get(route.material);
    const showingMaterial = Boolean(material);
    refs.atlasView.hidden = showingMaterial;
    refs.materialView.hidden = !showingMaterial;
    document.body.classList.toggle("is-reading", showingMaterial);
    closeMenu();

    if (showingMaterial) {
      renderMaterial(material);
      refs.routeStatus.textContent = `已打开 ${material.title}`;
      if (focus) {
        window.scrollTo({ top: 0, behavior: "auto" });
        refs.materialTitle.tabIndex = -1;
        refs.materialTitle.focus({ preventScroll: true });
      }
      return;
    }

    document.title = "Agent Memory Study · Research atlas";
    renderAtlasFrame();
    const activeSurface = selectedSurface();
    refs.routeStatus.textContent = route.path
      ? `已打开阅读路径：${pathsById.get(route.path).title}`
      : activeSurface
        ? `研究地图：${activeSurface.label}`
        : "研究地图：尚未选择 failure surface";
    if (!focus && !hash) return;
    window.requestAnimationFrame(() => {
      const target = route.thread
        ? refs.surfaceFocus
        : route.path
          ? refs.pathFocus
          : hash
            ? document.querySelector(hash)
            : document.querySelector("#main-content");
      if (target) {
        target.scrollIntoView({ behavior: "auto", block: "start" });
        if (focus && target.matches("[tabindex]")) target.focus({ preventScroll: true });
      }
    });
  }

  function updateFilters(changes) {
    navigate({ ...changes, material: null }, { replace: true, focus: false });
  }

  function closeMenu() {
    refs.siteNav.classList.remove("is-open");
    refs.menuButton.setAttribute("aria-expanded", "false");
  }

  refs.search.addEventListener("input", (event) => updateFilters({ q: event.target.value }));
  refs.libraryControls.addEventListener("submit", (event) => event.preventDefault());
  refs.topicFilter.addEventListener("change", (event) => updateFilters({ topic: event.target.value }));
  refs.surfaceFilter.addEventListener("change", (event) => {
    updateFilters({ surface: event.target.value, thread: null });
  });
  refs.depthFilter.addEventListener("change", (event) => updateFilters({ depth: event.target.value }));
  refs.clearFilters.addEventListener("click", () => {
    navigate({ q: "", topic: "", surface: "", depth: "", thread: null }, { replace: true, focus: false });
  });

  refs.menuButton.addEventListener("click", () => {
    const open = !refs.siteNav.classList.contains("is-open");
    refs.siteNav.classList.toggle("is-open", open);
    refs.menuButton.setAttribute("aria-expanded", String(open));
    if (open) refs.siteNav.querySelector("a").focus();
  });

  function activateRouteLink(link) {
    const type = link.dataset.route;
    const id = link.dataset.routeId;
    if (type === "material") {
      navigate({ material: id, thread: null, path: null }, { focus: true });
      return;
    }
    if (type === "thread") {
      navigate({ material: null, thread: id, path: null, surface: id }, { focus: true });
      return;
    }
    if (type === "path") {
      navigate({ material: null, thread: null, path: id }, { focus: true });
      return;
    }
    if (type === "home") {
      const scrollTarget = link.dataset.scrollTarget || "";
      navigate({ material: null, thread: null, path: null }, {
        focus: true,
        hash: scrollTarget ? `#${scrollTarget}` : "",
      });
    }
  }

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && refs.siteNav.classList.contains("is-open")) {
      closeMenu();
      refs.menuButton.focus();
    }
    if (!["Enter", " "].includes(event.key)) return;
    const link = event.target.closest("svg a[data-route]");
    if (!link) return;
    event.preventDefault();
    activateRouteLink(link);
  });

  document.addEventListener("click", (event) => {
    if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    const easterButton = event.target.closest("button[data-easter], #architecture-note");
    if (easterButton) {
      const revealed = easterButton.getAttribute("aria-pressed") !== "true";
      easterButton.setAttribute("aria-pressed", String(revealed));
      easterButton.setAttribute(
        "aria-label",
        revealed
          ? `${easterButton.dataset.reveal} Activate to restore ${easterButton.dataset.original}.`
          : `${easterButton.dataset.original} Activate to reveal ${easterButton.dataset.reveal}.`,
      );
      return;
    }
    const link = event.target.closest("a[data-route]");
    if (!link) return;
    event.preventDefault();
    activateRouteLink(link);
  });

  window.addEventListener("popstate", () => {
    route = readRoute();
    render({ focus: true, hash: window.location.hash });
  });

  render({ focus: false, hash: window.location.hash });
})();
