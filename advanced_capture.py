import sys
import json
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
from ui.pages.watermark_remove_page import WatermarkRemovePage
from config.constants import DATA_DIR
from pathlib import Path

app = QApplication(sys.argv)
w = WatermarkRemovePage()
w.resize(1024, 768)
w.show()

artifacts_dir = Path(r"C:\Users\ASUS\.gemini\antigravity\brain\9228e2ba-62b3-49c8-8df9-e48ecb1067de")
artifacts_dir.mkdir(parents=True, exist_ok=True)

# We grab the WebSourcePage inside the stacked widget
web_page = w.web_page

def check_dom():
    js_code = """
    (function() {
        return {
            readyState: document.readyState,
            domCount: document.querySelectorAll('*').length,
            cssCount: document.styleSheets.length,
            bodySample: document.body ? document.body.innerText.substring(0, 300) : ''
        };
    })();
    """
    
    def callback(result):
        with open(artifacts_dir / "dom_probe.json", "w", encoding="utf-8") as f:
            json.dump(result, f, indent=4, ensure_ascii=False)
        print("dom_probe.json saved.")
        app.quit()
        
    web_page.webview.page().runJavaScript(js_code, callback)

# Wait 3 seconds to ensure chromium renders everything
QTimer.singleShot(3000, check_dom)

# Fallback kill
QTimer.singleShot(10000, app.quit)
sys.exit(app.exec())
