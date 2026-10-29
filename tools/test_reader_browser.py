#!/usr/bin/env python3
"""Reading-room browser checks. Default: real HTTP/navigation on a Pages-like subpath.

--offline-render is a labelled DOM-only fallback for navigation-restricted hosts.
It does NOT test browser history, reload, HTTP serving, CDN or deployed Safari.
"""
from __future__ import annotations
import argparse
import functools
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import tempfile
import threading
from urllib.parse import parse_qs, urldefrag, urlparse

from playwright.sync_api import sync_playwright, expect, Error as PlaywrightError
from index_browser_checks import check_index_exercise, check_index_capacity

ROOT = Path(__file__).resolve().parents[1]


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *_):
        pass


def visible_map_labels(page):
    """Read the rendered result, including clipping, without using label candidates."""
    return page.locator('.map-node-label').evaluate_all('''labels => {
      const plot = document.querySelector('#constellation-plot > svg').getBoundingClientRect();
      return labels.flatMap(label => {
        const node = label.closest('[data-map-node]'), style = getComputedStyle(label);
        const box = label.getBoundingClientRect();
        if (!node || node.classList.contains('is-dimmed') || Number(style.opacity) < .99 ||
            style.display === 'none' || style.visibility !== 'visible' || !box.width || !box.height ||
            box.right <= plot.left || box.left >= plot.right || box.bottom <= plot.top || box.top >= plot.bottom) return [];
        const lines = label.querySelectorAll('tspan');
        return [{index: Number(node.dataset.mapNode), href: node.getAttribute('href'), text: label.textContent,
          lines: lines.length ? [...lines].map(line => line.textContent) : [label.textContent],
          x: box.x, y: box.y, width: box.width, height: box.height}];
      });
    }''')


def map_relationships(page):
    return page.evaluate('''() => ({
      selection: document.querySelector('#constellation-reading').dataset.selection,
      current: document.querySelector('.map-node.is-selected').getAttribute('href'),
      related: [...document.querySelectorAll('.map-related a')].map(a => a.getAttribute('href')).sort(),
      activeEdges: [...document.querySelectorAll('.map-edges path.is-active')].map(path => path.getAttribute('d')).sort()
    })''')


def map_signal_positions(page):
    return page.locator('.map-signals circle.is-active').evaluate_all(
        "dots => dots.map(dot => [dot.getAttribute('cx'), dot.getAttribute('cy')])")

def download_json(page, trigger):
    with page.expect_download() as event:
        trigger()
    return json.loads(Path(event.value.path()).read_text())

def download_text(page, trigger):
    with page.expect_download() as event:
        trigger()
    return Path(event.value.path()).read_text()

def workspace_keys(page):
    return page.locator('.workspace-item').evaluate_all(
        "rows => rows.map(row => row.dataset.workspaceKey)")

def check_desk_visibility(page, go, record):
    """Check that the desk launcher owns its initial state and entry actions."""
    go()
    launcher = page.locator('#workspace-launch')
    controls = page.locator('#workspace-controls')
    expect(launcher).to_be_visible()
    expect(launcher.get_by_role('button', name='开始一份研究案头 ↗', exact=True)).to_be_visible()
    expect(controls).to_be_hidden()
    expect(page.locator('.sculpture-toolbar')).to_be_visible()
    expect(page.locator('.sculpture-inspector')).to_be_visible()
    launcher.get_by_role('button', name='开始一份研究案头 ↗', exact=True).click()
    expect(launcher).to_be_hidden()
    expect(controls).to_be_visible()
    expect(page.locator('#workspace-title')).to_be_focused()
    go('?study=ams-thesis')
    go('#workbench')
    expect(controls).to_be_visible()
    expect(launcher).to_be_hidden()
    record('unopened desk keeps its launcher visible and controls hidden; launcher and #workbench open the desk while sculpture controls remain available')

def external_http_requests(requests):
    return [url for url in requests if urlparse(url).scheme in ('http', 'https')
            and urlparse(url).hostname not in (None, '127.0.0.1', 'static.cloudflareinsights.com')]

def check_workspace_flow(page, data, width, record, layout, go, external_requests):
    """Exercise the research desk through visible controls, not workspace internals."""
    private_title = f"Synthetic desk {width}"
    private_question = f"Private question {width} <img src=x onerror=alert(1)>"
    private_note = f"Private note {width} <script>window.WORKSPACE_BAD=true</script>"

    go("?study=after-a-correction")
    action = page.locator(".workspace-object-actions button", has_text="加入研究案头")
    expect(action).to_be_visible()
    action.click()
    expect(page.locator(".workspace-object-actions button", has_text="已在研究案头")).to_be_visible()
    page.locator(".workspace-object-actions a[data-route=home]").click()
    expect(page.locator("#workspace-title")).to_be_visible()
    expect(page.locator("#workspace-question")).to_be_visible()
    expect(page.locator("#workspace-synthesis")).to_be_visible()
    expect(page.locator("#workspace-next")).to_be_visible()
    page.locator("#workspace-title").fill(private_title)
    page.locator("#workspace-question").fill(private_question)
    page.locator("#workspace-synthesis").fill(f"Private synthesis {width}")
    page.locator("#workspace-next").fill(f"Private next {width}")
    dirty_dialog = []
    page.once("dialog", lambda dialog: (dirty_dialog.append(dialog.type), dialog.dismiss()))
    try:
        page.reload(wait_until="domcontentloaded", timeout=1500)
    except PlaywrightError:
        # Dismissing beforeunload cancels navigation. Depending on the browser
        # build reload reports that as aborted or waits for the cancelled load.
        assert dirty_dialog == ["beforeunload"], dirty_dialog
    assert dirty_dialog == ["beforeunload"], dirty_dialog
    expect(page.locator("#workspace-title")).to_have_value(private_title)
    page.once("dialog", lambda dialog: dialog.accept())
    page.reload(wait_until="domcontentloaded")
    expect(page.locator("#workspace-title")).to_have_value("")
    go("?study=after-a-correction")
    page.locator(".workspace-object-actions button", has_text="加入研究案头").click()
    page.locator(".workspace-object-actions a[data-route=home]").click()
    page.locator("#workspace-title").fill(private_title)
    page.locator("#workspace-question").fill(private_question)
    page.locator("#workspace-synthesis").fill(f"Private synthesis {width}")
    page.locator("#workspace-next").fill(f"Private next {width}")
    expect(page.locator("#workbench")).to_be_visible()

    question = data["questions"][0]
    finding = next(item for item in data["findings"]
                   if item["id"] == "correction-needs-retention-checks")
    for query, label, title in [
        ("TRUSTMEM", "来源札记", "TRUSTMEM"),
        (question["title"], "问题专题", question["title"]),
        (finding["title"], "实践判断", finding["title"]),
    ]:
        if not page.locator("#workspace-search").is_visible():
            page.locator(".workspace-picker summary").click()
        page.locator("#workspace-search").fill(query)
        result = page.locator(".workspace-picker-results button").filter(
            has_text=title).filter(has_text=label).first
        expect(result).to_be_visible()
        result.click()
    keys = workspace_keys(page)
    assert len(keys) == 4 and len(set(keys)) == 4, keys
    assert {"study", "material", "question", "finding"} == {key.split(":", 1)[0] for key in keys}
    expect(page.locator(".workspace-comparison")).to_have_count(2)
    expect(page.locator("[data-workspace-count]").first).to_contain_text("4")
    assert page.evaluate("localStorage.length") == 0
    assert private_title not in page.url and private_question not in page.url
    first_before = workspace_keys(page)
    first_title = page.locator(".workspace-item").first.locator(
        ".workspace-item-copy > button").inner_text()
    page.locator(".workspace-item").first.get_by_role(
        "button", name=f"下移 {first_title}").click()
    moved = workspace_keys(page)
    assert moved[0] == first_before[1] and moved[1] == first_before[0], (first_before, moved)
    page.get_by_role("button", name="撤销上次整理", exact=True).click()
    assert workspace_keys(page) == first_before

    note = page.locator("#workspace-note-study-after-a-correction")
    note.fill(private_note)
    assert page.evaluate("window.WORKSPACE_BAD") is None
    assert page.evaluate("localStorage.length") == 0
    assert not any(text in page.url for text in (private_title, private_question, private_note))
    page.locator('.workspace-item').first.get_by_role('button', name=f'移出 {first_title}', exact=True).click()
    assert len(workspace_keys(page)) == 3
    page.get_by_role('button', name='撤销上次整理', exact=True).click()
    assert workspace_keys(page) == first_before
    expect(page.locator('#workspace-note-study-after-a-correction')).to_have_value(private_note)

    # Dirty navigation is visible without discarding in-memory state.
    page.locator(".workspace-item").first.locator(".workspace-item-copy > button").click()
    expect(page.locator("#study-title")).to_be_visible()
    expect(page.locator('#continuation-note')).to_have_value(private_note)
    page.locator(".workspace-object-actions a[data-route=home]").click()
    expect(page.locator("#workspace-question")).to_have_value(private_question)
    expect(page.locator("#workspace-note-study-after-a-correction")).to_have_value(private_note)
    assert workspace_keys(page) == first_before
    page.go_back()
    expect(page.locator('#study-title')).to_be_visible()
    expect(page.locator('#continuation-note')).to_have_value(private_note)
    page.go_forward()
    expect(page.locator('#workspace-question')).to_have_value(private_question)

    # Private and public downloads must separate metadata and references.
    workspace_json = download_json(page, lambda: page.get_by_role(
        "button", name="保存案头 JSON ↓", exact=True).click())
    private_markdown = download_text(page, lambda: page.get_by_role(
        "button", name="导出私人札记 Markdown ↓", exact=True).click())
    assert workspace_json["schema"] == "ams-workspace/2"
    assert workspace_json["title"] == private_title
    assert any(ref.get("note") == private_note for ref in workspace_json["items"])
    assert private_title in private_markdown and private_note in private_markdown
    # Saving a composition must not disable recovery. Undo after save changes
    # the current workspace, marks it dirty and exports the restored version.
    page.locator('.workspace-item').first.get_by_role('button', name=f'下移 {first_title}', exact=True).click()
    moved_json = download_json(page, lambda: page.get_by_role('button', name='保存案头 JSON ↓', exact=True).click())
    assert [ref['id'] for ref in moved_json['items']] != [ref['id'] for ref in workspace_json['items']]
    page.get_by_role('button', name='撤销上次整理', exact=True).click()
    expect(page.locator('#workspace-save-state')).to_have_text('有未保存的整理')
    restored_json = download_json(page, lambda: page.get_by_role('button', name='保存案头 JSON ↓', exact=True).click())
    assert restored_json == workspace_json
    page.locator(".workspace-public summary").click()
    public_json = download_json(page, lambda: page.get_by_role(
        "button", name="公开选材 JSON ↓", exact=True).click())
    public_markdown = download_text(page, lambda: page.get_by_role(
        "button", name="公开选材 Markdown ↓", exact=True).click())
    public_blob = json.dumps(public_json, ensure_ascii=False) + public_markdown
    for private in (private_title, private_question, private_note, f'Private synthesis {width}', f'Private next {width}'):
        assert private not in public_blob, private
    assert [item["id"] for item in public_json["objects"]] == [
        key.split(":", 1)[1] for key in first_before]
    assert public_json["schema"] == "ams-study-collection/1"
    assert all("recordedResults" not in object["content"] for object in public_json["objects"])

    stable_keys = workspace_keys(page)
    page.locator("#workspace-file").set_input_files({
        "name": "malformed.json", "mimeType": "application/json",
        "buffer": b'{"schema":"ams-workspace/1","items":[',
    })
    expect(page.locator("#workspace-status")).to_contain_text("不是有效 JSON")
    assert workspace_keys(page) == stable_keys
    page.locator("#workspace-file").set_input_files({
        "name": "too-large.json", "mimeType": "application/json",
        "buffer": b"x" * (2 * 1024 * 1024 + 1),
    })
    expect(page.locator("#workspace-status")).to_contain_text("2 MiB")
    assert workspace_keys(page) == stable_keys
    assert page.locator("#workspace-import-preview").count() == 0

    imported = {
        "schema": "ams-workspace/1", "title": "Imported synthetic desk",
        "question": "Imported private question", "synthesis": "Imported private synthesis",
        "next": "Imported private next",
        "items": [{
            "kind": "material", "id": "trustmem-consolidation",
            "note": "Imported private note", "anchor": "",
            "contentVersion": workspace_json["items"][0]["contentVersion"],
            "basis": workspace_json["items"][0]["basis"],
        }],
        "compare": [],
    }
    page.locator("#workspace-file").set_input_files({
        "name": "imported.json", "mimeType": "application/json",
        "buffer": json.dumps(imported).encode(),
    })
    preview = page.locator("#workspace-import-preview")
    expect(preview).to_be_visible()
    expect(preview).to_contain_text("Imported synthetic desk")
    expect(preview).to_contain_text("TRUSTMEM")
    page.get_by_role("button", name="取消打开", exact=True).click()
    expect(preview).to_have_count(0)
    assert workspace_keys(page) == stable_keys
    expect(page.locator("#workspace-title")).to_have_value(private_title)

    imported["items"][0]["note"] = "Imported private note after explicit open"
    imported["items"][0]["basis"] = "opaque imported text only"
    page.locator("#workspace-file").set_input_files({
        "name": "imported.json", "mimeType": "application/json",
        "buffer": json.dumps(imported).encode(),
    })
    page.get_by_role("button", name="打开这份案头", exact=True).click()
    expect(page.locator("#workspace-title")).to_have_value("Imported synthetic desk")
    expect(page.locator("#workspace-question")).to_have_value("Imported private question")
    expect(page.locator("#workspace-synthesis")).to_have_value("Imported private synthesis")
    expect(page.locator("#workspace-next")).to_have_value("Imported private next")
    assert workspace_keys(page) == ["material:trustmem-consolidation"]
    assert page.evaluate("window.WORKSPACE_BAD") is None
    page.get_by_role("button", name="撤销上次整理", exact=True).click()
    expect(page.locator("#workspace-title")).to_have_value(private_title)
    assert workspace_keys(page) == stable_keys
    assert page.evaluate("localStorage.length") == 0
    assert urlparse(page.url).hostname == "127.0.0.1"
    assert not external_http_requests(external_requests), external_http_requests(external_requests)

    # Re-imported private metadata can never turn into a public collection title.
    poisoned = json.loads(json.dumps(imported))
    poisoned["items"][0]["basis"] = json.dumps({
        "title": "POISONED-BASIS-TITLE", "html": "<img src=x onerror=alert(1)>",
    })
    poisoned['compare'] = ['material:trustmem-consolidation']
    page.locator("#workspace-file").set_input_files({
        "name": "poisoned.json", "mimeType": "application/json",
        "buffer": json.dumps(poisoned).encode(),
    })
    page.get_by_role("button", name="打开这份案头", exact=True).click()
    expect(page.locator('.workspace-comparison [data-revision-status=invalid]')).to_contain_text('快照不可比较')
    expect(page.locator('img[src=x]')).to_have_count(0)
    assert page.evaluate('window.WORKSPACE_BAD') is None
    page.locator(".workspace-public summary").click()
    poisoned_public = download_json(page, lambda: page.get_by_role(
        "button", name="公开选材 JSON ↓", exact=True).click())
    assert "POISONED-BASIS-TITLE" not in json.dumps(poisoned_public, ensure_ascii=False)
    assert "<img src=x" not in json.dumps(poisoned_public, ensure_ascii=False)
    page.get_by_role("button", name="撤销上次整理", exact=True).click()

    # Restore the actual downloaded file, retaining all mixed references/notes.
    page.locator('#workspace-file').set_input_files({
        'name':'roundtrip.json', 'mimeType':'application/json',
        'buffer':json.dumps(workspace_json).encode(),
    })
    page.get_by_role('button', name='打开这份案头', exact=True).click()
    expect(page.locator('#workspace-title')).to_have_value(private_title)
    expect(page.locator('#workspace-note-study-after-a-correction')).to_have_value(private_note)
    assert workspace_keys(page) == stable_keys
    download_json(page, lambda: page.get_by_role('button', name='保存案头 JSON ↓', exact=True).click())

    layout("workspace private desk and public collection")
    record("workspace mixed selection, compare, notes, undo, private/public downloads, import preview, privacy and navigation")
    go()


