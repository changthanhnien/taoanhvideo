import sys
import os
os.environ['QT_API'] = 'pyside6'

import json
import logging
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer

# Path definitions
ARTIFACTS_DIR = Path(r"C:\Users\ASUS\.gemini\antigravity\brain\9228e2ba-62b3-49c8-8df9-e48ecb1067de")
LIFECYCLE_LOG = ARTIFACTS_DIR / "webview_lifecycle.log"
CONSOLE_LOG = ARTIFACTS_DIR / "browser_console.log"
DOM_PROBE = ARTIFACTS_DIR / "dom_state.json"
BRIDGE_PROBE = ARTIFACTS_DIR / "bridge_probe.json"
RENDER_IMAGE = ARTIFACTS_DIR / "render_verified.png"

logging.basicConfig(filename=str(LIFECYCLE_LOG), level=logging.INFO, 
                    format='[%(asctime)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

def log_event(event_name, data=""):
    msg = f"{event_name} -> {data}"
    logging.info(msg)
    print(msg)

app = QApplication(sys.argv)
from ui.pages.watermark_remove_page import WatermarkRemovePage

w = WatermarkRemovePage()
w.resize(1600, 900)
webview = w.web_page.webview

source_dir = Path(__file__).resolve().parent / "features" / "watermark_remove" / "source"
index_path = source_dir / "templates" / "index.html"

webview.loadStarted.connect(lambda: log_event("loadStarted"))
webview.loadProgress.connect(lambda p: log_event("loadProgress", str(p)))
webview.renderProcessTerminated.connect(lambda status, code: log_event("renderProcessTerminated", f"status={status}, code={code}"))

w.showEvent = lambda e: log_event("showEvent")
w.resizeEvent = lambda e: log_event("resizeEvent", f"{e.size().width()}x{e.size().height()}")

probe_results = {}

def capture_if_ready():
    if probe_results.get("domCount", 0) > 30 and probe_results.get("bodyLength", 0) > 1000:
        app.processEvents()
        w.repaint()
        w.grab().save(str(RENDER_IMAGE))
        size = RENDER_IMAGE.stat().st_size
        if size < 50000: log_event("captureResult", f"FAIL. Size is {size} bytes (< 50KB)")
        else: log_event("captureResult", f"Size is {size} bytes")
    app.quit()

callbacks = []

def execute_dom_probe():
    js_probe = """
    (function() {
        var res = {
            readyState: document.readyState,
            bodyLength: document.body ? document.body.innerHTML.length : 0,
            domCount: document.querySelectorAll('*').length,
            cssCount: document.styleSheets.length,
            bodySample: document.body ? document.body.innerText.substring(0, 500) : ''
        };
        return JSON.stringify(res);
    })();
    """
    def on_dom(res):
        global probe_results
        log_event("domResult", str(res)[:100])
        try:
            probe_results = json.loads(res)
        except:
            probe_results = {}
        with open(DOM_PROBE, "w", encoding="utf-8") as f: json.dump(probe_results, f, indent=4)
        execute_bridge_probe()
    callbacks.append(on_dom)
    webview.page().runJavaScript(js_probe, on_dom)

def execute_bridge_probe():
    js_bridge = """
    (async function() {
        try {
            let res1 = await fetch('/api/videos');
            let t1 = await res1.text();
            return JSON.stringify({ videos: t1 });
        } catch(e) { return JSON.stringify({ error: e.toString() }); }
    })();
    """
    def on_bridge(res):
        with open(BRIDGE_PROBE, "w", encoding="utf-8") as f:
            f.write(res)
        capture_if_ready()
    callbacks.append(on_bridge)
    webview.page().runJavaScript(js_bridge, on_bridge)

def on_load_finished(ok):
    log_event("loadFinished", str(ok))
    if ok: QTimer.singleShot(1000, execute_dom_probe)

webview.loadFinished.connect(on_load_finished)
w.show()
QTimer.singleShot(15000, app.quit)
try:
    sys.exit(app.exec())
except BaseException as e:
    with open("crash.txt", "w") as f: f.write(str(e))
