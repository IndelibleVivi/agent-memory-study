"""Real-browser index exercise checks shared by source and static reader suites.

Uses only synthetic private notes. Numerical assertions are independent of the
browser engine: displayed records supply the ordered keys, and Python bisect
checks the accepted lower_bound. This helper intentionally requires real HTTP
navigation, downloads, reload and history; it is not an offline-DOM check.
"""
from bisect import bisect_left
import json
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from playwright.sync_api import expect


def _download_json(page, action):
    with page.expect_download() as event:
        action()
    return json.loads(Path(event.value.path()).read_text(encoding="utf-8"))


def check_index_exercise(page, url, record):
    """Check a complete index lab, leaving its restored article ready to inspect.

    ``url`` is an HTTP source-query or physical index article URL. ``record``
    receives a short string only after each group of checks has passed. The
    caller owns viewport selection, request blocking and browser error capture.
    """
    assert urlparse(url).scheme in ("http", "https"), url
    response = page.goto(url, wait_until="load")
    assert response is not None and response.status == 200, url
    expect(page.locator("#study-title")).to_have_text("索引也能学习——究竟学了什么？")
    expect(page.locator("#index-summary")).to_be_visible()

    def state(expected):
        for key, value in expected.items():
            expect(page.locator(f"#index-{key}")).to_have_value(str(value))
        params = parse_qs(urlparse(page.url).query)
        for key, value in expected.items():
            assert params.get(key) == [str(value)], (key, page.url)

    def keys():
        return [int(value) for value in page.locator(".index-records li strong").all_text_contents()]

    def result(position=None, fallback=None, heading=None):
        rows = keys()
        assert rows and rows == sorted(set(rows)), rows
        query = int(page.locator("#index-query").input_value())
        expected = bisect_left(rows, query)
        if position is not None:
            assert expected == position, (rows, query, expected, position)
        expect(page.locator("#index-summary .index-metrics dd").nth(2)).to_have_text(str(expected))
        if fallback is not None:
            expect(page.locator("#index-summary")).to_have_attribute("data-fallback", str(fallback).lower())
        if heading is not None:
            expect(page.locator("#index-summary h3")).to_have_text(heading)
        return rows

    def select(field, value):
        page.locator(f"#index-{field}").select_option(value)
        expect(page.locator(f"#index-{field}")).to_have_value(value)
        expect(page.locator(f"#index-{field}")).to_be_focused()

    def query(value):
        control = page.locator("#index-query")
        control.fill(str(value))
        control.press("Enter")
        expect(page.locator("#index-query")).to_have_value(str(value))
        expect(page.locator("#index-query")).to_be_focused()
        assert parse_qs(urlparse(page.url).query).get("query") == [str(value)], page.url

    # Dataset selection deliberately resets mutation, repair and default query.
    select("dataset", "uniform")
    query(70)
    state({"dataset": "uniform", "mutation": "base", "repair": "stale", "query": 70})
    base_keys = result(6, False, "找到 70")
    assert len(base_keys) == 8, base_keys
    # For the known base line f(k)=0.1k-1, k=130 is above the plotted
    # eight-record range. Clip the line; never clamp its y-values into a fake plateau.
    prediction = page.locator(".index-prediction")
    assert prediction.get_attribute("clip-path") == "url(#index-plot-clip)"
    endpoint_y = [float(pair.split(",")[1]) for pair in prediction.get_attribute("d").split("L")[-3:]]
    assert endpoint_y[0] > endpoint_y[1] > endpoint_y[2] and endpoint_y[2] < 0, endpoint_y
    expect(page.locator("#index-repair")).to_be_disabled()
    select("mutation", "insert")
    expect(page.locator("#index-repair")).to_be_enabled()
    state({"dataset": "uniform", "mutation": "insert", "repair": "stale", "query": 70})
    inserted_keys = result(10, True, "找到 70")
    assert len(inserted_keys) == 12 and set(base_keys) < set(inserted_keys), inserted_keys
    assert int(page.locator("#index-summary .index-metrics dd").nth(1).inner_text()) != 10
    expect(page.locator(".index-guard")).to_contain_text("条件不成立")
    expect(page.locator(".index-calibration")).to_contain_text("旧校准不再保证")
    stale_formula = page.locator(".index-formula").inner_text()
    select("repair", "rebound")
    result(10, False, "找到 70")
    assert page.locator(".index-formula").inner_text() == stale_formula
    expect(page.locator(".index-calibration")).to_contain_text("已在当前记录上校准")
    select("repair", "retrain")
    result(10, False, "找到 70")
    assert page.locator(".index-formula").inner_text() != stale_formula
    expect(page.locator(".index-calibration")).to_contain_text("已在当前记录上校准")
    record("index base rank, stale local failure with verified fallback, rebound and actual refit")

    query(65)
    result(10, heading="没有相等键 · 后继 70")
    query(130)
    result(12, heading="没有相等键 · 位于末尾")
    query(0)
    result(0)
    page.go_back(wait_until="load")
    expect(page.locator("#index-query")).to_have_value("130")
    result(12, heading="没有相等键 · 位于末尾")
    page.reload(wait_until="load")
    state({"dataset": "uniform", "mutation": "insert", "repair": "retrain", "query": 130})
    result(12, heading="没有相等键 · 位于末尾")
    record("index missing and boundary keys, keyboard submit/focus, browser back and reload")

    dataset_ids = page.locator("#index-dataset option").evaluate_all("nodes => nodes.map(node => node.value)")
    assert len(dataset_ids) == 3 and len(set(dataset_ids)) == 3, dataset_ids
    datasets = {}
    for dataset in dataset_ids:
        select("dataset", dataset)
        expect(page.locator("#index-mutation")).to_have_value("base")
        expect(page.locator("#index-repair")).to_have_value("stale")
        rows = result()
        datasets[dataset] = tuple(rows)
        assert page.locator(".index-figure svg .index-point").count() == len(rows)
    assert len(set(datasets.values())) == 3, datasets
    record("all three index datasets change actual ordered records and produce checked lower_bounds")

    select("dataset", "uniform")
    select("mutation", "insert")
    query(70)
    expected_state = {"dataset": "uniform", "mutation": "insert", "repair": "stale", "query": 70}
    state(expected_state)
    result(10, True, "找到 70")
    note = "Synthetic index continuation <script>window.INDEX_PRIVATE_BAD=true</script>"
    continuation = page.locator(".private-continuation")
    if not continuation.evaluate("node => node.open"):
        continuation.locator("summary").click()
    page.locator("#continuation-note").fill(note)
    expect(page.locator("#continuation-note")).to_have_value(note)
    saved = _download_json(page, lambda: page.get_by_role("button", name="保存接续文件 ↓", exact=True).click())
    assert saved["schema"] == "ams-continuation/1" and saved["id"] == "what-an-index-learns"
    assert saved["exercise"] == expected_state and saved["note"] == note
    assert saved["anchor"] == "#study-lab"
    packet = _download_json(page, lambda: page.locator(".packet-actions").get_by_text("JSON ↓", exact=True).click())
    assert packet["id"] == "what-an-index-learns" and note not in json.dumps(packet)
    assert note not in unquote(page.url) and "INDEX_PRIVATE_BAD" not in unquote(page.url)
    assert page.evaluate("window.INDEX_PRIVATE_BAD") is None
    page.locator("a.site-mark").click()
    page.locator("#resume-file").set_input_files({
        "name": "synthetic-index-continuation.json", "mimeType": "application/json",
        "buffer": json.dumps(saved, ensure_ascii=False).encode(),
    })
    expect(page.locator("#continuation-note")).to_have_value(note)
    state(expected_state)
    result(10, True, "找到 70")
    assert page.evaluate("window.INDEX_PRIVATE_BAD") is None
    record("index single continuation preserves all four fields and literal notes without public packet or URL leakage")

    page.get_by_role("link", name="回到研究案头 ↗", exact=True).click()
    expect(page.locator("#workspace-note-study-what-an-index-learns")).to_have_value(note)
    picker = page.locator(".workspace-picker")
    if not picker.evaluate("node => node.open"):
        picker.locator("summary").click()
    page.locator("#workspace-search").fill("一条记录、一种表示、一个记忆系统")
    page.locator(".workspace-picker-results").get_by_role(
        "button", name="研究文章 · 一条记录、一种表示、一个记忆系统", exact=True).click()
    expect(page.locator('.workspace-item[data-workspace-key="study:records-representations-systems"]')).to_have_count(1)
    private_question = "Synthetic private index desk question"
    page.locator("#workspace-question").fill(private_question)
    expect(page.locator("#workspace-question")).to_have_value(private_question)
    work = _download_json(page, lambda: page.get_by_role("button", name="保存案头 JSON ↓", exact=True).click())
    assert work["schema"] == "ams-workspace/2" and work["question"] == private_question
    ref = next(item for item in work["items"] if item["id"] == "what-an-index-learns")
    assert ref["exercise"] == expected_state and ref["note"] == note
    assert {item["id"] for item in work["items"]} >= {"what-an-index-learns", "records-representations-systems"}
    page.reload(wait_until="load")
    expect(page.locator(".workspace-item")).to_have_count(0)
    page.locator("#workspace-file").set_input_files({
        "name": "synthetic-index-workspace.json", "mimeType": "application/json",
        "buffer": json.dumps(work, ensure_ascii=False).encode(),
    })
    expect(page.locator("#workspace-import-preview")).to_be_visible()
    expect(page.locator("#workspace-import-preview")).to_contain_text("索引也能学习")
    expect(page.locator(".workspace-item")).to_have_count(0)
    expect(page.locator("#workspace-question")).to_have_value("")
    page.get_by_role("button", name="打开这份案头", exact=True).click()
    expect(page.locator("#workspace-import-preview")).to_have_count(0)
    expect(page.locator(".workspace-item")).to_have_count(len(work["items"]))
    expect(page.locator("#workspace-question")).to_have_value(private_question)
    expect(page.locator("#workspace-note-study-what-an-index-learns")).to_have_value(note)
    panel = page.locator('[data-workspace-object="study:what-an-index-learns"]')
    panel.get_by_role("button", name="打开完整正文 ↗", exact=True).click()
    expect(page.locator("#study-title")).to_have_text("索引也能学习——究竟学了什么？")
    expect(page.locator("#continuation-note")).to_have_value(note)
    state(expected_state)
    result(10, True, "找到 70")
    assert private_question not in unquote(page.url) and "INDEX_PRIVATE_BAD" not in unquote(page.url)
    assert page.evaluate("window.INDEX_PRIVATE_BAD") is None
    assert page.evaluate("localStorage.length") == 0
    public = _download_json(page, lambda: page.locator(".packet-actions").get_by_text("JSON ↓", exact=True).click())
    assert note not in json.dumps(public) and private_question not in json.dumps(public)
    record("index multi-object workspace save/import preview/open/full article restores state and synthetic note")

    # Leave the restored lab, graph and open audit table available for screenshots.
    page.locator(".index-audit summary").click()
    expect(page.locator(".index-audit table")).to_be_visible()
    expect(page.locator(".index-audit tbody tr")).to_have_count(12)
    assert all(text.strip() for text in page.locator(".index-audit tbody td").all_text_contents())
    expect(page.locator(".index-figure svg")).to_be_visible()
    assert page.locator(".index-figure svg .index-point").count() == 12
    assert page.locator(".index-figure svg .index-prediction").get_attribute("d")
    for selector in (".index-figure svg", ".index-audit .table-scroll"):
        box = page.locator(selector).bounding_box()
        assert box and box["width"] > 100 and box["height"] > 30, (selector, box)
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
    page.locator("#study-lab").scroll_into_view_if_needed()
    record("restored index graph and complete audit table are visible, nonempty and fit the viewport")


