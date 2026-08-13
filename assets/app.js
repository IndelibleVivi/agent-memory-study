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
  const defaultSurfaceId = surfacesById.has("retrieval-active-context")
    ? "retrieval-active-context"
    : data.atlas.failureSurfaces[0].id;
  const routeKeys = ["material", "thread", "path", "q", "topic", "surface", "depth"];
  const depthOrder = ["abstract", "skim", "read", "worked"];
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
    emptyState: document.querySelector("#empty-state"),
    editorialNote: document.querySelector("#editorial-note"),
    materialNumber: document.querySelector("#material-number"),
    materialTitle: document.querySelector("#material-title"),
    materialMeta: document.querySelector("#material-meta"),
    materialSurfaceLinks: document.querySelector("#material-surface-links"),
    materialIntro: document.querySelector("#material-intro"),
    materialPoints: document.querySelector("#material-points"),
    findingsSection: document.querySelector("#paper-findings"),
    materialFindings: document.querySelector("#material-findings"),
    materialLimits: document.querySelector("#material-limits"),
    limitsFallback: document.querySelector("#limits-fallback"),
    materialInferences: document.querySelector("#material-inferences"),
    materialQuestion: document.querySelector("#material-question"),
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

  function renderAtlasFrame() {
    refs.atlasTitle.textContent = data.atlas.thesis;
    refs.atlasDek.textContent = data.atlas.dek;
    refs.atlasLabel.textContent = data.atlas.editorialLabel;
    refs.editorialNote.textContent = data.editorialNote;
    renderSurfaces();
    renderPaths();
    syncControls();
    renderLibrary();
  }

  function selectedSurface() {
    return surfacesById.get(route.thread || route.surface || defaultSurfaceId)
      || data.atlas.failureSurfaces[0];
  }

  function renderSurfaces() {
    const selected = selectedSurface();
    const rows = data.atlas.failureSurfaces.map((surface) => {
      const item = document.createElement("li");
      const link = createRouteLink("thread", surface.id, "", "surface-link");
      link.setAttribute("aria-current", String(surface.id === selected.id));
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
      const inferenceText = (material.editorialInferences || [])
        .map((inference) => `${inference.label} ${inference.text} ${inference.boundary}`)
        .join(" ");
      const haystack = normalize([
        material.title,
        material.authors.join(" "),
        material.shortAuthor,
        material.year,
        material.intro,
        material.editorialQuestion,
        material.keyPoints.join(" "),
        (material.reportedFindings || []).join(" "),
        (material.evidenceLimits || []).join(" "),
        material.keywords.join(" "),
        inferenceText,
      ].join(" "));
      return haystack.includes(query);
    });
  }

  function renderLibrary() {
    const materials = matchingMaterials();
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

    const findings = material.reportedFindings || [];
    refs.findingsSection.hidden = findings.length === 0;
    refs.materialFindings.replaceChildren(...findings.map((finding) => createTextElement("li", finding)));

    const limits = material.evidenceLimits || [];
    refs.materialLimits.replaceChildren(...limits.map((limit) => createTextElement("li", limit)));
    refs.materialLimits.hidden = limits.length === 0;
    refs.limitsFallback.hidden = limits.length !== 0;

    const inferences = material.editorialInferences || [];
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
    const sections = [...document.querySelectorAll(".article-main > .article-section:not([hidden])")];
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
    document.querySelectorAll(".article-main > .article-section:not([hidden])").forEach((section) => {
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
      : `研究地图：${activeSurface.label}`;
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

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && refs.siteNav.classList.contains("is-open")) {
      closeMenu();
      refs.menuButton.focus();
    }
  });

  document.addEventListener("click", (event) => {
    if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    const link = event.target.closest("a[data-route]");
    if (!link) return;
    event.preventDefault();
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
  });

  window.addEventListener("popstate", () => {
    route = readRoute();
    render({ focus: true, hash: window.location.hash });
  });

  render({ focus: false, hash: window.location.hash });
})();