def check_workspace_maturation(page, data, width, record, layout, go, output=None):
    """A public passage -> private annotation -> revision -> recovered author input."""
    go('?study=retrieval-and-relevance')
    references = page.locator('#study-view > .object-reference-browser')
    references.locator('> summary').click()
    source_id = next(row for row in data['studies'] if row['id'] == 'retrieval-and-relevance')['continuation']['studyIds'][0]
    row = references.locator('.object-reference-row').filter(
        has=page.locator(f'a[data-route=study][data-route-id="{source_id}"]')).first
    expect(row).to_be_visible()
    row.get_by_role('button', name='加入案头', exact=True).click()
    expect(page.locator('[data-workspace-count]').first).to_contain_text('1')
    # Select actual canonical DOM; the private textarea is never the quote source.
    passage = page.locator('#study-view .study-essay p').last
    quote = passage.inner_text().strip()
    passage.scroll_into_view_if_needed()
    passage.evaluate('''node => {
      const range = document.createRange(); range.selectNodeContents(node);
      const selection = getSelection(); selection.removeAllRanges(); selection.addRange(range);
    }''')
    capture = page.locator('#study-view .workspace-object-actions').get_by_role(
        'button', name='留下选中文字', exact=True)
    expect(capture).to_be_enabled(); expect(capture).to_be_in_viewport(); capture.click()
    expect(page.locator('.workspace-article-capture.has-public-selection')).to_have_count(0)
    expect(page.locator('[data-workspace-count]').first).to_contain_text('2')
    page.locator('#study-view .workspace-object-actions a[data-route=home]').click()
    panel = page.locator('[data-workspace-object="study:retrieval-and-relevance"]')
    excerpt = panel.locator('.workspace-excerpt')
    expect(excerpt.locator('blockquote')).to_have_text(quote)
    comment = f'Private excerpt reasoning {width} <script>window.EXCERPT_BAD=true</script>'
    excerpt.locator('textarea').fill(comment)
    excerpt.get_by_role('combobox', name='excerpt-1 的用途').select_option('contrast')
    expect(excerpt.locator('textarea')).to_have_value(comment)
    page.locator('#workspace-question').fill('One research question')
    page.locator('#workspace-next').fill('A next reading step')
    page.get_by_role('button', name='撤销上次整理', exact=True).click()
    expect(page.locator('#workspace-next')).to_have_value('')
    expect(page.locator('#workspace-question')).to_have_value('One research question')
    expect(page.locator('[data-workspace-undo]')).to_be_focused()
    page.keyboard.press('Enter')
    expect(page.locator('#workspace-question')).to_have_value('')
    for _ in range(2):
        page.get_by_role('button', name='重做整理', exact=True).click()
    expect(page.locator('#workspace-next')).to_have_value('A next reading step')
    saved = download_json(page, lambda: page.get_by_role('button', name='保存案头 JSON ↓', exact=True).click())
    entry = next(ref for ref in saved['items'] if ref['id'] == 'retrieval-and-relevance')
    assert saved['schema'] == 'ams-workspace/2'
    assert entry['excerpts'][0]['quote'] == quote
    assert entry['excerpts'][0]['comment'] == comment
    assert entry['excerpts'][0]['role'] == 'contrast'
    assert entry['excerpts'][0]['basis'] == entry['basis']
    page.locator('.workspace-public summary').click()
    public = download_json(page, lambda: page.get_by_role('button', name='公开选材 JSON ↓', exact=True).click())
    assert comment not in json.dumps(public)
    assert all('excerpts' not in obj and 'excerpts' not in obj['content'] for obj in public['objects'])

    older = json.loads(entry['basis'])
    older['bodyMarkdown'] = '# Older synthetic revision\n\n<img src=x onerror=window.EXCERPT_BAD=true>'
    entry['basis'] = json.dumps(older)
    entry['excerpts'][0]['basis'] = entry['basis']
    original_excerpt_basis = entry['excerpts'][0]['basis']
    page.locator('#workspace-file').set_input_files({
        'name':'older-desk.json', 'mimeType':'application/json', 'buffer':json.dumps(saved).encode(),
    })
    page.get_by_role('button', name='打开这份案头', exact=True).click()
    expect(panel.locator(':scope > .workspace-revision')).to_have_attribute('data-revision-status', 'changed')
    revision = panel.locator(':scope > .workspace-revision')
    revision.locator('summary').click()
    expect(revision.locator('[data-revision-before]')).to_contain_text('Older synthetic revision')
    expect(revision.locator('[data-revision-after]')).to_contain_text('recall')
    assert page.locator('img[src=x]').count() == 0
    assert page.evaluate('window.EXCERPT_BAD') is None
    expect(panel.locator('.workspace-reading')).not_to_contain_text('Older synthetic revision')
    panel.get_by_role('button', name='已核对，改以当前正文为据', exact=True).click()
    expect(panel.locator(':scope > .workspace-revision')).to_have_attribute('data-revision-status', 'current')
    expect(excerpt.locator('.workspace-revision')).to_have_attribute('data-revision-status', 'changed')
    page.get_by_role('button', name='撤销上次整理', exact=True).click()
    expect(panel.locator(':scope > .workspace-revision')).to_have_attribute('data-revision-status', 'changed')
    page.get_by_role('button', name='重做整理', exact=True).click()
    recovered = download_json(page, lambda: page.get_by_role('button', name='保存案头 JSON ↓', exact=True).click())
    recovered_entry = next(ref for ref in recovered['items'] if ref['id'] == 'retrieval-and-relevance')
    assert recovered_entry['excerpts'][0]['basis'] == original_excerpt_basis
    assert recovered_entry['excerpts'][0]['comment'] == comment
    assert recovered_entry['basis'] != original_excerpt_basis
    # Selecting a private comment cannot feed the public passage capture action.
    excerpt.locator('textarea').focus()
    excerpt.locator('textarea').evaluate('node => node.select()')
    expect(panel.get_by_role('button', name='留下选中文字', exact=True)).to_be_disabled()
    excerpt.get_by_role('button', name='移除这条摘录', exact=True).click()
    expect(panel.locator('.workspace-excerpt')).to_have_count(0)
    page.get_by_role('button', name='撤销上次整理', exact=True).click()
    expect(panel.locator('.workspace-excerpt textarea')).to_have_value(comment)
    layout('excerpt editing and source revision')
    if output:
        Path(output, f'workspace-{width}.json').write_text(json.dumps(recovered, ensure_ascii=False, indent=2))
        panel.screenshot(path=str(Path(output, f'workspace-revision-{width}.png')))
    record('real passage capture, bidirectional citations, private annotation, multi-step history, revision inspection and preserved origins')
    # Save before a document navigation; private state is still only page memory.
    download_json(page, lambda: page.get_by_role('button', name='保存案头 JSON ↓', exact=True).click())
    go()


