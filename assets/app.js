(() => {
  "use strict";

  if (window.AMS_READER_SHELL) document.querySelector("#main-content").innerHTML = window.AMS_READER_SHELL;
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
  const searchIndex = window.ReadingSearch.buildIndex(data);
  let route = readRoute();
  let articleObserver = null;
  let constellationController = null;

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
      domain: data.room.domains.some(x=>x.id===params.get("domain")) ? params.get("domain") : null,
      direction: data.room.directions.some(x=>x.id===params.get("direction")) ? params.get("direction") : null,
      ...window.StudyDesk.exerciseState(studiesById.get(study)?.exercise, Object.fromEntries(params)),
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
    captureDeskPosition();
    const { replace = false, hash = "", focus = true } = options;
    route = {
      ...route,
      ...nextRoute,
    };
    const exercise = window.StudyDesk.exerciseState(studiesById.get(route.study)?.exercise, route);
    for (const key of ["k", "ranking", "need", "dataset", "mutation", "repair", "query"]) delete route[key];
    Object.assign(route, exercise);
    const method = replace ? "replaceState" : "pushState";
    window.history[method]({}, "", routeUrl(route, hash));
    render({ focus, hash });
  }

  function normalize(value) {
    return String(value || "").toLocaleLowerCase("zh-CN").normalize("NFKC");
  }

  function routeHref(type, id) {
    const next = { ...route, question: null, finding: null, material: null, study: null, scenario: null, phase: "before", thread: null, path: null };
    if (type === "domain") next.domain = id;
    if (type === "direction") next.direction = id;
    if (type === "material") next.material = id;
    if (type === "study") next.study = id;
    if (type === "question") next.question = id;
    if (type === "finding") next.finding = id;
    if (type === "thread") {
      next.thread = id;
      next.surface = id;
    }
    if (type === "path") next.path = id;
    return routeUrl(next, type === "domain" ? "#domains" : type === "direction" ? "#directions" : "");
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
    renderRoom();
    refs.atlasLabel.textContent = data.atlas.editorialLabel;
    refs.editorialNote.textContent = data.editorialNote;
    renderSurfaces();
    renderConstellation();
    renderPaths();
    renderStudyIndex();
    renderInquiryIndex();
    syncControls();
    renderLibrary();
    document.querySelector("#library-count-label").textContent = `${searchIndex.length} 条公开内容`;
    if(route.q || route.topic || route.surface || route.depth || window.location.hash === "#library") document.querySelector("#library-catalog").open=true;
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

  function renderConstellation() {
    if (!constellationController) constellationController = window.AMSConstellation.mount({
      root: document.querySelector("#constellation"), data, routeHref
    });
    else constellationController.refresh();
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
    refs.sourceRail.replaceChildren(sourceContent);
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

  function studyLabel(study) {
    return ({"learning-note":"学习记录", "research-essay":"研究论述", "editorial-synthesis-with-proposed-experiment":"共读 · 未执行方案", "editorial-synthesis-with-recorded-experiment":"共读 · 已保存研究结果", "editorial-synthesis-with-deterministic-demo":"共读 · 原创规则演示"})[study.kind] || "研究记录";
  }

  function researchPlate(id) {
    const ns = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(ns, "svg");
    svg.setAttribute("viewBox", "0 0 400 230"); svg.setAttribute("class", "research-plate");
    svg.setAttribute("aria-hidden", "true");
    const add = (tag, attributes, text = "") => {
      const node = document.createElementNS(ns, tag);
      Object.entries(attributes).forEach(([key, value]) => node.setAttribute(key, value));
      node.textContent = text; svg.append(node); return node;
    };
    if (id === "experience-becomes-policy") {
      for (let r=0; r<5; r++) {
        add("ellipse", {cx:195,cy:105,rx:35+r*27,ry:16+r*13,transform:"rotate(-17 195 105)",class:"plate-main plate-dim"});
      }
      add("path", {d:"M115 142Q150 80 200 105T286 65M278 65l8 0 -3 8",class:"plate-main"});
      add("circle", {cx:115,cy:142,r:5,class:"plate-fill"});
      add("circle", {cx:286,cy:65,r:5,class:"plate-dot"});
      add("text",{x:94,y:170},"θ");add("text",{x:300,y:62},"θ′");
      add("text",{x:35,y:207},"03 / ΔD → revise → θ′");
    } else if (id === "retrieval-and-relevance") {
      add("circle", {cx:166,cy:107,r:65,class:"plate-fill"});
      add("circle", {cx:235,cy:107,r:65,class:"plate-main"});
      for (let i=0;i<28;i++) { const angle=i*2.39996, r=52*Math.sqrt((i+.5)/28);add("circle",{cx:166+Math.cos(angle)*r,cy:107+Math.sin(angle)*r,r:1.7,class:"plate-dot"}); }
      add("text",{x:102,y:26},"retrieved");add("text",{x:240,y:26},"relevant");
      add("path",{d:"M166 175v12h69v-12",class:"plate-main"});
      add("text",{x:35,y:212},"01 / A ∩ B ≠ A");
    } else {
      add("path",{d:"M65 175H340M65 175V35M65 175 320 50",class:"plate-main plate-dim"});
      add("path",{d:"M75 165C120 165 115 120 159 120S225 106 242 77 295 68 326 44",class:"plate-main"});
      for(let i=0;i<12;i++){const x=78+i*22,y=164-i*10+(i%3-1)*8;add("circle",{cx:x,cy:y,r:2.8,class:"plate-dot"});}
      add("text",{x:65,y:24},"position");add("text",{x:322,y:195},"key");
      add("text",{x:35,y:212},"02 / f(key) ≈ position");
    }
    return svg;
  }

  function directionMark(id) {
    const ns = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(ns, "svg");
    svg.setAttribute("viewBox", "0 0 260 80");
    svg.setAttribute("class", "direction-graphic");
    svg.setAttribute("aria-hidden", "true");
    const mark = (tag, attrs) => {
      const node = document.createElementNS(ns, tag);
      for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value);
      svg.append(node);
    };
    // Concept sketches describe the three questions, not measured research data.
    if (id === "forms") {
      for (let i = 0; i < 9; i++) {
        const y = 12 + i * 7;
        mark("path", {d: `M10 ${y} C70 ${40 + Math.sin(i * 2) * 30} 110 ${y} 155 ${y}`, class: "direction-flow"});
        mark("rect", {x: 164 + (i % 3) * 23, y: 13 + Math.floor(i / 3) * 21, width: 14, height: 12, class: i === 4 ? "direction-solid" : ""});
      }
    } else if (id === "relevance") {
      for (let i = 0; i < 5; i++) {
        const y = 12 + i * 14;
        mark("path", {d: `M25 40 C95 40 125 ${y} 208 ${y}`, class: i === 2 ? "direction-flow direction-strong" : "direction-dim"});
        mark("circle", {cx: 214, cy: y, r: i === 2 ? 6 : 3.5, class: i === 2 ? "direction-solid" : ""});
      }
      mark("circle", {cx: 25, cy: 40, r: 9});
    } else {
      for (let i = 0; i < 5; i++) {
        const y = 16 + i * 12;
        mark("path", {d: `M12 ${y} C80 ${y} 100 ${i < 2 ? y : 72 - i * 12} 152 ${i < 2 ? y : 72 - i * 12} S202 ${y} 245 ${y}`, class: i === 2 ? "direction-flow direction-strong" : ""});
      }
      mark("path", {d: "M112 3V77 M174 3V77", class: "direction-dim"});
    }
    return svg;
  }

  function renderRoom() {
    const el = createTextElement;
    refs.atlasTitle.replaceChildren(...(data.room.heroTitle || data.room.thesis).split("\n").map(text => el("span", text)));
    document.querySelector("#hero-question").replaceChildren(...data.room.thesis.split("、").map((part,i,all)=>el("span",part+(i<all.length-1?"、":""))));
    refs.atlasDek.textContent = data.room.intro;
    document.querySelector("#room-edition").textContent = data.room.edition;
    document.querySelector("#room-invitation").textContent = data.room.invitation;
    document.querySelector("#room-start-list").replaceChildren(...data.room.starts.map((start, i) => {
      const item = studiesById.get(start.studyId); const node = el("article", "", "start-entry");
      const title = el("h3", "");
      const titleLink = createRouteLink("study", item.id, "");
      start.prompt.split(/([A-Za-z][A-Za-z0-9]*(?:-[A-Za-z0-9]+)+)/).forEach((part, index) => {
        titleLink.append(index % 2 ? el("span", part, "unbroken-term") : document.createTextNode(part));
      });
      title.append(titleLink);
      node.append(el("p", `0${i+1} / ${start.kicker}`, "eyebrow"));
      node.append(researchPlate(item.id));
      if(start.notation) node.append(el("pre", start.notation, "start-notation"));
      node.append(title, el("p", item.intro), createRouteLink("study", item.id, "进入这次研究 ↗", "text-arrow")); return node;
    }));
    document.querySelector("#direction-list").replaceChildren(...data.room.directions.map((direction, i) => {
      const link = createRouteLink("direction", direction.id, "", "direction-row");
      if (route.direction === direction.id) link.setAttribute("aria-current", "true");
      const copy = el("span", "", "direction-copy"); copy.append(el("span", direction.title, "direction-title"), el("span", direction.intro));
      const notation=el("span", "", "direction-notation");
      notation.append(directionMark(direction.id), el("code", direction.notation || ""));
      link.append(el("span", `0${i+1}`, "direction-number"), copy, notation, el("span", "↗", "direction-arrow")); return link;
    }));
    const groupLinks = (group, target) => {
      target.replaceChildren(el("p", group.english || "", "eyebrow"), el("h3", group.title), el("p", group.question || group.intro, "group-question"));
      const links = el("div", "", "group-readings");
      for (const [field, kind, map] of [["studyIds","study",studiesById],["questionIds","question",questionsById],["materialIds","material",materialsById]]) {
        (group[field] || []).forEach(id => { const item = map.get(id); links.append(createRouteLink(kind, id, item.title + " ↗")); });
      }
      target.append(links);
    };
    const focus = document.querySelector("#direction-focus");
    const direction = data.room.directions.find(item => item.id === route.direction);
    focus.hidden = !direction; if (direction) groupLinks(direction, focus);
    document.querySelector("#domain-list").replaceChildren(...data.room.domains.map((domain, i) => {
      const link = createRouteLink("domain", domain.id, "", "domain-link");
      link.append(el("span", String(i+1).padStart(2,"0")), el("strong", domain.title), el("small", domain.english));
      if (domain.id === (route.domain || data.room.domains[0].id)) link.setAttribute("aria-current", "true"); return link;
    }));
    groupLinks(data.room.domains.find(item => item.id === route.domain) || data.room.domains[0], document.querySelector("#domain-focus"));
    document.querySelector("#room-change-list").replaceChildren(...data.room.changes.map(change => {
      const node = el("article", "", "change-entry"); const h = el("h3", ""); h.append(createRouteLink("study", change.studyId, change.title));
      node.append(el("time", change.date), h, el("p", change.text)); return node;
    }));
    const legacy = document.querySelector("#legacy-lenses");
    if (route.thread || route.path || ["#research-map","#reading-paths","#surface-focus"].includes(window.location.hash)) legacy.open = true;
    if (route.practice || window.location.hash === "#practice") document.querySelector(".practice-disclosure").open = true;
  }

  function renderStudyIndex() {
    const programme = new Set(["ams-thesis","how-we-study", ...data.room.directions.flatMap(item => item.studyIds.slice(0,1))]);
    const entries = data.studies.filter(item => !programme.has(item.id)).sort((a,b) => b.date.localeCompare(a.date) || a.title.localeCompare(b.title));
    refs.studyIndex.replaceChildren(...entries.map((study,index) => {
      const entry = createTextElement("article", "", "study-entry");
      entry.dataset.ordinal=String(index+1).padStart(2,"0");
      const heading = createTextElement("h3", ""); heading.append(createRouteLink("study", study.id, study.title));
      const copy = createTextElement("div", ""); copy.append(heading, createTextElement("p", study.intro));
      entry.append(createTextElement("p", studyLabel(study), "content-kind"), copy, createTextElement("time", study.date)); return entry;
    }));
  }

  function renderStudy(study) {
    const el = createTextElement;
    const fragment = document.createDocumentFragment();
    const header = el("header", "", "study-heading");
    const title = el("h1", study.title); title.id = "study-title"; title.tabIndex = -1;
    header.append(el("p", studyLabel(study), "content-kind"), title, el("p", study.intro, "study-dek"), el("p", `${study.byline} · ${study.date}`, "study-byline"));
    fragment.append(createRouteLink("home", "", "← 回到书房", "back-link"), header);
    const reading = el("section", "", "study-reading"); reading.id = "study-reading";
    const essay = el("div", "", "study-essay");
    // HTML is produced by the local Markdown compiler with raw HTML disabled.
    essay.innerHTML = study.bodyHtml;
    if (essay.firstElementChild?.tagName === "H1") essay.firstElementChild.remove();
    const toc = el("nav", "", "study-toc"); toc.setAttribute("aria-label", "本文目录"); toc.append(el("p", "在这篇里", "eyebrow"));
    essay.querySelectorAll("h2").forEach((h, i) => { h.id = `section-${i+1}`; const a=el("a", h.textContent); a.href=`#${h.id}`; toc.append(a); });
    essay.querySelectorAll("table").forEach(table => { const wrap=el("div","","table-scroll"); wrap.tabIndex=0; wrap.setAttribute("role","region"); wrap.setAttribute("aria-label","内容对照表，可横向滚动"); table.replaceWith(wrap); wrap.append(table); });
    essay.querySelectorAll("a").forEach(a => {
      const url = new URL(a.getAttribute("href"), siteRoot);
      const id = url.searchParams.get("study");
      if (id && studiesById.has(id)) { a.dataset.route="study"; a.dataset.routeId=id; a.href=routeHref("study", id) + url.hash; }
      else if (url.origin === siteRoot.origin && !a.getAttribute("href").startsWith("#")) a.href=url.href;
    });
    reading.append(toc, essay); fragment.append(reading);
    let lab = null;
    if (study.kind === "editorial-synthesis-with-proposed-experiment") lab=renderProposedLab(study);
    if (study.kind === "editorial-synthesis-with-recorded-experiment") lab=renderRecordedLab(study);
    if (study.kind === "editorial-synthesis-with-deterministic-demo") lab=renderRevisionLab(study);
    if (lab) fragment.append(lab.element);
    if (lab || study.exercise) { const a=el("a", study.kind === "editorial-synthesis-with-proposed-experiment" ? "下一项研究" : study.exercise ? "亲手演算" : "亲手比较"); a.href="#study-lab"; toc.append(a); }
    if (study.exercise === "retrieval-sets") fragment.append(renderRetrievalExercise());
    if (study.exercise === "ordered-index") fragment.append(renderIndexExercise());
    const sourceCount = study.readings.length + study.externalReadings.length;
    if (sourceCount) {
      const sources = el("details", "", "study-sources"); sources.id="study-sources"; const sourceJump=el("a","来源与阅读范围"); sourceJump.href="#study-sources"; toc.append(sourceJump); sources.append(el("summary", `来源与实际阅读范围 · ${sourceCount}`));
      study.readings.forEach(reading => {
        const material=materialsById.get(reading.materialId); const row=el("section","","study-source"); const h=el("h3",""); h.append(createRouteLink("material",material.id,reading.label));
        row.append(h,el("p",reading.takeaway),el("p",reading.locator,"study-locator"),el("p",reading.limit,"study-source-limit"),createExternalLink(material.sourceUrl,"回原文 ↗")); sources.append(row);
      });
      study.externalReadings.forEach(source => {
        const row=el("section","","study-source"); const h=el("h3",""); h.append(createExternalLink(source.url,source.label));
        row.append(el("p",source.kind,"content-kind"),h,el("p",source.takeaway),el("p",source.locator,"study-locator"),el("p",source.limit,"study-source-limit")); sources.append(row);
      }); fragment.append(sources);
    }
    if (study.takeaways.length || study.closing) {
      const takeaway=el("section","","study-takeaways"); takeaway.id="study-takeaways"; const takeawayJump=el("a","留下的理解");takeawayJump.href="#study-takeaways";toc.append(takeawayJump);takeaway.append(el("h2","留下的理解"));
      study.takeaways.forEach(item => takeaway.append(el("h3",item.title),el("p",item.text)));
      if (study.closing) takeaway.append(el("p",study.closing)); fragment.append(takeaway);
    }
    if (study.boundary && !lab) fragment.append(el("p",study.boundary,"study-boundary"));
    if (study.changes?.length) {
      const changes=el("section","","understanding-changes"); changes.append(el("p","理解怎样变化","eyebrow"));
      study.changes.forEach(change=>changes.append(el("time",change.date),el("p",`此前：${change.before}`),el("p",`现在：${change.after}`),el("p",change.basis,"study-locator"))); fragment.append(changes);
    }
    if (study.continuation) {
      const c=study.continuation; const onward=el("section","","continuation"); onward.append(el("p","下次，从这里继续","eyebrow"),el("h2",c.question),el("p",c.why));
      c.studyIds.forEach(id=>onward.append(createRouteLink("study",id,studiesById.get(id).title+" ↗")));
      c.materialIds.forEach(id=>onward.append(createRouteLink("material",id,materialsById.get(id).title+" ↗"))); fragment.append(onward);
    }
    const questions=data.questions.filter(item=>item.studyIds.includes(study.id));
    if (questions.length) {const onward=el("section","","study-onward");onward.append(el("h2","继续追问"));questions.forEach(item=>onward.append(createInquiryRow(item,"question")));fragment.append(onward);}
    refs.studyView.replaceChildren(fragment);
    refs.routeStatus.textContent=`已打开${studyLabel(study)}：${study.title}${lab ? `。${lab.status}` : ""}`;
  }

  function renderRetrievalExercise() {
    const el=createTextElement, x=window.StudyDesk.exercise(route);
    const lab=el("section","","study-lab retrieval-exercise");lab.id="study-lab";
    lab.append(el("p","ORIGINAL TEACHING SET / 原创集合演算","eyebrow"),el("h2","换一个集合，看看比例怎样变化。"),el("p","a–h、顺序与相关集合均为设定；这里没有执行 embedding、ANN 或模型检索。"));
    const controls=el("div","","study-controls"); controls.dataset.jsControl="";
    for(const [field,label,options] of [["ranking","返回的排序",[["reference","A · 与参考近邻相同"],["contrast","B · 手工对照"]]],["need","当前相关集合",[["understand","R₁ = {a, d, e, f}"],["implement","R₂ = {b, c, g}"]]]]) {
      const wrap=el("label",label);const select=el("select","");select.id=`retrieval-${field}`;options.forEach(([value,text])=>{const o=el("option",text);o.value=value;select.append(o);});select.value=x[field];
      select.addEventListener("change",()=>{navigate({[field]:select.value},{focus:false,hash:"study-lab"});document.querySelector(`#retrieval-${field}`).focus({preventScroll:true});});wrap.append(select);controls.append(wrap);
    }
    const wrap=el("label",`取前 k 项：${x.k}`);const input=document.createElement("input");input.type="range";input.min=1;input.max=8;input.value=x.k;input.id="retrieval-k";
    input.addEventListener("input",()=>{navigate({k:Number(input.value)},{replace:true,focus:false,hash:"study-lab"});document.querySelector("#retrieval-k").focus({preventScroll:true});});wrap.append(input);controls.append(wrap);lab.append(controls);
    const row=el("div","","retrieval-documents"); window.StudyDesk.documents.forEach(id=>{const chip=el("span",id,`retrieval-doc ${x.selected.includes(id)?"is-selected":""} ${x.relevant.includes(id)?"is-relevant":""}`);chip.title=`${id}：${x.selected.includes(id)?"已返回":"未返回"}，${x.relevant.includes(id)?"与需求相关":"不相关"}`;row.append(chip);});lab.append(row,el("p","深色底 = 已返回 · 下划线 = 需求相关","study-locator"));
    const results=el("div","","retrieval-metrics");results.setAttribute("aria-live","polite");
    for(const [label,value,formula] of [["近邻集合召回",x.neighborRecall,`${x.overlap.length} / ${x.k}`],[`Precision@${x.k}`,x.precision,`${x.hits.length} / ${x.k}`],[`Recall@${x.k}`,x.recall,`${x.hits.length} / ${x.relevant.length}`]]) {
      const cell=el("div","");cell.append(el("span",label),el("strong",`${(value*100).toFixed(1)}%`),el("span",formula));results.append(cell);
    }lab.append(results,el("p",`返回 {${x.selected.join(", ")}} · 参考近邻 {${x.reference.join(", ")}} · 相关 {${x.relevant.join(", ")}}`,"study-locator"));return lab;
  }

  function renderIndexExercise() {
    const el = createTextElement, engine = window.IndexStudy, x = engine.evaluate(route);
    const lab = el("section", "", "study-lab index-exercise"); lab.id = "study-lab";
    lab.append(el("p", "A POSITION IS A PREDICTION / 原创索引演算", "eyebrow"),
      el("h2", "预测可以出错。查找怎样保持正确？"),
      el("p", "先查找 70，再插入四个键：原来正确的位置会移动。试着只重测误差界，再重新拟合，观察哪些状态改变了。这里实际计算线性回归与二分查找，没有运行论文模型或 DSI。", "study-lab-intro"));
    const controls = el("div", "", "study-controls index-controls"); controls.dataset.jsControl = "";
    const update = (next, id) => {
      navigate(next, {focus: false, hash: "study-lab"});
      document.getElementById(id)?.focus({preventScroll: true});
    };
    for (const [field, label, options] of [
      ["dataset", "键的分布", engine.DATASETS.map(d => [d.id, d.label])],
      ["mutation", "记录状态", [["base", "原始记录"], ["insert", "插入一组新键"]]],
      ["repair", "索引怎样跟上", [["stale", "沿用旧模型与旧界"], ["rebound", "保留模型，重测误差界"], ["retrain", "重新拟合与校准"]]],
    ]) {
      const labelEl = el("label", label), select = el("select", ""); select.id = `index-${field}`;
      for (const [value, text] of options) { const option = el("option", text); option.value = value; select.append(option); }
      select.value = x.state[field]; select.disabled = field === "repair" && x.state.mutation === "base";
      select.addEventListener("change", () => update(field === "dataset"
        ? {dataset: select.value, mutation: "base", repair: "stale", query: engine.DATASETS.find(d => d.id === select.value).query}
        : {[field]: select.value}, select.id));
      labelEl.append(select); controls.append(labelEl);
    }
    const form = el("form", "", "index-query"), queryLabel = el("label", "查找键 · 0–130"), query = el("input", "");
    query.id = "index-query"; query.type = "number"; query.min = 0; query.max = 130; query.step = 1; query.required = true; query.value = x.state.query;
    queryLabel.append(query); const search = el("button", "查找 →"); search.type = "submit";
    form.append(queryLabel, search); form.addEventListener("submit", event => {event.preventDefault(); if(form.reportValidity()) update({query: Number(query.value)}, query.id);});
    controls.append(form); lab.append(controls);

    const board = el("div", "", "index-board"), figure = el("figure", "", "index-figure");
    const svgns = "http://www.w3.org/2000/svg";
    const svgEl = (name, attrs) => { const node = document.createElementNS(svgns, name); for(const [key, value] of Object.entries(attrs)) node.setAttribute(key, value); return node; };
    const svg = svgEl("svg", {viewBox: "0 0 600 260", role: "img", "aria-label": "真实键的位置与当前线性预测；具体数值见下面的逐键误差表"});
    const px = key => 40 + key / 130 * 520, py = rank => 220 - Math.max(-1, Math.min(x.keys.length + 1, rank)) / (x.keys.length + 1) * 190;
    for (let rank = 0; rank <= x.keys.length; rank += 2) svg.append(svgEl("line", {x1:40,x2:560,y1:py(rank),y2:py(rank),class:"index-gridline"}));
    svg.append(svgEl("rect", {x:40,y:py(x.window.hi),width:520,height:Math.max(2, py(x.window.lo)-py(x.window.hi)),class:"index-band"}));
    const curve = Array.from({length:131},(_,key)=>`${key ? "L" : "M"}${px(key)},${py(x.model.a*key+x.model.b)}`).join(" ");
    svg.append(svgEl("path",{d:curve,class:"index-prediction"}), svgEl("line",{x1:px(x.state.query),x2:px(x.state.query),y1:14,y2:244,class:"index-query-line"}));
    for (const row of x.rows) {
      const cx=px(row.key), cy=py(row.rank);
      const dot=row.inserted
        ? svgEl("path",{d:`M${cx},${cy-7} l7,7 -7,7 -7,-7 Z`,class:"index-point is-inserted"})
        : svgEl("circle",{cx,cy,r:row.key===x.state.query?7:5.5,class:"index-point"});
      const title=svgEl("title",{}); title.textContent=`键 ${row.key} · 位置 ${row.rank}${row.inserted?" · 新插入":""}`;dot.append(title);svg.append(dot);
    }
    for (const key of [0,65,130]) {const label=svgEl("text",{x:px(key),y:250,"text-anchor":"middle",class:"index-axis-label"});label.textContent=key;svg.append(label);}
    for (const rank of [0,Math.floor(x.keys.length/2),x.keys.length]) {const label=svgEl("text",{x:24,y:py(rank)+5,"text-anchor":"end",class:"index-axis-label"});label.textContent=rank;svg.append(label);}
    figure.append(el("p", "位置 ↑ · 预测线与真实记录", "index-axis"),svg,
      el("figcaption", "圆点：原有记录　铜色菱形：新增记录　斜线：f(k)　色带：当前搜索窗口　竖线：查找键 →", "index-legend"));
    const summary = el("div", "", "index-summary"); summary.id = "index-summary"; summary.setAttribute("aria-live", "polite");
    summary.dataset.fallback = String(x.result.fallback);
    const accepted = x.result.found ? `找到 ${x.state.query}` : x.result.position === x.keys.length ? "没有相等键 · 位于末尾" : `没有相等键 · 后继 ${x.keys[x.result.position]}`;
    summary.append(el("p", x.result.fallback ? "旧窗口未通过检查 → 全区间回退" : "相邻键检查通过 → 接受局部结果", "index-verdict"),el("h3", accepted));
    const metrics = el("dl", "", "index-metrics");
    for(const [label, value] of [["预测位置 p(q)", x.window.prediction],["局部候选位置",x.local.position],["最终 lower_bound",x.result.position]]) {
      const pair=el("div","");pair.append(el("dt",label),el("dd",String(value)));metrics.append(pair);
    }
    summary.append(metrics,el("p",`窗口 [${x.window.lo}, ${x.window.hi})；返回位置允许等于右端 ${x.window.hi}。`,"study-locator"),
      el("p",`f(k) = ${x.model.a.toFixed(5)}k ${x.model.b < 0 ? "−" : "+"} ${Math.abs(x.model.b).toFixed(5)}；p(k) = floor(f(k))。`,"index-formula"),
      el("p",`误差界 [${x.model.minError}, ${x.model.maxError}] · 拟合 ${x.model.trainedCount} 条 · 校准 ${x.model.calibratedCount} 条。`,"study-locator"),
      el("p",x.model.calibrationValid ? "误差界已在当前记录上校准。" : "记录已经变化，旧校准不再保证当前全部记录；一次查对也不恢复这项保证。", "index-calibration"));
    board.append(figure,summary);lab.append(board);

    const records=el("ol","","index-records"); records.setAttribute("aria-label","当前有序记录及从零开始的位置");
    x.rows.forEach(row=>{const cell=el("li","",`${row.inserted?"is-inserted ":""}${row.inWindow?"in-window ":""}${row.key===x.state.query?"is-query":""}`);cell.append(el("span",`#${row.rank}`),el("strong",String(row.key)),el("small",row.inserted?"新增":"原有"));records.append(cell);});lab.append(records);
    const guard = el("p", `位置 i=${x.local.position}：左侧须不存在或小于 ${x.state.query}，右侧须不存在或大于等于 ${x.state.query}。${x.local.certified ? "两个条件成立，已定位第一个不小于查询的记录。" : "条件不成立，局部候选不能当作查找答案；下面保留失败路径。"}`, "index-guard");lab.append(guard);
    const traces=el("div","","index-traces");
    const traceSection=(title,trace)=>{
      const section=el("section","");section.append(el("h3",title));const steps=el("ol","");
      trace.forEach(step=>steps.append(el("li",`[${step.lo}, ${step.hi}) → #${step.mid} 的键 ${step.key} ${step.relation} ${x.state.query}`)));
      if(!trace.length)section.append(el("p","区间为空；直接检查边界位置。"));else section.append(steps);return section;
    };
    traces.append(traceSection("① 窗口内实际查找",x.local.trace),traceSection(x.result.fallback?"② 检查失败后的全区间回退":"对照 · 从全区间直接二分",x.result.fallback?x.result.trace:x.baseline.trace));lab.append(traces);
    lab.append(el("p",`本次安全路径共 ${x.result.comparisons} 次键比较，其中相邻检查 ${x.result.guardComparisons} 次；包括局部搜索、必要的回退与相等检查。右侧对照单独运行，不给左侧提供答案。没有测量时间、内存访问或训练成本，次数不是速度排名。`,"study-locator"));
    const details=el("details","","index-audit");details.append(el("summary","逐键检查预测与误差"));
    details.append(el("p",`旁路检查：${x.audit.covered} / ${x.audit.total} 个存储键的位置落在本例的候选位置范围内。${x.audit.missedKeys.length?`超出范围的键：${x.audit.missedKeys.join("、")}。`:""}该检查只解释状态，查询算法不读取它。`));
    const scroll=el("div","","table-scroll");scroll.tabIndex=0;scroll.setAttribute("role","region");scroll.setAttribute("aria-label","逐键误差表，可横向滚动");
    const table=el("table","");const head=el("thead","");const hr=el("tr","");["键","真实位置","预测位置","位置 − 预测","记录"].forEach(t=>{const th=el("th",t);th.scope="col";hr.append(th);});head.append(hr);table.append(head);const body=el("tbody","");
    x.rows.forEach(row=>{const tr=el("tr","");[row.key,row.rank,row.prediction,row.error,row.inserted?"新增":"原有"].forEach(t=>tr.append(el("td",String(t))));body.append(tr);});table.append(body);scroll.append(table);details.append(scroll);lab.append(details);
    lab.append(el("p", "这些是固定整数集合上的原创计算：线性回归压缩位置映射，真实键负责核对。重新校准需要扫描当前记录；重新拟合也有成本。它不训练 DSI，不比较论文性能，也不保证现实数据库的吞吐与更新延迟。", "study-boundary"));
    return lab;
  }

  const desk = window.StudyDesk;
  const publicReferences = window.ResearchMap.referenceGraph(data);
  const publicNodes = new Map(publicReferences.nodes.map(node => [node.key, node]));
  const workspaceHistory = desk.history(desk.emptyWorkspace(), data);
  let workspaceState = workspaceHistory.value();
  let workspacePending = null;
  let workspaceOpened = false;
  let workspaceImportSequence = 0;
  let workspaceEditSequence = 0;
  let workspaceMessage = "选材与札记只在本页内存中；刷新或关闭前，请保存案头文件。";
  const workspaceLabels = {material: "来源札记", study: "研究文章", question: "问题专题", finding: "实践判断"};
  function currentDeskRef(kind, id) { return workspaceState.items.find(ref => ref.kind === kind && ref.id === id); }
  function captureDeskPosition() {
    const kind = seo.kinds.find(key => route[key]);
    const ref = kind && currentDeskRef(kind, route[kind]);
    if (!ref) return;
    const anchor = /^#[a-zA-Z0-9_-]{1,120}$/.test(window.location.hash) ? window.location.hash : "";
    const ex = kind === "study" ? desk.exerciseState(studiesById.get(ref.id)?.exercise, route) : null;
    const next = desk.workspace(workspaceState, data), entry = next.items.find(value => desk.key(value) === desk.key(ref));
    entry.anchor = anchor;
    if (ex) entry.exercise = ex;
    workspaceState = workspaceHistory.commit(next);
  }
  function updateWorkspaceStatus() {
    document.querySelectorAll('[data-workspace-count]').forEach(node => { node.textContent = workspaceState.items.length ? ` · ${workspaceState.items.length}` : ""; });
    document.querySelectorAll('#workspace-save-state, [data-workspace-save-state]').forEach(state => {
      state.hidden = false;
      state.textContent = workspaceHistory.dirty() ? "有未保存的整理" : "与当前检查点相同 · 仅页面内存";
    });
    document.querySelectorAll('[data-workspace-undo]').forEach(button => {button.disabled = !workspaceHistory.canUndo();});
    document.querySelectorAll('[data-workspace-redo]').forEach(button => {button.disabled = !workspaceHistory.canRedo();});
    const size = document.querySelector('[data-workspace-size]');
    if (size) size.textContent = `${(new TextEncoder().encode(desk.serializeWorkspace(workspaceState, data)).length / 1024).toFixed(1)} KiB / 2 MiB · 最多 24 个对象，每对象 12 条摘录`;
  }
  function changeWorkspace(next, message) {
    workspaceState = workspaceHistory.commit(next);
    workspaceMessage = message;
    renderWorkspace();
  }
  // One focus session is one undo step, including IME composition. Do not
  // replace the textarea DOM while typing or the browser loses selection.
  function bindWorkspaceInput(input, apply, onStatus) {
    let group, acceptedValue = input.value;
    input.addEventListener("focus", () => {group = `edit-${++workspaceEditSequence}`;});
    input.addEventListener("input", () => {
      const next = desk.workspace(workspaceState, data);
      let errorMessage = "";
      try {
        apply(next, input.value); workspaceState = workspaceHistory.commit(next, group || (group = `edit-${++workspaceEditSequence}`));
        workspaceMessage = "修改仅在本页内存中；刷新或关闭前，请保存文件。";
      }
      catch (error) {workspaceMessage = errorMessage = error.message; input.value = acceptedValue;}
      acceptedValue = input.value;
      onStatus?.(errorMessage);
      const status = document.querySelector('#workspace-status'); if (status && status.textContent !== workspaceMessage) status.textContent = workspaceMessage;
      updateWorkspaceStatus();
    });
  }
  function addToWorkspace(kind, item) {
    try {
      if (currentDeskRef(kind, item.id)) { workspaceMessage = "已在案头；可以打开案头继续整理。"; renderWorkspace(); return; }
      changeWorkspace(desk.add(workspaceState, {kind, id: item.id}, data), `已加入：${item.title}`);
    } catch (error) { workspaceMessage = error.message; renderWorkspace(); }
  }
  function openDeskRef(ref) {
    navigate({material: null, study: null, question: null, finding: null, thread: null, path: null,
      scenario: null, phase: "before", [ref.kind]: ref.id, ...(ref.exercise || {})}, {focus: true, hash: ref.anchor});
  }
  function workspaceButton(text, action, className = "") {
    const button = createTextElement("button", text, className); button.type = "button";
    button.addEventListener("click", action); return button;
  }
  function renderWorkspaceRevision(ref, excerpt = null) {
    const el = createTextElement, snapshot = excerpt ? {...ref, basis: excerpt.basis} : ref;
    const result = desk.revision(snapshot, data), wrap = el("div", "", "workspace-revision");
    wrap.dataset.revisionStatus = result.status;
    const labels = {current: "所据内容与当前相同", changed: "这份公开内容在保存后已有变化。原笔记与快照保留；对读展示当前内容。",
      unknown: "没有来源快照，只有内容日期，无法判断正文是否相同。", invalid: "保存的快照不可比较；身份或格式不匹配。它仍按原样保留，不能当作可信来源。"};
    wrap.append(el("p", labels[result.status], result.status === "changed" || result.status === "invalid" ? "workspace-stale" : "desk-hint"));
    if (result.status === "changed" || result.status === "invalid") {
      const details = el("details", "", "workspace-revision-details"); details.append(el("summary", "查看保存内容与当前内容"));
      details.append(el("p", "保存内容是本地文件中的未认证文字。这里只按文字显示，不执行 HTML；字段变化不等于论点变化。", "desk-hint"));
      if (result.status === "changed") {
        details.append(el("p", `变化字段：${result.fields.join("、")}`, "workspace-changed-fields"));
        const label = el("label", "查看字段"), select = el("select", "");
        select.setAttribute("aria-label", "查看变化字段");
        result.fields.forEach(field => {const option = el("option", field); option.value = field; select.append(option);});
        select.value = result.fields.includes("bodyMarkdown") ? "bodyMarkdown" : result.fields[0];
        label.append(select); details.append(label);
        const sides = el("div", "", "workspace-revision-sides");
        const before = el("pre", ""), after = el("pre", ""); before.dataset.revisionBefore = ""; after.dataset.revisionAfter = "";
        for (const [caption, text] of [["保存时的内容", before], ["当前公开内容", after]]) {
          const side = el("div", ""); side.append(el("h4", caption), text); sides.append(side);
        }
        const saved = JSON.parse(result.before), current = JSON.parse(result.after);
        const literal = value => typeof value === "string" ? value : value === undefined ? "（此字段不存在）" : JSON.stringify(value, null, 2);
        const show = () => {before.textContent = literal(saved[select.value]); after.textContent = literal(current[select.value]);};
        select.addEventListener("change", show); show(); details.append(sides);
      } else {const text = el("pre", result.before, "workspace-untrusted-snapshot"); details.append(text);}
      wrap.append(details);
    }
    if (!excerpt && result.status !== "current") wrap.append(workspaceButton("已核对，改以当前正文为据", () => {
      changeWorkspace(desk.rebase(workspaceState, desk.key(ref), data), "已记录以当前正文为据；旧摘录的来源版本保持原样。这不证明笔记正确。");
    }));
    return wrap;
  }
  const excerptCaptures = new Set();
  function selectedPublicText(source, ref) {
    const selection = window.getSelection();
    if (!selection || selection.rangeCount !== 1 || selection.isCollapsed) return null;
    const range = selection.getRangeAt(0);
    if (!source.contains(range.commonAncestorContainer)) return null;
    const start = range.startContainer.nodeType === Node.ELEMENT_NODE ? range.startContainer : range.startContainer.parentElement;
    if (start.closest("textarea,input,.study-desk,.workspace-object-actions,.object-reference-browser")) return null;
    for (const privateNode of source.querySelectorAll(".study-desk,.workspace-object-actions,.object-reference-browser,textarea,input")) {
      if (range.intersectsNode(privateNode)) return null;
    }
    const quote = selection.toString().trim(); if (!quote) return null;
    let anchor = "", section = start.closest("[id]");
    if (section && source.contains(section) && section !== source) anchor = `#${section.id}`;
    else {
      const headings = [...source.querySelectorAll("h2[id]")];
      const heading = headings.filter(node => node === start || Boolean(node.compareDocumentPosition(start) & Node.DOCUMENT_POSITION_FOLLOWING)).at(-1);
      if (heading) anchor = `#${heading.id}`;
    }
    anchor = anchor.replace(`#workspace-${ref.id}-`, "#");
    if (!/^#[a-zA-Z0-9_-]{1,120}$/.test(anchor)) anchor = "";
    return {quote, anchor};
  }
  document.addEventListener("selectionchange", () => {
    for (const control of excerptCaptures) {
      if (!control.button.isConnected) {excerptCaptures.delete(control); continue;}
      control.update();
    }
  });
  function renderExcerptCapture(ref, source) {
    // Renders can replace private panels without changing the browser selection.
    // Release their closures even when no selectionchange event is dispatched.
    for (const control of excerptCaptures) if (!control.button.isConnected) excerptCaptures.delete(control);
    const el = createTextElement, wrap = el("div", "", "workspace-capture"); wrap.dataset.jsControl = "";
    const hint = el("p", "在当前公开内容中选中文字，再留下摘录。摘录保留来源版本；用途与批注可在案头编辑。", "desk-hint");
    let selected = null;
    const button = workspaceButton("留下选中文字", () => {
      if (!selected) return;
      try {
        const work = desk.add(workspaceState, ref, data);
        changeWorkspace(desk.addExcerpt(work, desk.key(ref), {...selected, role: "context", comment: ""}, data), "已保留摘录及其来源版本；可在案头标记用途、批注并保存文件。");
        selected = null; button.disabled = true; wrap.classList.remove("has-public-selection"); hint.textContent = workspaceMessage;
        window.getSelection()?.removeAllRanges();
      } catch (error) {hint.textContent = error.message;}
    }); button.disabled = true;
    button.addEventListener("pointerdown", event => event.preventDefault());
    const control = {button, update() {
      selected = selectedPublicText(source, ref);
      button.disabled = !selected || selected.quote.length > 8000;
      button.textContent = selected?.quote.length > 8000 ? "选区超过 8,000 字符，请缩小" : "留下选中文字";
      wrap.classList.toggle("has-public-selection", Boolean(selected));
      if (selected) hint.textContent = selected.quote.length > 8000 ? "选中文字超过 8,000 字符；请缩小选区。" : `已选择 ${selected.quote.length} 字符 · ${selected.anchor || "当前对象"}。保存后可在案头批注。`;
    }}; excerptCaptures.add(control);
    const slot = el("div", "", "workspace-capture-slot"); slot.append(button);
    wrap.append(slot, hint); return wrap;
  }
  function renderExcerpts(ref) {
    const el = createTextElement, wrap = el("section", "", "workspace-excerpts");
    wrap.append(el("h4", `摘录与批注 · ${ref.excerpts.length} / ${desk.excerptLimit}`), el("p", "用途是你的阅读判断，不会变成公开证据或来源的认可。", "desk-hint"));
    ref.excerpts.forEach(part => {
      const entry = el("article", "", "workspace-excerpt"); entry.dataset.excerptId = part.id;
      entry.append(el("blockquote", part.quote));
      const location = createRouteLink(ref.kind, ref.id, `回到来源 ${part.anchor || "正文"}`); location.href += part.anchor;
      location.dataset.excerptAnchor = part.anchor;
      entry.append(location, el("p", `摘录内容日期：${part.contentVersion || "未标日期"}`, "workspace-meta"));
      const roleLabel = el("label", "这段文字在我的思考中做什么"), role = el("select", ""); role.setAttribute("aria-label", `${part.id} 的用途`); role.id = `${ref.kind}-${ref.id}-${part.id}-role`;
      Object.entries(desk.excerptRoles).forEach(([value, name]) => {const option = el("option", name); option.value = value; role.append(option);}); role.value = part.role;
      role.addEventListener("change", () => {const next = desk.workspace(workspaceState, data); next.items.find(value => desk.key(value) === desk.key(ref)).excerpts.find(value => value.id === part.id).role = role.value; changeWorkspace(next, "已更新摘录用途。");}); roleLabel.append(role); entry.append(roleLabel);
      const caption = el("label", "我的批注"), comment = el("textarea", ""); comment.rows = 3; comment.maxLength = 8000; comment.value = part.comment;
      comment.id = `${ref.kind}-${ref.id}-${part.id}-comment`; caption.htmlFor = comment.id;
      bindWorkspaceInput(comment, (next, text) => {next.items.find(value => desk.key(value) === desk.key(ref)).excerpts.find(value => value.id === part.id).comment = text;});
      entry.append(caption, comment, renderWorkspaceRevision(ref, part), workspaceButton("移除这条摘录", () => {
        const next = desk.workspace(workspaceState, data), target = next.items.find(value => desk.key(value) === desk.key(ref));
        target.excerpts = target.excerpts.filter(value => value.id !== part.id); changeWorkspace(next, "已移除摘录；可以撤销恢复。");
      })); wrap.append(entry);
    }); return wrap;
  }
  function renderReferenceBrowser(kind, item) {
    const el = createTextElement, current = `${kind}/${item.id}`, details = el("details", "", "object-reference-browser");
    const outgoing = publicReferences.references.filter(ref => ref.from === current), incoming = publicReferences.references.filter(ref => ref.to === current);
    details.append(el("summary", `沿引用继续读 · ${new Set(outgoing.map(ref => ref.to)).size} 个出处 / ${new Set(incoming.map(ref => ref.from)).size} 个引用者`),
      el("p", "关系来自公开对象的显式引用与正文链接。引用不自动表示赞同、论证依赖或已经读完。", "desk-hint"));
    for (const [title, refs, field] of [["这里引用了", outgoing, "to"], ["哪些对象引用了这里", incoming, "from"]]) {
      details.append(el("h4", title));
      const grouped = new Map(); refs.forEach(ref => {const values = grouped.get(ref[field]) || []; values.push(ref); grouped.set(ref[field], values);});
      if (!grouped.size) details.append(el("p", "当前没有显式引用。", "desk-hint"));
      for (const [key, refs] of grouped) {
        const node = publicNodes.get(key), row = el("div", "", "object-reference-row");
        row.append(createRouteLink(node.kind, node.id, node.title), el("p", refs.map(ref => `${ref.relation} · ${ref.locator}`).join("；"), "desk-hint"));
        const add = workspaceButton("加入案头", () => addToWorkspace(node.kind, node.item)); add.dataset.jsControl = ""; row.append(add); details.append(row);
      }
    }
    const indirect = window.ResearchMap.impact(data, kind, item.id).affected.filter(ref => ref.distance > 1);
    if (indirect.length) {
      const scope = el("details", "", "object-impact"); scope.append(el("summary", `修订时的间接检查范围 · ${indirect.length}`), el("p", "沿反向引用寻找需要人工重读的条目；不是断言这些条目的结论都受到了影响。", "desk-hint"));
      indirect.forEach(ref => {
        const row = el("p", ""); row.append(createRouteLink(ref.kind, ref.id, ref.title));
        const path = [...ref.path.map(step => step.from), current].map(key => publicNodes.get(key).title).join(" → ");
        row.append(el("span", ` · ${ref.distance} 层 · ${path}`, "desk-hint")); scope.append(row);
      }); details.append(scope);
    }
    return details;
  }
  function renderWorkspaceComparison(ref) {
    const el = createTextElement, item = desk.resolve(ref, data), panel = el("article", "", "workspace-comparison");
    panel.dataset.workspaceObject = desk.key(ref);
    panel.append(el("p", workspaceLabels[ref.kind], "content-kind"), el("h3", item.title));
    const byline = ref.kind === "material" ? `${item.authors.join(", ")} · ${item.year}；札记范围 ${item.noteDepth}` : `${item.byline} · ${item.date || item.updated}`;
    panel.append(el("p", byline, "workspace-meta"));
    if (ref.kind === "material") panel.append(el("p", item.readingScope, "workspace-scope"));
    if (ref.kind === "material") panel.append(el("p", "来源作者见上；本站札记及具体贡献的署名保留在完整研究包中。", "desk-hint"));
    if (item.boundary || item.limit) panel.append(el("p", item.boundary || item.limit, "workspace-scope"));
    panel.append(renderWorkspaceRevision(ref));
    const body = el("div", "", "workspace-reading");
    body.tabIndex = 0; body.setAttribute("role", "region"); body.setAttribute("aria-label", `${item.title}的当前公开内容`);
    if (item.bodyHtml) {
      // The same compiler output as the main article; no browser Markdown parser
      // and never HTML from an imported workspace snapshot.
      body.innerHTML = item.bodyHtml;
      if (body.firstElementChild?.tagName === "H1") body.firstElementChild.remove();
      body.querySelectorAll("[id]").forEach(node => node.removeAttribute("id"));
      body.querySelectorAll("h2").forEach((node, i) => {node.id = `workspace-${ref.id}-section-${i + 1}`;});
      body.querySelectorAll("a").forEach(link => {
        const href = link.getAttribute("href");
        const url = new URL(href, siteRoot), id = url.searchParams.get("study");
        if (id && studiesById.has(id)) {link.dataset.route = "study"; link.dataset.routeId = id; link.href = routeHref("study", id) + url.hash;}
        else if (href.startsWith("#")) {
          link.href = routeHref(ref.kind, ref.id) + href; link.dataset.route = ref.kind; link.dataset.routeId = ref.id;
        } else link.href = url.href;
      });
    } else {
      body.append(el("p", item.intro || item.claim || item.question));
      if (item.keyPoints?.length) {const list = el("ul", ""); item.keyPoints.forEach(text => list.append(el("li", text))); body.append(list);}
      for (const [field, label] of [["judgment", "目前的认识"], ["when", "适用情境"], ["action", "建议做法"], ["editorialQuestion", "继续追问"]]) if (item[field]) body.append(el("h4", label), el("p", item[field]));
      body.append(el("p", "这里并列核心内容与范围；完整论证、实验和证据在正文与研究包中。", "desk-hint"));
    }
    panel.append(body);
    const evidence = el("details", "", "workspace-references");
    evidence.append(el("summary", "出处、依据与完整研究包"));
    if (item.sourceUrl) evidence.append(createExternalLink(item.sourceUrl, "来源原文 ↗"));
    (item.readings || []).forEach(reading => {
      const source = materialsById.get(reading.materialId);
      evidence.append(createRouteLink("material", source.id, reading.label), el("p", reading.takeaway), el("p", `${reading.locator} · ${reading.limit}`, "desk-hint"));
    });
    (item.externalReadings || []).forEach(reading => evidence.append(createExternalLink(reading.url, reading.label), el("p", `${reading.locator} · ${reading.limit}`, "desk-hint")));
    (item.evidence || []).forEach(part => evidence.append(el("p", `${part.label}：${part.observation} · ${part.limit}`, "desk-hint")));
    const packet = window.StudyPackets.packet(data, ref.kind, ref.id);
    (item.evidenceLimits || []).forEach(limit => evidence.append(el("p", limit, "workspace-scope")));
    packet.manifest.forEach(part => {if (!part.missing) evidence.append(createRouteLink(part.publicKind || {source:"material",entry:"study",inquiry:"question",transfer:"finding"}[part.kind], part.id, part.title));});
    evidence.append(workspaceButton("下载此对象公开研究包", () => downloadFile(`${ref.kind}-${ref.id}.md`, window.StudyPackets.markdown(packet), "text/markdown")));
    panel.append(evidence, workspaceButton("打开完整正文 ↗", () => openDeskRef(ref), "workspace-open-reading"));
    panel.append(renderExcerptCapture(ref, body), renderExcerpts(ref));
    const label = el("label", "我的对读笔记"); label.htmlFor = `workspace-note-${ref.kind}-${ref.id}`;
    const note = el("textarea", ""); note.id = label.htmlFor; note.rows = 4; note.maxLength = 20000; note.value = ref.note;
    note.placeholder = "它解释了什么？与另一份材料哪里相合、哪里不能互推？";
    bindWorkspaceInput(note, (next, text) => {next.items.find(value => desk.key(value) === desk.key(ref)).note = text;});
    panel.append(label, note); return panel;
  }
  function renderWorkspace() {
    const el = createTextElement, root = document.querySelector('#workspace-controls');
    const active = root.contains(document.activeElement) ? document.activeElement : null;
    const focusKey = active?.dataset.workspaceFocus;
    workspaceOpened = workspaceOpened || window.location.hash === "#workbench" || workspaceState.items.length > 0;
    root.hidden = !workspaceOpened;
    const launch = document.querySelector('#workspace-launch'); launch.hidden = workspaceOpened;
    launch.replaceChildren(workspaceButton("开始一份研究案头 ↗", () => {workspaceOpened = true; renderWorkspace(); document.querySelector('#workspace-title').focus();}));
    document.querySelector('.workspace-nojs').hidden = true;
    updateWorkspaceStatus();
    const fragment = document.createDocumentFragment();
    const status = el("p", workspaceMessage, "workspace-status"); status.id = "workspace-status"; status.setAttribute("role", "status"); fragment.append(status);
    const actions = el("div", "", "workspace-actions");
    actions.append(workspaceButton("保存案头 JSON ↓", () => {
      captureDeskPosition();
      const serialized = desk.serializeWorkspace(workspaceState, data);
      downloadFile("ams-workspace.json", serialized, "application/json"); workspaceHistory.markSaved();
      workspaceMessage = "已生成案头文件，含私人文字与公开内容快照；请保管下载的文件。"; renderWorkspace();
    }), workspaceButton("导出私人札记 Markdown ↓", () => {captureDeskPosition(); downloadFile("ams-private-notes.md", desk.workspaceMarkdown(workspaceState, data, window.StudyPackets), "text/markdown");}));
    const fileLabel = el("label", "打开案头文件 ↗", "file-button"); fileLabel.htmlFor = "workspace-file";
    const file = el("input", "", "sr-only"); file.type = "file"; file.accept = ".json,application/json"; file.id = "workspace-file";
    file.addEventListener("change", async () => {
      const input = file.files[0]; if (!input) return;
      const sequence = ++workspaceImportSequence;
      try {
        if (input.size > desk.workspaceBytes) throw new Error("案头文件过大，限 2 MiB。");
        const parsed = desk.parseWorkspace(await input.text(), data);
        if (sequence !== workspaceImportSequence) return;
        workspacePending = parsed;
        workspaceMessage = "文件已检查；确认打开后才会替换当前案头。";
      } catch (error) {if (sequence !== workspaceImportSequence) return; workspacePending = null; workspaceMessage = error.message;}
      renderWorkspace();
    }); actions.append(fileLabel, file);
    const undo = workspaceButton("撤销上次整理", () => {
      workspaceState = workspaceHistory.undo(); workspaceMessage = "已撤销一次整理；可重做。"; renderWorkspace();
    }); undo.dataset.workspaceUndo = ""; undo.dataset.workspaceFocus = "undo"; undo.disabled = !workspaceHistory.canUndo();
    const redo = workspaceButton("重做整理", () => {
      workspaceState = workspaceHistory.redo(); workspaceMessage = "已重做一次整理。"; renderWorkspace();
    }); redo.dataset.workspaceRedo = ""; redo.dataset.workspaceFocus = "redo"; redo.disabled = !workspaceHistory.canRedo();
    const saveState=el("span",workspaceHistory.dirty()?"有未保存的整理":"与当前检查点相同 · 仅页面内存","workspace-save-hint");saveState.dataset.workspaceSaveState="";
    actions.append(undo,redo,saveState); fragment.append(actions);
    const size = el("p", "", "desk-hint"); size.dataset.workspaceSize = ""; fragment.append(size);
    if (workspacePending) {
      const preview = el("div", "", "workspace-import-preview"); preview.id = "workspace-import-preview";
      preview.append(el("h3", workspacePending.title || "未命名案头"), el("p", `${workspacePending.items.length} 个已知对象；私人笔记按纯文字读取。打开会替换当前案头，可撤销；尚未保存的内容建议先下载。`));
      workspacePending.items.forEach(ref => preview.append(el("p", desk.resolve(ref, data).title)));
      preview.append(workspaceButton("打开这份案头", () => { const next = workspacePending; workspacePending = null; changeWorkspace(next, "已从本地文件恢复案头；没有请求文件中的链接。"); workspaceHistory.markSaved(); updateWorkspaceStatus(); }), workspaceButton("取消打开", () => {workspacePending = null; workspaceMessage = "已取消，当前案头保持原样。"; renderWorkspace();}));
      fragment.append(preview);
    }
    const writing = el("div", "", "workspace-writing");
    for (const [field, label, hint, max] of [["title", "这次在研究什么", "给这份案头起一个名字，也可以暂时留空。", 240], ["question", "当前问题", "从一个词、一处困惑或两种不同解释开始。", 8000], ["synthesis", "已经讲清了什么", "留下使理解成立的例子、推导与条件；也允许不确定。", 20000], ["next", "回来时，从哪里继续", "一个段落、一个反例，或下一步值得做的动作。", 8000]]) {
      const wrap = el("div", "", `workspace-field workspace-field-${field}`), caption = el("label", label); caption.htmlFor = `workspace-${field}`;
      const input = el(field === "title" ? "input" : "textarea", ""); input.id = caption.htmlFor; input.maxLength = max; input.value = workspaceState[field]; input.placeholder = hint;
      if (field !== "title") input.rows = field === "synthesis" ? 6 : 3;
      bindWorkspaceInput(input, (next, text) => {next[field] = text;});
      wrap.append(caption, input); writing.append(wrap);
    } fragment.append(writing);
    const picking = el("details", "", "workspace-picker"); picking.open = !workspaceState.items.length;
    picking.append(el("summary", `选择公开内容 · 案头 ${workspaceState.items.length} / ${desk.workspaceLimit}`));
    const searchLabel = el("label", "查找可选对象"); searchLabel.htmlFor = "workspace-search";
    const search = el("input", ""); search.type = "search"; search.id = "workspace-search"; search.placeholder = "只搜索公开内容；不写入 URL。";
    const results = el("div", "", "workspace-picker-results");
    function fillChoices() {
      const hits = window.ReadingSearch.search(searchIndex, search.value);
      results.replaceChildren();
      if (!hits.length) results.append(el("p", "没有匹配内容。可以换个词，或从正文加入。"));
      hits.forEach(hit => {
        const button = workspaceButton(`${workspaceLabels[hit.kind]} · ${hit.item.title}`, () => addToWorkspace(hit.kind, hit.item));
        button.disabled = Boolean(currentDeskRef(hit.kind, hit.item.id)); results.append(button);
      });
    } search.addEventListener("input", fillChoices); fillChoices(); picking.append(searchLabel, search, results); fragment.append(picking);
    const list = el("ol", "", "workspace-list");
    workspaceState.items.forEach((ref, i) => {
      const row = el("li", "", "workspace-item"), item = desk.resolve(ref, data), id = desk.key(ref); row.dataset.workspaceKey = id;
      const heading = el("div", "", "workspace-item-copy"); heading.append(el("p", `${String(i + 1).padStart(2, "0")} / ${workspaceLabels[ref.kind]}`, "content-kind"), workspaceButton(item.title, () => openDeskRef(ref)));
      if (ref.note) heading.append(el("p", ref.note.slice(0, 140), "workspace-note-preview"));
      if (desk.changed(ref, data)) heading.append(el("p", "正文有变化 · 笔记保持原样", "workspace-stale"));
      else if (desk.revision(ref, data).status === "invalid") heading.append(el("p", "来源快照不可比较 · 笔记保持原样", "workspace-stale"));
      const controls = el("div", "", "workspace-item-actions");
      const compare = workspaceButton(workspaceState.compare.includes(id) ? "正在对读" : "放入对读", () => {
        const next = desk.workspace(workspaceState, data);
        if (next.compare.includes(id)) next.compare = next.compare.filter(value => value !== id);
        else if (next.compare.length < 2) next.compare.push(id);
        else {workspaceMessage = "先取消一个对读对象，再选择另一个；案头中的选材会保留。"; renderWorkspace(); return;}
        changeWorkspace(next, "已更新对读选择。");
      }); compare.setAttribute("aria-pressed", String(workspaceState.compare.includes(id))); controls.append(compare);
      compare.dataset.workspaceFocus = `compare-${id}`;
      for (const [offset, label] of [[-1, "上移"], [1, "下移"]]) {
        const button = workspaceButton(label, () => changeWorkspace(desk.move(workspaceState, id, offset, data), `已${label}：${item.title}`));
        button.setAttribute("aria-label", `${label} ${item.title}`); button.disabled = i + offset < 0 || i + offset >= workspaceState.items.length; controls.append(button);
        button.dataset.workspaceFocus = `move-${offset}-${id}`;
      }
      const remove = workspaceButton("移出", () => changeWorkspace(desk.remove(workspaceState, id, data), `已移出：${item.title}；可撤销恢复笔记。`)); remove.setAttribute("aria-label", `移出 ${item.title}`); controls.append(remove);
      row.append(heading, controls); list.append(row);
    }); fragment.append(list);
    if (workspaceState.items.length) {
      const publicActions = el("details", "", "workspace-public"); publicActions.append(el("summary", "只带走公开选材 · 不含私人文字"), el("p", "按当前顺序导出公开对象，包含正文、署名、依据与范围。案头名称、问题和笔记不在包内。", "desk-hint"));
      for (const format of ["markdown", "json"]) publicActions.append(workspaceButton(`公开选材 ${format === "json" ? "JSON" : "Markdown"} ↓`, () => {
        const bundle = window.StudyPackets.collection(data, workspaceState.items);
        downloadFile(`ams-public-collection.${format === "json" ? "json" : "md"}`, format === "json" ? JSON.stringify(bundle, null, 2) : window.StudyPackets.collectionMarkdown(bundle), format === "json" ? "application/json" : "text/markdown");
      })); fragment.append(publicActions);
    }
    if (workspaceState.compare.length) {
      const heading = el("div", "", "workspace-compare-heading"); heading.append(el("p", "READ TOGETHER / 当前公开内容与自己的笔记", "eyebrow"), el("h3", "让区别，出现在同一张桌上。")); fragment.append(heading);
      const panels = el("div", "", "workspace-comparisons"); workspaceState.compare.forEach(id => panels.append(renderWorkspaceComparison(workspaceState.items.find(ref => desk.key(ref) === id)))); fragment.append(panels);
    } else fragment.append(el("p", workspaceState.items.length ? "从选材中放入一至两个对读对象，正文阅读和笔记会并列出现。" : "案头还空着。可以在上方选材，也可以阅读正文时点“加入研究案头”。", "workspace-empty"));
    root.replaceChildren(fragment); updateWorkspaceStatus();
    if (active) {
      const target = focusKey ? [...root.querySelectorAll('[data-workspace-focus]')].find(node => node.dataset.workspaceFocus === focusKey && !node.disabled) :
        active.id ? document.getElementById(active.id) : null;
      if (target) target.focus({preventScroll: true});
      else {status.tabIndex = -1; status.focus({preventScroll: true});}
    }
  }
  function downloadFile(name, text, type) {
    const url=URL.createObjectURL(new Blob([text],{type}));const link=document.createElement("a");link.href=url;link.download=name;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  }
  function mountDesk(kind,item,view) {
    view.querySelector(".study-desk")?.remove();
    view.querySelector(".workspace-object-actions")?.remove();
    view.querySelector(".object-reference-browser")?.remove();
    const el=createTextElement, area=el("section","","study-desk");
    const objectActions=el("div","","workspace-object-actions"); objectActions.dataset.jsControl="";
    const add=workspaceButton(currentDeskRef(kind,item.id)?"已在研究案头":"加入研究案头",()=>{
      addToWorkspace(kind,item); add.textContent=currentDeskRef(kind,item.id)?"已在研究案头":"加入研究案头";
      feedback.textContent=workspaceMessage;
    });
    const back=createRouteLink("home","","回到研究案头 ↗");back.dataset.scrollTarget="workbench";
    const feedback=el("span","","desk-hint");feedback.setAttribute("role","status");
    objectActions.append(add,back,feedback);
    view.querySelector(".study-heading, .material-heading, .inquiry-heading").after(objectActions, renderReferenceBrowser(kind, item));
    const publicBody = kind === "study" ? view.querySelector(".study-essay") : kind === "material" ? view.querySelector(".article-main") : view;
    const capture = renderExcerptCapture({kind, id: item.id}, publicBody); capture.classList.add("workspace-article-capture");
    objectActions.append(capture);
    const actions=el("div","","packet-actions");actions.append(el("p","带走这份公开研究","eyebrow"));
    ["markdown","json"].forEach(format=>{
      const name=`${kind}-${item.id}.${format==="markdown"?"md":"json"}`;
      if(physicalRoutes){const a=el("a",format==="markdown"?"Markdown ↓":"JSON ↓");a.href=new URL(`${kind}/${item.id}/index.${format==="markdown"?"md":"json"}`,siteRoot);a.download=name;actions.append(a);}
      else {const b=el("button",format==="markdown"?"Markdown ↓":"JSON ↓");b.type="button";b.addEventListener("click",()=>{const p=window.StudyPackets.packet(data,kind,item.id);downloadFile(name,format==="markdown"?window.StudyPackets.markdown(p):JSON.stringify(p,null,2),format==="markdown"?"text/markdown":"application/json");});actions.append(b);}
    });
    area.append(actions,el("p","含当前正文、出处、阅读范围与接续线索；链接的全文不随包附带。","desk-hint"));
    const details=el("details","","private-continuation");details.append(el("summary","记下自己的继续位置"));
    const previous=currentDeskRef(kind,item.id);
    const label=el("label","下次想从哪里接着？");label.htmlFor="continuation-note";
    const input=el("textarea","");input.id="continuation-note";input.maxLength=20000;input.rows=4;input.placeholder="一个没想通的地方、一个例子，或下一步想试的事。";input.value=previous?.note||"";
    bindWorkspaceInput(input, (next, text) => {
      if(!next.items.some(ref => ref.kind === kind && ref.id === item.id)) Object.assign(next, desk.add(next, {kind, id: item.id}, data));
      next.items.find(ref => ref.kind === kind && ref.id === item.id).note = text;
    }, message => {
      feedback.textContent = message;
      add.textContent = currentDeskRef(kind,item.id) ? "已在研究案头" : "加入研究案头";
    });
    const button=el("button","保存接续文件 ↓");button.type="button";button.addEventListener("click",()=>{
      captureDeskPosition();
      const state={schema:window.StudyDesk.schema,kind,id:item.id,note:input.value,anchor:/^#[a-zA-Z0-9_-]{1,120}$/.test(window.location.hash)?window.location.hash:"",contentVersion:item.date||item.updated||data.room.edition};
      const exercise = desk.exerciseState(item.exercise, route);
      if (exercise) state.exercise = exercise;
      downloadFile(`ams-${item.id}.json`,JSON.stringify(window.StudyDesk.validate(state,data),null,2),"application/json");
      const sole = workspaceState.items.length === 1 && workspaceState.items[0];
      if(sole && sole.kind === kind && sole.id === item.id && !sole.excerpts.length && !workspaceState.title && !workspaceState.question && !workspaceState.synthesis && !workspaceState.next) workspaceHistory.markSaved();
      updateWorkspaceStatus();
    });
    details.append(label,input,button,el("p","只保留在本页内存中；刷新前请保存文件。文件由你保管，可从首页重新打开，不上传，也不写入浏览器存储。","desk-hint"));
    if(previous?.contentVersion && previous.contentVersion !== (item.date||item.updated||data.room.edition)) details.append(el("p","内容日期已变化；你的笔记仍按原样保留。","study-boundary"));
    if(previous)details.open=true;area.append(details);view.append(area);
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
      if(item.nextTest) { next.append(el("p", item.nextTest.question, "inquiry-lead"));
      for (const [key,label] of [["comparison","怎样比较"],["success","看什么结果"],["reviseWhen","何时改主意"]]) next.append(el("h3", label),el("p",item.nextTest[key]));
      next.append(el("p",item.nextTest.boundary,"inquiry-limit")); }
      if(item.continuation) next.append(el("p",item.continuation.question,"inquiry-lead"),el("p",item.continuation.why));
      fragment.append(next);
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
    // Drafts live in StudyDesk state. Inactive views must not retain duplicate
    // note inputs or stale workspace action controls with the same DOM IDs.
    document.querySelectorAll('.study-desk, .workspace-object-actions').forEach(node=>node.remove());
    renderView(options);
    const activeKind=seo.kinds.find(key=>route[key]);
    if(activeKind) {
      const collection={material:materialsById,study:studiesById,question:questionsById,finding:findingsById}[activeKind];
      const view=activeKind==="material"?refs.materialView:activeKind==="study"?refs.studyView:refs.inquiryView;
      mountDesk(activeKind,collection.get(route[activeKind]),view);
    }
    renderWorkspace();
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
      if(hash) window.requestAnimationFrame(()=>fragmentTarget(hash)?.scrollIntoView());
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
      if(hash) window.requestAnimationFrame(()=>fragmentTarget(hash)?.scrollIntoView());
      return;
    }

    renderAtlasFrame();
    const activeSurface = selectedSurface();
    refs.routeStatus.textContent = route.path
      ? `已打开阅读路径：${pathsById.get(route.path).title}`
      : activeSurface
        ? `研究地图：${activeSurface.label}`
        : "已打开 AMS 研究书房";
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
    const hash = new URL(link.href,window.location.href).hash;
    if(type==="domain" || type==="direction") {navigate({material:null,study:null,question:null,finding:null,thread:null,path:null,[type]:id},{focus:true,hash:type==="domain"?"#domains":"#directions"});return;}
    if (type === "question" || type === "finding") {
      navigate({material: null, study: null, question: type === "question" ? id : null,
        finding: type === "finding" ? id : null, scenario: null, phase: "before", thread: null, path: null}, {focus: true,hash});
      return;
    }
    if (type === "study") {
      navigate({question: null, finding: null, material: null, study: id, scenario: null, phase: "before", thread: null, path: null}, {focus: true,hash});
      return;
    }
    if (type === "material") {
      navigate({ question: null, finding: null, material: id, study: null, scenario: null, phase: "before", thread: null, path: null }, { focus: true, hash });
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

  });

  document.addEventListener("click", (event) => {
    if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    const link = event.target.closest("a[data-route]");
    if (!link) return;
    event.preventDefault();
    activateRouteLink(link);
  });

  window.addEventListener("popstate", () => {
    route = readRoute();
    render({ focus: true, hash: window.location.hash });
  });

  document.querySelector("#resume-file").addEventListener("change", async event => {
    const file=event.target.files[0];if(!file)return;
    const status=document.querySelector("#resume-status");
    try {
      if(file.size>128000)throw new Error("接续文件过大，限 128 KB。");
      const state=window.StudyDesk.parse(await file.text(),data);
      const wasDirty=workspaceHistory.dirty();
      const next=desk.add(workspaceState,state,data),ref=next.items.find(value=>desk.key(value)===desk.key(state));
      Object.assign(ref,state);delete ref.schema;ref.basis="";
      changeWorkspace(next,"已恢复单篇接续；可在案头撤销这次导入。");
      if (!wasDirty && workspaceState.items.length===1 && !workspaceState.items[0].excerpts.length && !workspaceState.title && !workspaceState.question && !workspaceState.synthesis && !workspaceState.next) workspaceHistory.markSaved();
      navigate({material:null,study:null,question:null,finding:null,scenario:null,phase:"before",[state.kind]:state.id,...(state.exercise||{})},{focus:true,hash:state.anchor});
      refs.routeStatus.textContent="已从本地文件恢复接续位置。";
      status.textContent="接续文件已在本地打开。";
    } catch(error) {status.textContent=error.message;}
    event.target.value="";
  });

  window.addEventListener("beforeunload", event => {
    if (!workspaceHistory.dirty()) return;
    event.preventDefault(); event.returnValue="";
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
