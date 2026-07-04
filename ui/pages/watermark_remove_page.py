from PySide6.QtWidgets import QWidget, QStackedLayout, QFileDialog
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEnginePage
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtCore import QUrl, QFile, QIODevice
from pathlib import Path
from features.watermark_remove.bridge.qt_bridge import WatermarkBridge

import logging
log = logging.getLogger(__name__)

class CustomWebEnginePage(QWebEnginePage):
    def __init__(self, bridge, parent=None):
        super().__init__(parent)
        self.bridge = bridge

    def javaScriptConsoleMessage(self, level, message, lineNumber, sourceID):
        try:
            log.info(f"JS: {message} (Line {lineNumber})")
            print(f"JS: {message} (Line {lineNumber})".encode('utf-8', 'replace').decode('utf-8'))
        except Exception:
            pass

    def chooseFiles(self, mode, oldFiles, acceptedMimeTypes):
        dialog = QFileDialog()
        if mode == QWebEnginePage.FileSelectOpenMultiple:
            dialog.setFileMode(QFileDialog.ExistingFiles)
        else:
            dialog.setFileMode(QFileDialog.ExistingFile)
            
        if dialog.exec():
            files = dialog.selectedFiles()
            for f in files:
                p = Path(f)
                self.bridge.recent_files_cache[p.name] = str(p)
            return files
        return []

    def acceptNavigationRequest(self, url, _type, isMainFrame):
        url_str = url.toString()
        if "/api/download" in url_str:
            self._handle_download(url_str)
            return False
        return super().acceptNavigationRequest(url, _type, isMainFrame)

    def _handle_download(self, url_str):
        import os, zipfile, shutil
        from PySide6.QtWidgets import QFileDialog
        from config.constants import BASE_DIR, DEFAULT_VIDEO_OUTPUT
        
        uploads_dir = DEFAULT_VIDEO_OUTPUT
        
        if url_str.endswith("/api/download_all"):
            path, _ = QFileDialog.getSaveFileName(self.view(), "Lưu tất cả (ZIP)", "processed_videos.zip", "ZIP Files (*.zip)")
            if not path:
                return
            with zipfile.ZipFile(path, 'w') as zf:
                for root, dirs, files in os.walk(str(uploads_dir)):
                    for file in files:
                        if "_no_watermark" in file:
                            zf.write(os.path.join(root, file), file)
        elif "/api/download/" in url_str:
            import urllib.parse
            filename = urllib.parse.unquote(url_str.split("/")[-1].split("?")[0])
            path, _ = QFileDialog.getSaveFileName(self.view(), "Lưu video", filename, "Video Files (*.mp4 *.webm *.mov *.avi)")
            if not path:
                return
            src_file = os.path.join(str(uploads_dir), filename)
            if os.path.exists(src_file):
                shutil.copy2(src_file, path)


