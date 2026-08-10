(() => {
  "use strict";

  const data = window.READING_ROOM;
  if (!data || !Array.isArray(data.materials) || data.materials.length === 0) {
    document.body.textContent = "阅读包数据缺失。";
    return;
  }

  const state = {
    selectedId: data.materials.some((material) => material.id === "truth-maintenance-system")
      ? "truth-maintenance-system"
      : data.materials[0].id,
    topic: "全部",
    query: "",
  };

  const refs = {
    search: document.querySelector("#search"),
    filters: document.querySelector("#topic-filters"),
    list: document.querySelector("#paper-list"),
    drawerList: document.querySelector("#drawer-paper-list"),
    empty: document.querySelector("#empty-list"),
    drawerEmpty: document.querySelector("#drawer-empty-list"),
    title: document.querySelector("#paper-title"),
    meta: document.querySelector("#paper-meta"),
    sourceNote: document.querySelector("#source-note"),
    intro: document.querySelector("#paper-intro"),
    points: document.querySelector("#paper-points"),
    question: document.querySelector("#paper-question"),
    scope: document.querySelector("#reading-scope"),
    source: document.querySelector("#source-link"),
    doi: document.querySelector("#doi-line"),
    sourceAction: document.querySelector("#open-source"),
    readingPane: document.querySelector("#reading-pane"),
    readingEmpty: document.querySelector("#reading-empty"),
    openIndex: document.querySelector("#open-index"),
    mobileIndex: document.querySelector("#mobile-index-trigger"),
    closeIndex: document.querySelector("#close-index"),
    drawer: document.querySelector("#paper-drawer"),
    backdrop: document.querySelector("#drawer-backdrop"),
  };

  const topics = ["全部", ...data.filters];

  document.querySelectorAll("[data-material-count]").forEach((node) => {
    node.textContent = `${data.materials.length} 份材料`;
  });

  function normalize(value) {
    return String(value || "").toLocaleLowerCase("zh-CN").normalize("NFKC");
  }

  function matchingPapers() {
    const query = normalize(state.query).trim();
    return data.materials.filter((paper) => {
      const topicMatch = state.topic === "全部" || paper.categories.includes(state.topic);
      if (!topicMatch) return false;
      if (!query) return true;
      const haystack = normalize([
        paper.title,
        paper.authors.join(" "),
        paper.year,
        paper.intro,
        paper.editorialQuestion,
        paper.keyPoints.join(" "),
        paper.keywords.join(" "),
      ].join(" "));
      return haystack.includes(query);
    });
  }

  function createFilter(label) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "topic-filter";
    button.textContent = label;
    button.setAttribute("aria-pressed", String(state.topic === label));
    button.addEventListener("click", () => {
      state.topic = label;
      const matches = matchingPapers();
      if (matches.length && !matches.some((paper) => paper.id === state.selectedId)) {
        state.selectedId = matches[0].id;
      }
      render();
    });
    return button;
  }

  function createPaperRow(paper) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "paper-row";
    button.dataset.paperId = paper.id;
    button.title = paper.title;
    button.setAttribute("aria-current", String(paper.id === state.selectedId));

    const number = document.createElement("span");
    number.className = "row-number";
    number.textContent = String(paper.number).padStart(2, "0");

    const title = document.createElement("span");
    title.className = "row-title";
    title.textContent = paper.title;

    const author = document.createElement("span");
    author.className = "row-author";
    author.textContent = paper.shortAuthor;

    const year = document.createElement("span");
    year.className = "row-year";
    year.textContent = paper.year;

    button.append(number, title, author, year);
    button.addEventListener("click", () => {
      state.selectedId = paper.id;
      renderLists();
      renderPaper();
      closeDrawer();
      document.querySelector("#reading-pane").scrollIntoView({ behavior: "smooth", block: "start" });
    });
    return button;
  }

  function renderFilters() {
    refs.filters.replaceChildren(...topics.map(createFilter));
  }

  function renderLists() {
    const papers = matchingPapers();
    const rows = papers.map(createPaperRow);
    const drawerRows = papers.map(createPaperRow);
    refs.list.replaceChildren(...rows);
    refs.drawerList.replaceChildren(...drawerRows);
    refs.empty.hidden = papers.length !== 0;
    refs.drawerEmpty.hidden = papers.length !== 0;
  }

  function renderPaper() {
    const matches = matchingPapers();
    if (matches.length === 0) {
      refs.readingPane.hidden = true;
      refs.readingEmpty.hidden = false;
      document.title = `没有匹配 · Agent Memory Study`;
      return;
    }
    refs.readingPane.hidden = false;
    refs.readingEmpty.hidden = true;
    const paper = data.materials.find((candidate) => candidate.id === state.selectedId) || matches[0];
    refs.title.textContent = paper.title;
    refs.meta.textContent = `${paper.authors.join(", ")} · ${paper.year}`;
    refs.sourceNote.textContent = paper.sourceNote || "";
    refs.sourceNote.hidden = !paper.sourceNote;
    refs.intro.textContent = paper.intro;
    refs.points.replaceChildren(...paper.keyPoints.map((point) => {
      const item = document.createElement("li");
      item.textContent = point;
      return item;
    }));
    refs.question.textContent = paper.editorialQuestion;
    refs.scope.textContent = `阅读范围：${paper.readingScope}`;
    refs.source.href = paper.sourceUrl;
    refs.doi.textContent = paper.doi ? `DOI ${paper.doi}` : "";
    refs.sourceAction.href = paper.sourceUrl;
    document.title = `${paper.title} · Agent Memory Study`;
  }

  function setDrawer(open) {
    refs.drawer.classList.toggle("is-open", open);
    refs.backdrop.hidden = !open;
    refs.backdrop.classList.toggle("is-open", open);
    refs.drawer.setAttribute("aria-hidden", String(!open));
    refs.drawer.toggleAttribute("inert", !open);
    refs.openIndex.setAttribute("aria-expanded", String(open));
    refs.mobileIndex.setAttribute("aria-expanded", String(open));
    document.body.style.overflow = open ? "hidden" : "";
    if (open) refs.closeIndex.focus();
  }

  function openDrawer() {
    setDrawer(true);
  }

  function closeDrawer() {
    if (!refs.drawer.classList.contains("is-open")) return;
    setDrawer(false);
    refs.mobileIndex.focus();
  }

  function render() {
    renderFilters();
    renderLists();
    renderPaper();
  }

  refs.search.addEventListener("input", (event) => {
    state.query = event.target.value;
    const matches = matchingPapers();
    if (matches.length && !matches.some((paper) => paper.id === state.selectedId)) {
      state.selectedId = matches[0].id;
    }
    renderLists();
    renderPaper();
  });

  refs.openIndex.addEventListener("click", openDrawer);
  refs.mobileIndex.addEventListener("click", openDrawer);
  refs.closeIndex.addEventListener("click", closeDrawer);
  refs.backdrop.addEventListener("click", closeDrawer);
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeDrawer();
  });
  const desktopBreakpoint = window.matchMedia("(min-width: 981px)");
  desktopBreakpoint.addEventListener("change", (event) => {
    if (event.matches) setDrawer(false);
  });

  render();
})();