def check_index_capacity(page, home_url, record):
    """An accepted exact-limit desk survives failed automatic exercise capture.

    Run once per source/static artifact, not once per viewport. The fixture is
    created from known public object identities plus explicitly synthetic inert
    basis text. It never contains private material or a model-produced result.
    """
    assert urlparse(home_url).scheme in ("http", "https") and home_url.endswith("/"), home_url
    response = page.goto(home_url + "#workbench", wait_until="load")
    # The source suite may already be on this homepage: a fragment-only hop
    # has no HTTP response. Reload also starts this fixture with an empty desk.
    if response is None:
        response = page.reload(wait_until="load")
    assert response is not None and response.status == 200, home_url
    expect(page.locator("#atlas-view")).to_be_visible()
    expect(page.locator("#workspace-file")).to_be_attached()
    text = page.evaluate('''() => {
      const desk = StudyDesk, data = READING_ROOM;
      let work = desk.add(desk.emptyWorkspace(), {kind:'study', id:'what-an-index-learns'}, data);
      for (const item of data.materials.slice(0, 11)) {
        work = desk.add(work, {kind:'material', id:item.id}, data);
      }
      work.title = 'A'; work.compare = [];
      work.items[0].note = 'Synthetic existing index note at capacity';
      work.items[0].anchor = '#study-lab';
      for (const ref of work.items) {
        ref.basis = JSON.stringify({id:ref.id, synthetic:'Original ASCII capacity filler; no source claims.'});
      }
      let remaining = desk.workspaceBytes - new TextEncoder().encode(desk.serializeWorkspace(work, data)).length;
      for (const ref of work.items) {
        const count = Math.min(remaining, 200000 - ref.basis.length);
        ref.basis = ref.basis.slice(0, -2) + 'x'.repeat(count) + '"}';
        remaining -= count;
      }
      if (remaining !== 0) throw Error('Capacity fixture could not reach the exact byte limit');
      const serialized = desk.serializeWorkspace(work, data);
      if (new TextEncoder().encode(serialized).length !== desk.workspaceBytes) throw Error('Wrong capacity bytes');
      if ('exercise' in work.items[0]) throw Error('Capacity fixture must omit optional exercise');
      return serialized;
    }''')
    assert len(text.encode("utf-8")) == 2 * 1024 * 1024
    expected = json.loads(text)
    assert "exercise" not in expected["items"][0]
    page.locator("#workspace-file").set_input_files({
        "name": "synthetic-exact-capacity.json", "mimeType": "application/json", "buffer": text.encode("utf-8"),
    })
    expect(page.locator("#workspace-import-preview")).to_be_visible()
    page.get_by_role("button", name="打开这份案头", exact=True).click()
    expect(page.locator(".workspace-item")).to_have_count(12)
    expect(page.locator("#workspace-title")).to_have_value("A")
    # Same UTF-8 byte count, but a real unsaved history transition. An automatic
    # capture refusal must neither append a partial transition nor mark it saved.
    page.locator("#workspace-title").fill("B")
    expected["title"] = "B"
    expect(page.locator("#workspace-save-state")).to_contain_text("有未保存")
    page.locator('[data-workspace-key="study:what-an-index-learns"] .workspace-item-copy > button').click()
    expect(page.locator("#index-summary")).to_be_visible()
    expect(page.locator("#continuation-note")).to_have_value(expected["items"][0]["note"])
    single = _download_json(page, lambda: page.get_by_role("button", name="保存接续文件 ↓", exact=True).click())
    assert single["id"] == "what-an-index-learns"
    assert single["note"] == expected["items"][0]["note"] and single["anchor"] == "#study-lab"
    assert single["exercise"] == {"dataset": "uniform", "mutation": "base", "repair": "stale", "query": 70}
    assert len(json.dumps(single, ensure_ascii=False).encode("utf-8")) < 128000
    article_status = page.locator(".workspace-object-actions [role=status]")
    expect(article_status).to_be_visible()
    expect(article_status).to_contain_text("2 MiB")
    expect(article_status).to_contain_text("已保留")
    expect(page.locator("#workspace-save-state")).to_contain_text("有未保存")
    page.get_by_role("link", name="回到研究案头 ↗", exact=True).click()
    expect(page.locator("#atlas-view")).to_be_visible()
    expect(page.locator("#workspace-status")).to_be_visible()
    expect(page.locator("#workspace-status")).to_contain_text("2 MiB")
    expect(page.locator("#workspace-status")).to_contain_text("已保留")
    expect(page.locator("#workspace-title")).to_have_value("B")
    expect(page.locator("#workspace-save-state")).to_contain_text("有未保存")
    # There is only the accepted title edit in history; no partial capture step.
    page.get_by_role("button", name="撤销上次整理", exact=True).click()
    expect(page.locator("#workspace-title")).to_have_value("A")
    page.get_by_role("button", name="重做整理", exact=True).click()
    expect(page.locator("#workspace-title")).to_have_value("B")
    with page.expect_download() as event:
        page.get_by_role("button", name="保存案头 JSON ↓", exact=True).click()
    saved_text = Path(event.value.path()).read_text(encoding="utf-8")
    assert len(saved_text.encode("utf-8")) == 2 * 1024 * 1024
    assert json.loads(saved_text) == expected
    assert "exercise" not in json.loads(saved_text)["items"][0]
    assert page.evaluate("localStorage.length") == 0
    record("exact-2-MiB accepted index workspace preserves state/history on capture refusal, reports capacity, navigates and saves single/full files without clearing unrelated dirty edits")
    # The large synthetic fixture must not affect the caller's later checks.
    page.reload(wait_until="load")
    expect(page.locator(".workspace-item")).to_have_count(0)
