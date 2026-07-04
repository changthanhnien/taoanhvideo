import sys, os, time
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
from pathlib import Path
from PIL import ImageGrab

os.environ['QT_API'] = 'pyside6'
sys.path.insert(0, os.path.abspath(r'd:\Downloads\NAVTools.exe_extracted\NAVTools.exe_extracted'))

from ui.pages.watermark_remove_page import WatermarkRemovePage

app = QApplication(sys.argv)
page = WatermarkRemovePage()
page.showMaximized()
page.raise_()
page.activateWindow()

ARTIFACTS_DIR = r'C:\Users\ASUS\.gemini\antigravity\brain\9228e2ba-62b3-49c8-8df9-e48ecb1067de'

def on_html_result(result):
    with open(os.path.join(ARTIFACTS_DIR, 'dom_dump.html'), 'w', encoding='utf-8') as f:
        f.write(result[:1000] if result else "")

def on_css_result(result):
    with open(os.path.join(ARTIFACTS_DIR, 'css_loaded.txt'), 'w', encoding='utf-8') as f:
        f.write(result if result else "")
    
    # Capture screen
    try:
        page.grab().save(os.path.join(ARTIFACTS_DIR, 'screenshot.png'))
    except Exception as e:
        print(e)
    print("Done CSS and Screenshot")
    app.quit()

def on_load_finished(ok):
    with open(os.path.join(ARTIFACTS_DIR, 'loaded_url.txt'), 'w', encoding='utf-8') as f:
        f.write(page.webview.url().toString())
    
    page.webview.page().runJavaScript('document.documentElement.outerHTML', 0, on_html_result)
    
    js_css = """
    Array.from(document.styleSheets).map(s => {
        try {
            return s.href ? s.href : (s.ownerNode ? s.ownerNode.outerHTML.substring(0, 50) : 'inline');
        } catch(e) {
            return 'cross-origin or error';
        }
    }).join('\\n')
    """
    # Wait a bit for CSS to render before screenshot
    QTimer.singleShot(2000, lambda: page.webview.page().runJavaScript(js_css, 0, on_css_result))

page.webview.loadFinished.connect(on_load_finished)
QTimer.singleShot(10000, app.quit) # Timeout fallback
app.exec()
