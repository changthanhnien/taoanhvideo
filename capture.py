import sys
import os
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
from ui.pages.watermark_remove_page import WatermarkRemovePage

app = QApplication(sys.argv)
w = WatermarkRemovePage()
w.resize(1024, 768)
w.show()

# Give QWebEngineView time to load the HTML
def capture_and_exit():
    w.grab().save("02_navtools_webview.png")
    app.quit()

QTimer.singleShot(2000, capture_and_exit)
sys.exit(app.exec())
