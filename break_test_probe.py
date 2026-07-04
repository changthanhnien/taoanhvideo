import sys
import os
import json
import time
from pathlib import Path
import PIL.Image

# Must be set BEFORE PySide6 imports
os.environ['QT_API'] = 'pyside6'

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer

ARTIFACTS_DIR = Path(r"C:\Users\ASUS\.gemini\antigravity\brain\9228e2ba-62b3-49c8-8df9-e48ecb1067de")
MEM_TRACE = ARTIFACTS_DIR / "memory_trace.csv"
BRIDGE_LOG = ARTIFACTS_DIR / "bridge_failure.log"
E2E_JSON = ARTIFACTS_DIR / "e2e_result.json"
CANVAS_JSON = ARTIFACTS_DIR / "canvas_events.json"
OUTPUT_PROBE = ARTIFACTS_DIR / "output_probe.json"

def get_ram_mb():
    try:
        val = os.popen(f'wmic process where processid={os.getpid()} get WorkingSetSize').read().split()[1]
        return int(val) / (1024*1024)
    except:
        return 0

# Track memory before PySide6 app start
ram_before = get_ram_mb()
with open(MEM_TRACE, "w") as f:
    f.write("Phase,Memory(MB)\n")
    f.write(f"Before Render,{ram_before:.2f}\n")

# Generate test input
test_img_path = str(ARTIFACTS_DIR / "test_input.jpg")
img = PIL.Image.new("RGB", (100, 100), color="blue")
img.save(test_img_path)

app = QApplication(sys.argv)
from ui.pages.watermark_remove_page import WatermarkRemovePage

w = WatermarkRemovePage()
w.resize(1600, 900)

webview = w.web_page.webview
callbacks = []

def run_js(js_code, callback):
    callbacks.append(callback)
    webview.page().runJavaScript(js_code, callback)

def log_mem(phase):
    m = get_ram_mb()
    with open(MEM_TRACE, "a") as f:
        f.write(f"{phase},{m:.2f}\n")

def perform_break_test():
    log_mem("After Render")
    
    # Task 4: Canvas Events
    js_canvas = """
    (function() {
        let c = document.querySelector('canvas');
        if(!c) return JSON.stringify({error: "No canvas found"});
        let rect = c.getBoundingClientRect();
        
        let ev1 = new MouseEvent('mousedown', {clientX: rect.left+10, clientY: rect.top+10, bubbles: true});
        c.dispatchEvent(ev1);
        
        let ev2 = new MouseEvent('mousemove', {clientX: rect.left+50, clientY: rect.top+50, bubbles: true});
        c.dispatchEvent(ev2);
        
        let ev3 = new MouseEvent('mouseup', {clientX: rect.left+50, clientY: rect.top+50, bubbles: true});
        c.dispatchEvent(ev3);
        
        return JSON.stringify({
            bbox: {width: rect.width, height: rect.height},
            coordinates: [rect.left+50, rect.top+50],
            state: "events dispatched"
        });
    })();
    """
    def on_canvas(res):
        with open(CANVAS_JSON, "w", encoding="utf-8") as f:
            f.write(res or '{"error": "empty res"}')
        test_bridge_failures()
        
    run_js(js_canvas, on_canvas)

def test_bridge_failures():
    js_bridge = """
    (async function() {
        let logs = [];
        try { let r1 = await fetch('/api/not_exist'); logs.push("not_exist: " + r1.status + " " + await r1.text()); } catch(e) { logs.push("not_exist error: " + e); }
        try { let r2 = await fetch('/api/preview'); logs.push("preview: " + r2.status + " " + await r2.text()); } catch(e) { logs.push("preview error: " + e); }
        try { let r3 = await fetch('/api/process_video'); logs.push("process_video: " + r3.status + " " + await r3.text()); } catch(e) { logs.push("process_video error: " + e); }
        return logs.join("\\n");
    })();
    """
    def on_bridge_fail(res):
        with open(BRIDGE_LOG, "w", encoding="utf-8") as f:
            f.write(res or "No response from bridge")
        test_e2e()
        
    run_js(js_bridge, on_bridge_fail)

def test_e2e():
    # End-To-End: Upload -> Preview -> Process -> Save Output
    js_e2e = f"""
    (async function() {{
        try {{
            // 1. Upload via bridge dispatch
            let uploadPayload = JSON.stringify({{ _files: [{{ path: "{test_img_path.replace(chr(92), '/')}", name: "test_input.jpg" }}] }});
            
            let uploadRes = await new Promise(resolve => {{
                window.qtBridge.dispatch('/api/upload', uploadPayload, resolve);
            }});
            let uData = JSON.parse(uploadRes);
            if(!uData.success) return JSON.stringify({{ error: "Upload failed" }});
            
            // 2. Preview
            let prevPayload = JSON.stringify({{ file_name: "test_input.jpg", method: "inpaint", shape: "rect", rect: [0,0,50,50], points: [] }});
            let prevRes = await new Promise(resolve => {{
                window.qtBridge.dispatch('/api/preview', prevPayload, resolve);
            }});
            
            // 3. Process
            let procPayload = JSON.stringify({{ file_name: "test_input.jpg", method: "inpaint", shape: "rect", rect: [0,0,50,50], points: [] }});
            let procRes = await new Promise(resolve => {{
                window.qtBridge.dispatch('/api/process_image', procPayload, resolve);
            }});
            
            return JSON.stringify({{ upload: uData, preview: JSON.parse(prevRes), process: JSON.parse(procRes) }});
        }} catch(e) {{
            return JSON.stringify({{ exception: e.toString() }});
        }}
    }})();
    """
    
    t0 = time.time()
    def on_e2e(res):
        log_mem("After Process")
        dt = time.time() - t0
        
        try:
            data = json.loads(res)
            out_file = data.get("process", {}).get("output_url", "")
            if out_file: out_file = str(Path(out_file).name)
        except:
            data = {"raw": res}
            out_file = ""
            
        out_path = Path("D:/Downloads/NAVTools.exe_extracted/NAVTools.exe_extracted/features/watermark_remove/source/uploads") / out_file if out_file else None
        
        e2e_out = {
            "input_path": test_img_path,
            "output_path": str(out_path) if out_path else "FAILED",
            "processing_time": f"{dt:.2f}s",
            "exception": data.get("exception", ""),
            "response_json": data
        }
        with open(E2E_JSON, "w", encoding="utf-8") as f:
            json.dump(e2e_out, f, indent=4)
            
        # Probe Output
        if out_path and out_path.exists():
            try:
                img = PIL.Image.open(out_path)
                w_img, h_img = img.size
                out_probe = {
                    "width": w_img, "height": h_img, 
                    "size_bytes": out_path.stat().st_size, "duration": 0
                }
            except Exception as e:
                out_probe = {"error": str(e)}
        else:
            out_probe = {"error": "Output not generated"}
            
        with open(OUTPUT_PROBE, "w", encoding="utf-8") as f:
            json.dump(out_probe, f, indent=4)
            
        app.quit()
        
    run_js(js_e2e, on_e2e)

def on_load_finished(ok):
    if ok: QTimer.singleShot(1500, perform_break_test)
    else: app.quit()

webview.loadFinished.connect(on_load_finished)
w.show()

# Timeout
QTimer.singleShot(25000, app.quit)

sys.exit(app.exec())
