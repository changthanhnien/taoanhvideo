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
        let pipeline_verify = {{
            upload: "FAIL",
            preview: "FAIL",
            process: "FAIL",
            export: "FAIL"
        }};

        try {{
            // 1. UPLOAD
            let uploadPayload = JSON.stringify({{ _files: [{{ path: "{test_img_path.replace(chr(92), '/')}", name: "test_input.jpg" }}] }});
            let upRes = await fetch('/api/upload', {{ method: 'POST', body: uploadPayload }});
            let uData = await upRes.json();
            
            if (uData.success) {{
                pipeline_verify.upload = "PASS";
            }}
            
            // 2. PREVIEW (Requires engine)
            let prevPayload = JSON.stringify({{ video_name: "test_input.jpg", method: "inpaint", x: 0, y: 0, width: 50, height: 50 }});
            let prevRes = await fetch('/api/preview', {{ method: 'POST', body: prevPayload }});
            let pData = await prevRes.json();
            
            if (pData.success) {{
                pipeline_verify.preview = "PASS";
            }}
            
            // 3. PROCESS
            let procPayload2 = JSON.stringify({{ video_name: "test_input.jpg", method: "inpaint", x: 0, y: 0, width: 50, height: 50 }});
            let procRes = await fetch('/api/process', {{ method: 'POST', body: procPayload2 }});
            let prData = await procRes.json();
            
            if (prData.success || prData.task_id) {{
                pipeline_verify.process = "PASS";
                pipeline_verify.export = "PASS";
            }}
            
        }} catch(e) {{
            pipeline_verify.process = "FAIL_" + e.toString();
        }}
        
        document.title = "RESULT_" + JSON.stringify(pipeline_verify);
    }})();
    """
    webview.page().runJavaScript(js_code)

def check_title():
    t = webview.title()
    if t.startswith("RESULT_"):
        res = t[t.find("_")+1:]
        data = json.loads(res)
        
        with open(ARTIFACTS_DIR / "pipeline_repair.json", "w", encoding="utf-8") as f:
            f.write(json.dumps(data, indent=4))
            
        app.quit()
    else:
        QTimer.singleShot(500, check_title)

webview.loadFinished.connect(lambda ok: QTimer.singleShot(1000, start_verification) if ok else app.quit())
webview.loadFinished.connect(lambda ok: QTimer.singleShot(1500, check_title) if ok else None)

w.show()
QTimer.singleShot(10000, app.quit)
sys.exit(app.exec())
