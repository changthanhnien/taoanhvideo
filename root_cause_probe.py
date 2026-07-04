import sys
import os
import json
import time
from pathlib import Path

os.environ['QT_API'] = 'pyside6'

from PySide6.QtCore import QObject, Slot, QTimer
from PySide6.QtWidgets import QApplication
import json

class ResultReceiver(QObject):
    def __init__(self):
        super().__init__()
        
    @Slot(str)
    def send_result(self, res):
        with open(ARTIFACTS_DIR / "root_cause_full.json", "w", encoding="utf-8") as f:
            f.write(res or 'null')
        try:
            data = json.loads(res)
        except:
            data = {"raw": res}
            
        with open(PING_JSON, "w") as f:
            f.write(str(data.get("ping_cb_error") or data.get("ping", "null")))
            
        with open(TRANSPORT_JSON, "w", encoding="utf-8") as f:
            json.dump(data.get("transport", {}), f, indent=4)
            
        app.quit()

receiver = ResultReceiver()

ARTIFACTS_DIR = Path(r"C:\Users\ASUS\.gemini\antigravity\brain\9228e2ba-62b3-49c8-8df9-e48ecb1067de")
TRACE_LOG = ARTIFACTS_DIR / "request_trace.log"
CHAIN_LOG = ARTIFACTS_DIR / "callback_chain.log"
PING_JSON = ARTIFACTS_DIR / "bridge_ping.json"
TRANSPORT_JSON = ARTIFACTS_DIR / "transport_test.json"
RETEST_JSON = ARTIFACTS_DIR / "bridge_retest.json"

app = QApplication(sys.argv)
from ui.pages.watermark_remove_page import WatermarkRemovePage

w = WatermarkRemovePage()
w.resize(800, 600)

webview = w.web_page.webview
callbacks = []

def run_js(code, cb):
    callbacks.append(cb)
    webview.page().runJavaScript(code, cb)

def run_all_tests():
    w.web_page.channel.registerObject("testReceiver", receiver)
    js_test = """
    (async function() {
        let results = { ping: null, transport: {} };
        
        // Ping
        try {
            await new Promise(resolve => {
                window.qtBridge.ping(function(res) {
                    results.ping = res;
                    resolve();
                });
            });
        } catch(e) { results.ping_error = e.toString(); }
        
        // Transport
        let sizes = [1024, 102400, 1048576]; // 1KB, 100KB, 1MB
        for(let s of sizes) {
            let payload = 'A'.repeat(s);
            try {
                await new Promise(resolve => {
                    window.qtBridge.transport_test("req_" + s, payload, function(res) {
                        results.transport[s] = res;
                        resolve();
                    });
                });
            } catch(e) {
                results.transport[s] = { error: e.toString() };
            }
        }
        
        window.testReceiver.send_result(JSON.stringify(results));
    })();
    """
    webview.page().runJavaScript(js_test)

webview.loadFinished.connect(lambda ok: QTimer.singleShot(1000, run_all_tests) if ok else app.quit())
w.show()
QTimer.singleShot(15000, app.quit)

sys.exit(app.exec())
