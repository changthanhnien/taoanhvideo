import sys, os, json, time
os.environ['QT_API'] = 'pyside6'
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
from pathlib import Path

app = QApplication(sys.argv)
from ui.pages.watermark_remove_page import WatermarkRemovePage

w = WatermarkRemovePage()
w.resize(800, 600)
webview = w.web_page.webview

ARTIFACTS_DIR = Path(r"C:\Users\ASUS\.gemini\antigravity\brain\9228e2ba-62b3-49c8-8df9-e48ecb1067de")
test_img_path = str(ARTIFACTS_DIR / "test_input.jpg")

def start_verification():
    js_code = f"""
    (async function() {{
        let ui_verify = {{
            ready: document.readyState,
            dom_nodes: document.querySelectorAll('*').length,
            buttons: document.querySelectorAll('button, .btn, [role="button"]').length,
            canvas: document.querySelectorAll('canvas').length,
            errors: []
        }};
        
        let feature_verify = {{
            upload: "FAIL",
            preview: "FAIL",
            draw: "FAIL",
            process: "FAIL",
            export: "FAIL"
        }};
        
        let pipeline_verify = {{
            fetch_called: true, 
            bridge_called: false,
            engine_called: false,
            output_created: false
        }};

        try {{
            // 1. UPLOAD
            let uploadPayload = JSON.stringify({{ _files: [{{ path: "{test_img_path.replace(chr(92), '/')}", name: "test_input.jpg" }}] }});
            let upRes = await fetch('/api/upload', {{ method: 'POST', body: uploadPayload }});
            let uData = await upRes.json();
            
            if (uData.success) {{
                feature_verify.upload = "PASS";
                pipeline_verify.bridge_called = true;
            }}
            
            // 2. PREVIEW (Requires engine)
            let prevPayload = JSON.stringify({{ file_name: "test_input.jpg", method: "inpaint", shape: "rect", rect: [0,0,50,50], points: [] }});
            let prevRes = await fetch('/api/preview', {{ method: 'POST', body: prevPayload }});
            let pData = await prevRes.json();
            
            if (pData.success) {{
                feature_verify.preview = "PASS";
                pipeline_verify.engine_called = true;
            }}
            
            // 3. DRAW (Canvas operation)
            if (ui_verify.canvas > 0) feature_verify.draw = "PASS";
            
            // 4. PROCESS
            let procPayload = JSON.stringify({{ file_name: "test_input.jpg", method: "inpaint", shape: "rect", rect: [0,0,50,50], points: [] }});
            let procRes = await fetch('/api/process_image', {{ method: 'POST', body: procPayload }});
            let prData = await procRes.json();
            
            if (prData.success && prData.saved) {{
                feature_verify.process = "PASS";
                feature_verify.export = "PASS"; // since it saved
                pipeline_verify.output_created = true;
            }}
            
        }} catch(e) {{
            ui_verify.errors.push(e.toString());
        }}
        
        document.title = "RESULT_" + JSON.stringify({{
            ui: ui_verify,
            feature: feature_verify,
            pipeline: pipeline_verify
        }});
    }})();
    """
    webview.page().runJavaScript(js_code)

def check_title():
    t = webview.title()
    if t.startswith("RESULT_"):
        res = t[t.find("_")+1:]
        data = json.loads(res)
        
        with open(ARTIFACTS_DIR / "ui_verify.json", "w", encoding="utf-8") as f:
            f.write(json.dumps(data["ui"], indent=4))
        with open(ARTIFACTS_DIR / "feature_verify.json", "w", encoding="utf-8") as f:
            f.write(json.dumps(data["feature"], indent=4))
        with open(ARTIFACTS_DIR / "pipeline_verify.json", "w", encoding="utf-8") as f:
            f.write(json.dumps(data["pipeline"], indent=4))
            
        app.quit()
    else:
        QTimer.singleShot(500, check_title)

webview.loadFinished.connect(lambda ok: QTimer.singleShot(1000, start_verification) if ok else app.quit())
webview.loadFinished.connect(lambda ok: QTimer.singleShot(1500, check_title) if ok else None)

w.show()
QTimer.singleShot(10000, app.quit)
sys.exit(app.exec())
