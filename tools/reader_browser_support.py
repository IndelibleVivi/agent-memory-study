"""Shared actual-browser harness. Only original synthetic private input is used."""
from contextlib import contextmanager
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
import threading
from urllib.parse import urlparse
from playwright.sync_api import expect

ROOT = Path(__file__).resolve().parents[1]

@contextmanager
def serve(site):
    with tempfile.TemporaryDirectory(prefix='ams-reader-http-') as tmp:
        (Path(tmp) / 'agent-memory-study').symlink_to(site.resolve(), target_is_directory=True)
        class Handler(SimpleHTTPRequestHandler):
            def log_message(self, *_): pass
            def send_error(self, code, message=None, explain=None):
                if code != 404: return super().send_error(code, message, explain)
                content=(site/'404.html').read_bytes()
                self.send_response(404); self.send_header('Content-Type','text/html; charset=utf-8'); self.end_headers(); self.wfile.write(content)
        server=ThreadingHTTPServer(('127.0.0.1',0),partial(Handler,directory=tmp))
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try: yield f'http://127.0.0.1:{server.server_port}/agent-memory-study/'
        finally: server.shutdown();server.server_close();thread.join()

def observe(page,base,report):
    page.set_default_timeout(10000)
    page.on('pageerror',lambda e:report['errors'].append(str(e)))
    page.on('dialog',lambda d:d.accept())
    origin=urlparse(base).netloc
    def request(route):
        url=urlparse(route.request.url)
        if url.scheme in ('file','data','blob') or url.netloc==origin: route.continue_()
        else: report['external'].append(route.request.url);route.abort()
    page.route('**/*',request)

def ready(page):
    page.wait_for_function('document.documentElement.classList.contains("interactive")')
    expect(page.locator('.ams-app')).to_have_attribute('data-ready','true')

def fits(page):
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1'),page.url

def download(page,action):
    with page.expect_download() as event: action()
    return Path(event.value.path()).read_bytes()

def import_file(page,value):
    page.locator('.thread-list input[type=file]').set_input_files({'name':'synthetic-research.json','mimeType':'application/json','buffer':value})
    expect(page.locator('.import-preview')).to_be_visible()
    page.get_by_role('button',name='确认导入',exact=True).click()
    expect(page.locator('.import-preview')).to_have_count(0)