class WatermarkRemovePage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        import time
        import json
        self.t_widget_created = time.perf_counter()
        self.t_ui_initialized = 0
        self.t_first_paint = 0
        self.t_page_visible = 0
        self.t_navigation_clicked = 0
        
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QColor
        
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("WatermarkRemovePage { background-color: #0e1015; } QWebEngineView { background: transparent; border: none; }")
        
        # QStackedLayout to overlay cover and webview
        self.stacked_layout = QStackedLayout(self)
        self.stacked_layout.setContentsMargins(0, 0, 0, 0)
        
        # Cover/loading placeholder matching dark theme
        self.loading_cover = QWidget(self)
        self.loading_cover.setStyleSheet("background-color: #0e1015;")
        self.stacked_layout.addWidget(self.loading_cover)
        
        self.webview = QWebEngineView(self)
        self.stacked_layout.addWidget(self.webview)
        self.stacked_layout.setCurrentIndex(1) # Show webview immediately
        
        # Expose Python Bridge
        self.bridge = WatermarkBridge(self)
        
        # Custom page to intercept file dialogs
        self.custom_page = CustomWebEnginePage(self.bridge, self.webview)
        
        # Complete anti-flicker for QWebEngineView
        self.custom_page.setBackgroundColor(Qt.transparent)
        self.webview.setAttribute(Qt.WA_TranslucentBackground, True)
        self.webview.setAttribute(Qt.WA_OpaquePaintEvent, False)
        
        self.webview.setPage(self.custom_page)
        
        # Force initial size to avoid resize delay when shown
        self.webview.resize(1920, 1080)
        
        # Enable local file access
        self.webview.settings().setAttribute(self.webview.settings().WebAttribute.LocalContentCanAccessRemoteUrls, True)
        self.webview.settings().setAttribute(self.webview.settings().WebAttribute.LocalContentCanAccessFileUrls, True)
        
        # Setup WebChannel
        self.channel = QWebChannel(self)
        self.webview.page().setWebChannel(self.channel)
        self.channel.registerObject("qtBridge", self.bridge)
        
        source_dir = Path(__file__).resolve().parent.parent.parent / "features" / "watermark_remove" / "source"
        index_path = source_dir / "templates" / "index.html"
        
        with open(index_path, "r", encoding="utf-8") as f:
            html = f.read()
            
        # MAPPING paths
        html = html.replace('"/static/', '"static/').replace('"/uploads/', '"uploads/')
        
        # Read buildin qwebchannel.js from Qt Resources to avoid CORS/qrc blocking
        qwebchannel_js = ""
        qfile = QFile(":/qtwebchannel/qwebchannel.js")
        if qfile.open(QIODevice.ReadOnly):
            qwebchannel_js = bytes(qfile.readAll()).decode("utf-8")
            qfile.close()
        else:
            log.warning("Could not read virtual :/qtwebchannel/qwebchannel.js resource")
            
        bridge_dir = Path(__file__).resolve().parent.parent.parent / "features" / "watermark_remove" / "bridge"
        api_shim_path = bridge_dir / "api_shim.js"
        with open(api_shim_path, "r", encoding="utf-8") as fs:
            shim_code = fs.read()
            
        from config.constants import BASE_DIR, DEFAULT_VIDEO_OUTPUT, DATA_DIR
        uploads_dir = DEFAULT_VIDEO_OUTPUT
        uploads_url = "file:///" + str(uploads_dir).replace("\\", "/")
        
        injection = f"""
        <script>window.NAV_UPLOADS_URL = '{uploads_url}';</script>
        <script>{qwebchannel_js}</script>
        <script>{shim_code}</script>
        """
        html = html.replace('<script src="static/main.js', injection + '\n<script src="static/main.js')
        
        try:
            with open(DATA_DIR / "debug_index.html", "w", encoding="utf-8") as f:
                f.write(html)
        except Exception:
            pass
            
        base_url = QUrl.fromLocalFile(source_dir.as_posix() + "/")
        self.webview.setHtml(html, base_url)
        self.webview.loadFinished.connect(self._on_load_finished)
        import time
        self.t_ui_initialized = time.perf_counter()

    def showEvent(self, event):
        super().showEvent(event)
        import time
        if not self.t_page_visible:
            self.t_page_visible = time.perf_counter()
            self._dump_timeline()

    def paintEvent(self, event):
        super().paintEvent(event)
        import time
        if not self.t_first_paint:
            self.t_first_paint = time.perf_counter()
            self._dump_timeline()

    def _dump_timeline(self):
        import json, os
        from config.constants import DATA_DIR
        # Only dump if we have both visible and paint (or at least visible if paint doesn't fire)
        if not self.t_page_visible:
            return
        
        try:
            # Pull navigation_clicked from a global file or set it somewhere
            try:
                click_time_file = DATA_DIR / "nav_click_time.txt"
                if click_time_file.exists():
                    with open(click_time_file, "r") as f:
                        self.t_navigation_clicked = float(f.read().strip())
            except Exception:
                pass

            data = {
                "navigation_clicked": self.t_navigation_clicked,
                "widget_created": getattr(self, "t_widget_created", 0),
                "ui_initialized": getattr(self, "t_ui_initialized", 0),
                "first_paint": getattr(self, "t_first_paint", 0),
                "page_visible": getattr(self, "t_page_visible", 0)
            }
            with open(DATA_DIR / "remove_logo_timeline.json", "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            log.warning(f"Could not dump timeline: {e}")

    def _on_load_finished(self, ok):
        if not ok:
            log.error("Failed to load index.html in WatermarkRemovePage")
            return
        from PySide6.QtCore import QTimer
        QTimer.singleShot(250, lambda: self.stacked_layout.setCurrentIndex(1))