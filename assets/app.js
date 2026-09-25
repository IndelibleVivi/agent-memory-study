(() => {
  "use strict";

  const data = window.READING_ROOM;
  if (
    !data
    || !Array.isArray(data.materials)
    || data.materials.length === 0
    || !data.atlas
    || !Array.isArray(data.atlas.failureSurfaces)
    || !Array.isArray(data.studies)
    || !Array.isArray(data.atlas.readingPaths)
  ) {
    document.body.textContent = "阅读室的 public data 缺失或不完整。";
    return;
  }

  const materialsById = new Map(data.materials.map((material) => [material.id, material]));
  const surfacesById = new Map(data.atlas.failureSurfaces.map((surface) => [surface.id, surface]));
  const pathsById = new Map(data.atlas.readingPaths.map((path) => [path.id, path]));
  const studiesById = new Map(data.studies.map((study) => [study.id, study]));
  const questionsById = new Map((data.questions || []).map(item => [item.id, item]));
  const findingsById = new Map((data.findings || []).map(item => [item.id, item]));
  const seo = window.AMS_SEO;
  const siteRoot = document.currentScript.src
    ? new URL("../", document.currentScript.src) : new URL("./", window.location.href);
  const physicalRoutes = document.documentElement.dataset.staticReader === "true" && window.location.protocol !== "file:";
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
  const searchIndex = window.ReadingSearch.buildIndex(data);
  let route = readRoute();
  let articleObserver = null;
  let constellationMeasurer = null;

  const refs = {
    atlasView: document.querySelector("#atlas-view"),
    materialView: document.querySelector("#material-view"),
    inquiryView: document.querySelector("#inquiry-view"),
    studyView: document.querySelector("#study-view"),
    studyIndex: document.querySelector("#study-index"),
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
    const detail = physicalRoutes && seo.pathRoute(new URL(window.location.href), siteRoot);
    if (detail) {
      seo.kinds.forEach(key => params.delete(key));
      Object.entries(detail).forEach(([key, value]) => params.set(key, value));
    }
    const material = materialsById.has(params.get("material")) ? params.get("material") : null;
    const study = !material && studiesById.has(params.get("study")) ? params.get("study") : null;
    const question = !material && !study && questionsById.has(params.get("question")) ? params.get("question") : null;
    const finding = !material && !study && !question && findingsById.has(params.get("finding")) ? params.get("finding") : null;
    const scenarios = study ? (studiesById.get(study).scenarios || (studiesById.get(study).recordedResults ? recordedScenarios(studiesById.get(study)) : [])) : [];
    const scenario = scenarios.some(item => item.id === params.get("scenario")) ? params.get("scenario") : null;
    const phase = params.get("phase") === "after" ? "after" : "before";
    const thread = surfacesById.has(params.get("thread")) ? params.get("thread") : null;
    const path = pathsById.has(params.get("path")) ? params.get("path") : null;
    const topic = data.filters.includes(params.get("topic")) ? params.get("topic") : "";
    const explicitSurface = surfacesById.has(params.get("surface")) ? params.get("surface") : "";
    const depth = depthOrder.includes(params.get("depth")) ? params.get("depth") : "";
    return {
      question, finding, practice: params.get("practice") || "",
      material,
      study,
      scenario,
      phase,
      thread,
      path,
      q: params.get("q") || "",
      topic,
      surface: explicitSurface || thread || "",
      depth,
    };
  }

  function routeUrl(nextRoute, hash = "") {
    return seo.routeUrl(nextRoute, window.location.href, siteRoot, physicalRoutes, hash);
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
    const next = { ...route, question: null, finding: null, material: null, study: null, scenario: null, phase: "before", thread: null, path: null };
    if (type === "material") next.material = id;
    if (type === "study") next.study = id;
    if (type === "question") next.question = id;
    if (type === "finding") next.finding = id;
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
    renderStudyIndex();
    renderInquiryIndex();
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

  function constellationMaterialLabel(material) {
    return `${String(material.number).padStart(2, "0")} ${material.shortAuthor || material.authors[0]}`;
  }

  function measureConstellationText(text, fontSize) {
    if (!constellationMeasurer) {
      const uiFont = getComputedStyle(document.documentElement).getPropertyValue("--ui").trim();
      constellationMeasurer = {
        context: document.createElement("canvas").getContext("2d"),
        fontFamily: uiFont || "sans-serif",
      };
    }
    constellationMeasurer.context.font = `${fontSize}px ${constellationMeasurer.fontFamily}`;
    return constellationMeasurer.context.measureText(text).width;
  }

  function constellationLabelRect(x, y, textAnchor, width) {
    const left = textAnchor === "end" ? x - width : textAnchor === "middle" ? x - width / 2 : x;
    return { x: left - 3, y: y - 14, width: width + 6, height: 19 };
  }

  function rectsOverlap(left, right) {
    return left.x < right.x + right.width
      && left.x + left.width > right.x
      && left.y < right.y + right.height
      && left.y + left.height > right.y;
  }

  function circleOverlapsRect(cx, cy, radius, rect) {
    const nearX = Math.max(rect.x, Math.min(cx, rect.x + rect.width));
    const nearY = Math.max(rect.y, Math.min(cy, rect.y + rect.height));
    return Math.hypot(cx - nearX, cy - nearY) < radius;
  }

  function resolveMaterialLabelPlacements(positions) {
    const placements = new Map();
    const obstacles = [];
    data.atlas.failureSurfaces.forEach((surface) => {
      const anchor = constellationAnchors.get(surface.id);
      const [primary, secondary] = surface.label.split(" / ");
      const width = Math.max(
        measureConstellationText(`${surface.number} ${primary}`, 13),
        secondary ? measureConstellationText(secondary, 11) : 0,
      );
      const left = anchor.textAnchor === "end"
        ? anchor.labelX - width
        : anchor.textAnchor === "middle"
          ? anchor.labelX - width / 2
          : anchor.labelX;
      obstacles.push({ x: left - 3, y: anchor.labelY - 16, width: width + 6, height: 37 });
    });

    const collides = (rect) => {
      if (
        rect.x < 6
        || rect.y < 6
        || rect.x + rect.width > constellationViewBox.width - 6
        || rect.y + rect.height > constellationViewBox.height - 6
      ) return true;
      if (obstacles.some((obstacle) => rectsOverlap(rect, obstacle))) return true;
      return data.atlas.failureSurfaces.some((surface) => {
        const anchor = constellationAnchors.get(surface.id);
        return circleOverlapsRect(anchor.x, anchor.y, 17, rect);
      });
    };

    positions.forEach((point, materialId) => {
      const width = measureConstellationText(constellationMaterialLabel(materialsById.get(materialId)), 11);
      const pointsRight = Math.cos(point.angle) >= 0;
      const sideCandidate = (right, dy) => ({
        x: point.x + (right ? 13 : -13),
        y: point.y + dy,
        textAnchor: right ? "start" : "end",
      });
      const candidates = [
        sideCandidate(pointsRight, 4),
        sideCandidate(!pointsRight, 4),
        sideCandidate(pointsRight, -10),
        sideCandidate(!pointsRight, -10),
        sideCandidate(pointsRight, 16),
        sideCandidate(!pointsRight, 16),
        sideCandidate(pointsRight, 30),
        sideCandidate(!pointsRight, 30),
        { x: point.x, y: point.y - 14, textAnchor: "middle" },
        { x: point.x, y: point.y + 22, textAnchor: "middle" },
      ];
      const chosen = candidates.find(
        (candidate) => !collides(constellationLabelRect(candidate.x, candidate.y, candidate.textAnchor, width)),
      ) || candidates[0];
      placements.set(materialId, chosen);
      obstacles.push(constellationLabelRect(chosen.x, chosen.y, chosen.textAnchor, width));
    });
    return placements;
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

  function renderConstellationPlot(positions, context, labelPlacements) {
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

      const labelPlacement = labelPlacements.get(material.id);
      link.append(
        createSvgElement("circle", { cx: point.x, cy: point.y, r: 22, class: "constellation-hit" }),
        createSvgElement("circle", { cx: point.x, cy: point.y, r: 4.7, class: "constellation-star" }),
      );
      if (["read", "worked"].includes(material.noteDepth)) {
        link.append(createSvgElement("circle", { cx: point.x, cy: point.y, r: 10.5, class: "constellation-depth-ring" }));
      }
      link.append(createSvgElement("text", {
        x: labelPlacement.x,
        y: labelPlacement.y,
        "text-anchor": labelPlacement.textAnchor,
        class: "constellation-material-label",
      }, constellationMaterialLabel(material)));
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
    const labelPlacements = resolveMaterialLabelPlacements(positions);
    const context = constellationContext();
    renderConstellationPlot(positions, context, labelPlacements);
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
    return window.ReadingSearch.search(searchIndex, route.q, route)
      .filter(hit => hit.kind === "material").map(hit => hit.item);
  }

  function renderLibrary() {
    const hits = window.ReadingSearch.search(searchIndex, route.q, route);
    const materialCount = hits.filter(hit => hit.kind === "material").length;
    const studyCount = hits.filter(hit => hit.kind === "study").length;
    const questionCount = hits.filter(hit => hit.kind === "question").length;
    const findingCount = hits.filter(hit => hit.kind === "finding").length;
    refs.librarySummary.textContent = `${data.materials.length} 份材料 · ${data.studies.length} 个共读 · ${questionsById.size} 个问题专题 · ${findingsById.size} 条实践判断。`;
    refs.resultCount.textContent = `${materialCount} 材料 · ${studyCount} 共读 · ${questionCount} 问题 · ${findingCount} 判断`;
    refs.emptyState.hidden = hits.length !== 0;
    refs.materialIndex.replaceChildren(...hits.map(hit => {
      const row = hit.kind === "material" ? createMaterialRow(hit.item) : hit.kind === "study" ? createStudyRow(hit.item) : createInquiryRow(hit.item, hit.kind);
      row.dataset.resultKind = hit.kind;
      row.setAttribute("role", "listitem");
      if (hit.snippet) {
        const copy = row.querySelector(".material-row-copy");
        copy.append(createTextElement("p", `命中：${hit.matchLabels.join(" · ")}`, "search-match-label"),
          createTextElement("p", hit.snippet.text, "search-snippet"));
      }
      return row;
    }));
  }

  function createStudyRow(study) {
    const row = createTextElement("article", "", "material-row study-result");
    row.setAttribute("role", "listitem");
    const copy = createTextElement("div", "", "material-row-copy");
    copy.append(createRouteLink("study", study.id, study.title, "material-row-title"),
      createTextElement("p", study.subtitle));
    row.append(createTextElement("span", "共读", "material-row-number"), copy,
      createTextElement("p", `${study.readings.length} 份串读材料`, "material-row-topics"));
    return row;
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
    const connections = [...(data.questions || []).filter(item => item.materialIds.includes(material.id)).map(item => createInquiryRow(item, "question")),
      ...(data.findings || []).filter(item => item.materialIds.includes(material.id)).map(item => createInquiryRow(item, "finding"))];
    document.querySelector("#paper-inquiries").hidden = !connections.length;
    document.querySelector("#material-inquiries").replaceChildren(...connections);
    const studies = data.studies.filter(study => study.readings.some(reading => reading.materialId === material.id));
    document.querySelector("#paper-studies").hidden = !studies.length;
    document.querySelector("#material-studies").replaceChildren(...studies.map(study => {
      const reading = study.readings.find(item => item.materialId === material.id);
      const block = createTextElement("section", "", "material-study-connection");
      const heading = createTextElement("h3", "");
      heading.append(createRouteLink("study", study.id, `${study.title} →`));
      block.append(heading, createTextElement("p", reading.takeaway),
        createTextElement("p", reading.limit, "inference-boundary"),
        createTextElement("p", `串读定位：${reading.locator}`, "research-note-locator"));
      return block;
    }));
    refs.materialNumber.textContent = String(material.number).padStart(2, "0");
    refs.materialTitle.textContent = material.title;
    refs.materialMeta.textContent = `${material.authors.join(", ")} · ${material.year}`;
    refs.materialSurfaceLinks.replaceChildren(...material.failureSurfaces.map((surfaceId) => {
      const surface = surfacesById.get(surfaceId);
      return createRouteLink("thread", surface.id, `${surface.number} ${surface.label}`);
    }));
    const transfer = material.designTransfer;
    document.querySelector("#paper-transfer").hidden = !transfer;
    const transferFields = document.querySelector("#material-transfer");
    transferFields.replaceChildren();
    if (transfer) {
      const earlyReading = ["abstract", "skim"].includes(material.noteDepth);
      document.querySelector("#transfer-disclosure").textContent = earlyReading
        ? "初读线索 · 基于本条已标注的阅读范围，仍待全文与实现核验。下面的迁移对照尚未执行。"
        : "基于既有精读与本条明确标注的证据范围整理；下面针对新场景的迁移对照尚未执行。";
      document.querySelector("#transfer-meta").textContent = `${transfer.byline} · ${transfer.date}`;
      for (const [field, label] of [["when", "什么时候有用"], ["move", "可以借哪一步"], ["check", "先做什么对照"], ["boundary", "带走时的边界"]]) {
        transferFields.append(createTextElement("dt", label), createTextElement("dd", transfer[field]));
      }
      document.querySelector("#transfer-basis").textContent = `阅读依据：${transfer.basis}`;
    }
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

    const audit = material.amsEvidence;
    document.querySelector("#paper-ams-evidence").hidden = !audit;
    const auditBody = document.querySelector("#material-ams-evidence");
    auditBody.replaceChildren();
    if (audit) {
      auditBody.append(createTextElement("p", audit.byline, "study-byline"));
      const artifact = document.createElement("a");
      artifact.href = audit.artifactUrl;
      artifact.textContent = "方法、记录与复跑入口 ↗";
      const detail = document.createElement("a");
      detail.href = "#paper-contributions";
      detail.textContent = "本页署名测试详情 ↓";
      const links = createTextElement("p", "", "ams-evidence-links");
      links.append(artifact, detail); auditBody.append(links);
      if (audit.observations.length) {
        const list = document.createElement("ul");
        list.append(...audit.observations.map(text => createTextElement("li", text)));
        auditBody.append(createTextElement("h3", "检查对象与观察"), list);
      }
      if (audit.findings.length) {
        const list = document.createElement("ul");
        list.append(...audit.findings.map(text => createTextElement("li", text)));
        auditBody.append(createTextElement("h3", "本站已记录的结果"), list);
      }
      if (audit.methods.length || audit.reasoning.length) {
        const details = document.createElement("details");
        details.append(createTextElement("summary", "展开复核方法与推论"));
        for (const item of audit.methods) {
          details.append(createTextElement("h3", item.label), createTextElement("p", item.text),
            createTextElement("p", item.locator, "research-note-locator"));
        }
        for (const item of audit.reasoning) {
          details.append(createTextElement("h3", item.step), createTextElement("p", item.claim),
            createTextElement("p", item.locator, "research-note-locator"));
        }
        auditBody.append(details);
      }
    }

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
        const active = link.hash === `#${visible.target.id}`;
        link.setAttribute("aria-current", String(active));
      });
    }, { rootMargin: "-18% 0px -66% 0px", threshold: 0 });
    [...document.querySelectorAll(".article-main > .article-section:not([hidden])")]
      .filter((section) => section.offsetParent !== null)
      .forEach((section) => {
        articleObserver.observe(section);
      });
  }

  function renderStudyIndex() {
    const entry = document.querySelector("#reading-entry");
    entry.hidden = data.studies.length === 0;
    entry.replaceChildren();
    if (data.studies.length) {
      entry.append("第一次来？", createRouteLink("study", data.studies[0].id, `从「${data.studies[0].title}」开始 →`));
    }
    refs.studyIndex.replaceChildren(...data.studies.map(study => {
      const entry = createTextElement("div", "", "study-entry");
      entry.append(createTextElement("span", study.number, "study-entry-number"));
      const text = createTextElement("div", "");
      const title = createTextElement("h3", "");
      title.append(createRouteLink("study", study.id, `${study.title} ↗`));
      text.append(createTextElement("p", "Shared reading · 共同的问题", "content-kind"), title,
        createTextElement("p", study.subtitle, "study-subtitle"), createTextElement("p", study.intro));
      const note = createTextElement("div", "", "study-entry-note");
      const recordedLabel = study.recordedResults?.schema === "ams-jev-contract-results/1" ? "已执行源码实验" : "已执行学习实验";
      const proposed = study.kind === "editorial-synthesis-with-proposed-experiment";
      const sourceCount = study.readings.length + (study.externalReadings || []).length;
      const studySummary = proposed ? `${sourceCount} 份来源 / 研究方案尚未执行`
        : study.kind === "editorial-synthesis-with-recorded-experiment" ? `${sourceCount} 份来源 / ${recordedLabel}`
        : `${study.readings.length} 份材料 / ${study.scenarios.length} 个可切换场景`;
      note.append(createTextElement("p", studySummary),
        createTextElement("p", proposed ? "原文 · 串读 · 下一项研究" : "原文 · 串读 · 亲手比较 · 带走判断"),
        createRouteLink("study", study.id, "进入共读专题 →", "study-enter"));
      entry.append(text, note);
      return entry;
    }));
  }

  function renderStudy(study) {
    const el = createTextElement;
    const proposed = study.kind === "editorial-synthesis-with-proposed-experiment";
    const fragment = document.createDocumentFragment();
    const back = createRouteLink("home", "", "← 回到公开书房", "back-link");
    const header = el("header", "", "study-heading");
    const title = el("h1", study.title); title.id = "study-title"; title.tabIndex = -1;
    header.append(el("p", `共读专题 ${study.number} / Shared reading`, "content-kind"), title,
      el("p", study.subtitle, "study-subtitle"), el("p", study.intro, "study-dek"),
      el("p", `${study.byline} · ${study.date} · 跨源编者论述`, "study-byline"));
    const jump = el("nav", "", "study-jump"); jump.setAttribute("aria-label", "共读专题目录");
    for (const [id, text] of [["study-reading","一起读"],["study-lab",proposed ? "下一项研究" : "亲手比较"],["study-takeaways","带走判断"]]) {
      const link = el("a", text); link.href = `#${id}`; jump.append(link);
    }
    fragment.append(back, header, jump);
    const reading = el("section", "", "study-reading"); reading.id = "study-reading";
    const essay = el("div", "", "study-essay");
    study.sections.forEach(section => essay.append(el("h2", section.title), el("p", section.text)));
    const sources = el("div", "", "study-sources");
    sources.append(el("p", "桌上的材料", "content-kind"));
    study.readings.forEach((reading, index) => {
      const material = materialsById.get(reading.materialId);
      const row = el("section", "", "study-source");
      const heading = el("h3", `${index + 1}. `);
      heading.append(createRouteLink("material", material.id, reading.label));
      const sourceLink = createExternalLink(material.sourceUrl, "回原文 ↗");
      row.append(heading, el("p", reading.takeaway), el("p", reading.limit, "study-source-limit"),
        el("p", reading.locator, "study-locator"), sourceLink);
      sources.append(row);
    });
    (study.externalReadings || []).forEach(source => {
      const row = el("section", "", "study-source");
      row.append(el("p", source.kind, "content-kind"), el("h3", source.label), el("p", source.takeaway),
        el("p", source.limit, "study-source-limit"), el("p", source.locator, "study-locator"),
        createExternalLink(source.url, "查看一手来源 ↗"));
      sources.append(row);
    });
    reading.append(essay, sources); fragment.append(reading);

    const renderedLab = proposed ? renderProposedLab(study)
      : study.kind === "editorial-synthesis-with-recorded-experiment"
        ? renderRecordedLab(study) : renderRevisionLab(study);
    fragment.append(renderedLab.element);

    const takeaways = el("section", "", "study-takeaways"); takeaways.id = "study-takeaways";
    takeaways.append(el("p", "Take it with you / 编者设计判断", "content-kind"), el("h2", "读完之后，带走什么"));
    const items = el("div", "", "study-takeaway-grid");
    study.takeaways.forEach(item => { const section = el("section", ""); section.append(el("h3", item.title), el("p", item.text)); items.append(section); });
    takeaways.append(items, el("p", study.closing, "study-closing"));
    const contribute = createExternalLink("https://github.com/IndelibleVivi/agent-memory-study/blob/main/CONTRIBUTING.md", "带着来源或反例参与共读 ↗");
    takeaways.append(contribute); fragment.append(takeaways);
    const questions = (data.questions || []).filter(item => item.studyIds.includes(study.id));
    if (questions.length) {
      const onward = el("section", "", "study-takeaways");
      onward.append(el("h2", "这个问题，还在继续"), ...questions.map(item => createInquiryRow(item, "question")));
      fragment.append(onward);
    }
    refs.studyView.replaceChildren(fragment);
    refs.routeStatus.textContent = study.title + "。" + renderedLab.status;
  }

  function renderProposedLab(study) {
    const el = createTextElement;
    const lab = el("section", "", "study-lab"); lab.id = "study-lab";
    const protocol = el("a", "阅读研究方案与执行边界 →"); protocol.href = study.artifactUrl;
    lab.append(el("p", "Proposed study / 研究方案尚未执行", "content-kind"),
      el("h2", study.labTitle), el("p", study.labIntro),
      el("p", study.boundary, "study-source-limit"), protocol);
    return {element: lab, status: "研究方案尚未执行，无模型或实验结果。"};
  }

  function renderRevisionLab(study) {
    const el = createTextElement;
    const lab = el("section", "", "study-lab"); lab.id = "study-lab";
    lab.append(el("p", "Reading experiment / 原创规则演示", "content-kind"), el("h2", study.labTitle),
      el("p", study.labIntro, "study-lab-intro"), el("p", study.boundary, "study-boundary"));
    const scenario = study.scenarios.find(item => item.id === route.scenario) || study.scenarios.find(item => item.id === "corrected") || study.scenarios[0];
    const phase = route.phase || "before";
    const controls = el("div", "", "study-controls");
    const label = el("label", "选择一个场景"); label.htmlFor = "study-scenario";
    const select = el("select", ""); select.id = "study-scenario";
    study.scenarios.forEach(item => { const option = el("option", item.title); option.value = item.id; select.append(option); });
    select.value = scenario.id;
    select.addEventListener("change", () => {
      navigate({scenario: select.value}, {focus: false});
      document.querySelector("#study-scenario").focus({preventScroll: true});
    });
    const picker = el("div", ""); picker.append(label, select);
    const phases = el("div", "", "study-phases"); phases.setAttribute("role", "group"); phases.setAttribute("aria-label", "事件阶段");
    for (const [id, text] of [["before","事件前"],["after","应用事件后"]]) {
      const button = el("button", text); button.type = "button"; button.id = `study-phase-${id}`;
      button.setAttribute("aria-pressed", String(phase === id));
      button.addEventListener("click", () => {
        navigate({scenario: scenario.id, phase: id}, {focus: false});
        document.querySelector(`#study-phase-${id}`).focus({preventScroll: true});
      });
      phases.append(button);
    }
    controls.append(picker, phases); lab.append(controls);
    const live = el("div", ""); live.setAttribute("role", "group"); live.setAttribute("aria-label", "场景与结果");
    live.append(el("p", scenario.description, "study-scenario-description"));
    const experiment = el("div", "", "study-experiment");
    const evidence = el("div", "", "study-evidence");
    const result = window.RevisionStudy.run(scenario, "scoped", phase);
    evidence.append(el("h3", `当前任务 / export-json ${scenario.target}`),
      el("p", `${phase === "after" ? "已应用" : "尚未应用"}：${scenario.change.label}`, "study-event"));
    const list = el("ul", "", "study-evidence-list");
    result.evidence.forEach(item => {
      const row = el("li", "");
      row.append(el("span", item.active ? "有效" : "已撤回", item.active ? "evidence-active" : "evidence-withdrawn"),
        el("code", item.id), el("p", `${item.scope} → ${item.flag} json`));
      list.append(row);
    });
    evidence.append(list);
    if (!result.evidence.length) evidence.append(el("p", "当前没有来源记录。"));
    evidence.append(el("p", "来源顺序表示收到的先后；有效 / 撤回、版本标签均由场景提供。", "study-locator"));
    const outputs = el("div", "", "study-outputs");
    const verdicts = {accepted: "工具接受", mismatch: "工具拒绝 · 参数不符", abstained: "未执行 · 任务未完成"};
    const reasons = {supported: "形成单一建议", conflict: "当前范围内存在冲突", "no-support": "没有可用支持", "no-memory": "未读取经验"};
    study.policies.forEach(policy => {
      const r = window.RevisionStudy.run(scenario, policy.id, phase);
      const row = el("section", "", `study-output verdict-${r.verdict}`);
      const heading = el("div", "", "study-output-heading");
      heading.append(el("h3", policy.label), el("span", verdicts[r.verdict], "study-verdict"));
      row.append(heading, el("p", policy.description, "study-policy-description"),
        el("code", r.flag ? `export-json ${r.flag} json` : "暂不建议执行", "study-command"),
        el("p", `${reasons[r.reason]} · 依据：${r.supports.join("、") || "无"}`, "study-locator"));
      outputs.append(row);
    });
    experiment.append(evidence, outputs); live.append(experiment,
      el("p", `独立工具 contract：${scenario.target} 接受 ${result.expected} json。这个答案只用于执行后的检查，不交给规则选取。`, "study-contract"),
      el("p", scenario.lesson, "study-lesson"));
    lab.append(live);
    const artifacts = el("p", "复跑与反驳：", "study-artifacts");
    const artifactLink = createExternalLink(`https://github.com/IndelibleVivi/agent-memory-study/blob/main/${study.artifactUrl}`, "方法、源码与逐场景结果 ↗");
    artifacts.append(artifactLink); lab.append(artifacts);

    const status = `${scenario.title}，${phase === "after" ? "应用事件后" : "事件前"}。${study.policies.map(policy => `${policy.label}：${verdicts[window.RevisionStudy.run(scenario, policy.id, phase).verdict]}`).join("；")}。`;
    return {element: lab, status};
  }

  function recordedScenarios(study) {
    if (study.recordedResults.schema === "ams-jev-contract-results/1") {
      return study.recordedResults.cases.map(({id}) => ({id}));
    }
    return [...new Set(study.recordedResults.cases.map(row => row.event))].map(id => ({id}));
  }

  function renderContractLab(study) {
    const el = createTextElement, receipt = study.recordedResults;
    const selected = receipt.cases.find(row => row.id === route.scenario) || receipt.cases[0];
    const phase = route.phase === "after" ? "after" : "before";
    const lab = el("section", "", "study-lab contract-lab"); lab.id = "study-lab";
    lab.append(el("p", "Executed source study / 已执行源码实验", "content-kind"), el("h2", study.labTitle),
      el("p", study.labIntro, "study-lab-intro"), el("p", study.boundary, "study-boundary"));
    const picker = el("div", "", "study-controls"), label = el("label", "选择一个源码对照");
    label.htmlFor = "study-scenario";
    const select = el("select", ""); select.id = "study-scenario";
    receipt.cases.forEach(row => { const option = el("option", row.title); option.value = row.id; select.append(option); });
    select.value = selected.id;
    select.addEventListener("change", () => { navigate({scenario: select.value}, {focus: false}); document.querySelector("#study-scenario").focus({preventScroll: true}); });
    picker.append(label, select); lab.append(picker);
    const phases = el("div", "", "study-phases"); phases.setAttribute("role", "group"); phases.setAttribute("aria-label", "查看调用前后状态");
    for (const [id, text] of [["before", "调用前"], ["after", "调用后"]]) {
      const button = el("button", text); button.type = "button"; button.id = `study-phase-${id}`;
      button.setAttribute("aria-pressed", String(phase === id));
      button.addEventListener("click", () => { navigate({phase: id}, {focus: false}); document.querySelector(`#study-phase-${id}`).focus({preventScroll: true}); });
      phases.append(button);
    }
    lab.append(el("p", selected.intervention, "study-scenario-description"), phases);
    const comparison = el("p", `存储节点 ${selected.before.stored_ids.length} → ${selected.after.stored_ids.length}；向量成员 ${selected.before.vector_ids.length} → ${selected.after.vector_ids.length}；派生摘要 ${selected.before.summary_ids.length} → ${selected.after.summary_ids.length}；关系 ${selected.before.links.length} → ${selected.after.links.length}。`, "study-lesson");
    comparison.id = "contract-comparison"; lab.append(comparison);
    const state = el("section", "", "study-evidence"); state.id = "contract-state";
    state.append(el("h3", phase === "after" ? "调用后的快照" : "调用前的快照"));
    const list = el("ul", "", "study-evidence-list");
    for (const [field, name] of [["stored_ids", "存储节点"], ["vector_ids", "向量成员"], ["summary_ids", "派生摘要"]]) {
      const row = el("li", ""); row.append(el("span", name), el("code", selected[phase][field].join(" · ") || "无")); list.append(row);
    }
    state.append(list, el("p", "这些 ID 是原始运行 UUID 的统一显示标签。成员变化来自上游内存后端；向量仍在，不等于已验证语义检索会命中。", "study-locator")); lab.append(state);
    const details = el("details", "", "decision-inputs"); details.id = "contract-observations";
    details.append(el("summary", "检查给定判断、实际返回、关系与逐项断言"), el("pre", JSON.stringify(selected, null, 2))); lab.append(details);
    const passed = Object.values(selected.checks).filter(Boolean).length, total = Object.keys(selected.checks).length;
    lab.append(el("p", `本例执行断言 ${passed}/${total} 符合预期；这不是模型判断正确率。`, "study-contract"));
    const method = el("details", "", "decision-inputs");
    method.append(el("summary", "实验使用了哪些原函数与替身"), el("pre", JSON.stringify({source: receipt.source, method: receipt.method, boundary: receipt.boundary}, null, 2))); lab.append(method);
    const artifacts = el("div", "", "brief-actions");
    artifacts.append(createExternalLink(`https://github.com/IndelibleVivi/agent-memory-study/blob/main/${study.artifactUrl}`, "方法、源码与复跑命令 ↗"));
    const download = el("button", "下载实验结果 JSON", "brief-download"); download.type = "button"; download.id = "contract-download";
    download.addEventListener("click", () => {
      const url = URL.createObjectURL(new Blob([JSON.stringify(receipt, null, 2) + "\n"], {type: "application/json"}));
      const a = el("a", ""); a.href = url; a.download = "ams-jev-memory-contract-results.json"; document.body.append(a); a.click(); a.remove(); window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    });
    artifacts.append(download); lab.append(artifacts);
    return {element: lab, status: `${selected.title}，${phase === "after" ? "调用后" : "调用前"}，显示保存的源码执行结果。`};
  }

  function renderRecordedLab(study) {
    if (study.recordedResults.schema === "ams-jev-contract-results/1") return renderContractLab(study);
    const el = createTextElement, receipt = study.recordedResults;
    const after = route.phase === "after", phase = after ? "after" : "before";
    const methods = after ? {frozen: "仅改记录 · 参数不动", refit: "完整重训", incremental: "仅纠正样本 · 继续训练", guard: "运行时约束"}
      : {"no-experience": "不使用新增经验", episodic: "案例近邻", rules: "归纳规则", scorer: "小型分类器"};
    const labels = {useful: "有用", redundant: "已知 / 无增量", irrelevant: "不相关", harmful: "有害"};
    const lab = el("section", "", "study-lab decision-lab"); lab.id = "study-lab";
    lab.append(el("p", "Executed study / 已执行实验", "content-kind"), el("h2", study.labTitle),
      el("p", study.labIntro, "study-lab-intro"), el("p", study.boundary, "study-boundary"));
    lab.append(el("p", `${receipt.splits.train.groups} 个训练组 / ${receipt.splits.test.groups} 个测试组；测试 ${receipt.splits.test.events} 个事件、${receipt.splits.test.rows} 条候选。${receipt.support.test_rows_with_seen_vector}/${receipt.support.test_rows} 条测试观测向量曾在训练中出现。这里测支持内的标签预测，不是新语义泛化。`, "decision-support"));
    const phases = el("div", "", "study-phases"); phases.setAttribute("role", "group"); phases.setAttribute("aria-label", "查看实验阶段");
    for (const [id, text] of [["before", "初次学习"], ["after", "纠正反馈后"]]) {
      const button = el("button", text); button.type = "button"; button.id = `study-phase-${id}`;
      button.setAttribute("aria-pressed", String(phase === id));
      button.addEventListener("click", () => { navigate({phase: id}, {focus: false}); document.querySelector(`#study-phase-${id}`).focus({preventScroll: true}); });
      phases.append(button);
    }
    lab.append(phases, el("p", after ? "新标签只改变：敏感任务中原本有用、但来源未核验的候选。完整重训从零拟合；其余处理保留或更新同一旧分类器。边界子集属于保留范围，两列不能相加。" : "四种具体实现接受相同观测；三种学习器使用同一份训练反馈。数字表示与生成标签一致，不是实际任务完成率。", "decision-phase-note"));
    function table(caption, headings, rows, id) {
      const wrap = el("div", "", "decision-table-wrap"); wrap.tabIndex = 0;
      wrap.setAttribute("role", "region"); wrap.setAttribute("aria-label", `${caption}；窄屏可横向滚动`);
      const node = el("table", "", "decision-table"); node.id = id;
      node.append(el("caption", caption)); const head = el("thead", ""), tr = el("tr", "");
      headings.forEach(text => { const th=el("th", text); th.scope="col"; tr.append(th); }); head.append(tr); node.append(head);
      const body=el("tbody", ""); rows.forEach(values => { const row=el("tr", ""); values.forEach((text,i) => { const cell=el(i ? "td" : "th", text); if (!i) cell.scope="row"; row.append(cell); }); body.append(row); });
      node.append(body); wrap.append(el("p", "左右滑动表格，比较各方法的完整结果。", "decision-scroll-hint"), node); return wrap;
    }
    const fraction=m => `${m.correct}/${m.n}`;
    const summary = Object.entries(methods).map(([id,name]) => {
      const m=receipt[phase].metrics[id];
      return after ? [name,fraction(m.changed),fraction(m.preserved),fraction(m.boundary)]
        : [name,fraction(m),`${m.exact_selection}/${m.events}`,String(m.useful_missed),String(m.harmful_selected),`${m.correct_empty}/${m.empty_events}`];
    });
    lab.append(table(after ? "纠正后的范围检查 · 正确数 / 总数" : "初次学习 · 测试集的实际预测",
      after ? ["处理", "应改变范围", "应保留范围", "其中：有效边界"] : ["方法", "标签正确", "选择集合完全正确", "有用候选遗漏", "有害候选误选", "全不选正确"], summary, "decision-summary"));
    const scenarios=recordedScenarios(study);
    const selected=route.scenario || receipt.cases.find(row => row.scope === "changed").event;
    const cases=receipt.cases.map((row,index)=>({...row,indexInReceipt:index})).filter(row=>row.event===selected);
    const picker=el("div", "", "study-controls"); const label=el("label", "逐个事件查看候选与预测"); label.htmlFor="study-scenario";
    const select=el("select", ""); select.id="study-scenario";
    scenarios.forEach(({id})=>{const option=el("option",id);option.value=id;select.append(option);});select.value=selected;
    select.addEventListener("change",()=>{navigate({scenario:select.value},{focus:false});document.querySelector("#study-scenario").focus({preventScroll:true});});
    picker.append(label,select);lab.append(picker);
    const context=cases[0].context;
    lab.append(el("p", `当前任务：${context.family} / ${context.goal}；${context.sensitive ? "敏感" : "普通"}范围。已知：${context.known.join("、")}；可用工具：${context.tools.join("、")}。`, "study-scenario-description"));
    const detailRows=cases.map(row=>[`${row.index+1}. ${row.candidate.description}`, labels[row[after?"expected_v2":"expected_v1"]],
      ...Object.keys(methods).map(id=>{const p=receipt[phase].predictions[id][row.indexInReceipt];return `${p===row[after?"expected_v2":"expected_v1"]?"✓":"✕"} ${labels[p]}`;})]);
    lab.append(table("此事件的完整候选 · ✓ 标签一致 / ✕ 不一致", ["候选经验", "生成规则标签", ...Object.values(methods)],detailRows,"decision-cases"));
    const inputs=el("details", "", "decision-inputs");inputs.append(el("summary","检查此事件的原始观测与两个版本标签"),el("pre",JSON.stringify(cases.map(({indexInReceipt,...row})=>row),null,2)));lab.append(inputs);
    const controls=el("details", "", "decision-inputs");controls.append(el("summary","查看负控制、信息删减与拟合规模"));
    controls.append(el("p", `分类器 ${receipt.cost.scorer_parameters} 个参数，${receipt.cost.fit_steps} 步拟合；案例 ${receipt.cost.saved_cases} 条；规则 ${receipt.cost.rule_leaves} 个叶节点。增量更新只使用 ${receipt.cost.incremental_rows} 条纠正样本。`));
    controls.append(table("置换训练标签后 · 保持测试标签", ["方法","标签正确"],Object.entries(receipt.controls["shuffled-label"]).map(([id,m])=>[{"no-experience":"固定参照",episodic:"案例近邻",rules:"归纳规则",scorer:"小分类器"}[id],fraction(m)]),"decision-control"));
    const ablationNames={"candidate-only":"仅候选独有字段","context-only":"仅 context 敏感字段","relations-only":"仅六个关系特征"};
    controls.append(table("分类器输入删减 · 独立重新拟合",["可见输入","标签正确"],Object.entries(receipt.controls["input-ablations"]).map(([id,m])=>[ablationNames[id],fraction(m)]),"decision-ablation"));
    controls.append(el("p",`任务名称一致重命名：${receipt.controls["identity-invariance"]?"输出不变":"输出发生变化"}。名称原本不进入特征，因此这里只检查实现的标识依赖。`));lab.append(controls);
    const artifacts=el("div","","brief-actions");
    artifacts.append(createExternalLink(`https://github.com/IndelibleVivi/agent-memory-study/blob/main/${study.artifactUrl}`,"方法、源码与完整结果 ↗"));
    const download=el("button","下载实验结果 JSON","brief-download");download.type="button";download.id="decision-download";
    download.addEventListener("click",()=>{const url=URL.createObjectURL(new Blob([JSON.stringify(receipt,null,2)+"\n"],{type:"application/json"}));const a=el("a","");a.href=url;a.download="ams-decision-learning-results.json";document.body.append(a);a.click();a.remove();window.setTimeout(()=>URL.revokeObjectURL(url),1000);});
    artifacts.append(download);lab.append(artifacts);
    return {element:lab,status:`${after?"纠正反馈后":"初次学习"}，${selected}，显示已执行的逐候选预测。`};
  }

  function createInquiryRow(item, kind) {
    const row = createTextElement("article", "", "material-row inquiry-result");
    const copy = createTextElement("div", "", "material-row-copy");
    copy.append(createRouteLink(kind, item.id, item.title, "material-row-title"),
      createTextElement("p", kind === "question" ? item.question : item.when));
    row.append(createTextElement("span", kind === "question" ? "问题" : "判断", "material-row-number"), copy,
      createTextElement("p", kind === "question" ? "持续研究 · 当前判断可修订" : "编者建议 · 目标侧待验证", "material-row-topics"));
    return row;
  }

  function briefActions(query, findingId = null) {
    const actions = createTextElement("div", "", "brief-actions");
    for (const [format, label] of [["markdown", "下载 Markdown"], ["json", "下载 JSON"]]) {
      const button = createTextElement("button", label, "brief-download");
      button.type = "button";
      button.addEventListener("click", () => {
        const brief = window.Practice.brief(data, query, {findingId});
        const content = format === "json" ? JSON.stringify(brief, null, 2) + "\n" : window.Practice.markdown(brief);
        const url = URL.createObjectURL(new Blob([content], {type: format === "json" ? "application/json" : "text/markdown;charset=utf-8"}));
        const link = document.createElement("a"); link.href = url;
        link.download = `ams-${findingId || "practice-brief"}.${format === "json" ? "json" : "md"}`;
        document.body.append(link); link.click(); link.remove();
        window.setTimeout(() => URL.revokeObjectURL(url), 1000);
      });
      actions.append(button);
    }
    return actions;
  }

  function renderInquiryIndex() {
    const el = createTextElement;
    document.querySelector("#question-index").replaceChildren(...(data.questions || []).map((item, index) => {
      const row = el("article", "", "question-entry");
      const heading = el("div", "");
      const title = el("h3", ""); title.append(createRouteLink("question", item.id, item.title));
      heading.append(el("p", `问题 ${String(index + 1).padStart(2, "0")} / 持续研究`, "content-kind"), title, el("p", item.question));
      const current = el("div", "", "question-current");
      current.append(el("p", "目前的认识", "content-kind"), el("p", item.judgment),
        createRouteLink("question", item.id, "读论述、证据与下一问 →", "study-enter"));
      row.append(heading, current); return row;
    }));
    const input = document.querySelector("#practice-query"); input.value = route.practice;
    // Example chips reuse the wording accepted by the canonical finding triggers.
    const examples = ["结果被重复条目占满", "新版说明覆盖了旧版经验", "来源删除后，缓存还有影响吗",
      "改对更正项却损伤保留范围", "输出被挡住，参数算纠正了吗"];
    document.querySelector("#practice-examples").replaceChildren(...examples.map(query => {
      const button = el("button", query); button.type = "button";
      button.addEventListener("click", () => runPracticeQuery(query)); return button;
    }));
    const hits = window.Practice.query(data, route.practice, 3);
    document.querySelector("#practice-result-count").textContent = route.practice
      ? `${hits.length} 条相关判断 · 请核对适用条件` : `先看看这三条判断，或用关键词在全部 ${data.findings.length} 条中检索`;
    const results = document.querySelector("#practice-results");
    results.replaceChildren(...hits.map(({finding, matches}) => {
      const row = el("article", "", "practice-result"); const title = el("h4", "");
      title.append(createRouteLink("finding", finding.id, `${finding.title} →`));
      row.append(title, el("p", finding.action), el("p", `适用：${finding.when}`, "practice-scope"));
      if (route.practice && matches?.length) row.append(el("p", `匹配线索：${matches.join("、")}`, "practice-scope"));
      return row;
    }));
    if (!hits.length) results.append(el("p", `没有找到相关判断。试试“重复候选”“版本更正”或“来源撤回”；当前整理了 ${data.findings.length} 条判断，也可用“全部内容”搜索；空结果不代表这个问题没有研究。`, "practice-empty"));
    document.querySelector("#practice-export").replaceChildren();
    if (hits.length) document.querySelector("#practice-export").append(briefActions(route.practice),
      el("p", "导出当前结果，连同署名、依据和边界。", "practice-scope"));
  }

  function runPracticeQuery(query) {
    navigate({question: null, finding: null, material: null, study: null, thread: null, path: null,
      practice: query.trim()}, {focus: false, hash: "practice"});
    document.querySelector("#practice-query").focus({preventScroll: true});
  }

  function evidenceList(evidence) {
    const list = createTextElement("div", "", "inquiry-evidence-list");
    evidence.forEach(item => {
      const row = createTextElement("section", "", "inquiry-evidence");
      const title = createTextElement("h3", "");
      const url = item.url.startsWith("https://") ? item.url
        : `https://github.com/IndelibleVivi/agent-memory-study/blob/main/${item.url}`;
      title.append(createExternalLink(url, `${item.label} ↗`));
      row.append(title, createTextElement("p", item.observation), createTextElement("p", item.limit, "inquiry-limit"));
      list.append(row);
    });
    return list;
  }

  function renderInquiry(item, kind) {
    const el = createTextElement;
    const fragment = document.createDocumentFragment();
    const back = createRouteLink("home", "", "← 回到研究与实践", "back-link"); back.dataset.scrollTarget = "inquiries";
    const header = el("header", "", "inquiry-heading");
    const title = el("h1", item.title); title.id = "inquiry-title"; title.tabIndex = -1;
    header.append(el("p", kind === "question" ? "A living question / 问题专题" : "A judgment to borrow / 实践判断", "content-kind"), title,
      el("p", kind === "question" ? item.question : item.claim, "inquiry-dek"),
      el("p", `${item.byline} · 更新 ${item.updated} · ${kind === "question" ? "开放问题 / 跨源编者论述" : "编者建议 / 目标侧待验证"}`, "inquiry-meta"));
    fragment.append(back, header);
    const nav = el("nav", "", "study-jump"); nav.setAttribute("aria-label", "研究与实践目录");
    const anchors = kind === "question" ? [["inquiry-judgment","目前的认识"],["inquiry-evidence","已有证据"],["inquiry-next","下一问"],["inquiry-practice","带回实践"]]
      : [["inquiry-use","怎样借用"],["inquiry-evidence","依据与边界"],["inquiry-applications","取用记录"]];
    anchors.forEach(([id, label]) => { const link = el("a", label); link.href = `#${id}`; nav.append(link); }); fragment.append(nav);
    const section = (id, title) => { const node = el("section", "", "inquiry-section"); node.id = id; node.append(el("h2", title)); return node; };
    if (kind === "question") {
      const current = section("inquiry-judgment", "目前的认识");
      current.append(el("p", item.judgment, "inquiry-lead"), el("p", item.intro));
      const explanations = el("div", "", "inquiry-explanations");
      item.explanations.forEach(part => { const block = el("section", ""); block.append(el("h3", part.title), el("p", part.text)); explanations.append(block); });
      current.append(explanations); fragment.append(current);
    } else {
      const use = section("inquiry-use", "怎样借用"); const list = el("dl", "", "inquiry-use");
      for (const [key, label] of [["when","什么时候想起它"],["action","它改变哪个选择"],["avoid","不要这样使用"],["validation","在目标侧怎样检查"]]) {
        list.append(el("dt", label), el("dd", item[key]));
      }
      use.append(list, el("p", item.limit, "inquiry-limit"), briefActions("", item.id)); fragment.append(use);
    }
    const evidence = section("inquiry-evidence", "这件事，是怎么知道的？");
    evidence.append(evidenceList(item.evidence));
    const materials = el("div", "", "inquiry-materials"); materials.append(el("p", "回到材料与精读", "content-kind"));
    item.materialIds.forEach(id => materials.append(createRouteLink("material", id, materialsById.get(id).title)));
    evidence.append(materials); fragment.append(evidence);
    if (kind === "question") {
      const next = section("inquiry-next", "下一次，怎样让认识改变？");
      next.append(el("p", item.nextTest.question, "inquiry-lead"));
      for (const [key,label] of [["comparison","怎样比较"],["success","看什么结果"],["reviseWhen","何时改主意"]]) next.append(el("h3", label),el("p",item.nextTest[key]));
      next.append(el("p",item.nextTest.boundary,"inquiry-limit")); fragment.append(next);
      const practice = section("inquiry-practice", "已有的理解，可以怎样带回去？");
      practice.append(el("p", item.findingIds.length ? "下面是可以独立引用的编者判断。已有实验支持限定范围内的认识；具体迁移方法仍需在目标系统验证。" : "本专题尚未形成独立的实践判断。可以先查看共读与已执行实验，沿着条件、失败和下一问继续研究。"),
        ...item.findingIds.map(id => createInquiryRow(findingsById.get(id), "finding")));
      item.studyIds.forEach(id => practice.append(createRouteLink("study", id, `亲手比较：${studiesById.get(id).title} →`, "inquiry-onward")));
      fragment.append(practice);
    } else {
      const applications = section("inquiry-applications", "取用之后，发生了什么？");
      const statuses = {adopted:"已采用",rejected:"未采用",inconclusive:"尚无定论",cited:"已引用"};
      if (!item.applications.length) applications.append(el("p", "尚无公开的目标侧取用记录。没有记录不等于已验证，也不等于没有价值。"));
      item.applications.forEach(app => {
        const block = el("section", "", "inquiry-evidence"); const heading = el("h3", "");
        const url = app.url.startsWith("https://") ? app.url : `https://github.com/IndelibleVivi/agent-memory-study/blob/main/${app.url}`;
        heading.append(createExternalLink(url, `${app.title} ↗`));
        block.append(el("p", `${statuses[app.status]} · ${app.date}`, "content-kind"), heading,
          el("p", app.decision), el("p", app.observation), el("p", app.limit, "inquiry-limit")); applications.append(block);
      });
      applications.append(el("p", "引用过、采用过、有帮助是不同结论。负反馈与不采用也值得保留；迁移反馈由目标项目决定公开范围。", "inquiry-limit"));
      item.questionIds.forEach(id => applications.append(createRouteLink("question", id, `继续追问：${questionsById.get(id).title} →`, "inquiry-onward")));
      fragment.append(applications);
    }
    refs.inquiryView.replaceChildren(fragment);
  }

  function render(options = {}) {
    renderView(options);
    if (physicalRoutes) {
      document.querySelectorAll('a[href^="#"], a[data-fragment]').forEach(link => {
        const hash = link.dataset.fragment || link.getAttribute("href");
        link.dataset.fragment = hash;
        link.href = routeUrl(route, hash);
      });
    }
    const meta = seo.metadata(data, route);
    document.title = meta.title;
    function setMeta(attribute, name, content) {
      let node = document.querySelector(`meta[${attribute}="${name}"]`);
      if (!node) { node = document.createElement("meta"); node.setAttribute(attribute, name); document.head.append(node); }
      node.content = content;
    }
    setMeta("name", "description", meta.description);
    for (const [name, value] of Object.entries({title: meta.title, description: meta.description, url: meta.canonical, type: "website", site_name: "Agent Memory Study", locale: "zh_CN", image: meta.image, "image:alt": "Agent Memory Study 标识"})) {
      setMeta("property", `og:${name}`, value);
    }
    for (const [name, value] of Object.entries({card: "summary", title: meta.title, description: meta.description, image: meta.image})) setMeta("name", `twitter:${name}`, value);
    let canonical = document.querySelector('link[rel="canonical"]');
    if (!canonical) { canonical = document.createElement("link"); canonical.rel = "canonical"; document.head.append(canonical); }
    canonical.href = meta.canonical;
    let structured = document.querySelector('#seo-structured-data');
    if (!structured) { structured = document.createElement("script"); structured.type = "application/ld+json"; structured.id = "seo-structured-data"; document.head.append(structured); }
    structured.textContent = JSON.stringify(meta.structured).replace(/</g, "\\u003c");
  }

  function renderView(options = {}) {
    const { focus = false, hash = window.location.hash } = options;
    const material = materialsById.get(route.material);
    const showingMaterial = Boolean(material);
    const study = !material && studiesById.get(route.study);
    const question = !material && !study && questionsById.get(route.question);
    const finding = !material && !study && !question && findingsById.get(route.finding);
    const inquiry = question || finding;
    refs.inquiryView.hidden = !inquiry;
    refs.studyView.hidden = !study;
    refs.atlasView.hidden = showingMaterial || Boolean(study) || Boolean(inquiry);
    refs.materialView.hidden = !showingMaterial;
    document.body.classList.toggle("is-reading", showingMaterial || Boolean(study) || Boolean(inquiry));
    closeMenu();

    if (inquiry) {
      renderInquiry(inquiry, question ? "question" : "finding");
      refs.routeStatus.textContent = `已打开${question ? "问题专题" : "实践判断"}：${inquiry.title}`;
      if (focus) {
        window.scrollTo({top: 0, behavior: "auto"});
        document.querySelector("#inquiry-title").focus({preventScroll: true});
      }
      if (hash) window.requestAnimationFrame(() => fragmentTarget(hash)?.scrollIntoView());
      return;
    }
    if (study) {
      renderStudy(study);
      if (focus) {
        window.scrollTo({top: 0, behavior: "auto"});
        document.querySelector("#study-title").focus({preventScroll: true});
      }
      return;
    }
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
            ? fragmentTarget(hash)
            : document.querySelector("#main-content");
      if (target) {
        target.scrollIntoView({ behavior: "auto", block: "start" });
        if (focus && target.matches("[tabindex]")) target.focus({ preventScroll: true });
      }
    });
  }

  function fragmentTarget(hash) {
    // A shared URL fragment is an ID, not a CSS selector.
    try { return document.getElementById(decodeURIComponent(hash.replace(/^#/, ""))); }
    catch { return null; }
  }

  function updateFilters(changes) {
    navigate({ ...changes, question: null, finding: null, material: null, study: null, scenario: null, phase: "before" }, { replace: true, focus: false });
  }

  function closeMenu() {
    refs.siteNav.classList.remove("is-open");
    refs.menuButton.setAttribute("aria-expanded", "false");
  }

  document.querySelector("#practice-form").addEventListener("submit", event => {
    event.preventDefault(); runPracticeQuery(document.querySelector("#practice-query").value);
  });

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
    if (type === "question" || type === "finding") {
      navigate({material: null, study: null, question: type === "question" ? id : null,
        finding: type === "finding" ? id : null, scenario: null, phase: "before", thread: null, path: null}, {focus: true});
      return;
    }
    if (type === "study") {
      navigate({question: null, finding: null, material: null, study: id, scenario: null, phase: "before", thread: null, path: null}, {focus: true});
      return;
    }
    if (type === "material") {
      navigate({ question: null, finding: null, material: id, study: null, scenario: null, phase: "before", thread: null, path: null }, { focus: true });
      return;
    }
    if (type === "thread") {
      navigate({ question: null, finding: null, material: null, study: null, scenario: null, phase: "before", thread: id, path: null, surface: id }, { focus: true });
      return;
    }
    if (type === "path") {
      navigate({ question: null, finding: null, material: null, study: null, scenario: null, phase: "before", thread: null, path: id }, { focus: true });
      return;
    }
    if (type === "home") {
      const scrollTarget = link.dataset.scrollTarget || "";
      navigate({ question: null, finding: null, material: null, study: null, scenario: null, phase: "before", thread: null, path: null }, {
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

  if (physicalRoutes) {
    // Keep old query links addressable; redirect to a real page whose initial HTML has the matching canonical.
    const target = routeUrl(route, window.location.hash);
    if (new URL(target, window.location.href).pathname !== window.location.pathname) {
      window.location.replace(target);
      return;
    }
  }
  render({ focus: false, hash: window.location.hash });
})();