def check_workspace_capacity(page, data, record, go):
    """The accepted desk stays saveable when a large native edit is rejected."""
    go('#workbench')
    text = page.evaluate('''data => {
      const desk = StudyDesk; let work = desk.emptyWorkspace();
      for (const item of data.materials.slice(0, 24)) work = desk.add(work, {kind:'material', id:item.id}, data);
      for (const ref of work.items.slice(1)) ref.note = '课'.repeat(20000);
      work.question = '问'.repeat(8000); work.synthesis = '思'.repeat(20000); work.next = '续'.repeat(8000);
      work = desk.workspace(work, data); let full = false;
      outer: for (const ref of work.items) for (let i = 0; i < 12; i++) {
        try {work = desk.addExcerpt(work, desk.key(ref), {quote:'A synthetic capacity fixture', comment:'', role:'context', anchor:''}, data);}
        catch (error) {if (!error.message.includes('2 MiB')) throw error; full = true; break outer;}
      }
      if (!full) throw Error('Fixture did not reach the byte boundary');
      return desk.serializeWorkspace(work, data);
    }''', data)
    assert 1900000 < len(text.encode()) <= 2 * 1024 * 1024
    page.locator('#workspace-file').set_input_files({
        'name':'capacity.json', 'mimeType':'application/json', 'buffer':text.encode(),
    })
    page.get_by_role('button', name='打开这份案头', exact=True).click()
    expect(page.locator('.workspace-item')).to_have_count(24)
    first = page.locator('.workspace-comparison').first.locator(':scope > textarea')
    expect(first).to_have_value('')
    first.fill('更' * 20000)
    expect(page.locator('#workspace-status')).to_contain_text('2 MiB')
    expect(first).to_have_value('')
    title = page.locator('#workspace-title'); title.focus()
    page.keyboard.type('continued')
    expect(title).to_have_value('continued')
    page.get_by_role('button', name='撤销上次整理', exact=True).click()
    expect(title).to_have_value('')
    saved = download_json(page, lambda: page.get_by_role('button', name='保存案头 JSON ↓', exact=True).click())
    assert saved == json.loads(text)
    assert page.evaluate('localStorage.length') == 0
    page.locator('#room-start-list a[data-route-id=retrieval-and-relevance]').first.click()
    page.locator('.private-continuation summary').click()
    page.locator('#continuation-note').fill('A note that cannot join the full desk')
    expect(page.locator('#continuation-note')).to_have_value('')
    expect(page.locator('.workspace-object-actions [role=status]')).to_contain_text('已满')
    expect(page.locator('.workspace-object-actions > button')).to_have_text('加入研究案头')
    page.locator('.workspace-object-actions a[data-route=home]').click()
    unchanged = download_json(page, lambda: page.get_by_role('button', name='保存案头 JSON ↓', exact=True).click())
    assert unchanged == saved
    record('near-2-MiB 24-object desk rejects oversized edit atomically and keeps native typing/undo/save usable')
    page.reload(wait_until='load')
    expect(page.locator('.workspace-item')).to_have_count(0)
    go()


def check_continuation_checkpoint(page, record, go):
    """Saving another article must never acknowledge the sole desk note."""
    go('?study=retrieval-and-relevance')
    page.locator('.private-continuation summary').click()
    note = 'Synthetic unsaved note belonging only to retrieval-and-relevance'
    page.locator('#continuation-note').fill(note)
    page.locator('#study-view .study-essay a[data-route-id=what-an-index-learns]').first.click()
    expect(page.locator('#continuation-note')).to_have_value('')
    page.locator('.private-continuation summary').click()
    other = download_json(page, lambda: page.get_by_role('button', name='保存接续文件 ↓', exact=True).click())
    assert other['id'] == 'what-an-index-learns' and other['note'] == ''
    expect(page.locator('#workspace-save-state')).to_have_text('有未保存的整理')
    page.locator('.workspace-object-actions a[data-route=home]').click()
    assert workspace_keys(page) == ['study:retrieval-and-relevance']
    expect(page.locator('#workspace-note-study-retrieval-and-relevance')).to_have_value(note)
    dialogs = []
    page.once('dialog', lambda dialog: (dialogs.append(dialog.type), dialog.dismiss()))
    try:
        page.reload(wait_until='domcontentloaded', timeout=1500)
    except PlaywrightError:
        assert dialogs == ['beforeunload'], dialogs
    assert dialogs == ['beforeunload'], dialogs
    # The matching single-article download still acknowledges its own note.
    page.locator('.workspace-item-copy > button').click()
    own = download_json(page, lambda: page.get_by_role('button', name='保存接续文件 ↓', exact=True).click())
    assert own['id'] == 'retrieval-and-relevance' and own['note'] == note
    expect(page.locator('#workspace-save-state')).not_to_have_text('有未保存的整理')
    record('single-article save acknowledges only the matching object; unrelated note and beforeunload stay dirty')
    go()


def emulate_map_motion(page, preference, evidence, *, paused=None, refresh_during_transition=False):
    """Wait for the native preference signal, then check the actual app state.

    Do not read MQL.matches between emulation and its notification: that getter
    is part of the Chromium timing regression exercised by the refresh action.
    An unchanged preference need not emit change or reset a manual override.
    """
    reduced = preference == 'reduce'
    expected_pause = reduced if paused is None else paused
    initial = page.evaluate("""() => {
      const query = matchMedia('(prefers-reduced-motion: reduce)');
      const observer = {query, initial: query.matches, events: []};
      observer.listener = event => observer.events.push({matches: event.matches, time: performance.now()});
      query.addEventListener('change', observer.listener);
      window.__amsMotionObservation = observer;
      return observer.initial;
    }""")
    observation = {'preference': preference, 'initial': initial,
                   'refresh_during_transition': refresh_during_transition}
    try:
        page.emulate_media(reduced_motion=preference)
        if refresh_during_transition:
            # Exercise the product's existing refresh path while media delivery
            # is pending; never set paused or dispatch a synthetic change event.
            page.evaluate("document.querySelector('#map-zoom-in').click()")
        if initial != reduced:
            page.wait_for_function("""reduced => window.__amsMotionObservation.events
              .some(event => event.matches === reduced)""", arg=reduced, timeout=5000)
        expect(page.locator('#map-motion')).to_have_attribute('aria-pressed', str(expected_pause).lower())
        observation['passed'] = True
    finally:
        observation['state'] = page.evaluate("""() => {
          const observer = window.__amsMotionObservation, root = document.querySelector('#constellation');
          const state = {matches: observer.query.matches, events: observer.events, hidden: document.hidden,
            paused: document.querySelector('#map-motion').getAttribute('aria-pressed'), motion: root.dataset.motion,
            view: [...root.querySelectorAll('[data-map-view]')].filter(x => x.getAttribute('aria-pressed') === 'true').map(x => x.dataset.mapView),
            plot: document.querySelector('#constellation-plot').getBoundingClientRect().toJSON(),
            signals: [...root.querySelectorAll('.map-signals circle.is-active')].map(x => [x.getAttribute('cx'), x.getAttribute('cy')])};
          observer.query.removeEventListener('change', observer.listener);
          delete window.__amsMotionObservation;
          return state;
        }""")
        evidence.setdefault('motion_transitions', []).append(observation)
    assert observation['state']['matches'] == reduced, observation


def assert_map_labels_do_not_overlap(labels, interaction):
    for index, first in enumerate(labels):
        for second in labels[index + 1:]:
            overlap_x = min(first['x'] + first['width'], second['x'] + second['width']) - max(first['x'], second['x'])
            overlap_y = min(first['y'] + first['height'], second['y'] + second['height']) - max(first['y'], second['y'])
            assert overlap_x <= 1 or overlap_y <= 1, (interaction, 'overlapping rendered titles', first, second)


def assert_map_label_inside_viewport(label, interaction):
    geometry = label.evaluate('''label => {
      const box = label.getBoundingClientRect(), plot = label.ownerSVGElement.getBoundingClientRect();
      return {left: box.left, right: box.right, top: box.top, bottom: box.bottom,
        width: box.width, height: box.height, viewport: {
          left: Math.max(plot.left, 0), right: Math.min(plot.right, innerWidth),
          top: Math.max(plot.top, 0), bottom: Math.min(plot.bottom, innerHeight)}};
    }''')
    viewport = geometry['viewport']
    assert geometry['width'] > 0 and geometry['height'] > 0, (interaction, 'empty rendered title', geometry)
    assert (geometry['left'] >= viewport['left'] - 1 and geometry['right'] <= viewport['right'] + 1 and
            geometry['top'] >= viewport['top'] - 1 and geometry['bottom'] <= viewport['bottom'] + 1), (
                interaction, 'the complete rendered title must fit within the visible map viewport', geometry)


def check_constellation_hierarchy(page, width, output):
    """Exercise title hierarchy through public pointer, focus, selection and camera controls."""
    svg = page.locator('#constellation-plot > svg')
    svg.scroll_into_view_if_needed()
    page.mouse.move(1, 1)
    svg.focus()
    page.evaluate('document.fonts.ready')
    expect(page.locator('.map-node-number')).to_have_count(0)
    expect(svg.locator('.map-coordinate ellipse, .map-domains ellipse')).to_have_count(0)
    palette = page.evaluate('''() => {
      function backgrounds(element) {
        for (let el = element; el; el = el.parentElement) {
          const style = getComputedStyle(el);
          const colors = [style.backgroundColor, ...(style.backgroundImage.match(/rgba?\\([^)]*\\)/g) || [])]
            .map(color => color.match(/[\\d.]+/g).map(Number)).filter(channels => channels.length === 3 || channels[3] === 1);
          if (colors.length) return colors.map(rgb => rgb.slice(0, 3).reduce((sum, channel, i) => {
            const c = channel / 255, linear = c <= .04045 ? c / 12.92 : ((c + .055) / 1.055) ** 2.4;
            return sum + linear * [.2126, .7152, .0722][i];
          }, 0));
        }
        return [];
      }
      return {map: backgrounds(document.querySelector('.map-observatory')), body: backgrounds(document.body),
        reading: backgrounds(document.querySelector('#constellation-reading'))};
    }''')
    assert palette['map'] and max(palette['map']) < .15 and min(palette['body']) > .6 and min(palette['reading']) > .6, (
        'night palette must stay local to the map, with a light reading panel and body', palette)
    reduced_positions = map_signal_positions(page)
    assert reduced_positions, 'the current object must retain its explicit reference signals'
    page.wait_for_timeout(100)
    assert map_signal_positions(page) == reduced_positions, 'reduced motion must stop actual reference signals'
    initial = map_relationships(page)
    initial_labels = visible_map_labels(page)
    assert initial_labels and {label['href'] for label in initial_labels} == {initial['current']}, (
        'overview must start with the current title, not an all-node title field', initial_labels)
    assert_map_labels_do_not_overlap(initial_labels, 'overview')
    svg.screenshot(path=str(output / f'constellation-overview-{width}.png'))

    # This published Chinese title was invisible at 390px even though its node
    # was in view: none of its single-line placement candidates fitted the map.
    # Keep the default selection so the regression cannot be hidden by selecting
    # or fitting the target, and locate the research by its public route identity.
    assert initial['selection'] == 'study/ams-thesis', initial
    long_node = page.locator('#constellation-plot .map-node[href*="who-controls-memory"]')
    expect(long_node).to_have_count(1)
    long_label = long_node.locator('.map-node-label')
    long_node.focus()
    expect(long_node).to_be_focused()
    expect(long_label).to_have_css('opacity', '1')
    assert_map_label_inside_viewport(long_label, 'long Chinese title keyboard focus')
    assert map_relationships(page) == initial, 'long-title focus must retain the default selection and references'
    long_title_labels = visible_map_labels(page)
    for label in long_title_labels:
        for line in label['lines']:
            text = line.lstrip()
            assert text and text[0] not in '，。、；：？！…）］｝〉》」』】〕〗〙〛’”', (
                'visible label lines must not start with closing Chinese punctuation', label)
    assert_map_labels_do_not_overlap(long_title_labels, 'long Chinese title keyboard focus')
    svg.screenshot(path=str(output / f'constellation-long-title-focus-{width}.png'))
    svg.focus()
    long_point = long_node.evaluate('''node => {
      const point = new DOMPoint(0, 0).matrixTransform(node.getScreenCTM());
      return {x: point.x, y: point.y};
    }''')
    page.mouse.move(long_point['x'], long_point['y'])
    assert long_node.evaluate("node => node.matches(':hover')"), 'the long-title node must receive actual pointer hover'
    expect(long_label).to_have_css('opacity', '1')
    assert_map_label_inside_viewport(long_label, 'long Chinese title pointer hover')
    assert map_relationships(page) == initial, 'long-title hover must retain the default selection and references'
    long_node.focus()
    page.mouse.move(1, 1)
    expect(long_node).to_be_focused()
    expect(long_label).to_have_css('opacity', '1')
    assert_map_label_inside_viewport(long_label, 'long Chinese title focus after pointer leave')
    assert map_relationships(page) == initial, 'long-title pointer leave must retain keyboard preview and selection'
    svg.focus()

    # Choose an actual close pair in the rendered viewport; layout order and the
    # specific neighboring identities are deliberately not part of this test.
    pair = page.locator('.map-node:not(.is-dimmed)').evaluate_all('''nodes => {
      const plot = document.querySelector('#constellation-plot > svg').getBoundingClientRect();
      const points = nodes.map(node => {
        const point = new DOMPoint(0, 0).matrixTransform(node.getScreenCTM());
        return {index: Number(node.dataset.mapNode), x: point.x, y: point.y};
      }).filter(point => point.x > plot.left + 10 && point.x < plot.right - 10 &&
        point.y > Math.max(plot.top + 10, 10) && point.y < Math.min(plot.bottom - 10, innerHeight - 10));
      let pair = [], distance = Infinity;
      for (let i = 0; i < points.length; i++) for (let j = i + 1; j < points.length; j++) {
        const d = Math.hypot(points[i].x - points[j].x, points[i].y - points[j].y);
        if (d < distance) { distance = d; pair = [points[i], points[j]]; }
      }
      return pair;
    }''')
    assert len(pair) == 2, 'the overview must expose two selectable neighboring nodes'
    first, second = pair
    first_node = page.locator(f'.map-node[data-map-node="{first["index"]}"]')
    second_node = page.locator(f'.map-node[data-map-node="{second["index"]}"]')
    first_node.focus()
    expect(first_node.locator('.map-node-label')).to_have_css('opacity', '1')
    assert map_relationships(page) == initial, 'keyboard focus must not select a node or replace its references'
    first_node.press('Enter')
    selected = map_relationships(page)
    page.mouse.move(second['x'], second['y'])
    expect(second_node.locator('.map-node-label')).to_have_css('opacity', '1')
    assert map_relationships(page) == selected, 'hover must not select a node or replace its references'
    hovered_labels = visible_map_labels(page)
    assert {first['index'], second['index']} <= {label['index'] for label in hovered_labels}, hovered_labels
    assert_map_labels_do_not_overlap(hovered_labels, 'nearest-neighbor hover')
    svg.screenshot(path=str(output / f'constellation-neighbor-hover-{width}.png'))
    page.mouse.move(1, 1)
    second_node.focus()
    expect(second_node.locator('.map-node-label')).to_have_css('opacity', '1')
    assert map_relationships(page) == selected, 'moving keyboard focus must preserve the selected research'
    focus_point = second_node.evaluate('''node => {
      const point = new DOMPoint(0, 0).matrixTransform(node.getScreenCTM());
      return {x: point.x, y: point.y};
    }''')
    page.mouse.move(focus_point['x'], focus_point['y'])
    assert second_node.evaluate("node => node.matches(':hover')"), 'the pointer must actually enter the focused node'
    expect(second_node).to_be_focused()
    page.mouse.move(1, 1)
    assert not second_node.evaluate("node => node.matches(':hover')"), 'the pointer must actually leave the focused node'
    expect(second_node).to_be_focused()
    expect(second_node.locator('.map-node-label')).to_have_css('opacity', '1')
    assert map_relationships(page) == selected, 'pointer leave must preserve keyboard preview and the selected references'
    focused_labels = visible_map_labels(page)
    assert {first['index'], second['index']} <= {label['index'] for label in focused_labels}, focused_labels
    assert_map_labels_do_not_overlap(focused_labels, 'nearest-neighbor keyboard focus')

    svg.focus()
    overview = visible_map_labels(page)
    allowed = {selected['current'], *selected['related']}
    assert overview and all(label['href'] in allowed for label in overview), ('unrelated overview titles', overview)
    assert_map_labels_do_not_overlap(overview, 'selected overview')
    overview_ids = {label['index'] for label in overview}
    revealed = set()
    for _ in range(3):
        page.locator('#map-zoom-in').click()
        zoomed = visible_map_labels(page)
        revealed.update(label['index'] for label in zoomed)
        assert_map_labels_do_not_overlap(zoomed, 'zoomed viewport')
    assert revealed - overview_ids, ('zoom must reveal additional titles within the viewport', overview_ids, revealed)
    assert map_relationships(page) == selected, 'zoom must not change the selected object or references'
    svg.screenshot(path=str(output / f'constellation-zoomed-{width}.png'))
    for _ in range(3):
        page.locator('#map-zoom-out').click()
    restored = visible_map_labels(page)
    assert restored and all(label['href'] in allowed for label in restored), ('zoom-only titles must recede', restored)
    assert not ({label['index'] for label in restored} & (revealed - overview_ids)), (
        'zoomed title detail must disappear again at overview scale', restored)
    assert_map_labels_do_not_overlap(restored, 'zoomed back to overview')
    page.locator('#map-reset').click()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--offline-render', action='store_true')
    parser.add_argument('--browser-executable')
    parser.add_argument('--output-dir', type=Path)
    args = parser.parse_args()
    data = json.loads((ROOT / 'data/materials.json').read_text())
    evidence = {'mode': 'offline-dom' if args.offline_render else 'http-e2e', 'checks': [],
                'skipped': ['HTTP navigation, reload and browser back/forward'] if args.offline_render else [],
                'errors': []}
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        (root / 'agent-memory-study').symlink_to(ROOT, target_is_directory=True)
        output = args.output_dir or root / 'evidence'
        output.mkdir(parents=True, exist_ok=True)
        server = ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(QuietHandler, directory=root))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f'http://127.0.0.1:{server.server_port}/agent-memory-study/'
        html = (ROOT / 'index.html').read_text()
        html = re.sub(r'<script\b[^>]*>.*?</script>', '', html, flags=re.S)
        html = re.sub(r'<link\b[^>]*>', '', html)
        html = html.replace('</head>', '<style>' + (ROOT / 'assets/styles.css').read_text() + '</style></head>')
        app = (ROOT / 'assets/app.js').read_text()
        offline_app = app.replace('window.location', 'window.__AMS_TEST_LOCATION').replace('window.history', 'window.__AMS_TEST_HISTORY')
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(executable_path=args.browser_executable, args=['--no-sandbox'])
                try:
                    for width, height in [(1440, 1000), (390, 844), (320, 740)]:
                        context = browser.new_context(viewport={'width': width, 'height': height}, reduced_motion='reduce', has_touch=width <= 390)
                        # No third-party requests or analytics during tests.
                        external_requests = []
                        context.on('request', lambda request: external_requests.append(request.url)
                                   if urlparse(request.url).hostname not in (None, '127.0.0.1') else None)
                        context.route('**/*', lambda r: r.continue_() if urlparse(r.request.url).hostname == '127.0.0.1' else r.abort())
                        page = context.new_page()
                        page.on('pageerror', lambda error: evidence['errors'].append(str(error)))
                        def go(query=''):
                            if args.offline_render:
                                page.set_content(html)
                                page.evaluate('''url => {
                                  window.__AMS_TEST_LOCATION = new URL(url);
                                  window.__AMS_TEST_HISTORY = {};
                                  for (const method of ['pushState', 'replaceState']) {
                                    window.__AMS_TEST_HISTORY[method] = (s,t,u) => {
                                      window.__AMS_TEST_LOCATION = new URL(u, window.__AMS_TEST_LOCATION);
                                    };
                                  }
                                }''', base + query)
                                for name in ['materials-data.js', 'revision-study.js', 'reading-search.js', 'practice.js', 'study-packets.js', 'index-study.js', 'study-desk.js', 'seo.js', 'research-map.js', 'constellation.js', 'continuity-sculpture.js']:
                                    page.add_script_tag(content=(ROOT / 'assets' / name).read_text())
                                page.add_script_tag(content=offline_app)
                            else:
                                target = base + query
                                previous_document = urldefrag(page.url).url
                                response = page.goto(target, wait_until='domcontentloaded')
                                if response is None:
                                    # Fragment-only navigation stays in the loaded document.
                                    # A new document must still provide an HTTP 200 response.
                                    assert previous_document == urldefrag(target).url, (page.url, target)
                                    assert urldefrag(page.url).url == previous_document, page.url
                                    assert urlparse(page.url).fragment == urlparse(target).fragment, page.url
                                else:
                                    assert response.status == 200, response.status
                            expect(page.locator('h1:visible')).to_have_count(1)
                        def current_url():
                            return page.evaluate('window.__AMS_TEST_LOCATION.href') if args.offline_render else page.url
                        def layout(label):
                            document_width, viewport_width, header_width, header_client_width = page.evaluate('''() => {
                              const header = document.querySelector('.site-header');
                              return [
                                document.documentElement.scrollWidth,
                                document.documentElement.clientWidth,
                                header.scrollWidth,
                                header.clientWidth,
                              ];
                            }''')
                            assert document_width <= viewport_width + 1, (
                                label, 'document', viewport_width, document_width
                            )
                            assert header_width <= header_client_width + 1, (
                                label, 'header', header_client_width, header_width
                            )
                        def record(name):
                            evidence['checks'].append({'width': width, 'check': name, 'passed': True})

                        # The two newest practice findings, shared by the direct
                        # question -> finding hop and the practice-desk checks.
                        new_findings = [item for item in data['findings']
                                        if item['id'] in ('correction-needs-retention-checks',
                                                          'output-guard-is-not-unlearning')]
                        assert len(new_findings) == 2

                        if not args.offline_render:
                            check_index_exercise(page, base + '?study=what-an-index-learns#study-lab', record)
                            page.locator('#study-lab').screenshot(path=str(output / f'index-lab-{width}.png'))
                            page.locator('#study-lab').evaluate('(node) => window.scrollTo(0, node.getBoundingClientRect().top + scrollY - 100)')
                            page.screenshot(path=str(output / f'index-viewport-{width}.png'))
                            page.locator('.index-board').evaluate('(node) => window.scrollTo(0, node.getBoundingClientRect().top + scrollY - 100)')
                            page.screenshot(path=str(output / f'index-board-{width}.png'))
                        go()
                        check_desk_visibility(page, go, record)
                        expect(page.locator('#room-start-list a[data-route=study]')).to_have_count(6)
                        expect(page.locator('#study-index')).to_contain_text('一条更正之后')
                        if not args.offline_render:
                            check_continuation_checkpoint(page, record, go)
                            check_workspace_flow(page, data, width, record, layout, go, external_requests)
                            check_workspace_maturation(page, data, width, record, layout, go, output)
                            if width == 1440:
                                check_workspace_capacity(page, data, record, go)
                                check_index_capacity(page, base, record)
                        if width <= 390:
                            expect(page.locator('#menu-button')).to_be_visible()
                            expect(page.locator('#search')).to_be_visible()
                        layout('home'); record('home entry and layout')
                        # Rebuilt research pathways are usable without an experiment-shaped entry.
                        page.locator('#domain-list a[data-route-id=retrieval]').click()
                        expect(page.locator('#domain-focus')).to_contain_text('检索')
                        assert parse_qs(urlparse(current_url()).query)['domain'] == ['retrieval']
                        page.locator('#direction-list a[data-route-id=forms]').click()
                        expect(page.locator('#direction-focus')).to_be_visible()
                        page.locator('#direction-focus a[data-route=study]').first.click()
                        expect(page.locator('#study-title')).to_have_text('经验怎样获得形式')
                        expect(page.locator('#study-lab')).to_have_count(0)
                        layout('non-experimental research essay')
                        go('?study=retrieval-and-relevance#study-lab')
                        expect(page.locator('#retrieval-ranking')).to_have_value('reference')
                        expect(page.locator('.retrieval-metrics strong')).to_have_text(['100.0%', '33.3%', '25.0%'])
                        page.locator('#retrieval-ranking').select_option('contrast')
                        expect(page.locator('.retrieval-metrics strong')).to_have_text(['33.3%', '100.0%', '75.0%'])
                        page.locator('#retrieval-k').focus(); page.locator('#retrieval-k').press('End')
                        expect(page.locator('#retrieval-k')).to_have_value('8')
                        assert page.evaluate('document.activeElement.id') == 'retrieval-k'
                        layout('retrieval exercise')
                        record('domain/direction navigation, independent essay, retrieval-set comparison and keyboard')
                        if not args.offline_render:
                            note = 'Synthetic continuation: 下次推导。<script>window.BAD=true</script>'
                            page.locator('.private-continuation summary').click()
                            page.locator('#continuation-note').fill(note)
                            with page.expect_download() as event:
                                page.get_by_role('button',name='保存接续文件 ↓',exact=True).click()
                            state = json.loads(Path(event.value.path()).read_text())
                            assert state['note'] == note and state['exercise']['k'] == 8
                            assert state['anchor'] == '#study-lab'
                            with page.expect_download() as event:
                                page.locator('.packet-actions').get_by_role('button',name='JSON ↓',exact=True).click()
                            packet = json.loads(Path(event.value.path()).read_text())
                            assert packet['id'] == 'retrieval-and-relevance'
                            assert note not in json.dumps(packet,ensure_ascii=False)
                            assert page.evaluate('localStorage.length') == 0
                            page.locator('a.site-mark').click()
                            page.locator('#resume-file').set_input_files({'name':'continuation.json','mimeType':'application/json',
                                                                       'buffer':json.dumps(state,ensure_ascii=False).encode()})
                            expect(page.locator('#continuation-note')).to_have_value(note)
                            expect(page.locator('#retrieval-k')).to_have_value('8')
                            expect(page.locator('#retrieval-ranking')).to_have_value('contrast')
                            assert page.evaluate('window.BAD') is None
                            assert 'Synthetic' not in page.url
                            page.locator('a.site-mark').click()
                            for payload, message in [(b'{', '不是有效 JSON'), (b'x'*128001, '过大')]:
                                page.locator('#resume-file').set_input_files({'name':'invalid.json','mimeType':'application/json','buffer':payload})
                                expect(page.locator('#resume-status')).to_contain_text(message)
                                expect(page.locator('#atlas-view')).to_be_visible()
                            record('private continuation roundtrip, public packet separation, malformed files and no persistent storage')
                            go()
                            stage = page.locator('#continuity-sculpture')
                            if stage.get_attribute('data-renderer') == 'webgl':
                                expect(stage).to_have_attribute('data-motion','still')
                                if width == 1440:
                                    page.locator('.sculpture-toggle').click()
                                    expect(stage).to_have_attribute('data-motion','running')
                                    first = stage.screenshot(); page.wait_for_timeout(250); second = stage.screenshot()
                                    assert first != second, 'Playing sculpture did not change its rendered frame'
                                    page.locator('#starts').scroll_into_view_if_needed()
                                    expect(stage).to_have_attribute('data-motion','still')
                                    stage.scroll_into_view_if_needed()
                                    expect(stage).to_have_attribute('data-motion','running')
                                    page.locator('.sculpture-toggle').click()
                                    expect(stage).to_have_attribute('data-motion','still')
                                before_pose = stage.get_attribute('data-pose')
                                stage.focus(); stage.press('ArrowRight')
                                assert before_pose != stage.get_attribute('data-pose'), 'Keyboard rotation did not reach the geometry'
                                page.locator('[data-sculpture-view="spread"]').click()
                                expect(stage).to_have_attribute('data-view', 'spread')
                                if width == 1440:
                                    point = page.evaluate('''() => {
                                        const api=ResearchSculpture, model=api.graph(READING_ROOM);
                                        const stage=document.querySelector('#continuity-sculpture'), box=stage.getBoundingClientRect();
                                        const [yaw,pitch]=stage.dataset.pose.split(',').map(Number);
                                        const index=15, pose=api.layout(model,'spread',0)[index];
                                        const xy=api.project(pose,yaw,pitch,box.width,box.height);
                                        return {x:box.x+xy[0],y:box.y+xy[1],key:model.nodes[index].key};
                                    }''')
                                    page.mouse.click(point['x'],point['y'])
                                    expect(stage).to_have_attribute('data-selection',point['key'])
                                    box=stage.bounding_box(); before_pose=stage.get_attribute('data-pose')
                                    page.mouse.move(box['x']+box['width']/2,box['y']+box['height']/2)
                                    page.mouse.down(); page.mouse.move(box['x']+box['width']/2+80,box['y']+box['height']/2-30,steps=8); page.mouse.up()
                                    assert before_pose != stage.get_attribute('data-pose'), 'Pointer drag did not rotate the model'
                                    # A drag that returns to its start is still a drag, not a new selection.
                                    selection_before = stage.get_attribute('data-selection')
                                    point = page.evaluate('''() => {
                                        const api=ResearchSculpture, model=api.graph(READING_ROOM);
                                        const stage=document.querySelector('#continuity-sculpture'), box=stage.getBoundingClientRect();
                                        const [yaw,pitch]=stage.dataset.pose.split(',').map(Number);
                                        const xy=api.project(api.layout(model,'spread',0)[0],yaw,pitch,box.width,box.height);
                                        return {x:box.x+xy[0],y:box.y+xy[1]};
                                    }''')
                                    page.mouse.move(point['x'],point['y']); page.mouse.down()
                                    page.mouse.move(point['x']+70,point['y']-20,steps=6)
                                    page.mouse.move(point['x'],point['y'],steps=6); page.mouse.up()
                                    expect(stage).to_have_attribute('data-selection',selection_before)
                                page.locator('[data-sculpture-view="links"]').click()
                                expect(stage).to_have_attribute('data-view','links')
                                if width == 1440:
                                    point = page.evaluate('''() => {
                                        const api=ResearchSculpture, model=api.graph(READING_ROOM);
                                        const stage=document.querySelector('#continuity-sculpture'), box=stage.getBoundingClientRect();
                                        const selected=model.nodes.findIndex(node=>node.key===stage.dataset.selection);
                                        const [yaw,pitch]=stage.dataset.pose.split(',').map(Number);
                                        const xy=api.project(api.layout(model,'links',selected)[selected],yaw,pitch,box.width,box.height);
                                        return {x:box.x+xy[0],y:box.y+xy[1]};
                                    }''')
                                    page.evaluate("document.querySelector('#continuity-sculpture canvas').getContext('webgl').getExtension('WEBGL_lose_context').loseContext()")
                                    expect(stage).to_have_attribute('data-renderer','fallback')
                                    page.mouse.move(point['x'],point['y'])
                                    expect(page.locator('.sculpture-labels button')).to_have_count(0)
                                    for button in page.locator('[data-sculpture-view]').all():
                                        expect(button).to_be_disabled()
                                    record('lost WebGL context keeps fallback stable during subsequent pointer input')
                                expected_title=page.locator('#sculpture-title').inner_text()
                                page.locator('#sculpture-open').click()
                                expect(page.locator('h1:visible')).to_have_text(expected_title)
                                go()
                                record('research sculpture keyboard/drag rotation, actual object picking, linked view and reading route')
                            else:
                                expect(page.locator('.sculpture-fallback')).to_be_visible()
                            stage_box = stage.bounding_box()
                            assert abs(stage_box['x'] + stage_box['width']/2 - width/2) < 10
                            layout('editorial cover')
                            page.screenshot(path=str(output / f'editorial-cover-{width}.png'))
                            record('central editorial composition, reduced-motion and available WebGL controls')
                        go('#constellation')
                        star_map = page.locator('#constellation')
                        map_svg = page.locator('#constellation-plot > svg')
                        map_svg.scroll_into_view_if_needed()
                        expect(map_svg).to_be_visible()
                        assert not page.locator('#legacy-lenses').evaluate('(el)=>el.open')
                        total = sum(len(data[key]) for key in ('materials','studies','questions','findings'))
                        expect(page.locator('.map-node')).to_have_count(total)
                        expect(star_map).to_have_attribute('data-motion','still')
                        check_constellation_hierarchy(page, width, output)
                        record('local night map, sparse overview titles, hover/focus identity, neighboring title collision and zoom detail/retraction')
                        page.locator('[data-map-kind="question"]').click()
                        expect(page.locator('#constellation-stats')).to_contain_text('02 /')
                        page.locator('[data-map-view="list"]').click()
                        expect(page.locator('#constellation-list .map-list-row:visible')).to_have_count(2)
                        if width == 1440:
                            emulate_map_motion(page, 'no-preference', evidence)
                            page.locator('#constellation-list .map-list-row:visible button').last.click()
                        page.locator('[data-map-view="map"]').click()
                        if width == 1440:
                            expect(page.locator('.map-node.is-selected .map-node-label')).to_have_css('opacity','1')
                            emulate_map_motion(page, 'reduce', evidence, refresh_during_transition=True)
                            page.locator('#map-reset').click()
                            linked_node = page.locator('.map-node[data-map-node="0"]')
                            linked_node.focus(); linked_node.press('Enter')
                            # A finite repetition guards actual signal motion and the
                            # active-map refresh/media boundary, not just a badge.
                            for _ in range(3):
                                emulate_map_motion(page, 'no-preference', evidence)
                                map_svg.scroll_into_view_if_needed()
                                expect(star_map).to_have_attribute('data-motion', 'running')
                                moving_signals = map_signal_positions(page)
                                assert moving_signals
                                page.wait_for_function('''before => JSON.stringify([...document.querySelectorAll('.map-signals circle.is-active')]
                                  .map(dot => [dot.getAttribute('cx'), dot.getAttribute('cy')])) !== JSON.stringify(before)''',
                                  arg=moving_signals, timeout=5000)
                                emulate_map_motion(page, 'reduce', evidence, refresh_during_transition=True)
                                expect(star_map).to_have_attribute('data-motion', 'still')
                                stopped_signals = map_signal_positions(page)
                                page.evaluate('() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(() => requestAnimationFrame(resolve))))')
                                assert map_signal_positions(page) == stopped_signals, 'media reduction must stop actual signals'
                            record('native media changes across active refresh, repeated actual signal start/stop')
                        page.locator('#map-reset').click()
                        page.locator('#map-query').fill('retrieval-and-relevance')
                        expect(page.locator('#constellation-stats')).to_contain_text('01 /')
                        expect(page.locator('#constellation-reading')).to_have_attribute('data-selection','study/retrieval-and-relevance')
                        before_url = current_url()
                        page.locator('#map-query').fill('no-such-object-xyz')
                        expect(page.locator('#map-empty')).to_be_visible()
                        assert current_url() == before_url, 'Map search must stay out of the URL'
                        page.locator('#map-reset').click()
                        page.locator('#map-domain').select_option('retrieval')
                        assert all(page.locator('.map-node:not(.is-dimmed)').evaluate_all("nodes=>nodes.map(n=>ResearchMap.graph(READING_ROOM).nodes[Number(n.dataset.mapNode)].domainIds.includes('retrieval'))"))
                        page.locator('#map-reset').click()
                        map_svg.scroll_into_view_if_needed()
                        node = page.locator('.map-node[data-map-node="0"]')
                        node.focus(); node.press('Enter')
                        expect(page.locator('#constellation-reading')).to_have_attribute('data-selection', 'study/' + data['studies'][0]['id'])
                        point = page.locator('.map-node[data-map-node="1"]').evaluate("node=>{const p=new DOMPoint(0,0).matrixTransform(node.getScreenCTM());return {x:p.x,y:p.y};}")
                        page.mouse.click(point['x'],point['y'])
                        expect(page.locator('#constellation-reading')).to_have_attribute('data-selection','study/'+data['studies'][1]['id'])
                        if width <= 390 and not args.offline_render:
                            touch_point=page.locator('.map-node[data-map-node="2"]').evaluate("node=>{const p=new DOMPoint(0,0).matrixTransform(node.getScreenCTM());return {x:p.x,y:p.y};}")
                            page.touchscreen.tap(touch_point['x'],touch_point['y'])
                            expect(page.locator('#constellation-reading')).to_have_attribute('data-selection','study/'+data['studies'][2]['id'])
                        before_box = map_svg.get_attribute('viewBox')
                        page.locator('#map-focus').click()
                        expect(page.locator('#map-focus')).to_have_attribute('aria-pressed','true')
                        assert before_box != map_svg.get_attribute('viewBox')
                        expect(page.locator('.map-edges .is-active')).not_to_have_count(0)
                        page.locator('#map-zoom-in').click()
                        zoom_box=map_svg.get_attribute('viewBox')
                        page.locator('#map-zoom-out').click()
                        assert zoom_box != map_svg.get_attribute('viewBox')
                        page.locator('#map-reset').click();map_svg.scroll_into_view_if_needed()
                        before_box=map_svg.get_attribute('viewBox');box=map_svg.bounding_box()
                        page.mouse.move(box['x']+box['width']*.5,box['y']+box['height']*.5)
                        page.mouse.down();page.mouse.move(box['x']+box['width']*.5+45,box['y']+box['height']*.5+25,steps=5);page.mouse.up()
                        assert before_box != map_svg.get_attribute('viewBox'), 'Pan did not move the camera'
                        if width == 1440:
                            expect(page.locator('#map-motion')).to_have_attribute('aria-pressed','true')
                            page.locator('#map-motion').click()
                            expect(page.locator('#map-motion')).to_have_attribute('aria-pressed','false')
                            emulate_map_motion(page, 'reduce', evidence, paused=False)
                            # Clicking a control may scroll its plot out of view. Running
                            # motion requires both an unpaused control and a visible plot.
                            map_svg.scroll_into_view_if_needed()
                            try:
                                expect(star_map).to_have_attribute('data-motion','running')
                            except AssertionError:
                                evidence['motion_failure_state'] = page.evaluate('''() => ({
                                  hidden: document.hidden,
                                  reduced: matchMedia('(prefers-reduced-motion: reduce)').matches,
                                  paused: document.querySelector('#map-motion').getAttribute('aria-pressed'),
                                  plot: document.querySelector('#constellation-plot').getBoundingClientRect().toJSON(),
                                  viewportHeight: innerHeight
                                })''')
                                raise
                            before_signals = map_signal_positions(page)
                            assert before_signals, 'a selected linked object must expose reference signals'
                            page.wait_for_function('''before => JSON.stringify([...document.querySelectorAll('.map-signals circle.is-active')]
                              .map(dot => [dot.getAttribute('cx'), dot.getAttribute('cy')])) !== JSON.stringify(before)''',
                              arg=before_signals)
                            page.locator('#starts').scroll_into_view_if_needed()
                            expect(star_map).to_have_attribute('data-motion','still')
                            offscreen_signals = map_signal_positions(page)
                            page.wait_for_timeout(100)
                            assert map_signal_positions(page) == offscreen_signals, 'offscreen reference signals must stop'
                            map_svg.scroll_into_view_if_needed()
                            expect(star_map).to_have_attribute('data-motion','running')
                            page.locator('#map-motion').click()
                            expect(star_map).to_have_attribute('data-motion','still')
                            paused_signals = map_signal_positions(page)
                            page.wait_for_timeout(100)
                            assert map_signal_positions(page) == paused_signals, 'the pause control must stop actual reference signals'
                        page.locator('#map-reset').click()
                        if width == 1440 and not args.offline_render:
                            page.locator('#map-fullscreen').click()
                            expect(page.locator('#map-fullscreen')).to_have_attribute('aria-pressed','true')
                            assert page.evaluate('document.fullscreenElement.id') == 'constellation'
                            page.locator('#map-fullscreen').click()
                            expect(page.locator('#map-fullscreen')).to_have_attribute('aria-pressed','false')
                        expected_title=page.locator('#map-reading-title').inner_text()
                        page.locator('#map-open').click()
                        expect(page.locator('h1:visible')).to_have_text(expected_title)
                        if not args.offline_render:
                            page.go_back();expect(star_map).to_be_visible()
                            assert page.evaluate('localStorage.length') == 0
                        layout('constellation and reading route')
                        record('constellation direct link, mobile map, filters, list, empty/reset, keyboard/pointer selection, focus/zoom/pan, reduced motion, offscreen pause, history and reading route')
                        for material in data['materials']:
                            go('?material=' + material['id'])
                            expect(page.locator('#material-title')).to_have_text(material['title'])
                            toc_labels = page.locator('#article-toc a').all_text_contents()
                            assert toc_labels and all('undefined' not in label and re.search(r'\D', label.strip()) for label in toc_labels), material['id']
                            expect(page.locator('#material-findings li')).to_have_text(material.get('reportedFindings', []))
                            section = page.locator('#paper-ams-evidence')
                            if material.get('amsEvidence'):
                                expect(section).to_be_visible()
                                expect(section.locator('a').first).to_have_attribute('href', material['amsEvidence']['artifactUrl'])
                                for finding in material['amsEvidence']['findings']:
                                    assert finding in section.inner_text()
                                    assert finding not in page.locator('#paper-findings').inner_text()
                                section.locator('summary').click()
                                expect(section.locator('details')).to_have_attribute('open', '')
                            else:
                                expect(section).to_be_hidden()
                            layout(material['id']); record('material ownership/layout: ' + material['id'])
                            if width in (1440, 390) and material['id'] == 'statefuse-conflict-preserving-memory':
                                page.locator('#paper-ams-evidence').screenshot(path=str(output / f'ams-evidence-{width}.png'))

                        go('?q=%E4%B8%80%E6%9D%A1%E6%9B%B4%E6%AD%A3%E4%B9%8B%E5%90%8E#library')
                        expect(page.locator('#material-index a[data-route=study]').first).to_contain_text('一条更正之后')
                        expect(page.locator('#material-index [data-result-kind=material]')).to_have_count(0)
                        page.locator('#material-index a[data-route=study]').first.click()
                        expect(page.locator('#study-title')).to_have_text('一条更正之后')
                        page.locator('#study-scenario').select_option('legacy')
                        assert page.evaluate('document.activeElement.id') == 'study-scenario'
                        page.locator('#study-phase-after').click()
                        assert page.evaluate('document.activeElement.id') == 'study-phase-after'
                        expect(page.locator('.study-output')).to_have_count(4)
                        expect(page.locator('#study-phase-after')).to_have_attribute('aria-pressed', 'true')
                        query = parse_qs(urlparse(current_url()).query)
                        assert query['scenario'] == ['legacy'] and query['phase'] == ['after'], query
                        layout('study after'); record('search to study, scenario, phase, focus and share state')
                        if not args.offline_render:
                            page.go_back()
                            expect(page.locator('#study-phase-before')).to_have_attribute('aria-pressed', 'true')
                            expect(page.locator('#study-scenario')).to_have_value('legacy')
                            page.go_back()
                            expect(page.locator('#study-scenario')).to_have_value('corrected')
                            page.go_back()
                            expect(page.locator('#search')).to_have_value('一条更正之后')
                            expect(page.locator('#material-index a[data-route=study]').first).to_contain_text('一条更正之后')
                            page.go_forward()
                            expect(page.locator('#study-title')).to_be_visible()
                            record('real browser back/forward restores search and scenario')
                        go('?study=after-a-correction&scenario=legacy&phase=after')
                        expect(page.locator('#study-scenario')).to_have_value('legacy')
                        expect(page.locator('#study-phase-after')).to_have_attribute('aria-pressed', 'true')
                        if not args.offline_render:
                            page.reload(wait_until='domcontentloaded')
                            expect(page.locator('#study-phase-after')).to_have_attribute('aria-pressed', 'true')
                            record('direct share URL and real reload')
                        else:
                            record('direct state render (not navigation)')

                        go('?q=TRUSTMEM+Yang#library')
                        expect(page.locator('#material-index [data-result-kind=material]')).to_have_count(1)
                        expect(page.locator('#material-index a[data-route=material]').first).to_contain_text('TRUSTMEM')
                        expect(page.locator('.search-match-label')).to_contain_text('作者')
                        page.locator('#search').fill('<img src=x onerror=alert(1)>')
                        expect(page.locator('#empty-state')).to_be_visible()
                        expect(page.locator('img[src=x]')).to_have_count(0)
                        page.locator('#clear-filters').click()
                        page.locator('#depth-filter').select_option('read')
                        assert parse_qs(urlparse(current_url()).query)['depth'] == ['read']
                        expected = sum(m['noteDepth'] == 'read' for m in data['materials'])
                        expect(page.locator('#material-index [data-result-kind=material]')).to_have_count(expected)
                        layout('filtered search'); record('multifield query, empty state, text safety and filter URL')
                        if width in (1440, 390):
                            page.screenshot(path=str(output / f'search-{width}.png'))
                        go('#inquiries')
                        expect(page.locator('#question-index a[data-route=question]')).to_have_count(len(data['questions']) * 2)
                        expect(page.locator('#practice-results .practice-result')).to_have_count(3)
                        page.locator('#question-index a[data-route=question]').first.click()
                        expect(page.locator('#inquiry-title')).to_have_text(data['questions'][0]['title'])
                        expect(page.locator('#inquiry-next')).to_contain_text('尚未运行真实模型 pilot')
                        layout('question dossier'); record('question entry, current judgment, evidence and next test')
                        if width in (1440, 390):
                            page.screenshot(path=str(output / f'question-{width}.png'))
                        page.locator('#inquiry-practice a[data-route=finding]').first.click()
                        expect(page.locator('#inquiry-title')).to_have_text(data['findings'][0]['title'])
                        expect(page.locator('#inquiry-applications')).to_contain_text('已采用')
                        expect(page.locator('#inquiry-applications')).to_contain_text('不证明真实开发效率')
                        layout('finding'); record('question to finding, scope, evidence and adopted boundary')
                        if width in (1440, 390):
                            page.screenshot(path=str(output / f'finding-{width}.png'))
                        if not args.offline_render:
                            for label, suffix in [('下载 JSON', 'json'), ('下载 Markdown', 'md')]:
                                with page.expect_download() as download_event:
                                    page.get_by_role('button', name=label, exact=True).click()
                                download = download_event.value
                                destination = output / f'finding-{width}.{suffix}'
                                download.save_as(destination)
                                content = destination.read_text()
                                assert 'retrieval-candidate-competition' in content
                                assert 'Agent Memory Study editors' in content
                                assert '不证明真实开发效率' in content
                                assert 'https://' in content
                                if suffix == 'json':
                                    assert len(json.loads(content)['findings']) == 1
                            page.go_back()
                            expect(page.locator('#inquiry-title')).to_have_text(data['questions'][0]['title'])
                            page.go_forward()
                            expect(page.locator('#inquiry-title')).to_have_text(data['findings'][0]['title'])
                            record('finding Markdown/JSON downloads and real history')
                        for kind, records in [('question', data['questions']), ('finding', data['findings'])]:
                            for item in records:
                                go('?' + kind + '=' + item['id'])
                                expect(page.locator('#inquiry-title')).to_have_text(item['title'])
                                if not args.offline_render:
                                    page.reload(wait_until='domcontentloaded')
                                    expect(page.locator('#inquiry-title')).to_have_text(item['title'])
                                layout(kind + ' direct ' + item['id'])
                        record('all question/finding direct links, reload and layout')
                        if not args.offline_render:
                            # The new findings hang off the second question; check
                            # question -> finding hopping, exact export and real
                            # back/forward for each of them.
                            for item in new_findings:
                                go('?question=experience-becomes-policy')
                                expect(page.locator('#inquiry-practice')).to_contain_text(item['title'])
                                page.locator(
                                    f'#inquiry-practice a[data-route=finding][href*="{item["id"]}"]'
                                ).first.click()
                                expect(page.locator('#inquiry-title')).to_have_text(item['title'])
                                expect(page.locator('#inquiry-use')).to_contain_text(item['action'])
                                expect(page.locator('#inquiry-use')).to_contain_text(item['validation'])
                                expect(page.locator('#inquiry-evidence')).to_contain_text(item['evidence'][0]['observation'])
                                expect(page.locator('#inquiry-evidence')).to_contain_text(item['evidence'][0]['limit'])
                                expect(page.locator('.inquiry-heading')).to_contain_text(item['byline'])
                                expect(page.locator('.inquiry-heading')).to_contain_text(item['updated'])
                                with page.expect_download() as download_event:
                                    page.locator('#inquiry-use').get_by_role('button', name='下载 Markdown').click()
                                destination = output / f'finding-{item["id"]}-{width}.md'
                                download_event.value.save_as(destination)
                                content = destination.read_text()
                                for token in [item['title'], item['byline'], item['updated'], item['limit'],
                                              item['evidence'][0]['observation'], item['evidence'][0]['limit']]:
                                    assert token in content, (item['id'], token)
                                page.reload(wait_until='domcontentloaded')
                                expect(page.locator('#inquiry-title')).to_have_text(item['title'])
                                page.go_back()
                                expect(page.locator('#inquiry-title')).to_have_text(
                                    next(q['title'] for q in data['questions'] if q['id'] == 'experience-becomes-policy'))
                                page.go_forward()
                                expect(page.locator('#inquiry-title')).to_have_text(item['title'])
                            record('question to new finding, exact export and real history')
                        go('#library')
                        page.locator('#search').fill('jevlike')
                        page.locator('#material-index a[data-route=study]').first.click()
                        expect(page.locator('#study-title')).to_have_text('没有再读那段往事，它为什么还是改变了选择？')
                        expect(page.locator('#decision-summary tbody tr')).to_have_count(4)
                        expect(page.locator('#decision-cases tbody tr')).to_have_count(12)
                        expect(page.locator('.decision-support')).to_contain_text('288/288')
                        page.locator('#study-phase-after').click()
                        expect(page.locator('#decision-summary')).to_contain_text('仅改记录')
                        expect(page.locator('#decision-summary')).to_contain_text('96/276')
                        assert page.evaluate('document.activeElement.id') == 'study-phase-after'
                        page.locator('#study-scenario').select_option('export-ordinary-all-known')
                        expect(page.locator('.study-scenario-description')).to_contain_text('普通')
                        assert page.evaluate('document.activeElement.id') == 'study-scenario'
                        layout('recorded experiment'); record('cross-source search, executed result, phase, case and focus')
                        if not args.offline_render:
                            page.go_back()
                            expect(page.locator('#study-scenario')).to_have_value('export-sensitive-base')
                            page.go_back()
                            expect(page.locator('#study-phase-before')).to_have_attribute('aria-pressed','true')
                            page.go_forward()
                            page.reload(wait_until='domcontentloaded')
                            expect(page.locator('#study-phase-after')).to_have_attribute('aria-pressed','true')
                            with page.expect_download() as download:
                                page.locator('#decision-download').click()
                            saved=json.loads(Path(download.value.path()).read_text())
                            assert saved == json.loads((ROOT/'research/decision-learning-study/results.json').read_text())
                            record('recorded experiment history, reload and exact result JSON export')
                        page.locator('#study-lab').scroll_into_view_if_needed()
                        page.screenshot(path=str(output/f'decision-learning-{width}.png'))
                        go('?study=experience-becomes-policy&scenario=export-ordinary-all-known&phase=after')
                        expect(page.locator('#study-scenario')).to_have_value('export-ordinary-all-known')
                        expect(page.locator('#study-phase-after')).to_have_attribute('aria-pressed','true')
                        go('?question=experience-becomes-policy')
                        expect(page.locator('#inquiry-practice a[data-route=finding]')).to_have_count(2)
                        for item in new_findings:
                            expect(page.locator('#inquiry-practice')).to_contain_text(item['title'])
                        expect(page.locator('#inquiry-practice')).to_contain_text('具体迁移方法仍需在目标系统验证')
                        page.locator('#inquiry-practice a[data-route=study]').filter(has_text='没有再读那段往事').click()
                        expect(page.locator('#decision-summary')).to_be_visible()
                        record('new study direct URL, question link and honest findings state')
                        contract = json.loads((ROOT/'research/jev-memory-contract-study/results.json').read_text())
                        first, last = contract['cases'][0], contract['cases'][-1]
                        go('?study=who-controls-memory&scenario='+last['id']+'&phase=after')
                        expect(page.locator('#study-scenario')).to_have_value(last['id'])
                        expect(page.locator('#contract-state h3')).to_have_text('调用后的快照')
                        expect(page.locator('#contract-comparison')).to_contain_text(
                            f"存储节点 {len(last['before']['stored_ids'])} → {len(last['after']['stored_ids'])}")
                        page.locator('#study-scenario').select_option(first['id'])
                        expect(page.locator('.study-scenario-description')).to_have_text(first['intervention'])
                        assert page.evaluate('document.activeElement.id') == 'study-scenario'
                        page.locator('#study-phase-before').click()
                        expect(page.locator('#contract-state h3')).to_have_text('调用前的快照')
                        assert page.evaluate('document.activeElement.id') == 'study-phase-before'
                        page.locator('#contract-observations summary').click()
                        expect(page.locator('#contract-observations pre')).to_contain_text(first['id'])
                        layout('source contract case and expanded receipt')
                        if not args.offline_render:
                            page.go_back()
                            expect(page.locator('#contract-state h3')).to_have_text('调用后的快照')
                            page.reload(wait_until='domcontentloaded')
                            expect(page.locator('#study-scenario')).to_have_value(first['id'])
                            with page.expect_download() as download:
                                page.locator('#contract-download').click()
                            assert json.loads(Path(download.value.path()).read_text()) == contract
                        page.locator('#study-lab').scroll_into_view_if_needed()
                        page.screenshot(path=str(output/f'jev-contract-{width}.png'))
                        go('?material=jev-mem-system-one-control')
                        page.locator('#material-studies a[data-route=study]').filter(has_text='谁在管理记忆').click()
                        expect(page.locator('#contract-download')).to_be_visible()
                        record('Jev source contract deep link, case, phase, focus, raw receipt, history and exact export')
                        go('?study=representation-and-use')
                        expect(page.locator('#study-title')).to_have_text('概括之后，往事还记得准吗？')
                        expect(page.locator('#study-lab')).to_contain_text('研究方案尚未执行')
                        expect(page.locator('#study-lab select, #study-lab button, #study-lab table')).to_have_count(0)
                        expect(page.locator('#study-lab a')).to_have_attribute('href', 'research/representation-use-study/README.md')
                        expect(page.locator('.study-toc a[href="#study-lab"]')).to_contain_text('下一项研究')
                        layout('proposed representation study')
                        if not args.offline_render:
                            response = context.request.get(page.locator('#study-lab a').evaluate('(a) => a.href'))
                            assert response.status == 200
                            assert 'proposed-not-run' in response.text()
                            page.reload(wait_until='domcontentloaded')
                            expect(page.locator('#study-lab')).to_contain_text('研究方案尚未执行')
                            go('?question=experience-becomes-policy')
                            page.locator('a.inquiry-onward[data-route=study]').filter(has_text='概括之后').click()
                            expect(page.locator('#study-title')).to_have_text('概括之后，往事还记得准吗？')
                            page.go_back()
                            expect(page.locator('#inquiry-title')).to_be_visible()
                            page.go_forward()
                            expect(page.locator('#study-lab select')).to_have_count(0)
                        page.locator('#study-lab').scroll_into_view_if_needed()
                        page.screenshot(path=str(output/f'representation-plan-{width}.png'))
                        record('proposed study deep link, status, protocol, reload, history and no execution controls')
                        go('?material=continual-learning-experience-reuse')
                        page.locator('#material-inquiries a[data-route=question]').first.click()
                        expect(page.locator('#inquiry-title')).to_have_text(data['questions'][0]['title'])
                        page.locator('.inquiry-materials a[data-route=material]').first.click()
                        expect(page.locator('#material-title')).to_contain_text('When continual learning')
                        record('material/question reciprocal links')
                        go('#practice')
                        problem = '候选增加之后，结果被重复条目占满'
                        page.locator('#practice-query').fill(problem)
                        page.locator('#practice-query').press('Enter')
                        expect(page.locator('#practice-results a[data-route=finding]').first).to_contain_text('旧经验还在')
                        assert '[object Object]' not in page.locator('#practice-results').inner_text()
                        assert parse_qs(urlparse(current_url()).query)['practice'] == [problem]
                        assert page.evaluate('document.activeElement.id') == 'practice-query'
                        layout('practice query'); record('natural problem query, match explanation, focus and URL')
                        if width in (1440, 390):
                            page.screenshot(path=str(output / f'practice-{width}.png'))
                        if not args.offline_render:
                            with page.expect_download() as download_event:
                                page.locator('#practice-export').get_by_role('button', name='下载 JSON').click()
                            destination = output / f'query-{width}.json'
                            download_event.value.save_as(destination)
                            brief = json.loads(destination.read_text())
                            assert brief['query'] == problem
                            assert brief['findings'][0]['id'] == 'retrieval-candidate-competition'
                            page.reload(wait_until='domcontentloaded')
                            expect(page.locator('#practice-query')).to_have_value(problem)
                            expect(page.locator('#practice-results .practice-result')).to_have_count(len(brief['findings']))
                            record('query export matches visible results and reload')
                        page.locator('#practice-query').fill('火星天气 superconductivity')
                        page.locator('#practice-query').press('Enter')
                        expect(page.locator('#practice-results')).to_contain_text('没有找到相关判断')
                        expect(page.locator('#practice-export button')).to_have_count(0)
                        page.locator('#practice-examples button').nth(1).click()
                        expect(page.locator('#practice-results a').first).to_contain_text('新说明出现')
                        page.locator('#practice-examples button').nth(2).click()
                        expect(page.locator('#practice-results a').first).to_contain_text('来源对象消失')
                        record('honest no-match state and working example queries')
                        # Two new practice findings must be reachable through the
                        # practice desk in both languages, from the example chips
                        # and from typed keyword queries, not just full sentences.
                        assert '只整理了这三条' not in page.locator('#practice').inner_text()
                        for idx, item in enumerate(new_findings):
                            page.locator('#practice-examples button').nth(3 + idx).click()
                            expect(page.locator('#practice-results a').first).to_contain_text(item['title'])
                        for query, finding_id in [('纠正 增量 保留范围', 'correction-needs-retention-checks'),
                                                  ('输出约束 参数 遗忘', 'output-guard-is-not-unlearning'),
                                                  ('correction retention', 'correction-needs-retention-checks'),
                                                  ('guard unlearning', 'output-guard-is-not-unlearning')]:
                            page.locator('#practice-query').fill(query)
                            page.locator('#practice-query').press('Enter')
                            # Lexical top-3 contract: the target ranks first and
                            # the visible set never exceeds three findings.
                            target_title = next(item['title'] for item in data['findings']
                                                if item['id'] == finding_id)
                            expect(page.locator('#practice-results a').first).to_contain_text(
                                target_title)
                            result_count = page.locator('#practice-results .practice-result').count()
                            assert 1 <= result_count <= 3, (query, result_count)
                        record('new findings discoverable from examples and keyword queries')
                        for text, kind in [('旧经验，怎样继续帮助当前任务？', 'question'), ('新说明出现，不代表旧范围已经失效', 'finding')]:
                            go('#library')
                            page.locator('#search').fill(text)
                            expect(page.locator('#material-index [data-result-kind=' + kind + ']')).to_have_count(1)
                            page.locator('#material-index a[data-route=' + kind + ']').first.click()
                            expect(page.locator('#inquiry-title')).to_have_text(text)
                        record('global search to new content kinds')
                        for query in ['?material=missing', '?study=after-a-correction&scenario=missing&phase=bad',
                                      '?question=missing', '?finding=missing', '?thread=retrieval-active-context', '?path=from-revision', '#%', '#missing[bracket]']:
                            go(query); layout(query)
                        record('invalid and legacy routes render')
                        context.close()
                finally:
                    browser.close()
            assert not evidence['errors'], evidence['errors']
            evidence['passed'] = True
        except Exception as error:
            evidence['passed'] = False
            evidence['failure'] = str(error)
            raise
        finally:
            server.shutdown(); server.server_close()
            (output / 'browser-check.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2))
        print(json.dumps({'mode': evidence['mode'], 'passed': evidence['passed'],
                          'checks': len(evidence['checks']), 'skipped': evidence['skipped']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
